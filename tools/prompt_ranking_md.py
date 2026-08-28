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

HEAD = """# 실물 테스트 프롬프트 `full` — **237장 통합 서열**

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
- **웹사진 서열이다.** 실물(ZED X)에서 확인된 것은 `origin`이 `real-validated` 인 **2개뿐**이고
  둘 다 **78위·87위**다 — 🔴 **상위 N 컷으로 자르면 그 둘이 잘린다**(§39-15).
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    t = json.load(open(a.src))["full"]
    t = sorted(t, key=lambda x: (x[3]["rank_237"], -x[3]["human_79"]))
    L = [HEAD, f"## 서열 ({len(t)}개)", "",
         "| 순위 | 237 | 79장 | 158장 | score | 옛 | Δ | 실물 | slug | 프롬프트 |",
         "|---:|---:|---:|---:|---:|---:|---:|:-:|---|---|"]
    for x in t:
        m = x[3]
        d = f"{m['delta']:+.0f}"
        d = f"**{d}**" if abs(m["delta"]) >= 30 else d
        real = "★" if "real" in str(m.get("origin", "")) else ""
        L.append(f"| {m['rank_237']:.0f} | **{m['ok237']}** | {m['human_79']}/79 | "
                 f"{m['ok158']}/158 | {m['score_min']:.3f} | {m['rank_old']} | {d} | {real} | "
                 f"`{x[0]}` | `{x[2]}` |")
    L += ["", "★ = 실물 ZED X 사진에서 사용자가 눈으로 확인한 것(`origin: real-validated`).", ""]
    Path(a.out).write_text("\n".join(L))
    print(f"→ {a.out}  ({len(t)}행)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
