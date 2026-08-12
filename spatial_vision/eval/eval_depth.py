"""M3 평가 — 예측 depth 를 sim GT 와 비교한다.

    envs/stereo_onnx/bin/python -m spatial_vision.eval.eval_depth \
        --gt runs/sim01 --pred runs/sim01_torch runs/sim01_onnx

★ 왜 sim 인가
    실환경에서는 depth GT 자체가 없어 §CONSUMER 2.7.1 처럼 ChArUco 거리 같은 대리지표로만 잰다.
    sim 은 **픽셀별 정확한 GT** 가 있어 오차 지도를 그대로 볼 수 있다 — 실환경에서 불가능한 검증이다.

★ 양자화 주의
    예측 depth 는 `disparity.npy`(float) 에서 다시 계산한다. `depth.png` 는 16-bit **1mm 격자**라
    그걸로 평가하면 서브밀리 비교가 격자에 묻힌다(M2 에서 겪은 것과 같은 함정).
    GT 도 같은 이유로 `depth_gt.npy`(float32) 를 쓴다.

영역별로 나눠 본다 — 정밀 pose 경로가 실제로 쓰는 곳은 flange 상면이지 장면 전체가 아니다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def load_gt(d: Path) -> dict:
    gt = np.load(d / "depth_gt.npy").astype(np.float64)
    return {
        "depth": np.where(gt > 0, gt, np.nan),
        "mask_full": cv2.imread(str(d / "mask_full.png"), cv2.IMREAD_GRAYSCALE) > 127,
        "mask_flange": cv2.imread(str(d / "mask_flange.png"), cv2.IMREAD_GRAYSCALE) > 127,
        "cam": json.loads((d / "cam.json").read_text()),
        "meta": json.loads((d / "meta_capture.json").read_text()),
    }


def load_pred(d: Path, cam: dict) -> dict:
    """예측 disparity 에서 depth 를 다시 계산 (양자화 회피)."""
    disp = np.load(d / "disparity.npy").astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        depth = cam["fx"] * cam["baseline_mm"] / disp
    depth[~np.isfinite(depth) | (disp <= 0.05)] = np.nan
    meta = json.loads((d / "meta_stereo.json").read_text())
    return {"disp": disp, "depth": depth, "meta": meta}


def stats(err: np.ndarray, disp_err: np.ndarray | None = None) -> dict:
    if err.size == 0:
        return {"n": 0}
    a = np.abs(err)
    out = {
        "n": int(err.size),
        "mae_mm": float(a.mean()),
        "median_ae_mm": float(np.median(a)),
        "rmse_mm": float(np.sqrt((err ** 2).mean())),
        "bias_mm": float(err.mean()),          # 부호 있는 평균 — 계통 편차가 있으면 여기 드러난다
        "p95_ae_mm": float(np.percentile(a, 95)),
        "within_1mm": float((a <= 1).mean()),
        "within_2mm": float((a <= 2).mean()),
        "within_5mm": float((a <= 5).mean()),
    }
    if disp_err is not None and disp_err.size:
        out["disp_mae_px"] = float(np.abs(disp_err).mean())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="M3 depth 평가 (예측 vs sim GT)")
    ap.add_argument("--gt", required=True, help="캡처 디렉토리 (depth_gt.npy 보유)")
    ap.add_argument("--pred", nargs="+", required=True, help="백엔드별 예측 디렉토리")
    ap.add_argument("--out", default=None, help="metrics.json 경로 (기본: 첫 pred 옆)")
    args = ap.parse_args(argv)

    gt_root = Path(args.gt)
    frames = sorted(p.name for p in gt_root.iterdir()
                    if p.is_dir() and (p / "depth_gt.npy").exists())
    if not frames:
        print(f"GT 프레임 없음: {gt_root}")
        return 1

    results = {}
    for pred_root in map(Path, args.pred):
        per_region = {"all": [], "obj": [], "obj_core": [], "flange": [], "flange_core": []}
        infer_times, backend, model, lic = [], None, None, None
        for name in frames:
            g = load_gt(gt_root / name)
            pdir = pred_root / name
            if not (pdir / "disparity.npy").exists():
                continue
            p = load_pred(pdir, g["cam"])
            backend = p["meta"].get("backend"); model = p["meta"].get("model")
            lic = p["meta"].get("license")
            if p["meta"].get("infer_s"):
                infer_times.append(p["meta"]["infer_s"])

            both = np.isfinite(g["depth"]) & np.isfinite(p["depth"])
            gt_disp = g["cam"]["fx"] * g["cam"]["baseline_mm"] / g["depth"]
            # 실루엣 경계는 stereo 가 원래 못 맞추는 곳이라 지표를 지배한다(P95 가 튄다).
            # 정밀 pose refinement 가 실제로 쓰는 것은 **면**이므로 침식한 core 영역을 따로 본다.
            k5 = np.ones((5, 5), np.uint8)
            core_obj = cv2.erode(g["mask_full"].astype(np.uint8), k5, iterations=1) > 0
            core_fl = cv2.erode(g["mask_flange"].astype(np.uint8), k5, iterations=1) > 0
            regions = {
                "all": both,
                "obj": both & g["mask_full"],
                "flange": both & g["mask_flange"],
                "flange_core": both & core_fl,
                "obj_core": both & core_obj,
            }
            for k, m in regions.items():
                if m.sum() == 0:
                    continue
                per_region[k].append({
                    "frame": name,
                    **stats(p["depth"][m] - g["depth"][m], p["disp"][m] - gt_disp[m]),
                    "valid_frac": float(np.isfinite(p["depth"])[g["mask_full"]].mean()
                                        if k != "all" else np.isfinite(p["depth"]).mean()),
                })
        results[pred_root.name] = {
            "backend": backend, "model": model, "license": lic,
            "mean_infer_s": float(np.mean(infer_times)) if infer_times else None,
            "per_region": per_region,
        }

    # ── 출력 ────────────────────────────────────────────────────────────────
    for tag, r in results.items():
        print(f"\n═══ {tag}  (backend={r['backend']}, model={r['model']})")
        if r["mean_infer_s"]:
            print(f"    평균 추론 {r['mean_infer_s']*1000:.0f}ms/frame")
        print(f"    {'영역':8s} {'n(px)':>10s} {'MAE':>9s} {'median':>9s} {'RMSE':>9s} "
              f"{'bias':>9s} {'P95':>9s} {'≤1mm':>7s} {'≤2mm':>7s} {'disp':>8s}")
        for region, rows in r["per_region"].items():
            if not rows:
                continue
            agg = {k: float(np.mean([x[k] for x in rows]))
                   for k in ("mae_mm", "median_ae_mm", "rmse_mm", "bias_mm", "p95_ae_mm",
                             "within_1mm", "within_2mm", "disp_mae_px")
                   if k in rows[0]}
            n = int(np.mean([x["n"] for x in rows]))
            print(f"    {region:8s} {n:10d} {agg['mae_mm']:8.3f}m {agg['median_ae_mm']:8.3f}m "
                  f"{agg['rmse_mm']:8.3f}m {agg['bias_mm']:+8.3f}m {agg['p95_ae_mm']:8.3f}m "
                  f"{agg['within_1mm']*100:6.1f}% {agg['within_2mm']*100:6.1f}% "
                  f"{agg.get('disp_mae_px', float('nan')):7.4f}px")

    # 백엔드 간 직접 비교 (flange 영역 = 정밀 pose 가 실제로 쓰는 곳)
    if len(results) > 1:
        print("\n═══ 백엔드 비교 (flange_core 영역 MAE — 경계 제외한 면)")
        base = None
        for tag, r in results.items():
            rows = r["per_region"]["flange_core"]
            if not rows:
                continue
            mae = float(np.mean([x["mae_mm"] for x in rows]))
            if base is None:
                base, base_tag = mae, tag
                print(f"    {tag:22s} {mae:7.3f}mm  (기준)")
            else:
                print(f"    {tag:22s} {mae:7.3f}mm  ({mae/base:.2f}× vs {base_tag})")

    out = Path(args.out) if args.out else Path(args.pred[0]) / "metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n상세 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
