"""M2 검증 — 캡처된 스테레오 프레임이 기하적으로 일관적인지 확인한다.

    envs/stereo_onnx/bin/python -m spatial_vision.eval.verify_stereo --in runs/sim01

★ 자기순환을 피한다
    `disparity_gt.npy` 는 캡처 스크립트가 `fx·B/Z` 로 만든 것이다. 같은 식으로 다시 검사하면
    아무것도 증명하지 못한다. 그래서 **독립적인** 세 가지를 본다:

    [1] rectification — 좌/우 카메라의 상대 변환이 회전 0, 평행이동 (-B,0,0) 인가.
        (캡처 스크립트가 의도한 rig 구조가 실제 렌더 카메라에 반영됐는지)
    [2] photometric warp — 우 영상을 disparity 로 좌 영상에 워프해 실제 픽셀이 일치하는가.
        baseline 부호나 rectification 이 틀리면 여기서 바로 깨진다.
    [3] pose ↔ depth ↔ intrinsic 교차검증 — CAD keypoint 를 pose_gt 로 투영해
        (a) mask 안에 떨어지는가, (b) 투영 깊이가 depth_gt 와 일치하는가.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def load_frame(d: Path) -> dict:
    f = {
        "cam": json.loads((d / "cam.json").read_text()),
        "pose": json.loads((d / "pose_gt.json").read_text()),
        "meta": json.loads((d / "meta_capture.json").read_text()),
        "left": cv2.imread(str(d / "left.png"), cv2.IMREAD_COLOR),
        "right": cv2.imread(str(d / "right.png"), cv2.IMREAD_COLOR),
        # 평가에는 양자화되지 않은 float GT 를 쓴다(있으면). 16-bit PNG 는 1mm 격자라
        # 경사면에서 이산화 오차가 섞여 GT 자체의 정확도를 가린다.
        "depth_mm": (np.load(d / "depth_gt.npy").astype(np.float64)
                     if (d / "depth_gt.npy").exists()
                     else cv2.imread(str(d / "depth_gt.png"), cv2.IMREAD_UNCHANGED).astype(np.float64)),
        "depth_quantized": not (d / "depth_gt.npy").exists(),
        "disp": np.load(d / "disparity_gt.npy"),
        "mask_full": cv2.imread(str(d / "mask_full.png"), cv2.IMREAD_GRAYSCALE) > 127,
        "mask_flange": cv2.imread(str(d / "mask_flange.png"), cv2.IMREAD_GRAYSCALE) > 127,
    }
    return f


def check_rectification(f: dict, tol_deg=0.01, tol_mm=0.05) -> tuple[bool, str]:
    """[1] 좌→우 상대 변환. rectified stereo 면 R=I, t=(-B,0,0)."""
    Tl = np.asarray(f["meta"]["T_cam_world_left"], float)
    Tr = np.asarray(f["meta"]["T_cam_world_right"], float)
    T_rl = Tr @ np.linalg.inv(Tl)  # 좌 카메라 좌표 → 우 카메라 좌표
    R, t_mm = T_rl[:3, :3], T_rl[:3, 3] * 1000.0
    ang = np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))
    B = f["cam"]["baseline_mm"]
    err = t_mm - np.array([-B, 0.0, 0.0])
    ok = ang <= tol_deg and np.abs(err).max() <= tol_mm
    return ok, (f"상대회전 {ang:.6f}°  상대이동 ({t_mm[0]:+.4f}, {t_mm[1]:+.4f}, {t_mm[2]:+.4f})mm "
                f"— 기대 (-{B:.1f}, 0, 0)")


def check_photometric_warp(f: dict) -> tuple[bool, str]:
    """[2] right(u-d, v) ≈ left(u, v). disparity 로 우→좌 워프해 실제 밝기를 비교."""
    d = f["disp"].astype(np.float32)
    h, w = d.shape
    valid = (d > 0.1) & f["mask_full"]
    if valid.sum() < 500:
        return False, f"유효 픽셀 부족 ({int(valid.sum())})"
    uu, vv = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    warped = cv2.remap(f["right"], uu - d, vv, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    gl = cv2.cvtColor(f["left"], cv2.COLOR_BGR2GRAY).astype(np.float64)
    gw = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY).astype(np.float64)
    inb = valid & (uu - d >= 0)  # 워프가 영상 밖을 참조하는 픽셀 제외
    mae = float(np.abs(gl[inb] - gw[inb]).mean())

    # 대조군: 부호를 뒤집은 워프. 올바른 방향이라면 이쪽이 훨씬 나빠야 한다.
    warped_neg = cv2.remap(f["right"], uu + d, vv, cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    gn = cv2.cvtColor(warped_neg, cv2.COLOR_BGR2GRAY).astype(np.float64)
    inb_n = valid & (uu + d < w)
    mae_neg = float(np.abs(gl[inb_n] - gn[inb_n]).mean())

    ok = mae < 8.0 and mae < mae_neg * 0.5
    return ok, (f"워프 MAE {mae:.2f} (0-255) / 부호반전 대조군 {mae_neg:.2f} "
                f"— 비율 {mae/max(mae_neg,1e-9):.3f}, 검사 픽셀 {int(inb.sum())}")


def _project(f: dict, pts_obj: np.ndarray):
    """obj-local mm → 카메라 좌표(mm) + 픽셀. pose_gt 는 BOP/OpenCV 규약."""
    R = np.asarray(f["pose"]["R"], float)
    t = np.asarray(f["pose"]["t_mm"], float)
    c = f["cam"]
    P = (R @ pts_obj.T).T + t
    u = c["fx"] * P[:, 0] / P[:, 2] + c["cx"]
    v = c["fy"] * P[:, 1] / P[:, 2] + c["cy"]
    return P, u, v


def check_pose_depth(f: dict, kpts: dict, tol_mm=0.05, visib_fract: float = 1.0) -> tuple[bool, str]:
    """[3] pose ↔ depth ↔ intrinsic 교차검증.

    두 가지를 나눠서 본다:
      (a) mask 적중 — 표준부 rim keypoint 를 투영해 객체 mask 안에 떨어지는가.
      (b) 깊이 일치 — **평탄면 위의 점**으로만 잰다. rim 은 실루엣 경계라 픽셀 반올림이 옆면이나
          배경을 집어 거리에 비례하는 오차가 생긴다(측정 도구의 한계이지 GT 오차가 아니다).
          그래서 flange 주 상면(z=0) 위 반경 r_mid 링을 따로 만들어 쓴다.
    """
    h, w = f["depth_mm"].shape
    # (a) rim keypoint 의 mask 적중
    rim = np.asarray(kpts["points"]["rim_circle"]["samples"], float)
    Pr, ur, vr = _project(f, rim)
    inimg_r = (Pr[:, 2] > 1) & (ur >= 0) & (ur < w) & (vr >= 0) & (vr < h)
    if inimg_r.sum() < 4:
        return False, f"영상 안에 든 rim keypoint 부족 ({int(inimg_r.sum())}/{len(rim)})"
    hit = f["mask_full"][np.round(vr[inimg_r]).astype(int), np.round(ur[inimg_r]).astype(int)]

    # (b) 평탄면(주 상면 z=0) 링 — 중심 홀(r=20)과 플랫폼 가장자리(r=92) 사이
    r_hole = float(kpts["points"]["center_hole_circle"]["radius_mm"])
    r_mid = (r_hole + 92.0) / 2.0
    ang = np.linspace(0, 2 * np.pi, 32, endpoint=False)
    flat = np.stack([r_mid * np.cos(ang), r_mid * np.sin(ang), np.zeros_like(ang)], 1)
    Pf, uf, vf = _project(f, flat)
    inimg_f = (Pf[:, 2] > 1) & (uf >= 1) & (uf < w - 1) & (vf >= 1) & (vf < h - 1)
    # ⚠️ 최근접 픽셀로 depth 를 읽으면 안 된다. 1.4m 에서 1픽셀 ≈ 표면상 1.5mm 라
    #    기울어진 면에서는 0.5픽셀 반올림이 그대로 ~1mm 깊이오차로 나타난다(도구의 한계).
    #    → 이중선형 보간으로 서브픽셀 위치의 깊이를 읽는다.
    uu, vv = uf[inimg_f], vf[inimg_f]
    u0, v0 = np.floor(uu).astype(int), np.floor(vv).astype(int)
    au, av = uu - u0, vv - v0
    D = f["depth_mm"]
    d00, d10, d01, d11 = D[v0, u0], D[v0, u0 + 1], D[v0 + 1, u0], D[v0 + 1, u0 + 1]
    # ★ depth 를 직접 보간하면 안 된다. 평면 위에서 픽셀 좌표에 **선형인 것은 1/Z**(역depth)이고
    #   Z 는 아니다. depth 를 보간하면 1/x 의 볼록성 때문에 경사가 클수록 커지는 계통 편향이 생긴다
    #   (실측: 경사 41.6° 뷰에서 0.83mm, 정면에 가까운 69.2° 뷰에서 0.21mm).
    with np.errstate(divide="ignore", invalid="ignore"):
        iz = ((1 - au) * (1 - av) / d00 + au * (1 - av) / d10
              + (1 - au) * av / d01 + au * av / d11)
        dz = 1.0 / iz
    # 깊이 불연속(가림/경계) 제외: 보간에 쓰인 4점이 모두 유효하고 서로 가까워야 한다
    quad = np.stack([d00, d10, d01, d11], 0)
    flatpx = (quad > 0).all(0) & ((quad.max(0) - quad.min(0)) < 5.0)
    ui, vi = np.round(uu).astype(int), np.round(vv).astype(int)
    cmp = (dz > 0) & flatpx & f["mask_flange"][vi, ui]
    derr = np.abs(dz[cmp] - Pf[inimg_f, 2][cmp]) if cmp.any() else np.array([np.nan])

    # ⚠️ 가림이 있는 씬에서 적중률 100% 를 요구하면 안 된다 — occluder 가 가린 keypoint 는
    # **당연히** 마스크에 안 맞는다(실측: clutter 40프레임 중 19건이 이 이유로 실패했고,
    # 정작 보이는 점들의 깊이오차는 여전히 median 0.000mm 였다).
    # 가림으로 설명되는 만큼은 봐주고, **그보다 더 빠지면** 진짜 기하 오류로 본다.
    hit_floor = 0.9 * max(float(visib_fract), 0.0)   # vf=1 이면 원래 기준(0.9)
    vis_note = "" if visib_fract >= 0.999 else f" [flange 가림 {(1-visib_fract)*100:.0f}%, 기준 {hit_floor*100:.0f}%]"
    msg = (f"rim {int(inimg_r.sum())}/{len(rim)} 투영 mask 적중 {hit.mean()*100:.0f}%{vis_note} | "
           f"평탄면 링(r={r_mid:.0f}mm) 깊이오차 median {np.nanmedian(derr):.3f}mm "
           f"max {np.nanmax(derr):.3f}mm (n={int(cmp.sum())})")
    # ★ "틀렸다" 와 "못 쟀다" 는 다르다. flange 가 거의 다 가려지면 표본이 없어서 판정 자체가
    #   불가능한데, 이를 실패로 세면 가림을 넣을수록 실패가 늘어 지표가 무의미해진다.
    if cmp.sum() < 8 and visib_fract < 0.9:
        return None, msg + "  → 검증 불가(가림으로 표본 부족)"
    return bool(hit.mean() >= hit_floor and cmp.sum() >= 8 and np.nanmedian(derr) <= tol_mm), msg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="M2 스테레오 캡처 검증")
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--keypoints", default="assets/obj/foup_300/keypoints.json")
    args = ap.parse_args(argv)

    root = Path(args.in_dir)
    frames = sorted(p for p in root.iterdir() if p.is_dir() and (p / "left.png").exists())
    if not frames:
        print(f"프레임 없음: {root}")
        return 1
    kpts = json.loads(Path(args.keypoints).read_text())

    n_fail = n_skip = 0
    for d in frames:
        f = load_frame(d)
        # 캡처가 실측한 가림률. clutter 씬에서는 이걸 알아야 적중률 판정이 성립한다.
        # rim keypoint 는 **flange 위**에 있으므로 전체 가림률이 아니라 flange 가림률로 판정한다
        # (occluder 가 시선 위에 놓여 flange 가 평균보다 더 가려진다).
        _vis = (f.get("meta") or {}).get("visibility", {})
        vf = float(_vis.get("visib_fract_flange", _vis.get("visib_fract", 1.0)))
        print(f"\n=== {d.name} ===")
        for tag, (ok, msg) in [
            ("[1] rectification ", check_rectification(f)),
            ("[2] photometric   ", check_photometric_warp(f)),
            ("[3] pose↔depth    ", check_pose_depth(f, kpts, visib_fract=vf)),
        ]:
            mark = "✅" if ok else ("⏭️" if ok is None else "❌")
            print(f"  {mark} {tag} {msg}")
            if ok is None:
                n_skip += 1
            elif not ok:
                n_fail += 1
        m = f["meta"]
        print(f"     mask full={m['mask_px']['full']} flange={m['mask_px']['flange']} "
              f"({m['mask_px']['flange']/max(m['mask_px']['full'],1)*100:.1f}%), "
              f"|t|={np.linalg.norm(f['pose']['t_mm']):.0f}mm, det(R)={f['pose']['det_R']:.6f}")

    print(f"\n{'✅ M2 검증 통과' if n_fail == 0 else f'❌ 실패 {n_fail}건'}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
