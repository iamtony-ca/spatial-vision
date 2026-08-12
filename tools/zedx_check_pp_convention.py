#!/usr/bin/env python3
"""ZED 의 cx/cy 가 **코너 원점**인지 **OpenCV 픽셀 중심**인지 실측으로 판정한다.

    # Jetson 에서 — pyzed 가 동작하는 **그 인터프리터**로 실행할 것
    python3 tools/zedx_check_pp_convention.py --mode rectify          # ① 오프라인, 카메라만 연결
    python3 tools/zedx_check_pp_convention.py --mode cloud            # ② ①이 판정 불가일 때
    python3 tools/zedx_check_pp_convention.py --mode selftest         # ③ 카메라 없이 API 점검

왜 0.5px 이 문제인가
    코너 원점은 픽셀 k 가 [k, k+1] 을 덮고 중심이 k+0.5, OpenCV 는 픽셀 k 의 중심이 정수 k 다.
    같은 광학중심이 두 규약에서 **정확히 0.5px 다르게** 적힌다. 0.35m 에서 0.481mm/px 이므로
    **0.24mm** 의 계통 편향이다.
    ⚠️ 단 `cx_left == cx_right` 이므로 **시차(depth)에는 영향이 0** 이다. 절대 pose 의 횡방향
       편향만 생기고 hand-eye 를 같은 파이프라인으로 잡으면 대부분 상쇄된다. **급하지 않다.**

판정 원리
    ① rectify — ZED 의 **raw** 캘리브레이션(K,D,R,T)을 `cv2.stereoRectify` 에 넣고 나온 새 cx
                (`P1[0,2]`)와 ZED 의 rectified cx 를 비교한다. OpenCV 출력은 **정의상 OpenCV 규약**이다.
                ⚠️ `alpha` 가 cx·fx 를 동시에 바꾸므로 **fx 가 ZED 와 일치하는 alpha 를 먼저 찾고**
                   그 지점에서 cx 를 비교한다. fx 를 못 맞추면 ZED 가 자체 정류를 쓴다는 뜻 → ②로.
                ⚠️ `stereo_transform` 의 방향(좌→우 / 우→좌)이 SDK 버전마다 다를 수 있어 **양쪽 부호를
                   모두** 시도하고 fx 가 맞는 쪽을 쓴다.
    ② cloud   — SDK 점군은 SDK 자신의 규약으로 역투영된 값이다. `fx·X/Z + cx` 를 **픽셀 인덱스**와
                비교한다. 잔차 중앙값 ≈0.0 → OpenCV / ≈+0.5 → 코너 원점.
                ⚠️ depth 원점이 광학중심에서 상수 d 만큼 밀려 있으면 X/Z 가 왜곡되므로 d 를 함께
                   스캔해 |d| 가 유의하면 경고한다.

환경 (Jetson NX / JetPack 6.x / Python 3.10 기준)
    필요한 것은 **numpy 와 cv2 뿐**이고 둘 다 numpy 1.x·2.x, OpenCV 4.5~5.x 에서 동작하는
    API 만 쓴다(`np.random.default_rng` 는 numpy≥1.17). 제거된 별칭(`np.float` 등)은 안 쓴다.
    🔴 **pip 로 `opencv-python` 을 새로 깔지 말 것** — 최신 휠이 numpy>=2 를 끌어와 pyzed 가
       *"numpy.core.multiarray failed to import"* 로 죽는 사례가 흔하다.
       JetPack 기본 OpenCV(`apt install python3-opencv`)를 그대로 쓰거나, 굳이 pip 라면
       `pip install --no-deps opencv-python-headless` 로 numpy 를 건드리지 않는다.
    → `--mode selftest` 가 카메라 없이 버전과 cv2 경로를 점검한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

VALID_DISTO_LEN = (4, 5, 8, 12, 14)     # cv2 가 받는 길이


# ──────────────────────────────────────────────────────────────── 공통
def verdict(delta: float, what: str) -> str:
    if abs(delta) < 0.15:
        return f"  → {what}: **OpenCV(픽셀 중심)** 규약   (Δ={delta:+.4f})"
    if abs(delta - 0.5) < 0.15:
        return f"  → {what}: **코너 원점** 규약           (Δ={delta:+.4f})"
    if abs(delta + 0.5) < 0.15:
        return f"  → {what}: 코너 원점의 **반대 부호**     (Δ={delta:+.4f}) — 부호 규약 확인 필요"
    return f"  ⚠️ {what}: 판정 불가 (Δ={delta:+.4f}) — 0.0/±0.5 어디에도 안 붙는다"


def env_banner() -> "object":
    import cv2
    print(f"python {sys.version.split()[0]} · numpy {np.__version__} · cv2 {cv2.__version__} "
          f"({getattr(cv2, '__file__', '?')})")
    return cv2


def K_of(c) -> np.ndarray:
    return np.array([[float(c.fx), 0.0, float(c.cx)],
                     [0.0, float(c.fy), float(c.cy)],
                     [0.0, 0.0, 1.0]], dtype=np.float64)


def D_of(c) -> np.ndarray:
    """ZED 의 `disto` → cv2 가 받는 길이 `(n,1)` 로 정규화한다.

    ZED 는 OpenCV 와 **같은 순서**(k1 k2 p1 p2 k3 k4 k5 k6 s1 s2 s3 s4)로 준다.
    🔴 **0 이 아닌 마지막 계수보다 짧게 자르면 안 된다** — 12→5 로 자르면 rational 모델의
       k4~k6 이 사라져 결과가 통째로 달라진다(실측: rectified fx 1050 → 1352).
       그래서 «마지막 nonzero 인덱스를 덮는 가장 짧은 유효 길이» 로만 맞춘다.
    """
    d = np.asarray(c.disto, dtype=np.float64).ravel()
    nz = int(np.nonzero(d)[0].max()) + 1 if np.any(d) else 4
    n = next((k for k in VALID_DISTO_LEN if k >= nz), VALID_DISTO_LEN[-1])
    out = np.zeros((n, 1), dtype=np.float64)
    out[:min(d.size, n), 0] = d[:n]
    return out


def RT_of(cal) -> "tuple":
    """`stereo_transform` → (R 3x3, T **(3,1)**) mm.

    pyzed 버전에 따라 `get_rotation_matrix().r` 이 (3,3) 이기도 (9,) 이기도 하다.
    🔴 **T 는 반드시 (3,1) 열벡터**여야 한다 — `cv2 5.0` 의 `stereoRectify` 는 (3,)/(1,3) 을
       받으면 `gemm` 단언으로 죽는다(4.x 는 통과). 버전 이식성 문제라 여기서 못 박는다.
    """
    tr = cal.stereo_transform
    t = np.asarray(tr.get_translation().get(), dtype=np.float64).ravel()[:3]
    try:
        r = np.asarray(tr.get_rotation_matrix().r, dtype=np.float64)
    except AttributeError:                              # 아주 옛 SDK
        r = np.asarray(tr.m, dtype=np.float64).reshape(4, 4)[:3, :3]
    return np.ascontiguousarray(r.reshape(3, 3)), t.reshape(3, 1)


# ──────────────────────────────────────────────────────────── ① rectify
def rectify_scan(cv2, Kl, Dl, Kr, Dr, R, T, size, target_fx):
    """alpha 를 훑어 ZED 의 fx 와 가장 가까운 지점을 찾는다. T 부호도 양쪽 시도.

    ⚠️ 첫 호출이 실패하면 **조용히 건너뛰지 않고** 예외를 올린다 — 형태 문제를
       *"판정 불가"* 로 오해하면 안 된다(교훈: 틀린 값을 조용히 돌려주는 fallback 금지).
    """
    T = np.asarray(T, dtype=np.float64).reshape(3, 1)
    best, first_err = None, None
    for sign in (1.0, -1.0):
        for alpha in np.linspace(0.0, 1.0, 101):
            try:
                out = cv2.stereoRectify(Kl, Dl, Kr, Dr, size, R, T * sign,
                                        flags=cv2.CALIB_ZERO_DISPARITY,
                                        alpha=float(alpha), newImageSize=size)
            except cv2.error as e:
                first_err = first_err or e
                continue
            P1 = out[2]
            err = abs(float(P1[0, 0]) - target_fx)
            if best is None or err < best[0]:
                best = (err, float(alpha), sign, P1)
    if best is None and first_err is not None:
        raise RuntimeError(
            f"cv2.stereoRectify 가 모든 조합에서 실패했다 (cv2 {cv2.__version__}): {first_err}") \
            from first_err
    return best


def mode_rectify(res_key: str, out_json) -> int:
    cv2 = env_banner()
    import pyzed.sl as sl

    z = sl.Camera()
    p = sl.InitParameters()
    p.camera_resolution = getattr(sl.RESOLUTION, res_key)
    p.depth_mode = sl.DEPTH_MODE.NONE
    st = z.open(p)
    if st != sl.ERROR_CODE.SUCCESS:
        print(f"❌ 카메라 open 실패: {st}", file=sys.stderr)
        return 2
    cc = z.get_camera_information().camera_configuration
    W, H = int(cc.resolution.width), int(cc.resolution.height)
    raw, rect = cc.calibration_parameters_raw, cc.calibration_parameters
    Kl, Dl = K_of(raw.left_cam), D_of(raw.left_cam)
    Kr, Dr = K_of(raw.right_cam), D_of(raw.right_cam)
    R, T = RT_of(raw)
    zfx, zcx, zcy = float(rect.left_cam.fx), float(rect.left_cam.cx), float(rect.left_cam.cy)
    z.close()

    print(f"해상도 {W}x{H} · raw disto {Dl.size}개 · T {np.round(T, 3).tolist()}")
    best = rectify_scan(cv2, Kl, Dl, Kr, Dr, R, T, (W, H), zfx)
    if best is None:
        print("❌ stereoRectify 가 전부 실패했다 — 입력 형태 문제. --mode selftest 먼저 확인.",
              file=sys.stderr)
        return 2
    err, alpha, sign, P1 = best
    print(f"ZED  rectified    fx {zfx:12.5f}  cx {zcx:11.5f}  cy {zcy:11.5f}")
    print(f"cv2.stereoRectify fx {P1[0,0]:12.5f}  cx {P1[0,2]:11.5f}  cy {P1[1,2]:11.5f}"
          f"   (alpha={alpha:.2f}, T부호={sign:+.0f})")
    res = {"width": W, "height": H, "zed": {"fx": zfx, "cx": zcx, "cy": zcy},
           "cv2": {"fx": float(P1[0, 0]), "cx": float(P1[0, 2]), "cy": float(P1[1, 2])},
           "alpha": alpha, "t_sign": sign, "fx_err": err}
    if err > 2.0:
        print(f"⚠️ fx 를 {err:.2f}px 이내로 못 맞췄다 → ZED 가 자체 정류를 쓴다."
              f" 이 모드로는 판정 불가. **--mode cloud** 를 쓸 것.")
        res["verdict"] = "inconclusive"
    else:
        print(verdict(zcx - float(P1[0, 2]), "cx"))
        print(verdict(zcy - float(P1[1, 2]), "cy"))
        res["d_cx"] = zcx - float(P1[0, 2])
        res["d_cy"] = zcy - float(P1[1, 2])
    if out_json:
        Path(out_json).write_text(json.dumps(res, indent=2))
        print(f"→ {out_json}")
    return 0


# ────────────────────────────────────────────────────────────── ② cloud
def mode_cloud(res_key: str, n_frames: int, zmin: float, zmax: float,
               depth_mode: str, out_json) -> int:
    env_banner()
    import pyzed.sl as sl

    z = sl.Camera()
    p = sl.InitParameters()
    p.camera_resolution = getattr(sl.RESOLUTION, res_key)
    for name in (depth_mode, "NEURAL", "ULTRA", "PERFORMANCE"):
        if hasattr(sl.DEPTH_MODE, name):
            p.depth_mode = getattr(sl.DEPTH_MODE, name)
            print(f"depth_mode = {name}")
            break
    p.coordinate_units = sl.UNIT.MILLIMETER
    p.coordinate_system = sl.COORDINATE_SYSTEM.IMAGE       # X→우, Y→하, Z→전방 (OpenCV/BOP)
    st = z.open(p)
    if st != sl.ERROR_CODE.SUCCESS:
        print(f"❌ 카메라 open 실패: {st}", file=sys.stderr)
        return 2
    cc = z.get_camera_information().camera_configuration
    c = cc.calibration_parameters.left_cam
    fx, fy, cx, cy = float(c.fx), float(c.fy), float(c.cx), float(c.cy)
    W, H = int(cc.resolution.width), int(cc.resolution.height)
    uu, vv = np.meshgrid(np.arange(W, dtype=np.float64), np.arange(H, dtype=np.float64))
    uu, vv = uu.ravel(), vv.ravel()
    rng = np.random.default_rng(0)

    US, VS, XS, YS, ZS = [], [], [], [], []
    m = sl.Mat()
    got, tries = 0, 0
    while got < n_frames and tries < n_frames * 20:
        tries += 1
        if z.grab() != sl.ERROR_CODE.SUCCESS:
            continue
        z.retrieve_measure(m, sl.MEASURE.XYZ)
        a = np.asarray(m.get_data(), dtype=np.float64)
        X, Y, Z = a[:, :, 0], a[:, :, 1], a[:, :, 2]
        ok = np.isfinite(X) & np.isfinite(Y) & np.isfinite(Z) & (Z > zmin) & (Z < zmax)
        ok[:H // 8, :] = False                              # 가장자리는 정류 보간 오차가 크다
        ok[H - H // 8:, :] = False
        ok[:, :W // 8] = False
        ok[:, W - W // 8:] = False
        idx = np.flatnonzero(ok.ravel())
        if idx.size < 5000:
            continue
        idx = rng.choice(idx, size=min(40000, idx.size), replace=False)
        US.append(uu[idx]); VS.append(vv[idx])
        XS.append(X.ravel()[idx]); YS.append(Y.ravel()[idx]); ZS.append(Z.ravel()[idx])
        got += 1
    z.close()
    if not got:
        print("❌ 유효 depth 프레임을 못 얻었다 — 텍스처 있는 장면을 0.5~2m 에 두고 다시.",
              file=sys.stderr)
        return 2

    u, v = np.concatenate(US), np.concatenate(VS)
    X, Y, Z = np.concatenate(XS), np.concatenate(YS), np.concatenate(ZS)
    ru = fx * X / Z + cx - u
    rv = fy * Y / Z + cy - v
    iqr = lambda a: float(np.percentile(a, 75) - np.percentile(a, 25))   # noqa: E731
    print(f"프레임 {got} · 표본 {u.size:,} · Z {Z.min():.0f}~{Z.max():.0f}mm")
    print(f"잔차 u  중앙 {np.median(ru):+.4f}  IQR {iqr(ru):.4f}")
    print(f"잔차 v  중앙 {np.median(rv):+.4f}  IQR {iqr(rv):.4f}")

    # depth 원점 오프셋 d 스캔 — |d| 가 유의하면 위 잔차가 오염된 것이다
    ds = np.arange(-60.0, 60.1, 2.0)
    spread = [iqr(fx * X / (Z - d) + cx - u) for d in ds]
    d_hat = float(ds[int(np.argmin(spread))])
    if abs(d_hat) > 6.0:
        print(f"⚠️ depth 원점 오프셋 d≈{d_hat:+.0f}mm 로 추정된다 — 잔차가 오염됐을 수 있다."
              f" --mode rectify 결과와 대조할 것.")
    print(verdict(float(np.median(ru)), "cx"))
    print(verdict(float(np.median(rv)), "cy"))
    if out_json:
        Path(out_json).write_text(json.dumps(
            {"frames": got, "n": int(u.size), "med_ru": float(np.median(ru)),
             "med_rv": float(np.median(rv)), "iqr_ru": iqr(ru), "iqr_rv": iqr(rv),
             "d_hat_mm": d_hat}, indent=2))
        print(f"→ {out_json}")
    return 0


# ─────────────────────────────────────────────────────────── ③ selftest
def mode_selftest() -> int:
    """카메라 없이 numpy/cv2 조합과 stereoRectify 경로를 점검한다."""
    cv2 = env_banner()
    W, H = 1920, 1200

    class C:                                             # pyzed 흉내
        def __init__(s, fx, fy, cx, cy, d):
            s.fx, s.fy, s.cx, s.cy, s.disto = fx, fy, cx, cy, d

    disto = [0.542747974, 0.132935002, 0.000296656013, -0.000293377991,
             -0.0239220001, 0.536751986, 0.206857994, -0.0316627994, 0, 0, 0, 0]
    left, right = C(1050.0, 1050.0, 965.0, 601.0, disto), C(1051.0, 1051.0, 958.0, 607.0, disto)
    Kl, Dl, Kr, Dr = K_of(left), D_of(left), K_of(right), D_of(right)
    R = cv2.Rodrigues(np.array([0.001, -0.002, 0.0005]))[0]
    T = np.array([120.201996, 0.3, -0.2]).reshape(3, 1)
    print(f"disto {Dl.size}개(shape {Dl.shape}) · T shape {T.shape} · dtype {Kl.dtype}")
    d5 = D_of(C(0, 0, 0, 0, disto[:5] + [0] * 7))
    assert d5.size == 5, f"0 꼬리 절단 실패: {d5.size}"
    assert Dl.size == 8, f"nonzero 를 덮는 최소 길이가 아니다: {Dl.size}"

    # ⚠️ 임의의 target 을 주면 err 가 커서 «판정 불가» 분기만 타게 된다.
    #    중간 alpha 의 실제 fx 를 target 으로 되먹여 «판정 가능» 분기도 실행시킨다.
    probe = cv2.stereoRectify(Kl, Dl, Kr, Dr, (W, H), R, T,
                              flags=cv2.CALIB_ZERO_DISPARITY, alpha=0.5, newImageSize=(W, H))
    best = rectify_scan(cv2, Kl, Dl, Kr, Dr, R, T, (W, H), float(probe[2][0, 0]))
    assert best is not None, "stereoRectify 가 전부 실패"
    err, alpha, sign, P1 = best
    assert err < 2.0, f"fx 매칭 실패 err={err}"
    print(f"stereoRectify OK → fx {P1[0,0]:.3f} cx {P1[0,2]:.3f} cy {P1[1,2]:.3f} "
          f"(alpha {alpha:.2f}, T부호 {sign:+.0f}, fx오차 {err:.3g})")

    # verdict / 잔차 계산 경로
    for d, lab in ((0.0, "OpenCV"), (0.5, "코너")):
        assert lab[:2] in verdict(d, "cx"), verdict(d, "cx")
    Z = np.linspace(400, 2000, 5000); X = np.linspace(-300, 300, 5000)
    u = 727.5751343 * X / Z + 960.49988
    ru = 727.5751343 * X / Z + 960.49988 - u
    assert abs(float(np.median(ru))) < 1e-9
    _ = [float(np.percentile(ru, 75) - np.percentile(ru, 25))]
    print("✅ selftest 통과 — 이 환경에서 rectify/cloud 계산 경로가 모두 동작한다")
    print("   (남은 것은 pyzed import 뿐 — pyzed 가 되는 인터프리터로 실행할 것)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ZED cx/cy 반픽셀 규약 판정")
    ap.add_argument("--mode", default="rectify", choices=["rectify", "cloud", "selftest"])
    ap.add_argument("--resolution", default="HD1200")
    ap.add_argument("--depth-mode", default="NEURAL", help="cloud 모드 전용. 없으면 자동 하향")
    ap.add_argument("--frames", type=int, default=3)
    ap.add_argument("--zmin", type=float, default=300.0)
    ap.add_argument("--zmax", type=float, default=3000.0)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args(argv)
    if a.mode == "selftest":
        return mode_selftest()
    if a.mode == "rectify":
        return mode_rectify(a.resolution, a.json_out)
    return mode_cloud(a.resolution, a.frames, a.zmin, a.zmax, a.depth_mode, a.json_out)


if __name__ == "__main__":
    raise SystemExit(main())
