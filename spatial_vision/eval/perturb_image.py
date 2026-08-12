"""캡처 이미지에 **센서 단계 효과**를 주입한다 — 모션블러 / 자동노출 (도메인 갭 잔여 축).

    envs/stereo_onnx/bin/python -m spatial_vision.eval.perturb_image \
        --in runs/r2_near --out runs/pert/r2_near_blur4 --blur-px 4

왜 이 단계인가
    블러·노출은 **카메라가 만드는 효과**다. 그래서 `left.png`/`right.png` 만 바꾸고
    GT(`depth_gt`·`mask_*`·`pose_gt`)는 **그대로 복사**한다 — 물체는 안 움직였다.
    바뀐 이미지로 stereo 를 다시 돌리면 **depth 열화까지 자동으로** 따라온다.
    (`eval/perturb_depth.py` 가 depth 에 하는 일을 이미지에 하는 셈이다.)

모션블러 `--blur-px`
    로봇이 셔터 동안 움직이면 이미지가 **한 방향으로** 번진다. 길이 W px 의 선형 커널을
    프레임마다 무작위 방향으로 적용한다(`--blur-dir` 로 고정 가능).
    ⚠️ **좌우에 같은 커널**을 쓴다 — 카메라 리그가 통째로 움직이므로 시차 방향이 아니라
       리그 운동 방향으로 번진다. 좌우를 따로 흔들면 있지도 않은 시차 오차를 만든다.

자동노출 `--ae`
    실카메라는 프레임마다 게인을 조절해 밝기를 목표치로 맞춘다. 우리 sim 은 AE 가 **없어서**
    프레임 밝기가 17.7~212.9 로 요동친다(실측) — 즉 AE 는 **해로울 수도 이로울 수도** 있다.
    구현: 측광 영역의 `--ae-percentile` 분위수가 `--ae-target` 이 되도록 게인을 곱하고,
    `--ae-knee` 위쪽은 부드럽게 눌러(soft knee) 클리핑을 흉내낸 뒤 8bit 로 자른다.
    `--ae-meter center` 면 중앙 40% 영역으로 측광한다(대부분의 카메라 기본).

⚠️ **게인은 좌우에 동일하게** 적용한다. 실제 스테레오 카메라도 AE 를 동기화한다 —
   따로 걸면 stereo 정합이 인위적으로 망가진다.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

KEEP = ("cam.json", "depth_gt.npy", "depth_gt.png", "disparity_gt.npy", "mask_full.png",
        "mask_flange.png", "pose_gt.json", "meta_capture.json")


def blur_kernel(width: float, angle_deg: float) -> np.ndarray:
    """길이 `width` px 의 선형 모션블러 커널 (정규화)."""
    n = max(3, int(np.ceil(width)) | 1)                  # 홀수
    k = np.zeros((n, n), np.float32)
    c = (n - 1) / 2.0
    t = np.linspace(-width / 2, width / 2, max(64, 8 * n))
    dx, dy = np.cos(np.radians(angle_deg)), np.sin(np.radians(angle_deg))
    for s in t:                                           # 선을 따라 누적(양선형)
        x, y = c + s * dx, c + s * dy
        x0, y0 = int(np.floor(x)), int(np.floor(y))
        fx, fy = x - x0, y - y0
        for (xi, yi, w) in ((x0, y0, (1 - fx) * (1 - fy)), (x0 + 1, y0, fx * (1 - fy)),
                            (x0, y0 + 1, (1 - fx) * fy), (x0 + 1, y0 + 1, fx * fy)):
            if 0 <= xi < n and 0 <= yi < n:
                k[yi, xi] += w
    s = k.sum()
    return k / s if s > 0 else k


def auto_exposure(img: np.ndarray, meter: np.ndarray, pct: float, target: float,
                  knee: float, read_dn: float = 0.0, rng=None,
                  gain_max: float = 20.0) -> tuple[np.ndarray, float]:
    """측광 분위수를 target 으로 맞추는 게인 + 게인 비례 노이즈 + soft knee.

    ⚠️ **게인만 올리고 노이즈를 안 올리면 낙관적인 흉내다.** 실센서는 게인이 판독 노이즈를
       **같이 증폭**한다 — 어두운 프레임에서 20× 를 걸면 노이즈도 20× 다. `--ae-noise-dn` 이
       게인 1 에서의 판독 노이즈(DN)이고, 여기에 게인을 곱해 더한다.
    """
    v = float(np.percentile(meter, pct))
    gain = float(np.clip(target / max(v, 1e-3), 0.05, gain_max))
    x = img.astype(np.float32) * gain
    if read_dn > 0 and rng is not None:
        x += rng.normal(0.0, read_dn * gain, size=x.shape).astype(np.float32)
    # soft knee: knee 위쪽을 점근적으로 255 로 압축 (실센서의 롤오프)
    hi = x > knee
    x[hi] = knee + (255.0 - knee) * (1.0 - np.exp(-(x[hi] - knee) / max(255.0 - knee, 1e-3)))
    return np.clip(x, 0, 255).astype(np.uint8), gain


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="이미지에 모션블러 / 자동노출 주입")
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blur-px", type=float, default=0.0, help="선형 모션블러 길이 (0=끄기)")
    ap.add_argument("--blur-dir", type=float, default=None,
                    help="블러 방향(도). 기본=프레임마다 무작위")
    ap.add_argument("--ae", action="store_true", help="자동노출 흉내")
    ap.add_argument("--ae-percentile", type=float, default=90.0)
    ap.add_argument("--ae-target", type=float, default=170.0, help="그 분위수가 가야 할 밝기")
    ap.add_argument("--ae-knee", type=float, default=200.0, help="이 위로는 부드럽게 눌린다")
    ap.add_argument("--ae-meter", default="center", choices=["center", "full"])
    ap.add_argument("--ae-noise-dn", type=float, default=0.0,
                    help="게인 1 에서의 판독 노이즈(DN). **게인에 비례해 증폭**된다 — 어두운 프레임에 "
                         "20× 를 걸면 노이즈도 20× 다. 0=끄기(낙관적). 실센서는 1~2 DN 정도")
    ap.add_argument("--ae-gain-max", type=float, default=20.0, help="AE 게인 상한(카메라 한계)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    src, out = Path(args.in_dir), Path(args.out)
    frames = sorted([p for p in src.glob("frame_*") if p.is_dir()])
    if not frames:
        print("❌ frame_* 가 없다")
        return 2
    rng = np.random.default_rng(args.seed)
    rows = []
    for f in frames:
        od = out / f.name
        od.mkdir(parents=True, exist_ok=True)
        ang = args.blur_dir if args.blur_dir is not None else float(rng.uniform(0, 180))
        k = blur_kernel(args.blur_px, ang) if args.blur_px > 0 else None
        gains = []
        # ⚠️ 좌우에 **같은** 커널·게인 (리그가 통째로 움직이고 AE 도 동기화된다)
        for side in ("left.png", "right.png"):
            img = cv2.imread(str(f / side))
            if img is None:
                continue
            if k is not None:
                img = cv2.filter2D(img, -1, k, borderType=cv2.BORDER_REPLICATE)
            if args.ae:
                g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                if args.ae_meter == "center":
                    h, w = g.shape
                    g = g[int(0.3 * h):int(0.7 * h), int(0.3 * w):int(0.7 * w)]
                img, gain = auto_exposure(img, g, args.ae_percentile, args.ae_target,
                                          args.ae_knee, args.ae_noise_dn, rng, args.ae_gain_max)
                gains.append(gain)
            cv2.imwrite(str(od / side), img)
        for n in KEEP:                                    # GT 는 그대로 — 물체는 안 움직였다
            if (f / n).exists():
                shutil.copy2(f / n, od / n)
        rows.append({"frame": f.name, "blur_px": args.blur_px, "blur_dir_deg": round(ang, 1),
                     "ae_gain": round(float(np.mean(gains)), 4) if gains else None})
        print(f"  {f.name}: blur {args.blur_px:.1f}px @{ang:5.1f}°"
              + (f"  AE gain ×{np.mean(gains):.3f}" if gains else ""))

    out.mkdir(parents=True, exist_ok=True)
    (out / "meta_perturb_image.json").write_text(json.dumps({
        "stage": "perturb_image", "source": args.in_dir,
        "blur_px": args.blur_px, "blur_dir_deg": args.blur_dir,
        "ae": args.ae, "ae_percentile": args.ae_percentile, "ae_target": args.ae_target,
        "ae_knee": args.ae_knee, "ae_meter": args.ae_meter,
        "ae_noise_dn": args.ae_noise_dn, "ae_gain_max": args.ae_gain_max, "seed": args.seed,
        "note": "left/right 만 바꾼다. GT(depth_gt·mask·pose_gt)는 원본 그대로 복사 — 물체는 안 움직였다.",
        "frames": rows,
    }, indent=2, ensure_ascii=False))
    g = [r["ae_gain"] for r in rows if r["ae_gain"]]
    print(f"{len(rows)} 프레임 → {out}" + (f"  | AE 게인 {min(g):.2f}~{max(g):.2f}" if g else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
