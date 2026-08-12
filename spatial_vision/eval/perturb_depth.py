"""depth 에 **통제된 오차를 주입**해 pose 파이프라인의 강건성을 시험한다.

    envs/stereo_onnx/bin/python -m spatial_vision.eval.perturb_depth \
        --in runs/dr2_near_onnx --capture runs/dr2_near \
        --out runs/pert/near_corr60_17 --mode corr --corr-px 60 --target-mm 17

왜 필요한가
    실환경 예비측정에서 D435 + FoundationStereo 의 Z 오차가 **17mm** 였다(RESULTS.md § 실카메라
    depth 오차 예산). sim 의 ZED X 조합은 0.7mm 다. "실환경이 그만큼 나쁘다면 어느 파이프라인이
    살아남는가" 를 묻기 위해, sim depth 에 17mm 급 오차를 **성격별로** 주입한다.

★ 오차의 **성격**이 크기보다 중요하다
    flange 는 근접에서 ~142,000 px 다. 픽셀 독립(iid) 노이즈는 √142000 ≈ 378배로 평균화되어
    pose 에는 거의 도달하지 않는다. 실제 스테레오 오차는 **공간적으로 상관**돼 있어(패치 단위로
    함께 밀린다) 평균화가 훨씬 덜 된다. 따라서 상관길이가 사실상의 주 변수다.

모드 — RESULTS.md 의 "편향 vs 산포" 진단(거리 지수 p)과 대응한다
    iid     시차 공간 백색잡음                p≈2, 상관 0     — 낙관적 하한
    corr    시차 공간 상관잡음(--corr-px)     p≈2, 상관 유    — 실제 스테레오에 가장 가깝다
    scale   Z ×= (1+s)                       p≈1            — baseline 스케일 오차
    offset  Z += c                           p≈0            — 고정 오프셋(원점·정렬)

크기 보정
    `--target-mm` 은 **캘리브레이션 마스크 영역의 평균 |ΔZ|** 다. 모드마다 파라미터→mm 관계가
    다르므로(비선형) 이분법으로 맞춘다. 실제 달성치를 항상 출력·기록한다.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np


def _noise_field(shape, corr_px: float, rng: np.random.Generator) -> np.ndarray:
    """std=1 의 (선택적으로 공간상관된) 잡음장."""
    n = rng.standard_normal(shape).astype(np.float32)
    if corr_px and corr_px > 0:
        k = int(max(3, round(corr_px * 3)) | 1)          # 3σ 커널, 홀수
        n = cv2.GaussianBlur(n, (k, k), corr_px)
        s = n.std()
        if s > 1e-9:
            n /= s                                        # 평활화로 줄어든 분산을 되돌린다
    return n


def perturb(depth_mm: np.ndarray, mode: str, amp: float, fxb: float,
            noise: np.ndarray | None) -> np.ndarray:
    """depth(mm, 0=invalid) → 교란된 depth(mm). invalid 는 invalid 로 남긴다."""
    out = depth_mm.astype(np.float64).copy()
    ok = out > 0
    if mode in ("iid", "corr"):
        # 시차 공간에서 더한다 — 물리적으로 옳은 자리. d = fx·B/Z
        d = np.zeros_like(out)
        d[ok] = fxb / out[ok]
        d[ok] += amp * noise[ok]
        good = ok & (d > 1e-6)
        out[:] = 0.0
        out[good] = fxb / d[good]
    elif mode == "scale":
        out[ok] *= (1.0 + amp)
    elif mode == "offset":
        out[ok] += amp
    else:
        raise ValueError(mode)
    out[out < 0] = 0.0
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="depth 에 통제된 오차 주입")
    ap.add_argument("--in", dest="in_dir", required=True, help="stereo 산출 런 (depth.png)")
    ap.add_argument("--capture", required=True, help="캡처 런 (cam.json·mask·depth_gt.npy)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", required=True, choices=["iid", "corr", "scale", "offset"])
    ap.add_argument("--corr-px", type=float, default=60.0, help="mode=corr 의 상관길이(px)")
    ap.add_argument("--target-mm", type=float, default=17.0,
                    help="캘리브레이션 마스크 영역의 목표 평균 |ΔZ| (mm)")
    ap.add_argument("--calib-mask", default="mask_full.png",
                    help="크기를 맞출 영역. 근접 flange 실험이면 mask_flange.png")
    ap.add_argument("--seed", type=int, default=12345)
    args = ap.parse_args(argv)

    src, cap, out = Path(args.in_dir), Path(args.capture), Path(args.out)
    frames = sorted([p for p in src.glob("frame_*") if (p / "depth.png").exists()])
    if not frames:
        print(f"❌ depth.png 를 가진 프레임이 없다: {src}")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    # --- 1) 크기 보정: 전 프레임 공통 amp 를 이분법으로 찾는다 ---
    cal = []
    for f in frames[: min(8, len(frames))]:
        cam = json.loads((cap / f.name / "cam.json").read_text())
        d = cv2.imread(str(f / "depth.png"), cv2.IMREAD_UNCHANGED).astype(np.float64)
        m = cv2.imread(str(cap / f.name / args.calib_mask), cv2.IMREAD_GRAYSCALE)
        sel = (m > 127) & (d > 0)
        if sel.any():
            cal.append((d, sel, cam["fx"] * cam["baseline_mm"],
                        _noise_field(d.shape, args.corr_px if args.mode == "corr" else 0.0, rng)))
    if not cal:
        print("❌ 캘리브레이션 표본 없음")
        return 2

    def achieved(amp: float) -> float:
        e = [np.abs(perturb(d, args.mode, amp, fxb, n)[s] - d[s]).mean() for d, s, fxb, n in cal]
        return float(np.mean(e))

    lo, hi = 0.0, {"iid": 5.0, "corr": 5.0, "scale": 0.5, "offset": 500.0}[args.mode]
    while achieved(hi) < args.target_mm and hi < 1e5:
        hi *= 2
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        if achieved(mid) < args.target_mm:
            lo = mid
        else:
            hi = mid
    amp = 0.5 * (lo + hi)
    print(f"보정 완료: mode={args.mode} amp={amp:.6g} "
          f"({'σ_disp px' if args.mode in ('iid','corr') else 'scale' if args.mode=='scale' else 'mm'})"
          f"  → 목표 {args.target_mm}mm, 표본 달성 {achieved(amp):.2f}mm")

    # --- 2) 전 프레임 적용 ---
    stats = []
    for f in frames:
        cam = json.loads((cap / f.name / "cam.json").read_text())
        d = cv2.imread(str(f / "depth.png"), cv2.IMREAD_UNCHANGED).astype(np.float64)
        n = _noise_field(d.shape, args.corr_px if args.mode == "corr" else 0.0, rng)
        p = perturb(d, args.mode, amp, cam["fx"] * cam["baseline_mm"], n)
        fo = out / f.name
        fo.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(fo / "depth.png"), np.rint(p).clip(0, 65535).astype(np.uint16))
        # depth.png 만 pose 가 읽는다. disparity.npy(3.7MB/frame)는 복사하지 않는다 — 런이 수십 개다.
        if (f / "valid.png").exists():
            shutil.copy(f / "valid.png", fo / "valid.png")
        m = cv2.imread(str(cap / f.name / args.calib_mask), cv2.IMREAD_GRAYSCALE)
        sel = (m > 127) & (d > 0)
        if sel.any():
            stats.append(float(np.abs(p[sel] - d[sel]).mean()))

    got = float(np.mean(stats))
    (out / "meta_perturb.json").write_text(json.dumps({
        "stage": "perturb_depth", "source": str(src), "capture": str(cap),
        "mode": args.mode, "corr_px": args.corr_px if args.mode == "corr" else None,
        "amp": amp, "amp_unit": {"iid": "px_disparity", "corr": "px_disparity",
                                 "scale": "relative", "offset": "mm"}[args.mode],
        "target_mm": args.target_mm, "achieved_mean_abs_dz_mm": got,
        "calib_mask": args.calib_mask, "seed": args.seed, "frames": len(frames),
        "note": "sim depth 에 통제된 오차를 주입한 것이다. 실측 아님.",
    }, indent=2, ensure_ascii=False))
    print(f"{len(frames)} 프레임 → {out}   실제 평균 |ΔZ| = {got:.2f} mm ({args.calib_mask})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
