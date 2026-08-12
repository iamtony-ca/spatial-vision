"""flange 의 **테두리 밴드만** 남긴 obj 를 만든다 (PIPELINE_CATALOG §2.2 S⑤).

    envs/cad/bin/python -m spatial_vision.cad.build_rim_obj \
        --obj assets/obj/foup_300_semi --band-mm 20 --out assets/obj/foup_300_semi_rim20

왜 필요한가
    SEMI 가 규정하는 것은 flange 의 **테두리와 중심 홀뿐**이고 **중간부는 제조사마다 다르다**
    (RESULTS.md §20-1: 두 번째 CAD 와 flange 중앙 4.87mm 차이). 그런데 flange 의 **방향 정보는
    전부 테두리**에 있다(중심 홀은 완전한 원이라 yaw 정보 0 — § flange 의 회전 구속).
    → 중간부를 빼면 *표준부 순수성*과 *방향 신호*를 동시에 지킬 수 있다는 가설. 이 스크립트가
      그 가설의 **모델 쪽**을 만든다(마스크 쪽은 `pose_fp --mask-band-mm`).

밴드의 정의 — 왜 반경이 아니라 **외곽선까지의 거리**인가
    이 flange 외곽은 원이 아니라 **모서리 라운드된 정사각형**(변 142mm, 모서리 r=91.7mm)이다.
    반경으로 자르면 모서리만 남고 변 중앙은 통째로 날아간다. 그래서 **XY 외곽선을 안쪽으로
    `--band-mm` 만큼 offset** 해 만든 띠를 쓴다. 이것은 영상에서 실루엣을 **원판으로 침식**한 것과
    같은 도형이라 `pose_fp --mask-band-mm` 의 마스크와 정확히 대응한다.

    z 는 자르지 않는다 — 밴드 안이면 상면·외측벽·아랫면을 모두 남긴다(외측벽이 곧 테두리다).

`--hub-r-mm`
    중심 홀 주변도 표준부이므로 반경 R 안쪽 원판을 함께 남기는 변형. 홀은 yaw 정보를 주지 않지만
    x/y/z 병진은 강하게 구속한다. 기본 0(끄기) — 밴드 단독과 나눠서 재기 위함.

출력은 `--obj` 와 **같은 원점 규약**의 obj 디렉토리다. `full.ply`·`keypoints.json` 은 바이트 복사하고
`top_flange.ply` 만 밴드로 바꾼다 → 기존 스테이지가 `--primary flange` 그대로 읽는다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import MultiPoint, Point


def outline_polygon(mesh: trimesh.Trimesh, mode: str = "true"):
    """XY 외곽선 — **실제 윤곽 그대로**(오목 포함).

    ⚠️ 처음에는 볼록껍질을 썼는데 **틀렸다.** 이 flange 테두리에는 변 중앙·모서리마다 **오목한 노치**가
    파여 있고, 볼록껍질은 그 위에 다리를 놓아 노치를 통째로 메운다(면적 차 200mm²). 그러면
    ① 밴드가 노치 벽을 따라가지 못하고 ② 노치 안쪽이 통째로 "테두리" 로 잡힌다.
    **노치야말로 방향 신호가 가장 센 곳**이라 이 오차는 그냥 면적 문제가 아니다.
    → 삼각형 투영의 합집합(`trimesh.path.polygons.projected`)으로 진짜 윤곽을 쓴다.
    """
    from trimesh.path import polygons as _tp

    if mode == "hull":       # 대조군 — 노치를 다리 놓아 메운다. 정말 나쁜지 A/B 하려고 남긴다
        return MultiPoint(np.asarray(mesh.vertices)[:, :2]).convex_hull
    # ⚠️ 여기서 **볼록껍질로 물러나면 안 된다** (2026-08-11). `projected()` 가 터졌을 때 조용히
    #    껍질을 돌려주면 노치가 메워진 채로 하류에 흘러간다 — `verify_semi` 가 그 때문에
    #    *"노치가 4면 모두 같다"* 는 거짓 위반을 냈다. 정본 구현(`prepare_obj.outline_xy`)이
    #    삼각형 합집합으로 진짜 윤곽을 복구한다.
    from spatial_vision.cad.prepare_obj import outline_xy
    return outline_xy(mesh)


def band_solid(poly, band_mm: float, z_lo: float, z_hi: float, hub_r: float):
    """외곽선을 안쪽으로 band_mm offset 해 만든 띠(+선택적 중심 원판)를 z 로 밀어 낸 솔리드.

    `buffer(-band_mm)` 는 오목부에서도 올바르게 안쪽으로 물러나므로 **노치를 그대로 따라간다**
    (영상 쪽 `pose_fp.to_band` 의 원판 침식과 같은 도형 — 그래서 둘이 대응한다).
    `join_style=2`(mitre)로 두어 노치 모서리가 둥글게 뭉개지지 않게 한다.
    """
    inner = poly.buffer(-band_mm, join_style=2, mitre_limit=8.0)
    ring = poly.difference(inner) if not inner.is_empty else poly
    if hub_r > 0:
        ring = ring.union(Point(0, 0).buffer(hub_r, quad_segs=64))
    pad = 1.0                                    # 상·하로 1mm 여유 → 경계면이 정확히 겹치는 것을 피한다
    # hub 를 붙이면 밴드와 원판이 떨어져 있어 MultiPolygon 이 된다 → 조각마다 밀어 내고 합친다.
    parts = list(getattr(ring, "geoms", [ring]))
    solid = trimesh.util.concatenate(
        [trimesh.creation.extrude_polygon(p, height=(z_hi - z_lo) + 2 * pad) for p in parts])
    solid.apply_translation([0, 0, z_lo - pad])
    return ring, solid


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="flange 테두리 밴드만 남긴 obj 생성")
    ap.add_argument("--obj", required=True, help="원본 assets/obj/<obj_id>")
    ap.add_argument("--band-mm", type=float, required=True, help="외곽선에서 안쪽으로의 밴드 폭")
    ap.add_argument("--hub-r-mm", type=float, default=0.0, help="중심 홀 주변을 남길 반경 (0=끄기)")
    ap.add_argument("--hole-band-mm", type=float, default=0.0,
                    help="중심 홀 **경계에서 바깥으로** 남길 띠 폭. 규격은 최외곽 테두리와 **중심 원**이므로 "
                         "둘 다 남기는 구성을 만든다. meta 의 center_hole_radius 를 읽어 "
                         "`--hub-r-mm (r_hole + W)` 로 환산한다")
    ap.add_argument("--subdivide-mm", type=float, default=6.0,
                    help="자른 뒤 세분화 최대 변 길이. 밴드는 평면이라 정점이 100여개로 줄어드는데 "
                         "FoundationPose 의 `guess_translation`·스코어러가 model_pts(정점)를 쓰므로 "
                         "원본 flange 와 밀도를 맞춘다. 형상은 바뀌지 않는다. 0=끄기")
    ap.add_argument("--outline", default="true", choices=["true", "hull"],
                    help="true=실제 윤곽(노치 포함, 기본) / hull=볼록껍질 대조군(노치를 메운다)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    obj = Path(args.obj)
    fl = trimesh.load(obj / "top_flange.ply", process=False)
    poly = outline_polygon(fl, args.outline)
    z_lo, z_hi = float(fl.bounds[0][2]), float(fl.bounds[1][2])
    hub_r = args.hub_r_mm
    if args.hole_band_mm > 0:
        sf = json.loads((obj / "meta.json").read_text()).get(
            "standard_features_semi_e47_1_1106", {})
        r_hole = float(sf.get("center_hole_radius_mm", 20.5))
        hub_r = r_hole + args.hole_band_mm
        print(f"중심 홀 띠 {args.hole_band_mm}mm → 반경 {hub_r:.2f}mm 까지 남긴다 (r_hole {r_hole:.2f})")
    ring, solid = band_solid(poly, args.band_mm, z_lo, z_hi, hub_r)

    rim = trimesh.boolean.intersection([fl, solid])
    if isinstance(rim, list):
        rim = trimesh.util.concatenate(rim)
    if rim.is_empty or len(rim.faces) == 0:
        print("❌ 교집합이 비었다 — band-mm 가 너무 작거나 외곽선 계산이 틀렸다")
        return 2

    n_raw = len(rim.faces)
    if args.subdivide_mm > 0:
        v, f_ = trimesh.remesh.subdivide_to_size(
            np.asarray(rim.vertices), np.asarray(rim.faces), max_edge=args.subdivide_mm)
        rim = trimesh.Trimesh(vertices=v, faces=f_, process=False)

    # ⚠️ 원점이 움직이면 GT·2-stage 규약이 깨진다. **z 상한(=주 상면, z=0)과 XY 외곽**이 기준이다.
    #    z 하한은 밴드가 좁으면 당연히 올라간다(테두리 쪽 판이 얇다) — 그건 원점 이동이 아니다.
    d_top = float(abs(rim.bounds[1][2] - fl.bounds[1][2]))
    d_xy = float(np.abs(np.asarray(rim.bounds)[:, :2] - np.asarray(fl.bounds)[:, :2]).max())
    if max(d_top, d_xy) > 1e-3:
        print(f"❌ 원점 규약 위반: 상면 z 차 {d_top:.4f}mm · XY 외곽 차 {d_xy:.4f}mm")
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rim.export(out / "top_flange.ply")
    for name in ("full.ply", "body.ply", "keypoints.json", "meta.json",
                 "sam3_prompts.json", "wafers.ply"):
        p = obj / name
        if p.exists():
            (out / name).write_bytes(p.read_bytes())

    stats = {
        "source_obj": str(obj), "band_mm": args.band_mm, "outline": args.outline, "hub_r_mm": hub_r,
        "hole_band_mm": args.hole_band_mm,
        "outline_area_mm2": float(poly.area), "band_area_mm2": float(ring.area),
        "band_area_frac": float(ring.area / poly.area),
        "faces": int(len(rim.faces)), "faces_before_subdivide": int(n_raw),
        "vertices": int(len(rim.vertices)), "subdivide_mm": args.subdivide_mm,
        "watertight": bool(rim.is_watertight),
        "surface_area_mm2": float(rim.area), "flange_surface_area_mm2": float(fl.area),
        "surface_area_frac": float(rim.area / fl.area),
        "volume_cm3": round(float(rim.volume) / 1000, 3),
        "bbox_mm": [rim.bounds[0].round(4).tolist(), rim.bounds[1].round(4).tolist()],
        "z_range_mm": [float(rim.bounds[0][2]), float(rim.bounds[1][2])],
        "flange_z_range_mm": [float(fl.bounds[0][2]), float(fl.bounds[1][2])],
        "note": "top_flange.ply 를 테두리 밴드로 교체한 obj. full.ply 는 원본 그대로 — "
                "pose_fp --primary flange --mask-band-mm <band> 로 쓴다.",
    }
    (out / "meta_rim.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"밴드 {args.band_mm}mm (hub {hub_r}) → faces {n_raw:,}→{len(rim.faces):,} "
          f"| XY 면적 {stats['band_area_frac']*100:.1f}% | 표면적 {stats['surface_area_frac']*100:.1f}% "
          f"| z {rim.bounds[0][2]:.1f}~{rim.bounds[1][2]:.1f} (flange {fl.bounds[0][2]:.1f}~{fl.bounds[1][2]:.1f}) "
          f"| watertight {rim.is_watertight}")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
