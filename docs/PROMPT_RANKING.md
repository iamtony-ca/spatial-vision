# 실물 테스트 프롬프트 `full` — **237장 통합 서열**

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

## 서열 (136개)

| 순위 | 237 | 79장 | 158장 | score | 옛 | Δ | 실물 | slug | 프롬프트 |
|---:|---:|---:|---:|---:|---:|---:|:-:|---|---|
| 1 | **236** | 78/79 | 158/158 | 0.973 | 5 | +4 |  | `f005` | `plastic cube shaped sealed wafer pod` |
| 2 | **235** | 77/79 | 158/158 | 0.977 | 2 | -0 |  | `f002` | `cube shaped sealed plastic wafer pod` |
| 2 | **235** | 77/79 | 158/158 | 0.977 | 4 | +2 |  | `f004` | `CUBE SHAPED SEALED PLASTIC WAFER POD` |
| 5 | **234** | 77/79 | 157/158 | 0.949 | 12 | +7 |  | `f012` | `cube shaped plastic sealed wafer pod` |
| 5 | **234** | 76/79 | 158/158 | 0.852 | 29 | +24 |  | `f029` | `cube shaped sealed plastic wafer magazine` |
| 5 | **234** | 76/79 | 158/158 | 0.420 | 70 | **+65** |  | `f070` | `black cube shaped sealed plastic wafer pod` |
| 8 | **233** | 76/79 | 157/158 | 0.680 | 51 | **+42** |  | `f051` | `cube shaped sealed polymer wafer pod` |
| 8 | **233** | 75/79 | 158/158 | 0.953 | 11 | +2 |  | `f011` | `cubeshaped sealed plastic wafer pod` |
| 8 | **233** | 75/79 | 158/158 | 0.867 | 26 | +18 |  | `f026` | `cube shaped sealed resin wafer pod` |
| 8 | **233** | 75/79 | 158/158 | 0.684 | 50 | **+42** |  | `f050` | `cube shaped sealed semiconductor plastic wafer pod` |
| 14 | **232** | 76/79 | 156/158 | 0.977 | 3 | -11 |  | `f003` | `blocky sealed plastic wafer pod` |
| 14 | **232** | 76/79 | 156/158 | 0.824 | 32 | +18 |  | `f032` | `sealed wafer container, a cube shaped plastic case` |
| 14 | **232** | 76/79 | 156/158 | 0.742 | 43 | +29 |  | `f043` | `cube shaped semiconductor plastic wafer pod` |
| 14 | **232** | 74/79 | 158/158 | 0.930 | 15 | +1 |  | `f015` | `boxlike sealed plastic wafer pod` |
| 14 | **232** | 74/79 | 158/158 | 0.887 | 22 | +8 |  | `f022` | `large cube shaped sealed plastic wafer pod` |
| 14 | **232** | 74/79 | 158/158 | 0.730 | 44 | **+30** |  | `f044` | `cube shaped sealed plastic semiconductor wafer pod` |
| 14 | **232** | 74/79 | 158/158 | 0.715 | 46 | **+32** |  | `f046` | `a sealed boxy plastic wafer carrier with a removable front door` |
| 20 | **231** | 74/79 | 157/158 | 0.953 | 10 | -10 |  | `f010` | `a cube shaped sealed plastic wafer pod` |
| 20 | **231** | 74/79 | 157/158 | 0.816 | 37 | +17 |  | `f037` | `a boxy sealed plastic wafer pod` |
| 20 | **231** | 74/79 | 157/158 | 0.816 | 38 | +18 |  | `f038` | `clear cube shaped sealed plastic wafer pod` |
| 20 | **231** | 74/79 | 157/158 | 0.605 | 54 | **+34** |  | `f054` | `sealed wafer container, a boxy plastic object` |
| 20 | **231** | 73/79 | 158/158 | 0.914 | 18 | -2 |  | `f018` | `cube like sealed plastic wafer pod` |
| 28 | **230** | 75/79 | 155/158 | 0.691 | 49 | +21 |  | `f049` | `boxy silicon plastic wafer pod` |
| 28 | **230** | 74/79 | 156/158 | 0.824 | 33 | +5 |  | `f033` | `boxy sealed plastic wafer case` |
| 28 | **230** | 74/79 | 156/158 | 0.207 | 98 | **+70** |  | `f098` | `boxy sealed plastic wafer box` |
| 28 | **230** | 73/79 | 157/158 | 0.969 | 6 | -22 |  | `f006` | `box shaped sealed plastic wafer pod` |
| 28 | **230** | 73/79 | 157/158 | 0.957 | 7 | -21 |  | `f007` | `boxy sealed plastic wafer pod` |
| 28 | **230** | 73/79 | 157/158 | 0.957 | 8 | -20 |  | `f008` | `Boxy sealed plastic wafer pod` |
| 28 | **230** | 73/79 | 157/158 | 0.957 | 9 | -19 |  | `f009` | `boxy sealed plastic wafer pod.` |
| 28 | **230** | 73/79 | 157/158 | 0.934 | 14 | -14 |  | `f014` | `the cube shaped sealed plastic wafer pod` |
| 28 | **230** | 73/79 | 157/158 | 0.824 | 34 | +6 |  | `f034` | `the boxy sealed plastic wafer pod` |
| 28 | **230** | 73/79 | 157/158 | 0.531 | 61 | **+33** |  | `f061` | `sealed cube shaped wafer carrier` |
| 28 | **230** | 72/79 | 158/158 | 0.844 | 30 | +2 |  | `f030` | `cube shaped sealed polycarbonate wafer pod` |
| 37 | **229** | 74/79 | 155/158 | 0.836 | 31 | -6 |  | `f031` | `blocky semiconductor plastic wafer pod` |
| 37 | **229** | 73/79 | 156/158 | 0.520 | 62 | +25 |  | `f062` | `cube shaped sealed plastic wafer case` |
| 37 | **229** | 73/79 | 156/158 | 0.320 | 78 | **+41** |  | `f078` | `cube shaped sealed plastic wafer canister` |
| 37 | **229** | 72/79 | 157/158 | 0.204 | 99 | **+62** |  | `f099` | `cube shaped sealed plastic wafer crate` |
| 37 | **229** | 71/79 | 158/158 | 0.895 | 20 | -17 |  | `f020` | `cube shaped sealed wafer pod` |
| 37 | **229** | 71/79 | 158/158 | 0.820 | 36 | -1 |  | `f036` | `cube-shaped sealed plastic wafer pod` |
| 37 | **229** | 71/79 | 158/158 | 0.781 | 40 | +3 |  | `f040` | `cube shaped sealed silicon plastic wafer pod` |
| 46 | **228** | 73/79 | 155/158 | 0.355 | 73 | +27 |  | `f073` | `blocky sealed semiconductor plastic wafer pod` |
| 46 | **228** | 72/79 | 156/158 | 0.867 | 25 | -21 |  | `f025` | `the sealed wafer container, a cube shaped plastic case` |
| 46 | **228** | 72/79 | 156/158 | 0.432 | 69 | +23 |  | `f069` | `cube shaped sealed acrylic wafer pod` |
| 46 | **228** | 72/79 | 156/158 | 0.252 | 87 | **+41** |  | `f087` | `plastic pod for wafer storage` |
| 46 | **228** | 71/79 | 157/158 | 0.934 | 13 | **-33** |  | `f013` | `boxy sealed plastic wafer pod on a table` |
| 46 | **228** | 71/79 | 157/158 | 0.777 | 41 | -5 |  | `f041` | `clean cube shaped sealed plastic wafer pod` |
| 46 | **228** | 71/79 | 157/158 | 0.551 | 59 | +13 |  | `f059` | `sealed wafer container, a square plastic box with a handle on the side` |
| 46 | **228** | 71/79 | 157/158 | 0.539 | 60 | +14 |  | `f060` | `chunky sealed plastic wafer pod` |
| 46 | **228** | 70/79 | 158/158 | 0.988 | 1 | **-45** |  | `f001` | `Entegris cube shaped sealed plastic wafer pod` |
| 46 | **228** | 70/79 | 158/158 | 0.891 | 21 | -25 |  | `f021` | `Shin-Etsu cube shaped sealed plastic wafer pod` |
| 46 | **228** | 70/79 | 158/158 | 0.246 | 89 | **+43** |  | `f089` | `sealed wafer container, a sealed plastic box with a front door` |
| 54 | **227** | 73/79 | 154/158 | 0.087 | 122 | **+68** |  | `f122` | `boxy cleanroom plastic wafer pod` |
| 54 | **227** | 71/79 | 156/158 | 0.434 | 68 | +14 |  | `f068` | `cube shaped sealed plastic wafer housing` |
| 54 | **227** | 70/79 | 157/158 | 0.594 | 55 | +0 |  | `f055` | `small cube shaped sealed plastic wafer pod` |
| 54 | **227** | 70/79 | 157/158 | 0.469 | 65 | +10 |  | `f065` | `cube shaped sealed plastic silicon wafer pod` |
| 54 | **227** | 70/79 | 157/158 | 0.187 | 103 | **+48** |  | `f103` | `cube shaped sealed plastic wafer tote` |
| 54 | **227** | 69/79 | 158/158 | 0.703 | 48 | -6 |  | `f048` | `cubic sealed plastic wafer pod` |
| 58 | **226** | 70/79 | 156/158 | 0.727 | 45 | -14 |  | `f045` | `a single boxy sealed plastic wafer pod` |
| 58 | **226** | 70/79 | 156/158 | 0.475 | 63 | +4 |  | `f063` | `closed cube shaped sealed plastic wafer pod` |
| 64 | **225** | 71/79 | 154/158 | 0.852 | 28 | **-36** |  | `f028` | `blocky sealed plastic wafer case` |
| 64 | **225** | 70/79 | 155/158 | 0.766 | 42 | -22 |  | `f042` | `boxy plastic wafer pod` |
| 64 | **225** | 70/79 | 155/158 | 0.122 | 117 | **+54** |  | `f117` | `boxy sealed plastic wafer container` |
| 64 | **225** | 69/79 | 156/158 | 0.285 | 83 | +20 |  | `f083` | `sealed plastic wafer pod` |
| 64 | **225** | 69/79 | 156/158 | 0.270 | 85 | +22 |  | `f085` | `cube shaped, sealed, plastic wafer pod` |
| 64 | **225** | 69/79 | 156/158 | 0.210 | 96 | **+32** |  | `f096` | `cube shaped sealed plastic wafer enclosure` |
| 64 | **225** | 68/79 | 157/158 | 0.238 | 90 | +26 |  | `f090` | `cube shaped sealed plastic substrate pod` |
| 64 | **225** | 67/79 | 158/158 | 0.559 | 58 | -6 |  | `f058` | `cube shaped sealed plastic wafer cassette` |
| 70 | **224** | 72/79 | 152/158 | 0.169 | 107 | **+37** |  | `f107` | `sealed wafer container, a plastic box` |
| 70 | **224** | 71/79 | 153/158 | 0.895 | 19 | **-51** |  | `f019` | `a boxy plastic object` |
| 70 | **224** | 71/79 | 153/158 | 0.162 | 108 | **+38** |  | `f108` | `boxy sealed plastic wafer pods` |
| 70 | **224** | 70/79 | 154/158 | 0.151 | 110 | **+40** |  | `f110` | `silicon wafer carrier, a boxy plastic object` |
| 70 | **224** | 68/79 | 156/158 | 0.469 | 64 | -6 |  | `f064` | `boxy sealed plastic semiconductor wafer transport pod` |
| 74 | **223** | 68/79 | 155/158 | 0.181 | 105 | **+31** |  | `f105` | `boxy plastic wafer carrier` |
| 74 | **223** | 67/79 | 156/158 | 0.208 | 97 | +23 |  | `f097` | `wafer transport container, a cube shaped plastic case` |
| 74 | **223** | 66/79 | 157/158 | 0.812 | 39 | **-35** |  | `f039` | `boxy sealed wafer pod` |
| 78 | **222** | 68/79 | 154/158 | 0.211 | 95 | +18 |  | `f095` | `cube shaped plastic wafer container` |
| 78 | **222** | 66/79 | 156/158 | 0.324 | 77 | -0 |  | `f077` | `plastic wafer carrier, not a metal cabinet` |
| 78 | **222** | 64/79 | 158/158 | 0.867 | 24 | **-54** |  | `f024` | `Entegris wafer carrier pod` |
| 78 | **222** | 64/79 | 158/158 | 0.250 | 88 | +10 | ★ | `f088` | `front opening unified pod` |
| 82 | **221** | 70/79 | 151/158 | 0.097 | 121 | **+40** |  | `f121` | `boxy 300 mm plastic wafer pod` |
| 82 | **221** | 67/79 | 154/158 | 0.305 | 81 | -0 |  | `f081` | `silicon wafer carrier with a door on the front` |
| 82 | **221** | 65/79 | 156/158 | 0.148 | 112 | **+30** |  | `f112` | `substrate carrier, a square plastic box with a handle on the side` |
| 82 | **221** | 63/79 | 158/158 | 0.254 | 86 | +4 |  | `f086` | `front opening pod, a boxy plastic object` |
| 84 | **220** | 64/79 | 156/158 | 0.926 | 16 | **-68** |  | `f016` | `boxy semiconductor plastic wafer pod` |
| 87 | **219** | 71/79 | 148/158 | 0.173 | 106 | +19 |  | `f106` | `substrate carrier, a cube shaped plastic case` |
| 87 | **219** | 66/79 | 153/158 | 0.586 | 57 | **-30** |  | `f057` | `a cube shaped plastic case, a semiconductor fab carrier` |
| 87 | **219** | 65/79 | 154/158 | 0.645 | 52 | **-35** | ★ | `f052` | `boxy plastic object` |
| 87 | **219** | 63/79 | 156/158 | 0.338 | 76 | -11 |  | `f076` | `Entegris plastic wafer pod` |
| 87 | **219** | 61/79 | 158/158 | 0.469 | 66 | -21 |  | `f066` | `cube shaped sealed plastic wafer shell` |
| 90 | **218** | 71/79 | 147/158 | 0.065 | 127 | **+36** |  | `f127` | `boxy sealed plastic pod` |
| 90 | **218** | 66/79 | 152/158 | 0.875 | 23 | **-68** |  | `f023` | `boxy semiconductor plastic wafer case` |
| 93 | **217** | 67/79 | 150/158 | 0.230 | 92 | -1 |  | `f092` | `cleanroom wafer container, a cube shaped plastic case` |
| 93 | **217** | 65/79 | 152/158 | 0.914 | 17 | **-76** |  | `f017` | `the boxy plastic object` |
| 93 | **217** | 65/79 | 152/158 | 0.217 | 94 | +1 |  | `f094` | `sealed wafer container with a door on the front` |
| 96 | **216** | 65/79 | 151/158 | 0.309 | 80 | -16 |  | `f080` | `the cube shaped plastic case` |
| 96 | **216** | 62/79 | 154/158 | 0.188 | 102 | +6 |  | `f102` | `sealed plastic box that holds silicon wafers, with a door on the front and a flange on top` |
| 98 | **215** | 64/79 | 151/158 | 0.342 | 75 | -23 |  | `f075` | `Entegris wafer pod` |
| 98 | **215** | 61/79 | 154/158 | 0.141 | 113 | +15 |  | `f113` | `boxy wafer pod` |
| 98 | **215** | 59/79 | 156/158 | 0.590 | 56 | **-42** |  | `f056` | `transparent cube shaped sealed plastic wafer pod` |
| 100 | **214** | 61/79 | 153/158 | 0.099 | 120 | +20 |  | `f120` | `plastic box for silicon wafers` |
| 100 | **214** | 57/79 | 157/158 | 0.232 | 91 | -10 |  | `f091` | `sealed plastic box with a latching door` |
| 102 | **213** | 61/79 | 152/158 | 0.637 | 53 | **-50** |  | `f053` | `Shin-Etsu wafer carrier pod` |
| 102 | **213** | 58/79 | 155/158 | 0.852 | 27 | **-76** |  | `f027` | `cube shaped semiconductor plastic wafer case` |
| 105 | **211** | 66/79 | 145/158 | 0.050 | 136 | **+31** |  | `f136` | `boxy, sealed, plastic wafer pod` |
| 105 | **211** | 56/79 | 155/158 | 0.151 | 111 | +6 |  | `f111` | `Entegris FOUP wafer carrier` |
| 105 | **211** | 55/79 | 156/158 | 0.285 | 82 | -23 |  | `f082` | `plastic box with a removable front door` |
| 107 | **210** | 61/79 | 149/158 | 0.408 | 72 | **-35** |  | `f072` | `cube shaped silicon plastic wafer pod` |
| 108 | **209** | 63/79 | 146/158 | 0.052 | 134 | +26 |  | `f134` | `plastic box with wafers inside` |
| 108 | **209** | 57/79 | 152/158 | 0.160 | 109 | +0 |  | `f109` | `boxy sealed plastic wafer carrier` |
| 112 | **207** | 59/79 | 148/158 | 0.055 | 133 | +22 |  | `f133` | `semiconductor fab carrier, a boxy plastic object` |
| 112 | **207** | 58/79 | 149/158 | 0.418 | 71 | **-40** |  | `f071` | `blocky silicon plastic wafer pod` |
| 112 | **207** | 57/79 | 150/158 | 0.068 | 126 | +14 |  | `f126` | `plastic wafer carrier, not a cardboard box` |
| 112 | **207** | 56/79 | 151/158 | 0.824 | 35 | **-76** |  | `f035` | `blocky semiconductor plastic wafer case` |
| 114 | **206** | 57/79 | 149/158 | 0.707 | 47 | **-68** |  | `f047` | `boxy silicon plastic wafer case` |
| 114 | **206** | 51/79 | 155/158 | 0.314 | 79 | **-36** |  | `f079` | `square sealed plastic wafer pod` |
| 116 | **205** | 60/79 | 145/158 | 0.354 | 74 | **-42** |  | `f074` | `the main object, a cube shaped sealed plastic wafer pod` |
| 116 | **205** | 55/79 | 150/158 | 0.081 | 123 | +6 |  | `f123` | `front opening unified pod, a sealed plastic wafer carrier with a black top flange` |
| 118 | **204** | 56/79 | 148/158 | 0.135 | 115 | -3 |  | `f115` | `a photo of a cube shaped sealed plastic wafer pod` |
| 119 | **201** | 60/79 | 141/158 | 0.059 | 131 | +12 |  | `f131` | `cubic plastic container` |
| 120 | **200** | 49/79 | 151/158 | 0.136 | 114 | -6 |  | `f114` | `boxy plastic object for carrying wafers` |
| 122 | **199** | 58/79 | 141/158 | 0.063 | 130 | +8 |  | `f130` | `boxy plastic pod` |
| 122 | **199** | 56/79 | 143/158 | 0.064 | 128 | +6 |  | `f128` | `sealed plastic box rather than a crate` |
| 122 | **199** | 54/79 | 145/158 | 0.229 | 93 | -29 |  | `f093` | `a cube shaped plastic case, a sealed wafer container` |
| 124 | **196** | 55/79 | 141/158 | 0.123 | 116 | -8 |  | `f116` | `a boxy Entegris wafer carrier pod` |
| 125 | **190** | 51/79 | 139/158 | 0.051 | 135 | +10 |  | `f135` | `plastic wafer pod` |
| 126 | **187** | 43/79 | 144/158 | 0.270 | 84 | **-42** |  | `f084` | `blocky plastic object` |
| 128 | **184** | 52/79 | 132/158 | 0.077 | 124 | -4 |  | `f124` | `boxy plastic container` |
| 128 | **184** | 50/79 | 134/158 | 0.063 | 129 | +2 |  | `f129` | `a cube shaped plastic case` |
| 129 | **182** | 38/79 | 144/158 | 0.197 | 101 | -28 |  | `f101` | `a cube shaped plastic case, a silicon wafer carrier` |
| 130 | **181** | 45/79 | 136/158 | 0.183 | 104 | -26 |  | `f104` | `a cube shaped plastic case, a substrate carrier` |
| 131 | **180** | 45/79 | 135/158 | 0.104 | 119 | -12 |  | `f119` | `rectangular plastic case` |
| 132 | **178** | 49/79 | 129/158 | 0.057 | 132 | +0 |  | `f132` | `cube shaped semiconductor wafer carrier` |
| 133 | **175** | 32/79 | 143/158 | 0.455 | 67 | **-66** |  | `f067` | `blocky silicon plastic wafer case` |
| 134 | **168** | 49/79 | 119/158 | 0.202 | 100 | **-34** |  | `f100` | `a cube shaped plastic case, a cleanroom wafer container` |
| 135 | **167** | 36/79 | 131/158 | 0.072 | 125 | -10 |  | `f125` | `cube shaped case` |
| 136 | **156** | 31/79 | 125/158 | 0.113 | 118 | -18 |  | `f118` | `cube shaped silicon plastic wafer case` |

★ = 실물 ZED X 사진에서 사용자가 눈으로 확인한 것(`origin: real-validated`).
