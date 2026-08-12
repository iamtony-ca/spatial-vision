"""CAD 메쉬를 **여러 각도에서 셰이딩 렌더**해 형상을 눈으로 검사한다.

    envs/cad/bin/python -m spatial_vision.viz.render_mesh \
        --mesh assets/obj/foup_300_semi_spec/top_flange.ply \
        --compare assets/obj/foup_300_semi/top_flange.ply \
        --out docs/semi/rim_render_compare.png

왜 필요한가
    `views.png`(직교 3면도)는 실루엣만 보여줘서 **라운드·융기·크리스** 같은 표면 형상이 안 보인다.
    이 프로젝트에서 기하 오류를 실제로 잡아낸 건 지표가 아니라 눈이었다(횡단 정리 #39·#46·#50).
    Isaac 캡처는 씬 구성이 필요하고 느리므로, **형상 확인용**으로는 이 렌더가 맞다.

무엇을 보여주나
    Blinn-Phong(확산 + 강한 스페큘러). **스페큘러가 라운드를 드러낸다** — 평평한 면과 필렛은
    확산광으로는 거의 같아 보이지만 하이라이트 띠의 유무로 갈린다.
    ⚠️ 화가 알고리즘(면 중심 깊이 정렬 + 후면 제거)이라 **상호 관통이 있는 메쉬에서는 틀린다.**
    FOUP flange 처럼 위에서 봐 star-shaped 인 형상에는 충분하다. 정확한 가림이 필요하면 z-buffer 로 바꿀 것.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import trimesh


def render(mesh: trimesh.Trimesh, tilt_deg: float, azim_deg: float, W: int = 560, H: int = 560,
           dist: float = 380.0, fov: float = 35.0, target=None) -> np.ndarray:
    """tilt=0 이면 정수리에서, 90 이면 옆에서 본다. 길이 단위는 메쉬와 같다(mm)."""
    V = np.asarray(mesh.vertices, float)
    F = np.asarray(mesh.faces)
    target = np.zeros(3) if target is None else np.asarray(target, float)
    t, a = np.deg2rad(tilt_deg), np.deg2rad(azim_deg)
    eye = target + dist * np.array([np.sin(t) * np.cos(a), np.sin(t) * np.sin(a), np.cos(t)])
    fwd = target - eye
    fwd /= np.linalg.norm(fwd)
    up0 = np.array([0., 0., 1.]) if abs(fwd[2]) < 0.98 else np.array([0., 1., 0.])
    right = np.cross(fwd, up0)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    Rw = np.stack([right, -up, fwd])                       # world → camera (OpenCV 규약)
    Xc = (Rw @ (V - eye).T).T
    f = 0.5 * H / np.tan(np.deg2rad(fov) / 2)
    K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]])
    uv = (K @ Xc.T).T
    uv = uv[:, :2] / np.maximum(uv[:, 2:3], 1e-6)

    Nc = (Rw @ np.asarray(mesh.face_normals).T).T
    Cc = (Rw @ (np.asarray(mesh.triangles_center) - eye).T).T
    keep = (np.einsum("ij,ij->i", Nc, Cc) < 0) & (Xc[F][:, :, 2] > 1.0).all(1)
    order = np.where(keep)[0]
    order = order[np.argsort(-Cc[order, 2])]               # 뒤 → 앞 (화가 알고리즘)

    L = np.array([0.35, -0.55, 0.76]); L /= np.linalg.norm(L)
    Hv = L + np.array([0, 0, -1.0]); Hv /= np.linalg.norm(Hv)
    shade = np.clip(38 + 165 * np.clip(-(Nc @ L), 0, 1)
                    + 210 * np.clip(-(Nc @ Hv), 0, 1) ** 48, 0, 255)
    img = np.zeros((H, W, 3), np.uint8)
    tri = np.rint(uv[F]).astype(np.int32)
    for i in order:
        c = int(shade[i])
        cv2.fillConvexPoly(img, tri[i], (c, c, c))
    return img


def _label(img, txt):
    cv2.putText(img, txt, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    return img


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="메쉬 다각도 셰이딩 렌더 (형상 육안 검사)")
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--compare", default=None, help="나란히 놓을 비교 메쉬(예: 원본)")
    ap.add_argument("--angles", default="0,0 20,20 40,20 65,20",
                    help="'tilt,azim' 공백 구분. 예: '0,0 30,20 70,90'")
    ap.add_argument("--dist", type=float, default=380.0)
    ap.add_argument("--fov", type=float, default=35.0)
    ap.add_argument("--target", default="0,0,0", help="바라볼 점 x,y,z (확대 검사에 쓴다)")
    ap.add_argument("--size", type=int, default=560)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--title", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    angles = [tuple(float(v) for v in a.split(",")) for a in args.angles.split()]
    tgt = np.array([float(v) for v in args.target.split(",")])
    meshes = [(Path(args.mesh).parent.name, trimesh.load(args.mesh, process=False))]
    if args.compare:
        meshes.insert(0, (Path(args.compare).parent.name, trimesh.load(args.compare, process=False)))

    tiles = []
    for (t, a) in angles:
        for name, m in meshes:
            tiles.append(_label(render(m, t, a, args.size, args.size, args.dist, args.fov, tgt),
                                f"{name}  tilt{t:.0f} azim{a:.0f}"))
    per_row = len(meshes) * max(1, args.cols // max(len(meshes), 1))
    rows = [np.concatenate(tiles[i:i + per_row], 1) for i in range(0, len(tiles), per_row)]
    w = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0))) for r in rows]
    img = np.concatenate(rows, 0)
    bar = np.full((30, img.shape[1], 3), 35, np.uint8)
    cv2.putText(bar, args.title or Path(args.mesh).as_posix(), (8, 21),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), np.concatenate([bar, img], 0))
    print(f"→ {out}  ({len(tiles)} 뷰)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
