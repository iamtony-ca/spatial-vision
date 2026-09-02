#!/usr/bin/env python3
"""«두 선택 규칙이 같은 답을 냈다» 와 «같은 메커니즘으로 냈다» 를 **가른다**.

왜 이 도구가 따로 있나
    `tools/why_misselect.py` 는 프레임 **한 장**을 그림으로 본다. 이건 여러 프레임에서
    **`contracts.select_index` 의 3단 필터가 실제로 무엇을 했는지** 를 통계로 낸다.

    🔴 «단일 FOUP 씬에서 `score` 와 `center+0.9` 가 같은 마스크를 냈다»(§44-17)는
    **결과의 일치**이지 **메커니즘의 일치가 아니다.** 둘이 같아지는 길이 두 가지다 —
      **(A) 게이트 통과 후보가 1개** → 뒤 두 단계가 «할 일이 없다» = 사실상 같은 계산
      **(B) 통과 후보가 여럿인데 중앙 근접이 마침 최고점과 일치** → **우연한 일치**
    (A)면 «배포 조건에서 규칙이 비활성» 이라고 쓸 수 있고, (B)면 **씬이 조금만 바뀌어도 갈린다.**
    이 도구는 그 비율을 센다.

    ⚠️ **«FOUP 이 1개» ≠ «후보가 1개»** 다. SAM3 는 바닥·부품·배경까지 10~20개를 낸다.

출력
    프레임마다: 후보 수 · 점수게이트 통과 수 · 면적필터 통과 수 · 각 규칙이 고른 index ·
    일치 여부 · 일치했다면 그 이유가 (A)인지 (B)인지.

⚠️ 인터프리터는 **`envs/seg_sam3`** (SAM3 를 다시 돌린다). 프레임당 ~0.2s + 모델 로드 ~10s.

사용
    envs/seg_sam3/bin/python tools/select_rule_stats.py --in runs/S44_cap60 \\
        --prompt "cube shaped sealed plastic wafer pod" --confidence 0.05
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--ckpt", default="weights/sam3/sam3.pt")
    ap.add_argument("--confidence", type=float, default=0.05)
    ap.add_argument("--score-frac", type=float, default=0.9)
    ap.add_argument("--min-area-frac", type=float, default=0.3)
    ap.add_argument("--limit", type=int, default=0, help="앞 N 프레임만")
    ap.add_argument("--md-out", default=None)
    a = ap.parse_args(argv)

    import cv2
    import torch
    from PIL import Image

    from spatial_vision.contracts import select_index
    from spatial_vision.stages.segment_sam3 import build

    cap = Path(a.in_dir)
    frames = sorted(x for x in cap.glob("frame_*") if (x / "left.png").exists())
    if a.limit:
        frames = frames[:a.limit]
    processor, _device = build(Path(a.ckpt), a.confidence)   # build 는 (processor, device) 를 낸다

    lines: list[str] = []

    def out(s: str = "") -> None:
        print(s)
        lines.append(s)

    rows = []
    for f in frames:
        with torch.autocast("cuda", dtype=torch.bfloat16):
            state = processor.set_image(Image.open(f / "left.png").convert("RGB"))
            o = processor.set_text_prompt(state=state, prompt=a.prompt)
        if o["masks"] is None or len(o["masks"]) == 0:
            rows.append(None); continue
        np_ = lambda x: np.asarray(x.detach().float().cpu()) if hasattr(x, "detach") else np.asarray(x)
        m, s = np_(o["masks"]), np_(o["scores"]).reshape(-1)
        m = m.squeeze(1) if m.ndim == 4 else m
        m = m > 0.5 if m.dtype != bool else m

        # 🔴 `select_index` 의 3단을 **그대로** 다시 밟는다 (contracts.py:219-245)
        areas = m.reshape(len(m), -1).sum(1).astype(float)
        hi = s.max()
        keep1 = np.nonzero(s >= hi * a.score_frac)[0]
        if len(keep1) == 0:
            keep1 = np.array([int(s.argmax())])
        keep2 = keep1[areas[keep1] >= a.min_area_frac * areas[keep1].max()]

        i_score = select_index(m, s, "score", a.min_area_frac, a.score_frac)
        i_center = select_index(m, s, "center", a.min_area_frac, a.score_frac)

        gt_p = f / "mask_full.png"
        iou = np.nan
        if gt_p.exists():
            y = cv2.imread(str(gt_p), 0) > 127
            x = m[i_center]
            iou = float((x & y).sum() / max((x | y).sum(), 1))
        # ★ «1개만 통과» 가 아슬아슬한지 견고한지 — 2위/1위 점수비. 이 값이 `score_frac` 를 넘으면
        #   후보가 2개가 되고 그때부터 중앙 근접이 실제로 작동한다.
        ratio = float(np.sort(s)[-2] / hi) if len(s) > 1 else 0.0
        rows.append(dict(n=len(m), k1=len(keep1), k2=len(keep2), ratio=ratio,
                         same=int(i_score) == int(i_center), iou=iou))

    ok = [r for r in rows if r]
    if not ok:
        out("❌ 검출된 프레임이 없다")
        return 2
    n = len(ok)
    same = sum(r["same"] for r in ok)
    trivial = sum(1 for r in ok if r["k2"] == 1)                    # (A) 뒤 단계가 할 일 없음
    coincid = sum(1 for r in ok if r["k2"] > 1 and r["same"])       # (B) 우연한 일치
    differ = sum(1 for r in ok if not r["same"])

    out(f"# 선택 규칙 추적 — `{cap.name}` · {n}프레임 · 프롬프트 `{a.prompt}`")
    out()
    out(f"게이트 `score_frac={a.score_frac}` · 파편 필터 `min_area_frac={a.min_area_frac}` · "
        f"`--confidence {a.confidence}`")
    out()
    out("| 항목 | 값 |")
    out("|---|---|")
    out(f"| SAM3 후보 수 (중앙 / 최소~최대) | **{int(np.median([r['n'] for r in ok]))}** "
        f"/ {min(r['n'] for r in ok)}~{max(r['n'] for r in ok)} |")
    out(f"| 점수 게이트 통과 (중앙 / 최대) | **{int(np.median([r['k1'] for r in ok]))}** "
        f"/ {max(r['k1'] for r in ok)} |")
    out(f"| + 파편 필터 통과 (중앙 / 최대) | **{int(np.median([r['k2'] for r in ok]))}** "
        f"/ {max(r['k2'] for r in ok)} |")
    out(f"| `score` 와 `center` 가 **같은 것을 골랐다** | **{same}/{n}** ({100*same/n:.1f}%) |")
    out(f"| ↳ **(A) 통과 후보 1개** — 뒤 두 단계가 할 일 없음 | **{trivial}/{n}** ({100*trivial/n:.1f}%) |")
    out(f"| ↳ **(B) 통과 후보 여럿인데 마침 일치** | **{coincid}/{n}** ({100*coincid/n:.1f}%) |")
    out(f"| **갈렸다** | **{differ}/{n}** |")
    r2 = np.array([r["ratio"] for r in ok])
    out(f"| ★ **2위/1위 점수비** (중앙 / **최대**) | {np.median(r2):.3f} / **{r2.max():.3f}** |")
    out(f"| ↳ 게이트 `{a.score_frac}` 까지 여유 | **×{a.score_frac/max(r2.max(),1e-9):.2f}** "
        f"(2위가 최고점의 {100*a.score_frac:.0f}% 를 넘으면 후보가 2개가 된다) |")
    out()
    if differ == 0 and coincid == 0:
        out("→ ✅ **결과도 메커니즘도 같다** — 게이트를 통과한 후보가 항상 1개라 "
            "면적 필터·중앙 근접이 **실행은 되지만 결과에 관여하지 않는다**. "
            "이 조건에서는 `--select score` 와 등가라고 서술해도 된다.")
    elif differ == 0:
        out(f"→ 🔴 **결과는 같은데 메커니즘은 다르다** — {coincid}/{n} 프레임에서 "
            "**게이트를 통과한 후보가 여럿인데 중앙 근접이 마침 최고점과 일치**했다. "
            "**우연이고, 씬이 조금만 바뀌면 갈린다.** «등가» 라고 쓰면 안 되고 "
            "«이 표본에서 결과가 일치했다» 로 써야 한다.")
    else:
        out(f"→ 🔴 **갈린다** ({differ}/{n}) — 두 규칙은 이 조건에서 등가가 아니다.")
    out()
    out("⚠️ **«FOUP 이 1개» ≠ «후보가 1개»** 다 — 위 «후보 수» 는 바닥·부품·배경을 포함한다.")

    if a.md_out:
        Path(a.md_out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n→ {Path(a.md_out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
