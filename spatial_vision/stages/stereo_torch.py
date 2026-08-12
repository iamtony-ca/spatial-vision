"""stereo 스테이지 — FoundationStereo PyTorch 백엔드 (연구 전용, 정확도 기준선).

    envs/stereo/bin/python -m spatial_vision.stages.stereo_torch \
        --in runs/sim01 --out runs/sim01_fs_torch

⚠️ 라이선스 — **research/evaluation 전용** (docs/LICENSES.md §1)
    `NVlabs/FoundationStereo` 코드와 GitHub 배포 가중치는 NVIDIA Source Code License §3.3 로
    상업적 사용이 금지돼 있다. 이 파일은 repo 코드를 **직접 import** 하므로 상업 경로에 쓸 수 없다.
    상업 경로는 `stereo_onnx.py`(NGC 가중치 + 자체 전/후처리)를 쓴다.
    두 백엔드가 **같은 계약**을 구현하므로 config 로 갈아끼울 수 있고, M3 평가가 그 차이를 수치화한다.

repo 사용법은 `scripts/run_demo.py` 를 따른다:
    raw 0-255 RGB (NCHW float) → InputPadder(divis_by=32) → model.forward(iters=, test_mode=True)
    → padder.unpad → disparity(px). 정규화는 모델 내부에서 한다(ONNX 판과 다른 점).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "third_party" / "FoundationStereo"))

from spatial_vision.contracts import CameraParams, read_rgb, write_stereo_frame  # noqa: E402

LICENSE_NOTE = ("NVIDIA Source Code License §3.3 — research purposes only "
                "(NVlabs/FoundationStereo, GitHub weights). 상업 사용 불가.")


class TorchStereoBackend:
    def __init__(self, ckpt_path: str | Path, valid_iters: int = 32, hiera: bool = False,
                 device: str = "cuda"):
        import logging

        import torch
        from omegaconf import OmegaConf

        from core.foundation_stereo import FoundationStereo
        from core.utils.utils import InputPadder

        logging.disable(logging.INFO)
        self.torch = torch
        self.InputPadder = InputPadder
        self.valid_iters = valid_iters
        self.hiera = hiera
        self.device = device
        self.ckpt_path = str(ckpt_path)

        cfg_path = Path(ckpt_path).parent / "cfg.yaml"
        cfg = OmegaConf.load(str(cfg_path))
        if "vit_size" not in cfg:
            cfg["vit_size"] = "vitl"
        self.vit_size = str(cfg.get("vit_size"))

        t0 = time.time()
        model = FoundationStereo(cfg)
        ckpt = torch.load(self.ckpt_path, map_location="cpu", weights_only=False)
        sd = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
        missing, unexpected = model.load_state_dict(sd, strict=True), None
        model.to(device).eval()
        self.model = model
        self.load_s = time.time() - t0
        self.global_step = ckpt.get("global_step") if isinstance(ckpt, dict) else None

    @property
    def torch_no_grad(self):
        return self.torch.no_grad()

    def infer(self, left_rgb: np.ndarray, right_rgb: np.ndarray, scale: float = 1.0) -> np.ndarray:
        """좌/우 RGB(uint8) → 원본 해상도 disparity(px, float32)."""
        torch = self.torch
        h0, w0 = left_rgb.shape[:2]
        if scale != 1.0:
            size = (int(round(w0 * scale)), int(round(h0 * scale)))
            left_rgb = cv2.resize(left_rgb, size, interpolation=cv2.INTER_AREA)
            right_rgb = cv2.resize(right_rgb, size, interpolation=cv2.INTER_AREA)
        hs, ws = left_rgb.shape[:2]

        # repo 규약: raw 0-255 RGB, NCHW float. 정규화는 모델 forward 안에서 한다.
        a = torch.as_tensor(left_rgb).to(self.device).float()[None].permute(0, 3, 1, 2)
        b = torch.as_tensor(right_rgb).to(self.device).float()[None].permute(0, 3, 1, 2)
        padder = self.InputPadder(a.shape, divis_by=32, force_square=False)
        a, b = padder.pad(a, b)

        with torch.no_grad(), torch.amp.autocast("cuda", enabled=True):
            if self.hiera:
                disp = self.model.run_hierachical(a, b, iters=self.valid_iters, test_mode=True,
                                                  small_ratio=0.5)
            else:
                disp = self.model.forward(a, b, iters=self.valid_iters, test_mode=True)
        disp = padder.unpad(disp.float()).squeeze().detach().cpu().numpy().reshape(hs, ws)

        if scale != 1.0:
            disp = cv2.resize(disp, (w0, h0), interpolation=cv2.INTER_LINEAR) / scale
        return np.ascontiguousarray(disp, dtype=np.float32)


def find_frames(root: Path) -> list[Path]:
    if (root / "left.png").exists():
        return [root]
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "left.png").exists())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="stereo 스테이지 (FoundationStereo PyTorch)")
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--out", dest="out_dir", default=None)
    ap.add_argument("--ckpt", default="third_party/FoundationStereo/pretrained_models/23-51-11/model_best_bp2.pth")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--valid-iters", type=int, default=32)
    ap.add_argument("--hiera", action="store_true", help="고해상도(>1K)용 계층 추론")
    ap.add_argument("--min-disparity-px", type=float, default=0.05)
    ap.add_argument("--z-near-mm", type=float, default=100.0)
    ap.add_argument("--z-far-mm", type=float, default=10000.0)
    args = ap.parse_args(argv)

    in_root = Path(args.in_dir)
    out_root = Path(args.out_dir) if args.out_dir else in_root
    frames = find_frames(in_root)
    if not frames:
        print(f"처리할 프레임이 없다: {in_root}", file=sys.stderr)
        return 1

    be = TorchStereoBackend(args.ckpt, valid_iters=args.valid_iters, hiera=args.hiera)
    print(f"모델 로드 {be.load_s:.1f}s | vit_size={be.vit_size} | ckpt={Path(be.ckpt_path).parent.name} "
          f"| 프레임 {len(frames)}개")

    for f in frames:
        cam = CameraParams.from_json(f / "cam.json")
        left, right = read_rgb(f / "left.png"), read_rgb(f / "right.png")
        t0 = time.time()
        disp = be.infer(left, right, scale=args.scale)
        dt = time.time() - t0
        out = out_root / f.name if f != in_root else out_root
        m = write_stereo_frame(
            out, disp, cam,
            backend="fs_torch", model=f"{Path(be.ckpt_path).parent.name}/{Path(be.ckpt_path).name}",
            license_note=LICENSE_NOTE,
            extra={"vit_size": be.vit_size, "valid_iters": args.valid_iters,
                   "hiera": args.hiera, "scale": args.scale, "infer_s": round(dt, 4),
                   "normalization": "model-internal (repo forward)"},
            min_disparity_px=args.min_disparity_px,
            z_near_mm=args.z_near_mm, z_far_mm=args.z_far_mm,
        )
        d = m["depth_mm"]
        print(f"  {f.name}: {dt*1000:6.0f}ms  disp {m['disparity_px']['min']:.1f}/"
              f"{m['disparity_px']['median']:.1f}/{m['disparity_px']['max']:.1f}px  "
              f"depth median {d['median']:.0f}mm  valid {d['valid_frac']*100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
