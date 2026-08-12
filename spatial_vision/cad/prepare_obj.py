"""M1 — CAD 준비: 소비자용 메쉬 2종 + keypoints + meta 생성.

    envs/cad/bin/python -m spatial_vision.cad.prepare_obj --config assets/obj/foup_300/source.json

무엇을 만드나 (PIPELINE_PLAN.md M1)
    full.ply         전체 형상 (stage-1 coarse pose 용)
    top_flange.ply   top flange 만  (stage-2 정밀 refine 용)
    keypoints.json   표준부(rim/center hole/top plane) 앵커점
    meta.json        단위·원점·bbox·표준부 실측치·생성 출처

핵심 원칙
    1. **두 메쉬는 반드시 같은 좌표계**를 쓴다 — 2-stage 가 성립하는 조건.
    2. 원점은 **flange 주 상면 중심**. FoundationPose 의 depth-median Z 초기화가 관측 표면
       근처의 원점에서 잘 동작하기 때문이다 (CONSUMER_6DPOSE.md §2.6-1).
    3. **표준부에만 앵커한다** — SEMI E47.1-1106 이 규정하는 건 외곽 테두리·중심 홀·높이뿐이고,
       body 는 제조사마다 다르다 (§2.7.4). body 는 coarse pose 전용.
    4. 단위 스케일은 **표준 치수로 자체 검증**한다. rim ø190 / hole ø40 이 나오지 않으면 실패시킨다
       — 오픈 CAD 는 cm/inch 로 받는 경우가 흔한데, 단위가 틀리면 이후 전부가 조용히 틀어진다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import trimesh


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def load_scaled(src: Path, scale: float) -> trimesh.Trimesh:
    """소스 메쉬를 읽어 mm 로 스케일한다."""
    m = trimesh.load(str(src), process=True, force="mesh")
    if not isinstance(m, trimesh.Trimesh):
        raise TypeError(f"단일 메쉬가 아니다: {type(m)}")
    if scale != 1.0:
        m.apply_scale(scale)
    return m


def to_z_up(mesh: trimesh.Trimesh, up_axis: str) -> trimesh.Trimesh:
    """소스의 up axis 를 파이프라인 규약인 **+Z** 로 돌린다.

    분리·원점·keypoints 로직은 전부 Z-up 을 전제한다. **가장 먼저** 한 번 돌려 놓으면
    이후 코드가 소스별 분기 없이 그대로 동작한다(규약을 한 곳에서만 처리한다).
    """
    if up_axis.lower() in ("z", "+z"):
        return mesh
    m = mesh.copy()
    if up_axis.lower() in ("y", "+y"):      # +Y → +Z : X축 기준 +90°
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    elif up_axis.lower() in ("x", "+x"):    # +X → +Z : Y축 기준 -90°
        m.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]))
    else:
        raise ValueError(f"지원하지 않는 up-axis: {up_axis}")
    return m


def load_multibody(src: Path, scale: float) -> trimesh.Trimesh:
    """STEP/멀티바디 소스를 읽어 mm 로 스케일한 **단일 메쉬**로 합친다(정점 병합 포함).

    ⚠️ STEP 은 trimesh 단독으로 못 읽는다 — `cascadio`(OCCT)가 있어야 한다.
    ⚠️ cascadio 는 **면 단위로 정점을 분리해서** 내놓는다(연결성분 = ADVANCED_FACE 수).
       `merge_vertices()` 를 하지 않으면 solid 단위 분리가 불가능하고 watertight 도 전부 False 가 된다.
    ⚠️ cascadio 는 STEP 의 단위를 **미터로 정규화**해 준다 → 컨텍스트가 cm 든 mm 든 scale=1000 이다.
    """
    scene = trimesh.load(str(src))
    if isinstance(scene, trimesh.Scene):
        mesh = trimesh.util.concatenate(list(scene.geometry.values()))
    else:
        mesh = scene
    if scale != 1.0:
        mesh.apply_scale(scale)
    mesh.merge_vertices()
    return mesh


def split_bodies(mesh: trimesh.Trimesh, min_faces: int = 8) -> list[trimesh.Trimesh]:
    """연결성분 = solid. 테셀레이션 부스러기(면 몇 개짜리 축퇴 성분)는 버린다."""
    return [c for c in mesh.split(only_watertight=False) if len(c.faces) >= min_faces]


def classify_bodies(
    bodies: list[trimesh.Trimesh], wafer_diameter_mm: float = 300.0, tol_mm: float = 2.0
) -> dict:
    """solid 들을 wafer / flange / 나머지(body+door)로 가른다.

    - **wafer**: 얇은 원판(두께 ≤2mm) 이고 지름이 기대치와 일치. 개수·지름이 곧 **단위 체크섬**이다
      (300mm FOUP 이면 ø300 × 25). rim 치수보다 훨씬 강한 검증자다 — 제조사 불변이고 개수까지 맞아야 한다.
    - **flange**: wafer 가 아닌 것 중 **최상단(z 최대)** 이면서 중심축 위에 있는 solid.
    """
    wafers, rest = [], []
    for b in bodies:
        e = b.bounds[1] - b.bounds[0]
        r = np.linalg.norm(b.vertices[:, :2] - b.centroid[:2], axis=1).max()
        is_wafer = e[2] <= 2.0 and abs(2 * r - wafer_diameter_mm) <= tol_mm
        (wafers if is_wafer else rest).append(b)
    if not rest:
        raise RuntimeError("wafer 가 아닌 solid 가 없다")

    # 최상단 solid = flange 후보. 중심축에서 벗어나 있으면(예: 도어) flange 가 아니다.
    cand = sorted(rest, key=lambda b: -b.bounds[1][2])
    flange = None
    for b in cand:
        axis_off = float(np.linalg.norm(b.centroid[:2]))
        if axis_off < 10.0:
            flange = b
            break
    if flange is None:
        raise RuntimeError("중심축 위의 최상단 solid(=flange)를 찾지 못했다")
    others = [b for b in rest if b is not flange]
    return {"wafers": wafers, "flange": flange, "others": others}


def split_part_by_plane(
    mesh: trimesh.Trimesh, z_cut: float, keep_axis_component: bool = True
) -> tuple[trimesh.Trimesh, int]:
    """z_cut 위를 잘라내고 **중심축을 포함하는 연결성분**을 고른다.

    FOUP 은 z=z_cut 평면 하나로 flange 와 shell 이 완전히 분리된다(반경 간극 ~44mm).
    원통 컷이 필요 없고, 잘린 두 성분 모두 watertight 로 나온다.
    """
    sliced = mesh.slice_plane(plane_origin=[0, 0, z_cut], plane_normal=[0, 0, 1], cap=True)
    comps = sliced.split(only_watertight=False)
    if not len(comps):
        raise RuntimeError(f"z={z_cut} 위에 남는 형상이 없다")
    if not keep_axis_component:
        return max(comps, key=lambda c: len(c.faces)), len(comps)
    # 중심축(x=y=0)에 가장 가까운 성분 = flange
    key = lambda c: np.linalg.norm(c.vertices[:, :2], axis=1).min()  # noqa: E731
    return min(comps, key=key), len(comps)


def body_complement(mesh: trimesh.Trimesh, z_cut: float) -> trimesh.Trimesh:
    """full − flange = 컷 평면 아래 전체 + 위쪽의 flange 아닌 성분.

    왜 필요한가: Isaac 의 semantic segmentation 은 **prim 단위**로 라벨을 붙인다. flange mask 를
    따로 얻으려면 USD 에 body 와 flange 가 **겹치지 않는 별개 mesh prim** 으로 들어가야 한다
    (겹치면 z-fighting). full.ply 는 FoundationPose stage-1 용이라 그대로 두고, 렌더용 짝을 따로 만든다.
    """
    lower = mesh.slice_plane(plane_origin=[0, 0, z_cut], plane_normal=[0, 0, -1], cap=True)
    upper = mesh.slice_plane(plane_origin=[0, 0, z_cut], plane_normal=[0, 0, 1], cap=True)
    comps = upper.split(only_watertight=False)
    key = lambda c: np.linalg.norm(c.vertices[:, :2], axis=1).min()  # noqa: E731
    flange = min(comps, key=key)
    others = [c for c in comps if c is not flange]
    return trimesh.util.concatenate([lower, *others])


def dominant_top_plane(mesh: trimesh.Trimesh, tol: float = 0.05) -> tuple[float, float]:
    """위를 향하는 면 중 **면적이 가장 큰 수평 평면**의 z 와 그 면적.

    bbox 최댓값을 쓰면 안 된다 — FOUP 은 최상단이 작은 중앙 돌기(r 25~33mm)라
    실제 관측 표면(주 상면)보다 2mm 높다. 원점이 2mm 틀어지면 depth-median Z 초기화가 그만큼 편향된다.
    """
    n = mesh.face_normals
    up = n[:, 2] > 0.99  # 위를 향하는 수평면
    if not up.any():
        raise RuntimeError("위를 향하는 수평면이 없다")
    zc = mesh.triangles_center[up][:, 2]
    area = mesh.area_faces[up]
    levels = {}
    for z, a in zip(zc, area):
        key = round(float(z) / tol) * tol
        levels[key] = levels.get(key, 0.0) + float(a)
    z_best = max(levels, key=levels.get)
    return z_best, levels[z_best]


def measure_standard_features(flange: trimesh.Trimesh) -> dict:
    """SEMI E47.1-1106 표준부 실측 — rim(외곽 테두리) / center hole / height."""
    V = flange.vertices
    r = np.linalg.norm(V[:, :2], axis=1)
    z_top, top_area = dominant_top_plane(flange)

    rim_r = float(r.max())
    # 중심 홀은 **주 상면 위에서** 재야 한다. 메쉬 전체의 최소 반경을 쓰면 보이지 않는 내부 형상을
    # 집는다 — 신 CAD 의 flange 는 홀이 원뿔 보어라 상면 개구부는 ø41 인데 목은 ø15 다.
    # keypoint 는 "관측되는 것" 에만 걸어야 하므로 상면 기준이 맞다(원점을 bbox 가 아니라
    # 주 상면으로 잡은 것과 같은 이유).
    # ⚠️ 주 상면**만** 보면 홀 주변 융기가 있을 때 융기 바깥 경계를 홀로 잡는다 → `z ≥ z_top` 전체에서.
    above = (V[:, 2] >= z_top - 0.05) & (r > 0.5)
    r_top = r[above]
    hole_r = float(r_top.min()) if len(r_top) else float("nan")

    zs = V[:, 2]
    # 외곽이 원이 아닐 수 있다(신 CAD 의 flange 는 모서리 라운드된 정사각형) → 외곽을 두 가지로 기술한다.
    # rim_* 는 "외접 반경" 이므로 정사각형이면 모서리 값이 잡힌다. 변 길이를 따로 낸다.
    side_x = float(V[:, 0].max() - V[:, 0].min())
    side_y = float(V[:, 1].max() - V[:, 1].min())
    outline_circular = abs(side_x - side_y) < 0.5 and abs(rim_r * 2 - side_x) < 0.5
    return {
        "rim_radius_mm": rim_r,
        "rim_diameter_mm": rim_r * 2,
        "outline_is_circular": bool(outline_circular),
        "outline_side_x_mm": side_x,
        "outline_side_y_mm": side_y,
        "center_hole_radius_mm": hole_r,
        "center_hole_diameter_mm": hole_r * 2,
        "top_plane_z_mm": float(z_top),
        "top_plane_area_mm2": float(top_area),
        "bbox_top_z_mm": float(zs.max()),
        "bottom_z_mm": float(zs.min()),
        "height_mm": float(zs.max() - zs.min()),
    }


def _outline_is_circular(V: np.ndarray, rim_r: float, tol: float = 0.5) -> bool:
    """외곽이 원인가 — 외접반경과 변 길이 절반이 같으면 원(정사각형이면 √2 배 차이가 난다)."""
    side_x = float(V[:, 0].max() - V[:, 0].min())
    side_y = float(V[:, 1].max() - V[:, 1].min())
    return abs(side_x - side_y) < tol and abs(rim_r * 2 - side_x) < tol


def outline_xy(mesh_local: trimesh.Trimesh):
    """메쉬의 **XY 투영 윤곽**(오목 포함) 폴리곤. 이 파일이 정본이고 다른 모듈은 이걸 부른다.

    `trimesh.path.polygons.projected` 를 먼저 쓰고, 그게 터지면 **삼각형을 직접 합집합**한다.
    ⚠️ 실패했다고 **볼록껍질로 물러나면 안 된다** — 노치를 다리 놓아 메워 keypoint 가 허공에
    뜬다(횡단 정리 #46·#47). 그래서 대체 경로도 진짜 윤곽을 낸다: 좌표를 `grid_size` 로 스냅해
    GEOS 의 side-location conflict(세분화·변위된 메쉬에서 자주 난다)를 피한다.
    """
    from trimesh.path import polygons as _tp
    import shapely

    poly = None
    try:
        poly = _tp.projected(mesh_local, normal=[0, 0, 1])
    except Exception as e:                       # noqa: BLE001 — GEOS 예외 종류가 버전마다 다르다
        print(f"⚠️ projected() 실패({type(e).__name__}) — 삼각형 합집합으로 다시 시도한다")
    if poly is None:
        tri = np.asarray(mesh_local.vertices)[:, :2][np.asarray(mesh_local.faces)]
        u, v = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        area2 = np.abs(u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0])   # numpy 2 는 2D cross 를 없앴다
        tri = tri[area2 > 1e-9]
        rings = np.concatenate([tri, tri[:, :1]], axis=1)          # 닫힌 링
        poly = shapely.union_all(shapely.polygons(rings), grid_size=1e-4)
    if poly is None or poly.is_empty:
        raise RuntimeError("XY 윤곽을 투영하지 못했다")
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly


def _sample_outline(mesh_local: trimesh.Trimesh, z_plane: float, n: int) -> np.ndarray:
    """**실제 XY 윤곽선**(오목 포함)을 등호길이로 n 개 샘플한다.

    ⚠️ **볼록껍질을 쓰면 안 된다** (2026-08-10 정정, 횡단 정리 #46·#47). `foup_300_semi` 테두리에는
    변 중앙·모서리마다 **오목한 노치**가 있어 껍질이 그 위에 다리를 놓는다(면적 차 200mm²).
    옛 구현의 n=16 샘플은 **우연히** 노치를 다 비껴가 표면거리 0.000mm 였지만, `--n-rim-keypoints`
    를 바꾸거나 노치가 많은 CAD 가 오면 keypoint 가 **허공에 뜬다** — 그리고 M2 의 2D 투영 검사는
    실루엣 안이기만 하면 통과시키므로 그 오류를 못 잡는다(#11 과 같은 함정).

    윤곽은 삼각형 투영의 합집합(`trimesh.path.polygons.projected`)으로 얻는다. 이 flange 는
    주 상면이 가장 넓어 Z 투영 실루엣이 곧 상면 외곽이다 — 아니면 `verify_obj` 의 3D 표면거리에서 걸린다.
    """
    poly = outline_xy(mesh_local)
    ring = np.asarray(poly.exterior.coords)[:-1]           # 닫힘점 제거
    if len(ring) < 3:
        raise RuntimeError("윤곽 정점이 부족하다")
    seg = np.linalg.norm(np.diff(np.vstack([ring, ring[:1]]), axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])          # 누적 호길이
    want = np.linspace(0, cum[-1], n, endpoint=False)
    pts = []
    for w in want:
        k = int(np.searchsorted(cum, w, side="right") - 1)
        k = min(k, len(seg) - 1)
        t = (w - cum[k]) / seg[k]
        a, b = ring[k], ring[(k + 1) % len(ring)]
        pts.append(a + t * (b - a))
    return np.column_stack([np.array(pts), np.full(n, z_plane)])


def build_keypoints(flange: trimesh.Trimesh, origin: np.ndarray, n_rim: int = 16) -> dict:
    """표준부에만 앵커한 keypoints (obj-local, 원점 이동 **후** 좌표).

    body 는 제조사마다 다르므로 keypoint 를 걸지 않는다.
    """
    V = flange.vertices - origin
    r = np.linalg.norm(V[:, :2], axis=1)
    rim_r = float(r.max())
    # 홀은 **주 상면 이상(z ≥ 0)의 모든 정점**에서 최소 반경으로 잡는다.
    # ⚠️ `|z| < 0.05` 로 주 상면**만** 보면 **홀 주변 융기가 있는 자산에서 틀린다** —
    #    융기가 홀 둘레를 z=+2 로 들어올려 주 상면이 홀에 닿지 않고, 융기 **바깥** 경계(ø53)를
    #    홀로 잡는다(실측 개구는 ø49). 실물 FOUP 은 제조사에 따라 이 융기가 있다(사용자 확정).
    #    → keypoint 는 "관측되는 개구" 에 걸려야 하므로 융기 꼭대기의 개구가 맞다.
    above = (V[:, 2] >= -0.05) & (r > 0.5)
    r_ab = r[above]
    hole_r = float(r_ab.min())
    hole_z = float(V[above][int(np.argmin(r_ab)), 2])

    # rim 최상단 z (외곽 테두리가 실제로 관측되는 높이)
    rim_z = float(V[r > rim_r - 0.5][:, 2].max())

    ang = np.linspace(0, 2 * np.pi, n_rim, endpoint=False)
    hole_pts = np.stack([hole_r * np.cos(ang), hole_r * np.sin(ang), np.full(n_rim, hole_z)], 1)

    # ⚠️ 외곽이 원이라고 가정하면 안 된다. 신 CAD 의 flange 는 **모서리 라운드된 정사각형**이라
    # 외접반경(91.68mm) 원주에 뿌리면 16개 중 12개가 형상 밖 최대 21.3mm 허공에 뜬다(실측).
    # keypoint 는 pose refine 의 앵커이므로 형상 위에 있어야 한다 → **실제 외곽선**을 따라 뿌린다.
    # (M2 의 투영 검사는 2D 실루엣 안에만 들어가면 통과하므로 이 오류를 잡아주지 못한다.)
    outline_circular = _outline_is_circular(V, rim_r)
    if outline_circular:
        rim_pts = np.stack([rim_r * np.cos(ang), rim_r * np.sin(ang), np.full(n_rim, rim_z)], 1)
        outline_type = "circle"
    else:
        local = trimesh.Trimesh(vertices=V, faces=np.asarray(flange.faces), process=False)
        rim_pts = _sample_outline(local, z_plane=0.0, n=n_rim)
        outline_type = "polyline(true XY outline, concave notches kept)"

    return {
        "frame": "object-local, origin = flange top plane center",
        "units": "mm",
        "note": "SEMI E47.1-1106 표준부(외곽 테두리·중심 홀·높이)에만 앵커. body 는 제조사별 상이하여 제외.",
        "points": {
            "flange_top_center": [0.0, 0.0, 0.0],
            "flange_axis": {"point": [0.0, 0.0, 0.0], "direction": [0.0, 0.0, 1.0]},
            "rim_circle": {"radius_mm": rim_r, "z_mm": rim_z, "outline": outline_type,
                           "samples": rim_pts.round(4).tolist()},
            "center_hole_circle": {
                "radius_mm": hole_r,
                "z_mm": hole_z,
                "samples": hole_pts.round(4).tolist(),
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M1 CAD 준비 (mm 정규화 + part 분리 + keypoints)")
    ap.add_argument("--config", help="JSON 설정 파일 (CLI 인자보다 우선순위 낮음)")
    ap.add_argument("--source", help="소스 메쉬 (STL/OBJ/PLY)")
    ap.add_argument("--obj-id", help="출력 디렉토리 이름 (assets/obj/<obj_id>)")
    ap.add_argument("--scale", type=float, help="mm 로 만드는 배율 (cm 소스면 10, cascadio STEP 이면 1000)")
    ap.add_argument("--split", choices=["plane", "parts"], default=None,
                    help="plane=평면 컷(구 CAD, 파트 트리 없음) / parts=solid 단위(STEP 멀티바디)")
    ap.add_argument("--up-axis", default=None, help="소스의 up axis (z|y|x). 기본 z")
    ap.add_argument("--z-cut-mm", type=float, help="[plane] flange 분리 평면 z (스케일 적용 후)")
    ap.add_argument("--expect-rim-diameter-mm", type=float, default=None)
    ap.add_argument("--expect-hole-diameter-mm", type=float, default=None)
    ap.add_argument("--expect-wafer-diameter-mm", type=float, default=None,
                    help="[parts] 단위 체크섬 — 웨이퍼 지름")
    ap.add_argument("--expect-n-wafers", type=int, default=None,
                    help="[parts] 단위 체크섬 — 웨이퍼 개수")
    ap.add_argument("--keep-wafers", action="store_true",
                    help="[parts] full.ply 에 웨이퍼 포함 (기본: 제외, wafers.ply 로 따로 저장)")
    ap.add_argument("--tolerance-mm", type=float, default=2.0)
    ap.add_argument("--n-rim-keypoints", type=int, default=16)
    ap.add_argument("--out-root", default="assets/obj")
    args = ap.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text()) if args.config else {}
    get = lambda k, d=None: getattr(args, k.replace("-", "_")) or cfg.get(k, d)  # noqa: E731

    source = Path(get("source"))
    obj_id = get("obj-id")
    scale = args.scale if args.scale is not None else cfg.get("scale", 1.0)
    z_cut = args.z_cut_mm if args.z_cut_mm is not None else cfg.get("z-cut-mm")
    method = args.split or cfg.get("split", "plane")
    up_axis = args.up_axis or cfg.get("up-axis", "z")
    exp = lambda k: (getattr(args, k.replace("-", "_")) if getattr(args, k.replace("-", "_")) is not None  # noqa: E731
                     else cfg.get(k))
    keep_wafers = args.keep_wafers or bool(cfg.get("keep-wafers", False))
    if not source or not obj_id:
        ap.error("source / obj-id 가 필요하다 (CLI 또는 --config)")
    if method == "plane" and z_cut is None:
        ap.error("--split plane 은 z-cut-mm 이 필요하다")

    out_dir = Path(args.out_root) / obj_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"소스: {source}  (scale ×{scale} → mm, up={up_axis}, split={method})")
    parts_info = None
    if method == "parts":
        model = to_z_up(load_multibody(source, scale), up_axis)
        bodies = split_bodies(model)
        print(f"  전체: verts={len(model.vertices)} faces={len(model.faces)} solid {len(bodies)}개")
        print(f"  bbox {np.round(model.bounds[0],2)} ~ {np.round(model.bounds[1],2)} mm (Z-up 변환 후)")
        cls = classify_bodies(bodies, exp("expect-wafer-diameter-mm") or 300.0, args.tolerance_mm)
        flange_raw = cls["flange"]
        wafers, others = cls["wafers"], cls["others"]
        print(f"  분류: flange 1 / wafer {len(wafers)} / 기타 {len(others)}")
        print(f"    flange: faces={len(flange_raw.faces)} watertight={flange_raw.is_watertight} "
              f"z[{flange_raw.bounds[0][2]:.1f},{flange_raw.bounds[1][2]:.1f}]")
        # full = flange + 기타(본체·도어). 웨이퍼는 '내용물'이라 기본 제외.
        keep = [flange_raw, *others] + (wafers if keep_wafers else [])
        full_raw = trimesh.util.concatenate(keep)
        body_raw = trimesh.util.concatenate(others) if len(others) > 1 else others[0]
        parts_info = {"n_solids": len(bodies), "n_wafers": len(wafers), "n_others": len(others),
                      "wafers_in_full": keep_wafers}
    else:
        full_raw = load_scaled(source, scale)
        print(f"  전체: verts={len(full_raw.vertices)} faces={len(full_raw.faces)} "
              f"watertight={full_raw.is_watertight} volume={full_raw.volume/1000:.1f}cm^3")
        print(f"  bbox {np.round(full_raw.bounds[0],2)} ~ {np.round(full_raw.bounds[1],2)} mm")
        flange_raw, n_comp = split_part_by_plane(full_raw, z_cut)
        print(f"  z>={z_cut} 컷 → 연결성분 {n_comp}개, flange 선택: "
              f"faces={len(flange_raw.faces)} watertight={flange_raw.is_watertight}")
        wafers, body_raw = [], body_complement(full_raw, z_cut)
        parts_info = {"n_components": n_comp}

    feat = measure_standard_features(flange_raw)
    print("  flange 실측:")
    shape = "원형" if feat["outline_is_circular"] else f"비원형 {feat['outline_side_x_mm']:.1f}×{feat['outline_side_y_mm']:.1f}mm"
    print(f"    외곽  외접ø{feat['rim_diameter_mm']:.2f}mm ({shape})")
    print(f"    중심 홀 ø{feat['center_hole_diameter_mm']:.2f}mm")
    print(f"    주 상면 z={feat['top_plane_z_mm']:.2f}mm (면적 {feat['top_plane_area_mm2']:.0f}mm²), "
          f"bbox 최상단 z={feat['bbox_top_z_mm']:.2f}mm")

    # ── 단위 자체 검증: 표준 치수가 안 맞으면 스케일이 틀린 것이다 ──────────────
    # 무엇을 체크섬으로 쓸지는 CAD 마다 다르다. 구 CAD 는 rim ø190/hole ø40, 신 CAD 는 웨이퍼 ø300×25.
    # **하나도 지정하지 않으면 실패시킨다** — 체크섬 없는 단위는 조용히 틀릴 수 있다.
    errs, checks = [], []
    if exp("expect-rim-diameter-mm") is not None:
        checks.append("rim")
        if abs(feat["rim_diameter_mm"] - exp("expect-rim-diameter-mm")) > args.tolerance_mm:
            errs.append(f"rim ø{feat['rim_diameter_mm']:.2f} ≠ 기대 ø{exp('expect-rim-diameter-mm')}±{args.tolerance_mm}")
    if exp("expect-hole-diameter-mm") is not None:
        checks.append("hole")
        if abs(feat["center_hole_diameter_mm"] - exp("expect-hole-diameter-mm")) > args.tolerance_mm:
            errs.append(f"hole ø{feat['center_hole_diameter_mm']:.2f} ≠ 기대 ø{exp('expect-hole-diameter-mm')}±{args.tolerance_mm}")
    if exp("expect-n-wafers") is not None:
        checks.append("wafer")
        wd = exp("expect-wafer-diameter-mm") or 300.0
        if len(wafers) != exp("expect-n-wafers"):
            errs.append(f"웨이퍼 {len(wafers)}장 ≠ 기대 {exp('expect-n-wafers')}장 (ø{wd} 원판 기준)")
        else:
            print(f"    웨이퍼 ø{wd:.0f} × {len(wafers)}장 확인")
    if not checks:
        print("\n❌ 단위 체크섬이 하나도 지정되지 않았다 — 스케일이 틀려도 조용히 통과한다.",
              file=sys.stderr)
        print("   expect-rim-diameter-mm / expect-hole-diameter-mm / expect-n-wafers 중 하나 이상을 준다.",
              file=sys.stderr)
        return 2
    if errs:
        print("\n❌ 단위/스케일 검증 실패 — 표준 치수가 맞지 않는다:", file=sys.stderr)
        for e in errs:
            print(f"   {e}", file=sys.stderr)
        print("   --scale 을 확인할 것 (cm 소스면 10, inch 면 25.4).", file=sys.stderr)
        return 2
    print(f"  ✅ 단위 검증 통과 ({'+'.join(checks)})")

    # ── 원점 = flange 주 상면 중심. 모든 메쉬에 **동일하게** 적용한다 ─────────────
    origin = np.array([0.0, 0.0, feat["top_plane_z_mm"]])
    full = full_raw.copy(); full.apply_translation(-origin)
    flange = flange_raw.copy(); flange.apply_translation(-origin)
    body = body_raw.copy(); body.apply_translation(-origin)
    print(f"  원점 이동: -{np.round(origin,3)} (flange 주 상면 중심)")

    full.export(out_dir / "full.ply")
    flange.export(out_dir / "top_flange.ply")
    body.export(out_dir / "body.ply")
    if wafers:
        w = trimesh.util.concatenate(wafers); w.apply_translation(-origin)
        w.export(out_dir / "wafers.ply")
        print(f"  wafers.ply 별도 저장 ({len(wafers)}장, full.ply 포함={keep_wafers})")
    (out_dir / "keypoints.json").write_text(
        json.dumps(build_keypoints(flange_raw, origin, args.n_rim_keypoints), indent=2)
    )

    meta = {
        "obj_id": obj_id,
        "units": "mm",
        "origin": {
            "definition": "flange 주 상면(dominant top plane) 중심, 중심축 위",
            "offset_from_source_mm": origin.round(6).tolist(),
            "rationale": "FoundationPose 의 depth-median Z 초기화가 관측 표면 근처 원점에서 정합 (CONSUMER_6DPOSE.md §2.6-1)",
        },
        "source": {
            "path": str(source),
            "sha256": sha256(source),
            "scale_applied": scale,
            "up_axis": up_axis,
        },
        "part_split": {
            "method": ("solid(연결성분) 단위 — CAD 가 파트로 분리돼 있다"
                       if method == "parts" else "plane cut + connected component (중심축 포함 성분)"),
            "up_axis_source": up_axis,
            "z_cut_mm_source_frame": z_cut,
            **(parts_info or {}),
        },
        "unit_checksum": {"applied": checks, "tolerance_mm": args.tolerance_mm},
        "standard_features_semi_e47_1_1106": feat,
        "meshes": {
            "full.ply": {
                "faces": int(len(full.faces)),
                "watertight": bool(full.is_watertight),
                "volume_cm3": round(float(full.volume) / 1000, 3),
                "bbox_mm": [full.bounds[0].round(4).tolist(), full.bounds[1].round(4).tolist()],
                "use": "stage-1 coarse pose (body 포함 — 근사 대칭인 flange 단독의 90°/180° 오추정 방지)",
            },
            "top_flange.ply": {
                "faces": int(len(flange.faces)),
                "watertight": bool(flange.is_watertight),
                "volume_cm3": round(float(flange.volume) / 1000, 3),
                "bbox_mm": [flange.bounds[0].round(4).tolist(), flange.bounds[1].round(4).tolist()],
                "use": "stage-2 정밀 refine (표준부만 — 제조사 불변)",
            },
            "body.ply": {
                "faces": int(len(body.faces)),
                "volume_cm3": round(float(body.volume) / 1000, 3),
                "use": "렌더용 — USD 에서 top_flange 와 겹치지 않는 별개 prim 으로 넣어 part mask 를 얻는다. "
                       "body ∪ top_flange ≈ full (컷면에 내부 캡이 생기지만 외부에서 보이지 않는다)",
            },
        },
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    print(f"\n산출물 → {out_dir}")
    for f in ["full.ply", "top_flange.ply", "keypoints.json", "meta.json"]:
        print(f"  {f:16s} {(out_dir / f).stat().st_size/1024:8.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
