"""CAD-실물 형상 불일치를 모사한다 — **body 만** 교란하고 표준부(flange)는 고정한다.

    envs/cad/bin/python -m spatial_vision.cad.perturb_mesh \
        --obj assets/obj/foup_300_semi --delta-mm 10 --seed 0 --out runs/mesh_pert/d10_s0

왜 필요한가
    SEMI 가 규정하는 것은 flange 의 **테두리와 중심 홀뿐**이고, flange 중간부도 **body 도 제조사마다
    다르다**(사용자 확정 2026-08-10, 편차는 **cm 급**). 그런데 실측 최선 구성들이 **회전을 원거리
    `full`(= body 포함)에서** 가져온다 → 정밀 회전이 비표준부에 의존한다(PIPELINE_PLAN R5).

    ⚠️ **sim 은 이 축을 원천적으로 못 잡는다** — 렌더와 CAD 가 **같은 메쉬**라 불일치가 0 이다.
    그래서 관측은 그대로 두고 **FoundationPose 에 주는 CAD 만** 틀리게 만들어 민감도를 잰다.

교란의 모양 — 왜 저주파인가
    제조사 차이는 픽셀 잡음이 아니라 **덩어리진 형상 변화**다(문 형상, 측면 리브, 전체 폭).
    정점마다 독립으로 흔들면 정합에서 평균화되어 **영향을 과소평가**한다. 그래서 파장이 물체 크기
    급인 저주파 장(場)을 법선 방향으로 입힌다. (`eval/perturb_depth.py` 의 `corr` 모드와 같은 논리다.)

크기 규약
    `--delta-mm` 은 **교란된 정점의 평균 |변위|** 다(최댓값이 아니다). 달성치를 항상 출력한다.

무엇을 고정하나
    `top_flange.ply` 가 차지하는 영역은 **변위 0** 이고, 경계에서 `--taper-mm` 에 걸쳐 매끄럽게 올린다
    (급격히 끊으면 메쉬가 찢어져 교란이 아니라 파손을 재는 꼴이 된다).
    → pose frame 원점(flange 주 상면 중심)이 **불변**이므로 GT 를 그대로 쓸 수 있다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def smooth_field(V: np.ndarray, n_modes: int, rng: np.random.Generator) -> np.ndarray:
    """파장이 물체 크기 급인 저주파 무작위 장. 반환값은 평균 |f| = 1 로 정규화."""
    L = float((V.max(0) - V.min(0)).max())
    f = np.zeros(len(V))
    for _ in range(n_modes):
        k = rng.normal(size=3)
        k /= np.linalg.norm(k)
        wl = rng.uniform(0.5, 2.0) * L          # 물체 크기 급 파장 → 국소 잡음이 아니라 덩어리
        f += np.sin(2.0 * np.pi * (V @ k) / wl + rng.uniform(0, 2 * np.pi))
    m = np.abs(f).mean()
    return f / m if m > 1e-9 else f


def _smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def body_weight(V: np.ndarray, flange_lo: np.ndarray, flange_hi: np.ndarray,
                taper: float) -> np.ndarray:
    """flange AABB 안이면 0, 밖으로 `taper` mm 나가면 1 로 매끄럽게 오르는 가중치."""
    # AABB 까지의 유클리드 거리 (안쪽이면 0)
    d = np.linalg.norm(np.maximum(np.maximum(flange_lo - V, V - flange_hi), 0.0), axis=1)
    return _smoothstep(d / max(taper, 1e-6))


def rim_band_weight(V: np.ndarray, poly, band: float, r_hole: float, taper: float) -> np.ndarray:
    """**폭 `band` 의 테두리 밴드 전체**와 중심 홀을 0 으로 고정한다 (rim 밴드 가설의 대조군).

    `flange_weight` 는 외곽선 **곡선 하나**만 고정하고 12mm 로 taper 한다 — 즉 *"규격이 잡는 것은
    경계선뿐"* 이라는 모델이다. 여기서는 *"규격이 폭 W 의 띠를 잡는다"* 를 모델로 삼는다.
    이래야 **model=rim 밴드(불일치 0)** 와 **model=flange 전체(불일치 있음)** 를 같은 눈금에서 비교할 수 있다.

    거리는 XY 외곽선까지의 거리 — `cad.build_rim_obj` 의 밴드 정의와 **같은 도형**이어야 한다.
    """
    from shapely.geometry import MultiPoint, Point

    inner = poly.buffer(-band)
    d_out = np.array([inner.exterior.distance(Point(p)) if inner.contains(Point(p)) else 0.0
                      for p in V[:, :2]]) if not inner.is_empty else np.zeros(len(V))
    w_out = _smoothstep(d_out / max(taper, 1e-6))          # 밴드 안이면 0, 안쪽으로 taper 만큼 가면 1
    r = np.linalg.norm(V[:, :2], axis=1)
    w_in = _smoothstep((r - r_hole) / max(taper, 1e-6))     # 중심 홀도 고정
    return w_in * w_out


def flange_weight(V: np.ndarray, r_hole: float, r_rim: float, taper: float) -> np.ndarray:
    """flange **중간부만** 1 — SEMI 가 규정하는 **테두리와 중심 홀은 0** 으로 고정한다.

    반경 r = sqrt(x²+y²) 기준으로 `r_hole + taper < r < r_rim − taper` 구간만 완전히 자유롭고
    양끝에서 매끄럽게 0 으로 내린다. 규격이 잡는 것은 이 두 경계뿐이라는 사용자 확정 사실을 그대로 옮긴 것.
    """
    r = np.linalg.norm(V[:, :2], axis=1)
    w_in = _smoothstep((r - r_hole) / max(taper, 1e-6))      # 홀에서 멀어질수록 1
    w_out = _smoothstep((r_rim - r) / max(taper, 1e-6))      # 테두리에 가까울수록 0
    return w_in * w_out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="body 만 교란한 full 메쉬를 만든다 (flange 고정)")
    ap.add_argument("--obj", required=True, help="assets/obj/<obj_id>")
    ap.add_argument("--delta-mm", type=float, required=True, help="교란 정점의 평균 |변위| (mm)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--modes", type=int, default=4, help="저주파 모드 수. 클수록 잔잔해진다")
    ap.add_argument("--taper-mm", type=float, default=30.0, help="고정 영역 경계에서 변위를 올리는 폭")
    ap.add_argument("--region", default="body", choices=["body", "flange", "flange_all", "flange_in_full"],
                    help="body = 비표준 몸체만 (flange 고정) / "
                         "flange = flange **중간부만** (테두리·중심 홀 고정) / "
                         "flange_all = flange **전체**(테두리·중심 홀까지 전부 어긋난다) — "
                         "**실루엣/테두리 정합**을 시험하려면 이것이어야 한다(테두리를 고정하면 정의상 면역이다) / "
                         "flange_in_full = **`full.ply` 안의** flange 중간부만 (body 고정) — "
                         "원거리 `full` 경로가 flange 불일치에 흔들리는지 재는 대조군")
    ap.add_argument("--rim-band-mm", type=float, default=0.0,
                    help="[region=flange] 규격이 잡는 **테두리 띠의 폭**. 0 이면 외곽선 곡선만 고정하고 "
                         "taper 한다(기존 동작). >0 이면 폭 W 의 띠 **전체**를 고정한다 — "
                         "`build_rim_obj --band-mm W` 와 짝지어 *'model=밴드는 불일치 0'* 대조군을 만든다")
    ap.add_argument("--subdivide-mm", type=float, default=0.0,
                    help="교란 전 세분화 최대 변 길이. flange 는 정점이 적어 필요하다(권장 6)")
    ap.add_argument("--out", required=True, help="출력 obj 디렉토리")
    args = ap.parse_args(argv)

    obj = Path(args.obj)
    meta_src = json.loads((obj / "meta.json").read_text())

    if args.region in ("body", "flange_in_full"):
        target = "full.ply"
        keep = "top_flange.ply"
    else:
        target = "top_flange.ply"
        keep = "full.ply"

    full = trimesh.load(obj / target, process=False)

    # ⚠️ `top_flange.ply` 는 1,819 정점뿐이고 대부분이 테두리·홀에 몰려 있다. 그대로 교란하면
    # 중간부에 움직일 정점이 177개밖에 없어 **형상 변화가 아니라 스파이크**가 된다(최대/평균 6.4배).
    # 세분화는 형상을 바꾸지 않으므로 δ=0 대조군도 같은 메쉬로 만들면 비교가 성립한다.
    if args.subdivide_mm > 0:
        if args.region == "flange_in_full":
            # ⚠️ `full.ply` 를 통째로 6mm 세분화하면 33,722 → **2.2M 삼각형**이 되어 nvdiffrast 가
            #    cudaMalloc 에서 죽는다. flange 는 full.ply 안에서 **별개 solid**(연결성분)라
            #    그 부분만 세분화해도 T-junction 이 생기지 않는다.
            lo, hi = trimesh.load(obj / "top_flange.ply", process=False).bounds
            Vf, Ff = np.asarray(full.vertices), np.asarray(full.faces)
            inb = np.all((Vf >= lo - 1e-6) & (Vf <= hi + 1e-6), axis=1)
            sel = inb[Ff].all(axis=1)
            v_sub, f_sub = trimesh.remesh.subdivide_to_size(Vf, Ff[sel], max_edge=args.subdivide_mm)
            part_rest = trimesh.Trimesh(vertices=Vf, faces=Ff[~sel], process=False)
            merged = trimesh.util.concatenate(
                [part_rest, trimesh.Trimesh(vertices=v_sub, faces=f_sub, process=False)])
            print(f"세분화(flange 성분만 {sel.sum():,}면): 면 {len(Ff):,} → {len(merged.faces):,}")
            full = merged
        else:
            v, f_ = trimesh.remesh.subdivide_to_size(
                np.asarray(full.vertices), np.asarray(full.faces), max_edge=args.subdivide_mm)
            print(f"세분화: 정점 {len(full.vertices):,} → {len(v):,} (최대 변 {args.subdivide_mm}mm)")
            full = trimesh.Trimesh(vertices=v, faces=f_, process=False)

    V = np.asarray(full.vertices, dtype=np.float64)
    N = np.asarray(full.vertex_normals, dtype=np.float64)

    if args.region == "body":
        lo, hi = trimesh.load(obj / "top_flange.ply", process=False).bounds
        w = body_weight(V, lo, hi, args.taper_mm)
    else:
        sf = meta_src.get("standard_features_semi_e47_1_1106", {})
        r_hole = float(sf.get("center_hole_radius_mm", 20.5))
        fl_mesh = trimesh.load(obj / "top_flange.ply", process=False)
        if args.region == "flange_all":
            # 고정 영역 없음 — 테두리·중심 홀까지 전부 어긋난다. §20-1 이 실측한 flange 중앙 4.87mm 가 눈금.
            w = np.ones(len(V))
            print("flange **전체** 교란 (고정 영역 없음) — 테두리·중심 홀도 어긋난다")
        elif args.rim_band_mm > 0:
            from spatial_vision.cad.build_rim_obj import outline_polygon
            poly = outline_polygon(fl_mesh)
            w = rim_band_weight(V, poly, args.rim_band_mm, r_hole, args.taper_mm)
            print(f"flange 교란(테두리 띠 {args.rim_band_mm}mm 전체 고정): 중심 홀 r={r_hole:.1f} 고정, "
                  f"taper {args.taper_mm}mm")
        else:
            r_rim = float(sf.get("outline_side_x_mm", 142.0)) / 2.0     # 테두리 = 외곽 변까지
            w = flange_weight(V, r_hole, r_rim, args.taper_mm)
            print(f"flange 중간부만 교란: 중심 홀 r={r_hole:.1f} · 테두리 r={r_rim:.1f} 고정, "
                  f"taper {args.taper_mm}mm")
        if args.region == "flange_in_full":
            # `full.ply` 를 교란하되 **flange 아래(body)는 고정**한다. flange 하단에서 taper 로 내린다.
            z_bot = float(fl_mesh.bounds[0][2])
            w = w * _smoothstep((V[:, 2] - z_bot) / max(args.taper_mm, 1e-6))
            print(f"  → full.ply 안의 flange 만 (body 고정, z>{z_bot:.1f} 에서 taper)")

    rng = np.random.default_rng(args.seed)
    f = smooth_field(V, args.modes, rng)

    # 크기 보정 — 교란되는(w>0) 정점의 평균 |변위| 가 delta 가 되도록 스케일
    raw = f * w
    moved = w > 1e-3
    if not moved.any():
        print("❌ 교란 대상 정점이 없다 — taper 나 flange bbox 를 확인할 것")
        return 2
    scale = args.delta_mm / max(np.abs(raw[moved]).mean(), 1e-9)
    disp = (raw * scale)[:, None] * N

    V2 = V + disp
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    pert = trimesh.Trimesh(vertices=V2, faces=np.asarray(full.faces), process=False)
    pert.export(out_dir / target)

    # 교란하지 않은 쪽은 원본 그대로 — 대조군이 성립하려면 바이트 동일해야 한다
    for name in (keep, "keypoints.json", "meta.json"):
        p = obj / name
        if p.exists():
            (out_dir / name).write_bytes(p.read_bytes())

    d = np.linalg.norm(disp, axis=1)
    # 원점 규약 검사 — pose frame 원점(주 상면 중심)이 움직이면 GT 가 무효가 된다
    near_origin = (np.linalg.norm(V[:, :2], axis=1) < 5.0) & (V[:, 2] > -1.0)
    stats = {"region": args.region, "target_mesh": target,
             "delta_mm_requested": args.delta_mm,
             "delta_mm_achieved_mean": float(d[moved].mean()),
             "delta_mm_max": float(d.max()),
             "n_vertices": int(len(V)), "n_perturbed": int(moved.sum()),
             "fixed_vertices_moved": int((d[~moved] > 1e-6).sum()),
             "origin_region_max_disp_mm": float(d[near_origin].max()) if near_origin.any() else 0.0,
             "seed": args.seed, "modes": args.modes, "taper_mm": args.taper_mm,
             "rim_band_mm": args.rim_band_mm,
             "watertight": bool(pert.is_watertight), "source_obj": str(obj)}
    (out_dir / "meta_perturb.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"[{args.region}] δ 요청 {args.delta_mm}mm → 달성 평균 {stats['delta_mm_achieved_mean']:.2f}mm "
          f"(최대 {stats['delta_mm_max']:.2f}) | 교란 {moved.sum():,}/{len(V):,} "
          f"| 고정영역 이동 {stats['fixed_vertices_moved']} "
          f"| 원점부 최대 {stats['origin_region_max_disp_mm']:.3f}mm "
          f"| watertight {pert.is_watertight}")
    print(f"→ {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
