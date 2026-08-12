"""M2 확장 2단계 — 배경·재질 randomization 이 **의도한 것만** 흔드는지 검사한다.

    envs/stereo_onnx/bin/python -m spatial_vision.eval.verify_randomization --in runs/mat_iso

왜 이 검사가 필요한가
    "flange 는 고정, body 만 randomize" 는 **눈으로 확인할 수 없는 종류의 계약**이다.
    재질 바인딩이 프림 하나 위로 새면(루트에 걸리거나, GeomSubset·instance proxy 를 만나면)
    flange 까지 물드는데, 렌더 결과는 여전히 그럴듯해 보인다. 그러면 exemplar 참조·ISM 템플릿이
    기대하는 외관이 조용히 무너지고, 우리는 그것을 **도메인 갭으로 오독**하게 된다.

무엇을 재나 (프레임 쌍마다)
    - **body 픽셀의 변화량** — 커야 한다. 작으면 randomization 이 안 걸린 것이다.
    - **flange 픽셀의 변화량** — 작아야 한다.
    - 두 값의 **비**로 판정한다. 절대값이 아니라 비인 이유: 조명·HDRI 를 함께 흔들면 두 영역이
      **같이** 변하므로 절대 문턱은 의미가 없다.

⚠️ flange 변화량이 정확히 0 이 되지는 않는다 — body 에서 반사된 간접광이 flange 아래·모서리에
   닿는다. 그건 물리적으로 옳은 결과이지 누수가 아니다. 그래서 0 이 아니라 **비**를 본다.

⚠️ 이 검사는 **카메라·조명·객체 자세를 고정한 런**에서만 뜻이 있다. 시점이 프레임마다 바뀌면
   두 영역이 전부 바뀌어 아무것도 분리되지 않는다. 그런 런은 거부한다.
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np


def _frames(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("frame_*") if (p / "left.png").exists())


def _view_is_frozen(frames: list[Path]) -> tuple[bool, str]:
    """시점·객체 자세가 고정됐는지. meta 의 카메라 파라미터로 판정한다."""
    keys = ("camera_distance_m", "elevation_deg", "azimuth_deg", "object_yaw_deg")
    vals = []
    for f in frames:
        m = json.loads((f / "meta_capture.json").read_text())
        vals.append(tuple(round(float(m[k]), 6) for k in keys))
    if len(set(vals)) == 1:
        return True, ""
    spread = {k: (min(v[i] for v in vals), max(v[i] for v in vals)) for i, k in enumerate(keys)}
    return False, str(spread)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="배경·재질 randomization 격리 검사")
    ap.add_argument("--in", dest="in_dir", required=True, help="시점 고정 캡처 런")
    ap.add_argument("--min-ratio", type=float, default=5.0,
                    help="body 변화 / flange 변화. 이 미만이면 실패(누수 의심)")
    ap.add_argument("--min-body-delta", type=float, default=5.0,
                    help="body 평균 |Δ| (0~255). 이 미만이면 randomization 이 안 걸린 것")
    args = ap.parse_args(argv)

    root = Path(args.in_dir)
    frames = _frames(root)
    if len(frames) < 2:
        print(f"❌ 프레임 부족: {len(frames)}")
        return 2

    frozen, spread = _view_is_frozen(frames)
    if not frozen:
        print("❌ 시점이 고정되지 않은 런이다 — 이 검사로는 재질 누수를 분리할 수 없다.")
        print(f"   변동: {spread}")
        print("   --distance-m A A --elevation-deg B B --azimuth-deg C C --yaw-jitter-deg 0 로 다시 뜰 것")
        return 2

    imgs, body, flange = [], [], []
    for f in frames:
        imgs.append(cv2.imread(str(f / "left.png")).astype(np.float32))
        full = cv2.imread(str(f / "mask_full.png"), 0) > 127
        fl = cv2.imread(str(f / "mask_flange.png"), 0) > 127
        # ★ flange 는 **침식**해서 본다. 경계 픽셀은 body 와 섞여 있어 누수 판정을 오염시킨다
        #   (횡단 정리 #5 와 같은 이유).
        fl_core = cv2.erode(fl.astype(np.uint8), np.ones((5, 5), np.uint8), iterations=2) > 0
        body.append(full & ~fl)
        flange.append(fl_core)
    if not any(m.any() for m in flange):
        print("❌ flange core 마스크가 비었다")
        return 2

    rows = []
    for i, j in combinations(range(len(frames)), 2):
        d = np.abs(imgs[i] - imgs[j]).mean(axis=2)
        mb = body[i] & body[j]
        mf = flange[i] & flange[j]
        rows.append((frames[i].name, frames[j].name, float(d[mb].mean()), float(d[mf].mean())))

    b = float(np.mean([r[2] for r in rows]))
    f = float(np.mean([r[3] for r in rows]))
    ratio = b / max(f, 1e-6)

    print(f"═══ randomization 격리 검사 | {root} | {len(frames)} 프레임 · {len(rows)} 쌍")
    print(f"{'쌍':24s} {'body |Δ|':>10s} {'flange |Δ|':>11s} {'비':>7s}")
    for a, c, db, df in rows[:10]:
        print(f"{a[-4:]}↔{c[-4:]:19s} {db:10.3f} {df:11.3f} {db / max(df, 1e-6):7.1f}")
    if len(rows) > 10:
        print(f"  … {len(rows) - 10} 쌍 생략")
    print(f"\n평균  body {b:.3f} / flange {f:.3f}  → **비 {ratio:.1f}×**  (0~255 스케일)")

    ok = True
    if b < args.min_body_delta:
        print(f"❌ body 가 거의 안 변했다 ({b:.3f} < {args.min_body_delta}) — 재질이 안 걸렸다")
        ok = False
    if ratio < args.min_ratio:
        print(f"❌ flange 가 함께 변한다 (비 {ratio:.1f} < {args.min_ratio}) — 재질 바인딩 누수 의심")
        ok = False
    if ok:
        print(f"✅ body 만 변한다. flange 잔여 변화 {f:.3f}/255 = {100 * f / 255:.2f}% "
              f"(body 반사 간접광 — 물리적으로 정상)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
