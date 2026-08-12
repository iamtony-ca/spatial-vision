"""rim 밴드 마스크를 **주어진 pose 로 정확히 투영**해 만든다 (진단용 상한).

    envs/cad/bin/python -m spatial_vision.cad.render_band_masks \
        --capture runs/dr2_near --obj assets/obj/foup_300_semi_rim20 --pose gt \
        --out runs/rim_maskgt_w20

왜 필요한가 — **모델 문제와 마스크 문제를 가른다**
    rim 밴드 가설이 실패할 때 원인은 둘이다: (a) 테두리만으로는 방향을 못 정한다,
    (b) 밴드 **마스크**를 정확히 못 만든다. 처방이 정반대이므로 먼저 갈라야 한다.
    이 스크립트는 (b) 를 **완전히 제거한** 상한을 만든다 — 여기서도 실패하면 (a) 다.

⚠️ **`--pose gt` 는 자기순환이다.** 실환경에 그대로 못 쓴다(GT 가 없다 —
   `PIPELINE_CATALOG §7.5`). 배포 경로는 `pose_fp --mask-band-mm`(마스크 침식, GT-free)이거나
   coarse pose 에서의 재투영이다. 이 산출물은 **상한 비교용**으로만 인용한다.

실루엣은 **투영 삼각형의 합집합**으로 만든다 — 밴드는 가운데가 뚫려 있어 볼록껍질을 쓰면 메워진다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import trimesh

MM_TO_M = 0.001


def project_faces(mesh: trimesh.Trimesh, T_mm: np.ndarray, K: np.ndarray,
                  hw: tuple[int, int]) -> np.ndarray:
    V = np.asarray(mesh.vertices)
    F = np.asarray(mesh.faces)
    Xc = (T_mm[:3, :3] @ V.T + T_mm[:3, 3:4]).T
    uv = (K @ Xc.T).T
    good = uv[:, 2] > 1e-6
    uv = np.divide(uv[:, :2], np.where(uv[:, 2:3] > 1e-6, uv[:, 2:3], 1.0))
    tri = np.rint(uv[F[good[F].all(axis=1)]]).astype(np.int32)
    m = np.zeros(hw, np.uint8)
    # ⚠️ `cv2.fillPoly(m, tri, 255)` 로 한 번에 그리면 안 된다 — **겹치는 삼각형이 짝홀 규칙으로
    #    상쇄**되어 내부에 구멍이 뚫린다(full flange 실루엣이 밴드보다 작게 나오는 것이 신호다).
    #    합집합이 필요하므로 삼각형마다 따로 채운다.
    for t in tri:
        cv2.fillConvexPoly(m, t, 255)
    return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="rim 밴드 마스크 정확 투영 (진단용 상한)")
    ap.add_argument("--capture", required=True, help="cam.json + pose 가 있는 캡처 디렉토리")
    ap.add_argument("--obj", required=True, help="밴드 obj (top_flange.ply = 밴드)")
    ap.add_argument("--pose", default="gt", choices=["gt", "pred"],
                    help="gt=pose_gt.json (⚠️ 자기순환, 상한 전용) / pred=--pose-dir 의 예측 pose")
    ap.add_argument("--pose-dir", default=None)
    ap.add_argument("--pose-name", default="pose_coarse.json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    cap, out = Path(args.capture), Path(args.out)
    mesh = trimesh.load(Path(args.obj) / "top_flange.ply", process=False)
    frames = sorted([p for p in cap.glob("frame_*") if p.is_dir()]) or [cap]

    n, areas = 0, []
    for f in frames:
        cam = json.loads((f / "cam.json").read_text())
        K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], float)
        if args.pose == "gt":
            pj = f / "pose_gt.json"
        else:
            pj = Path(args.pose_dir) / f.name / args.pose_name
        if not pj.exists():
            print(f"  {f.name}: {pj} 없음 — 건너뜀")
            continue
        d = json.loads(pj.read_text())
        T = np.eye(4)
        T[:3, :3] = np.asarray(d["R"], float).reshape(3, 3)
        T[:3, 3] = np.asarray(d["t_mm"], float)
        hw = cv2.imread(str(f / "left.png"), cv2.IMREAD_GRAYSCALE).shape
        m = project_faces(mesh, T, K, hw)
        od = out / f.name
        od.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(od / "mask_flange.png"), m)
        cv2.imwrite(str(od / "mask_full.png"), m)   # --primary full 로도 읽히도록
        n += 1
        areas.append(int((m > 127).sum()))

    out.mkdir(parents=True, exist_ok=True)
    (out / "meta_band_mask.json").write_text(json.dumps({
        "stage": "band_mask", "obj": args.obj, "capture": args.capture,
        "pose_source": args.pose, "pose_dir": args.pose_dir, "frames": n,
        "area_px_median": float(np.median(areas)) if areas else 0.0,
        "warning": "pose=gt 는 자기순환 — 상한 비교 전용",
    }, indent=2, ensure_ascii=False))
    print(f"{n} 프레임 | 밴드 면적 중앙 {np.median(areas):.0f}px → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
