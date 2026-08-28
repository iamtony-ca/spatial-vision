#!/usr/bin/env python3
"""`assets/prompts/real_testset.json` 을 읽어 **읽기용 서열 표**(`docs/PROMPT_RANKING.md`)를 낸다.

왜 도구로 두나
    표를 손으로 쓰면 JSON 과 어긋난다. **수치의 정본은 JSON 의 메타**이고 이 파일은 그 렌더링이다.
    서열이 갱신될 때마다 이걸 다시 돌린다(추론·계산 0, 1초).

🔴 `runs/` 에 두지 않는다 — `runs/` 는 통째로 `.gitignore` 라서 다른 PC 로 안 넘어간다.
"""
import argparse
import json
from pathlib import Path

SRC = Path("assets/prompts/real_testset.json")
OUT = Path("docs/PROMPT_RANKING.md")

HEAD = """# 실물 테스트 프롬프트 `full` — **237장 통합 서열 + 실물 3런**

> 이 파일은 **`assets/prompts/real_testset.json` 의 렌더링**이다. 수치의 정본은 그 JSON 의 메타이고,
> 실험 경위·해석의 정본은 **`docs/RESULTS.md §39`** 다. 갱신은 `tools/prompt_ranking_md.py`.

## 열 읽는 법

- **`237`** = `79장 + 158장`. 🔴 **자가 다른 두 수의 합**이다.
- **`79장`** = 68개 프롬프트가 «서로 다른 마스크» 를 낸 79장에서 **사용자가 직접 판정**한 통과 수.
  이 데이터에 붙은 **유일한 사람 라벨**이고 **가장 믿을 수 있는 수**다.
- **`158장`** = 나머지 158장. 사람 라벨이 없어 **«자기를 뺀 나머지 135개의 과반과 합의하는가»** 로 잰다.
  🔴 이 규칙은 79장에서 사람 판정과 **85.7% 일치**했고, **«다 같이 틀린» 이미지가 3장** 있었다.
  ⚠️ 158장은 **천장에 눌려 변별력이 낮다**(통과율 ≥95% 가 39/68) — **두 열이 어긋나면 `79장` 을 믿는다.**
- **`score`** = SAM3 검출 자신감의 최소값(웹 9장 기준). 🔴 **품질이 아니라 «필요한 문턱» 이다** —
  낮은 것은 `--text-conf 0.05` 에서만 쓸 수 있다(기본 0.15 에서 프레임을 통째로 놓친다).
- **`옛`·`Δ`** = `score_min` 내림차순이던 옛 순위와 변동(30 이상 굵게).

## 🔴 함정

- **동점이 매우 많다** — 1~2위 차는 무의미하고 수십 위 규모만 읽는다.
  30~110위는 사실상 **평지**다(ok237 이 229→209 로 20장 차이인데 그 안에 78개가 들어 있다).
- **slug(`f001`…)은 프롬프트에 붙박이라 순서대로가 아니다** — 마스크·라벨·군집이 slug 로 참조된다.
- **웹사진 서열이다.** 🔴 **상위 N 컷으로 자르면 안 된다**(§39-15·§39-21) — 실물 3런을 통과한 58개 중
  **22개(38%)가 웹 60위 밖**이고, 실물 11·12위가 웹 70·93위다.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    t = json.load(open(a.src))["full"]
    t = sorted(t, key=lambda x: (x[3]["rank_237"], -x[3]["human_79"]))

    # ★ 실물 3런 결과를 열로 붙인다 — 「웹 순위」와 「실물 순위」는 **다른 것을 잰다**(§39-19a)
    real = {}
    p = Path("assets/prompts/real_pass58.json")
    if p.exists():
        real = {x[0]: x[3] for x in json.loads(p.read_text())["full"]}
    cur = []
    p = Path("assets/prompts/real_current.json")
    if p.exists():
        cur = [(x[2], x[3].get("role", "")) for x in json.loads(p.read_text())["full"]]

    L = [HEAD]
    if cur:
        L += ["## 🟢 현행 실험군 — `assets/prompts/real_current.json`", "",
              f"**{len(cur)}개.** pose 까지 돌리는 팔은 이것뿐이다. 넓히는 조건은 "
              "«오선택 축을 열 때»·«개체·조명이 바뀔 때» 뿐(§39-30).", "",
              "| 프롬프트 | 역할 |", "|---|---|"]
        L += [f"| `{s}` | {r} |" for s, r in cur]
        L += [""]
    L += [f"## 서열 ({len(t)}개)", "",
          "🔴 **`실물` 열은 웹 열과 다른 것을 잰다** — 웹은 «사람이 판정한 마스크 품질», "
          "실물은 «전 이미지 통과 → `score` 최소값» 즉 **검출 여유**다. 실물에서는 갈린 이미지가 "
          "0장이라 품질 축이 **측정되지 않았다**(§39-19a). 빈칸 = 실물 3런에서 **탈락**.", "",
          "| 순위 | 237 | 79장 | 158장 | score | 옛 | Δ | **실물** | slug | 프롬프트 |",
          "|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for x in t:
        m = x[3]
        d = f"{m['delta']:+.0f}"
        d = f"**{d}**" if abs(m["delta"]) >= 30 else d
        rr = real.get(x[0])
        rcol = f"**{rr['real_rank']}**" if rr else "—"
        L.append(f"| {m['rank_237']:.0f} | **{m['ok237']}** | {m['human_79']}/79 | "
                 f"{m['ok158']}/158 | {m['score_min']:.3f} | {m['rank_old']} | {d} | {rcol} | "
                 f"`{x[0]}` | `{x[2]}` |")
    L += ["", f"**실물** = 실물 3런(1차·50cm·28cm) **전부 통과한 {len(real)}개**의 평균 순위. "
              "빈칸은 어느 라운드에선가 떨어진 것 — 버린 게 아니라 **대기**다"
              "(`real_pass58.json` 등의 `_dropped*`).", ""]
    Path(a.out).write_text("\n".join(L))
    print(f"→ {a.out}  ({len(t)}행)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
