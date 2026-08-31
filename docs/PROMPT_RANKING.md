# 실물 테스트 프롬프트 `full` — **237장 통합 서열 + 실물 3런**

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

## 🟢 현행 실험군 — `assets/prompts/real_current.json`

**4개.** pose 까지 돌리는 팔은 이것뿐이다. 넓히는 조건은 «오선택 축을 열 때»·«개체·조명이 바뀔 때» 뿐(§39-30).

★★ **`--mode prompts` 로 넷을 한 런에서 돌린다** (§41-10) — 프롬프트마다 `RP1@<tag>`·`RH1@<tag>` 두 팔이 붙고, `report.md` 가 **「검출 → pose → 이탈 → 좌우 `|Δdx|`」 순서의 전용 표**를 낸다.

```bash
envs/pose/bin/python tools/run_group_a.py --in <촬영> --out <출력> \
    --no-exemplar --mode combo,prompts \
    --text-prompt "cube shaped sealed plastic wafer pod" \
    --text-prompt-flange "top mounting plate with a hole" --text-conf-flange 0.15
```

- 🔴 **초기값이 달라지는 비교**라 게이트 후퇴율로 판정하면 안 된다(교훈 #82). 갈리는 축은 **«검출되느냐» 하나**다(§37-5·§39-17) — 전 프레임 통과한 것이 여럿이면 그때 **좌우 `|Δdx|`** 로 고른다.
- 🔴 **이 넷에는 색어가 하나도 없다** — `black` 하나를 붙이면 `score` 가 0.977 → 0.420 으로 절반 넘게 깎인다(§39-27a). 몸체 3종 어디에도 그대로 쓴다.
- **`flange` 는 이 파일이 아니다** → `assets/prompts/flange_real_top2.json` **2개** (실물 3거리에서 20 → 2, §41). 서열 표는 `docs/PROMPT_RANKING_FLANGE.md`.

| 프롬프트 | 역할 |
|---|---|
| `cube shaped sealed plastic wafer pod` | A — 웹 2.5위·실물 1위. **양쪽 1위**이자 기준선 |
| `plastic cube shaped sealed wafer pod` | W — **웹 1위**(사람 판정 78/79, 최고). A 와 «어순» 만 다르다 |
| `boxy sealed plastic wafer pod` | B — **실물 3위**. 형상어가 `boxy` 로 다르다 |
| `a boxy plastic object` | C — 🔴 **대조군**. 도메인 낱말이 없다 (성능 서열에 섞지 말 것) |

## 서열 (136개)

🔴 **`실물` 열은 웹 열과 다른 것을 잰다** — 웹은 «사람이 판정한 마스크 품질», 실물은 «전 이미지 통과 → `score` 최소값» 즉 **검출 여유**다. 실물에서는 갈린 이미지가 0장이라 품질 축이 **측정되지 않았다**(§39-19a). 빈칸 = 실물 3런에서 **탈락**.

| 순위 | 237 | 79장 | 158장 | score | 옛 | Δ | **실물** | slug | 프롬프트 |
|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | **236** | 78/79 | 158/158 | 0.973 | 5 | +4 | **14** | `f005` | `plastic cube shaped sealed wafer pod` |
| 2 | **235** | 77/79 | 158/158 | 0.977 | 2 | -0 | **1** | `f002` | `cube shaped sealed plastic wafer pod` |
| 2 | **235** | 77/79 | 158/158 | 0.977 | 4 | +2 | **2** | `f004` | `CUBE SHAPED SEALED PLASTIC WAFER POD` |
| 5 | **234** | 77/79 | 157/158 | 0.949 | 12 | +7 | **20** | `f012` | `cube shaped plastic sealed wafer pod` |
| 5 | **234** | 76/79 | 158/158 | 0.852 | 29 | +24 | **16** | `f029` | `cube shaped sealed plastic wafer magazine` |
| 5 | **234** | 76/79 | 158/158 | 0.420 | 70 | **+65** | **6** | `f070` | `black cube shaped sealed plastic wafer pod` |
| 8 | **233** | 76/79 | 157/158 | 0.680 | 51 | **+42** | — | `f051` | `cube shaped sealed polymer wafer pod` |
| 8 | **233** | 75/79 | 158/158 | 0.953 | 11 | +2 | **26** | `f011` | `cubeshaped sealed plastic wafer pod` |
| 8 | **233** | 75/79 | 158/158 | 0.867 | 26 | +18 | — | `f026` | `cube shaped sealed resin wafer pod` |
| 8 | **233** | 75/79 | 158/158 | 0.684 | 50 | **+42** | **21** | `f050` | `cube shaped sealed semiconductor plastic wafer pod` |
| 14 | **232** | 76/79 | 156/158 | 0.977 | 3 | -11 | **23** | `f003` | `blocky sealed plastic wafer pod` |
| 14 | **232** | 76/79 | 156/158 | 0.824 | 32 | +18 | — | `f032` | `sealed wafer container, a cube shaped plastic case` |
| 14 | **232** | 76/79 | 156/158 | 0.742 | 43 | +29 | **40** | `f043` | `cube shaped semiconductor plastic wafer pod` |
| 14 | **232** | 74/79 | 158/158 | 0.930 | 15 | +1 | **58** | `f015` | `boxlike sealed plastic wafer pod` |
| 14 | **232** | 74/79 | 158/158 | 0.887 | 22 | +8 | **15** | `f022` | `large cube shaped sealed plastic wafer pod` |
| 14 | **232** | 74/79 | 158/158 | 0.730 | 44 | **+30** | **39** | `f044` | `cube shaped sealed plastic semiconductor wafer pod` |
| 14 | **232** | 74/79 | 158/158 | 0.715 | 46 | **+32** | **48** | `f046` | `a sealed boxy plastic wafer carrier with a removable front door` |
| 20 | **231** | 74/79 | 157/158 | 0.953 | 10 | -10 | **7** | `f010` | `a cube shaped sealed plastic wafer pod` |
| 20 | **231** | 74/79 | 157/158 | 0.816 | 37 | +17 | **38** | `f037` | `a boxy sealed plastic wafer pod` |
| 20 | **231** | 74/79 | 157/158 | 0.816 | 38 | +18 | — | `f038` | `clear cube shaped sealed plastic wafer pod` |
| 20 | **231** | 74/79 | 157/158 | 0.605 | 54 | **+34** | — | `f054` | `sealed wafer container, a boxy plastic object` |
| 20 | **231** | 73/79 | 158/158 | 0.914 | 18 | -2 | **19** | `f018` | `cube like sealed plastic wafer pod` |
| 28 | **230** | 75/79 | 155/158 | 0.691 | 49 | +21 | **42** | `f049` | `boxy silicon plastic wafer pod` |
| 28 | **230** | 74/79 | 156/158 | 0.824 | 33 | +5 | **29** | `f033` | `boxy sealed plastic wafer case` |
| 28 | **230** | 74/79 | 156/158 | 0.207 | 98 | **+70** | **41** | `f098` | `boxy sealed plastic wafer box` |
| 28 | **230** | 73/79 | 157/158 | 0.969 | 6 | -22 | **18** | `f006` | `box shaped sealed plastic wafer pod` |
| 28 | **230** | 73/79 | 157/158 | 0.957 | 7 | -21 | **3** | `f007` | `boxy sealed plastic wafer pod` |
| 28 | **230** | 73/79 | 157/158 | 0.957 | 8 | -20 | **4** | `f008` | `Boxy sealed plastic wafer pod` |
| 28 | **230** | 73/79 | 157/158 | 0.957 | 9 | -19 | **9** | `f009` | `boxy sealed plastic wafer pod.` |
| 28 | **230** | 73/79 | 157/158 | 0.934 | 14 | -14 | **8** | `f014` | `the cube shaped sealed plastic wafer pod` |
| 28 | **230** | 73/79 | 157/158 | 0.824 | 34 | +6 | **22** | `f034` | `the boxy sealed plastic wafer pod` |
| 28 | **230** | 73/79 | 157/158 | 0.531 | 61 | **+33** | — | `f061` | `sealed cube shaped wafer carrier` |
| 28 | **230** | 72/79 | 158/158 | 0.844 | 30 | +2 | — | `f030` | `cube shaped sealed polycarbonate wafer pod` |
| 37 | **229** | 74/79 | 155/158 | 0.836 | 31 | -6 | — | `f031` | `blocky semiconductor plastic wafer pod` |
| 37 | **229** | 73/79 | 156/158 | 0.520 | 62 | +25 | — | `f062` | `cube shaped sealed plastic wafer case` |
| 37 | **229** | 73/79 | 156/158 | 0.320 | 78 | **+41** | — | `f078` | `cube shaped sealed plastic wafer canister` |
| 37 | **229** | 72/79 | 157/158 | 0.204 | 99 | **+62** | **33** | `f099` | `cube shaped sealed plastic wafer crate` |
| 37 | **229** | 71/79 | 158/158 | 0.895 | 20 | -17 | **51** | `f020` | `cube shaped sealed wafer pod` |
| 37 | **229** | 71/79 | 158/158 | 0.820 | 36 | -1 | **35** | `f036` | `cube-shaped sealed plastic wafer pod` |
| 37 | **229** | 71/79 | 158/158 | 0.781 | 40 | +3 | **13** | `f040` | `cube shaped sealed silicon plastic wafer pod` |
| 46 | **228** | 73/79 | 155/158 | 0.355 | 73 | +27 | — | `f073` | `blocky sealed semiconductor plastic wafer pod` |
| 46 | **228** | 72/79 | 156/158 | 0.867 | 25 | -21 | — | `f025` | `the sealed wafer container, a cube shaped plastic case` |
| 46 | **228** | 72/79 | 156/158 | 0.432 | 69 | +23 | — | `f069` | `cube shaped sealed acrylic wafer pod` |
| 46 | **228** | 72/79 | 156/158 | 0.252 | 87 | **+41** | — | `f087` | `plastic pod for wafer storage` |
| 46 | **228** | 71/79 | 157/158 | 0.934 | 13 | **-33** | **5** | `f013` | `boxy sealed plastic wafer pod on a table` |
| 46 | **228** | 71/79 | 157/158 | 0.777 | 41 | -5 | — | `f041` | `clean cube shaped sealed plastic wafer pod` |
| 46 | **228** | 71/79 | 157/158 | 0.551 | 59 | +13 | — | `f059` | `sealed wafer container, a square plastic box with a handle on the side` |
| 46 | **228** | 71/79 | 157/158 | 0.539 | 60 | +14 | — | `f060` | `chunky sealed plastic wafer pod` |
| 46 | **228** | 70/79 | 158/158 | 0.988 | 1 | **-45** | **10** | `f001` | `Entegris cube shaped sealed plastic wafer pod` |
| 46 | **228** | 70/79 | 158/158 | 0.891 | 21 | -25 | — | `f021` | `Shin-Etsu cube shaped sealed plastic wafer pod` |
| 46 | **228** | 70/79 | 158/158 | 0.246 | 89 | **+43** | — | `f089` | `sealed wafer container, a sealed plastic box with a front door` |
| 54 | **227** | 73/79 | 154/158 | 0.087 | 122 | **+68** | — | `f122` | `boxy cleanroom plastic wafer pod` |
| 54 | **227** | 71/79 | 156/158 | 0.434 | 68 | +14 | **47** | `f068` | `cube shaped sealed plastic wafer housing` |
| 54 | **227** | 70/79 | 157/158 | 0.594 | 55 | +0 | — | `f055` | `small cube shaped sealed plastic wafer pod` |
| 54 | **227** | 70/79 | 157/158 | 0.469 | 65 | +10 | **24** | `f065` | `cube shaped sealed plastic silicon wafer pod` |
| 54 | **227** | 70/79 | 157/158 | 0.187 | 103 | **+48** | — | `f103` | `cube shaped sealed plastic wafer tote` |
| 54 | **227** | 69/79 | 158/158 | 0.703 | 48 | -6 | **44** | `f048` | `cubic sealed plastic wafer pod` |
| 58 | **226** | 70/79 | 156/158 | 0.727 | 45 | -14 | — | `f045` | `a single boxy sealed plastic wafer pod` |
| 58 | **226** | 70/79 | 156/158 | 0.475 | 63 | +4 | **50** | `f063` | `closed cube shaped sealed plastic wafer pod` |
| 64 | **225** | 71/79 | 154/158 | 0.852 | 28 | **-36** | — | `f028` | `blocky sealed plastic wafer case` |
| 64 | **225** | 70/79 | 155/158 | 0.766 | 42 | -22 | — | `f042` | `boxy plastic wafer pod` |
| 64 | **225** | 70/79 | 155/158 | 0.122 | 117 | **+54** | — | `f117` | `boxy sealed plastic wafer container` |
| 64 | **225** | 69/79 | 156/158 | 0.285 | 83 | +20 | — | `f083` | `sealed plastic wafer pod` |
| 64 | **225** | 69/79 | 156/158 | 0.270 | 85 | +22 | — | `f085` | `cube shaped, sealed, plastic wafer pod` |
| 64 | **225** | 69/79 | 156/158 | 0.210 | 96 | **+32** | **49** | `f096` | `cube shaped sealed plastic wafer enclosure` |
| 64 | **225** | 68/79 | 157/158 | 0.238 | 90 | +26 | — | `f090` | `cube shaped sealed plastic substrate pod` |
| 64 | **225** | 67/79 | 158/158 | 0.559 | 58 | -6 | **37** | `f058` | `cube shaped sealed plastic wafer cassette` |
| 70 | **224** | 72/79 | 152/158 | 0.169 | 107 | **+37** | — | `f107` | `sealed wafer container, a plastic box` |
| 70 | **224** | 71/79 | 153/158 | 0.895 | 19 | **-51** | **11** | `f019` | `a boxy plastic object` |
| 70 | **224** | 71/79 | 153/158 | 0.162 | 108 | **+38** | — | `f108` | `boxy sealed plastic wafer pods` |
| 70 | **224** | 70/79 | 154/158 | 0.151 | 110 | **+40** | **30** | `f110` | `silicon wafer carrier, a boxy plastic object` |
| 70 | **224** | 68/79 | 156/158 | 0.469 | 64 | -6 | — | `f064` | `boxy sealed plastic semiconductor wafer transport pod` |
| 74 | **223** | 68/79 | 155/158 | 0.181 | 105 | **+31** | **45** | `f105` | `boxy plastic wafer carrier` |
| 74 | **223** | 67/79 | 156/158 | 0.208 | 97 | +23 | — | `f097` | `wafer transport container, a cube shaped plastic case` |
| 74 | **223** | 66/79 | 157/158 | 0.812 | 39 | **-35** | — | `f039` | `boxy sealed wafer pod` |
| 78 | **222** | 68/79 | 154/158 | 0.211 | 95 | +18 | — | `f095` | `cube shaped plastic wafer container` |
| 78 | **222** | 66/79 | 156/158 | 0.324 | 77 | -0 | **28** | `f077` | `plastic wafer carrier, not a metal cabinet` |
| 78 | **222** | 64/79 | 158/158 | 0.867 | 24 | **-54** | — | `f024` | `Entegris wafer carrier pod` |
| 78 | **222** | 64/79 | 158/158 | 0.250 | 88 | +10 | — | `f088` | `front opening unified pod` |
| 82 | **221** | 70/79 | 151/158 | 0.097 | 121 | **+40** | — | `f121` | `boxy 300 mm plastic wafer pod` |
| 82 | **221** | 67/79 | 154/158 | 0.305 | 81 | -0 | **36** | `f081` | `silicon wafer carrier with a door on the front` |
| 82 | **221** | 65/79 | 156/158 | 0.148 | 112 | **+30** | **57** | `f112` | `substrate carrier, a square plastic box with a handle on the side` |
| 82 | **221** | 63/79 | 158/158 | 0.254 | 86 | +4 | **52** | `f086` | `front opening pod, a boxy plastic object` |
| 84 | **220** | 64/79 | 156/158 | 0.926 | 16 | **-68** | — | `f016` | `boxy semiconductor plastic wafer pod` |
| 87 | **219** | 71/79 | 148/158 | 0.173 | 106 | +19 | — | `f106` | `substrate carrier, a cube shaped plastic case` |
| 87 | **219** | 66/79 | 153/158 | 0.586 | 57 | **-30** | — | `f057` | `a cube shaped plastic case, a semiconductor fab carrier` |
| 87 | **219** | 65/79 | 154/158 | 0.645 | 52 | **-35** | **34** | `f052` | `boxy plastic object` |
| 87 | **219** | 63/79 | 156/158 | 0.338 | 76 | -11 | — | `f076` | `Entegris plastic wafer pod` |
| 87 | **219** | 61/79 | 158/158 | 0.469 | 66 | -21 | **32** | `f066` | `cube shaped sealed plastic wafer shell` |
| 90 | **218** | 71/79 | 147/158 | 0.065 | 127 | **+36** | — | `f127` | `boxy sealed plastic pod` |
| 90 | **218** | 66/79 | 152/158 | 0.875 | 23 | **-68** | **25** | `f023` | `boxy semiconductor plastic wafer case` |
| 93 | **217** | 67/79 | 150/158 | 0.230 | 92 | -1 | — | `f092` | `cleanroom wafer container, a cube shaped plastic case` |
| 93 | **217** | 65/79 | 152/158 | 0.914 | 17 | **-76** | **12** | `f017` | `the boxy plastic object` |
| 93 | **217** | 65/79 | 152/158 | 0.217 | 94 | +1 | — | `f094` | `sealed wafer container with a door on the front` |
| 96 | **216** | 65/79 | 151/158 | 0.309 | 80 | -16 | — | `f080` | `the cube shaped plastic case` |
| 96 | **216** | 62/79 | 154/158 | 0.188 | 102 | +6 | **55** | `f102` | `sealed plastic box that holds silicon wafers, with a door on the front and a flange on top` |
| 98 | **215** | 64/79 | 151/158 | 0.342 | 75 | -23 | — | `f075` | `Entegris wafer pod` |
| 98 | **215** | 61/79 | 154/158 | 0.141 | 113 | +15 | — | `f113` | `boxy wafer pod` |
| 98 | **215** | 59/79 | 156/158 | 0.590 | 56 | **-42** | — | `f056` | `transparent cube shaped sealed plastic wafer pod` |
| 100 | **214** | 61/79 | 153/158 | 0.099 | 120 | +20 | — | `f120` | `plastic box for silicon wafers` |
| 100 | **214** | 57/79 | 157/158 | 0.232 | 91 | -10 | **53** | `f091` | `sealed plastic box with a latching door` |
| 102 | **213** | 61/79 | 152/158 | 0.637 | 53 | **-50** | — | `f053` | `Shin-Etsu wafer carrier pod` |
| 102 | **213** | 58/79 | 155/158 | 0.852 | 27 | **-76** | **31** | `f027` | `cube shaped semiconductor plastic wafer case` |
| 105 | **211** | 66/79 | 145/158 | 0.050 | 136 | **+31** | — | `f136` | `boxy, sealed, plastic wafer pod` |
| 105 | **211** | 56/79 | 155/158 | 0.151 | 111 | +6 | — | `f111` | `Entegris FOUP wafer carrier` |
| 105 | **211** | 55/79 | 156/158 | 0.285 | 82 | -23 | **46** | `f082` | `plastic box with a removable front door` |
| 107 | **210** | 61/79 | 149/158 | 0.408 | 72 | **-35** | — | `f072` | `cube shaped silicon plastic wafer pod` |
| 108 | **209** | 63/79 | 146/158 | 0.052 | 134 | +26 | — | `f134` | `plastic box with wafers inside` |
| 108 | **209** | 57/79 | 152/158 | 0.160 | 109 | +0 | **27** | `f109` | `boxy sealed plastic wafer carrier` |
| 112 | **207** | 59/79 | 148/158 | 0.055 | 133 | +22 | — | `f133` | `semiconductor fab carrier, a boxy plastic object` |
| 112 | **207** | 58/79 | 149/158 | 0.418 | 71 | **-40** | — | `f071` | `blocky silicon plastic wafer pod` |
| 112 | **207** | 57/79 | 150/158 | 0.068 | 126 | +14 | — | `f126` | `plastic wafer carrier, not a cardboard box` |
| 112 | **207** | 56/79 | 151/158 | 0.824 | 35 | **-76** | — | `f035` | `blocky semiconductor plastic wafer case` |
| 114 | **206** | 57/79 | 149/158 | 0.707 | 47 | **-68** | — | `f047` | `boxy silicon plastic wafer case` |
| 114 | **206** | 51/79 | 155/158 | 0.314 | 79 | **-36** | **56** | `f079` | `square sealed plastic wafer pod` |
| 116 | **205** | 60/79 | 145/158 | 0.354 | 74 | **-42** | — | `f074` | `the main object, a cube shaped sealed plastic wafer pod` |
| 116 | **205** | 55/79 | 150/158 | 0.081 | 123 | +6 | — | `f123` | `front opening unified pod, a sealed plastic wafer carrier with a black top flange` |
| 118 | **204** | 56/79 | 148/158 | 0.135 | 115 | -3 | — | `f115` | `a photo of a cube shaped sealed plastic wafer pod` |
| 119 | **201** | 60/79 | 141/158 | 0.059 | 131 | +12 | — | `f131` | `cubic plastic container` |
| 120 | **200** | 49/79 | 151/158 | 0.136 | 114 | -6 | **43** | `f114` | `boxy plastic object for carrying wafers` |
| 122 | **199** | 58/79 | 141/158 | 0.063 | 130 | +8 | — | `f130` | `boxy plastic pod` |
| 122 | **199** | 56/79 | 143/158 | 0.064 | 128 | +6 | — | `f128` | `sealed plastic box rather than a crate` |
| 122 | **199** | 54/79 | 145/158 | 0.229 | 93 | -29 | — | `f093` | `a cube shaped plastic case, a sealed wafer container` |
| 124 | **196** | 55/79 | 141/158 | 0.123 | 116 | -8 | — | `f116` | `a boxy Entegris wafer carrier pod` |
| 125 | **190** | 51/79 | 139/158 | 0.051 | 135 | +10 | — | `f135` | `plastic wafer pod` |
| 126 | **187** | 43/79 | 144/158 | 0.270 | 84 | **-42** | — | `f084` | `blocky plastic object` |
| 128 | **184** | 52/79 | 132/158 | 0.077 | 124 | -4 | — | `f124` | `boxy plastic container` |
| 128 | **184** | 50/79 | 134/158 | 0.063 | 129 | +2 | — | `f129` | `a cube shaped plastic case` |
| 129 | **182** | 38/79 | 144/158 | 0.197 | 101 | -28 | **54** | `f101` | `a cube shaped plastic case, a silicon wafer carrier` |
| 130 | **181** | 45/79 | 136/158 | 0.183 | 104 | -26 | **17** | `f104` | `a cube shaped plastic case, a substrate carrier` |
| 131 | **180** | 45/79 | 135/158 | 0.104 | 119 | -12 | — | `f119` | `rectangular plastic case` |
| 132 | **178** | 49/79 | 129/158 | 0.057 | 132 | +0 | — | `f132` | `cube shaped semiconductor wafer carrier` |
| 133 | **175** | 32/79 | 143/158 | 0.455 | 67 | **-66** | — | `f067` | `blocky silicon plastic wafer case` |
| 134 | **168** | 49/79 | 119/158 | 0.202 | 100 | **-34** | — | `f100` | `a cube shaped plastic case, a cleanroom wafer container` |
| 135 | **167** | 36/79 | 131/158 | 0.072 | 125 | -10 | — | `f125` | `cube shaped case` |
| 136 | **156** | 31/79 | 125/158 | 0.113 | 118 | -18 | — | `f118` | `cube shaped silicon plastic wafer case` |

**실물** = 실물 3런(1차·50cm·28cm) **전부 통과한 58개**의 평균 순위. 빈칸은 어느 라운드에선가 떨어진 것 — 버린 게 아니라 **대기**다(`real_pass58.json` 등의 `_dropped*`).
