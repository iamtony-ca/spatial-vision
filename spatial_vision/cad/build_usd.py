"""M2 준비 — M1 산출 메쉬로 Isaac 용 USD 에셋을 **직접 저작**한다.

    envs/cad/bin/python -m spatial_vision.cad.build_usd --obj assets/obj/foup_300

왜 omni.kit.asset_converter 를 안 쓰나
    변환기는 단위(metersPerUnit)·up-axis 를 소스에서 추측하는데 tessellated 포맷은 단위를 담지
    않는다(sdg_ws `tools/import_cad.py` 가 같은 문제를 경고한다). 우리는 M1 에서 좌표계를 이미
    확정했으므로 추측이 낄 여지를 없애고 pxr 로 직접 쓴다. Isaac 없이 cad venv 에서 돌아간다.

구조
    /World/<obj_id>            Xform   ← 이 prim 의 world transform 이 곧 pose GT 의 대상
      /body                    Mesh    semantic: <obj_id>
      /top_flange              Mesh    semantic: <obj_id>,top_flange
    body 와 top_flange 는 **겹치지 않는** 별개 prim 이다 — Isaac 의 semantic seg 가 prim 단위라
    part mask(flange only)를 얻으려면 이 구조여야 한다. 겹치면 z-fighting 이 난다.

★ 원점 규약 (PIPELINE_PLAN.md §4.1 보강)
    이 USD 는 **pose frame(= flange 주 상면 중심)을 그대로 원점으로 굽는다.** M1 의 ply 와 완전히
    같은 좌표계다. §4.1 이 "USD origin 은 건드리지 말고 GT 를 t'=t+R·d 로 변환하라"고 한 것은
    **우리가 저작하지 않은 에셋**(예: sdg_ws 가 CAD 원점으로 만든 USD)에 대한 처방이고,
    우리가 직접 만드는 에셋은 애초에 한 규약으로 통일하는 편이 §4.1 이 경고한 "두 규약 혼재" 위험을
    원천 제거한다. 배치는 캡처 스크립트가 명시적으로 계산한다(바닥에 놓으려면 원점을 +|z_min| 만큼 올림).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
from pxr import Gf, Sdf, Usd, UsdGeom, Vt

MM_TO_M = 0.001


def add_mesh(stage: Usd.Stage, path: str, mesh: trimesh.Trimesh, scale: float) -> UsdGeom.Mesh:
    """trimesh → UsdGeom.Mesh. 삼각형만, subdivision 없음(CAD 형상을 그대로 유지)."""
    m = UsdGeom.Mesh.Define(stage, path)
    v = np.asarray(mesh.vertices, dtype=np.float64) * scale
    f = np.asarray(mesh.faces, dtype=np.int32)
    m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(v.astype(np.float32)))
    m.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(len(f), 3, np.int32)))
    m.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(f.reshape(-1)))
    m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)  # CAD 메쉬는 세분화하지 않는다
    # 면 법선 (flat shading) — 없으면 렌더러가 추정하면서 곡면이 뭉개질 수 있다
    fn = np.repeat(np.asarray(mesh.face_normals, dtype=np.float32), 3, axis=0)
    n = m.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(fn))
    m.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    lo, hi = v.min(0), v.max(0)
    # Gf.Vec3f 는 numpy 스칼라를 안 받는다 → 파이썬 float 로
    m.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float, lo)), Gf.Vec3f(*map(float, hi))]))
    return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M1 메쉬 → Isaac USD 에셋")
    ap.add_argument("--obj", required=True, help="assets/obj/<obj_id> 디렉토리")
    ap.add_argument("--out", default=None, help="기본값: <obj>/mesh.usda")
    args = ap.parse_args(argv)

    d = Path(args.obj)
    meta = json.loads((d / "meta.json").read_text())
    obj_id = meta["obj_id"]
    out = Path(args.out) if args.out else d / "mesh.usda"

    body = trimesh.load(str(d / "body.ply"), process=False)
    flange = trimesh.load(str(d / "top_flange.ply"), process=False)

    stage = Usd.Stage.CreateNew(str(out)) if not out.exists() else Usd.Stage.CreateInMemory()
    if out.exists():
        stage = Usd.Stage.CreateNew(str(out.with_suffix(".tmp.usda")))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)   # Isaac 스테이지 관례
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)          # 정점을 미터로 쓴다

    root = UsdGeom.Xform.Define(stage, f"/{obj_id}")
    stage.SetDefaultPrim(root.GetPrim())
    add_mesh(stage, f"/{obj_id}/body", body, MM_TO_M)
    add_mesh(stage, f"/{obj_id}/top_flange", flange, MM_TO_M)

    # 소비자가 규약을 코드가 아니라 파일에서 읽을 수 있도록 메타를 prim 에 새긴다.
    p = root.GetPrim()
    p.CreateAttribute("spatial_vision:units", Sdf.ValueTypeNames.String).Set("m")
    p.CreateAttribute("spatial_vision:origin", Sdf.ValueTypeNames.String).Set(
        meta["origin"]["definition"]
    )
    p.CreateAttribute("spatial_vision:source_sha256", Sdf.ValueTypeNames.String).Set(
        meta["source"]["sha256"]
    )
    # 바닥에 놓을 때 원점을 얼마나 띄워야 하는지 (캡처 스크립트가 읽는다)
    z_min_m = float(min(body.bounds[0][2], flange.bounds[0][2])) * MM_TO_M
    p.CreateAttribute("spatial_vision:z_min_m", Sdf.ValueTypeNames.Float).Set(z_min_m)

    stage.GetRootLayer().Save()
    tmp = out.with_suffix(".tmp.usda")
    if tmp.exists():
        tmp.replace(out)

    print(f"USD 저장: {out}")
    print(f"  /{obj_id}/body        faces={len(body.faces)}")
    print(f"  /{obj_id}/top_flange  faces={len(flange.faces)}")
    print(f"  upAxis=Z  metersPerUnit=1.0  z_min={z_min_m:.4f}m (바닥 배치 시 원점을 이만큼 올린다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
