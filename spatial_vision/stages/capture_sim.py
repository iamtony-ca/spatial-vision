"""M2 — Isaac Sim 스테레오 rig 캡처 (standalone).

    /isaac-sim/python.sh -m spatial_vision.stages.capture_sim \
        --obj-usd assets/obj/foup_300/mesh.usda --out runs/sim01 --frames 8

★ 왜 rig 인가
    FoundationStereo 는 좌/우 쌍이 입력이다. 두 카메라를 **개별로** 움직이면 baseline 이 매 프레임
    달라져 stereo 가 무효가 된다. 그래서 부모 Xform(rig) 하나만 움직이고 좌/우는 rig 로컬에
    고정한다: right = left + (baseline, 0, 0) in rig-local X. (SDG 로드맵 §5-6 항목 I 와 동일 설계)

★ 왜 look_at 을 직접 계산하나
    `rep.functional.modify.pose(..., look_at_value=)` 가 Xform 에 대해 어떤 전방 축 규약을 쓰는지
    문서화돼 있지 않다. 스테레오는 좌/우 상대 회전이 0 이어야(rectified) 성립하므로 규약을 추측하지
    않고 USD 카메라 규약(-Z 전방, +Y 위, +X 오른쪽)으로 rig 행렬을 직접 구성한다.

★ 6.0.1 API (sdg_ws 에서 검증된 것만 사용)
    rep.functional.create.camera / dome_light / reference,  rep.functional.modify.semantics,
    rep.create.render_product,  rep.annotators.get(...).attach(rp),
    rep.orchestrator.set_capture_on_play(False) / step(...),
    rep.functional.utils.get_world_transform(prim).GetMatrix()  → row-vector local→world
    camera_params: cameraViewTransform(row-vector world→cam), cameraFocalLength,
                   cameraAperture, cameraApertureOffset, renderProductResolution,
                   metersPerSceneUnit
    distance_to_image_plane: float32 (H,W), **스테이지 단위**, 배경 +inf/NaN

출력 (PIPELINE_PLAN.md §4 계약 + sim GT)
    <out>/frame_XXXX/  left.png right.png cam.json
                       depth_gt.png(16-bit mm) disparity_gt.npy
                       mask_full.png mask_flange.png
                       pose_gt.json  meta_capture.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# ── SimulationApp 은 다른 Isaac/omni import 보다 **먼저** 만들어야 한다 ────────────
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Isaac Sim 스테레오 rig 캡처")
    ap.add_argument("--obj-usd", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    # 카메라 — 기본값은 실측 캘리브레이션(CONSUMER_6DPOSE.md §4-A: fx=fy=952.2, cx=640, cy=360 @1280x720)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fx", type=float, default=952.2)
    ap.add_argument("--fy", type=float, default=None, help="기본값 = fx (정사각 픽셀)")
    # 🔴 --cx/--cy 는 **코너 원점(USD/Isaac)** 규약이다. cam.json 에는 −0.5 되어 OpenCV 규약으로 나간다
    #    (`intrinsics_from_params` 참조, 횡단 정리 #1). 실카메라 캘리브레이션(ZED SDK·`rs2_intrinsics`)은
    #    **OpenCV(픽셀 중심)** 이므로 그 값을 여기 넣을 때는 **+0.5** 해야 한다.
    #    안 하면 정확히 0.5px 이 어긋나 경사면에서 0.2~0.8mm 깊이 오차가 조용히 들어간다.
    #    → 카메라 프로파일은 `assets/cam/*.json` 의 `capture_sim_args` 를 그대로 쓸 것.
    ap.add_argument("--cx", type=float, default=None,
                    help="코너 원점 규약. 기본값 = width/2. OpenCV cx 를 넣으려면 +0.5")
    ap.add_argument("--cy", type=float, default=None,
                    help="코너 원점 규약. 기본값 = height/2. OpenCV cy 를 넣으려면 +0.5")
    ap.add_argument("--baseline-mm", type=float, default=120.0,
                    help="ZED X=120, ZED X Mini=63, D435(IR)=50")
    ap.add_argument("--near-m", type=float, default=0.05)
    ap.add_argument("--far-m", type=float, default=100.0)
    # 뷰 제약 (CONSUMER_6DPOSE.md §2.7.2: top flange 가 보이도록, 반경 1.0~2.5m)
    ap.add_argument("--distance-m", type=float, nargs=2, default=[1.0, 2.5])
    ap.add_argument("--elevation-deg", type=float, nargs=2, default=[40.0, 80.0])
    ap.add_argument("--azimuth-deg", type=float, nargs=2, default=[-180.0, 180.0])
    ap.add_argument("--yaw-jitter-deg", type=float, default=180.0, help="객체 z축 회전 랜덤 범위 ±")
    ap.add_argument("--no-ground", action="store_true")
    # ── 씬 randomization / clutter (M2 확장) ─────────────────────────────────
    ap.add_argument("--distractors", type=int, default=0, help="사전 생성할 distractor 풀 크기")
    ap.add_argument("--distractor-foups", type=int, default=0,
                    help="그중 **같은 FOUP** 인스턴스 개수. 유사 인스턴스 오선택률 측정의 전제")
    ap.add_argument("--distractors-active", type=int, nargs=2, default=[0, 0], help="프레임당 표시 개수")
    ap.add_argument("--distractor-size-m", type=float, nargs=2, default=[0.1, 0.4])
    ap.add_argument("--scatter-radius-m", type=float, default=1.2)
    ap.add_argument("--occluders", type=int, default=0)
    ap.add_argument("--occluders-active", type=int, nargs=2, default=[0, 0])
    ap.add_argument("--occluder-size-m", type=float, nargs=2, default=[0.08, 0.25])
    ap.add_argument("--occluder-ray-frac", type=float, nargs=2, default=[0.2, 0.5],
                    help="카메라→타깃 시선 위 위치 (0=타깃, 1=카메라)")
    ap.add_argument("--occluder-offset-sigma", type=float, default=0.6,
                    help="시선에서 비껴놓는 정도(타깃 반경 배수). 0 이면 전체를 가린다")
    ap.add_argument("--light-fixtures", type=int, default=0, help="사전 생성할 조명 개수")
    ap.add_argument("--light-fixtures-active", type=int, nargs=2, default=[0, 0])
    ap.add_argument("--fixture-intensity", type=float, nargs=2, default=[3000.0, 30000.0])
    ap.add_argument("--light-distance-m", type=float, nargs=2, default=[2.0, 5.0])
    ap.add_argument("--dome-intensity", type=float, nargs=2, default=[1500.0, 1500.0])
    ap.add_argument("--color-temperature-k", type=float, nargs=2, default=[6500.0, 6500.0])
    ap.add_argument("--no-visib-fract", action="store_true",
                    help="가림률 프리체크를 끈다(프레임당 싼 렌더 2회 절약, 대신 과한 가림을 못 막는다)")
    ap.add_argument("--min-visib-fract", type=float, default=0.35,
                    help="이 미만으로 가려지면 occluder 를 줄여 재시도한다")
    ap.add_argument("--occluder-retries", type=int, default=3)
    ap.add_argument("--min-flange-visib", type=float, default=0.99,
                    help="★ top flange 는 온전히 보이는 것을 전제로 한다. 이 미만이면 재시도")
    ap.add_argument("--occluder-aim-drop-m", type=float, default=0.20,
                    help="occluder 조준점을 원점(=flange 상면)에서 이만큼 아래로 내린다")
    # ── 배경(HDRI) / 재질 randomization ─────────────────────────────────────
    # 자산: bash envs/fetch_env_assets.sh  →  assets/env/{hdri,ground}/
    ap.add_argument("--hdri", nargs="+", default=None,
                    help="dome light latlong 텍스처 풀. 디렉토리 또는 파일들. 예: assets/env/hdri")
    ap.add_argument("--hdri-rotate-deg", type=float, nargs=2, default=[0.0, 360.0],
                    help="배경 회전 범위. lo==hi 면 고정")
    ap.add_argument("--no-hdri-normalize", dest="hdri_normalize", action="store_false",
                    help="맵별 평균 밝기 보정을 끈다. ⚠️ 끄면 프레임 밝기가 10배 이상 튄다")
    ap.add_argument("--ground-material", action="store_true",
                    help="바닥에 OmniPBR 재질을 걸고 색·거칠기(+텍스처)를 흔든다")
    ap.add_argument("--ground-textures", nargs="+", default=None, help="예: assets/env/ground")
    ap.add_argument("--ground-roughness", type=float, nargs=2, default=[0.15, 0.95])
    ap.add_argument("--ground-saturation", type=float, nargs=2, default=[0.0, 0.5])
    ap.add_argument("--ground-value", type=float, nargs=2, default=[0.15, 0.95])
    ap.add_argument("--ground-texture-scale", type=float, nargs=2, default=[0.5, 4.0])
    ap.add_argument("--body-material", action="store_true",
                    help="★ FOUP **몸체**의 재질을 흔든다. top_flange 는 건드리지 않는다. "
                         "타깃과 distractor FOUP 를 독립적으로 흔들어 색이 타깃 단서가 되지 않게 한다")
    ap.add_argument("--body-textures", nargs="+", default=None,
                    help="몸체에도 텍스처를 입힌다(기본: 색·거칠기·금속성만). "
                         "실물 FOUP 은 무지 플라스틱이라 과한 randomization 이지만, "
                         "형상 의존을 강제하는 쪽으로는 유리하다 — 효과는 측정 대상이다")
    ap.add_argument("--body-appearance", default="random",
                    choices=["random", "black", "orange", "clear"],
                    help="★ FOUP **몸체**를 실물 3종 중 하나로 **고정**한다 (사용자 확정 2026-08-13): "
                         "black=flange 와 같은 검정 불투명 · orange=반투명 주황 · clear=투명. "
                         "`random` 이면 기존 randomization. 고정 모드는 `--body-material` 없이도 "
                         "재질을 바인딩하고 **프레임마다 흔들지 않는다**(flange 와 같은 취급). "
                         "⚠️ 투명은 OmniPBR cutout opacity 라 **굴절이 없다** — 색·대비만 재현한다")
    ap.add_argument("--body-roughness", type=float, nargs=2, default=[0.05, 0.85])
    ap.add_argument("--body-metallic", type=float, nargs=2, default=[0.0, 0.35])
    ap.add_argument("--body-saturation", type=float, nargs=2, default=[0.0, 0.75])
    ap.add_argument("--body-value", type=float, nargs=2, default=[0.12, 0.95])
    ap.add_argument("--body-texture-scale", type=float, nargs=2, default=[0.5, 4.0])
    ap.add_argument("--flange-color", type=float, nargs=3, default=None, metavar=("R", "G", "B"),
                    help="★ top_flange 를 이 **고정색**으로 칠한다(실물 FOUP 은 검정). 0~1 선형 RGB. "
                         "randomize 가 아니라 상수다 — pose 앵커·exemplar 참조의 외관이므로 흔들지 않는다. "
                         "예: --flange-color 0.03 0.03 0.03")
    ap.add_argument("--flange-roughness", type=float, default=0.45)
    ap.add_argument("--flange-metallic", type=float, default=0.0)
    ap.add_argument("--rt-subframes", type=int, default=16)
    ap.add_argument("--headless", type=int, default=1)
    return ap.parse_args(argv)


ARGS = parse_args()

from isaacsim import SimulationApp  # noqa: E402

_app = SimulationApp(launch_config={"headless": bool(ARGS.headless)})

import numpy as np  # noqa: E402
import carb.settings  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
from pxr import Gf, Usd, UsdGeom  # noqa: E402

WORLD = "/World"
RIG = f"{WORLD}/stereo_rig"

# Omniverse/USD 카메라 프레임(+X 우, +Y 상, **-Z 전방**) → OpenCV/BOP 프레임(+X 우, +Y 하, +Z 전방).
# X 축 180° 회전. 이걸 빼먹으면 pose 의 Z 가 음수가 되어 투영이 전부 카메라 뒤로 간다.
# (sdg_ws `writers/bop_writer.py:46` 과 동일 — 검증된 규약)
M_USD_TO_CV = np.diag([1.0, -1.0, -1.0, 1.0])


# ────────────────────────────────────────────────────────────── 기하 유틸
def look_at_matrix(eye: np.ndarray, target: np.ndarray, up=(0.0, 0.0, 1.0)) -> Gf.Matrix4d:
    """USD 카메라 규약(-Z 전방, +Y 위, +X 오른쪽)의 row-vector local→world 행렬.

    row 0/1/2 = 카메라 로컬 X/Y/Z 축의 월드 방향, row 3 = 위치.
    (USD 는 row-vector 규약: p_world = p_local · M)
    """
    eye = np.asarray(eye, float)
    fwd = np.asarray(target, float) - eye
    n = np.linalg.norm(fwd)
    if n < 1e-9:
        raise ValueError("eye 와 target 이 같다")
    fwd /= n
    z = -fwd                                   # 카메라는 -Z 를 본다
    u = np.asarray(up, float)
    if abs(float(np.dot(u, z))) > 0.999:       # 시선이 up 과 평행하면 다른 up 을 쓴다
        u = np.array([0.0, 1.0, 0.0])
    x = np.cross(u, z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    M = Gf.Matrix4d(1.0)
    for i, v in enumerate((x, y, z)):
        M.SetRow(i, Gf.Vec4d(float(v[0]), float(v[1]), float(v[2]), 0.0))
    M.SetRow(3, Gf.Vec4d(float(eye[0]), float(eye[1]), float(eye[2]), 1.0))
    return M


def set_local_transform(prim, M: Gf.Matrix4d) -> None:
    """prim 의 로컬 변환을 단일 transform op 로 덮어쓴다(기존 op 순서를 지운다)."""
    x = UsdGeom.Xformable(prim)
    x.ClearXformOpOrder()
    x.AddTransformOp().Set(M)


def orthonormalize(R: np.ndarray) -> np.ndarray:
    """SVD 로 가장 가까운 회전행렬(det=+1). 모델링 스케일이 섞여 들어온 경우를 대비."""
    U, _, Vt = np.linalg.svd(R)
    Rn = U @ Vt
    if np.linalg.det(Rn) < 0:
        U[:, -1] *= -1
        Rn = U @ Vt
    return Rn


# ────────────────────────────────────────────────────────────── 씬 구성
def optics_for_intrinsics(fx, fy, cx, cy, w, h, focal_mm=24.0):
    """요청한 픽셀 intrinsic 을 재현하는 USD 카메라 광학값(mm).

    fx = focal·W/h_aperture,  cx = W·(0.5 + h_offset/h_aperture)  (수직도 동일)
    focal 은 게이지 자유도라 임의의 양수면 되고 aperture 가 따라 스케일된다.
    ⚠️ create.camera 에는 vertical_aperture 인자가 **없어서** USD 기본값(15.2908mm)이 남는다 →
       비정사각 픽셀이 된다. 생성 후 UsdGeom.Camera 로 직접 세팅해야 한다. (sdg_ws ideal.py 와 동일)
    """
    ha = focal_mm * w / fx
    va = focal_mm * h / fy
    return {
        "focal_length_mm": focal_mm,
        "h_aperture_mm": ha,
        "v_aperture_mm": va,
        "h_offset_mm": ha * (cx / w - 0.5),
        "v_offset_mm": va * (cy / h - 0.5),
    }


def build_scene(args):
    stage = omni.usd.get_context().get_stage()
    UsdGeom.Xform.Define(stage, WORLD)
    dome = rep.functional.create.dome_light(intensity=1500, parent=WORLD, name="DomeLight")

    ground_prims = []
    if not args.no_ground:
        from isaacsim.core.experimental.objects import GroundPlane

        gp = GroundPlane(f"{WORLD}/GroundPlane")
        rep.functional.modify.semantics(gp.prims, {"class": "ground_plane"}, mode="add")
        # 재질을 걸 대상은 Xform 이 아니라 실제 **Gprim**(Mesh/Plane)이다. 상위에 걸면
        # GroundPlane 내부의 collider·guide 프림까지 물든다.
        ground_prims = [p for p in Usd.PrimRange(stage.GetPrimAtPath(f"{WORLD}/GroundPlane"))
                        if UsdGeom.Gprim(p)]

    obj_usd = str(Path(args.obj_usd).resolve())
    obj_id = Path(args.obj_usd).parent.name
    prim = rep.functional.create.reference(
        usd_path=obj_usd, parent=WORLD, name=obj_id, semantics={"class": obj_id}
    )
    prim_path = str(prim.GetPath())

    # flange 서브프림에 별도 semantic → part mask. 라벨은 "obj,part" 로 병합되어 나온다.
    flange_prim = stage.GetPrimAtPath(f"{prim_path}/top_flange")
    if not flange_prim or not flange_prim.IsValid():
        raise RuntimeError(f"top_flange 서브프림을 찾을 수 없다: {prim_path}/top_flange")
    rep.functional.modify.semantics([flange_prim], {"class": "top_flange"}, mode="add")

    # 바닥에 놓기: USD 원점이 flange 주 상면이므로 |z_min| 만큼 올린다.
    z_min = prim.GetAttribute("spatial_vision:z_min_m")
    z_lift = float(-z_min.Get()) if z_min and z_min.Get() is not None else 0.0
    return prim, prim_path, obj_id, z_lift, dome, ground_prims


def build_rig(args):
    """부모 Xform 아래 좌/우 카메라. 좌=(0,0,0), 우=(B,0,0) rig-local. 회전은 동일(rectified)."""
    stage = omni.usd.get_context().get_stage()
    UsdGeom.Xform.Define(stage, RIG)
    rig_prim = stage.GetPrimAtPath(RIG)

    fy = args.fy if args.fy is not None else args.fx
    cx = args.cx if args.cx is not None else args.width / 2.0
    cy = args.cy if args.cy is not None else args.height / 2.0
    o = optics_for_intrinsics(args.fx, fy, cx, cy, args.width, args.height)
    b_m = args.baseline_mm / 1000.0

    cams = {}
    for name, dx in (("left", 0.0), ("right", b_m)):
        cam = rep.functional.create.camera(
            position=(0.0, 0.0, 0.0),
            look_at=(0.0, 0.0, -1.0),
            focal_length=o["focal_length_mm"],
            horizontal_aperture=o["h_aperture_mm"],
            horizontal_aperture_offset=o["h_offset_mm"],
            vertical_aperture_offset=o["v_offset_mm"],
            clipping_range=(args.near_m, args.far_m),
            parent=RIG,
            name=name,
        )
        # create.camera 에 vertical_aperture 인자가 없다 → 직접 세팅(안 하면 fy != fx)
        UsdGeom.Camera(cam).GetVerticalApertureAttr().Set(float(o["v_aperture_mm"]))
        # 로컬 변환을 명시적으로 덮어쓴다: 회전 없음 + X 방향 baseline 만.
        M = Gf.Matrix4d(1.0)
        M.SetRow(3, Gf.Vec4d(dx, 0.0, 0.0, 1.0))
        set_local_transform(cam, M)
        rp = rep.create.render_product(cam, resolution=(args.width, args.height), name=f"{name}_rp")
        cams[name] = {"prim": cam, "rp": rp}

    annots = {}
    for name, c in cams.items():
        a = {}
        for ann, params in (("camera_params", None), ("rgb", None),
                            ("distance_to_image_plane", None),
                            ("semantic_segmentation", {"colorize": False})):
            h = rep.annotators.get(ann, init_params=params) if params else rep.annotators.get(ann)
            h.attach(c["rp"])
            a[ann] = h
        annots[name] = a
    return rig_prim, cams, annots, {"fx": args.fx, "fy": fy, "cx": cx, "cy": cy}


# ────────────────────────────────────────────────────────────── 수집/저장
def intrinsics_from_params(cam, w, h):
    """camera_params → 픽셀 intrinsic.

    ★ 반픽셀 규약 (실측으로 확정, 2026-08-07)
        Isaac 의 cx = W·(0.5 + offset/aperture) 는 **코너 원점** 연속 이미지 좌표계 값이다
        (이미지가 [0,W] 를 덮고 픽셀 k 의 중심이 k+0.5). OpenCV/BOP 는 **픽셀 중심이 정수 인덱스**다.
        그대로 쓰면 정확히 0.5픽셀이 어긋나고, 경사면에서는 그것이 깊이 오차로 나타난다
        — 실측 0.21~0.83mm(뷰 경사에 비례), −0.5 보정 시 0.0001mm 로 붕괴.
        FoundationPose·FoundationStereo·mask 소비자가 전부 OpenCV 규약이므로 **여기서 한 번** 맞춘다.
        (검증: 바닥면(world z=0)에서도 동일한 오프셋이 나와 렌더러/객체와 무관한 규약 문제임을 확인)
    """
    f = float(np.asarray(cam["cameraFocalLength"]).reshape(-1)[0])
    ap = np.asarray(cam["cameraAperture"]).reshape(-1)
    off = np.asarray(cam.get("cameraApertureOffset", [0.0, 0.0])).reshape(-1)
    ah, av = float(ap[0]), float(ap[1])
    cx_corner = w * (0.5 + float(off[0]) / ah)
    cy_corner = h * (0.5 + float(off[1]) / av)
    return {
        "fx": f * w / ah, "fy": f * h / av,
        "cx": cx_corner - 0.5, "cy": cy_corner - 0.5,     # OpenCV/BOP 규약
        "cx_usd_corner": cx_corner, "cy_usd_corner": cy_corner,  # 추적용 원본
    }


def camera_ready(annots) -> bool:
    for a in annots.values():
        cam = a["camera_params"].get_data()
        ap = np.asarray(cam.get("cameraAperture", [0, 0]), float).reshape(-1)
        if ap.size < 2 or ap[0] == 0 or ap[1] == 0:
            return False
        v = np.asarray(cam.get("cameraViewTransform", []), float).reshape(-1)
        if v.size < 16 or abs(np.linalg.det(v.reshape(4, 4))) < 1e-9:
            return False
    return True


def masks_from_semantic(sem, obj_id):
    """semantic 채널 → (full mask, flange mask).

    중첩 semantic 은 라벨이 "obj_id,top_flange" 로 **병합**되어 나온다(sdg_ws CHANGELOG 확인 사항).
    따라서 prim 경로가 아니라 **라벨 문자열로 슬라이스**한다.

    ⚠️ **부분 문자열이 아니라 정확 일치로 판정한다.** distractor 를 넣으면서 클래스를
    `foup_300_semi_distractor` 처럼 지으면 `obj_id in label` 이 참이 되어 **distractor 가 GT 마스크에
    섞여 들어간다** — 그림으로는 그럴듯해 보이고 지표만 조용히 오염된다. 라벨을 콤마로 쪼개
    집합 원소로 비교하면 이름 짓기와 무관하게 안전하다.
    """
    data = np.asarray(sem["data"], dtype=np.uint32)
    id2lab = sem.get("info", {}).get("idToLabels", {}) or {}
    full_ids, flange_ids = [], []
    for k, v in id2lab.items():
        label = v.get("class", "") if isinstance(v, dict) else str(v)
        parts = {s.strip() for s in str(label).split(",") if s.strip()}
        try:
            key = int(k)
        except (TypeError, ValueError):
            continue
        if obj_id in parts:
            full_ids.append(key)
        if "top_flange" in parts:
            flange_ids.append(key)
            if key not in full_ids:
                full_ids.append(key)
    full = np.isin(data, full_ids) if full_ids else np.zeros(data.shape, bool)
    flange = np.isin(data, flange_ids) if flange_ids else np.zeros(data.shape, bool)
    return full, flange, {str(k): (v.get("class", "") if isinstance(v, dict) else str(v))
                          for k, v in id2lab.items()}


def save_png(path, arr):
    """PNG 저장 — Isaac 파이썬엔 cv2 가 없을 수 있어 PIL 사용(Isaac 번들에 포함)."""
    from PIL import Image

    Image.fromarray(arr).save(str(path))


def main() -> int:
    args = ARGS
    rng = np.random.default_rng(args.seed)
    rep.orchestrator.set_capture_on_play(False)
    carb.settings.get_settings().set("rtx/post/dlss/execMode", 2)
    rep.set_global_seed(args.seed)

    obj_prim, obj_path, obj_id, z_lift, dome_prim, ground_prims = build_scene(args)
    rig_prim, cams, annots, req_intr = build_rig(args)

    # 씬 randomization / clutter (M2 확장). 옵션을 안 주면 예전과 동일한 최소 씬이다.
    from spatial_vision.stages.scene_random import SceneRandomizer

    args._z_lift = z_lift
    # 타깃의 XY 반경(m) — distractor 겹침 판정과 occluder 오프셋의 기준자. meta.json 실측값을 쓴다.
    meta_p = Path(args.obj_usd).parent / "meta.json"
    TARGET_RADIUS_M = 0.3
    if meta_p.exists():
        bb = json.loads(meta_p.read_text())["meshes"]["full.ply"]["bbox_mm"]
        # ⚠️ 최대 변이 아니라 **XY 외접 반경**이다. 변으로 잡으면 대각선을 놓쳐 사각 물체끼리
        # 모서리가 겹친다(실측: FOUP distractor 가 서로 파고들었다).
        rx = max(abs(bb[0][0]), abs(bb[1][0]))
        ry = max(abs(bb[0][1]), abs(bb[1][1]))
        TARGET_RADIUS_M = math.hypot(rx, ry) / 1000.0
    randomizer = None
    if args.distractors or args.occluders or args.light_fixtures \
       or args.dome_intensity[0] != args.dome_intensity[1] \
       or args.color_temperature_k[0] != args.color_temperature_k[1] \
       or args.hdri or args.ground_material or args.body_material or args.flange_color \
       or args.body_appearance != "random":
        randomizer = SceneRandomizer(args, rng, WORLD, obj_prim, str(Path(args.obj_usd).resolve()))
        randomizer.setup(dome_prim=dome_prim, ground_prims=ground_prims)
        print(f"[capture_sim] randomizer: distractor {args.distractors}"
              f"(FOUP {args.distractor_foups}) / occluder {args.occluders} / 조명 {args.light_fixtures}"
              f" / HDRI {len(randomizer._hdris)} / 재질 바닥={bool(args.ground_material)}"
              f" 몸체={len(randomizer._body_shaders)}")
    b_m = args.baseline_mm / 1000.0

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    # 워밍업: SyntheticData 그래프가 유효한 camera_params 를 낼 때까지.
    # ⚠️ 예산이 30 스텝이면 **콜드 스타트에서 모자란다** — 새 USD 를 처음 여는 실행(셰이더 컴파일·
    # 에셋 로드)에서 실패하고, 같은 명령을 다시 돌리면 캐시가 더워져 통과한다(실측 2026-08-07).
    # 재현성 관점에서 "두 번째부터 된다" 는 고장이므로 넉넉히 잡고, 오래 걸리면 진행 상황을 알린다.
    WARMUP_STEPS = 120
    for i in range(WARMUP_STEPS):
        rep.orchestrator.step(rt_subframes=4, wait_for_render=True)
        if camera_ready(annots):
            if i >= 30:
                print(f"[capture_sim] 워밍업에 {i+1} 스텝 소요 (콜드 스타트)")
            break
        if i and i % 30 == 0:
            print(f"[capture_sim] 워밍업 대기 중… {i}/{WARMUP_STEPS}")
    else:
        print(f"[capture_sim] camera_params 가 {WARMUP_STEPS} 스텝 안에 준비되지 않았다", file=sys.stderr)
        return 1

    target_center = np.array([0.0, 0.0, z_lift])  # 객체 원점(=flange 상면) 위치
    for i in range(args.frames):
        # 객체: 바닥에 놓고 z축(yaw)만 랜덤 — flange 가 보이는 orientation 제약 유지
        yaw = math.radians(float(rng.uniform(-args.yaw_jitter_deg, args.yaw_jitter_deg)))
        c, s = math.cos(yaw), math.sin(yaw)
        Mo = Gf.Matrix4d(1.0)
        Mo.SetRow(0, Gf.Vec4d(c, s, 0, 0)); Mo.SetRow(1, Gf.Vec4d(-s, c, 0, 0))
        Mo.SetRow(2, Gf.Vec4d(0, 0, 1, 0)); Mo.SetRow(3, Gf.Vec4d(0, 0, z_lift, 1))
        set_local_transform(obj_prim, Mo)

        # rig: 객체 중심을 보는 구면 위 한 점 (rig 전체를 통째로 이동 → baseline 보존)
        dist = float(rng.uniform(*args.distance_m))
        el = math.radians(float(rng.uniform(*args.elevation_deg)))
        az = math.radians(float(rng.uniform(*args.azimuth_deg)))
        eye = target_center + np.array([
            dist * math.cos(el) * math.cos(az),
            dist * math.cos(el) * math.sin(az),
            dist * math.sin(el),
        ])
        set_local_transform(rig_prim, look_at_matrix(eye, target_center))

        # ── clutter 배치 + 가림률 프리체크 ────────────────────────────────────
        # 가림을 무작정 걸면 프레임이 통째로 낭비된다(실측: visib 4% 프레임 발생).
        # **싼 렌더(subframe 1)로 먼저 재고** 기준 미달이면 occluder 를 줄여 재시도한 뒤,
        # 통과한 배치로만 본 캡처(subframe N)를 돌린다. semantic 채널은 경로추적 잡음에
        # 둔감하므로 프리체크에 고품질 렌더가 필요 없다.
        rand_state, visib = {}, {"visib_fract": 1.0, "visib_fract_flange": 1.0, "measured": False}
        if randomizer is not None:
            for attempt in range(args.occluder_retries + 1):
                shrink = 0.6 ** attempt
                rand_state = randomizer.randomize(eye, target_center, TARGET_RADIUS_M, shrink)
                if args.no_visib_fract:
                    break
                rep.orchestrator.step(rt_subframes=1, wait_for_render=True)
                f_now, fl_now, _ = masks_from_semantic(
                    annots["left"]["semantic_segmentation"].get_data(), obj_id)
                randomizer.hide_all_clutter()
                rep.orchestrator.step(rt_subframes=1, wait_for_render=True)
                f_un, fl_un, _ = masks_from_semantic(
                    annots["left"]["semantic_segmentation"].get_data(), obj_id)
                randomizer.restore_clutter()
                vf = float(f_now.sum() / max(int(f_un.sum()), 1))
                visib = {"visib_fract": vf,
                         "visib_fract_flange": float(fl_now.sum() / max(int(fl_un.sum()), 1)),
                         "unoccluded_px": int(f_un.sum()), "unoccluded_flange_px": int(fl_un.sum()),
                         "attempts": attempt + 1, "measured": True}
                # 합격 조건: 전체는 적당히 가려도 되지만 **flange 는 온전해야** 한다.
                if vf >= args.min_visib_fract and visib["visib_fract_flange"] >= args.min_flange_visib:
                    break
            else:
                pass

        rep.orchestrator.step(rt_subframes=args.rt_subframes, wait_for_render=True)

        fdir = out_root / f"frame_{i:04d}"
        fdir.mkdir(parents=True, exist_ok=True)
        record = {}
        for name in ("left", "right"):
            a = annots[name]
            cp = a["camera_params"].get_data()
            mpu = float(np.asarray(cp.get("metersPerSceneUnit", 1.0)).reshape(-1)[0])
            res = np.asarray(cp["renderProductResolution"]).reshape(-1)
            w, h = int(res[0]), int(res[1])
            intr = intrinsics_from_params(cp, w, h)
            view_rv = np.asarray(cp["cameraViewTransform"], float).reshape(4, 4)
            T_cam_world = view_rv.T                       # column-vector world→camera
            T_cam_world[:3, 3] *= mpu                     # 스테이지 단위 → m

            rgb = np.asarray(a["rgb"].get_data())[..., :3]
            save_png(fdir / f"{name}.png", rgb.astype(np.uint8))

            depth_m = np.asarray(a["distance_to_image_plane"].get_data(), np.float32)
            depth_m = np.nan_to_num(depth_m, nan=0.0, posinf=0.0, neginf=0.0) * mpu
            record[name] = {"intr": intr, "T_cam_world": T_cam_world, "depth_m": depth_m,
                            "sem": a["semantic_segmentation"].get_data(), "wh": (w, h)}

        L = record["left"]
        w, h = L["wh"]
        # depth GT (좌 기준) — 16bit mm, 0=invalid
        # ⚠️ astype(uint16) 는 **버림**이다 — 그대로 쓰면 depth 가 평균 0.5mm 작게 저장되고,
        #    역투영하면 표면이 카메라 쪽으로 0.5mm 밀린 것처럼 보인다(실측으로 확인). 반드시 반올림.
        depth_mm = np.where(L["depth_m"] > 0, np.rint(L["depth_m"] * 1000.0), 0.0)
        depth_mm = np.clip(depth_mm, 0, 65535).astype(np.uint16)
        save_png(fdir / "depth_gt.png", depth_mm)
        # GT 는 양자화하지 않은 원본도 남긴다. 16-bit PNG(1mm 격자)는 소비 계약용이지만,
        # 평가 기준으로 쓰면 경사면에서 ~0.7mm 급 이산화 오차가 섞인다(실측). 평가는 이 float 를 쓴다.
        np.save(fdir / "depth_gt.npy", (L["depth_m"] * 1000.0).astype(np.float32))

        # disparity GT = fx·B/Z  (rectified 이므로 성립; verify_stereo 가 이 가정을 검사한다)
        with np.errstate(divide="ignore", invalid="ignore"):
            disp = np.where(L["depth_m"] > 0, L["intr"]["fx"] * b_m / L["depth_m"], 0.0)
        np.save(fdir / "disparity_gt.npy", disp.astype(np.float32))

        full, flange, id2lab = masks_from_semantic(L["sem"], obj_id)
        save_png(fdir / "mask_full.png", (full * 255).astype(np.uint8))
        save_png(fdir / "mask_flange.png", (flange * 255).astype(np.uint8))



        # pose GT: cam_T_obj (좌 카메라 기준). USD 원점 = pose frame 이라 추가 변환이 없다.
        obj_rv = np.asarray(rep.functional.utils.get_world_transform(obj_prim).GetMatrix())
        T_world_obj = obj_rv.T                            # column-vector local→world
        T_world_obj[:3, 3] *= mpu
        pose = M_USD_TO_CV @ (L["T_cam_world"] @ T_world_obj)   # BOP/OpenCV 프레임
        pose[:3, :3] = orthonormalize(pose[:3, :3])
        t_mm = pose[:3, 3] * 1000.0

        (fdir / "cam.json").write_text(json.dumps({
            "fx": L["intr"]["fx"], "fy": L["intr"]["fy"],
            "cx": L["intr"]["cx"], "cy": L["intr"]["cy"],
            "baseline_mm": args.baseline_mm, "width": w, "height": h,
        }, indent=2))
        (fdir / "pose_gt.json").write_text(json.dumps({
            "obj_id": obj_id,
            "frame": "cam_T_obj (좌 카메라), BOP/OpenCV 규약 (+X 우, +Y 하, +Z 전방)",
            "origin": "flange 주 상면 중심 (assets/obj/<id>/meta.json 과 동일)",
            "R": pose[:3, :3].tolist(),
            "t_mm": t_mm.tolist(),
            "det_R": float(np.linalg.det(pose[:3, :3])),
        }, indent=2))
        (fdir / "meta_capture.json").write_text(json.dumps({
            "stage": "capture_sim", "backend": "isaac_sim",
            "frame_index": i, "seed": args.seed,
            "requested_intrinsics": req_intr,
            "rendered_intrinsics": L["intr"],
            "baseline_mm": args.baseline_mm,
            "camera_distance_m": dist,
            "elevation_deg": math.degrees(el), "azimuth_deg": math.degrees(az),
            "object_yaw_deg": math.degrees(yaw),
            "T_cam_world_left": L["T_cam_world"].tolist(),  # USD 카메라 프레임(-Z 전방)
            "T_cam_world_right": record["right"]["T_cam_world"].tolist(),
            "right_intrinsics": record["right"]["intr"],
            "semantic_labels": id2lab,
            "mask_px": {"full": int(full.sum()), "flange": int(flange.sum())},
            # ★ 분석용 조건 기록 — depth 오차·pose 오차를 이 값들에 대해 회귀할 수 있어야 한다.
            "visibility": visib,
            "scene": rand_state,
        }, indent=2, ensure_ascii=False))

        vf = visib["visib_fract"]
        extra = ""
        if rand_state:
            extra = (f" | dist{rand_state['distractors']['n_shown']}"
                     f"(foup{rand_state['distractors']['n_foup']})"
                     f" occ{rand_state['occluders']['n_shown']} vis{vf*100:5.1f}%")
        print(f"  frame {i:04d}: d={dist:.2f}m el={math.degrees(el):5.1f}° "
              f"mask full={int(full.sum()):7d} flange={int(flange.sum()):6d} "
              f"depth median={np.median(L['depth_m'][L['depth_m']>0])*1000:.0f}mm "
              f"|t|={np.linalg.norm(t_mm):.0f}mm{extra}")

    rep.orchestrator.wait_until_complete()
    print(f"\n{args.frames} 프레임 → {out_root}")
    return 0


if __name__ == "__main__":
    # ⚠️ Isaac 의 `--/app/fastShutdown=True` 경로가 프로세스를 자체 종료시켜 **SystemExit 이 무시된다**
    # (실측 2026-08-07: 워밍업 실패로 return 1 을 냈는데 셸에는 EXIT=0 이 찍혔다).
    # 실패한 캡처가 성공으로 보고되면 뒤 스테이지가 빈 디렉토리를 정상으로 취급한다 →
    # app 을 닫은 뒤 os._exit 로 **종료 코드를 강제**한다.
    import os
    import traceback

    code = 1
    try:
        code = main()
    except BaseException:
        traceback.print_exc()
        code = 1
    finally:
        try:
            _app.close()
        except Exception:
            pass
        os._exit(code)
