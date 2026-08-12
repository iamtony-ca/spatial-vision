"""pose 결과를 **눈으로 검사**할 컨택트 시트를 만든다.

    envs/cad/bin/python -m spatial_vision.viz.overlay_pose \
        --capture runs/dr2_near --pred runs/rim_g9_w3 --obj assets/obj/foup_300_semi_rim3 \
        --frames 6 --out runs/rim_g9_w3/overlay_sheet.png

왜 필요한가
    `metrics_pose.json` 의 숫자만으로는 **무엇이 잘못됐는지** 안 보인다. 90° 뒤집힘인지, 마스크가
    엉뚱한 곳을 잡았는지, 밴드가 물체를 안 덮는지는 **겹쳐 그려야** 안다. 이 프로젝트에서
    기하 오류를 실제로 잡아낸 건 지표가 아니라 눈이었다(RESULTS.md 횡단 정리 #39·#46).

무엇을 그리나 — 프레임마다 한 타일
    · 배경: `left.png`
    · **빨강** = GT pose 로 투영한 모델 윤곽      (pose_gt.json)
    · **초록** = 예측 pose 로 투영한 모델 윤곽    (--pose-name, 기본 pose_refined.json)
    · **파랑 반투명** = 정합에 실제로 쓴 마스크   (mask_band.png > mask_flange_proj.png > mask_flange.png)
    · 좌상단에 R/t 오차. 빨강·초록이 어긋난 만큼이 오차다.

⚠️ **GT 를 그리는 건 sim 전용이다.** 실환경에는 GT 가 없으므로(PIPELINE_CATALOG §7.5)
   거기서는 초록과 마스크만 보고 판단해야 한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import trimesh


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


def rot_deg(A: np.ndarray, B: np.ndarray) -> float:
    c = (np.trace(A[:3, :3].T @ B[:3, :3]) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="pose overlay 컨택트 시트")
    ap.add_argument("--capture", required=True, help="left.png·cam.json·pose_gt.json 이 있는 캡처 디렉토리")
    ap.add_argument("--pred", required=True, help="pose 산출 디렉토리")
    ap.add_argument("--obj", required=True, help="투영에 쓸 obj (밴드 런이면 밴드 obj)")
    ap.add_argument("--mesh", default="top_flange.ply")
    ap.add_argument("--pose-name", default="pose_refined.json")
    ap.add_argument("--frames", type=int, default=6, help="균등 간격으로 고를 프레임 수")
    ap.add_argument("--pick", default=None,
                    help="프레임을 직접 지정한다(쉼표 구분, 예 frame_0010,frame_0026). --frames 를 무시한다")
    ap.add_argument("--worst", type=int, default=0,
                    help="`--pred/metrics_pose.json` 에서 회전 오차 상위 N 프레임을 고른다(--pick 다음 우선)")
    ap.add_argument("--worst-key", default="rot_deg", choices=["rot_deg", "trans_mm"],
                    help="--worst 의 정렬 기준")
    ap.add_argument("--tile", type=int, default=420, help="타일 한 변 픽셀")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    cap, pred = Path(args.capture), Path(args.pred)
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
        mp = json.loads((pred / "metrics_pose.json").read_text())["results"]
        key = next((k for k in mp if k.endswith("refined")), sorted(mp)[0])
        by_name = {f.name: f for f in frames}
        ranked = sorted(mp[key]["frames"], key=lambda r: -r[args.worst_key])
        sel = [by_name[r["frame"]] for r in ranked[:args.worst] if r["frame"] in by_name]
    else:
        sel = [frames[i] for i in
               np.linspace(0, len(frames) - 1, min(args.frames, len(frames))).round().astype(int)]

    tiles = []
    for f in sel:
        cam = json.loads((f / "cam.json").read_text())
        K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], float)
        img = cv2.imread(str(f / "left.png"))
        hw = img.shape[:2]

        # 정합에 실제로 쓴 마스크를 찾는다 (밴드 런이면 mask_band.png 가 있다)
        for name, src in (("mask_band.png", pred / f.name), ("mask_flange_proj.png", pred / f.name),
                          ("mask_flange.png", f)):
            mp = src / name
            if mp.exists():
                mk = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
                break
        else:
            mk, name = None, "-"
        if mk is not None:
            img[mk > 127] = (0.55 * img[mk > 127] + 0.45 * np.array([255, 120, 0])).astype(np.uint8)

        T_gt = load_pose(f / "pose_gt.json")
        T_pr = load_pose(pred / f.name / args.pose_name)
        txt = f.name
        for T, col in ((T_gt, (0, 0, 255)), (T_pr, (0, 255, 0))):
            if T is None:
                continue
            s = silhouette(mesh, T, K, hw)
            cs, _ = cv2.findContours(s, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(img, cs, -1, col, 2)
        if T_gt is not None and T_pr is not None:
            txt += f"  R {rot_deg(T_gt, T_pr):5.2f}°  t {np.linalg.norm(T_gt[:3,3]-T_pr[:3,3]):5.2f}mm"

        # 물체 주변으로 크롭해야 얇은 밴드가 보인다
        s_gt = silhouette(mesh, T_gt, K, hw) if T_gt is not None else None
        if s_gt is not None and s_gt.any():
            ys, xs = np.nonzero(s_gt)
            pad = int(0.35 * max(np.ptp(xs), np.ptp(ys)) + 20)   # numpy 2 에서 ndarray.ptp 제거됨
            x0, x1 = max(0, xs.min() - pad), min(hw[1], xs.max() + pad)
            y0, y1 = max(0, ys.min() - pad), min(hw[0], ys.max() + pad)
            img = img[y0:y1, x0:x1]
        img = cv2.resize(img, (args.tile, args.tile))
        cv2.putText(img, txt, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        tiles.append(img)

    cols = args.cols
    rows = [np.concatenate(tiles[i:i + cols] + [np.zeros_like(tiles[0])] * ((cols - len(tiles[i:i + cols])) % cols), 1)
            for i in range(0, len(tiles), cols)]
    sheet = np.concatenate(rows, 0)
    legend = np.zeros((34, sheet.shape[1], 3), np.uint8)
    cv2.putText(legend, f"red=GT  green={args.pose_name}  blue={name}  | {pred.name} / {Path(args.obj).name}",
                (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), np.concatenate([legend, sheet], 0))
    print(f"→ {out}  ({len(tiles)} 프레임)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
