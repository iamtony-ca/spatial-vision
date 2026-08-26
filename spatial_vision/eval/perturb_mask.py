"""분할 마스크에 **부품 결손**을 주입한다 — 「flange 가 빠지면 pose 가 얼마나 틀리나」.

    envs/pose/bin/python -m spatial_vision.eval.perturb_mask \
        --in runs/seg_x --out runs/seg_x_drop100 --gt runs/fr_d50 --drop-frac 1.0

왜 필요한가
    실사진 프롬프트 스윕에서 **`full` 마스크가 top flange 를 통째로 빼먹는** 경우가 나왔다
    (반투명 주황 몸체에서 대부분의 프롬프트, `runs/promptsweep/report.md`).
    `pose_fp --primary full` 은 `mask_full` 을 `full.ply` 와 맞추는데 **pose 원점이 flange
    상면 중심**이므로, 빠진 것이 하필 기준 구조물이다. 그런데 그 결손은 면적의 4~6% 라
    **IoU·면적비·볼록성 같은 지표가 원리적으로 못 잡는다**(교훈 #6·#13).
    → 실물에서는 GT 가 없어 영향을 못 재므로, **sim 에서 결손만 주입해** 대가를 매긴다.

★ 교란 축은 «면적» 이 아니라 «어느 부품인가» 다
    기존 `perturb_depth`·`perturb_image` 는 전역 열화를 넣는다. 여기서는 **구조물 하나**를
    지운다 — 다른 종류의 고장이고, 그래서 다른 도구다.

⚠️ GT `mask_flange.png` 를 «어디를 지울지» 정하는 데만 쓴다. 결손 자체는 실물에서 실제로
   관측된 현상이고, GT 는 그 위치를 재현하는 수단일 뿐이다.
⚠️ 반투명·투명 몸체 캡처의 `mask_flange` 는 유효하지만 `mask_full` 은 무효다(cutout opacity,
   CLAUDE.md). 이 도구는 `mask_flange` 만 읽으므로 그 축과 무관하다.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np


def drop_region(mask: np.ndarray, part: np.ndarray, frac: float,
                dilate_px: int = 0) -> tuple[np.ndarray, int]:
    """`mask` 에서 `part` 의 **위쪽 `frac` 비율**을 지운다 → (새 마스크, 지운 픽셀 수).

    ★ «위쪽부터» 인 이유 — 관측된 실패가 «상면이 통째로 잘려 나가는» 형태였다
      (`cube shaped plastic case` 가 주황 몸체에서 flange 를 잘라낸 오버레이).
      무작위로 구멍을 뚫는 것과는 다른 고장이다. `frac=1.0` 이면 부품 전체를 지운다.
    """
    if not part.any() or frac <= 0:
        return mask.copy(), 0
    p = part
    if dilate_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate_px + 1,) * 2)
        p = cv2.dilate(p.astype(np.uint8), k).astype(bool)
    ys = np.nonzero(p)[0]
    y0, y1 = int(ys.min()), int(ys.max())
    cut = y0 + int(round(frac * (y1 - y0 + 1)))       # 이 행 미만을 지운다
    sel = np.zeros_like(p)
    sel[:cut] = p[:cut]
    out = mask & ~sel
    return out, int((mask & sel).sum())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="분할 마스크에 부품 결손을 주입")
    ap.add_argument("--in", dest="in_dir", required=True, help="분할 산출 디렉토리 (mask_*.png)")
    ap.add_argument("--out", dest="out_dir", required=True)
    ap.add_argument("--gt", required=True, help="캡처 디렉토리 — 지울 부품 마스크의 출처")
    ap.add_argument("--part", default="mask_flange.png", help="지울 부품 (GT 쪽 파일명)")
    ap.add_argument("--target", default="full", help="교란할 마스크 (mask_<target>.png)")
    ap.add_argument("--drop-frac", type=float, default=1.0,
                    help="부품의 위쪽 몇 %를 지우나. 1.0 = 부품 전체")
    ap.add_argument("--dilate-px", type=int, default=0,
                    help="부품 마스크를 키워서 지운다 (경계 여유)")
    a = ap.parse_args(argv)

    ind, outd, gtd = Path(a.in_dir), Path(a.out_dir), Path(a.gt)
    frames = sorted(p for p in ind.iterdir() if p.is_dir() and p.name.startswith("frame_"))
    if not frames:
        print(f"🔴 프레임이 없다: {ind}")
        return 1

    outd.mkdir(parents=True, exist_ok=True)
    n_ok = n_empty = n_nopart = 0
    dropped = []
    for f in frames:
        od = outd / f.name
        od.mkdir(exist_ok=True)
        # 🔴 부수 산출물(det/meta)을 같이 복사한다 — 하류가 읽는다. 마스크만 바꾸는 게 목적이니
        #    나머지는 손대지 않고 그대로 흘린다.
        for q in f.iterdir():
            if q.is_file() and q.name != f"mask_{a.target}.png":
                shutil.copy2(q, od / q.name)

        mp = f / f"mask_{a.target}.png"
        m = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
        if m is None:
            continue
        mb = m > 127
        if not mb.any():
            cv2.imwrite(str(od / mp.name), m)          # 원래 비어 있던 것은 그대로 둔다
            n_empty += 1
            continue
        gp = gtd / f.name / a.part
        g = cv2.imread(str(gp), cv2.IMREAD_GRAYSCALE)
        if g is None or not (g > 127).any():
            cv2.imwrite(str(od / mp.name), m)
            n_nopart += 1
            continue
        new, nd = drop_region(mb, g > 127, a.drop_frac, a.dilate_px)
        cv2.imwrite(str(od / mp.name), (new.astype(np.uint8) * 255))
        dropped.append(nd / max(int(mb.sum()), 1))
        n_ok += 1

    med = float(np.median(dropped)) if dropped else 0.0
    (outd / "meta_perturb_mask.json").write_text(json.dumps({
        "stage": "perturb_mask", "src": str(ind), "gt": str(gtd), "part": a.part,
        "target": a.target, "drop_frac": a.drop_frac, "dilate_px": a.dilate_px,
        "n_frames": len(frames), "n_perturbed": n_ok, "n_empty_kept": n_empty,
        "n_part_missing": n_nopart, "dropped_area_frac_median": round(med, 5),
    }, indent=2, ensure_ascii=False))
    print(f"== 마스크 교란 | {n_ok}/{len(frames)} 프레임 | 부품 `{a.part}` 위쪽 "
          f"{a.drop_frac:.0%} 제거 | 지운 면적 중앙 {med:.1%}")
    if n_empty:
        print(f"   · 원래 비어 있던 프레임 {n_empty}개는 그대로 뒀다")
    if n_nopart:
        print(f"   ⚠️ 부품 마스크가 없는 프레임 {n_nopart}개는 교란 안 됨")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
