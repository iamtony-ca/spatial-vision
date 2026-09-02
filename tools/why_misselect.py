#!/usr/bin/env python3
"""«왜 엉뚱한 걸 집었나» — SAM3 **후보를 전부** 그리고 **어느 단계가 정답을 떨어뜨렸는지** 표시한다.

왜 필요한가
    분할이 틀렸을 때 원인은 **세 갈래**이고 처방이 전부 다르다(§42-6):
      ① **분할이 틀렸다** — 정답 마스크가 후보에 아예 없다        → 프롬프트·모델
      ② **점수가 틀렸다** — 정답은 있는데 SAM3 가 낮은 점수를 줬다 → 선택 규칙
      ③ **우리 규칙이 틀렸다** — 정답이 «필터» 에서 잘렸다          → `--select-score-frac`
    러너 산출물(`det_full.json`)은 **고른 것 하나만** 남기므로 이 셋을 못 가른다.
    이 도구는 SAM3 를 다시 돌려 **후보 전부**를 보여 준다.

읽는 법 (타일마다)
    · 채움 = 그 후보의 마스크 · **초록 굵은 윤곽 = GT**(있을 때)
    · 머리글 = `score` · 면적비 · 중심이탈 · GT 대비 IoU
    · 꼬리표 — **`★선택됨`**(현행 규칙이 고른 것) · **`✅정답`**(IoU 최대) ·
      `🔴점수컷`(점수 게이트에서 탈락) · `🔴면적컷`(파편 필터에서 탈락)
    🔴 **`✅정답` 에 `🔴점수컷` 이 같이 붙어 있으면 그것이 ③ 이다** — 분할은 맞았는데
       우리 규칙이 버린 것이고, `--select-score-frac 0` 으로 고쳐진다.

⚠️ 인터프리터는 **`envs/seg_sam3`**. SAM3 를 다시 돌리므로 프레임당 ~1초 + 모델 로드 ~10초.

사용
    envs/seg_sam3/bin/python tools/why_misselect.py --in runs/zx_n30 \\
        --pick frame_0016,frame_0019 --prompt "cube shaped sealed plastic wafer pod" \\
        --out runs/why.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="in_dir", required=True, help="캡처 디렉토리")
    ap.add_argument("--pick", required=True, help="프레임 이름(쉼표). 예 frame_0016,frame_0019")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--ckpt", default="weights/sam3/sam3.pt")
    ap.add_argument("--confidence", type=float, default=0.15)
    ap.add_argument("--score-frac", type=float, default=0.9, help="현행 점수 게이트 (표시용)")
    ap.add_argument("--min-area-frac", type=float, default=0.3, help="현행 파편 필터 (표시용)")
    ap.add_argument("--width", type=int, default=520, help="타일 폭")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    import torch
    from PIL import Image
    from spatial_vision.contracts import select_index
    from spatial_vision.stages.segment_sam3 import build

    cap = Path(a.in_dir)
    frames = [cap / x.strip() for x in a.pick.split(",") if x.strip()]
    frames = [f for f in frames if (f / "left.png").exists()]
    if not frames:
        print(f"❌ `{a.in_dir}` 에서 프레임을 못 찾았다", file=sys.stderr); return 2

    proc, _ = build(Path(a.ckpt), a.confidence)
    rows = []
    for fr in frames:
        img = cv2.imread(str(fr / "left.png"))
        H, W = img.shape[:2]
        gt_p = fr / "mask_full.png"
        gt = (cv2.imread(str(gt_p), 0) > 127) if gt_p.exists() else None

        with torch.autocast("cuda", dtype=torch.bfloat16):
            st = proc.set_image(Image.open(fr / "left.png").convert("RGB"))
            out = proc.set_text_prompt(state=st, prompt=a.prompt)
        npf = (lambda x: np.asarray(x.detach().float().cpu())
               if hasattr(x, "detach") else np.asarray(x))
        m, s = npf(out["masks"]), npf(out["scores"]).reshape(-1)
        m = (m.squeeze(1) if m.ndim == 4 else m)
        m = m > 0.5 if m.dtype != bool else m
        if not len(m):
            print(f"    ⚠️ {fr.name}: 후보 0개 — 건너뛴다"); continue

        ar = m.reshape(len(m), -1).sum(1).astype(float)
        iou = (np.array([(x & gt).sum() / max((x | gt).sum(), 1) for x in m])
               if gt is not None else np.full(len(m), np.nan))
        sel = int(select_index(m, s, "center", a.min_area_frac, a.score_frac))
        best = int(np.nanargmax(iou)) if gt is not None else -1
        # 현행 규칙이 어디서 걸렀는지 재현 (표시 전용)
        lo = s.max() * a.score_frac
        keep = np.nonzero(s >= lo)[0]
        keep2 = keep[ar[keep] >= a.min_area_frac * ar[keep].max()] if len(keep) else keep

        tiles = []
        for i in np.argsort(-s):
            t = img.copy()
            col = (0, 255, 76) if i == best else (255, 0, 128)
            t[m[i]] = (0.62 * t[m[i]] + 0.38 * np.array(col)).astype(np.uint8)
            cs, _ = cv2.findContours(m[i].astype(np.uint8), cv2.RETR_EXTERNAL,
                                     cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(t, cs, -1, col, max(2, W // 500))
            if gt is not None:               # GT 는 늘 초록 굵은 선
                cs, _ = cv2.findContours(gt.astype(np.uint8), cv2.RETR_EXTERNAL,
                                         cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(t, cs, -1, (0, 255, 0), max(3, W // 380))
            ys, xs = np.nonzero(m[i])
            off = float(np.hypot(xs.mean() / W - .5, ys.mean() / H - .5)) if len(xs) else 9.0
            # 🔴 `cv2.putText` 는 한글을 못 그린다 — **이미지 안 글자는 ASCII 만** 쓴다
            #    (첫 판이 «?????» 로 깨졌다). 한글 설명은 로그·문서에 둔다.
            tag = []
            if i == sel:
                tag.append("<< PICKED")
            if i == best:
                tag.append("** TRUE (best IoU)")
            if i not in keep:
                tag.append("[X] cut by SCORE gate")
            elif i not in keep2:
                tag.append("[X] cut by AREA filter")
            s_ = a.width / W
            t = cv2.resize(t, (a.width, int(H * s_)))
            bar = np.zeros((44, a.width, 3), np.uint8)
            cv2.putText(bar, f"#{i} score {s[i]:.3f}  area {ar[i] / ar.max():.2f}  off {off:.2f}"
                             + ("" if gt is None else f"  IoU {iou[i]:.3f}"),
                        (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1)
            cv2.putText(bar, "  ".join(tag) or "-", (6, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.46,
                        (0, 255, 76) if any("TRUE" in x for x in tag) else (255, 255, 0), 1)
            tiles.append(np.concatenate([bar, t], 0))

        hdr = np.zeros((30, a.width * len(tiles), 3), np.uint8)
        cv2.putText(hdr, f"{fr.name}  prompt: {a.prompt}  (score-frac {a.score_frac}, "
                         f"min-area-frac {a.min_area_frac})  |  GT = thick GREEN outline",
                    (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        h = max(t.shape[0] for t in tiles)
        tiles = [np.pad(t, ((0, h - t.shape[0]), (0, 0), (0, 0))) for t in tiles]
        rows.append(np.concatenate([hdr, np.concatenate(tiles, 1)], 0))
        v = ("③ 우리 규칙이 버렸다 (`--select-score-frac 0`)" if best not in keep else
             "① 분할이 틀렸다" if gt is not None and iou[best] < 0.3 else
             "정상 (선택 = 정답)" if sel == best else "② 점수·중앙 규칙이 갈렸다")
        print(f"    {fr.name}: 후보 {len(m)}개 · 선택 #{sel} · 정답 #{best} → **{v}**")

    if not rows:
        print("❌ 그릴 것이 없다", file=sys.stderr); return 2
    w = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0))) for r in rows]
    o = Path(a.out)
    o.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(o), np.concatenate(rows, 0))
    print(f"\n→ {o.resolve()}")
    print("🔴 **`✅정답` 에 `🔴점수컷` 이 같이 붙었으면** 분할은 맞았고 **우리 규칙이 버린 것**이다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
