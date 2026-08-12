"""스테이지 경계의 데이터 계약.

파이프라인의 모든 스테이지는 **작업 디렉토리** 하나를 읽고 자기 산출물만 더한다
(PIPELINE_PLAN.md §4). 모델마다 venv 가 달라 in-process 로 못 엮이기 때문에,
스테이지 간 통신은 디스크를 경유한다.

이 모듈은 numpy + opencv 만 의존한다 — 어느 venv 에서도 import 되어야 하므로
torch/onnxruntime 같은 백엔드 의존성을 여기 두지 않는다.

규약
----
- 길이 단위는 **mm**. (CAD·BOP·FoundationPose 와 맞춘다.)
- depth 는 16-bit PNG, 값 = mm, **0 = invalid**.
- pose 는 ``cam_T_obj`` (BOP 관례).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np

DEPTH_INVALID = 0
DEPTH_MAX_MM = 65535  # uint16 상한 — 이걸 넘는 depth 는 저장할 수 없다


@dataclass
class CameraParams:
    """rectified stereo rig 의 좌측 카메라 intrinsic + baseline.

    좌/우가 rectified 되어 있고 두 카메라의 intrinsic 이 같다고 가정한다
    (Isaac Sim rig 는 정의상 그렇고, 실카메라는 rectify 후 그렇게 된다).
    """

    fx: float
    fy: float
    cx: float
    cy: float
    baseline_mm: float
    width: int | None = None
    height: int | None = None

    @property
    def K(self) -> np.ndarray:
        return np.array(
            [[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )

    def scaled(self, sx: float, sy: float) -> "CameraParams":
        """이미지를 리사이즈했을 때의 intrinsic. baseline 은 물리량이라 불변."""
        return CameraParams(
            fx=self.fx * sx,
            fy=self.fy * sy,
            cx=self.cx * sx,
            cy=self.cy * sy,
            baseline_mm=self.baseline_mm,
            width=None if self.width is None else int(round(self.width * sx)),
            height=None if self.height is None else int(round(self.height * sy)),
        )

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def from_json(cls, path: str | Path) -> "CameraParams":
        d = json.loads(Path(path).read_text())
        if "K" in d:  # 3x3 행렬로 준 경우도 받아준다
            K = np.asarray(d.pop("K"), dtype=np.float64).reshape(3, 3)
            d.setdefault("fx", float(K[0, 0]))
            d.setdefault("fy", float(K[1, 1]))
            d.setdefault("cx", float(K[0, 2]))
            d.setdefault("cy", float(K[1, 2]))
        if "baseline_mm" not in d and "baseline_m" in d:
            d["baseline_mm"] = float(d.pop("baseline_m")) * 1000.0
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})


def read_rgb(path: str | Path) -> np.ndarray:
    """RGB uint8 (H,W,3) 로 읽는다. cv2 는 BGR 이므로 변환한다."""
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"이미지를 읽을 수 없음: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def save_depth_png(path: str | Path, depth_mm: np.ndarray) -> None:
    """depth(mm, float) → 16-bit PNG. 비유효·범위 밖은 0."""
    d = np.asarray(depth_mm, dtype=np.float64)
    bad = ~np.isfinite(d) | (d <= 0) | (d > DEPTH_MAX_MM)
    out = np.where(bad, 0, np.rint(d)).astype(np.uint16)
    if not cv2.imwrite(str(path), out):
        raise IOError(f"depth 저장 실패: {path}")


def load_depth_png(path: str | Path) -> np.ndarray:
    """16-bit PNG → depth(mm, float32). 0 은 NaN 으로 돌려준다."""
    d = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if d is None:
        raise FileNotFoundError(f"depth 를 읽을 수 없음: {path}")
    out = d.astype(np.float32)
    out[d == DEPTH_INVALID] = np.nan
    return out


def write_stereo_frame(
    out_dir,
    disparity_px: np.ndarray,
    cam: "CameraParams",
    *,
    backend: str,
    model: str,
    license_note: str,
    extra: dict | None = None,
    min_disparity_px: float = 0.05,
    z_near_mm: float = 100.0,
    z_far_mm: float = 10000.0,
) -> dict:
    """stereo 스테이지의 공통 산출물 writer.

    백엔드(PyTorch / ONNX)가 달라도 **산출물과 메타 스키마는 하나**여야 비교가 가능하다.
    각 스테이지가 따로 쓰면 조용히 갈라진다.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    disp = np.asarray(disparity_px, dtype=np.float32)
    depth = disparity_to_depth_mm(disp, cam, min_disparity_px=min_disparity_px)
    valid = np.isfinite(depth) & (depth >= z_near_mm) & (depth <= z_far_mm)
    depth_out = np.where(valid, depth, np.nan)

    np.save(out_dir / "disparity.npy", disp)
    save_depth_png(out_dir / "depth.png", depth_out)
    cv2.imwrite(str(out_dir / "valid.png"), (valid * 255).astype(np.uint8))

    meta = {
        "stage": "stereo",
        "backend": backend,
        "model": model,
        "license": license_note,
        "resolution": [int(disp.shape[0]), int(disp.shape[1])],
        "disparity_px": {
            "min": float(np.nanmin(disp)), "median": float(np.nanmedian(disp)),
            "max": float(np.nanmax(disp)),
        },
        "depth_mm": {
            "valid_frac": float(valid.mean()),
            "min": float(np.nanmin(depth_out)) if valid.any() else None,
            "median": float(np.nanmedian(depth_out)) if valid.any() else None,
            "max": float(np.nanmax(depth_out)) if valid.any() else None,
        },
        "confidence": None,  # 어느 백엔드도 confidence 를 내지 않는다. 만들어내지 않는다.
        **(extra or {}),
    }
    (out_dir / "meta_stereo.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


def disparity_to_depth_mm(
    disparity_px: np.ndarray, cam: CameraParams, min_disparity_px: float = 0.05
) -> np.ndarray:
    """rectified stereo 의 기본식: ``depth = fx * baseline / disparity``.

    disparity 가 0 근처면 depth 가 발산하므로 잘라낸다(NaN).
    """
    d = np.asarray(disparity_px, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        depth = (cam.fx * cam.baseline_mm) / d
    depth[~np.isfinite(d) | (d < min_disparity_px)] = np.nan
    return depth


def select_index(masks: "np.ndarray", scores=None, rule: str = "score",
                 min_area_frac: float = 0.3, score_frac: float = 0.9) -> int:
    """후보 여러 개 중 타깃 하나를 고른다.

    ★ `center` 는 **점수를 대체하는 규칙이 아니라 동점자 tie-break** 다.
      점수는 "이 후보가 찾는 물체를 닮았는가" 를 담는다. 동일 인스턴스가 여럿일 때만
      점수가 비슷해져 최대값 선택이 임의가 되는 것이고(FOUP 3대), 그 구간에서만
      "카메라가 타깃을 겨눈다" 는 씬 규약으로 가른다.

    ⚠️ 두 번 틀렸던 지점이다 —
      (1) 점수를 무시하고 중앙 근접만 쓰면 물체의 **작은 파편**이 뽑힌다(IoU 0.009).
      (2) 거기에 면적 필터만 더하면 이번엔 **배경(바닥면)** 이 뽑힌다(precision 0.001).
      → 점수 상위(max·score_frac 이상)로 **먼저 거르고**, 파편 제거용 면적 필터를 얹은 뒤,
        남은 후보에서 중앙에 가까운 것을 고른다.

    rule: score(최고 점수) | center(동점자 중 중앙 근접) | largest(면적 최대)
    """
    import numpy as np

    areas = masks.reshape(len(masks), -1).sum(1).astype(float)
    if rule == "largest":
        return int(np.argmax(areas))
    sc = None if scores is None else np.asarray(scores, dtype=float).reshape(-1)
    if rule != "center" or sc is None:
        return int(np.argmax(sc)) if sc is not None else int(np.argmax(areas))

    hi = sc.max()
    lo = hi * score_frac if hi > 0 else -np.inf
    keep = np.nonzero(sc >= lo)[0]
    if len(keep) == 0:
        keep = np.array([int(np.argmax(sc))])
    a_keep = areas[keep]
    keep = keep[a_keep >= min_area_frac * a_keep.max()]        # 파편 제거
    if len(keep) == 0:
        return int(np.argmax(sc))

    h, w = masks.shape[-2:]
    best, bestd = int(keep[0]), 1e18
    for i in keep:
        ys, xs = np.nonzero(masks[i])
        if not len(xs):
            continue
        d = float(np.hypot(xs.mean() - w / 2.0, ys.mean() - h / 2.0))
        if d < bestd:
            best, bestd = int(i), d
    return best
