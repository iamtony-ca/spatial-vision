"""스테레오 depth 오차 예산 — "이 카메라로 이 거리에서 KPI 를 만족할 수 있는가".

    envs/cad/bin/python -m spatial_vision.eval.depth_budget
    envs/cad/bin/python -m spatial_vision.eval.depth_budget --observed-mm 17 --observed-dist 1.0

모델
    σ_Z = Z² / (fx·B) · σ_disp        깊이 오차는 거리의 **제곱**, `fx·B` 에 **반비례**
    측면 오차 = Z / fx · σ_px          같은 픽셀 오차가 Z 를 때리는 배율 = **Z / B**

이 두 식이 실환경 관측을 거의 다 설명한다 (RESULTS.md § 실카메라 depth 오차 예산):
  - D435 실측 Z 오차 17mm 는 σ_disp 0.57px 에 해당 → **스테레오는 정상, baseline 이 문제**
  - "X/Y 는 안정적인데 Z 만 튄다" 는 이상 증상이 아니라 Z/B = 20배의 정상 거동

⚠️ 이 전부는 오차가 **랜덤 산포**일 때만 성립한다. 계통 편향이면 거리 지수가 다르다 —
   `--diagnose` 로 판별법을 출력한다.
"""

from __future__ import annotations

import argparse

import numpy as np

# 이름: (fx @1280×720, baseline mm, depth HFOV°)
CAMERAS = {
    "RealSense D435": (674, 50, 87),      # depth FOV 87° → fx = 640/tan(43.5°)
    "RealSense D455": (674, 95, 87),
    "ZED 2i (4mm)": (1050, 120, 72),
    "ZED X (4mm)": (1200, 120, 72),       # ← sim 에서 검증된 조합
}
DISTANCES = (0.4, 0.6, 1.0, 1.5, 2.0)
FLANGE_MM, FOUP_MM = 142.0, 390.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="스테레오 depth 오차 예산")
    ap.add_argument("--kpi-mm", type=float, default=5.0, help="translation KPI (mm)")
    ap.add_argument("--lateral-mm", type=float, default=1.7,
                    help="측면 오차 실측치 — depth 가 쓸 수 있는 예산을 이만큼 깎는다")
    ap.add_argument("--observed-mm", type=float, default=17.0, help="실측 Z 오차")
    ap.add_argument("--observed-cam", default="RealSense D435")
    ap.add_argument("--observed-dist", type=float, default=None,
                    help="실측 거리(m). 모르면 여러 후보로 역산한다")
    args = ap.parse_args(argv)

    print("=== 시차 1px 오차 → 깊이 오차 (mm)")
    hdr = "  ".join(f"{d:5.1f}m" for d in DISTANCES)
    print(f"{'카메라':18s} {'fx':>5s} {'B':>4s} {'fx·B':>7s} {'상대':>6s} | {hdr}")
    base = max(fx * b for fx, b, _ in CAMERAS.values())
    for k, (fx, b, _) in CAMERAS.items():
        fb = fx * b
        row = "  ".join(f"{(z*1000)**2/fb:6.1f}" for z in DISTANCES)
        print(f"{k:18s} {fx:5d} {b:4d} {fb:7d} {fb/base:5.2f}x | {row}")

    print("\n=== 같은 픽셀 오차가 Z 를 때리는 배율 (= Z / baseline)")
    print("   'X/Y 는 안정적인데 Z 만 튄다' 는 여기서 나온다")
    for k, (_, b, _) in CAMERAS.items():
        print(f"  {k:18s} B={b:3d}mm | " + "  ".join(f"{z:.1f}m:{z*1000/b:5.1f}x" for z in DISTANCES))

    budget = args.kpi_mm - args.lateral_mm
    print(f"\n=== KPI {args.kpi_mm:.0f}mm 중 측면 {args.lateral_mm:.1f}mm 를 빼면 depth 예산 {budget:.1f}mm")
    print("   → 최대 작업거리 (m)")
    print(f"{'σ_disp':>8s} | " + " ".join(f"{k:>16s}" for k in CAMERAS))
    for sd in (0.3, 0.5, 0.9):
        cells = []
        for fx, b, hf in CAMERAS.values():
            z = np.sqrt(budget * fx * b / sd) / 1000.0
            fov = 2 * z * np.tan(np.radians(hf / 2))
            fits = "FOUP" if fov > FOUP_MM / 1000 else ("flange" if fov > FLANGE_MM / 1000 else "✗")
            cells.append(f"{z:5.2f} ({fits:>6s})")
        print(f"{sd:8.1f} | " + " ".join(f"{c:>16s}" for c in cells))
    print("   괄호 = 그 거리의 FOV 폭에 무엇이 들어가는가")

    fx, b, _ = CAMERAS[args.observed_cam]
    fb = fx * b
    print(f"\n=== 실측 {args.observed_mm:.0f}mm 역산 ({args.observed_cam}, fx·B={fb})")
    dists = [args.observed_dist] if args.observed_dist else [0.8, 1.0, 1.2, 1.5]
    for z in dists:
        sd = args.observed_mm / ((z * 1000) ** 2 / fb)
        print(f"  거리 {z:.1f}m → σ_disp = {sd:.3f} px", end="")
        print("   ← 0.3~1.0px 면 스테레오는 정상, 카메라 기하가 원인" if 0.2 < sd < 1.5 else "")
        for tk, (tfx, tb, _) in CAMERAS.items():
            if tk == args.observed_cam:
                continue
            for tz in (0.43, 0.6):
                print(f"       → {tk} @ {tz:.2f}m 예측 {(tz*1000)**2/(tfx*tb)*sd:6.2f} mm")

    print("\n=== ⚠️ 편향 vs 산포 — 거리 지수로 구분한다 (M6 최우선 실험)")
    print("   같은 물체를 0.5 / 1.0 / 1.5m 에서 재고 오차의 거리 지수 p 를 맞춘다:")
    print("     p ≈ 2 : 시차 랜덤오차   → 카메라(baseline)·거리로 해결")
    print("     p ≈ 1 : baseline 스케일 → 재캘리브레이션 (카메라 바꿔도 안 나음)")
    print("     p ≈ 0 : 고정 오프셋     → 원점 규약·정렬 점검")
    frac = args.observed_mm / ((args.observed_dist or 1.0) * 1000)
    print(f"   참고: {(args.observed_dist or 1.0):.1f}m 에서 {args.observed_mm:.0f}mm 를 스케일 오차로 보면 "
          f"{frac*100:.2f}% → baseline {b*frac:.2f}mm 어긋남과 동등")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
