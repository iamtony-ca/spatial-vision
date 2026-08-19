"""M5 평가 — 추정 pose 를 sim GT 와 비교한다.

    envs/pose/bin/python -m spatial_vision.eval.eval_pose \
        --gt runs/semi01 --pred runs/semi01_pose_gt --obj assets/obj/foup_300_semi

무엇을 재나
    R err   : 측지 회전 오차 (deg)
    t err   : 평행이동 오차 (mm) — **축별로도 낸다.** Z 는 depth 계열 bias 가 직접 들어오는 축이라
              (§M3 의 flange 음의 bias −2.1~−2.9mm) XY 와 섞어 놓으면 원인 추적이 안 된다.
    ADD     : 모델 점의 평균 대응거리 (mm)
    ADD-S   : 최근접점 기준 — **대칭/근사대칭에서 ADD 는 과하게 벌한다.** top flange 는 근사 대칭이라
              두 값의 괴리 자체가 "방향을 맞췄는가"의 지표가 된다(ADD≫ADD-S 면 90°/180° 오추정 의심).

⚠️ ADD-S 는 관대한 지표다. 단독으로 쓰면 대칭 오추정을 통과시킨다 → 항상 ADD 와 함께 본다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from spatial_vision.contracts import rotation_angle_deg


def load_pose(p: Path) -> tuple[np.ndarray, np.ndarray] | None:
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    return np.asarray(d["R"], float).reshape(3, 3), np.asarray(d["t_mm"], float).reshape(3)


# 🔴 `arccos((tr−1)/2)` 는 항등 근처에서 오차를 **제곱근으로 증폭**한다 — 저장된 R 이
#    정확히 직교가 아니라(9자리 반올림) **자기 자신과 비교해도 0.03° 가 나왔다**
#    (실측 p90 0.028° · 최대 0.049°, 2026-08-19). 정본은 `contracts.rotation_angle_deg`.
def rot_err_deg(R1: np.ndarray, R2: np.ndarray) -> float:
    return rotation_angle_deg(R1, R2)


def add_metrics(pts: np.ndarray, Rg, tg, Rp, tp) -> tuple[float, float]:
    """ADD / ADD-S (mm). pts 는 모델 점(mm, 객체 좌표계)."""
    A = (Rg @ pts.T).T + tg
    B = (Rp @ pts.T).T + tp
    add = float(np.linalg.norm(A - B, axis=1).mean())
    # ADD-S: B 의 각 점에서 A 의 최근접점까지
    from scipy.spatial import cKDTree

    adds = float(cKDTree(A).query(B, k=1)[0].mean())
    return add, adds


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="M5 pose 평가 (예측 vs sim GT)")
    ap.add_argument("--gt", required=True, help="캡처 디렉토리 (pose_gt.json 보유)")
    ap.add_argument("--pred", nargs="+", required=True)
    ap.add_argument("--obj", required=True, help="assets/obj/<id> (full.ply — ADD 계산용)")
    ap.add_argument("--n-points", type=int, default=4096)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    import trimesh

    mesh = trimesh.load(str(Path(args.obj) / "full.ply"), process=False)
    rng = np.random.default_rng(0)
    idx = rng.choice(len(mesh.vertices), min(args.n_points, len(mesh.vertices)), replace=False)
    pts = np.asarray(mesh.vertices)[idx]

    gt_root = Path(args.gt)
    frames = sorted([p for p in gt_root.glob("frame_*") if p.is_dir()]) or [gt_root]
    report = {"gt": str(gt_root), "n_frames": len(frames), "results": {}}

    print(f"\n═══ M5 pose | GT {gt_root} | {len(frames)} 프레임 | ADD 점 {len(pts)}개")
    print(f"{'구성':<28}{'단계':<10}{'R err°':>9}{'t err mm':>10}{'tX':>8}{'tY':>8}{'tZ':>8}"
          f"{'ADD':>9}{'ADD-S':>9}")

    for pred_root in map(Path, args.pred):
        for stage_file, stage in [("pose_coarse.json", "coarse"), ("pose_refined.json", "refined")]:
            rows = []
            for f in frames:
                g = load_pose(f / "pose_gt.json")
                p = load_pose((pred_root / f.name) / stage_file)
                if g is None or p is None:
                    continue
                (Rg, tg), (Rp, tp) = g, p
                add, adds = add_metrics(pts, Rg, tg, Rp, tp)
                dt = tp - tg
                rows.append({"frame": f.name, "rot_deg": rot_err_deg(Rg, Rp),
                             "trans_mm": float(np.linalg.norm(dt)),
                             "dx": float(dt[0]), "dy": float(dt[1]), "dz": float(dt[2]),
                             "add_mm": add, "adds_mm": adds})
            if not rows:
                continue
            m = lambda k: float(np.mean([r[k] for r in rows]))  # noqa: E731
            summary = {"n": len(rows), "rot_deg": m("rot_deg"), "trans_mm": m("trans_mm"),
                       "dx": m("dx"), "dy": m("dy"), "dz": m("dz"),
                       "add_mm": m("add_mm"), "adds_mm": m("adds_mm"), "frames": rows}
            report["results"][f"{pred_root.name}/{stage}"] = summary
            print(f"{pred_root.name:<28}{stage:<10}{summary['rot_deg']:>9.3f}{summary['trans_mm']:>10.3f}"
                  f"{summary['dx']:>8.2f}{summary['dy']:>8.2f}{summary['dz']:>8.2f}"
                  f"{summary['add_mm']:>9.3f}{summary['adds_mm']:>9.3f}")

    out = Path(args.out) if args.out else Path(args.pred[0]) / "metrics_pose.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n상세 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
