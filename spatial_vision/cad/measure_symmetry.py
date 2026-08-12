"""물체의 **회전 구속력**을 측정한다 — "이 형상은 yaw 를 정할 수 있는가".

    envs/cad/bin/python -m spatial_vision.cad.measure_symmetry --obj assets/obj/foup_300_semi

왜 필요한가
    pose 추정이 회전에서 실패할 때 원인은 둘 중 하나다: (a) 형상에 방향 정보가 없거나,
    (b) 정보는 있는데 관측이 그것을 못 잡거나. **둘은 처방이 정반대**다 — (a) 면 다른 부분을 봐야 하고,
    (b) 면 마스크·depth 품질을 고쳐야 한다. 이 스크립트는 (a) 를 배제/확정한다.

방법
    형상을 Z 축으로 θ 회전시켜 원래 표면과의 거리를 잰다. 잔차가 작으면 그 각도로 착각해도 관측이
    같다는 뜻이다. 세 가지로 본다:
      [1] 3D 표면 잔차     — 이상적 정합기가 볼 수 있는 정보량의 상한
      [2] 테두리 r(φ)      — 실루엣이 주는 방향 정보 (사분면별로 접어서 비교)
      [3] 비대칭 기하의 위치 — 그 정보가 **위에서 보이는 곳에 있는가**

⚠️ 반드시 **pose 원점 기준**으로 재야 한다. `trimesh.to_2D()` 등 임의 2D 프레임에서 재면 중심이
   어긋나 가짜 비대칭이 나온다(최대반경이 어긋나는 것이 신호다). — RESULTS.md § flange 의 회전 구속
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def rot_z(deg: float) -> np.ndarray:
    t = np.deg2rad(deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def surface_residual(mesh: trimesh.Trimesh, angles, n: int = 120000, seed: int = 1):
    """[1] 표면 점을 θ 회전 → 원본 표면까지의 거리. 분위수까지 함께 본다(평균만 보면 속는다)."""
    pts, _ = trimesh.sample.sample_surface(mesh, n, seed=seed)
    pq = trimesh.proximity.ProximityQuery(mesh)
    rows = []
    for a in angles:
        d = np.abs(pq.signed_distance(pts @ rot_z(a).T))
        rows.append(dict(deg=float(a), median=float(np.median(d)), mean=float(d.mean()),
                         p95=float(np.percentile(d, 95)), p99=float(np.percentile(d, 99)),
                         max=float(d.max())))
    return pts, pq, rows


def rim_profile(mesh: trimesh.Trimesh, z: float, r_min: float, nb: int = 3600):
    """[2] 높이 z 단면의 테두리 r(φ). **물체 프레임 그대로** 쓴다."""
    sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1.0])
    if sec is None:
        return None
    V = sec.vertices[:, :2]
    r = np.hypot(*V.T)
    rim = V[r >= r_min]
    if len(rim) < 8:
        return None
    a = np.degrees(np.arctan2(rim[:, 1], rim[:, 0]))
    rr = np.hypot(*rim.T)
    o = np.argsort(a)
    grid = np.linspace(-180, 180, nb, endpoint=False)
    return grid, np.interp(grid, a[o], rr[o], period=360)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="회전 대칭 / 회전 구속력 측정")
    ap.add_argument("--obj", required=True, help="assets/obj/<obj_id>")
    ap.add_argument("--meshes", nargs="*", default=["top_flange", "full"])
    ap.add_argument("--section-z", type=float, default=-0.5, help="테두리를 뽑을 단면 높이(mm)")
    ap.add_argument("--rim-min-r", type=float, default=45.0, help="이 반경 이상을 테두리로 본다")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    obj = Path(args.obj)
    report = {}
    for name in args.meshes:
        p = obj / f"{name}.ply"
        if not p.exists():
            print(f"건너뜀(없음): {p}")
            continue
        mesh = trimesh.load(p, process=False)
        print(f"\n{'='*72}\n{name}.ply  faces={len(mesh.faces)}  bbox={mesh.bounds.round(1).tolist()}")
        ent = {"faces": int(len(mesh.faces))}

        # [1] 3D 표면 잔차
        angles = [0, 1, 3, 5, 45, 90, 180, 270]
        pts, pq, rows = surface_residual(mesh, angles)
        print("\n[1] 3D 표면 잔차 (mm) — 90°/180°/270° 가 작으면 그 각도로 착각한다")
        print("   θ°   median      p95      p99      max")
        for r in rows:
            print(f"  {r['deg']:4.0f}  {r['median']:7.4f} {r['p95']:8.4f} {r['p99']:8.4f} {r['max']:8.4f}")
        ent["surface_residual"] = rows

        # [3] 대칭을 깨는 기하가 어디 있나 (위에서 보이는가)
        d90 = np.abs(pq.signed_distance(pts @ rot_z(90).T))
        bad = d90 > 0.5
        if bad.any():
            q = pts[bad]
            top = q[q[:, 2] > mesh.bounds[1][2] - 1.0]
            print(f"\n[3] 90° 대칭을 깨는 표면 {bad.mean()*100:.2f}%  "
                  f"Z {q[:,2].min():.1f}~{q[:,2].max():.1f}mm  반경 {np.hypot(q[:,0],q[:,1]).min():.0f}~{np.hypot(q[:,0],q[:,1]).max():.0f}mm")
            print(f"    이 중 상면(위에서 보임)에 있는 것: 전체 표면의 {len(top)/len(pts)*100:.3f}%"
                  f"  ← 이 값이 작으면 정보는 있으나 카메라가 못 본다")
            ent["asym_frac"] = float(bad.mean())
            ent["asym_visible_frac"] = float(len(top) / len(pts))

        # [2] 테두리 r(φ) 를 사분면별로 접어서 비교
        prof = rim_profile(mesh, args.section_z, args.rim_min_r)
        if prof is not None:
            grid, rp = prof
            nb = len(rp)
            print(f"\n[2] 테두리 r(φ) at Z={args.section_z}mm : {rp.min():.2f}~{rp.max():.2f} mm")
            print("   n중 대칭 잔차 (median / max):", end="")
            sym = {}
            for n in (2, 3, 4, 6):
                e = np.abs(rp - np.roll(rp, nb // n))
                sym[n] = (float(np.median(e)), float(e.max()))
                print(f"  {n}중 {np.median(e):.2f}/{e.max():.2f}", end="")
            print()
            ent["rim_symmetry"] = sym
            # 4중 기준 사분면 접기 — max 를 반드시 함께 본다(median 만 보면 대칭으로 착각한다)
            print("   사분면 접기 (4중):  φ내      Q1      Q2      Q3      Q4    편차")
            worst = 0.0
            for k in range(0, nb // 4, nb // 72):
                qv = [rp[(k + nb // 4 * j) % nb] for j in range(4)]
                dev = max(qv) - min(qv)
                worst = max(worst, dev)
                if dev > 0.5 or k % (nb // 18) == 0:
                    print(f"                    {k*360/nb:5.1f}° " + " ".join(f"{v:7.2f}" for v in qv) + f" {dev:7.2f}")
            print(f"   → 사분면 최대 편차 **{worst:.2f} mm**  (0 에 가까우면 yaw 정보 없음)")
            ent["quadrant_max_dev_mm"] = float(worst)
        report[name] = ent

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\n→ {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
