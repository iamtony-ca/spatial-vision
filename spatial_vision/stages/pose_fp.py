"""M5 — pose 스테이지: FoundationPose 2-stage.

    envs/pose/bin/python -m spatial_vision.stages.pose_fp \
        --in runs/semi01 --out runs/semi01_pose --obj assets/obj/foup_300_semi \
        --masks runs/semi01_sam3 --depth gt

⚠️ **실사용 기본값은 coarse(단일 단계)다. 2-stage 는 시험 후 기각됐다.**
    설계 의도는 "전체 형상으로 방향을 고정한 뒤 표준부(flange)로 정밀화" 였는데, 세 방식 모두
    **회전이 악화**됐다 — 같은 이미지 refine 0.349°→1.282°, flange 단독 18~24°,
    카메라 이동 + 초기값 전달 + refine 0.604°→3.432°. 원인은 공통으로 **flange 의 약한 회전 구속**이고
    초기값을 정확히 줘도 refine 이 회전을 끌고 나간다. 하이브리드(R=1차, t=2차)도 2차의 t 꼬리를
    물려받아 KPI 75% < 단일 단계 100% 다. (RESULTS.md § M5 확장 §6-7)
    → `--no-stage2` 가 실사용 경로. `--primary flange` / `--init-from` 은 **재현·연구용**으로 남긴다.

★ 단위·원점 (코드로 확인, 추측 아님)
    - FoundationPose 는 **미터**를 쓴다: `datareader.py:123` 이 depth PNG 를 `/1e3` 한다.
      우리 계약은 mm 이므로 mesh 와 depth 를 **0.001 배**해서 넣고, 나온 t 를 다시 mm 로 돌린다.
    - 반환 pose 는 **메쉬 파일 자기 원점 기준**이다: `estimater.py` 가
      `best_pose = poses[0] @ get_tf_to_centered_mesh()` 로 내부 centering 을 상쇄한다.
      → full.ply / top_flange.ply 가 같은 원점(M1 에서 검증)이므로 coarse pose 를 그대로 stage-2 초기값으로 쓴다.
    - stage-2 시딩은 `pose_last` 에 넣는데, 그건 **centered mesh 기준**이다 →
      `pose_last = cam_T_obj @ T(+model_center)` 로 되돌려 넣어야 한다.

★ flange 마스크는 두 경로를 비교한다
    seg  : M4 의 segmentation 결과 (신 CAD 에서 SAM3 IoU 0.954)
    pose : coarse pose 로 top_flange.ply 를 투영해 만든 마스크 (segmentation 불필요)
    어느 쪽이 pose 정확도에 유리한지는 수치로 답한다.

출력  <out>/frame_XXXX/  pose_coarse.json  pose_refined.json  (mask_flange_proj.png)  + meta_pose.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

VISION_ROOT = Path(__file__).resolve().parents[2]
FP_DIR = VISION_ROOT / "third_party/FoundationPose"

MM_TO_M = 0.001


def _import_fp():
    """FoundationPose 는 패키지가 아니라 스크립트 묶음이다 — sys.path 에 얹어야 import 된다."""
    for p in (str(FP_DIR), str(FP_DIR / "mycpp/build")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import nvdiffrast.torch as dr  # noqa: F401
    from estimater import FoundationPose, ScorePredictor, PoseRefinePredictor  # noqa: F401
    return FoundationPose, ScorePredictor, PoseRefinePredictor, dr


def load_mesh_m(path: Path):
    """mm PLY → 미터 trimesh. FoundationPose 의 절대 임계값(vox_size 하한 0.003 등)이 미터 전제다."""
    import trimesh

    m = trimesh.load(str(path), process=False)
    m.apply_scale(MM_TO_M)
    return m


def project_mask(mesh_m, pose_m: np.ndarray, K: np.ndarray, hw: tuple[int, int]) -> np.ndarray:
    """pose 로 메쉬를 투영해 실루엣 마스크를 만든다 (볼록껍질 채우기).

    ⚠️ **"flange 실루엣은 볼록" 이라는 전제는 틀렸다** (2026-08-10, 사용자가 overlay 에서 발견).
    이 테두리에는 변 중앙·모서리마다 **오목한 노치**가 있어 볼록껍질이 그것을 메운다 —
    GT 마스크 대비 평균 **1.55%**(최대 2.18%) 만큼 물체 밖으로 부풀고, depth 는 마스크 안만 남기므로
    그 배경 픽셀이 refine 에 들어간다. 올바른 것은 `project_mask_faces`(삼각형 합집합)다.
    → `--flange-mask-proj faces` 가 기본. 이 함수는 **옛 결과 재현용 대조군**으로 남긴다.
    """
    V = np.asarray(mesh_m.vertices)
    Xc = (pose_m[:3, :3] @ V.T + pose_m[:3, 3:4]).T
    Xc = Xc[Xc[:, 2] > 1e-6]
    if len(Xc) < 3:
        return np.zeros(hw, np.uint8)
    uv = (K @ Xc.T).T
    uv = (uv[:, :2] / uv[:, 2:3]).astype(np.int32)
    hull = cv2.convexHull(uv.reshape(-1, 1, 2))
    mask = np.zeros(hw, np.uint8)
    cv2.fillConvexPoly(mask, hull, 255)
    return mask


def project_mask_faces(mesh_m, pose_m: np.ndarray, K: np.ndarray, hw: tuple[int, int]) -> np.ndarray:
    """삼각형 합집합으로 실루엣을 만든다 — **비볼록(고리) 메쉬용**.

    `project_mask` 의 볼록껍질은 rim 밴드처럼 가운데가 뚫린 형상에서 구멍을 메워 버린다.
    실루엣은 z 순서와 무관하게 **투영 삼각형의 합집합**이므로 z-buffer 없이 정확하다.
    """
    V = np.asarray(mesh_m.vertices)
    F = np.asarray(mesh_m.faces)
    Xc = (pose_m[:3, :3] @ V.T + pose_m[:3, 3:4]).T
    uv = (K @ Xc.T).T
    good = uv[:, 2] > 1e-6
    uv = np.divide(uv[:, :2], np.where(uv[:, 2:3] > 1e-6, uv[:, 2:3], 1.0))
    keep = good[F].all(axis=1)
    tri = np.rint(uv[F[keep]]).astype(np.int32)
    mask = np.zeros(hw, np.uint8)
    # ⚠️ 한 번의 `fillPoly` 는 **겹치는 삼각형을 짝홀 규칙으로 상쇄**해 내부에 구멍을 낸다. 합집합이
    #    필요하므로 삼각형마다 채운다 (17k 삼각형에 ~40ms — 프레임당 무시할 만하다).
    for t in tri:
        cv2.fillConvexPoly(mask, t, 255)
    return mask


def to_band(mask: np.ndarray, band_mm: float, hub_r_mm: float,
            fx: float, z_m: float) -> np.ndarray:
    """실루엣 마스크를 **바깥 테두리 밴드**로 줄인다 (rim 밴드 정합, CATALOG §2.2 S⑤).

    왜 침식인가 — flange 실루엣의 **바깥 경계가 곧 테두리**다. 그래서 실루엣을 반지름 `w_px` 원판으로
    침식하고 뺀 나머지가 폭 `band_mm` 의 밴드이고, 이것은 `cad.build_rim_obj` 가 **XY 외곽선을 안쪽으로
    offset** 해 만든 모델 밴드와 같은 도형이다. 둘이 어긋나면 정합기는 없는 표면을 찾게 된다.

    ★ **GT 를 쓰지 않는다** — 필요한 것은 flange 마스크와 그 안의 depth 중앙값(거리)뿐이라
    실환경에 그대로 옮겨진다. mm→px 는 `w_px = band_mm · fx / Z`.
    """
    m = mask > 127
    if not m.any() or z_m <= 1e-6:
        return mask
    w_px = int(round(band_mm * MM_TO_M * fx / z_m))
    if w_px < 1:
        return mask
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * w_px + 1, 2 * w_px + 1))
    inner = cv2.erode(m.astype(np.uint8), k)
    band = (m.astype(np.uint8) - inner) * 255
    if hub_r_mm > 0:
        # 중심 홀 주변도 표준부다. 실루엣 무게중심을 중심축으로 본다(밴드가 대칭이라 편향이 작다).
        ys, xs = np.nonzero(m)
        r_px = int(round(hub_r_mm * MM_TO_M * fx / z_m))
        cv2.circle(band, (int(xs.mean()), int(ys.mean())), max(r_px, 1), 255, -1)
        band = np.where(m, band, 0).astype(np.uint8)
    return band


def mask_depth_median_m(mask: np.ndarray, depth_m: np.ndarray) -> float:
    """마스크 안 유효 depth 의 중앙값(m). 밴드 폭을 px 로 바꾸는 거리 기준이다."""
    v = depth_m[(mask > 127) & (depth_m > 1e-6)]
    return float(np.median(v)) if v.size else 0.0


def load_pose_json(p: Path) -> np.ndarray | None:
    """우리 계약(cam_T_obj, R + t mm) → 4x4 미터 행렬."""
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    T = np.eye(4)
    T[:3, :3] = np.asarray(d["R"], float).reshape(3, 3)
    T[:3, 3] = np.asarray(d["t_mm"], float) * MM_TO_M
    return T


def relative_cam_transform(gt_far: Path, gt_near: Path) -> np.ndarray | None:
    """T_cam2_cam1 — 원거리 시점에서 근접 시점으로의 카메라 변환.

    두 시점의 GT `cam_T_obj` 로부터 `T_cam2_cam1 = cam2_T_obj · (cam1_T_obj)^-1` 로 얻는다.
    **객체 pose 는 쓰지 않는다** — 같은 객체를 두 시점에서 본 관계만 쓰므로 결과적으로
    카메라 이동만 남는다. 실환경에서는 로봇 kinematics(hand-eye)가 이 값을 준다.
    """
    T1, T2 = load_pose_json(gt_far), load_pose_json(gt_near)
    if T1 is None or T2 is None:
        return None
    return T2 @ np.linalg.inv(T1)


def pose_to_json(pose_m: np.ndarray, stage: str, extra: dict | None = None) -> dict:
    """FoundationPose 의 미터 pose → 우리 계약(cam_T_obj, R row-major + t mm)."""
    return {
        "frame": "cam_T_obj",
        "convention": "BOP (R 3x3 row-major, t mm)",
        "R": np.asarray(pose_m[:3, :3], float).round(9).tolist(),
        "t_mm": (np.asarray(pose_m[:3, 3], float) / MM_TO_M).round(6).tolist(),
        "stage": stage,
        **(extra or {}),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="pose 스테이지 (FoundationPose 2-stage)")
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--out", dest="out_dir", required=True)
    ap.add_argument("--obj", required=True, help="assets/obj/<obj_id> (full.ply + top_flange.ply)")
    ap.add_argument("--masks", default=None,
                    help="full 마스크가 있는 디렉토리(M4 산출물). 생략하면 --in 의 GT 마스크")
    ap.add_argument("--depth", default="gt", choices=["gt", "stereo"])
    ap.add_argument("--depth-dir", default=None)
    ap.add_argument("--flange-mask-from", default="pose", choices=["pose", "seg"],
                    help="pose=coarse pose 투영(기본) / seg=segmentation 결과")
    ap.add_argument("--est-iter", type=int, default=5, help="stage-1 register refine 반복")
    ap.add_argument("--refine-iter", type=int, default=5, help="stage-2 refine 반복")
    ap.add_argument("--no-stage2", action="store_true",
                    help="coarse 만. **실사용 경로다** — 2-stage 는 회전을 악화시켜 기각됐다(모듈 docstring)")
    ap.add_argument("--init-from", default=None,
                    help="[연구용] 다른(원거리) 런의 pose 를 초기값으로 받는다 — **카메라 이동 2단계**. "
                         "1차에서 FOUP 전체로 방향을 확정하고, 카메라를 접근시킨 2차에서 flange 로 refine 만 한다. "
                         "flange 단독 추정은 근사 대칭 때문에 초기 pose 를 스스로 잡으면 안 된다(R4, 실측 R 18~24°). "
                         "⚠️ 초기값을 정확히 줘도 refine 이 R 을 0.604°→3.432° 악화시킨다 — 채택하지 않는다.")
    ap.add_argument("--init-pose-name", default="pose_coarse.json")
    ap.add_argument("--init-capture", default=None,
                    help="1차 **캡처** 디렉토리(pose_gt.json 이 있는 곳). --rel-from-gt 에 필요하다. "
                         "--init-from 은 pose **출력** 디렉토리라 GT 가 없다.")
    ap.add_argument("--rel-from-gt", action="store_true",
                    help="두 시점의 상대 카메라 변환을 GT 로 계산한다. 실환경에서는 로봇 TCP(hand-eye)가 주는 값이고, "
                         "sim 에서는 그 대역이다. **객체 pose 가 아니라 카메라 이동만** GT 를 쓴다.")
    ap.add_argument("--primary", default="full", choices=["full", "flange"],
                    help="stage-1 에 쓸 메쉬·마스크. flange 면 top_flange.ply 로 **직접** 추정한다 — "
                         "FOUP 전체가 FOV 를 벗어나는 근접 거리에서 쓰는 경로다(flange 만 온전히 보이면 된다)")
    ap.add_argument("--flange-mask-proj", default="faces", choices=["faces", "hull"],
                    help="[--flange-mask-from pose] 투영 마스크 만드는 법. "
                         "faces=삼각형 합집합(**올바름**, 노치를 살린다) / hull=볼록껍질(옛 동작, 대조군). "
                         "볼록껍질은 GT 대비 평균 1.55% 부푼다 — 그만큼 배경 depth 가 refine 에 들어간다")
    ap.add_argument("--mask-band-mm", type=float, default=0.0,
                    help="flange 마스크를 **바깥 테두리 밴드**로 줄인다(rim 밴드 정합, CATALOG §2.2 S⑤). "
                         "⚠️ 반드시 `cad.build_rim_obj --band-mm` 로 같은 폭의 밴드 메쉬를 만든 obj 와 "
                         "짝지어 쓴다 — 모델과 마스크가 어긋나면 정합기가 없는 표면을 찾는다. 0=끄기")
    # ★ 고해상도 입력용 (ZED X 1920×1200 등)
    #   FoundationPose 는 crop 을 **160×160 으로 리샘플**하므로(§22) 네트워크가 보는 해상도는
    #   `diameter × crop_ratio / 160` mm/px 로 **원본 해상도와 무관**하다. 그런데 내부의
    #   `transform_depth_to_xyzmap` 이 crop 을 **원본 크기로 되돌리며** 가설 수만큼 warp 해서
    #   메모리가 원본 픽셀 수에 비례한다 → 1920×1200 에서 31GB GPU 가 OOM 난다(실측).
    #   ⚠️ 그래서 줄인다. **crop 원본 영역이 160px 아래로 내려가지 않는 한 정보 손실이 없다** —
    #      0.55m 원거리 crop 919px, 근접 flange crop 400px 이므로 0.5 배까지 안전하다.
    ap.add_argument("--input-scale", type=float, default=1.0,
                    help="FP 에 넣기 전 rgb/depth/mask 와 K 를 함께 축소한다(<1). "
                         "출력 pose 는 3D 미터라 영향 없다. 🔴 1920×1200 상한은 **0.75** — 단 "
                         "`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` 가 있어야 한다"
                         "(env.sh 가 상설로 건다). 없으면 0.5. 1.0 은 불가 (RESULTS §38-4)")
    ap.add_argument("--mask-hub-r-mm", type=float, default=0.0,
                    help="밴드에 중심 홀 주변 원판을 더한다(build_rim_obj --hub-r-mm 과 같은 값)")
    args = ap.parse_args(argv)

    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    if in_dir.resolve() == out_dir.resolve():
        print("❌ --out 이 --in 과 같다 (GT 를 덮어쓴다).", file=sys.stderr)
        return 2
    obj_dir = Path(args.obj)
    mask_root = Path(args.masks) if args.masks else in_dir

    import torch
    FoundationPose, ScorePredictor, PoseRefinePredictor, dr = _import_fp()

    frames = sorted([p for p in in_dir.glob("frame_*") if p.is_dir()]) or [in_dir]
    print(f"== FoundationPose 2-stage | {len(frames)} 프레임 | depth={args.depth} "
          f"| masks={mask_root.name} | flange_mask={args.flange_mask_from}")

    t0 = time.time()
    mesh_full = load_mesh_m(obj_dir / "full.ply")
    mesh_flange = load_mesh_m(obj_dir / "top_flange.ply")
    # ★ primary=flange: 전체 형상 대신 flange 로 직접 추정한다.
    #   근접(예: 0.3~0.5m)에서는 FOUP 전체가 화면을 벗어나지만 flange 는 온전히 들어온다.
    #   두 메쉬가 **같은 원점**(M1 검증)이라 pose 규약은 동일하다.
    mesh_primary = mesh_flange if args.primary == "flange" else mesh_full
    mask_primary = "mask_flange.png" if args.primary == "flange" else "mask_full.png"
    scorer, refiner = ScorePredictor(), PoseRefinePredictor()
    glctx = dr.RasterizeCudaContext()
    est1 = FoundationPose(model_pts=mesh_primary.vertices, model_normals=mesh_primary.vertex_normals,
                          mesh=mesh_primary, scorer=scorer, refiner=refiner, glctx=glctx,
                          debug=0, debug_dir=str(VISION_ROOT / ".cache/fp_debug"))
    est2 = None
    if not args.no_stage2:
        est2 = FoundationPose(model_pts=mesh_flange.vertices, model_normals=mesh_flange.vertex_normals,
                              mesh=mesh_flange, scorer=scorer, refiner=refiner, glctx=glctx,
                              debug=0, debug_dir=str(VISION_ROOT / ".cache/fp_debug"))
    print(f"  초기화 {time.time()-t0:.1f}s | stage-1 메쉬 = {args.primary} "
          f"({len(mesh_primary.faces)}f, 마스크 {mask_primary})")

    rows, t_frames = [], []
    for f in frames:
        cam = json.loads((f / "cam.json").read_text())
        K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], dtype=np.float64)
        rgb = cv2.cvtColor(cv2.imread(str(f / "left.png")), cv2.COLOR_BGR2RGB)

        dd = Path(args.depth_dir) / f.name if args.depth_dir else f
        if args.depth == "gt":
            # --depth-dir 을 주면 GT 경로에서도 그 디렉토리를 본다 — 교란된 depth 주입용
            # (`eval.perturb_depth`). 양자화 없는 float 를 유지해야 mm 이하 비교가 가능하다.
            depth_mm = np.load(dd / "depth_gt.npy").astype(np.float64)
        else:
            depth_mm = cv2.imread(str(dd / "depth.png"), cv2.IMREAD_UNCHANGED).astype(np.float64)
        depth_m = np.nan_to_num(depth_mm, nan=0.0, posinf=0.0, neginf=0.0) * MM_TO_M

        md = mask_root / f.name if mask_root != in_dir or (mask_root / f.name).exists() else f
        mask_full = cv2.imread(str(md / mask_primary), cv2.IMREAD_GRAYSCALE)

        orig_hw = depth_m.shape[:2]
        if args.input_scale != 1.0:
            s = float(args.input_scale)
            h0, w0 = orig_hw
            w, h = int(round(w0 * s)), int(round(h0 * s))
            sx, sy = w / w0, h / h0                       # 반올림 후의 **실제** 배율을 쓴다
            rgb = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA)
            # ⚠️ depth 는 **NEAREST** — 평균을 내면 물체/배경 경계에 없는 거리가 생긴다
            depth_m = cv2.resize(depth_m, (w, h), interpolation=cv2.INTER_NEAREST)
            if mask_full is not None:
                mask_full = cv2.resize(mask_full, (w, h), interpolation=cv2.INTER_NEAREST)
            # ⚠️ 반픽셀: OpenCV 규약에서 픽셀 중심이 정수이므로 c' = (c+0.5)·s − 0.5 다.
            #    c·s 로 쓰면 0.5·(1−s) px 이 어긋난다 (횡단 정리 #1 과 같은 계열).
            K = np.array([[cam["fx"] * sx, 0, (cam["cx"] + 0.5) * sx - 0.5],
                          [0, cam["fy"] * sy, (cam["cy"] + 0.5) * sy - 0.5],
                          [0, 0, 1]], dtype=np.float64)

        if mask_full is None or not (mask_full > 127).any():
            # ⚠️ 둘을 구분해서 말한다 — 원인이 완전히 다르다.
            #   «없음»    = 분할 스테이지를 안 돌렸거나 --masks 경로가 틀렸다
            #   «비었음»  = 분할은 돌았는데 **아무것도 검출하지 못했다** (참조·프롬프트·도메인 갭)
            why = "없음" if mask_full is None else "비었음(분할이 검출 0)"
            print(f"  {f.name}: {md / mask_primary} {why} — 건너뜀", file=sys.stderr)
            rows.append({"frame": f.name, "ok": False})
            continue

        od = out_dir / f.name
        od.mkdir(parents=True, exist_ok=True)
        ts = time.time()

        # ── rim 밴드: 모델(top_flange.ply = 밴드)과 **같은 도형**으로 마스크를 줄인다 ──────
        z_med = mask_depth_median_m(mask_full, depth_m) if args.mask_band_mm > 0 else 0.0
        if args.mask_band_mm > 0:
            mask_full = to_band(mask_full, args.mask_band_mm, args.mask_hub_r_mm, cam["fx"], z_med)
            cv2.imwrite(str(od / "mask_band.png"), mask_full)
            if not (mask_full > 127).any():
                print(f"  {f.name}: 밴드 마스크가 비었다 — 건너뜀", file=sys.stderr)
                rows.append({"frame": f.name, "ok": False})
                continue

        # ── stage 1: 초기 pose 를 얻는다 ─────────────────────────────────────────
        if args.init_from:
            # 카메라 이동 2단계: 1차(원거리) pose 를 이 시점으로 옮겨 **초기값으로만** 쓴다.
            prev = load_pose_json(Path(args.init_from) / f.name / args.init_pose_name)
            rel = np.eye(4)
            if args.rel_from_gt:
                cap = Path(args.init_capture) if args.init_capture else Path(args.init_from)
                rel = relative_cam_transform(cap / f.name / "pose_gt.json", f / "pose_gt.json")
            if prev is None or rel is None:
                print(f"  {f.name}: 초기 pose 없음 — 건너뜀", file=sys.stderr)
                rows.append({"frame": f.name, "ok": False})
                continue
            init = rel @ prev
            c = np.asarray(est1.model_center, dtype=np.float64).reshape(3)
            T = np.eye(4); T[:3, 3] = c
            est1.pose_last = torch.as_tensor(init @ T, dtype=torch.float, device="cuda")
            depth_crop = np.where(mask_full > 127, depth_m, 0.0)
            coarse = est1.track_one(rgb=rgb, depth=depth_crop, K=K, iteration=args.est_iter)
        else:
            coarse = est1.register(K=K, rgb=rgb, depth=depth_m, ob_mask=(mask_full > 127),
                                   iteration=args.est_iter)
        (od / "pose_coarse.json").write_text(json.dumps(
            pose_to_json(coarse, f"coarse_{args.primary}"), indent=2))

        rec = {"frame": f.name, "ok": True,
               "t_coarse_mm": (coarse[:3, 3] / MM_TO_M).round(3).tolist()}

        # ── stage 2: flange 로 refine (초기 pose 생성 skip) ─────────────────────
        if est2 is not None:
            if args.flange_mask_from == "pose":
                # ⚠️ 밴드는 고리라 **볼록껍질을 쓰면 구멍이 메워진다** → 삼각형 합집합으로 투영한다.
                #    stage-1 의 침식 밴드와 달리 이쪽은 원근 단축까지 정확하다.
                mf = (project_mask(mesh_flange, coarse, K, depth_m.shape)
                      if (args.mask_band_mm <= 0 and args.flange_mask_proj == "hull")
                      else project_mask_faces(mesh_flange, coarse, K, depth_m.shape))
                mf_out = (mf if mf.shape[:2] == orig_hw else
                          cv2.resize(mf, (orig_hw[1], orig_hw[0]), interpolation=cv2.INTER_NEAREST))
                cv2.imwrite(str(od / "mask_flange_proj.png"), mf_out)
            else:
                mf = cv2.imread(str(md / "mask_flange.png"), cv2.IMREAD_GRAYSCALE)
                if mf is None or not (mf > 127).any():
                    print(f"  {f.name}: flange 마스크 없음 — coarse 만 사용", file=sys.stderr)
                    mf = None
                elif args.mask_band_mm > 0:
                    mf = to_band(mf, args.mask_band_mm, args.mask_hub_r_mm, cam["fx"],
                                 mask_depth_median_m(mf, depth_m))
            if mf is not None:
                # flange 밖의 depth 를 지운다 — refiner 는 마스크를 따로 받지 않고 depth 를 본다.
                depth_crop = np.where(mf > 127, depth_m, 0.0)
                # pose_last 는 centered mesh 기준 → T(+model_center) 를 곱해 되돌린다.
                c = np.asarray(est2.model_center, dtype=np.float64).reshape(3)
                T = np.eye(4); T[:3, 3] = c
                est2.pose_last = torch.as_tensor(coarse @ T, dtype=torch.float, device="cuda")
                refined = est2.track_one(rgb=rgb, depth=depth_crop, K=K, iteration=args.refine_iter)
            else:
                refined = coarse
            (od / "pose_refined.json").write_text(json.dumps(
                pose_to_json(refined, f"refine_flange({args.flange_mask_from})"), indent=2))
            rec["t_refined_mm"] = (refined[:3, 3] / MM_TO_M).round(3).tolist()

        dt = (time.time() - ts) * 1000
        t_frames.append(dt)
        rows.append(rec)
        d = (np.linalg.norm(np.array(rec.get("t_refined_mm", rec["t_coarse_mm"]))
                            - np.array(rec["t_coarse_mm"])) if "t_refined_mm" in rec else 0.0)
        print(f"  {f.name}: {dt:7.0f}ms  |t|={np.linalg.norm(coarse[:3,3])/MM_TO_M:7.1f}mm  "
              f"coarse→refine 이동 {d:6.2f}mm")

    meta = {
        "stage": "pose", "backend": "foundationpose_2stage",
        "license": "NVIDIA Source Code License — research/evaluation only (docs/LICENSES.md §1)",
        "obj": str(obj_dir), "masks": str(mask_root), "depth_source": args.depth,
        "primary": args.primary, "init_from": args.init_from, "rel_from_gt": args.rel_from_gt,
        "flange_mask_from": args.flange_mask_from,
        "mask_band_mm": args.mask_band_mm, "mask_hub_r_mm": args.mask_hub_r_mm,
        "flange_mask_proj": args.flange_mask_proj,
        "input_scale": args.input_scale,
        "est_iter": args.est_iter, "refine_iter": args.refine_iter,
        "two_stage": est2 is not None,
        "mean_ms": float(np.mean(t_frames)) if t_frames else None, "frames": rows,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta_pose.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"  평균 {np.mean(t_frames):.0f}ms/frame → {out_dir}" if t_frames else "  산출 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
