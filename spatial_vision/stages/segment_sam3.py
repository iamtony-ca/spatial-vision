"""M4 — segment 스테이지: SAM 3 백엔드 (텍스트 concept prompt).

    envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 \
        --in runs/sim01 --out runs/sim01_sam3 --target full \
        --prompt "white plastic wafer carrier box"

★ ISM 과의 근본적 차이
    ISM 은 **CAD 를 안다**(템플릿 매칭). SAM3 는 **말만 안다**(open-vocabulary). 그래서 이 비교는
    "CAD 를 쓰는 것이 실제로 값을 하는가"를 재는 실험이다 — 특히 top flange 처럼 표준 명칭이 없는
    부분에서. CONSUMER_6DPOSE.md §2.7.4 의 관찰("SAM3 는 top-flange-only 분리가 어렵다")을
    sim GT 로 정량 재확인하는 것이 M4 의 목적 중 하나다(PIPELINE_PLAN §M4).

★ 가중치는 로컬 경로로 준다
    `build_sam3_image_model()` 기본값은 HF 에서 받는데(gated) 우리는 weights/sam3/sam3.pt 를 이미 갖고
    있다 → `checkpoint_path=..., load_from_HF=False` 로 런타임 HF 인증을 없앤다(RESULTS.md § M0).

출력 (PIPELINE_PLAN.md §4 계약)
    <out>/frame_XXXX/  mask_<target>.png  det_<target>.json  meta_segment_<target>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import shutil

import cv2
import numpy as np

VISION_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CKPT = VISION_ROOT / "weights/sam3/sam3.pt"

# 기본 프롬프트 — sim01 4프레임에서 탐색한 실측 최선 (RESULTS.md § M4 의 프롬프트 표).
# ⚠️ 도메인 용어는 통하지 않는다: "wafer carrier"·"flange"·"plastic container" 는 confidence 를
# 0.1 까지 낮춰도 **검출 0건**이다(임계값 문제가 아니라 개념 자체를 못 잡는다).
# 일반적 시각 서술("white plastic box")로 가야 한다 — 이 성질이 SAM3 를 쓸 때의 실질적 제약이다.
DEFAULT_PROMPTS = {
    "full": "white plastic box",
    "flange": "circle on top of the box",
}
DEFAULT_CONFIDENCE = 0.3  # 0.5 는 일부 프레임을 통째로 놓친다(frame_0002 'box' 등)


def build_video(checkpoint_path: Path):
    """SAM3 **비디오** 모델 — 사전 제작 참조 이미지(exemplar)를 쓰는 유일한 경로.

    image processor 의 `add_geometric_prompt` 는 박스를 **지금 set_image 한 이미지** 위에서
    해석한다(좌표만 저장한다 — `Prompt(box_embeddings=boxes_cxcywh)`). 즉 "이 이미지의 이 영역"
    이지 "이렇게 생긴 것" 이 아니다. 사전 이미지의 박스를 쓰려면 참조와 질의를 **한 시퀀스**로
    묶어 비디오 경로로 전파해야 한다.
    """
    from sam3.model_builder import build_sam3_video_model

    return build_sam3_video_model(checkpoint_path=str(checkpoint_path), load_from_HF=False)


def _run_seq(model, seq, box_xywh, work: Path):
    """[참조..., 질의] 시퀀스를 전파해 **마지막 프레임**의 마스크를 얻는다."""
    import torch

    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for i, srcp in enumerate(seq):
        cv2.imwrite(str(work / f"{i:05d}.jpg"), cv2.imread(str(srcp)))
    st = model.init_state(resource_path=str(work))
    with torch.autocast("cuda", dtype=torch.bfloat16):
        model.add_prompt(st, frame_idx=0,
                         boxes_xywh=torch.tensor([box_xywh], dtype=torch.float32),
                         box_labels=torch.tensor([1]))
        res = {fi: d for fi, d in model.propagate_in_video(st, start_frame_idx=0)}
    out = res[len(seq) - 1]
    M = np.asarray(out["out_binary_masks"])
    if M.size == 0:
        return None, 0.0
    M = (M > 0).reshape(-1, *M.shape[-2:])
    probs = np.asarray(out.get("out_probs", np.ones(len(M)))).reshape(-1)
    k = int(np.argmax(probs)) if len(probs) == len(M) else 0
    return M[k], float(probs[k]) if len(probs) else 1.0


def segment_frame_refs_independent(model, rgb_path: Path, refs: list, work: Path, fuse: str,
                                   save_dir: Path | None = None):
    """★ 참조마다 **독립 질의**(사슬 길이 2)를 돌리고 결과를 융합한다.

    기본 경로(`segment_frame_refs`)는 참조를 **한 사슬**로 잇고 박스를 frame 0 에만 건다
    (`add_prompt` 가 매번 reset 한다). 참조가 길수록 추적 사슬이 끊길 확률이 늘어
    "2~3장이 최적, 5장은 오히려 나빠진다" 는 결과가 나왔다 — 이는 **참조 수의 한계가 아니라
    사슬 방식의 한계**라는 가설을 검정하기 위한 경로다. 각 질의가 독립이므로 참조 수에 비례해
    비용은 늘지만 사슬이 끊기지 않는다.
    """
    masks, scores = [], []
    for i, r in enumerate(refs):
        m, s = _run_seq(model, [r["_img"], rgb_path], r["box_xywh_norm"], work)
        if save_dir is not None:
            # 참조별 마스크를 남겨 두면 **어떤 부분집합의 융합이든 재추론 없이** 평가할 수 있다.
            save_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(save_dir / f"ref{i:03d}.png"),
                        (m.astype(np.uint8) * 255) if m is not None else
                        np.zeros((1, 1), np.uint8))
        if m is not None:
            masks.append(m); scores.append(s)
    if not masks:
        return None, 0.0, None, 0
    M = np.stack(masks)
    if fuse == "vote":                      # 픽셀별 과반 — 독립 추정의 정석 융합
        best = M.sum(axis=0) * 2 > len(M)
    elif fuse == "union":
        best = M.any(axis=0)
    else:                                   # best-score
        best = M[int(np.argmax(scores))]
    ys, xs = np.nonzero(best)
    box = [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())] if len(xs) else None
    return best, float(np.mean(scores)), box, len(M)


def segment_frame_refs(model, rgb_path: Path, refs: list, work: Path):
    """참조 N장 + 질의 1장을 **한 시퀀스**로 만들어 마지막 프레임의 마스크를 얻는다."""
    import torch

    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    seq = [r["_img"] for r in refs] + [rgb_path]
    for i, srcp in enumerate(seq):
        cv2.imwrite(str(work / f"{i:05d}.jpg"), cv2.imread(str(srcp)))

    st = model.init_state(resource_path=str(work))
    with torch.autocast("cuda", dtype=torch.bfloat16):
        model.add_prompt(st, frame_idx=0,
                         boxes_xywh=torch.tensor([refs[0]["box_xywh_norm"]], dtype=torch.float32),
                         box_labels=torch.tensor([1]))
        res = {fi: d for fi, d in model.propagate_in_video(st, start_frame_idx=0)}
    out = res[len(seq) - 1]
    M = np.asarray(out["out_binary_masks"])
    if M.size == 0:
        return None, 0.0, None, 0
    M = (M > 0).reshape(-1, *M.shape[-2:])
    probs = np.asarray(out.get("out_probs", np.ones(len(M)))).reshape(-1)
    k = int(np.argmax(probs)) if len(probs) == len(M) else 0
    ys, xs = np.nonzero(M[k])
    box = [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())] if len(xs) else None
    return M[k], float(probs[k]) if len(probs) else 1.0, box, len(M)


def build(checkpoint_path: Path, confidence: float):
    import torch
    from sam3.model_builder import build_sam3_image_model
    from sam3.model.sam3_image_processor import Sam3Processor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam3_image_model(
        device=device, checkpoint_path=str(checkpoint_path), load_from_HF=False)
    return Sam3Processor(model, device=device, confidence_threshold=confidence), device


def segment_frame(processor, rgb_path: Path, prompt: str, merge: bool, select: str = "score",
                  box: tuple | None = None, use_text: bool = True, min_area_frac: float = 0.3):
    """→ (mask bool HxW | None, score, bbox, n_instances).

    SAM3 는 concept 에 맞는 **인스턴스 여러 개**를 낸다.

    ★ 동일 인스턴스가 여러 개면 "어느 것이 타깃인가" 는 **분할 문제가 아니라 선택 문제**다.
      프롬프트는 모든 FOUP 에 똑같이 맞으므로 점수 최대값은 사실상 임의 선택이 된다
      (실측: distractor FOUP 이 있는 씬에서 오선택 45%). 카메라가 타깃을 겨누고 있다는
      씬 규약을 쓰면 **영상 중심에 가장 가까운 인스턴스**가 타깃이다 → `--select center`.
        score  : 최고 점수 (기본, 단일 객체 씬용)
        center : 영상 중심에 가장 가까운 인스턴스
        largest: 면적 최대
    """
    import torch
    from PIL import Image

    image = Image.open(rgb_path).convert("RGB")
    # ⚠️ SAM3 는 **bf16 autocast 안에서 돌아야 한다.** 가중치 일부가 bf16 이라 fp32 입력이 들어가면
    # `mat1 and mat2 must have the same dtype` 로 죽는다. README 에는 없고 examples/*.ipynb 가
    # 노트북 전역에서 `torch.autocast("cuda", dtype=torch.bfloat16).__enter__()` 를 부른다.
    # 전역 진입은 다른 스테이지에 샐 수 있으므로 추론 구간에만 건다.
    with torch.autocast("cuda", dtype=torch.bfloat16):
        state = processor.set_image(image)
        out = None
        if use_text:
            out = processor.set_text_prompt(state=state, prompt=prompt)
        if box is not None:
            # ★ exemplar(박스) 프롬프트 — "이것" 이라고 직접 가리킨다.
            # 텍스트가 없어도 된다(processor 가 "visual" 더미를 넣고 기하 프롬프트만 쓴다).
            # 동일 인스턴스가 여럿일 때 **어느 것이 타깃인지**를 모델에 직접 알려주므로
            # 점수/중앙 같은 사후 선택 휴리스틱이 필요 없어진다.
            out = processor.add_geometric_prompt(box=list(box), label=True, state=state)
    if out is None:
        raise ValueError("텍스트도 박스도 주어지지 않았다")
    masks, boxes, scores = out["masks"], out["boxes"], out["scores"]

    n = 0 if masks is None else len(masks)
    if n == 0:
        return None, 0.0, None, 0

    # autocast 안에서 나온 텐서는 bf16 일 수 있고 numpy 는 bf16 을 모른다 → float() 를 거친다.
    def _np(x):
        return np.asarray(x.detach().float().cpu()) if hasattr(x, "detach") else np.asarray(x)

    m, s, b = _np(masks), _np(scores).reshape(-1), _np(boxes)
    m = m.squeeze(1) if m.ndim == 4 else m
    m = m > 0.5 if m.dtype != bool else m

    if merge:
        return m.astype(bool).any(axis=0), float(s.max()), b[int(s.argmax())].tolist(), n

    from spatial_vision.contracts import select_index

    k = select_index(m, s, select, min_area_frac)
    return m[k].astype(bool), float(s[k]), b[k].tolist(), n


def _make_box(args, frame_dir: Path, rng):
    """exemplar 박스 [cx,cy,w,h] (0~1 정규화). SAM3 규약이 정규화 center-size 형식이다."""
    if not args.box_source:
        return None
    img = cv2.imread(str(frame_dir / "left.png"), cv2.IMREAD_GRAYSCALE)
    H, W = img.shape
    if args.box_source == "center":
        return (0.5, 0.5, args.box_frac, args.box_frac)
    gt = cv2.imread(str(frame_dir / "mask_full.png"), cv2.IMREAD_GRAYSCALE)
    if gt is None or not (gt > 127).any():
        return (0.5, 0.5, args.box_frac, args.box_frac)
    ys, xs = np.nonzero(gt > 127)
    cx, cy = (xs.min() + xs.max()) / 2 / W, (ys.min() + ys.max()) / 2 / H
    w, h = (xs.max() - xs.min()) / W, (ys.max() - ys.min()) / H
    if args.box_source == "gt-jitter":
        j = args.box_jitter
        cx += float(rng.uniform(-j, j)) * w
        cy += float(rng.uniform(-j, j)) * h
        w *= float(rng.uniform(1 - j, 1 + j))
        h *= float(rng.uniform(1 - j, 1 + j))
    return (float(np.clip(cx, 0, 1)), float(np.clip(cy, 0, 1)),
            float(np.clip(w, 0.01, 1)), float(np.clip(h, 0.01, 1)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="segment 스테이지 (SAM 3)")
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--out", dest="out_dir", required=True)
    ap.add_argument("--target", required=True, choices=["full", "flange"])
    ap.add_argument("--prompt", default=None, help=f"내장 기본값: {DEFAULT_PROMPTS}")
    ap.add_argument("--prompts-file", default=None,
                    help="객체별 프롬프트 JSON — {target: {prompt, confidence}}. "
                         "프롬프트는 객체 형상에 딸린 값이라 코드가 아니라 객체 디렉토리에 둔다 "
                         "(예: assets/obj/<id>/sam3_prompts.json). --prompt 가 있으면 그쪽이 우선.")
    ap.add_argument("--ckpt", default=str(DEFAULT_CKPT))
    ap.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE)
    ap.add_argument("--merge", action="store_true", help="검출 인스턴스를 전부 합집합")
    ap.add_argument("--select", default="score", choices=["score", "center", "largest"],
                    help="인스턴스가 여럿일 때 타깃을 고르는 규칙 (동일 인스턴스 씬에서 결정적)")
    ap.add_argument("--refs", default=None,
                    help="사전 제작 참조 세트 디렉토리(assets/obj/<id>/sam3_refs). "
                         "주면 텍스트/같은이미지박스 대신 **exemplar 전파 경로**를 쓴다")
    ap.add_argument("--n-refs", type=int, default=3, help="쓸 참조 장수 (사슬 방식의 실측 최적 2~3)")
    ap.add_argument("--refs-mode", default="chain", choices=["chain", "independent"],
                    help="chain=참조를 한 시퀀스로 잇는다(기본) / independent=참조마다 따로 질의 후 융합")
    ap.add_argument("--refs-fuse", default="vote", choices=["vote", "union", "best"],
                    help="refs-mode=independent 의 융합 규칙")
    ap.add_argument("--save-per-ref", action="store_true",
                    help="참조별 마스크를 frame_*/per_ref/ 에 저장 (참조 세트 선택 실험용)")
    ap.add_argument("--select-min-area-frac", type=float, default=0.3,
                    help="center 규칙에서 후보를 거르는 최소 면적(최대 후보 대비)")
    ap.add_argument("--box-source", default=None, choices=["center", "gt", "gt-jitter"],
                    help="exemplar(박스) 프롬프트의 출처. "
                         "center=화면 중앙 고정 박스(카메라가 타깃을 겨눈다는 전제), "
                         "gt=GT bbox(상한 참조용), gt-jitter=GT bbox 에 지정 오차를 섞은 것(현실적)")
    ap.add_argument("--box-frac", type=float, default=0.45, help="center 박스의 화면 대비 크기")
    ap.add_argument("--box-jitter", type=float, default=0.2,
                    help="gt-jitter: 중심 이동(bbox 크기 대비)·크기 배율의 랜덤 폭")
    ap.add_argument("--no-text", action="store_true", help="텍스트 없이 박스만 사용")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    if in_dir.resolve() == out_dir.resolve():
        print("❌ --out 이 --in 과 같다. 예측이 GT 마스크를 덮어쓴다.", file=sys.stderr)
        return 2

    # 우선순위: --prompt > --prompts-file > 내장 기본값
    file_cfg = {}
    if args.prompts_file:
        file_cfg = json.loads(Path(args.prompts_file).read_text()).get(args.target, {})
    prompt = args.prompt or file_cfg.get("prompt") or DEFAULT_PROMPTS[args.target]
    confidence = args.confidence
    if args.confidence == DEFAULT_CONFIDENCE and "confidence" in file_cfg:
        confidence = float(file_cfg["confidence"])
    frames = sorted([p for p in in_dir.glob("frame_*") if p.is_dir()]) or [in_dir]
    print(f'== SAM 3 | target={args.target} | {len(frames)} 프레임 | conf={confidence} | prompt="{prompt}"')

    t0 = time.time()
    use_refs = bool(args.refs)
    refs = []
    if use_refs:
        rd = Path(args.refs)
        meta_r = json.loads((rd / "refs.json").read_text())
        refs = meta_r["refs"][:args.n_refs]
        for r in refs:
            r["_img"] = rd / r["image"]
        model = build_video(Path(args.ckpt))
        device = "cuda"
        print(f"  exemplar 경로 | 참조 {len(refs)}장 ← {rd}")
    else:
        processor, device = build(Path(args.ckpt), confidence)
    print(f"  모델 초기화 {time.time()-t0:.1f}s ({device})")
    work = VISION_ROOT / ".cache/sam3_refseq"

    rng = np.random.default_rng(args.seed)
    results, t_frames = [], []
    for f in frames:
        ts = time.time()
        if use_refs:
            pbox = None
            if args.refs_mode == "independent":
                sd = (out_dir / f.name / "per_ref") if args.save_per_ref else None
                mask, score, box, n = segment_frame_refs_independent(
                    model, f / "left.png", refs, work, args.refs_fuse, sd)
            else:
                mask, score, box, n = segment_frame_refs(model, f / "left.png", refs, work)
        else:
            pbox = _make_box(args, f, rng)
            mask, score, box, n = segment_frame(processor, f / "left.png", prompt, args.merge,
                                                args.select, pbox, not args.no_text,
                                                args.select_min_area_frac)
        dt = (time.time() - ts) * 1000
        t_frames.append(dt)

        od = out_dir / f.name if f != in_dir else out_dir
        od.mkdir(parents=True, exist_ok=True)
        h, w = cv2.imread(str(f / "left.png"), cv2.IMREAD_GRAYSCALE).shape
        area = 0 if mask is None else int(mask.sum())
        cv2.imwrite(str(od / f"mask_{args.target}.png"),
                    (np.zeros((h, w), np.uint8) if mask is None else (mask * 255).astype(np.uint8)))
        (od / f"det_{args.target}.json").write_text(json.dumps(
            {"score": score, "bbox": box, "area_px": area, "n_instances": n,
             "prompt": prompt, "found": mask is not None}, indent=2))
        results.append({"frame": f.name, "score": score, "area_px": area, "n_instances": n,
                        "prompt_box": list(pbox) if pbox else None})
        print(f"  {f.name}: {dt:7.0f}ms  score {score:.3f}  area {area:6d}px  instances {n}")

    meta = {
        "stage": "segment", "backend": "sam3", "target": args.target, "prompt": prompt,
        "license": "SAM License (2025-11-19) — 상업 금지 조항 없음, Trade Controls 제약",
        "checkpoint": args.ckpt, "confidence_threshold": confidence, "merge": args.merge,
        "mode": "exemplar_refs" if args.refs else ("box" if args.box_source else "text"),
        "refs": args.refs, "n_refs": args.n_refs,
        "refs_mode": args.refs_mode, "refs_fuse": args.refs_fuse,
        "select": args.select, "box_source": args.box_source,
        "box_frac": args.box_frac, "box_jitter": args.box_jitter, "use_text": not args.no_text,
        "prompts_file": args.prompts_file,
        "mean_ms": float(np.mean(t_frames)), "frames": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"meta_segment_{args.target}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"  평균 {np.mean(t_frames):.0f}ms/frame → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
