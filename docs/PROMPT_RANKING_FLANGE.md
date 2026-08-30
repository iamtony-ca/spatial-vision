# `flange` 프롬프트 서열 — 웹 «어려운» 40장 **세 벌 합산** (2026-08-29)

> 정본은 `docs/RESULTS.md §39-32 ~ §39-39`. 현행 후보는 `assets/prompts/flange_top3.json`.
> 갱신은 `runs/psweep_flange8_web40c/graded_pooled.json` 에서 손으로 옮긴다(1회성 표).

## 어떻게 잰 값인가

- **정답은 사람이 직접 매겼다** — 프롬프트들이 «갈린» 이미지만 시트로 내고 사용자가 정답 칸을 골랐다.
  🔴 **어느 프롬프트의 출력도 정답으로 삼지 않았다** — 그렇게 하면 그 프롬프트가 자기 자신과 IoU 1.0 이라
  **8%p 자기편향**이 생긴다(§39-37b 에서 실측).
- **A** = 1차 40장(n=39~40) · **B** = 2차 40장 중 갈린 25장 · **C** = 3차 40장 중 갈린 18장.
  세 벌은 이미지가 서로 겹치지 않는다. 합산 n ≈ 83.
- **복수 정답**을 허용했다(FOUP 이 여러 대인 사진). ★ **«미검출이 정답»** 인 이미지도 3장 있었다.
- 판정 문턱 **IoU ≥ 0.90**.

## 🔴 읽을 때 함정 셋

1. **13개가 1위와 통계적으로 구분되지 않는다**(1위 95% 하한 **83.6%**). 순위표의 1~2위 차이는 **의미 없다**.
2. **표본별 «폭» 을 안정성으로 읽지 말 것** — n=40·25·18 이면 참 85% 라도 폭 중앙 11.4%p 가
   그냥 나온다(교훈 #105). 그래서 **합산**으로만 본다.
3. **웹 서열은 실물로 그대로 안 간다**(교훈 #92). 🟢 표시된 둘만 실물에서 확인된 것이다.

## 서열

| # | 합산 | 95% 구간 | A(40) | B(25) | C(18) | 축 | 핵명사 | 프롬프트 |
|---:|---:|:---:|---:|---:|---:|:-:|:-:|---|
| 1 | **91.6%** | [83.6, 95.9] | 37/40 | 24/25 | 15/18 | old | `plate` | `top mounting plate with a hole` 🟢 |
| 2 | **91.6%** | [83.6, 95.9] | 37/40 | 23/25 | 16/18 | H | `plate` | `a top mounting plate with a hole` |
| 3 | **89.2%** | [80.7, 94.2] | 34/40 | 24/25 | 16/18 | old | `bracket` | `black square plastic top bracket` |
| 4 | **89.2%** | [80.7, 94.2] | 35/40 | 22/25 | 17/18 | old | `bracket` | `black square bracket on top` 🟢 |
| 5 | **89.0%** | [80.4, 94.1] | 34/39 | 23/25 | 16/18 | old | `coupling` | `black square plastic top coupling` |
| 6 | **88.0%** | [79.2, 93.3] | 35/40 | 21/25 | 17/18 | H | `plate` | `top mounting plate` |
| 7 | **87.8%** | [79.0, 93.2] | 37/39 | 20/25 | 15/18 | old | `flange` | `black square top flange` |
| 8 | **84.1%** | [74.7, 90.5] | 34/39 | 21/25 | 14/18 | F | `flange` | `a black square plastic top flange` |
| 9 | **84.1%** | [74.7, 90.5] | 36/39 | 17/25 | 16/18 | old | `flange` | `square black plastic top flange` |
| 10 | **80.5%** | [70.6, 87.6] | 33/39 | 18/25 | 15/18 | old | `flange` | `black square plastic top flange` |
| 11 | **79.5%** | [69.6, 86.8] | 29/40 | 23/25 | 14/18 | I | `cap` | `black square plastic top cap with a hole` |
| 12 | **78.3%** | [68.3, 85.8] | 34/40 | 15/25 | 16/18 | old | `flange` | `black plastic square top flange` |
| 13 | **77.1%** | [67.0, 84.8] | 32/40 | 18/25 | 14/18 | D | `panel` | `black square plastic top panel` |
| 14 | **76.8%** | [66.6, 84.6] | 32/39 | 16/25 | 15/18 | J | `mount` | `black square top mount` |
| 15 | **74.4%** | [64.0, 82.6] | 32/39 | 15/25 | 14/18 | F | `flange` | `the black square top flange` 🔴 |
| 16 | **73.5%** | [63.1, 81.8] | 31/40 | 16/25 | 14/18 | I | `panel` | `black square plastic top panel with a hole` 🔴 |
| 17 | **73.2%** | [62.7, 81.6] | 28/39 | 19/25 | 13/18 | old | `flange` | `rectangular black plastic top flange` 🔴 |
| 18 | **72.3%** | [61.8, 80.8] | 28/40 | 18/25 | 14/18 | I | `lid` | `black square top lid with a center hole` 🔴 |
| 19 | **69.9%** | [59.3, 78.7] | 29/40 | 16/25 | 13/18 | H | `plate` | `square mounting plate with a hole` 🔴 |
| 20 | **63.9%** | [53.1, 73.4] | 27/40 | 12/25 | 14/18 | old | `flange` | `plastic black square top flange` 🔴 |

🟢 = 실물 ZED X 사진에서 사용자가 눈으로 고른 것(`real-validated`, §37-10).
🔴 = 1위와 **유의하게 나쁘다**(95% 상한 < 1위 95% 하한).

## 축 이름

| 축 | 뜻 |
|---|---|
| A | 색 제거 |
| B | 중심 홀 |
| C | 닻 |
| D | 핵명사 |
| F | 관사 |
| H | mounting |
| I | 승자조합 |
| J | 변주 |
| old | 기존(§37-17) |

## 현행 후보 3개 (계보를 벌렸다)

| 프롬프트 | 합산 | 계보 |
|---|---|---|
| `top mounting plate with a hole` 🟢 | **91.6%** | `mounting` |
| `black square bracket on top` 🟢 | 89.2% | `bracket` |
| `black square plastic top coupling` | 89.0% | `coupling` |

⚠️ 2위 `a top mounting plate with a hole` 는 1위와 **관사만 다르고 동점**이라 뺐다.
⚠️ 3위 `black square plastic top bracket` 은 4위와 **같은 계보**라 `real-validated` 쪽을 택했다.
