# 실물 사진 — SAM3 프롬프트 스윕 **복붙 순서** (다른 PC용)

> 목적: **실물 ZED X 사진에서 `full` 프롬프트 136개를 전부 돌려**, 결과가 갈린 것만 눈으로 판정하고
> 서열을 다시 낸다. 그 서열이 「어느 프롬프트로 pose 까지 돌릴까」를 정한다.
>
> - 경위·수치의 정본: **`docs/RESULTS.md §39`** · 현재 서열: **`docs/PROMPT_RANKING.md`**
> - 🔴 **웹사진 서열은 실물로 전이되지 않을 수 있다**(교훈 #92·#100). 실물에서 다시 내는 게 이 문서다.
> - 🔴 **자르지 않는다.** 136개 전부 돌린다 — 실물에서 확인된 두 프롬프트가 웹 서열로는 **78위·87위**라
>   «상위 N 컷» 이면 잘린다(§39-15). 비용은 40장 기준 **약 17분**이다.

---

## 0. 전제 — 이것만 되면 된다

```bash
cd <ws>/src/vision
source envs/env.sh                 # 🔴 반드시 먼저. 캐시·CUDA·PYTORCH_CUDA_ALLOC_CONF 를 잡는다
envs/seg_sam3/bin/python -c "import torch;print(torch.cuda.is_available())"   # True 여야 한다
ls -lL weights/sam3/sam3.pt        # SAM3 체크포인트 (없으면 envs/fetch_weights.sh + place_weights.sh)
```

- 새 머신이면 **`docs/SETUP.md §1~§6`** 을 먼저 순서대로. 이 스윕에 필요한 venv 는 **`seg_sam3` 하나**
  (판정·시트 단계만 `pose`).
- 🔴 **venv 를 activate 하지 않는다.** 항상 인터프리터 경로를 직접 쓴다.

## 1. 사진 놓기

```bash
mkdir -p assets/real_imgs/zedx_2026xxxx
# 여기에 **왼쪽 rectified 이미지만** 넣는다 (스윕은 분할만 하므로 right/cam.json 불필요)
```

### 1a. 이미 `runs/<촬영>/frame_XXXX/` 로 들어와 있다면 — `left.png` 만 모은다

🔴 **`--imgs` 를 촬영 디렉토리로 바로 겨누면 안 된다.** 스윕은 준 디렉토리를 **한 겹만** 훑으므로
`frame_*/` 아래를 못 보고, 평평하게 펴 놓으면 `right.png` 까지 같이 읽는다.

```bash
SRC=runs/real_zedx_28cm                       # 촬영 디렉토리 (frame_0000/left.png …)
DST=assets/real_imgs/zedx_2026xxxx
mkdir -p "$DST"
for f in "$SRC"/frame_*/left.png; do
    cp "$f" "$DST/$(basename "$SRC")_$(basename "$(dirname "$f")").png"
done
ls "$DST" | wc -l                              # 프레임 수와 같아야 한다
```

**거리·조명이 다른 촬영을 한 번에** 보려면 그대로 여러 번 돌리면 된다 — 접두어가 달라 안 섞인다:

```bash
DST=assets/real_imgs/zedx_2026xxxx; mkdir -p "$DST"
for SRC in runs/real_zedx_28cm runs/real_zedx_40cm runs/real_zedx_50cm; do
    for f in "$SRC"/frame_*/left.png; do
        cp "$f" "$DST/$(basename "$SRC")_$(basename "$(dirname "$f")").png"
    done
done
ls "$DST" | wc -l
```

- 파일명이 `real_zedx_28cm_frame_0007.png` 가 되어 **거리·프레임이 이름에 남는다** — 나중에
  «28cm 만 통과했다» 같은 층화를 파일명으로 할 수 있다.
- 용량이 아까우면 `cp` 대신 **`ln -s "$(realpath "$f")"`** 로 심링크해도 스윕은 잘 읽는다.
  🔴 다만 원본 촬영을 지우거나 옮기면 스윕이 통째로 깨진다.
- ⚠️ **`left.png` 는 rectified BGR8 PNG** 여야 한다(`make_frame_from_zed.py` 가 그렇게 만든다).
  raw 이미지를 넣으면 왜곡이 살아 있어 분할은 되지만 뒤의 pose 와 조건이 달라진다.

- 확장자 `jpg jpeg png bmp webp` 만 읽는다. 그 외는 **건너뛰고 경고를 찍는다** — 그 줄을 반드시 확인할 것
  (`.webp` 14장이 조용히 빠져 237장 스윕이 223장으로 돈 적이 있다, §39-8).
- **파일명이 곧 이름표**다. 거리·외관을 넣어 두면 나중에 층화해서 볼 수 있다
  (예: `d28_black_01.png`, `d50_black_07.png`).
- 몸체 외관(검정/주황/투명)이 섞여 있으면 **섞어서 한 번에 돌려도 된다** — 판정은 이미지별이다.

## 2. 스윕 — `full` 136개 전부

```bash
envs/seg_sam3/bin/python tools/sam3_prompt_sweep.py \
    --imgs assets/real_imgs/zedx_2026xxxx \
    --out  runs/psweep_real01 \
    --target full \
    --prompts-json assets/prompts/real_testset.json \
    --confidence 0.05 \
    --full-area-min 0.005 \
    --note "실물 ZED X 1차 · 검정 몸체 28/40/50cm · full 136개"
```

| 인자 | 왜 이 값인가 |
|---|---|
| `--confidence 0.05` | **낮게 두고 점수를 기록**한다. 임계값은 사후에 정하는 편이 낫다(§35-2m-2). 🔴 기본 0.15 로 두면 «맞는데 자신감만 낮은» 마스크가 «미검출» 로 사라진다 |
| `--full-area-min 0.005` | 🔴 **기본 0.10 은 «흰 배경 · 물체가 화면의 46%» 인 사진 기준**이다. 클린룸·로드포트 전경처럼 배경이 있으면 **맞는 마스크를 떨어뜨린다**(§39-2). 실물 사진에서 FOUP 이 화면을 크게 채우면 0.05~0.10 으로 올려도 된다 — **먼저 0.005 로 돌리고 `report.md` 의 실패 사유 분포를 보고 정한다** |
| `--prompts-json` | 🔴 **현행은 `assets/prompts/real_current.json` = 4개**(§39-30e): **A** `cube shaped sealed plastic wafer pod`(양쪽 1위) · **W** `plastic cube shaped sealed wafer pod`(웹 1위) · **B** `boxy sealed plastic wafer pod`(실물 3위) · **C** `a boxy plastic object`(🔴 **대조군** — 도메인어 없음, 성능 서열에 섞어 읽지 말 것). 넷이 **어순(A↔W)·형상어(A↔B)·도메인어(A·B↔C)** 세 축을 본다. 넓힐 때는 `real_final12`(12) → `real_pass37` → `real_pass58` → `real_testset`(136). ⚠️ **넓히는 이유는 «오선택 축을 열 때» 와 «개체·조명이 바뀔 때» 뿐**이다. slug 은 프롬프트에 붙박이라 파일이 바뀌어도 이름이 유지된다 |

**예상**: 40장 × 136개 = 5,440 추론 ≈ **17분**(웹 실측 5,372 추론 = 986초). 산출물 **10~20GB**
(오버레이 PNG 가 대부분). 🔴 디스크를 먼저 확인할 것 — `df -h`.

**중간에 죽으면**: `results_partial.json` 이 이미지마다 갱신되므로 어디까지 갔는지 보인다.
큰 사진(2천만 화소 이상)에서 OOM 이 나면 그 프롬프트만 **0.5배씩 줄여 재시도**하고 로그에 `⚠️ … OOM →`
을 찍는다(§39-11e). `🔴 0.25배에서도 OOM` 이 뜬 칸은 **그 프롬프트만 불리해지므로 서열에서 뺀다.**

### 2b. (선택) `flange` 도 볼 거면

```bash
envs/seg_sam3/bin/python tools/sam3_prompt_sweep.py \
    --imgs assets/real_imgs/zedx_2026xxxx --out runs/psweep_real01_fl \
    --target full,flange --prompts-json assets/prompts/real_testset.json \
    --confidence 0.05 --full-area-min 0.005 \
    --ref-full-slug f005,f002,f012
```

🔴 **`--ref-full-slug` 를 반드시 준다.** flange 판정은 같은 이미지의 `full` 마스크를 **물체 기준
프레임**으로 쓰는데, 기본값 slug 은 `real_testset.json` 에 **없다**. 위 셋은 현재 서열 1·2·4위다
(3위는 대문자 중복이라 같은 마스크가 나온다). 로그에 `flange 기준 full 참조 3개 잡힘` 이 떠야 정상이고,
**3개 미만이면 flange 결과가 무효**다(§37-2).
⚠️ `flange` 는 **개체·조명이 바뀔 때마다 다시 골라야** 한다 — `full` 과 달리 도메인을 안 넘는다(§37-13).

## 3. 「갈린 것만」 시트 → 눈으로 판정

```bash
# ① 군집화 → 갈린 이미지만 시트로  (추론 0 · 수 초)
envs/pose/bin/python tools/prompt_sweep_diff.py sheets \
    --run runs/psweep_real01 --imgs assets/real_imgs/zedx_2026xxxx
```

산출: `runs/psweep_real01/diff/diff_p01.png …` · `LEGEND.md` · `clusters.json`

**읽는 법** — 행 하나 = 이미지. **맨 왼쪽(파란 테두리)이 원본**, 오른쪽이 서로 다른 마스크 군집.
`n=44` 는 «136개 중 44개가 이 마스크를 냈다». 초록 = 형상 휴리스틱 통과 / 빨강 = 탈락.

- 🔴 **다수결이 정답이 아니다.** 소수 군집이 맞는 경우를 보라고 만든 시트다
  (실측: 접전 ≤47/68 에서 다수가 틀린 사례 5건. 다만 압도적 ≥50/68 에서는 60/60 다수가 옳았다).
- ⚠️ 초록(휴리스틱 통과)이 «맞다» 는 뜻이 **아니다** — 형상만 본다.
- 갈린 이미지가 **0장**이면 136개가 구분되지 않는다는 뜻이다 → 그 사진들로는 프롬프트를 고를 수 없다.
  (웹 237장에서는 67%가 «전원 동일» 이었다. 실물도 비슷하면 40장 중 **13장 남짓 = 페이지 2장**이다.)

```bash
# ② 판정 기록 — 페이지마다 한 번. 🔴 칸1 = 원본이므로 «2번째» = 군집1
envs/pose/bin/python tools/prompt_sweep_diff.py check \
    --run runs/psweep_real01 --imgs assets/real_imgs/zedx_2026xxxx \
    --page 1 --picks "3;2;2,3,4;2;2,3;2;2,5,6;2,3;2,4;2;2;2,3"
```

- `--picks` 는 **`;` 로 행 구분, `,` 로 한 행의 복수 선택**. 행 수가 그 페이지의 이미지 수와 다르면
  🔴 로 막고 아무것도 안 쓴다.
- 산출: `CHECK_selected_p01.png`(**고른 것만 다시 모아 보여 준다 — 오해가 없었는지 확인용**) ·
  `human_labels.json`(누적).
- 페이지마다 반복한다. 다시 돌려도 **멱등**이다(같은 값이면 파일 내용이 안 변한다).

```bash
# ③ 서열
envs/pose/bin/python tools/prompt_sweep_diff.py rank \
    --run runs/psweep_real01 --combine sum \
    --md-out docs/PROMPT_RANKING_real.md
```

### 3c. 🔴 「갈린 이미지가 0장」이면 — 판정할 게 없다. **다른 축을 본다**

실물 1차에서 실제로 이랬다: **갈린 이미지 0장 · 전 이미지 통과 83/136**.
즉 **검출만 되면 어느 프롬프트든 같은 마스크**를 내고, 갈리는 것은 **«검출·판정을 통과하느냐» 하나**다.
(sim 에서도 같은 결론이었다 — §37-5: *"갈리는 것은 검출률뿐인데 그게 곧 KPI 다"*.)

이때 ②③은 돌릴 값이 없고, 대신:

```bash
# 전 이미지 통과한 것의 slug 만 txt 로  (기본 출력 = <run>/pass_slugs_full.txt)
envs/pose/bin/python tools/prompt_sweep_diff.py slugs --run runs/psweep_real01
# 프롬프트·통과수·score 까지 같이:            --with-prompt
# 다음 라운드에 그대로 먹일 부분집합 json:      --json-out assets/prompts/real_pass83.json
# 문턱을 낮춰 더 넓게:                        --min-pass 38
```

- 🔴 **도구를 못 당겨왔으면 파일명만으로도 된다** — `sheets/perfect/` 의 이름에 slug 이 들어 있다:
  ```bash
  ls runs/psweep_real01/sheets/perfect/ | sed -n 's/^full__[0-9]*__\(f[0-9]*\)\.png$/\1/p' > slugs.txt
  ```
  (위 CLI 와 **완전히 같은 목록**임을 기존 런에서 확인했다.)
- ★ 그다음 좁히는 축은 **`score` 최소값 = «미검출까지의 여유»** 다. 통과 수가 같으면 이걸로 고르고,
  **고른 값이 곧 `--text-conf` 의 근거**가 된다. 🔴 단 **품질 순위로 읽지 말 것**(교훈 #90·#100).
- 🔴 **«전 이미지 통과» 는 «맞다» 가 아니다** — 형상 휴리스틱만 본 것이고, 웹 실측에서 그런 프롬프트가
  사람 기준 **92위**였다(§39-11d). **`sheets/perfect__full.png` 를 눈으로 봐서 «다 같이 틀린» 게
  아닌지** 확인하는 절차가 여기서는 유일한 방어다.
- ⚠️ 통과 못 한 것들의 **실패 사유 분포**를 `report.md` 에서 본다. `no detection` 이 대부분이면
  `--confidence` 문제이고, `area …` 가 대부분이면 `--full-area-min` 이 데이터와 안 맞는 것이다(§39-2).

- **`사람`**(판정한 이미지) 과 **`합의`**(나머지 이미지에서 «자기를 뺀 나머지의 과반과 합의하는가») 를
  **따로** 낸다. 🔴 **자가 다르다 — 어긋나면 `사람` 을 믿는다.**
- `--combine human` 이면 사람 라벨만으로 매긴다.
- 🔴 **`--md-out` 은 `runs/` 밖으로.** `runs/` 는 통째로 `.gitignore` 다.

## 4. 고른 프롬프트로 pose 까지

```bash
python3 tools/make_frame_from_zed.py --left L.png --right R.png \
    --cam assets/cam/zedx_s48560070_hd1200.json --out runs/real01/frame_0000

envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out runs/real01_A \
    --mode all --no-exemplar \
    --text-prompt "<3에서 1위>" --text-conf 0.05 \
    --note "1차 · 프롬프트 스윕 1위" --true-distance-mm 300
```

- 🔴 **팔은 3~4개까지**다. 프롬프트 하나가 `T`·`TF` 두 경로에 들어가므로 5개만 걸어도 팔이 두 자릿수가
  되고 **선택 편향**이 커진다(§35-2o-4). 스윕에서 1~3위 + `origin: real-validated` 1개 정도로 끝낸다.
- `--no-exemplar` 는 **sim 참조 경로를 뺀다** — 실물에서 전부 실패했다(§38-1). `--preset` 도 불필요.
- `--text-conf` 는 스윕에서 고른 프롬프트의 `score` 최소값을 보고 정한다. **낮은 `score` 는 «품질» 이
  아니라 «필요한 문턱» 이다**(§39-13b) — 낮으면 0.05 를 쓴다. 🔴 내리면 배경을 집을 위험이 오르므로
  `segcmp` 시트의 «이탈» 열로 확인한다.
- 리포트 읽는 순서는 `CLAUDE.md` 의 「열린 항목 #2」 행에 있다 — **⓪ 배선 감사가 ❌ 면 아래를 읽지 말 것.**

## 5. 이 PC 로 되가져올 것

| 가져온다 | 크기 | 왜 |
|---|---|---|
| `runs/psweep_real01/results.json` · `results.csv` | ~10MB | 전 지표. 이것만 있으면 재분석된다 |
| `runs/psweep_real01/diff/` | ~100MB | 사람 라벨·군집·판정 시트 — **다시 만들 수 없는 것** |
| `runs/psweep_real01/masks/` | ~1GB | 서열을 다시 계산하려면 필요 |
| `docs/PROMPT_RANKING_real.md` | 수십 KB | 결과 표 |
| **`ov/`·`sheets/`** | **10~20GB** | ❌ **안 가져와도 된다** — `--rebuild-sheets` 로 다시 그린다 |

🔴 사진 원본(`assets/real_imgs/…`)도 함께 보관한다. 없으면 `masks/` 만으로는 오버레이를 못 그린다.

## 6. 자주 나는 문제

| 증상 | 원인·처방 |
|---|---|
| 이미지 수가 예상보다 적다 | 확장자 목록에 없는 파일 → 로그의 `⚠️ 건너뛴 파일` 줄을 볼 것 |
| 검출이 거의 0 | `--confidence` 가 높다. **0.05** 로 |
| 실패 사유가 `area …` 뿐 | `--full-area-min` 이 데이터와 안 맞는다(§39-2). 분포를 보고 다시 |
| `CUDA out of memory` | 큰 사진. 재시도가 자동으로 돌지만 계속 나면 사진을 **긴 변 3000px** 정도로 줄여 둔다 |
| 중간에 죽었다 | `results_partial.json` 확인 후 **처음부터 다시** 돌린다(재개 기능은 없다) |
| `flange` 결과가 이상하다 | `--ref-full-slug` 를 안 줬을 가능성. 로그에 `참조 3개 잡힘` 이 있는지 |
| 시트가 너무 크다 | `sheets --rows 8` 로 페이지를 잘게. 스윕 자체의 `by_image__*` 는 프롬프트 136개에서 **못 쓴다** |
| 판정 행 수가 안 맞는다 | 그 페이지의 이미지 수와 `--picks` 의 `;` 개수가 달라야 한다 → 시트 제목의 `pN/M` 확인 |

## 7. 한 장 요약

```bash
source envs/env.sh
# runs/ 안의 촬영에서 left 만 모으기
DST=assets/real_imgs/zedx_2026xxxx; mkdir -p "$DST"
for SRC in runs/real_zedx_*; do for f in "$SRC"/frame_*/left.png; do
    cp "$f" "$DST/$(basename "$SRC")_$(basename "$(dirname "$f")").png"; done; done

envs/seg_sam3/bin/python tools/sam3_prompt_sweep.py --imgs <사진> --out runs/psweep_real01 \
    --target full --prompts-json assets/prompts/real_testset.json \
    --confidence 0.05 --full-area-min 0.005 --note "<메모>"
envs/pose/bin/python tools/prompt_sweep_diff.py sheets --run runs/psweep_real01 --imgs <사진>
#   → diff_p*.png 를 눈으로 보고
envs/pose/bin/python tools/prompt_sweep_diff.py check --run runs/psweep_real01 --imgs <사진> \
    --page 1 --picks "…"
envs/pose/bin/python tools/prompt_sweep_diff.py rank --run runs/psweep_real01 \
    --md-out docs/PROMPT_RANKING_real.md
```
