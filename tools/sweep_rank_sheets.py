#!/usr/bin/env python3
"""프롬프트 스윕 결과를 **통과 순으로 정렬한 시트**로 낸다 — 통과·부분·실패 전부.

    envs/pose/bin/python tools/sweep_rank_sheets.py --run runs/psweep_domain4 --imgs assets/real_imgs

왜 따로 만드나
    `sam3_prompt_sweep.py` 가 내는 `matrix__<target>.png` 는 **JSON 순서**라, 프롬프트가 40개면
    2220×7000px 이 되어 «무엇이 좋았나» 가 한눈에 안 들어온다. 여기서는
      ① **통과 수 → score 최소값** 순으로 정렬하고
      ② **등급별로 파일을 쪼갠다**(pass / part / dead)
    그래서 «전부 보여주되 읽을 수 있게» 된다. 🔴 실패도 반드시 낸다 — «안 나온 것» 을 눈으로
    확인해야 «프롬프트가 틀렸나 이미지가 어려웠나» 를 가른다.

셀 주석
    `OK`/`NG` · `n=` 검출 인스턴스 수 · `s=` score
    ⚠️ **`score` 로 순위를 매기지 않는다** — 마스크 품질과 상관 r=+0.06 이다(교훈 #90).
      문턱 지표라 중앙값이 아니라 **최소값**(= 미검출까지의 여유)을 라벨에 찍는다.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib

import cv2
import numpy as np

CW, LW, TH = 226, 430, 26                       # 셀 폭 · 라벨 폭 · 셀 위 제목줄
TINT = {"pass": (40, 90, 40), "part": (30, 70, 95), "dead": (40, 40, 90)}
GROUPS = [("pass", "전 이미지 통과"), ("part", "부분 통과"), ("dead", "전 이미지 실패")]


def _tier(a):
    return "pass" if a["ok"] == a["n"] else ("dead" if a["ok"] == 0 else "part")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="스윕 결과 정렬 시트 (통과·실패 전부)")
    ap.add_argument("--run", required=True, help="스윕 출력 디렉토리 (results.json 보유)")
    ap.add_argument("--imgs", default="assets/real_imgs", help="원본 이미지 디렉토리 (대체 표시용)")
    ap.add_argument("--cell", type=int, default=CW)
    # ★ 목록이 커지면 한 장이 1만 px 을 넘어 «전부 보여주기» 가 «아무것도 안 보여주기» 가 된다
    #   (실측: 48행 → 14,728px). 등급 안에서 다시 쪼개고 파일명에 `_p1`·`_p2` 를 붙인다.
    #   🔴 정렬은 **쪼개기 전에** 끝나 있으므로 p1 이 상위권이다 — 순서를 믿어도 된다.
    ap.add_argument("--max-rows", type=int, default=16, help="한 장에 넣을 최대 행 수 (0=무제한)")
    a = ap.parse_args(argv)

    R = pathlib.Path(a.run)
    OUT = R / "sheets"; OUT.mkdir(parents=True, exist_ok=True)
    rows = json.loads((R / "results.json").read_text())
    rows = rows["rows"] if isinstance(rows, dict) and "rows" in rows else rows

    imgs = sorted({r["image"] for r in rows})
    by = {(r["target"], r["slug"], r["image"]): r for r in rows}
    agg = collections.defaultdict(lambda: {"n": 0, "ok": 0, "s": [], "p": "", "c": ""})
    for r in rows:
        g = agg[(r["target"], r["slug"])]
        g["n"] += 1; g["ok"] += bool(r.get("ok")); g["p"] = r["prompt"]; g["c"] = r.get("category") or ""
        if r.get("score") is not None:
            g["s"].append(r["score"])

    made = []
    for target in sorted({k[0] for k in agg}):
        keys = sorted({k[1] for k in agg if k[0] == target},
                      key=lambda s: (-agg[(target, s)]["ok"],
                                     -(min(agg[(target, s)]["s"]) if agg[(target, s)]["s"] else 0)))
        for g, gt in GROUPS:
            ks_all = [s for s in keys if _tier(agg[(target, s)]) == g]
            if not ks_all:
                continue
            step = a.max_rows if a.max_rows > 0 else len(ks_all)
            parts = [ks_all[i:i + step] for i in range(0, len(ks_all), step)]
            for pi, ks in enumerate(parts, 1):
                _draw(R, OUT, target, g, gt, ks, agg, by, imgs, a, made,
                      part=(pi, len(parts)))
    if not made:
        print("⚠️ 그린 것이 없다 — results.json 이 비었나?")
        return 1
    return 0


def _draw(R, OUT, target, g, gt, ks, agg, by, imgs, a, made, part=(1, 1)):
    """등급 한 덩이를 한 장으로 그린다. `part` 는 (몇 번째, 전체 몇 장)."""
    band = []
    for slug in ks:
        m = agg[(target, slug)]
        cells = []
        for im in imgs:
            ov = R / "ov" / im / target / f"{slug}.png"
            src = cv2.imread(str(ov)) if ov.exists() else None
            if src is None:                       # 오버레이가 없으면 원본을 깐다
                cand = sorted(pathlib.Path(a.imgs).glob(im.rsplit("_", 1)[0] + ".*"))
                src = cv2.imread(str(cand[0])) if cand else np.zeros((100, 100, 3), np.uint8)
            h, w = src.shape[:2]
            t = cv2.resize(src, (a.cell, int(round(a.cell * h / w))))
            r = by.get((target, slug, im), {})
            col = ((90, 230, 90) if r.get("ok") else
                   (60, 190, 240) if r.get("n_inst") else (60, 60, 245))
            bar = np.zeros((TH, a.cell, 3), np.uint8)
            cv2.putText(bar, im[:18], (4, 11), cv2.FONT_HERSHEY_SIMPLEX, 0.30,
                        (190, 190, 190), 1, cv2.LINE_AA)
            cv2.putText(bar, f"{'OK ' if r.get('ok') else 'NG '}n={r.get('n_inst', 0)}"
                             f" s={r.get('score', 0):.2f}", (4, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.32, col, 1, cv2.LINE_AA)
            cells.append(np.vstack([bar, t]))
        H = max(c.shape[0] for c in cells)
        cells = [np.vstack([c, np.zeros((H - c.shape[0], a.cell, 3), np.uint8)]) for c in cells]
        lab = np.full((H, LW, 3), TINT[g], np.uint8)
        mn = min(m["s"]) if m["s"] else 0.0
        cv2.putText(lab, f"{m['ok']}/{m['n']}   score_min {mn:.3f}", (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(lab, m["c"], (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (170, 200, 255), 1, cv2.LINE_AA)
        for i, ch in enumerate([m["p"][i:i + 44] for i in range(0, len(m["p"]), 44)][:3]):
            cv2.putText(lab, ch, (8, 70 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.46,
                        (120, 255, 160) if g == "pass" else (230, 230, 230), 1, cv2.LINE_AA)
        band.append(np.hstack([lab] + cells))
    W = max(c.shape[1] for c in band)
    grid = np.vstack([np.hstack([c, np.zeros((c.shape[0], W - c.shape[1], 3), np.uint8)])
                      for c in band])
    hdr = np.zeros((40, W, 3), np.uint8)
    pi, np_ = part
    tag = f"  [{pi}/{np_}]  (sorted by pass then score_min; part 1 = best)" if np_ > 1 else ""
    cv2.putText(hdr, f"[{target}] {gt} - {len(ks)} prompts{tag}  |  "
                     f"green=OK  cyan=detected but rejected  red=no detection",
                (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 1, cv2.LINE_AA)
    fn = f"rank__{target}__{g}" + (f"_p{pi}" if np_ > 1 else "") + ".png"
    cv2.imwrite(str(OUT / fn), np.vstack([hdr, grid]))
    made.append(fn)
    print(f"  → {OUT / fn}  {W}x{grid.shape[0] + 40}  ({len(ks)}행)")


if __name__ == "__main__":
    raise SystemExit(main())
