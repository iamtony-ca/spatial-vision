#!/usr/bin/env python3
"""실카메라 좌/우 이미지 + 카메라 프로파일 → 우리 파이프라인의 **프레임 디렉토리**를 만든다.

    python3 tools/make_frame_from_zed.py \
        --left  shot_left.png --right shot_right.png \
        --cam   assets/cam/zedx_s48560070_hd1200.json \
        --out   runs/real01/frame_0000

왜 이 도구인가
    실환경에서 파이프라인에 **필요한 입력은 3개뿐**이다 — `left.png` · `right.png` · `cam.json`.
    나머지(`depth_gt.npy` · `mask_*.png` · `pose_gt.json`)는 **sim GT 전용**이고 실물에는 없어도 된다.
    (없으면 `eval_*` 만 못 돌린다 — 즉 실환경에서는 절대 오차를 못 잰다. 이미 확정된 제약이다.)

🔴 rectified 만 넣는다
    ZED SDK 의 `sl.VIEW.LEFT` / `sl.VIEW.RIGHT` (정류본). `*_UNRECTIFIED` 를 넣으면 왜곡이
    살아 있어 `cam.json`(왜곡항 없음)과 안 맞는다. 프로파일의 값도 `calibration_parameters`
    (rectified) 기준이다.

🔴 무손실만 넣는다
    PNG. JPEG 는 서브픽셀 기울기 정합(`refine_contour`)이 압축 아티팩트를 먹는다.

⚠️ `cam.json` 의 `cx/cy` 는 **OpenCV(픽셀 중심) 규약**이다. sim 캡처(`capture_sim --cx/--cy`)만
   코너 원점이라 +0.5 가 필요하고, 여기서는 **프로파일 값을 그대로** 쓴다.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

REQUIRED = ("fx", "fy", "cx", "cy", "baseline_mm", "width", "height")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="실카메라 좌/우 → 프레임 디렉토리")
    ap.add_argument("--left", required=True, help="rectified 좌 이미지 (PNG)")
    ap.add_argument("--right", required=True, help="rectified 우 이미지 (PNG)")
    ap.add_argument("--cam", required=True, help="assets/cam/<id>.json")
    ap.add_argument("--out", required=True, help="frame_XXXX 디렉토리")
    ap.add_argument("--note", default=None, help="meta 에 남길 메모 (거리·조명 등)")
    a = ap.parse_args(argv)

    prof = json.loads(Path(a.cam).read_text())
    cam = {k: prof[k] for k in REQUIRED}
    if not str(a.left).lower().endswith(".png") or not str(a.right).lower().endswith(".png"):
        print("❌ PNG 무손실만 받는다 (JPEG 아티팩트가 테두리 정합을 망친다)")
        return 2

    import cv2
    for side, src in (("left", a.left), ("right", a.right)):
        img = cv2.imread(str(src), cv2.IMREAD_COLOR)      # BGR8, 알파 제거
        if img is None:
            print(f"❌ 못 읽음: {src}")
            return 2
        h, w = img.shape[:2]
        if (w, h) != (cam["width"], cam["height"]):
            print(f"❌ {side} 해상도 {w}x{h} 가 프로파일 {cam['width']}x{cam['height']} 와 다르다. "
                  f"해상도 모드를 바꿨으면 캘리브레이션·SAM3 참조를 전부 다시 만들어야 한다.")
            return 2
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out / f"{side}.png"), img)

    out = Path(a.out)
    (out / "cam.json").write_text(json.dumps(cam, indent=2))
    (out / "meta_capture.json").write_text(json.dumps({
        "stage": "capture_real", "source": "external",
        "cam_profile": a.cam, "cam_profile_id": prof.get("id"),
        "rectified": True, "convention": "opencv_pixel_center",
        "left_src": str(a.left), "right_src": str(a.right), "note": a.note,
        "gt": None, "note_gt": "실환경에는 GT 가 없다 — eval_* 는 못 돌린다(서열화는 GT-free 지표로).",
    }, indent=2, ensure_ascii=False))
    print(f"✅ {out}  ({cam['width']}x{cam['height']}, fx {cam['fx']:.3f}, B {cam['baseline_mm']:.3f}mm)")
    print(f"   다음: stereo_onnx --in {out.parent} --out ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
