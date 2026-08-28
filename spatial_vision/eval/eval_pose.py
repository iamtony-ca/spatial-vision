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

🔴 **표를 읽는 법 — 표가 둘이다** (2026-08-27 추가)
    첫 표는 **평균**이고 둘째 표가 **중앙값 / p90 / 최대 / KPI** 다. 이 파이프라인은 대실패 한 건이
    평균을 지배하므로(교훈 #14: 평균 85mm 인데 중앙값 3.8mm 였던 사례) **처방은 둘째 표로 낸다.**
    ⚠️ 옛 문서의 수치를 인용할 때는 **어느 표의 값인지** 먼저 확인할 것(§25-1b).

🔴 **`n` 열을 반드시 본다.** 프레임이 없으면 조용히 빠진다 — 예측 디렉토리가 도중에 죽었거나
    `--limit-frames` 로 잘렸으면 **10프레임 결과가 120프레임 결과 옆에 나란히 찍힌다.**
    n 이 다른 두 행은 **비교 대상이 아니다**(꼬리 통계는 특히).
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
    # KPI (2026-08-07 확정) — 여기 한 곳에서만 정의한다. 문서마다 손으로 세던 것을 없앤다.
    ap.add_argument("--kpi-mm", type=float, default=5.0, help="KPI 평행이동 상한 (mm)")
    ap.add_argument("--kpi-deg", type=float, default=3.0, help="KPI 회전 상한 (deg)")
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
    print(f"── 평균 ──  🔴 처방은 아래 «중앙값·꼬리» 표로 낸다 (교훈 #14)")
    print(f"{'구성':<28}{'단계':<10}{'n':>5}{'R err°':>9}{'t err mm':>10}{'tX':>8}{'tY':>8}{'tZ':>8}"
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
            # ⚠️ 아래 6개 키(`rot_deg`·`trans_mm`·…)는 **평균**이다. 옛 산출물을 읽는 코드가
            #    있으므로 이름·의미를 바꾸지 않고 `median`/`p90`/`max`/`kpi` 를 **덧붙인다.**
            rr = np.array([r["rot_deg"] for r in rows], float)
            tt = np.array([r["trans_mm"] for r in rows], float)
            aa = np.array([r["add_mm"] for r in rows], float)
            n_ok = int(((rr <= args.kpi_deg) & (tt <= args.kpi_mm)).sum())
            q = lambda v: {"median": round(float(np.median(v)), 4),  # noqa: E731
                           "p90": round(float(np.percentile(v, 90)), 4),
                           "max": round(float(v.max()), 4)}
            summary = {"n": len(rows), "rot_deg": m("rot_deg"), "trans_mm": m("trans_mm"),
                       "dx": m("dx"), "dy": m("dy"), "dz": m("dz"),
                       "add_mm": m("add_mm"), "adds_mm": m("adds_mm"),
                       "stat": {"rot_deg": q(rr), "trans_mm": q(tt), "add_mm": q(aa)},
                       "kpi": {"n_pass": n_ok, "n": len(rows),
                               "pct": round(100.0 * n_ok / len(rows), 1),
                               "kpi_deg": args.kpi_deg, "kpi_mm": args.kpi_mm},
                       "frames": rows}
            report["results"][f"{pred_root.name}/{stage}"] = summary
            print(f"{pred_root.name:<28}{stage:<10}{len(rows):>5}"
                  f"{summary['rot_deg']:>9.3f}{summary['trans_mm']:>10.3f}"
                  f"{summary['dx']:>8.2f}{summary['dy']:>8.2f}{summary['dz']:>8.2f}"
                  f"{summary['add_mm']:>9.3f}{summary['adds_mm']:>9.3f}")

    # ── 중앙값·꼬리·KPI ─────────────────────────────────────────────────────
    # 🔴 이 표가 처방의 근거다. 평균은 대실패 한 건에 끌려간다(교훈 #14·#16).
    res = report["results"]
    if res:
        ns = {v["n"] for v in res.values()}
        print(f"\n── 중앙값 / p90 / 최대  ·  KPI = R ≤ {args.kpi_deg}° & t ≤ {args.kpi_mm}mm ──")
        print(f"{'구성':<28}{'단계':<10}{'n':>5}{'R 중앙':>9}{'R p90':>9}{'R 최대':>9}"
              f"{'t 중앙':>9}{'t p90':>9}{'t 최대':>9}{'ADD 중앙':>10}{'KPI':>11}")
        for key, v in res.items():
            name, _, stage = key.rpartition("/")
            s, k = v["stat"], v["kpi"]
            kpi_txt = "{}/{}".format(k["n_pass"], k["n"])
            print(f"{name:<28}{stage:<10}{v['n']:>5}"
                  f"{s['rot_deg']['median']:>9.3f}{s['rot_deg']['p90']:>9.3f}{s['rot_deg']['max']:>9.2f}"
                  f"{s['trans_mm']['median']:>9.3f}{s['trans_mm']['p90']:>9.3f}{s['trans_mm']['max']:>9.2f}"
                  f"{s['add_mm']['median']:>10.3f}{kpi_txt:>11}")
        if len(ns) > 1:
            print(f"\n🔴 **행마다 프레임 수가 다르다** {sorted(ns)} — 이 행들은 나란히 비교할 수 없다. "
                  f"꼬리 통계(p90·최대·KPI)는 특히 표본 수에 좌우된다(교훈 #58).")
        if min(ns) < 40:
            print(f"⚠️ n={min(ns)} 는 꼬리를 못 본다 — n=40 무결점의 실패율 95% 상한이 7.5% 다. "
                  f"«40/40» 을 «≤7.5%» 로 읽는다(교훈 #58).")

    out = Path(args.out) if args.out else Path(args.pred[0]) / "metrics_pose.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n상세 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
