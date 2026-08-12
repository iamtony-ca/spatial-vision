"""M1 검증 — 생성된 메쉬 2종이 같은 좌표계에 있고 원점 규약을 지키는지 확인한다.

    envs/cad/bin/python -m spatial_vision.cad.verify_obj --obj assets/obj/foup_300

검사 항목
    1. top_flange 가 full 의 **실제 부분집합**인가 (정점→full 표면 거리 ≈ 0)
       — 좌표계가 어긋나면 여기서 바로 드러난다. 2-stage 성립의 필수 조건.
    2. 원점 규약: flange 주 상면이 z=0 인가.
    3. 표준부 치수가 meta.json 과 일치하는가.
    4. 직교 투영 렌더 3면도 — flange 가 body 위 중앙에 얹혀 있는지 눈으로 확인.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def ortho_zbuffer(
    mesh: trimesh.Trimesh,
    axis: int,
    size: int = 400,
    margin: float = 0.04,
    bounds: np.ndarray | None = None,
) -> np.ndarray:
    """축 방향 직교 투영 z-buffer. 외부 렌더러 없이 형상을 눈으로 확인하려는 용도.

    axis: 0=+X 에서 봄, 1=+Y, 2=+Z(위에서 내려다봄)
    bounds: **여러 메쉬를 겹쳐 보려면 반드시 공통 bbox 를 넘겨야 한다.**
            메쉬마다 자기 bounds 로 정규화하면 축척·중심이 달라져 겹쳐 볼 수 없다.
    반환: (size,size) float, 값 = 카메라까지의 깊이(가까울수록 작음), 배경 NaN
    """
    u, v = [a for a in range(3) if a != axis]
    T = mesh.triangles.copy()
    lo, hi = mesh.bounds if bounds is None else bounds
    span = max(hi[u] - lo[u], hi[v] - lo[v]) * (1 + margin * 2)
    cu, cv = (lo[u] + hi[u]) / 2, (lo[v] + hi[v]) / 2
    scale = size / span

    def to_px(pts):
        x = (pts[..., u] - cu) * scale + size / 2
        y = (pts[..., v] - cv) * scale + size / 2
        return x, y

    depth = np.full((size, size), np.nan)
    X, Y = to_px(T)
    D = -T[..., axis]  # 축의 + 방향에서 본다 → 값이 작을수록 가까움
    for i in range(len(T)):
        x, y, d = X[i], Y[i], D[i]
        x0, x1 = int(np.floor(x.min())), int(np.ceil(x.max()))
        y0, y1 = int(np.floor(y.min())), int(np.ceil(y.max()))
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        # 무게중심 좌표
        d00 = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d00) < 1e-12:
            continue
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d00
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d00
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        dd = w0 * d[0] + w1 * d[1] + w2 * d[2]
        sub = depth[gy[inside], gx[inside]]
        depth[gy[inside], gx[inside]] = np.where(np.isnan(sub), dd[inside], np.minimum(sub, dd[inside]))
    return depth


def save_views(full: trimesh.Trimesh, flange: trimesh.Trimesh, out: Path, size: int = 400) -> None:
    """3면도 PNG — full 을 회색, flange 영역을 빨강으로 덧칠해 정합을 눈으로 본다."""
    import struct
    import zlib

    common = np.array([full.bounds[0], full.bounds[1]])  # 두 메쉬 공통 투영 기준
    tiles = []
    for axis, name in [(2, "top(+Z)"), (1, "front(+Y)"), (0, "side(+X)")]:
        df = ortho_zbuffer(full, axis, size, bounds=common)
        dl = ortho_zbuffer(flange, axis, size, bounds=common)
        img = np.zeros((size, size, 3), np.uint8)
        m = ~np.isnan(df)
        if m.any():  # 깊이를 명암으로
            v = df[m]
            g = (255 * (1 - (v - v.min()) / max(float(np.ptp(v)), 1e-9))).astype(np.uint8)
            img[m] = np.stack([g, g, g], -1) // 2 + 40
        ml = ~np.isnan(dl)
        img[ml, 0] = 255  # flange = 빨강 채널 강조
        img[ml, 1] //= 3
        img[ml, 2] //= 3
        tiles.append(img)
    canvas = np.concatenate(tiles, axis=1)[::-1]  # 이미지 좌표계로 뒤집기

    # 의존성 없이 PNG 쓰기
    h, w, _ = canvas.shape
    raw = b"".join(b"\x00" + canvas[y].tobytes() for y in range(h))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))
    out.write_bytes(png)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M1 CAD 산출물 검증")
    ap.add_argument("--obj", required=True, help="assets/obj/<obj_id> 디렉토리")
    ap.add_argument("--tol-mm", type=float, default=0.05)
    ap.add_argument("--render-size", type=int, default=400)
    args = ap.parse_args(argv)

    d = Path(args.obj)
    meta = json.loads((d / "meta.json").read_text())
    full = trimesh.load(str(d / "full.ply"), process=False)
    flange = trimesh.load(str(d / "top_flange.ply"), process=False)
    fails = []

    print(f"=== {meta['obj_id']} ===")
    print(f"full  : faces={len(full.faces):6d} watertight={full.is_watertight} "
          f"bbox z[{full.bounds[0][2]:.2f},{full.bounds[1][2]:.2f}]")
    print(f"flange: faces={len(flange.faces):6d} watertight={flange.is_watertight} "
          f"bbox z[{flange.bounds[0][2]:.2f},{flange.bounds[1][2]:.2f}]")

    # 1) flange 가 full 의 부분집합인가 — 좌표계 일치의 결정적 검사
    #    바닥 캡(z_min 평면)은 컷으로 새로 생긴 면이라 원본 표면에 없다 → 제외한다.
    V = flange.vertices
    z_cap = flange.bounds[0][2]
    keep = V[:, 2] > z_cap + 1e-6
    dist = np.abs(trimesh.proximity.signed_distance(full, V[keep]))
    print(f"\n[1] flange 정점 → full 표면 거리 (바닥 캡 {int((~keep).sum())}개 제외, {int(keep.sum())}개 검사)")
    print(f"    max={dist.max():.6f}mm  mean={dist.mean():.6f}mm")
    if dist.max() > args.tol_mm:
        fails.append(f"flange 가 full 표면 위에 있지 않다 (max {dist.max():.4f}mm > {args.tol_mm}mm) — 좌표계 불일치")
    else:
        print(f"    ✅ 두 메쉬가 같은 좌표계 (허용 {args.tol_mm}mm)")

    # 2) 원점 규약
    from spatial_vision.cad.prepare_obj import dominant_top_plane

    z_top, area = dominant_top_plane(flange)
    print(f"\n[2] 원점 규약: flange 주 상면 z={z_top:+.4f}mm (면적 {area:.0f}mm²) — 0 이어야 함")
    if abs(z_top) > args.tol_mm:
        fails.append(f"원점이 주 상면에 있지 않다 (z={z_top:.4f})")
    else:
        print("    ✅ 원점 = flange 주 상면 중심")
    # rim 원의 중심을 최소자승으로 맞춰 본다 — 원점 축이 실제 rim 축과 일치하는지의 직접 검사.
    # (정점 평균은 정점 분포에 좌우돼 지표가 못 된다.)
    rr = np.linalg.norm(flange.vertices[:, :2], axis=1)
    P = flange.vertices[rr > rr.max() - 0.5][:, :2]
    if len(P) >= 3:
        A = np.c_[2 * P, np.ones(len(P))]
        sol, *_ = np.linalg.lstsq(A, (P ** 2).sum(1), rcond=None)
        cx, cy = sol[0], sol[1]
        rad = float(np.sqrt(sol[2] + cx ** 2 + cy ** 2))
        print(f"    rim 원 최소자승 적합: 중심=({cx:+.4f}, {cy:+.4f})mm, 반경={rad:.4f}mm "
              f"→ 중심축 오프셋 {np.hypot(cx, cy):.4f}mm")
        if np.hypot(cx, cy) > args.tol_mm:
            fails.append(f"rim 축이 원점 축과 어긋난다 ({np.hypot(cx,cy):.4f}mm)")

    # 3) 표준부 치수 재측정
    # ⚠️ 측정 규칙을 여기에 다시 쓰면 prepare_obj 와 갈라진다(실제로 갈라졌다: 홀을 메쉬 전체
    # 최소 반경으로 재면 원뿔 보어의 목 ø15 가 잡히고, 주 상면 개구부는 ø41 이다).
    # → **정의는 prepare_obj 한 곳에만 둔다.** 여기서는 같은 함수를 다시 돌려 meta 와 대조할 뿐이다.
    from spatial_vision.cad.prepare_obj import measure_standard_features

    remeasured = measure_standard_features(flange)
    rim_d, hole_d = remeasured["rim_diameter_mm"], remeasured["center_hole_diameter_mm"]
    f = meta["standard_features_semi_e47_1_1106"]
    shape = "원형" if remeasured["outline_is_circular"] else \
        f"비원형 {remeasured['outline_side_x_mm']:.1f}×{remeasured['outline_side_y_mm']:.1f}"
    print(f"\n[3] 표준부 재측정: 외곽 외접ø{rim_d:.2f} ({shape}) (meta ø{f['rim_diameter_mm']:.2f}), "
          f"hole ø{hole_d:.2f} (meta ø{f['center_hole_diameter_mm']:.2f})")
    if abs(rim_d - f["rim_diameter_mm"]) > args.tol_mm or abs(hole_d - f["center_hole_diameter_mm"]) > args.tol_mm:
        fails.append("표준부 치수가 meta.json 과 다르다")
    else:
        print("    ✅ meta.json 과 일치")

    # 4) keypoint 가 실제 형상 위에 있는가
    # ⚠️ 이게 없어서 놓쳤던 것: rim 을 원으로 가정하고 외접반경 원주에 뿌리면, 외곽이 정사각형인
    # CAD 에서 16개 중 12개가 최대 21.3mm 허공에 뜬다. M2 의 투영 검사는 **2D 실루엣 안에만
    # 들어가면 통과**하므로 이 오류를 걸러주지 못한다 → M1 에서 3D 로 직접 잰다.
    kp_path = d / "keypoints.json"
    if kp_path.exists():
        kp = json.loads(kp_path.read_text())["points"]
        print("\n[4] keypoint ↔ 형상 일치")
        for name in ("rim_circle", "center_hole_circle"):
            if name not in kp:
                continue
            P = np.asarray(kp[name]["samples"], dtype=float)
            dev = np.abs(trimesh.proximity.signed_distance(flange, P))
            n_bad = int((dev > args.tol_mm).sum())
            kind = kp[name].get("outline", "circle")
            print(f"    {name:20s} ({kind}): 최대 이탈 {dev.max():.4f}mm, "
                  f"허용({args.tol_mm}mm) 초과 {n_bad}/{len(P)}")
            if n_bad:
                fails.append(f"{name} keypoint {n_bad}개가 형상에서 벗어나 있다 (max {dev.max():.2f}mm)")
        if not any("keypoint" in f for f in fails):
            print("    ✅ 전부 형상 위")

    # 5) 3면도
    out_png = d / "views.png"
    save_views(full, flange, out_png, args.render_size)
    print(f"\n[5] 3면도 저장: {out_png} (회색=full, 빨강=top_flange)")

    print()
    if fails:
        for x in fails:
            print(f"❌ {x}")
        return 1
    print("✅ M1 검증 통과")
    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main())
