"""SAM3 exemplar **참조 세트를 눈으로 확인**한다 — 무엇이 프롬프트로 들어가는가.

    envs/pose/bin/python -m spatial_vision.viz.ref_sheet \
        --refs assets/obj/foup_300_semi_r2/sam3_refs_flange_n25 --n-refs 3 \
        --out runs/overlay_demo/refs/refs_n25.png

왜 필요한가
    exemplar 경로에서 **분할의 성패는 참조 이미지가 거의 다 정한다**(원거리 참조로 근접을 질의하면
    IoU 0.044, 클린 참조로 랜덤화 질의를 하면 0.382). 그런데 참조는 자산 디렉토리 안의 PNG 라
    **아무도 안 본다.** 실물에서 분할이 무너졌을 때 *"질의가 이상한가, 참조가 이상한가"* 를
    가르려면 참조부터 봐야 한다.

무엇을 그리나
    · 참조 이미지 + **초록 박스**(`box_xywh_norm` 을 픽셀로 환산한 것 = 실제 프롬프트)
    · 캡션: 거리·고도·방위 · 밝기 중앙값/포화율 · 박스 면적비
    · **실제로 쓰이는 장에는 `[USED]`**, 안 쓰이는 장은 어둡게 — `--n-refs` 는 앞에서 N장을 자른다

🔴 **`--refs-mode chain`(러너 기본값)에서는 박스가 `ref_0` 에만 걸린다.**
   `add_prompt(frame_idx=0)` 이고 나머지 참조는 추적으로만 이어진다 → **ref_0 이 사실상 지배한다.**
   `--refs-mode independent` 는 참조마다 독립 질의라 N장이 대등하다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SAM3 exemplar 참조 세트 컨택트 시트")
    ap.add_argument("--refs", required=True, help="refs.json + ref_*.png 이 있는 디렉토리")
    ap.add_argument("--n-refs", type=int, default=3, help="실제 사용 장수 (앞에서 N장)")
    ap.add_argument("--mode", default="chain", choices=["chain", "independent"])
    ap.add_argument("--tile", type=int, default=460)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    rd = Path(a.refs)
    meta = json.loads((rd / "refs.json").read_text())
    refs = meta["refs"]
    tiles = []
    for i, r in enumerate(refs):
        img = cv2.imread(str(rd / r["image"]))
        if img is None:
            continue
        h, w = img.shape[:2]
        x, y, bw, bh = r["box_xywh_norm"]
        p0 = (int(x * w), int(y * h))
        p1 = (int((x + bw) * w), int((y + bh) * h))
        used = i < a.n_refs
        # ⚠️ chain 모드에서 박스가 실제로 걸리는 것은 **ref_0 뿐**이다 — 색으로 구분한다
        prompted = used and (a.mode == "independent" or i == 0)
        if not used:
            img = (img * 0.38).astype(np.uint8)          # 안 쓰이는 장은 어둡게
        cv2.rectangle(img, p0, p1, (0, 255, 0) if prompted else (0, 165, 255), 4)

        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        s = float(bw * bh)
        tile = cv2.resize(img, (a.tile, int(round(a.tile * h / w))), interpolation=cv2.INTER_AREA)
        bar = np.full((74, a.tile, 3), 22, np.uint8)
        tag = "[USED]" if used else "[unused]"
        tag += " [BOX PROMPT]" if prompted else (" (chain: 추적만)" if used else "")
        for k, (txt, col) in enumerate((
                (f"{i}  {r['image']}  {tag}", (0, 255, 255) if used else (120, 120, 120)),
                (f"src {r.get('source', '?')}", (185, 185, 185)),
                (f"dist {r.get('distance_m', 0)*1000:.0f}mm  elev {r.get('elevation_deg', 0):.0f}"
                 f"  azim {r.get('azimuth_deg', 0):.0f}", (185, 185, 185)),
                (f"box {100*s:.1f}% of frame   img med {np.median(g):.0f}  "
                 f"sat {100*(g > 250).mean():.1f}%", (185, 185, 185)))):
            cv2.putText(bar, txt, (6, 16 + 16 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.42, col, 1)
        tiles.append(np.concatenate([bar, tile], 0))

    if not tiles:
        print(f"❌ {rd} 에 참조 이미지가 없다")
        return 2
    cols = min(a.cols, len(tiles))
    rows = []
    for i in range(0, len(tiles), cols):
        ch = tiles[i:i + cols]
        ch += [np.zeros_like(ch[0])] * (cols - len(ch))
        rows.append(np.concatenate(ch, 1))
    sheet = np.concatenate(rows, 0)
    head = np.full((30, sheet.shape[1], 3), 30, np.uint8)
    cv2.putText(head, f"{rd.name}  |  {len(refs)} refs, using first {a.n_refs}, mode={a.mode}  "
                      f"|  green=box prompt  orange=tracked only  |  target={meta.get('target')}",
                (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), np.concatenate([head, sheet], 0))
    print(f"→ {out}  ({len(tiles)}장 중 앞 {a.n_refs}장 사용, mode={a.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
