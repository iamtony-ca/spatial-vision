"""M4 평가 — 예측 마스크를 sim GT 마스크와 비교한다.

    envs/seg_sam6d/bin/python -m spatial_vision.eval.eval_seg \
        --gt runs/sim01 --pred runs/sim01_ism runs/sim01_sam3 --targets full flange

왜 IoU 만으로는 부족한가
    M4 의 판정 기준은 두 가지다(PIPELINE_PLAN §M4):
      1. flange-only mask 의 IoU — 정밀 pose 경로가 실제로 쓰는 영역
      2. **검출 실패율** — IoU 평균은 "못 찾은 프레임"을 0 으로 섞어 희석한다. 4프레임 중 1프레임을
         통째로 놓친 것과 4프레임 모두 어중간한 것은 완전히 다른 고장인데 평균은 같아질 수 있다.
    그래서 `IoU(전체 평균)` 과 `IoU(검출된 프레임만)` 과 `검출률` 을 나눠서 낸다.

    precision/recall 도 같이 낸다: pose 입력으로는 **경계를 넘어 배경을 먹는 것(precision↓)** 이
    **덜 먹는 것(recall↓)** 보다 해롭다 — depth 를 배경까지 끌어와 초기 translation 을 망친다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

MASK_NAME = {"full": "mask_full.png", "flange": "mask_flange.png"}


def _load(path: Path) -> np.ndarray | None:
    if not path.exists():
        return None
    m = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return None if m is None else m > 127


def score(pred: np.ndarray, gt: np.ndarray) -> dict:
    inter = int((pred & gt).sum())
    union = int((pred | gt).sum())
    return {
        "iou": inter / union if union else 0.0,
        "precision": inter / int(pred.sum()) if pred.any() else 0.0,
        "recall": inter / int(gt.sum()) if gt.any() else 0.0,
        "pred_px": int(pred.sum()),
        "gt_px": int(gt.sum()),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="M4 segmentation 평가 (예측 vs sim GT)")
    ap.add_argument("--gt", required=True, help="캡처 디렉토리 (mask_full/mask_flange 보유)")
    ap.add_argument("--pred", nargs="+", required=True)
    ap.add_argument("--targets", nargs="+", default=["full", "flange"], choices=["full", "flange"])
    ap.add_argument("--gross-iou", type=float, default=0.1,
                    help="이 IoU 미만인데 검출은 된 것 = 오선택으로 센다")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    gt_root = Path(args.gt)
    frames = sorted([p for p in gt_root.glob("frame_*") if p.is_dir()]) or [gt_root]
    report = {"gt": str(gt_root), "n_frames": len(frames), "results": {}}

    print(f"\n═══ M4 segmentation | GT {gt_root} | {len(frames)} 프레임")
    print(f"{'백엔드':<18}{'타깃':<8}{'검출':>6}{'오선택':>7}{'IoU(전체)':>10}"
          f"{'IoU(정상)':>10}{'precision':>11}{'recall':>9}")

    for pred_root in map(Path, args.pred):
        for target in args.targets:
            rows, detected = [], 0
            for f in frames:
                gt = _load(f / MASK_NAME[target])
                if gt is None:
                    continue
                pred = _load((pred_root / f.name if f != gt_root else pred_root) / MASK_NAME[target])
                if pred is None or not pred.any():
                    # 검출 실패 = IoU 0. 평균에는 섞되 "검출분" 통계에서는 뺀다.
                    rows.append({"frame": f.name, "found": False, "iou": 0.0,
                                 "precision": 0.0, "recall": 0.0,
                                 "pred_px": 0, "gt_px": int(gt.sum())})
                    continue
                detected += 1
                rows.append({"frame": f.name, "found": True, **score(pred, gt)})

            if not rows:
                continue
            det_rows = [r for r in rows if r["found"]]
            # ★ 오선택: 마스크는 냈는데 GT 와 거의 겹치지 않는다 = 다른 인스턴스를 고른 것.
            # 검출 실패와 성격이 완전히 다른 고장인데 IoU 평균에 섞으면 구분되지 않는다
            # (PIPELINE_PLAN §M4 의 "유사 인스턴스 오선택률" 이 이것).
            gross = [r for r in det_rows if r["iou"] < args.gross_iou]
            ok_rows = [r for r in det_rows if r["iou"] >= args.gross_iou]
            m = lambda k, rs: float(np.mean([r[k] for r in rs])) if rs else 0.0
            summary = {
                "n_frames": len(rows), "n_detected": detected,
                "detection_rate": detected / len(rows),
                "n_gross_fail": len(gross), "gross_fail_frames": [r["frame"] for r in gross],
                "iou_all": m("iou", rows), "iou_detected": m("iou", det_rows),
                "iou_ok": m("iou", ok_rows),
                "precision": m("precision", det_rows), "recall": m("recall", det_rows),
                "frames": rows,
            }
            report["results"][f"{pred_root.name}/{target}"] = summary
            print(f"{pred_root.name:<18}{target:<8}{detected}/{len(rows):<4}{len(gross):>6}"
                  f"{summary['iou_all']:>10.3f}{summary['iou_ok']:>10.3f}"
                  f"{summary['precision']:>11.3f}{summary['recall']:>9.3f}")

    out = Path(args.out) if args.out else Path(args.pred[0]) / "metrics_seg.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n상세 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
