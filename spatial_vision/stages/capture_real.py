"""M6 — 실카메라 캡처 스테이지 (ZED X · Jetson).

    # Jetson 에서 — pyzed 가 동작하는 **그 인터프리터**로
    python3 -m spatial_vision.stages.capture_real \
        --out runs/real01_near --cam assets/cam/zedx_s48560070_hd1200.json --frames 5

파이프라인이 실제로 요구하는 입력은 **셋뿐**이다 — `left.png` · `right.png` · `cam.json`.
`depth_gt.npy` · `mask_*.png` · `pose_gt.json` 은 **sim GT 전용**이라 실물에는 없다
(그래서 실환경에서는 `eval_*` 를 못 돌린다 — 서열화는 GT-free 지표로만 한다).

🔴 반드시 지키는 것 (전부 실측으로 확정된 제약이다)
    1. **rectified 만 쓴다** — `sl.VIEW.LEFT` / `sl.VIEW.RIGHT`. `*_UNRECTIFIED` 는 왜곡이 살아 있어
       (`k1 0.543`) 왜곡항 없는 `cam.json` 과 안 맞는다. rectified 의 `disto` 는 전부 0 이고,
       그래서 우리 sim 의 핀홀 모델과 **동형**이 된다.
    2. **PNG 무손실 · BGR8** — JPEG 아티팩트가 서브픽셀 기울기 정합(`refine_contour`)을 먹는다.
       ZED 는 BGRA 로 주므로 알파를 버린다.
    3. **`cam.json` 은 «지금 이 카메라» 의 rectified 캘리브레이션**을 쓴다. 프로파일은 대조용이다 —
       해상도 모드나 개체가 바뀌면 즉시 드러난다(`--cam` 을 주면 자동 대조).
    4. **해상도 모드를 바꾸지 않는다.** 바꾸면 캘리브레이션·SAM3 참조가 **전부 무효**다(참조는 거리+조건 종속).
    5. **`DEPTH_MODE.NONE`** — SDK depth 를 안 쓴다(FoundationStereo 로 직접 만든다). Jetson 부담 제거.

⚠️ `cx/cy` 규약
    여기 쓰는 값은 **ZED SDK 가 준 그대로**이고 우리 계약은 OpenCV(픽셀 중심)다.
    `capture_sim --cx/--cy` **만** 코너 원점이라 +0.5 가 필요하다(횡단 정리 #1).
    ZED 가 어느 규약인지는 `tools/zedx_check_pp_convention.py` 로 판정한다(차이 0.5px = 근접 0.24mm,
    `cx_left == cx_right` 라 **depth 에는 영향 0**).

⚠️ AE 수렴
    실카메라 AE 는 수렴 동역학이 있고 우리는 그걸 모델링한 적이 없다(`RESULTS.md §33` 한계).
    `--warmup` 프레임을 버려 안정된 뒤에 저장하고, **프레임별 노출·게인을 meta 에 남긴다.**

환경 (Jetson NX / JetPack 6.x / Python 3.10)
    `pyzed` · `numpy` 만 필수다(**repo import 0 — 이 파일 하나만 Jetson 에 복사해도 돌아간다**).
    `cv2` 는 있으면 쓰고 없으면 ZED SDK 로 저장한다. 🔴 pip 로 `opencv-python` 을 새로 깔지 말 것 —
    numpy>=2 를 끌어와 pyzed 가 죽는 사례가 흔하다(`apt install python3-opencv` 또는 `--no-deps`).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

# 프로파일/계약과 같은 키 순서를 쓴다 (contracts.CameraParams 와 동일 필드)
CAM_KEYS = ("fx", "fy", "cx", "cy", "baseline_mm", "width", "height")


def cam_from_sdk(cc) -> dict:
    """`camera_configuration` → 우리 `cam.json` (rectified·OpenCV 규약)."""
    c = cc.calibration_parameters.left_cam
    return {
        "fx": float(c.fx), "fy": float(c.fy), "cx": float(c.cx), "cy": float(c.cy),
        "baseline_mm": float(cc.calibration_parameters.get_camera_baseline()),
        "width": int(cc.resolution.width), "height": int(cc.resolution.height),
    }


def check_profile(live: dict, prof_path: str, tol_px: float, tol_mm: float) -> int:
    """프로파일과 대조한다. **틀리면 조용히 넘어가지 않고 실패시킨다.**

    해상도 모드를 바꾸거나 개체가 바뀌면 SAM3 참조·ISM 템플릿이 전부 무효인데,
    그건 산출물을 봐서는 안 보이고 pose 정확도로만 드러난다 — 여기서 잡는다.
    """
    # 🔴 `encoding="utf-8"` 을 반드시 준다. 안 주면 **로케일 기본 인코딩**으로 읽는데
    #    Jetson 은 보통 `LANG` 이 안 잡혀 있어 ASCII 가 되고, 프로파일 주석의 한글에서
    #    `UnicodeDecodeError: 'ascii' codec can't decode byte 0xeb` 로 죽는다(실측 2026-08-12).
    prof = json.loads(Path(prof_path).read_text(encoding="utf-8"))
    bad = []
    for k in ("width", "height"):
        if int(prof[k]) != int(live[k]):
            bad.append(f"{k}: 프로파일 {prof[k]} vs 실측 {live[k]}")
    for k, tol in (("fx", tol_px), ("fy", tol_px), ("cx", tol_px), ("cy", tol_px),
                   ("baseline_mm", tol_mm)):
        d = abs(float(prof[k]) - float(live[k]))
        if d > tol:
            bad.append(f"{k}: 프로파일 {prof[k]:.4f} vs 실측 {live[k]:.4f}  (Δ{d:.4f})")
    if bad:
        print("❌ 카메라 프로파일과 실측 캘리브레이션이 다르다:", file=sys.stderr)
        for b in bad:
            print(f"    {b}", file=sys.stderr)
        print("   해상도 모드나 카메라 개체가 바뀌었다면 **SAM3 참조·ISM 템플릿이 무효**다.\n"
              "   의도한 변경이면 프로파일을 갱신하고 참조를 재생성할 것 (--no-check 로 건너뛸 수 있다).",
              file=sys.stderr)
        return 1
    print(f"✅ 프로파일 일치 ({prof.get('id', prof_path)})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="실카메라(ZED X) 캡처 — left/right/cam.json 만 낸다")
    ap.add_argument("--out", required=True, help="출력 디렉토리 (frame_XXXX 가 생긴다)")
    ap.add_argument("--cam", default=None,
                    help="assets/cam/<id>.json — 대조용. 어긋나면 실패한다")
    ap.add_argument("--no-check", action="store_true", help="프로파일 대조를 건너뛴다")
    ap.add_argument("--frames", type=int, default=1, help="저장할 프레임 수")
    ap.add_argument("--interval-s", type=float, default=0.0, help="프레임 간 간격 (0=최대속도)")
    ap.add_argument("--warmup", type=int, default=15,
                    help="버릴 프레임 수. **AE 수렴에 필요하다** — 0 으로 두면 첫 장이 어둡거나 날아간다")
    ap.add_argument("--on-key", action="store_true",
                    help="Enter 를 칠 때마다 1장 저장 (자세를 손으로 바꿔가며 찍을 때)")
    ap.add_argument("--resolution", default="HD1200", help="⚠️ 바꾸면 참조 자산이 전부 무효다")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--start-index", type=int, default=0, help="frame_XXXX 시작 번호")
    # 노출 — 기본은 AE. 고정하려면 둘 다 준다
    ap.add_argument("--exposure", type=int, default=None, help="0~100 (미지정=AE)")
    ap.add_argument("--gain", type=int, default=None, help="0~100 (미지정=AE)")
    ap.add_argument("--note", default=None, help="meta 에 남길 메모 (거리·조명·자세 등)")
    a = ap.parse_args(argv)

    # 🔴 Jetson 은 `LANG` 이 안 잡혀 있는 일이 흔하고, 그러면 파이썬의 기본 인코딩이 ASCII 가 된다
    #    (PEP 538 의 C 로케일 강제 변환도 항상 걸리지는 않는다). 이 파일은 한글 문자열을 찍으므로
    #    **표준출력이 ASCII 면 `UnicodeEncodeError` 로 죽는다.** 파일 IO 는 각 호출에서
    #    `encoding="utf-8"` 로 못박았고, 출력은 여기서 한 번 고정한다.
    #    (환경변수로 미리 막으려면 `PYTHONUTF8=1` 또는 `LANG=C.UTF-8`.)
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    import pyzed.sl as sl
    # cv2 는 **있으면 쓰고 없으면 SDK 로 저장**한다. Jetson 에 `pip install opencv-python` 을
    # 하면 numpy>=2 를 끌어와 pyzed 가 죽는다 — 그걸 하느니 SDK 저장이 낫다.
    # ⚠️ SDK 경로는 BGRA(4채널) PNG 를 쓴다. 하류는 `IMREAD_COLOR`/`IMREAD_GRAYSCALE` 로 읽어
    #    알파를 버리므로 무해하지만, **무손실 PNG 라는 계약은 양쪽 다 지킨다.**
    try:
        import cv2
    except ImportError:
        cv2 = None

    print(f"python {sys.version.split()[0]} · numpy {np.__version__} · "
          f"cv2 {cv2.__version__ if cv2 else '없음 → ZED SDK 로 저장(BGRA PNG)'}")
    z = sl.Camera()
    p = sl.InitParameters()
    if not hasattr(sl.RESOLUTION, a.resolution):
        print(f"❌ 알 수 없는 해상도 {a.resolution}", file=sys.stderr)
        return 2
    p.camera_resolution = getattr(sl.RESOLUTION, a.resolution)
    p.camera_fps = a.fps
    p.depth_mode = sl.DEPTH_MODE.NONE                  # SDK depth 안 쓴다
    st = z.open(p)
    if st != sl.ERROR_CODE.SUCCESS:
        print(f"❌ 카메라 open 실패: {st}", file=sys.stderr)
        return 2

    info = z.get_camera_information()
    cc = info.camera_configuration
    live = cam_from_sdk(cc)
    print(f"ZED S/N {info.serial_number} · FW {getattr(info, 'camera_firmware_version', '?')} · "
          f"{live['width']}x{live['height']} @{a.fps} · rectified")
    print(f"  fx {live['fx']:.4f} · cx {live['cx']:.4f} · cy {live['cy']:.4f} · B {live['baseline_mm']:.4f}mm")
    if a.cam and not a.no_check:
        if check_profile(live, a.cam, tol_px=0.5, tol_mm=0.5):
            z.close()
            return 1

    if a.exposure is not None or a.gain is not None:
        z.set_camera_settings(sl.VIDEO_SETTINGS.AEC_AGC, 0)
        if a.exposure is not None:
            z.set_camera_settings(sl.VIDEO_SETTINGS.EXPOSURE, int(a.exposure))
        if a.gain is not None:
            z.set_camera_settings(sl.VIDEO_SETTINGS.GAIN, int(a.gain))
        print(f"  노출 고정: exposure={a.exposure} gain={a.gain}")
    else:
        z.set_camera_settings(sl.VIDEO_SETTINGS.AEC_AGC, 1)
        print("  노출: AE (프레임별 값을 meta 에 기록한다)")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    L, R = sl.Mat(), sl.Mat()
    rt = sl.RuntimeParameters()

    # ⚠️ AE 수렴용 워밍업 — 버리는 프레임이다
    for _ in range(max(0, a.warmup)):
        z.grab(rt)

    rows, saved = [], 0
    t0 = time.time()
    while saved < a.frames:
        if a.on_key:
            try:
                input(f"[{saved + 1}/{a.frames}] 자세를 잡고 Enter (q+Enter 로 중단) > ")
            except EOFError:
                break
            for _ in range(3):                          # 손을 뗀 뒤 흔들림 제거
                z.grab(rt)
        if z.grab(rt) != sl.ERROR_CODE.SUCCESS:
            continue
        z.retrieve_image(L, sl.VIEW.LEFT)               # ★ rectified
        z.retrieve_image(R, sl.VIEW.RIGHT)
        idx = a.start_index + saved
        fd = out / f"frame_{idx:04d}"
        fd.mkdir(parents=True, exist_ok=True)
        for side, m in (("left", L), ("right", R)):
            p_out = fd / f"{side}.png"
            if cv2 is not None:
                img = np.asarray(m.get_data())[:, :, :3]    # BGRA → BGR8, 알파 버림
                ok = bool(cv2.imwrite(str(p_out), np.ascontiguousarray(img)))
            else:
                ok = m.write(str(p_out)) == sl.ERROR_CODE.SUCCESS
            if not ok:
                print(f"❌ 저장 실패: {p_out}", file=sys.stderr)
                z.close()
                return 2
        (fd / "cam.json").write_text(
            json.dumps({k: live[k] for k in CAM_KEYS}, indent=2), encoding="utf-8")
        exp = z.get_camera_settings(sl.VIDEO_SETTINGS.EXPOSURE)
        gn = z.get_camera_settings(sl.VIDEO_SETTINGS.GAIN)
        exp = exp[1] if isinstance(exp, (tuple, list)) else exp   # SDK 버전별 반환형 차이
        gn = gn[1] if isinstance(gn, (tuple, list)) else gn
        rows.append({"frame": fd.name, "timestamp_ns": int(z.get_timestamp(
            sl.TIME_REFERENCE.IMAGE).get_nanoseconds()), "exposure": int(exp), "gain": int(gn)})
        print(f"  {fd.name}: exposure {exp} · gain {gn}")
        saved += 1
        if a.interval_s > 0 and saved < a.frames:
            time.sleep(a.interval_s)
    z.close()

    if not saved:
        print("❌ 한 장도 저장하지 못했다", file=sys.stderr)
        return 2
    (out / "meta_capture.json").write_text(json.dumps({
        "stage": "capture_real", "backend": "zed_sdk", "license": "Stereolabs SDK (proprietary, 캡처 전용)",
        "serial": info.serial_number, "resolution_mode": a.resolution, "fps": a.fps,
        "view": "rectified (sl.VIEW.LEFT / RIGHT)", "format": "PNG 무손실 · BGR8",
        "depth_mode": "NONE (FoundationStereo 로 직접 만든다)",
        "cam": {k: live[k] for k in CAM_KEYS}, "convention": "opencv_pixel_center",
        "cam_profile": a.cam, "profile_checked": bool(a.cam and not a.no_check),
        "ae": a.exposure is None and a.gain is None,
        "exposure_fixed": a.exposure, "gain_fixed": a.gain, "warmup": a.warmup,
        "note": a.note, "sec": round(time.time() - t0, 2), "frames": rows,
        "gt": None,
        "note_gt": "실환경에는 GT 가 없다 — eval_* 를 못 돌린다. 서열화는 GT-free 지표로 "
                   "(게이트 후퇴율 · G0↔G1 불일치율 · 좌우 투영 일관성 · 파지 성공률).",
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{saved} 프레임 → {out}")
    print(f"  다음: stereo_onnx --in {out} --out {out}_st --scale 0.5 …")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
