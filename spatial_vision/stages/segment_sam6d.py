"""M4 — segment 스테이지: SAM-6D ISM 백엔드 (CAD 템플릿 기반 zero-shot).

    envs/seg_sam6d/bin/python -m spatial_vision.stages.segment_sam6d \
        --in runs/sim01 --out runs/sim01_ism --target full \
        --templates assets/obj/foup_300/ism_full --cad assets/obj/foup_300/full.ply

★ 왜 스크립트를 부르지 않고 in-process 로 감싸나
    ISM 은 SAM vit_h(2.4GB) + DINOv2 를 올린다. 프레임마다 프로세스를 띄우면 초기화가 지배한다
    (M3 에서 ONNX 세션 31s 로 같은 교훈을 얻었다). 모델·템플릿을 한 번 만들고 프레임을 돌린다.
    ISM 은 MIT(CNOS 유래)라 stereo_onnx 와 달리 repo 코드를 써도 라이선스 문제가 없다.

★ 단위 (코드로 확인, 추측 아님)
    utils/trimesh_utils.py:87  `Z = depth * scale / 1000`   → depth 는 mm, 결과는 m
    run_inference_custom.py:190 `mesh.sample(2048)/1000.0`  → CAD 는 mm
    우리 계약도 mm 이므로 **depth_scale = 1.0**. cam.json 은 fx/fy/cx/cy 라 ISM 의 cam_K 로 조립해 넘긴다.

★ full / flange 는 템플릿 세트를 갈아끼워 같은 코드로 처리한다
    ISM 은 "이 CAD 처럼 생긴 것"을 찾으므로, top_flange.ply 로 렌더한 템플릿을 주면 flange 를 찾는다.
    → PIPELINE_PLAN §M4 의 "두 모델 × 두 타깃" 비교가 성립한다.

    ⚠️ **다만 flange 전용 템플릿은 실사용에 쓰지 말 것.** 실측 오선택 **23/40**(IoU 0.382) —
    맞힌 프레임의 IoU 는 0.898 로 멀쩡하니 **분할이 아니라 선택**이 깨진다. flange 만 떼면
    "판때기 + 구멍" 이라 distractor FOUP 의 flange·배경 평면과 구별되지 않는다.
    flange 마스크가 필요하면 **전체 pose 에서 투영**(`pose_fp --flange-mask-from pose`)하거나
    SAM3 의 flange 참조(오선택 0/40, IoU 0.879)를 쓴다. (RESULTS.md § M5 확장 §4)

출력 (PIPELINE_PLAN.md §4 계약)
    <out>/frame_XXXX/  mask_<target>.png  det_<target>.json  meta_segment.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import cv2
import numpy as np

VISION_ROOT = Path(__file__).resolve().parents[2]
ISM_DIR = VISION_ROOT / "third_party/SAM-6D/SAM-6D/Instance_Segmentation_Model"


@contextmanager
def _in_ism_dir():
    """ISM 은 hydra `config_path="configs"` 를 상대경로로 쓰고 `from model...` 로 자기 패키지를
    import 한다 → cwd 와 sys.path 가 ISM 디렉토리여야 한다. 우리 경로 규약을 깨지 않도록 국소화한다."""
    prev = os.getcwd()
    os.chdir(ISM_DIR)
    if str(ISM_DIR) not in sys.path:
        sys.path.insert(0, str(ISM_DIR))
    try:
        yield
    finally:
        os.chdir(prev)


def build_model(stability_score_thresh: float = 0.97):
    import torch
    from hydra import initialize_config_dir, compose
    from hydra.utils import instantiate

    # ⚠️ hydra 의 `initialize(config_path=...)` 는 cwd 가 아니라 **호출한 모듈 파일 기준**으로 푼다.
    # 우리는 ISM 밖에서 부르므로 상대경로판을 쓰면 spatial_vision/stages/configs 를 찾다가 죽는다.
    # → 절대경로판(initialize_config_dir). chdir 은 여전히 필요하다: 체크포인트 경로가 상대경로다.
    with _in_ism_dir():
        with initialize_config_dir(version_base=None, config_dir=str(ISM_DIR / "configs")):
            cfg = compose(config_name="run_inference.yaml")
        with initialize_config_dir(version_base=None, config_dir=str(ISM_DIR / "configs/model")):
            cfg.model = compose(config_name="ISM_sam.yaml")
        cfg.model.segmentor_model.stability_score_thresh = stability_score_thresh
        model = instantiate(cfg.model)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.descriptor_model.model = model.descriptor_model.model.to(device)
    model.descriptor_model.model.device = device
    if hasattr(model.segmentor_model, "predictor"):
        model.segmentor_model.predictor.model = model.segmentor_model.predictor.model.to(device)
    else:
        model.segmentor_model.model.setup_model(device=device, verbose=True)
    return model, device


def load_templates(model, template_dir: Path, cad_path: Path, device):
    """템플릿 디스크립터 + CAD 포인트클라우드를 model.ref_data 에 채운다 (프레임마다 재계산 금지)."""
    import torch
    import trimesh
    from PIL import Image

    with _in_ism_dir():
        from utils.bbox_utils import CropResizePad
        from utils.poses.pose_utils import (
            get_obj_poses_from_template_level,
            load_index_level_in_level2,
        )

    tdir = Path(template_dir) / "templates"
    n = len(sorted(tdir.glob("xyz_*.npy")))
    if n == 0:
        raise FileNotFoundError(f"템플릿이 없다: {tdir} (blenderproc 렌더를 먼저 돌린다)")

    boxes, masks, templates = [], [], []
    for idx in range(n):
        image = Image.open(tdir / f"rgb_{idx}.png")
        mask = Image.open(tdir / f"mask_{idx}.png")
        boxes.append(mask.getbbox())
        image = torch.from_numpy(np.array(image.convert("RGB")) / 255).float()
        mask = torch.from_numpy(np.array(mask.convert("L")) / 255).float()
        templates.append(image * mask[:, :, None])
        masks.append(mask.unsqueeze(-1))

    templates = torch.stack(templates).permute(0, 3, 1, 2)
    masks = torch.stack(masks).permute(0, 3, 1, 2)
    boxes = torch.tensor(np.array(boxes))

    proc = CropResizePad(224)
    templates = proc(images=templates, boxes=boxes).to(device)
    masks_cropped = proc(images=masks, boxes=boxes).to(device)

    model.ref_data = {}
    model.ref_data["descriptors"] = model.descriptor_model.compute_features(
        templates, token_name="x_norm_clstoken").unsqueeze(0).data
    model.ref_data["appe_descriptors"] = model.descriptor_model.compute_masked_patch_feature(
        templates, masks_cropped[:, 0, :, :]).unsqueeze(0).data

    template_poses = get_obj_poses_from_template_level(level=2, pose_distribution="all")
    template_poses[:, :3, 3] *= 0.4
    poses = torch.tensor(template_poses).to(torch.float32).to(device)
    model.ref_data["poses"] = poses[load_index_level_in_level2(0, "all"), :, :]

    mesh = trimesh.load_mesh(str(cad_path))
    model_points = mesh.sample(2048).astype(np.float32) / 1000.0  # CAD 는 mm → m
    model.ref_data["pointcloud"] = torch.tensor(model_points).unsqueeze(0).data.to(device)
    return n


def segment_frame(model, device, rgb_path: Path, depth_mm: np.ndarray, K: np.ndarray,
                  select: str = "score", min_area_frac: float = 0.3,
                  ref_mask: np.ndarray | None = None):
    """한 프레임 → (best_mask bool HxW, score, bbox, n_proposals). 검출이 없으면 mask=None.

    ★ 동일 인스턴스가 여러 개면 점수 최대는 사실상 임의 선택이다(FOUP 3대가 다 같은 CAD 다).
      `center` 는 "카메라가 타깃을 겨눈다" 는 씬 규약으로 중앙에 가장 가까운 후보를 고른다
      — segment_sam3 와 같은 규칙. 실측: SAM3 에서 오선택 18/40 → 1/40.

    ★★ `exemplar` (F5) — **씬 규약에 기대지 않는 지정 수단.** ISM 의 제안·점수는 그대로 두고
      **선택만** 외부 exemplar 마스크(SAM3 참조 기반)와의 IoU 최대로 바꾼다. 마스크 자체는
      여전히 SAM 제안이므로 **마스크 품질은 변하지 않고 오선택만 사라진다**는 것이 예측이다
      (근거: SAM-6D `detector.py` — 제안은 RGB, depth 는 점수의 1/3).
    """
    import torch
    from PIL import Image

    with _in_ism_dir():
        from model.utils import Detections

    rgb = Image.open(rgb_path).convert("RGB")
    proposals = model.segmentor_model.generate_masks(np.array(rgb))
    detections = Detections(proposals)
    n_proposals = len(detections.masks)

    # 🔴 폭·높이가 0 인 제안을 걸러낸다. ISM 의 `CropResizePad` 가 그 상자로 crop 한 뒤
    #    `F.interpolate` 를 부르는데 빈 텐서에서 죽는다 —
    #    `RuntimeError: Input and output sizes should be greater than 0, but got input (H: 0, W: 30)`.
    #    상류(third_party) 는 손대지 않고 여기서 막는다. **한 프레임의 퇴화 제안 하나가
    #    스테이지 전체를 죽이면 안 된다** (실제로 n30 캡처 frame_0001 에서 났다).
    wh = detections.boxes[:, 2:] - detections.boxes[:, :2]
    keep = ((wh[:, 0] >= 1) & (wh[:, 1] >= 1)).nonzero(as_tuple=True)[0]
    if len(keep) < n_proposals:                     # 교훈 #21: 필터는 남은 개수를 반드시 로그로
        print(f"    ⚠️ 퇴화 제안 {n_proposals - len(keep)}개 제외 (폭 또는 높이 0) "
              f"→ {len(keep)}개", flush=True)
    if len(keep) == 0:
        return None, 0.0, None, n_proposals, select
    detections.filter(keep)

    q_desc, q_appe = model.descriptor_model.forward(np.array(rgb), detections)

    idx_sel, pred_idx_obj, semantic_score, best_template = model.compute_semantic_score(q_desc)
    if len(idx_sel) == 0:
        return None, 0.0, None, n_proposals, select
    detections.filter(idx_sel)
    q_appe = q_appe[idx_sel, :]

    appe_scores, ref_aux = model.compute_appearance_score(best_template, pred_idx_obj, q_appe)

    batch = {
        "depth": torch.from_numpy(depth_mm.astype(np.int32)).unsqueeze(0).to(device),
        "cam_intrinsic": torch.from_numpy(K).unsqueeze(0).to(device),
        # 우리 depth 는 이미 mm → scale 1.0 (utils/trimesh_utils.py:87 이 /1000 으로 m 변환)
        "depth_scale": torch.from_numpy(np.array(1.0)).unsqueeze(0).to(device),
    }
    image_uv = model.project_template_to_image(best_template, pred_idx_obj, batch, detections.masks)
    geo_score, visible_ratio = model.compute_geometric_score(
        image_uv, detections, q_appe, ref_aux, visible_thred=model.visible_thred)

    final = (semantic_score + appe_scores + geo_score * visible_ratio) / (1 + 1 + visible_ratio)
    from spatial_vision.contracts import select_index

    M = detections.masks.detach().cpu().numpy().astype(bool)
    S = final.detach().cpu().numpy()
    used = select
    if select == "exemplar":
        if ref_mask is None or not ref_mask.any():
            # 🔴 **조용히 넘어가면 안 된다.** 주석은 그렇게 적혀 있었는데 코드는 말없이 `score` 로
            #    후퇴하고 있었다(2026-08-20 실물에서 드러남). 그 결과 «exemplar 로 골랐다» 고
            #    믿게 되는데 실제로는 ISM 점수가 골랐고, **광각·원거리에서 배경을 집는다**
            #    (§34-10 오선택 14/120). 사용자가 «mask_full 은 멀쩡한데 50cm 에서 가장자리
            #    물체를 잡는다» 를 본 것이 정확히 이 경로다.
            #    → 후퇴는 그대로 하되 **반드시 알린다**(교훈 #21: 폴백은 «있다» 보다 «조용하다» 가 위험).
            used = "score(exemplar 비어서 후퇴)"
            print(f"    ⚠️ exemplar 마스크가 비었다 → **`score` 규칙으로 후퇴**한다. "
                  f"이 프레임의 선택은 SAM3 와 무관하며 배경을 집을 수 있다", flush=True)
            best = select_index(M, S, "score", min_area_frac)
        else:
            inter = (M & ref_mask[None]).sum(axis=(1, 2)).astype(np.float64)
            union = (M | ref_mask[None]).sum(axis=(1, 2)).astype(np.float64)
            best = int(np.argmax(inter / np.maximum(union, 1.0)))
    else:
        best = select_index(M, S, select, min_area_frac)
    mask = detections.masks[best].detach().cpu().numpy().astype(bool)
    box = detections.boxes[best].detach().cpu().numpy().tolist()
    return mask, float(final[best]), box, n_proposals, used


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="segment 스테이지 (SAM-6D ISM)")
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--out", dest="out_dir", required=True)
    ap.add_argument("--templates", required=True, help="blenderproc 렌더 출력 (templates/ 를 담은 디렉토리)")
    ap.add_argument("--cad", required=True, help="템플릿과 같은 메쉬 (mm)")
    ap.add_argument("--target", required=True, choices=["full", "flange"])
    ap.add_argument("--depth", default="gt", choices=["gt", "stereo"],
                    help="gt=depth_gt.npy (M4 를 depth 오차와 분리), stereo=depth.png")
    ap.add_argument("--depth-dir", default=None, help="stereo depth 를 다른 디렉토리에서 읽을 때")
    ap.add_argument("--stability-score-thresh", type=float, default=0.97)
    ap.add_argument("--select-min-area-frac", type=float, default=0.3,
                    help="center 규칙에서 후보를 거르는 최소 면적(최대 후보 대비)")
    ap.add_argument("--select", default="score", choices=["score", "center", "exemplar"],
                    help="인스턴스가 여럿일 때 타깃 선택 규칙 (동일 인스턴스 씬에서 결정적)")
    ap.add_argument("--exemplar-dir", default=None,
                    help="select=exemplar 용 — SAM3 exemplar 산출 런(frame_*/mask_<target>.png). "
                         "제안·점수는 ISM 그대로 두고 **선택만** 이 마스크와의 IoU 최대로 한다")
    args = ap.parse_args(argv)

    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    # GT 마스크와 파일명이 같다 — 같은 디렉토리에 쓰면 GT 를 조용히 덮어쓴다.
    if in_dir.resolve() == out_dir.resolve():
        print("❌ --out 이 --in 과 같다. 예측이 GT 마스크를 덮어쓴다. 다른 디렉토리를 쓴다.", file=sys.stderr)
        return 2

    frames = sorted([p for p in in_dir.glob("frame_*") if p.is_dir()]) or [in_dir]
    print(f"== SAM-6D ISM | target={args.target} | {len(frames)} 프레임 | depth={args.depth}")

    t0 = time.time()
    model, device = build_model(args.stability_score_thresh)
    n_tmpl = load_templates(model, Path(args.templates), Path(args.cad), device)
    print(f"  모델+템플릿({n_tmpl}뷰) 초기화 {time.time()-t0:.1f}s")

    results, t_frames = [], []
    for f in frames:
        cam = json.loads((f / "cam.json").read_text())
        K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], dtype=np.float64)

        if args.depth == "gt":
            depth_mm = np.load(f / "depth_gt.npy").astype(np.float64)
        else:
            dd = Path(args.depth_dir) / f.name if args.depth_dir else f
            depth_mm = cv2.imread(str(dd / "depth.png"), cv2.IMREAD_UNCHANGED).astype(np.float64)
        depth_mm = np.nan_to_num(depth_mm, nan=0.0, posinf=0.0, neginf=0.0)

        ref_mask = None
        if args.select == "exemplar":
            rp = Path(args.exemplar_dir) / f.name / f"mask_{args.target}.png"
            rm = cv2.imread(str(rp), cv2.IMREAD_GRAYSCALE) if rp.exists() else None
            ref_mask = (rm > 127) if rm is not None else None

        ts = time.time()
        mask, score, box, n_prop, sel_used = segment_frame(model, device, f / "left.png", depth_mm, K,
                                                 args.select, args.select_min_area_frac, ref_mask)
        dt = (time.time() - ts) * 1000
        t_frames.append(dt)

        od = out_dir / f.name if f != in_dir else out_dir
        od.mkdir(parents=True, exist_ok=True)
        area = 0 if mask is None else int(mask.sum())
        cv2.imwrite(str(od / f"mask_{args.target}.png"),
                    (np.zeros(depth_mm.shape, np.uint8) if mask is None else (mask * 255).astype(np.uint8)))
        (od / f"det_{args.target}.json").write_text(json.dumps(
            {"score": score, "bbox": box, "area_px": area, "n_proposals": n_prop,
             # ★ **어떤 선택 규칙이 실제로 쓰였는가** — exemplar 가 비면 score 로 후퇴하므로
             #   기록해 두지 않으면 «exemplar 로 골랐다» 고 오해하게 된다.
             "select_used": sel_used,
             "found": mask is not None}, indent=2))
        results.append({"frame": f.name, "score": score, "area_px": area,
                        "n_proposals": n_prop, "select_used": sel_used})
        print(f"  {f.name}: {dt:7.0f}ms  score {score:.3f}  area {area:6d}px  proposals {n_prop}")

    meta = {
        "stage": "segment", "backend": "sam6d_ism", "target": args.target,
        "segmentor": "sam_vit_h", "descriptor": "dinov2_vitl14",
        "license": "MIT (Instance_Segmentation_Model, CNOS 유래)",
        "templates": str(args.templates), "n_templates": n_tmpl, "cad": str(args.cad),
        "depth_source": args.depth, "depth_scale": 1.0, "select": args.select,
        "exemplar_dir": args.exemplar_dir,
        "stability_score_thresh": args.stability_score_thresh,
        "mean_ms": float(np.mean(t_frames)), "frames": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"meta_segment_{args.target}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"  평균 {np.mean(t_frames):.0f}ms/frame → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
