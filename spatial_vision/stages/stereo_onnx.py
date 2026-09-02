"""stereo 스테이지 — NGC FoundationStereo ONNX 백엔드 (상업 라이선스 경로).

    envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx \
        --in runs/foo --out runs/foo --model weights/ngc_foundationstereo/<model>.onnx

★ 라이선스 경계 (docs/LICENSES.md)
    NGC 배포 가중치는 NVIDIA Open Model License(상업 사용 가능)지만,
    GitHub `NVlabs/FoundationStereo` **코드는 research-only** 다.
    따라서 이 파일의 전처리·후처리는 **repo 코드를 참조하지 않고 직접 구현**한다.
    이 경계가 유지되어야 상업 경로가 성립한다.

ONNX 인터페이스 (실측, 2026-08-07)
    입력  left_image / right_image : float32 (B,3,H,W), 완전 동적
    출력  disparity                : float32 (B,1,H,W), 좌영상 기준 px
    ⚠️ 그래프에 정규화 상수가 없다 → **정규화는 호출자 책임**.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from spatial_vision.contracts import (  # noqa: E402
    CameraParams,
    read_rgb,
    write_stereo_frame,
)

# ImageNet 통계. ONNX 그래프에 정규화 레이어가 없어서 여기서 적용한다.
# ★ 근거는 추측이 아니다 — upstream `core/foundation_stereo.py:43-48` 이
#   `Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])(img/255)` 를 쓴다(`:204-205`).
#   논문 §3.1 의 단안 prior 가 DepthAnythingV2(DINOv2 계보)라 그 관례를 그대로 따른다.
# 실측 확인: raw 0-255 로 넣으면 MAE 1.43px 어긋난다.
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], np.float32).reshape(1, 3, 1, 1)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], np.float32).reshape(1, 3, 1, 1)

LICENSE_NOTE = "NVIDIA Open Model License (NGC nvidia/tao/foundationstereo) — commercial use permitted"


def _normalize(img_rgb_u8: np.ndarray, mode: str) -> np.ndarray:
    """(H,W,3) uint8 → (1,3,H,W) float32."""
    x = img_rgb_u8.transpose(2, 0, 1)[None].astype(np.float32)
    if mode == "raw":
        return x
    x /= 255.0
    if mode == "unit":
        return x
    if mode == "imagenet":
        return (x - IMAGENET_MEAN) / IMAGENET_STD
    raise ValueError(f"알 수 없는 정규화 모드: {mode}")


def _pad_to_multiple(img: np.ndarray, m: int) -> tuple[np.ndarray, int, int]:
    """오른쪽·아래로만 replicate 패딩 (32 배수).

    **왜 32 인가** — 논문(arXiv:2501.09898) §3.1 이 특징 피라미드를 `i ∈ {4, 8, 16, 32}` 로 쓴다
    (가장 깊은 단계가 1/32). upstream 도 `run_demo.py:82` 에서 `divis_by=32` 를 준다.

    **왜 오른쪽·아래인가** — ⚠️ **«왼쪽에 패딩하면 disparity 가 오프셋된다» 는 틀렸다**
    (2026-09-02 실측 정정). 좌·우 영상에 **같은** 패딩을 주면 `x_L − x_R` 이 보존된다.
    실제로 가로 10px 를 왼쪽에 줘도 disparity 차이는 **중앙 0.038px** 로 모델 잡음 수준이었다
    (upstream 은 오히려 좌우 대칭 패딩 `mode='sintel'` 이다).
    → 오른쪽·아래를 쓰는 이유는 **되돌리기가 단순한 슬라이스(`[:h, :w]`)** 라서다. 등가 선택이다.
    🔴 단 **좌·우 영상에 «다른» 패딩을 주면 그때는 실제로 오프셋된다** — 그것만 피하면 된다.
    """
    h, w = img.shape[:2]
    ph, pw = (-h) % m, (-w) % m
    if ph or pw:
        img = cv2.copyMakeBorder(img, 0, ph, 0, pw, cv2.BORDER_REPLICATE)
    return img, ph, pw


class OnnxStereoBackend:
    """ONNX Runtime 세션을 감싼다.

    세션 초기화가 ~31초(53k 노드)라 **반드시 재사용**해야 한다.
    프레임마다 프로세스를 띄우면 84 프레임에 43분이 초기화로만 날아간다.
    """

    def __init__(
        self,
        model_path: str | Path,
        providers: list[str] | None = None,
        pad_to: int = 32,
        norm: str = "imagenet",
    ):
        import onnxruntime as ort  # 지연 import — contracts 는 ORT 없이도 쓰이게

        self.model_path = str(model_path)
        self.pad_to = pad_to
        self.norm = norm
        so = ort.SessionOptions()
        so.log_severity_level = 3  # ScatterND 경고가 수만 줄 쏟아진다
        if providers is None:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        t0 = time.time()
        self.session = ort.InferenceSession(self.model_path, so, providers=providers)
        self.session_init_s = time.time() - t0
        self.providers = self.session.get_providers()
        names = {i.name for i in self.session.get_inputs()}
        missing = {"left_image", "right_image"} - names
        if missing:
            raise RuntimeError(f"예상과 다른 ONNX 입력 이름: {names} (없음: {missing})")

    def infer(self, left_rgb: np.ndarray, right_rgb: np.ndarray, scale: float = 1.0) -> np.ndarray:
        """좌/우 RGB(uint8) → 원본 해상도 disparity(px, float32).

        scale<1 로 줄여 추론하면 disparity 도 같은 비율로 작아지므로 되돌린다.
        """
        h0, w0 = left_rgb.shape[:2]
        if scale != 1.0:
            size = (int(round(w0 * scale)), int(round(h0 * scale)))
            left_rgb = cv2.resize(left_rgb, size, interpolation=cv2.INTER_AREA)
            right_rgb = cv2.resize(right_rgb, size, interpolation=cv2.INTER_AREA)
        hs, ws = left_rgb.shape[:2]

        lp, ph, pw = _pad_to_multiple(left_rgb, self.pad_to)
        rp, _, _ = _pad_to_multiple(right_rgb, self.pad_to)
        feeds = {
            "left_image": _normalize(lp, self.norm),
            "right_image": _normalize(rp, self.norm),
        }
        disp = self.session.run(["disparity"], feeds)[0][0, 0]
        disp = disp[:hs, :ws]  # 패딩 제거

        if scale != 1.0:
            disp = cv2.resize(disp, (w0, h0), interpolation=cv2.INTER_LINEAR) / scale
        return np.ascontiguousarray(disp, dtype=np.float32)


def process_frame(
    backend: OnnxStereoBackend,
    in_dir: Path,
    out_dir: Path,
    scale: float = 1.0,
    min_disparity_px: float = 0.05,
    z_near_mm: float = 100.0,
    z_far_mm: float = 10000.0,
) -> dict:
    """작업 디렉토리 하나 처리 — 계약대로 읽고 자기 산출물만 더한다."""
    cam = CameraParams.from_json(in_dir / "cam.json")
    left = read_rgb(in_dir / "left.png")
    right = read_rgb(in_dir / "right.png")
    if left.shape != right.shape:
        raise ValueError(f"좌/우 해상도 불일치: {left.shape} vs {right.shape}")

    t0 = time.time()
    disp = backend.infer(left, right, scale=scale)
    infer_s = time.time() - t0

    # 산출물/메타 스키마는 백엔드 공통 writer 로 통일한다 (stereo_torch 와 비교 가능해야 하므로).
    return write_stereo_frame(
        out_dir, disp, cam,
        backend="ngc_onnx", model=Path(backend.model_path).name, license_note=LICENSE_NOTE,
        extra={"providers": backend.providers, "normalization": backend.norm,
               "scale": scale, "pad_to": backend.pad_to, "infer_s": round(infer_s, 4)},
        min_disparity_px=min_disparity_px, z_near_mm=z_near_mm, z_far_mm=z_far_mm,
    )


def find_frames(root: Path) -> list[Path]:
    """작업 디렉토리 자신 또는 하위 프레임 디렉토리들을 찾는다."""
    if (root / "left.png").exists():
        return [root]
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "left.png").exists())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="stereo 스테이지 (NGC FoundationStereo ONNX)")
    ap.add_argument("--in", dest="in_dir", required=True, help="left.png/right.png/cam.json 이 있는 디렉토리(또는 그 상위)")
    ap.add_argument("--out", dest="out_dir", default=None, help="기본값: --in 과 동일")
    ap.add_argument("--model", required=True, help="NGC deployable ONNX 경로")
    ap.add_argument("--scale", type=float, default=1.0, help="추론 해상도 배율(<1 이면 축소 후 복원)")
    ap.add_argument("--norm", default="imagenet", choices=["imagenet", "unit", "raw"])
    ap.add_argument("--pad-to", type=int, default=32)
    ap.add_argument("--provider", default="cuda", choices=["cuda", "tensorrt", "cpu"])
    ap.add_argument("--min-disparity-px", type=float, default=0.05)
    ap.add_argument("--z-near-mm", type=float, default=100.0)
    ap.add_argument("--z-far-mm", type=float, default=10000.0)
    args = ap.parse_args(argv)

    providers = {
        "cuda": ["CUDAExecutionProvider", "CPUExecutionProvider"],
        "tensorrt": ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
        "cpu": ["CPUExecutionProvider"],
    }[args.provider]

    in_root = Path(args.in_dir)
    out_root = Path(args.out_dir) if args.out_dir else in_root
    frames = find_frames(in_root)
    if not frames:
        print(f"처리할 프레임이 없다: {in_root}", file=sys.stderr)
        return 1

    backend = OnnxStereoBackend(args.model, providers=providers, pad_to=args.pad_to, norm=args.norm)
    print(f"세션 준비 {backend.session_init_s:.1f}s | providers={backend.providers} | 프레임 {len(frames)}개")
    if "CUDAExecutionProvider" in providers and "CUDAExecutionProvider" not in backend.providers:
        print("  ⚠️ CUDA EP 로 못 올라가고 CPU 로 돌고 있다 (프레임당 ~19s). 라이브러리 확인 필요.", file=sys.stderr)

    for f in frames:
        out = out_root / f.name if f != in_root else out_root
        m = process_frame(
            backend, f, out,
            scale=args.scale,
            min_disparity_px=args.min_disparity_px,
            z_near_mm=args.z_near_mm,
            z_far_mm=args.z_far_mm,
        )
        d = m["depth_mm"]
        print(
            f"  {f.name}: {m['infer_s']*1000:6.0f}ms  "
            f"disp {m['disparity_px']['min']:.1f}/{m['disparity_px']['median']:.1f}/{m['disparity_px']['max']:.1f}px  "
            f"depth median {d['median']:.0f}mm  valid {d['valid_frac']*100:.1f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
