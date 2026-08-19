"""pose 결과를 **눈으로 검사**할 컨택트 시트를 만든다.

    # sim (GT 있음)
    envs/pose/bin/python -m spatial_vision.viz.overlay_pose \
        --capture runs/dr2_near --pred runs/rim_g9_w3 --obj assets/obj/foup_300_semi_rim3 \
        --frames 6 --out runs/rim_g9_w3/overlay_sheet.png

    # 실환경 (GT 없음) — 변형을 나란히 놓고 비교한다
    envs/pose/bin/python -m spatial_vision.viz.overlay_pose \
        --capture runs/real01 --obj assets/obj/foup_300_semi_r2 \
        --pred runs/real01_A/fp_ns2:pose_coarse.json --pred runs/real01_A/A1 \
        --pred runs/real01_A/A2a --frames 4 --out runs/real01_A/overlay_sheet.png

왜 필요한가
    `metrics_pose.json` 의 숫자만으로는 **무엇이 잘못됐는지** 안 보인다. 90° 뒤집힘인지, 마스크가
    엉뚱한 곳을 잡았는지, 밴드가 물체를 안 덮는지는 **겹쳐 그려야** 안다. 이 프로젝트에서
    기하 오류를 실제로 잡아낸 건 지표가 아니라 눈이었다(RESULTS.md 횡단 정리 #39·#46).

🔴 **실환경에는 GT 가 없다 — 그래서 이 도구가 «유일한» 육안 판정 수단이다**
    절대 오차(mm·도)는 원리적으로 못 낸다(`PIPELINE_CATALOG §7.5`). 남는 것은
    ① 투영 실루엣이 사진의 물체 테두리에 **붙는가** ② 축 삼각대가 상식적인 방향인가
    ③ 변형끼리 **서로 어긋나는가** 다. 셋 다 이 시트에서만 보인다.

무엇을 그리나 — (프레임 × 예측) 한 타일
    · 배경: `left.png`
    · **빨강** = GT pose 로 투영한 모델 윤곽    (`pose_gt.json` — 없으면 안 그린다)
    · **초록** = 예측 pose 로 투영한 모델 윤곽
    · **파랑 반투명** = 정합에 실제로 쓴 마스크 (mask_band > mask_flange_proj > mask_flange)
    · **축 삼각대** = 물체 원점(flange 주 상면 중심)의 X/Y/Z. 글자로 라벨을 찍는다
    · 좌상단: GT 가 있으면 R/t 오차, 없으면 **초기값 대비 이동량**과 **게이트 후퇴 여부**

⚠️ **`stages.refine_contour --debug` 와 색 규약이 다르다** — 거기서는 초록=GT · 노랑=모델 샘플이다.
   그래서 두 도구 모두 **이미지에 범례를 찍는다.** 시트를 인용할 때 색을 말로 옮기지 말 것.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from spatial_vision.contracts import rotation_angle_deg
import trimesh

MASK_CANDIDATES = ("mask_band.png", "mask_flange_proj.png", "mask_flange.png")


def load_pose(p: Path) -> np.ndarray | None:
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    T = np.eye(4)
    T[:3, :3] = np.asarray(d["R"], float).reshape(3, 3)
    T[:3, 3] = np.asarray(d["t_mm"], float)
    return T


def silhouette(mesh: trimesh.Trimesh, T: np.ndarray, K: np.ndarray, hw) -> np.ndarray:
    """투영 삼각형의 **합집합**. ⚠️ fillPoly 한 번으로 그리면 짝홀 규칙으로 상쇄된다(교훈 #41)."""
    V, F = np.asarray(mesh.vertices), np.asarray(mesh.faces)
    Xc = (T[:3, :3] @ V.T + T[:3, 3:4]).T
    uv = (K @ Xc.T).T
    good = uv[:, 2] > 1e-6
    uv = np.divide(uv[:, :2], np.where(uv[:, 2:3] > 1e-6, uv[:, 2:3], 1.0))
    m = np.zeros(hw, np.uint8)
    for t in np.rint(uv[F[good[F].all(axis=1)]]).astype(np.int32):
        cv2.fillConvexPoly(m, t, 255)
    return m


# 🔴 `arccos((tr−1)/2)` 는 항등 근처에서 오차를 **제곱근으로 증폭**한다 — 저장된 R 이
#    정확히 직교가 아니라(9자리 반올림) **자기 자신과 비교해도 0.03° 가 나왔다**
#    (실측 p90 0.028° · 최대 0.049°, 2026-08-19). 정본은 `contracts.rotation_angle_deg`.
def rot_deg(A: np.ndarray, B: np.ndarray) -> float:
    return rotation_angle_deg(A[:3, :3], B[:3, :3])


def draw_axes(img, T, K, mm: float) -> None:
    """물체 원점의 X/Y/Z. **글자로 라벨을 찍는다** — 색만으로는 다른 도구와 헷갈린다."""
    P = np.array([[0, 0, 0], [mm, 0, 0], [0, mm, 0], [0, 0, mm]], float)
    Xc = (T[:3, :3] @ P.T + T[:3, 3:4]).T
    if (Xc[:, 2] <= 1e-6).any():
        return
    uv = (K @ Xc.T).T
    uv = np.rint(uv[:, :2] / uv[:, 2:3]).astype(int)
    o = tuple(uv[0])
    for i, (lab, col) in enumerate(((("X"), (0, 0, 255)), ("Y", (0, 255, 0)), ("Z", (255, 0, 0))), 1):
        cv2.arrowedLine(img, o, tuple(uv[i]), col, 2, tipLength=0.18)
        cv2.putText(img, lab, tuple(uv[i]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
    cv2.circle(img, o, 4, (255, 255, 255), -1)


def parse_pred(spec: str, default_name: str) -> tuple[Path, str, str]:
    """`경로[:pose_이름]` → (디렉토리, pose 파일명, 라벨)."""
    if ":" in spec and not spec.split(":")[-1].startswith(("/", "\\")):
        head, name = spec.rsplit(":", 1)
    else:
        head, name = spec, default_name
    d = Path(head)
    lab = d.name if name == default_name else f"{d.name}/{name.replace('pose_', '').replace('.json', '')}"
    return d, name, lab


def square_box(mask: np.ndarray, hw, pad_frac: float = 0.35) -> tuple[int, int, int, int] | None:
    """실루엣 주위 **정사각** 크롭 — 직사각으로 자른 뒤 정사각 타일로 리사이즈하면 찌그러진다."""
    if mask is None or not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    cx, cy = (xs.min() + xs.max()) / 2.0, (ys.min() + ys.max()) / 2.0
    r = 0.5 * max(np.ptp(xs), np.ptp(ys)) * (1 + 2 * pad_frac) + 20   # numpy 2: ndarray.ptp 제거됨
    r = min(r, min(hw) / 2.0)
    x0 = int(np.clip(cx - r, 0, hw[1] - 2 * r))
    y0 = int(np.clip(cy - r, 0, hw[0] - 2 * r))
    return x0, y0, int(x0 + 2 * r), int(y0 + 2 * r)


def make_tile(frame: Path, pred_dir: Path, pose_name: str, mesh, K, box, tile: int,
              mask_alpha: float = 0.22):
    """타일 하나. `box` 가 None 이면 이 타일의 예측으로 잡는다(그 박스를 반환해 행에서 공유).

    ⚠️ 마스크는 **연하게** 깐다 — 실환경 판정은 *"초록 윤곽이 사진의 진짜 테두리에 붙는가"* 인데
       진하게 칠하면 그 테두리가 가려진다. `--mask-alpha 0` 으로 아예 끌 수 있다.
    """
    img = cv2.imread(str(frame / "left.png"))
    hw = img.shape[:2]

    for name, src in ((n, s) for n in MASK_CANDIDATES for s in (pred_dir / frame.name, frame)):
        mp = src / name
        if mask_alpha <= 0:
            break
        if mp.exists():
            mk = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
            if mk is not None and mk.shape == hw:
                img[mk > 127] = ((1 - mask_alpha) * img[mk > 127]
                                 + mask_alpha * np.array([255, 120, 0])).astype(np.uint8)
            break

    T_gt = load_pose(frame / "pose_gt.json")
    T_pr = load_pose(pred_dir / frame.name / pose_name)
    s_pr = silhouette(mesh, T_pr, K, hw) if T_pr is not None else None
    if box is None:
        box = square_box(silhouette(mesh, T_gt, K, hw) if T_gt is not None else s_pr, hw)

    for T, col in ((T_gt, (0, 0, 255)), (T_pr, (0, 255, 0))):
        if T is None:
            continue
        s = s_pr if T is T_pr else silhouette(mesh, T, K, hw)
        cs, _ = cv2.findContours(s, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, cs, -1, col, 2)
    if T_pr is not None:
        draw_axes(img, T_pr, K, 60.0)

    # 좌상단 주석 — GT 가 있으면 오차, 없으면 GT-free 단서(이동량·게이트)
    if T_pr is None:
        note = "pose 없음"
    elif T_gt is not None:
        note = f"R {rot_deg(T_gt, T_pr):5.2f}deg  t {np.linalg.norm(T_gt[:3, 3] - T_pr[:3, 3]):5.2f}mm"
    else:
        note = f"z {T_pr[2, 3]:.0f}mm"
        T0 = load_pose(pred_dir / frame.name / "pose_coarse.json")
        if T0 is not None and pose_name != "pose_coarse.json":
            note += f"  moved {rot_deg(T0, T_pr):.2f}deg {np.linalg.norm(T0[:3, 3] - T_pr[:3, 3]):.2f}mm"
        if (pred_dir / frame.name / "pose_contour_raw.json").exists():
            note += "  [GATED]"          # 정합 결과를 버리고 초기값을 낸 프레임

    if box:
        x0, y0, x1, y1 = box
        img = img[y0:y1, x0:x1]
    if img.size == 0:
        img = np.zeros((tile, tile, 3), np.uint8)
    img = cv2.resize(img, (tile, tile))
    cv2.rectangle(img, (0, 0), (tile - 1, 22), (0, 0, 0), -1)
    cv2.putText(img, note, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 255, 255), 1)
    return img, box


def label_bar(text: str, w: int, h: int = 26, col=(255, 255, 255)) -> np.ndarray:
    """⚠️ 폰트를 폭에 맞춰 줄인다 — 범례가 잘리면 색 규약을 알 수 없고, 그게 이 도구의 존재 이유다."""
    bar = np.full((h, w, 3), 30, np.uint8)
    fs = 0.55
    while fs > 0.24 and cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)[0][0] > w - 14:
        fs -= 0.03
    cv2.putText(bar, text, (8, h - 8), cv2.FONT_HERSHEY_SIMPLEX, fs, col, 1)
    return bar


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="pose overlay 컨택트 시트 (GT 없어도 된다)")
    ap.add_argument("--capture", required=True, help="left.png·cam.json (+sim 이면 pose_gt.json) 디렉토리")
    ap.add_argument("--pred", action="append", required=True,
                    help="pose 산출 디렉토리. `경로:pose_이름` 으로 파일도 지정한다. 여러 번 주면 열로 나란히 놓는다")
    ap.add_argument("--obj", required=True, help="투영에 쓸 obj (밴드 런이면 밴드 obj)")
    ap.add_argument("--mesh", default="top_flange.ply")
    ap.add_argument("--pose-name", default="pose_refined.json", help="--pred 에 `:이름` 이 없을 때의 기본값")
    ap.add_argument("--frames", type=int, default=6, help="균등 간격으로 고를 프레임 수")
    ap.add_argument("--pick", default=None,
                    help="프레임을 직접 지정한다(쉼표 구분, 예 frame_0010,frame_0026). --frames 를 무시한다")
    ap.add_argument("--worst", type=int, default=0,
                    help="`--pred/metrics_pose.json` 에서 오차 상위 N 프레임 (sim 전용, --pick 다음 우선)")
    ap.add_argument("--worst-key", default="rot_deg", choices=["rot_deg", "trans_mm"])
    ap.add_argument("--tile", type=int, default=420, help="타일 한 변 픽셀")
    ap.add_argument("--cols", type=int, default=3, help="예측이 하나일 때의 열 수")
    ap.add_argument("--mask-alpha", type=float, default=0.22,
                    help="마스크 반투명도. 0 이면 안 그린다 — 실물 테두리를 가리지 않고 보고 싶을 때")
    ap.add_argument("--per-frame-dir", default=None,
                    help="프레임마다 한 장씩 따로 쓴다(전체 시트와 별개). 육안 확대 검사용")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    cap = Path(args.capture)
    preds = [parse_pred(s, args.pose_name) for s in args.pred]
    mesh = trimesh.load(Path(args.obj) / args.mesh, process=False)
    frames = sorted([p for p in cap.glob("frame_*") if p.is_dir()])
    if not frames:
        print("❌ 프레임이 없다")
        return 2
    if args.pick:
        want = [s.strip() for s in args.pick.split(",") if s.strip()]
        by_name = {f.name: f for f in frames}
        missing = [w for w in want if w not in by_name]
        if missing:
            print(f"❌ 없는 프레임: {missing}")
            return 2
        sel = [by_name[w] for w in want]
    elif args.worst:
        # ⚠️ 균등 간격은 **꼬리를 못 잡는다** — 대실패는 몇 프레임에 몰리므로 지표에서 직접 고른다(교훈 #14).
        mp = json.loads((preds[0][0] / "metrics_pose.json").read_text())["results"]
        key = next((k for k in mp if k.endswith("refined")), sorted(mp)[0])
        by_name = {f.name: f for f in frames}
        ranked = sorted(mp[key]["frames"], key=lambda r: -r[args.worst_key])
        sel = [by_name[r["frame"]] for r in ranked[:args.worst] if r["frame"] in by_name]
    else:
        sel = [frames[i] for i in
               np.linspace(0, len(frames) - 1, min(args.frames, len(frames))).round().astype(int)]

    has_gt = (sel[0] / "pose_gt.json").exists()
    rows, per_frame = [], {}
    for f in sel:
        cam = json.loads((f / "cam.json").read_text())
        K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], float)
        box, tiles = None, []
        for d, name, _ in preds:               # ★ 행 안에서 크롭 박스를 공유해야 나란히 비교된다
            t, box = make_tile(f, d, name, mesh, K, box, args.tile, args.mask_alpha)
            tiles.append(t)
        rows.append((f.name, tiles))
        per_frame[f.name] = tiles

    ncol = len(preds) if len(preds) > 1 else min(args.cols, len(sel))
    W = ncol * args.tile

    if len(preds) > 1:      # 행 = 프레임, 열 = 변형
        blocks = [label_bar("  |  ".join(f"{lab:^18}" for _, _, lab in preds), W, 28, (0, 255, 255))]
        for fname, tiles in rows:
            blocks.append(label_bar(fname, W, 22))
            blocks.append(np.concatenate(tiles, 1))
    else:                   # 예측 하나 — 프레임을 격자로
        flat = [t for _, ts in rows for t in ts]
        blocks = []
        for i in range(0, len(flat), ncol):
            chunk = flat[i:i + ncol]
            chunk += [np.zeros_like(chunk[0])] * (ncol - len(chunk))
            blocks.append(np.concatenate(chunk, 1))

    legend = ("red=GT  green=pred  " if has_gt else "green=pred (GT 없음)  ") + \
             ("blue=mask  " if args.mask_alpha > 0 else "") + "axes=obj XYZ 60mm  | " + \
             " · ".join(f"{lab}" for _, _, lab in preds) + f"  / {Path(args.obj).name}"
    sheet = np.concatenate([label_bar(legend, W, 30)] + blocks, 0)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet)
    print(f"→ {out}  ({len(sel)} 프레임 × {len(preds)} 예측)")

    if args.per_frame_dir:
        pfd = Path(args.per_frame_dir)
        pfd.mkdir(parents=True, exist_ok=True)
        head = label_bar("  |  ".join(f"{lab:^18}" for _, _, lab in preds), W, 28, (0, 255, 255))
        for fname, tiles in rows:
            cv2.imwrite(str(pfd / f"overlay_{fname}.png"),
                        np.concatenate([label_bar(legend, W, 30), head,
                                        np.concatenate(tiles, 1)], 0))
        print(f"→ {pfd}/overlay_frame_*.png  ({len(rows)}장)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
