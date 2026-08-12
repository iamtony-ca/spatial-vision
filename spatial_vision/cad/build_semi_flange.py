"""SEMI E47.1 규격·실물에 맞춰 **top flange 만 고친 새 obj** 를 만든다. 원본은 건드리지 않는다.

    envs/cad/bin/python -m spatial_vision.cad.build_semi_flange \
        --obj assets/obj/foup_300_semi --out assets/obj/foup_300_semi_spec

무엇을 고치나 — `RESULTS.md §24` 가 찾은 두 가지

1. **중심 홀 `d63`** — 규격은 **상판 밑면(상면에서 `z49` 아래)에서 ø35 ± 0.1** 이다.
   원본은 그 자리에서 **ø31.2** 다(상면 개구 ø41 에서 45° 원뿔로 내려오다 보니 3.8mm 모자란다).
   → 원뿔 벽을 **반경 방향으로 Δ 만큼 밀어** 상판 밑면에서 정확히 ø35 가 되게 한다.
   45° 원뿔이므로 상면 개구는 자동으로 ø(35 + 2·z49) 가 된다.
   ⚠️ **상판 밑면보다 아래**(평탄 바닥 `x69`=7.6±0.1, 2차 원뿔 `γ`=52±1°)는 **모델링하지 않는다** —
   위에서 내려다보는 우리 파이프라인에서 보이지 않고, 원본 메쉬에 그 구조가 아예 없다.

2. **최외곽 융기** (실물 관측, 사용자) — 실물은 최외곽 테두리가 상판보다 **약 2mm 높고**,
   그 높이를 **1~2.5mm 폭**으로 유지하다 **라운드**되며 `z49` 로 내려온다. 원본은 평평하다.
   → 상면 정점을 **윤곽까지의 거리 d** 로 나눠 `d ≤ flat` 는 +raise, 그 다음 `round` 폭에서
   **1/4 원 필렛**으로 0 까지 내린다.

★ **원점 규약은 유지된다** — 융기 링의 면적(≈1,000mm²)이 주 상면(≈18,300mm²)보다 훨씬 작아
  `dominant_top_plane`(면적 최대)은 여전히 z=0 을 고른다. 생성 후 실제로 검사한다.

🔴 **자산이 바뀌므로 캡처부터 다시 해야 한다** (횡단 정리 #40). 이 obj 로는
  `build_usd` → `capture_sim` → stereo → segmentation → pose 를 새로 돌린다. 옛 런에 섞어 쓰면 안 된다.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Point

from spatial_vision.cad.build_rim_obj import outline_polygon
from spatial_vision.cad.prepare_obj import build_keypoints, dominant_top_plane, measure_standard_features


def plate_underside_z(mesh: trimesh.Trimesh, probe_r: float = 30.0, probe_y: float = 0.0) -> float:
    """주 환상부(r=probe_r)에서 상판 밑면 z — 점유 격자로 확실히 읽는다.

    ⚠️ `probe_y=0` 은 **position notch 자리**다(모든 변의 0 위치에 깊이 5mm 노치가 있다).
    최외곽(r≥66)을 잴 때는 노치를 피해 `probe_y=20` 처럼 옮겨야 한다 — 안 그러면 "재료 없음" 이 난다.
    """
    zs = np.arange(0.5, -12.001, -0.05)
    P = np.stack([np.full(len(zs), probe_r), np.full(len(zs), probe_y), zs], 1)
    ins = mesh.contains(P)
    k = np.where(ins)[0]
    if not len(k):
        raise RuntimeError(f"r={probe_r}mm 에 재료가 없다 — probe_r 을 조정할 것")
    return float(zs[k[-1]])


def cone_radius_at(mesh: trimesh.Trimesh, z: float, r_max: float = 40.0) -> float:
    """높이 z 에서 중심 홀 벽의 반경(= 그 높이에서 재료가 시작하는 반경)."""
    rs = np.arange(0.0, r_max, 0.02)
    P = np.stack([rs, np.zeros(len(rs)), np.full(len(rs), z)], 1)
    ins = mesh.contains(P)
    return float(rs[np.argmax(ins)]) if ins.any() else float("nan")


def fillet(d: np.ndarray, raise_mm: float, flat: float, round_w: float,
           profile: str = "smoothstep") -> np.ndarray:
    """윤곽까지 거리 d 에 대한 융기 높이. d≤flat 은 raise, 그 뒤 `round_w` 에 걸쳐 0 으로.

    ⚠️ 1/4 원(`arc`)은 안쪽 끝에서 **접선이 수직**이라 판과 만나는 곳에 crease 가 생기고,
    삼각형 크기만큼 능선이 **톱니처럼** 보인다(렌더로 확인). 기본은 양 끝 기울기가 0 인
    **smoothstep** — 실물의 "라운드 처리" 에도 이쪽이 가깝다.
    """
    h = np.zeros_like(d)
    h[d <= flat] = raise_mm
    m = (d > flat) & (d <= flat + round_w)
    t = (d[m] - flat) / max(round_w, 1e-9)
    if profile == "arc":
        h[m] = raise_mm * np.sqrt(np.clip(1.0 - t * t, 0.0, 1.0))
    else:
        h[m] = raise_mm * (1.0 - (t * t * (3.0 - 2.0 * t)))      # C1 매끄러운 어깨
    return h


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SEMI 규격·실물에 맞춘 flange 로 새 obj 생성")
    ap.add_argument("--obj", required=True, help="원본 assets/obj/<obj_id> (변경하지 않는다)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--hole-d63", type=float, default=35.0, help="상판 밑면에서의 중심 홀 지름 (SEMI d63)")
    ap.add_argument("--hole-taper-mm", type=float, default=0.0,
                    help="원뿔 변위를 아래에서 0 으로 되돌리는 구간. **0 이 기본** — 0 이 아니면 "
                         "그 구간에서 **원뿔 각이 바뀌어 홀이 중간에 꺾인다**(렌더로 확인, dr/dz 1.0→1.65). "
                         "규격은 각(`β`)을 정하므로 **각을 유지한 채 통째로 밀어야** 한다")
    ap.add_argument("--rim-raise-mm", type=float, default=2.0, help="최외곽 융기 높이 (실물 관측 ≈2mm)")
    ap.add_argument("--rim-flat-mm", type=float, default=1.75, help="융기를 유지하는 폭 (실물 1~2.5mm)")
    ap.add_argument("--rim-round-mm", type=float, default=2.5, help="라운드로 내려오는 폭")
    ap.add_argument("--pre-subdivide-mm", type=float, default=6.0,
                    help="먼저 **전체**를 이 크기로 균일 세분화한다. 원본 상면은 거대 삼각형 몇 개라 "
                         "이 단계 없이 띠만 세분화하면 그 거대 삼각형이 통째로 쪼개져 43만 면이 된다")
    ap.add_argument("--subdivide-mm", type=float, default=1.0,
                    help="상면 정점이 성글면 융기·라운드를 표현할 수 없다 — 먼저 세분화한다")
    ap.add_argument("--hole-raise-mm", type=float, default=0.0,
                    help="**중심 홀 주변 융기** 높이. 실물은 제조사마다 홀 최상면에 융기가 있는 것과 "
                         "없는 것이 있다(사용자 확정 2026-08-11). 45° 원뿔이 위로 연장되므로 "
                         "**최상면 개구가 `2×raise` 만큼 커진다** (ø45 → raise 2mm 면 ø49). "
                         "0=없음(현행 자산)")
    ap.add_argument("--hole-flat-mm", type=float, default=1.75, help="홀 융기를 유지하는 폭")
    ap.add_argument("--hole-round-mm", type=float, default=2.5, help="홀 융기가 라운드로 내려오는 폭")
    ap.add_argument("--no-hole", action="store_true", help="중심 홀 수정 생략")
    ap.add_argument("--no-rim", action="store_true", help="최외곽 융기 생략")
    ap.add_argument("--rim-plate-mm", type=float, default=0.0,
                    help="**외곽 밴드의 판 두께**(융기 제외)를 이 값으로 맞춘다. 0=끄기. "
                         "SEMI 는 판 두께를 `z49` 로 정하고 실물은 균일한데, 우리 CAD 는 안쪽 5.0mm / "
                         "외곽 밴드 8.0mm 로 **계단이 있다**. 5.0 을 주면 밴드를 세로로 압축해 "
                         "균일 5mm 로 만든다(상면 z=0 고정, 밑면 −8 → −5, 벽 정점도 비례 이동해 접힘 없음). "
                         "그러면 융기 포함 총 높이가 5+raise = **7.0mm** 가 된다")
    ap.add_argument("--rim-band-mm", type=float, default=18.0,
                    help="[--rim-plate-mm] 외곽 밴드로 볼 폭(윤곽에서 안쪽으로). 우리 CAD 는 약 16mm")
    ap.add_argument("--rim-profile", default="smoothstep", choices=["smoothstep", "arc"],
                    help="융기에서 판으로 내려오는 단면. smoothstep=양 끝 기울기 0(기본, crease 없음) / "
                         "arc=1/4 원(안쪽 끝이 수직 접선이라 능선이 톱니처럼 보인다)")
    ap.add_argument("--rim-mode", default="top-only", choices=["top-only", "translate"],
                    help="top-only=**밑면은 그대로 두고 위로만 두꺼워진다**(기본, 실물 확인 — 사용자 2026-08-11). "
                         "최외곽은 `z49` 적용 대상이 아니므로 그 자리 두께가 8mm 를 넘어도 위반이 아니다. "
                         "translate=밴드째 평행이동해 두께를 보존(대조군)")
    args = ap.parse_args(argv)

    src, out = Path(args.obj), Path(args.out)
    fl0 = trimesh.load(src / "top_flange.ply", process=False)

    z_bot = plate_underside_z(fl0)
    r_now = cone_radius_at(fl0, z_bot)
    # 원뿔이 끝나는 높이 — 그 아래로는 벽이 없다. 변위를 여기까지 **같은 크기로** 준다.
    _zs = np.arange(0.0, -30.0, -0.25)
    _r = np.array([cone_radius_at(fl0, z) for z in _zs])
    z_cone_end = float(_zs[np.argmax(_r <= 0.05)]) if (_r <= 0.05).any() else float(_zs[-1])
    r_target = args.hole_d63 / 2.0
    delta = r_target - r_now
    print(f"상판 두께 z49 = {-z_bot:.2f}mm | 밑면 홀 반경 {r_now:.2f} → 목표 {r_target:.2f} (Δ {delta:+.2f}mm) "
          f"| 원뿔 끝 z={z_cone_end:.2f}mm")

    # ⚠️ 전체를 1mm 로 세분화하면 3,634 → **730,634 면**이 되어 nvdiffrast 가 죽는다(교훈 #43).
    #    변위가 생기는 **띠만** 세분화한다. 그 띠의 바깥 경계에서는 변위가 0 이므로
    #    T-junction 이 생겨도 **기하학적 틈은 없다**(새 정점이 이웃 모서리 위에 그대로 남는다).
    Vp, Fp = trimesh.remesh.subdivide_to_size(np.asarray(fl0.vertices), np.asarray(fl0.faces),
                                              max_edge=args.pre_subdivide_mm)
    print(f"1차 균일 세분화({args.pre_subdivide_mm}mm): 면 {len(fl0.faces):,} → {len(Fp):,}")
    V0, F0 = Vp, Fp
    bnd0 = outline_polygon(fl0).exterior
    rim_w = args.rim_flat_mm + args.rim_round_mm + 2.0        # 여유 2mm
    r_top0 = cone_radius_at(fl0, 0.0)
    # ⚠️ **면 중심**으로 고르면 안 된다 — 중심은 밖에 있는데 **꼭짓점 하나가 변위 영역에 걸친**
    #    거대 삼각형이 통째로 기울어 주 상면이 z=+1.35 로 밀려났다(실측). **꼭짓점 기준**으로 고른다.
    dV = np.array([bnd0.distance(Point(q[0], q[1])) for q in V0])
    rV = np.hypot(V0[:, 0], V0[:, 1])
    need = np.zeros(len(F0), bool)
    if not args.no_rim:
        # 융기는 **상면에만** 생긴다 → 옆벽·밑면 면까지 잘게 쪼갤 이유가 없다(.all 로 제한)
        z_lo = -0.5 if (args.rim_mode == "top-only" and args.rim_plate_mm <= 0) else -10.5
        need |= (dV[F0] < rim_w).any(axis=1) & (V0[F0][:, :, 2] > z_lo).all(axis=1)
    hole_ridge_w = args.hole_raise_mm + args.hole_flat_mm + args.hole_round_mm + 2.0
    if not args.no_hole or args.hole_raise_mm > 0:
        need |= (rV[F0] < r_top0 + max(3.0, hole_ridge_w)).any(axis=1) & \
                (V0[F0][:, :, 2] > z_cone_end - 1.0).all(axis=1)
    v_sub, f_sub = trimesh.remesh.subdivide_to_size(V0, F0[need], max_edge=args.subdivide_mm)
    rest = trimesh.Trimesh(vertices=V0, faces=F0[~need], process=False)
    merged = trimesh.util.concatenate([rest, trimesh.Trimesh(vertices=v_sub, faces=f_sub, process=False)])
    v, f = np.asarray(merged.vertices), np.asarray(merged.faces)
    print(f"세분화(변위 띠 {int(need.sum()):,}면만): 면 {len(F0):,} → {len(f):,}")
    V = np.asarray(v, float).copy()
    r = np.hypot(V[:, 0], V[:, 1])

    n_hole = n_rim = 0
    if not args.no_hole:
        # ⚠️ 벽 정점만 밀면 **옛 상면 링(r 20.5~22.5)이 얇은 턱으로 남는다**(실측: 개구가 ø45 가
        #    아니라 ø42.2 로 측정됐다). 그래서 "새 원뿔 안쪽에 들어온 모든 정점을 벽으로 밀어낸다".
        r_top0 = cone_radius_at(fl0, 0.0)
        taper = args.hole_taper_mm
        if taper > 0:
            w = np.clip((V[:, 2] - (z_cone_end - taper)) / taper, 0.0, 1.0)
        else:
            w = np.ones(len(V))                        # 각을 유지하려면 **전 구간 동일 변위**
        r_new = r_top0 + delta * w + V[:, 2]           # 45° 원뿔의 새 반경(높이 z 에서)
        band = (V[:, 2] <= 0.02) & (V[:, 2] >= z_cone_end - max(taper, 0.5)) & (r < r_new + 0.6)
        scale = np.where((r > 1e-6) & band, np.maximum(r_new, r) / np.maximum(r, 1e-6), 1.0)
        V[band, :2] *= scale[band, None]
        n_hole = int(band.sum())

    if args.rim_plate_mm > 0:
        # ★ 판 두께를 균일하게 — 밴드를 **세로로 압축**한다(상면 0 고정). 밑면만 올리면 외벽 중간
        #   정점이 남아 접힌다. 비례 축소하면 벽이 그대로 수직으로 짧아진다. 융기는 이 다음에 얹는다.
        bnd0e = outline_polygon(fl0).exterior
        z_rim_bot = plate_underside_z(fl0, probe_r=68.0, probe_y=20.0)   # 노치 회피
        sc = args.rim_plate_mm / max(-z_rim_bot, 1e-9)
        dV2 = np.array([bnd0e.distance(Point(q[0], q[1])) for q in V])
        band = (dV2 < args.rim_band_mm) & (V[:, 2] <= 1e-6) & (V[:, 2] >= z_rim_bot - 1e-3)
        V[band, 2] *= sc
        print(f"  외곽 밴드 판 두께 {-z_rim_bot:.2f} → {args.rim_plate_mm:.2f}mm "
              f"(정점 {int(band.sum()):,}개, 배율 {sc:.3f})")

    if not args.no_rim:
        bnd = outline_polygon(fl0).exterior
        # ★ 실물은 **밑면 그대로, 위로만 두꺼워진다**(사용자 확인 2026-08-11). 그래서 최외곽에서
        #   두께가 `z49`(≤8)를 넘지만 **위반이 아니다** — 그 부위는 애초에 `z49` 가 규정하는 곳이 아니다.
        #   원본 외곽 밴드가 이미 8.0mm(한계 그 자체)라 +2mm 를 얹으면 9.9mm 가 된다.
        #   (`--rim-mode translate` 는 두께를 보존하는 대조군 — 실물과 다르다.)
        if args.rim_mode == "translate":
            idx = np.where((V[:, 2] > -10.5) & (V[:, 2] < 0.5))[0]
        else:
            idx = np.where(np.abs(V[:, 2]) < 1e-3)[0]
        d = np.array([bnd.distance(Point(V[i, 0], V[i, 1])) for i in idx])
        h = fillet(d, args.rim_raise_mm, args.rim_flat_mm, args.rim_round_mm, args.rim_profile)
        V[idx, 2] += h
        n_rim = int((h > 1e-9).sum())

    n_hring = 0
    if args.hole_raise_mm > 0:
        # ★ **홀 주변 융기** — 최외곽 융기와 같은 프로파일이되 기준이 **홀 가장자리에서 바깥으로**다.
        #   ⚠️ z 만 올리면 옛 개구 자리에 수직 턱이 생긴다. 실물은 45° 원뿔이 그대로 위로 이어지므로
        #   올린 만큼 **반경도 밀어내** 개구가 `2×raise` 커진다(ø45 → raise 2 면 ø49).
        #   외곽 융기 **다음에** 얹는다 — 앞 단계가 `|z|<1e-3` 로 정점을 고르기 때문이다.
        r_open = r_top0 + delta                       # 홀 수정 후의 최상면 개구 반경
        idx = np.where(np.abs(V[:, 2]) < 1e-3)[0]
        rr = np.hypot(V[idx, 0], V[idx, 1])
        sdist = rr - r_open
        h = fillet(np.maximum(sdist, 0.0), args.hole_raise_mm, args.hole_flat_mm,
                   args.hole_round_mm, args.rim_profile)
        h[sdist < -1e-9] = 0.0                        # 개구 안쪽 정점은 건드리지 않는다
        V[idx, 2] += h
        want = r_open + h                             # 45° 원뿔 위로 연장 → 그 안쪽은 밀어낸다
        sc = np.where((rr > 1e-6) & (rr < want), np.maximum(want, rr) / np.maximum(rr, 1e-6), 1.0)
        V[idx, :2] *= sc[:, None]
        n_hring = int((h > 1e-9).sum())
        print(f"  홀 융기 {args.hole_raise_mm}mm (flat {args.hole_flat_mm} / round {args.hole_round_mm}) "
              f"→ 정점 {n_hring:,}개, 개구 반경 {r_open:.2f} → {r_open + args.hole_raise_mm:.2f}mm")


    flange = trimesh.Trimesh(vertices=V, faces=f, process=False)
    z_top, top_area = dominant_top_plane(flange)
    print(f"홀 정점 {n_hole:,}개 이동 · 외곽 융기 {n_rim:,}개 · 홀 융기 {n_hring:,}개 | "
          f"주 상면 z={z_top:+.4f} (면적 {top_area:.0f}mm²) | watertight {flange.is_watertight}")
    if abs(z_top) > 1e-3:
        print(f"❌ 원점 규약 위반: 주 상면이 z={z_top:.4f} 로 이동했다")
        return 2

    out.mkdir(parents=True, exist_ok=True)
    flange.export(out / "top_flange.ply")
    body = trimesh.load(src / "body.ply", process=False)
    trimesh.util.concatenate([body, flange]).export(out / "full.ply")
    for n in ("body.ply", "wafers.ply", "sam3_prompts.json", "source.json"):
        if (src / n).exists():
            shutil.copy(src / n, out / n)
    (out / "keypoints.json").write_text(json.dumps(build_keypoints(flange, np.zeros(3)), indent=2))

    meta = json.loads((src / "meta.json").read_text())
    meta["obj_id"] = out.name
    meta["standard_features_semi_e47_1_1106"] = measure_standard_features(flange)
    meta["derived_from"] = {
        "source_obj": str(src), "tool": "spatial_vision.cad.build_semi_flange",
        "note": "top_flange 만 SEMI E47.1 / 실물 관측에 맞춰 수정. body·wafers 는 원본 그대로.",
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    stats = {
        "z49_plate_thickness_mm": float(-z_bot),
        "hole": {"target_d63_mm": args.hole_d63, "before_at_underside_mm": float(2 * r_now),
                 "after_at_underside_mm": float(2 * cone_radius_at(flange, z_bot)),
                 "top_opening_mm": float(2 * cone_radius_at(flange, 0.0)),
                 "vertices_moved": n_hole, "taper_mm": args.hole_taper_mm,
                 "cone_end_z_mm": float(z_cone_end),
                 "not_modeled": "상판 밑면 아래의 평탄 바닥(x69=7.6±0.1)과 2차 원뿔(γ=52±1°)"},
        "rim": {"mode": args.rim_mode, "profile": args.rim_profile, "raise_mm": args.rim_raise_mm, "flat_mm": args.rim_flat_mm,
                "round_mm": args.rim_round_mm, "vertices_raised": n_rim,
                "plate_mm": args.rim_plate_mm, "band_mm": args.rim_band_mm,
                "source": "실물 관측(사용자, 2026-08-10) — 규격 항목이 아니다"},
        "subdivide_mm": args.subdivide_mm,
        "dominant_top_plane": {"z_mm": float(z_top), "area_mm2": float(top_area)},
        "watertight": bool(flange.is_watertight),
        "warning": "자산이 바뀌었다 — build_usd → capture 부터 다시 돌린다 (횡단 정리 #40)",
    }
    (out / "meta_semi_fix.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"  홀: 밑면 ø{stats['hole']['before_at_underside_mm']:.2f} → "
          f"ø{stats['hole']['after_at_underside_mm']:.2f} (상면 개구 ø{stats['hole']['top_opening_mm']:.2f})")
    print(f"→ {out}   ⚠️ build_usd → capture 부터 다시 돌릴 것")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
