"""새 FOUP CAD 가 **SEMI E47.1 top robotic handling flange 규격**을 지키는지 검사한다.

    envs/cad/bin/python -m spatial_vision.cad.verify_semi --obj assets/obj/<id>

왜 필요한가
    새 CAD 를 받으면 **파이프라인을 태우기 전에** 규격 준수부터 확인해야 한다. 우리 첫 CAD 는
    중심 홀이 상판 밑면에서 **ø31**(규격 ø35±0.1)이었고 그걸 §24 에서야 발견했다 —
    그 전까지의 모든 실험이 "규격과 다른 물체" 위에서 돈 셈이다.
    ⚠️ 이 검사는 **`prepare_obj` 의 `standard_features_semi_e47_1_1106` 을 대체한다.**
    그 필드의 `rim_radius_mm`(외접 반경)은 **SEMI 치수가 아니다.**

무엇을 재나 (`docs/semi/` 의 Figure 12)
    도면 규약(§6.7): **굵은 선 = 공차가 있는 면**, ≤/≥ 만 있는 것은 봉투(제조사 자유).

    [공차]  x46/y46 = 71 ± 1        외곽 반폭
            d63      = ø35 ± 0.1     중심 홀 — **높이 z47 = flange 밑면에서** (E47.1-1101 p15 원문)
            x41/y41  = 30 ± 1        노치 위치
            x42/x43  = 50 ± 1        노치 위치
            θ        = 45 ± 0.5°     노치 각 (16×)
            β        = 45 ± 1°       중심 오목부 상부 원뿔각
    [봉투]  x47/y47 ≥ 58             챔퍼 시작(직선 변이 끝나는 곳)
            z49      ≤ 8             flange **밑면→윗면 전체 두께** (융기 포함). 봉투 항목
    [규칙]  orientation notch 는 **네 변이 서로 달라야** 한다 (§6.1)

⚠️ **`x45/y45 = 65.3 ± 1` 은 재지 않는다** — 도면상 "중심 → 코너 챔퍼 위 노치 모서리" 인데
   그 노치 모서리를 메쉬에서 일반적으로 특정하는 규칙을 확정하지 못했다. 확정되면 추가할 것.

측정 방법 (형상 가정을 최소화)
    · XY 윤곽은 **진짜 투영 윤곽**(오목 노치 포함)으로 잡는다 — 볼록껍질은 노치를 메운다(교훈 #46).
    · 두께·홀은 정점이 아니라 **점유(inside/outside) 격자**로 읽는다. 정점 샘플링은 성글어 속는다.
    · ⚠️ 두께는 **노치가 없는 방위**에서 재야 한다 — 모든 변의 0 위치에 노치가 있어
      `y=0` 으로 재면 "재료 없음" 이 나온다.

종료 코드: 공차 항목이 하나라도 벗어나면 **non-zero**. 봉투 항목 위반도 non-zero.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Point

from spatial_vision.cad.build_rim_obj import outline_polygon
from spatial_vision.cad.prepare_obj import dominant_top_plane

SPEC = {
    "x46_half_width_mm": (71.0, 1.0),
    "d63_hole_at_underside_mm": (35.0, 0.1),
    "x45_notch_nearest_mm": (65.3, 1.0),
    "notch_pos_30_mm": (30.0, 1.0),
    "notch_pos_50_mm": (50.0, 1.0),
    "theta_notch_deg": (45.0, 0.5),
    "beta_cone_deg": (45.0, 1.0),
}
ENVELOPE = {"x47_chamfer_start_mm": ("min", 58.0), "z49_plate_thickness_mm": ("max", 8.0)}


def flange_from_cad(path: Path, scale: float, up_axis: str, z_cut: float | None,
                    top_mm: float) -> trimesh.Trimesh:
    """원시 CAD 파일에서 **top flange 만** 떼어 원점을 주 상면 중심으로 옮긴다.

    새 CAD 를 받았을 때 `prepare_obj` 를 돌리기 **전에** 규격만 빠르게 보려는 경로다.
    ⚠️ 자동 추출은 만능이 아니다 — 항상 무엇을 잘랐는지 출력하니 **눈으로 확인**할 것.
    """
    m = trimesh.load(path, process=False)
    if isinstance(m, trimesh.Scene):
        m = trimesh.util.concatenate(list(m.geometry.values()))
    # ⚠️ STL 은 삼각형마다 정점을 복제해 둔다 — **용접하지 않고 자르면** 연결성분이 수천 개로
    #    부서지고(실측 2,236개) 엉뚱한 조각을 flange 로 고른다.
    m.merge_vertices()
    m.apply_scale(scale)
    if up_axis.lower() == "y":
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    elif up_axis.lower() == "x":
        m.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]))
    z_max = float(m.bounds[1][2])
    cut = z_cut if z_cut is not None else z_max - top_mm
    keep = (np.asarray(m.vertices)[:, 2] >= cut)
    faces = np.asarray(m.faces)[keep[np.asarray(m.faces)].all(axis=1)]
    top = trimesh.Trimesh(vertices=np.asarray(m.vertices), faces=faces, process=False)
    top.remove_unreferenced_vertices()
    comps = top.split(only_watertight=False)
    if len(comps) > 1:
        # flange 는 **축 근처의 컴팩트한** 성분이다. 면적 최대로 고르면 바깥 shell 을 집고,
        # 축 근접만 보면 1면짜리 파편을 집는다 — 둘 다 실측으로 겪었다.
        # → 의미 있는 크기(면적 ≥1,000mm²) 중 **최대 반경이 가장 작은** 성분.
        big = [c for c in comps if float(c.area) > 1000.0] or list(comps)
        rad = [float(np.hypot(*np.asarray(c.vertices)[:, :2].T).max()) for c in big]
        fl = big[int(np.argmin(rad))]
        print(f"  [자동 추출] 연결성분 {len(comps)}개 (면적≥1000: {len(big)}) → "
              f"최대반경 최소 {min(rad):.1f}mm 성분 선택")
    else:
        fl = comps[0] if len(comps) else top
    zt, area = dominant_top_plane(fl)
    on = np.abs(np.asarray(fl.vertices)[:, 2] - zt) < 0.05
    ctr = np.asarray(fl.vertices)[on][:, :2].mean(axis=0) if on.any() else fl.centroid[:2]
    fl.apply_translation([-ctr[0], -ctr[1], -zt])
    print(f"  [자동 추출] z ≥ {cut:.1f} 절단 → 성분 {len(comps)}개, 선택 성분 면 {len(fl.faces):,} | "
          f"주 상면 z={zt:.2f}(면적 {area:.0f}mm²) 중심 ({ctr[0]:.2f},{ctr[1]:.2f}) → 원점 이동")
    return fl


def occupancy_column(mesh, x, y, z0=20.0, z1=-40.0, dz=0.05):
    """(x,y) 수직선에서 재료 구간. 반환 (최상면 z, 그 아래 첫 빈틈 z) 또는 None."""
    zs = np.arange(z0, z1, -dz)
    P = np.stack([np.full(len(zs), x), np.full(len(zs), y), zs], 1)
    ins = np.concatenate([mesh.contains(P[i:i + 6000]) for i in range(0, len(P), 6000)])
    k = np.where(ins)[0]
    if not len(k):
        return None
    brk = np.where(np.diff(k) > 1)[0]
    return float(zs[k[0]]), float(zs[k[brk[0]]] if len(brk) else zs[k[-1]])


def hole_radius_at(mesh, z, r_max=40.0, dr=0.02):
    rs = np.arange(0.0, r_max, dr)
    P = np.stack([rs, np.zeros(len(rs)), np.full(len(rs), z)], 1)
    ins = np.concatenate([mesh.contains(P[i:i + 6000]) for i in range(0, len(P), 6000)])
    return float(rs[np.argmax(ins)]) if ins.any() else float("nan")


def hole_opening_topmost(mesh, z_plate_top: float, z_top_max: float, dz: float = 0.1):
    """**홀 둘레에 재료가 있는 가장 높은 z** 에서의 개구 지름과 그 z.

    ⚠️ `z_top_max` 에서 그냥 재면 안 된다 — 그건 메쉬 전체의 최고점이라 **최외곽 융기**일 수 있고,
    홀 융기가 없는 자산에서는 그 높이의 중심부에 재료가 없어 `nan` 이 나온다(실측: `spec15`).
    위에서부터 내려오며 처음 잡히는 곳이 «카메라가 보는 개구» 다.
    """
    z = z_top_max - 0.02          # 표면 «위» 의 점은 contains 판정이 모호하다 — 살짝 안쪽에서 잰다
    while z > z_plate_top:
        r = hole_radius_at(mesh, z)
        if np.isfinite(r) and r > 0:
            return float(2 * r), float(z)
        z -= dz
    # 홀 융기가 없으면 **주 상면이 곧 최상면**이다 (위 스캔은 최외곽 융기 구간을 훑고 지나간다)
    r = hole_radius_at(mesh, z_plate_top)
    return (float(2 * r), float(z_plate_top)) if np.isfinite(r) and r > 0 else (float("nan"),) * 2


def measure(mesh: trimesh.Trimesh) -> dict:
    poly = outline_polygon(mesh)
    ring = np.asarray(poly.exterior.coords)[:-1]
    x, y = ring[:, 0], ring[:, 1]
    half = max(np.abs(x).max(), np.abs(y).max())

    # ── 변별 노치: 직선 변에서 안쪽으로 들어간 점 ──────────────────────────────
    edges = {"+x": (0, +1, 1), "-x": (0, -1, 1), "+y": (1, +1, 0), "-y": (1, -1, 0)}
    notches, chamfer_start, depths = {}, [], []
    cs_per_edge = {}
    for lab, (ax, sgn, other) in edges.items():
        on_edge = np.abs(sgn * ring[:, ax] - half) < 0.3
        cs_per_edge[lab] = float(np.abs(ring[on_edge, other]).max()) if on_edge.any() else half - 8.0
        if on_edge.any():
            chamfer_start.append(cs_per_edge[lab])
    for lab, (ax, sgn, other) in edges.items():
        # ⚠️ 직선 변의 **끝(=챔퍼 시작)** 을 실측해서 자른다. 고정 여유(8mm)로 자르면 챔퍼 진입
        #    정점이 노치로 잡힌다 — 윤곽 정점이 촘촘한 메쉬에서만 나타나 재현이 어려웠다(2026-08-11).
        band = (sgn * ring[:, ax] > half - 8.0) & (np.abs(ring[:, other]) < cs_per_edge[lab] - 0.5)
        p = ring[band]
        inset = half - sgn * p[:, ax]
        # ⚠️ 세분화된 메쉬는 노치 하나에 정점이 여럿이라 그대로 뽑으면 0 옆에 ±0.6 같은 게 붙는다.
        #    6mm 이내는 같은 노치로 묶고 **중심**을 위치로 본다(규격상 노치 간격은 최소 20mm).
        raw = np.sort(p[inset > 0.3][:, other]) if (inset > 0.3).any() else np.array([])
        pos, cur = [], []
        for v in raw:
            if cur and v - cur[-1] > 6.0:
                pos.append(round(float(np.mean(cur)), 1)); cur = []
            cur.append(float(v))
        if cur:
            pos.append(round(float(np.mean(cur)), 1))
        notches[lab] = pos
        depths += [float(v) for v in inset[inset > 0.3]]

    # ── 노치 각 θ: V 를 이루는 두 변의 사잇각 (변 방향 기준) ────────────────────
    thetas = []
    for lab, (ax, sgn, other) in edges.items():
        band = (sgn * ring[:, ax] > half - 8.0) & (np.abs(ring[:, other]) < half - 8.0)
        p = ring[band]
        if len(p) < 3:
            continue
        p = p[np.argsort(p[:, other])]
        d = np.diff(p, axis=0)
        n = np.linalg.norm(d, axis=1)
        d = d[n > 0.2] / n[n > 0.2, None]
        for i in range(len(d) - 1):
            c = float(np.clip(d[i] @ d[i + 1], -1, 1))
            a = np.degrees(np.arccos(c))
            if 20.0 < a < 160.0:
                thetas.append(a)

    # ── 두께·홀: 노치를 피한 방위에서 점유 격자로 ─────────────────────────────
    # ⚠️ **규격 원문(E47.1-1101 p15)의 정의를 그대로 쓴다** (2026-08-11 정정):
    #    `z47` = 밑면(bottom of robotic handling flange) 위치 · `d63` = **그 높이 z47 에서의** 홀 지름
    #    `z49` = **밑면에서 윗면까지** (bottom → top of robotic handling flange), **8mm 이하 봉투**
    #    → ① z49 는 **융기를 포함한 최대 두께**여야 한다. 융기를 안 지나는 반경에서 재면
    #         봉투 검사가 무의미해진다(실물은 융기 포함 ≈7mm).
    #      ② d63 는 **밑면 기준**이다. `z_top − z49` 로 잡으면 융기가 있을 때 판 아래로 내려가 틀린다.
    probe_y = 20.0
    inner = occupancy_column(mesh, 0.55 * half, probe_y)
    outer = occupancy_column(mesh, 0.85 * half, probe_y)
    z_bot = inner[1] if inner else -5.0
    z_plate_top = inner[0] if inner else 0.0
    z_top_max = float(np.asarray(mesh.vertices)[:, 2].max())      # 융기 포함 최고점
    z49 = z_top_max - z_bot
    d63 = 2 * hole_radius_at(mesh, z_bot + 0.02)

    # ── β: 상부 원뿔각 — **주 판 구간에서만** 잰다(융기의 라운드 어깨를 피한다) ──
    z_top = z_plate_top
    zz = np.linspace(z_plate_top - 0.5, z_bot + 0.2, 8)
    rr = np.array([hole_radius_at(mesh, z) for z in zz])
    ok = np.isfinite(rr) & (rr > 0)
    beta = float(np.degrees(np.arctan(abs(np.polyfit(zz[ok], rr[ok], 1)[0])))) if ok.sum() > 2 else float("nan")
    _hole_top = hole_opening_topmost(mesh, z_plate_top, z_top_max)

    # ── x45 / 노치 경사면 시작 — 중심선(y=0) 노치를 변 프로파일에서 잰다 ─────────
    #    x45 = 변에서 가장 깊이 들어간 점까지의 거리(= half − depth). 규격 65.3±1.
    #    "경사면 시작" 은 노치가 직선 변에서 갈라지는 |y| 다 — `x69`(7.6±0.1) 후보인데
    #    **해석이 미확정**이라 INFO 로만 낸다 (규격 원문이 스캔 OCR 이라 도면 확인이 필요하다).
    x45 = notch_start = notch_depth0 = float("nan")
    side = ring[(ring[:, 0] > half - 12.0) & (np.abs(ring[:, 1]) < 12.0)]
    if len(side) > 4:
        ins = half - side[:, 0]
        notch_depth0 = float(ins.max())
        x45 = float(half - notch_depth0)
        on = np.abs(side[np.abs(ins) < 0.02][:, 1])
        notch_start = float(on.min()) if len(on) else float("nan")

    return {
        "x45_notch_nearest_mm": x45,
        "notch_angled_start_mm": notch_start,
        "notch_depth_center_mm": notch_depth0,
        "x46_half_width_mm": float(half),
        "x47_chamfer_start_mm": float(min(chamfer_start)) if chamfer_start else float("nan"),
        "z49_plate_thickness_mm": float(z49) if z49 else float("nan"),
        "z49_probe": {"inner_r": round(0.55 * half, 1), "outer_r": round(0.85 * half, 1),
                      "inner": inner, "outer": outer,
                      "z_bot": round(float(z_bot), 3), "z_plate_top": round(float(z_plate_top), 3),
                      "z_top_max_incl_ridge": round(float(z_top_max), 3),
                      "note": "z49 = z_top_max − z_bot (E47.1-1101 p15: bottom→top of flange, ≤8 봉투)"},
        "d63_hole_at_underside_mm": float(d63),
        # 🔴 홀은 45° 원뿔이라 **높이마다 지름이 다르다.** 셋을 구분해서 낸다:
        #   · d63          = 상판 **밑면**. SEMI 가 공차를 거는 유일한 값(ø35±0.1)
        #   · plate_top    = **주 상면**. 융기가 없으면 이게 곧 최상면이다
        #   · top_max      = **최상면(융기 꼭대기 포함)** ← **카메라가 보는 개구**이고
        #                    §28·§29·§36 의 «최상면 개구» 는 전부 이것이다. 규격이 안 잡는 값이다.
        #   ⚠️ 예전에 keypoint 가 «주 상면에서만» 홀을 찾아 융기 바깥 경계를 홀로 잡은 적이 있다
        #      (교훈 참조). 라벨과 측정 높이가 어긋나면 같은 사고가 난다.
        "hole_opening_at_plate_top_mm": float(2 * hole_radius_at(mesh, z_top)),
        "hole_opening_topmost_mm": _hole_top[0],
        "hole_opening_topmost_z": _hole_top[1],
        "beta_cone_deg": beta,
        "theta_notch_deg": float(np.median(thetas)) if thetas else float("nan"),
        "notch_depth_mm": float(np.median(depths)) if depths else float("nan"),
        "notches_per_edge": notches,
        "notches_differ_per_side": len({tuple(v) for v in notches.values()}) == len(notches),
        "outline_is_concave": bool(poly.area < poly.convex_hull.area - 1.0),
    }


def check(m: dict) -> tuple[list[dict], bool]:
    rows, ok_all = [], True
    for key, (nom, tol) in SPEC.items():
        if key.startswith("notch_pos"):
            continue
        v = m.get(key, float("nan"))
        meas = np.isfinite(v)
        ok = bool(meas and abs(v - nom) <= tol)
        rows.append({"item": key, "spec": f"{nom} ± {tol}",
                     "measured": round(float(v), 3) if meas else "측정불가",
                     "kind": "공차", "ok": ok, "measurable": bool(meas)})
        ok_all &= ok
    # 노치 위치 — 0 은 모든 변, 그 밖은 30/50 중 하나여야 한다
    bad = []
    for lab, pos in m["notches_per_edge"].items():
        for p in pos:
            if min(abs(abs(p) - t) for t in (0.0, 30.0, 50.0)) > 1.0:
                bad.append(f"{lab}:{p}")
    rows.append({"item": "notch_positions (0 / ±30±1 / ±50±1)", "spec": "0, 30±1, 50±1",
                 "measured": m["notches_per_edge"], "kind": "공차", "ok": not bad})
    ok_all &= not bad
    rows.append({"item": "orientation notch differs per side", "spec": "4면 모두 달라야",
                 "measured": m["notches_differ_per_side"], "kind": "규칙",
                 "ok": bool(m["notches_differ_per_side"])})
    ok_all &= bool(m["notches_differ_per_side"])
    for key, (mode, lim) in ENVELOPE.items():
        v = m.get(key, float("nan"))
        meas = np.isfinite(v)
        ok = bool(meas and (v >= lim if mode == "min" else v <= lim))
        rows.append({"item": key, "spec": f"{'≥' if mode=='min' else '≤'} {lim}",
                     "measured": round(float(v), 3) if meas else "측정불가",
                     "kind": "봉투", "ok": ok, "measurable": bool(meas)})
        ok_all &= ok
    return rows, ok_all


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SEMI E47.1 top flange 규격 검증")
    ap.add_argument("--obj", help="assets/obj/<id> (top_flange.ply 를 쓴다)")
    ap.add_argument("--mesh", help="flange 메쉬를 직접 지정 (--obj 대신)")
    ap.add_argument("--cad", help="원시 CAD 파일(STL/STEP/…)에서 flange 를 자동 추출해 검사한다")
    ap.add_argument("--scale", type=float, default=1.0, help="[--cad] mm 로 만드는 배율 (cm 이면 10)")
    ap.add_argument("--up-axis", default="z", choices=["x", "y", "z"], help="[--cad] 소스의 up 축")
    ap.add_argument("--z-cut-mm", type=float, default=None, help="[--cad] flange 를 떼는 절단 높이(스케일 후)")
    ap.add_argument("--top-mm", type=float, default=40.0,
                    help="[--cad] --z-cut-mm 이 없으면 최상단에서 이만큼 아래를 절단면으로 쓴다")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    if args.cad:
        path = Path(args.cad)
        print(f"=== SEMI E47.1 검증 | {path}  (원시 CAD, scale×{args.scale}, up={args.up_axis})")
        mesh = flange_from_cad(path, args.scale, args.up_axis, args.z_cut_mm, args.top_mm)
    else:
        path = Path(args.mesh) if args.mesh else Path(args.obj) / "top_flange.ply"
        mesh = trimesh.load(path, process=False)
        print(f"=== SEMI E47.1 검증 | {path}  ({len(mesh.faces):,} faces)")
    if not mesh.is_watertight:
        print("  ⚠️ watertight 가 아니다 — 점유 격자(내부 판정)가 부정확할 수 있다")

    m = measure(mesh)
    rows, ok_all = check(m)
    w = max(len(r["item"]) for r in rows)
    for r in rows:
        # ⚠️ **"위반" 과 "측정 불가" 는 다르다.** watertight 가 아닌 메쉬는 점유 판정이 안 돼
        #    두께·홀을 못 잰다 — 그걸 위반으로 읽으면 원인을 엉뚱한 데서 찾는다.
        mark = "✅" if r["ok"] else ("⚠️" if r.get("measurable") is False else "❌")
        print(f"  {mark} [{r['kind']:2}] {r['item']:<{w}}  규격 {r['spec']:<12} 실측 {r['measured']}")
    ridge = m["hole_opening_topmost_mm"] - m["hole_opening_at_plate_top_mm"]
    print(f"  ─ 참고: 홀 개구 — 주 상면 ø{m['hole_opening_at_plate_top_mm']:.2f}"
          f" · ★최상면 ø{m['hole_opening_topmost_mm']:.2f} (z={m['hole_opening_topmost_z']:+.2f})"
          + (f"  ← 홀 융기 +{ridge:.2f}" if ridge > 0.1 else "  ← 홀 융기 없음"))
    print("    ★최상면 개구가 **카메라가 보는 값**이고 규격이 안 잡는다 — 실물 캘리퍼와 비교할 대상이다.")
    print("      개체마다 다를 수 있어 파이프라인 선택 근거로 쓰지 않는다(§36) — 배포는 `--outer-only`.")
    print(f"  ─ 참고: 노치 깊이 {m['notch_depth_mm']:.2f}mm · 윤곽 오목(노치 존재) {m['outline_is_concave']}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps({"mesh": str(path), "measured": m,
                                                   "checks": rows, "pass": bool(ok_all)},
                                                  indent=2, ensure_ascii=False))
        print(f"  → {args.json_out}")
    n_bad = sum(1 for r in rows if not r["ok"] and r.get("measurable") is not False)
    n_unk = sum(1 for r in rows if r.get("measurable") is False)
    if ok_all:
        print("✅ SEMI 규격 통과")
    else:
        print(f"❌ SEMI 규격 위반 {n_bad}건" + (f" · ⚠️ 측정불가 {n_unk}건 (watertight 확인)" if n_unk else ""))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
