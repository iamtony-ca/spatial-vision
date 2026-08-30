# 실물 사진 — SAM3 프롬프트 스윕 **복붙 순서** (다른 PC용)

> 목적: **실물 ZED X 사진에서 `full` 136개(§2)와 `flange` 20개(§2b)를 돌려**, 결과가 갈린 것만
> 눈으로 판정하고 서열을 다시 낸다. 그 서열이 「어느 프롬프트로 pose 까지 돌릴까」를 정한다.
>
> | | 실험군 파일 | 개수 | 갈리는가 |
> |---|---|---|---|
> | **`full`** (§2) | `assets/prompts/real_testset.json` | 136 | 실물 3라운드에서 **갈린 이미지 0장** → §3c 로 |
> | **`flange`** (§2b) | `assets/prompts/flange_real20.json` | 20 (+ 기준용 `full` 4) | **거의 다 갈린다** → 육안 판정을 실제로 한다 |
>
> - 경위·수치의 정본: **`docs/RESULTS.md §39`**
> - 현재 서열: **`docs/PROMPT_RANKING.md`**(`full`) · **`docs/PROMPT_RANKING_FLANGE.md`**(`flange`)
> - 🔴 **웹사진 서열은 실물로 전이되지 않을 수 있다**(교훈 #92·#100). 실물에서 다시 내는 게 이 문서다.
> - 🔴 **자르지 않는다.** 136개 전부 돌린다 — 실물에서 확인된 두 프롬프트가 웹 서열로는 **78위·87위**라
>   «상위 N 컷» 이면 잘린다(§39-15). 비용은 40장 기준 **약 17분**이다.

---

## 0a. 🔴 어느 파일을 쓰나 — **현행 3개뿐**이다

`assets/prompts/` 에 json 이 31개 있는데 **대부분 이력**이다. 라운드마다 «🟢 현행» 이라 적어 온 것이
혼동의 원인이었어서, **파일마다 맨 앞에 `_status` 를 박아 뒀다** — 열면 바로 보인다.

```bash
envs/pose/bin/python - <<'EOF'
import json, glob, os
for p in sorted(glob.glob("assets/prompts/*.json")):
    print(f"{os.path.basename(p):30s} {json.load(open(p))['_status'][:70]}")
EOF
```

| 파일 | 상태 | 무엇에 쓰나 |
|---|---|---|
| **`real_current.json`** | 🟢 **현행** | **`full` 정본** — `--prompts-json` · `--text-prompt` 는 여기서 고른다(§39-28). 현재 `full` **4개** |
| **`flange_real20.json`** | 🟢 **현행** | **`flange` 분할 스윕 정본** — 20개 + 판정 기준 `full` 4개. §2b 가 이걸 쓴다 |
| **`flange_top3.json`** | 🟢 **현행** | **`flange` pose 팔 후보 3개**(웹 근거). ⚠️ 실물 스윕(§2b)을 돌렸으면 **그 결과로 대체**한다 |
| `tested_prompts.json` | 📘 참조 | 장부 — 이미 시험한 프롬프트 전부. 중복 거르기용(`tools/prompt_ledger.py`). 실험군이 아니다 |
| `flange_human_labels.json` | 📘 참조 | **사람 라벨 원본** — 시트·마스크가 `runs/`(gitignore)라 **다시 만들 수 없다** |
| 나머지 26개 | ⚪ 이력 | 좁혀 온 계보. **되돌릴 때만** 연다 |

**«현행» = 지금 명령에 그대로 거는 파일. «이력» = 그 파일이 만들어진 시점의 스냅샷**이고,
좁히다 후보가 모자라거나 조건이 바뀌면 **되돌아가는 곳**이다(버린 게 아니다).

- `full` 계보 — `real_testset`(136) → `real_pass81` → `real_pass70_50cm` → `real_pass58` →
  `real_pass37` → `real_top15` → `real_final14` → `real_final12` → `real_final11` →
  **`real_top4` = 현행 `real_current`**
- `flange` 계보 — `flange_round3`(35) → `round4`(52) → `round5`(73) → `round6`(43) →
  `flange_top20`(20) → **`flange_real20`(20, 재정렬) · `flange_top3`(3)**
- ⚠️ **되돌리는 조건**은 둘뿐이다 — **① 「오선택」 축을 열 때**(여러 FOUP·로드포트 전경. 지금까지 전
  표본이 단일 물체 씬이라 **측정된 적이 없는** 축이다) **② 개체·조명이 바뀔 때**. 그냥 넓히는 것은
  얻을 게 없다(§39-30b: 158장을 더해도 서열 +0.943 로 불변).

🔴 **`real_current.json` 의 `flange` 블록을 2026-08-30 에 현행 20개로 갈아 끼웠다** — 그전까지 **round-4
이전 21개**가 실려 있어서 이 파일로 flange 스윕을 돌리면 낡은 집합이 돌았다(`handling flange` 계열은
§39-34 에서 확정 기각, `black top flange on top of the plastic box` 는 sim 에서 R 최대 176.7°).
옛 21개는 같은 파일 `_dropped_flange_old21` 에 **대기**한다.
⚠️ 그래도 **flange 스윕은 `flange_real20.json` 을 쓴다** — 판정 기준 `full` slug 과 3벌 합산 메타가 그쪽에 있다.

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

---

## 2b. `flange` 프롬프트 **20개** — 실물에서 좁히는 전용 순서

현행 flange 실험군은 **`assets/prompts/flange_real20.json`** 이다(`flange` 20개 + 판정 기준용 `full` 4개).
웹 «어려운» 40장 **세 벌**을 사람이 판정해 합산한 서열이고(n≈83), 표는 **`docs/PROMPT_RANKING_FLANGE.md`**.

🔴 **20개를 다 가져가는 이유** — ① 3벌 합산 Wilson 구간에서 **13개가 1위와 구분되지 않는다**
② **`flange` 는 `full` 과 달리 도메인을 안 넘는다**(교훈 #92). 웹 하위권이 실물 상위일 수 있다.
★ 리트머스: `origin: real-validated` 인 둘(`top mounting plate with a hole` 웹 1위 ·
`black square bracket on top` 웹 4위)이 **실물에서도 상위인가** — 그게 «웹→실물 이전이 되는가» 를 말해 준다.

### ① 스윕 (40장 기준 ≈ 3분)

```bash
envs/seg_sam3/bin/python tools/sam3_prompt_sweep.py \
    --imgs assets/real_imgs/zedx_2026xxxx \
    --out  runs/psweep_real01_fl \
    --target full,flange \
    --prompts-json assets/prompts/flange_real20.json \
    --confidence 0.05 \
    --full-area-min 0.005 \
    --ref-full-slug f002,f005,f007 \
    --note "실물 ZED X · flange 상위 20 · 검정 몸체 28/40/50cm"
```

| 인자 | 왜 |
|---|---|
| `--target full,flange` | 🔴 **`flange` 만 주면 안 된다.** flange 판정은 같은 이미지의 **`full` 마스크를 «물체 기준 프레임»** 으로 쓴다(몸체 ∪ 몸체 바로 위 영역). `full` 이 없으면 기준이 없다 |
| `--ref-full-slug f002,f005,f007` | 그 기준을 만들 `full` slug. **기본값(`s_boxy,d_fooup_long,s_cube`)은 이 파일에 없다** — 반드시 준다. 셋은 현행 `full` 실험군 A·W·B 다 |
| `--confidence 0.05` | flange 는 작아서 점수가 낮게 나온다. 문턱은 사후에 정한다 |

🔴 **로그에 `flange 기준 full 참조 3개 잡힘` 이 떠야 한다. 3개 미만이면 그 런의 flange 결과는 무효**다(§37-2).
확인:

```bash
grep -m1 "flange 기준 full 참조" runs/psweep_real01_fl/report.md || \
    echo "🔴 참조가 안 잡혔다 — --ref-full-slug 확인"
```

### ①b. 🟢 먼저 **`report.md` 만 읽고** 20개를 서열화한다

스윕이 끝나면 `runs/psweep_real01_fl/report.md` 에 **결정용 종합표**가 들어 있다
(`### 🟢 target = flange — 결정용 종합표`). **이 표 하나로 20개를 줄일 수 있게** 만들어 뒀다:

| 열 | 무엇 | 판정에 쓰는 법 |
|---|---|---|
| 통과 / 검출 | 형상 휴리스틱 / 인스턴스 유무 | **통과 ≪ 검출** = 찾긴 하는데 **엉뚱한 것** (오선택 대리) |
| **`score` 최소** | 전 이미지 중 최저 자신감 | ★ **미검출까지의 여유**. `--text-conf` 근거. 🔴 중앙값 아님 |
| `in_region` · `rel_y` | 물체 기준 위치 | 낮은 `in_region` · 큰 `rel_y` = 문 링·손잡이를 집었다 |
| 주 실패사유 | 떨어진 이유 최빈값 | `no`=문턱 · `rel_y`=위치 · `area`=크기 · `solidity`=모양 |
| 웹 정답률 · 95%CI · **핵명사** · 1위와 구분? | 웹 3벌 사전정보 | 🔴 **20개 중 13개가 «동률»** — 웹 순위로 자르지 않는다 |

**고르는 절차**(리포트에도 같은 내용이 박혀 있다):
① 검출 < 절반 제외 → ② 통과 ≪ 검출 제외 → ③ `score` 최소값 내림차순 →
④ **여기서 눈으로**(`sheets/by_image__flange__*.png`) → ⑤ 갈린 것만 `prompt_sweep_diff`(아래) → ⑥ 3~4개.

🔴🔴 **flange 는 쓰이는 자리가 둘이고 요구 수준이 다르다 — 같이 고르면 안 된다**:

| 경로 | 마스크의 역할 | 필요한 것 |
|---|---|---|
| **TF** (`--primary flange`) | `guess_translation` 을 **직접** 결정 | 🔴 **최고 IoU** — 어긋나면 90°/180° 뒤집힘(§32-1) |
| **RH2s** (`--primary full` + `--flange-mask-from seg`) | 2단계 depth 를 **자르기만** | 🟢 **검출률·오선택 없음**이면 충분(IoU 0.93 차가 pose 를 안 바꿨다, §38-12) |

### ② 갈린 것만 시트 → 눈으로 (🔴 `--target flange` 를 빠뜨리지 말 것)

```bash
envs/pose/bin/python tools/prompt_sweep_diff.py sheets \
    --run runs/psweep_real01_fl --target flange \
    --imgs assets/real_imgs/zedx_2026xxxx --rows 8
```

★ **`full` 과 달리 flange 는 거의 항상 갈린다** — 웹 237장에서 `full` 은 79장만 갈렸는데
**flange 는 234장**이었다(§39-32a). 즉 `full` 에서 건너뛰었던 ②③을 **여기서는 실제로 돌리게 된다.**
👉 §3 의 「갈린 이미지 0장」 우회로(`slugs`)는 flange 에서는 거의 안 쓰인다.

### ③ 판정 기록 — 페이지마다

```bash
envs/pose/bin/python tools/prompt_sweep_diff.py check \
    --run runs/psweep_real01_fl --target flange \
    --imgs assets/real_imgs/zedx_2026xxxx \
    --page 1 --picks "2;2,3;2;3;2,3;2;2;2"
```

- 🔴 **칸1 = 원본**이므로 «2번째» = 군집 1. 행 수는 그 페이지의 이미지 수와 같아야 한다.
- 🔴🔴 **어느 한 프롬프트의 마스크를 «정답» 으로 삼지 않는다** — 그 프롬프트는 자기 자신과 IoU 1.0 이라
  **구조적으로 만점**이 된다. 웹에서 실측 **8%p**(100% → 92.5%)였고 **1위가 바뀌었다**(§39-37).
  반드시 시트를 보고 **직접** 고른다.
- ⚠️ **«미검출이 정답» 인 이미지가 있다** — flange 가 안 보이는 각도면 검출한 쪽이 오답이다.
  웹 150장에서 3장 나왔다(§39-38·§39-39). 그런 행은 아무것도 안 고르거나 원본 칸(1)을 고른다.

### ④ 서열

```bash
envs/pose/bin/python tools/prompt_sweep_diff.py rank \
    --run runs/psweep_real01_fl --target flange --combine human \
    --md-out docs/PROMPT_RANKING_FLANGE_real.md
```

- **`--combine human` 을 쓴다** — flange 는 거의 다 갈려서 «합의» 열이 잘 안 선다. 사람 판정이 정본이다.
- 🔴 `--md-out` 은 **`runs/` 밖으로**(`runs/` 는 통째로 `.gitignore`).

### ⑤ 3~4개로 좁혀 파일로

```bash
envs/pose/bin/python tools/prompt_sweep_diff.py slugs \
    --run runs/psweep_real01_fl --target flange \
    --src-json assets/prompts/flange_real20.json \
    --with-prompt --json-out assets/prompts/flange_real_pass.json
```

🔴 **나온 json 에는 `flange` 키만 들어간다** — 다음 라운드에 그대로 먹이려면 `full` 블록을 도로 붙여야
`--ref-full-slug` 가 산다:

```bash
envs/pose/bin/python - <<'EOF'
import json
p = "assets/prompts/flange_real_pass.json"
d = json.load(open(p))
d["full"] = json.load(open("assets/prompts/flange_real20.json"))["full"]
json.dump(d, open(p, "w"), ensure_ascii=False, indent=1)
print(f'flange {len(d["flange"])} + full {len(d["full"])} → {p}')
EOF
```

⚠️ `flange` 는 **개체·조명이 바뀔 때마다 다시 골라야** 한다 — `full` 과 달리 도메인을 안 넘는다(§37-13).
좁히다 후보가 모자라면 되돌릴 순서는 `flange_top3` → `flange_real20` → `flange_round6`(43) → `flange_round5`(73).

### 🔴 `flange_top20.json` 과 헷갈리지 말 것

같은 디렉토리에 **`flange_top20.json`** 이 있는데 **프롬프트 20개의 문장·slug 이 완전히 같다.**
다른 것은 **정렬 근거**뿐이다 — 쓰는 것은 **`flange_real20.json`** 이다.

| | `flange_top20.json` | **`flange_real20.json`** ← 이걸 쓴다 |
|---|---|---|
| 서열 근거 | 어려운 웹 40장 **한 벌** (n=39, §39-37) | 어려운 40장 **세 벌 합산** (n≈83, §39-39) |
| 통계 | 정답 수만 | **Wilson 95% CI** · `pooled` · `per_round` · **`sig_worse_than_1st`** |

**그 사이에 순위가 바뀌었다** — `black square top flange` **1위 → 7위**,
`black square plastic top bracket` **10위 → 3위**. 한 표본의 서열은 표본을 안 넘는다(교훈 #105).
★ `sig_worse_than_1st` 는 `real20` 에만 있고, **하위 6개만** 1위와 유의하게 나쁘다
= **나머지 13개는 구분되지 않는다** — 20개를 다 가져가는 근거다.
(`flange_top20.json` 파일 안에도 `_superseded_by` 로 같은 내용을 박아 뒀다.)

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
    --text-prompt-flange "<2b-④ 에서 1위>" --text-conf-flange 0.05 \
    --note "1차 · 프롬프트 스윕 1위" --true-distance-mm 300
```

- **`--text-prompt-flange` 를 주면 TF 경로**(`seg_txtf` → `fp_txtf --primary flange` → **TF1·TF3**)가 생긴다.
  안 주면 그 두 팔이 통째로 빠진다 — 🔴 **값이 필요해서 `--mode all` 로도 자동으로 못 켠다.**
  (`--sam3-text`·`--ism` 은 `--mode all` 이 알아서 켠다.)
- ★ **왜 TF 를 굳이 도는가** — `--primary full` 은 §22 유효 해상도 때문에 **t 가 구조적으로 3배 나쁘다**
  (4.34 vs 1.38 mm/px). sim GT 로 재면 t 중앙 1.973 → **1.095mm (1.8배)**(§37-9b). 그 천장을 넘는 유일한 길이다.
- 🔴 **대가와 안전망**: flange 계열은 **R 이 2배 나쁘고**, 마스크가 조금만 어긋나면 **90°/180° 로 뒤집힌다.**
  **TF1 을 단독 채택하지 말고 A1/I1·COMBO 와 나란히 놓고 «회전이 90° 배수로 어긋나면 버린다»**(§37-9c).
  🔴 실사진 1위 프롬프트가 sim 검정에서 몸체 전체를 집어 **R 최대 176.7°** 를 낸 전례가 있다 —
  **오버레이(`overlay_combo.png`)로 «무엇을 집었는지» 를 반드시 눈으로 본다.**
- `--text-conf-flange` 는 **기본 0.15**. flange 는 작아서 점수가 낮게 나오므로 미검출이면 **0.05** 로 내리되,
  내린 뒤에는 `segcmp` 의 «이탈» 열과 오버레이로 배경을 집지 않았는지 확인한다.
- 🔴 **팔은 3~4개까지**다. 프롬프트 하나가 `T`·`TF` 두 경로에 들어가므로 5개만 걸어도 팔이 두 자릿수가
  되고 **선택 편향**이 커진다(§35-2o-4). 스윕에서 1~3위 + `origin: real-validated` 1개 정도로 끝낸다.
  프롬프트를 여러 개 비교할 때는 **한 번에 하나씩, `--out` 을 나눠** 돌리고 `compare_runs.py` 로 합친다.
- ⚠️ **마스크가 「판(plate)만」 인지 「규격 목(neck)까지」 인지도 이때 본다** — 판만이 유리하다(§40).
  시선 경사 ≤40° 면 차이가 없고, 55° 부터 갈리며 80° 에서 초기 t 가 **+11.9~16.6mm** 벌어진다.
  🔴 **프레임마다 목을 넣었다 뺐다 하는 프롬프트가 가장 나쁘다**(초기값 지터).
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
| **`runs/psweep_real01_fl/`** 의 `results.json`·`diff/`·`masks/` | ~200MB | **flange 런**. 🔴 `diff/human_labels.json` 이 **다시 만들 수 없는 것** |
| `docs/PROMPT_RANKING_FLANGE_real.md` · `assets/prompts/flange_real_pass.json` | 수십 KB | flange 결과 표·좁힌 실험군 |
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
| `flange` 결과가 이상하다 | `--ref-full-slug` 를 안 줬을 가능성. 로그에 `참조 3개 잡힘` 이 있는지 (§2b-①) |
| `flange` 인데 `sheets`/`check`/`rank` 가 `full` 것을 낸다 | **`--target flange` 를 빠뜨렸다.** 세 부명령 전부에 붙여야 한다 |
| `slugs --json-out` 파일이 다음 스윕에서 «참조 0개» | 그 json 에 **`flange` 키만** 있다. §2b-⑤ 의 병합 스니펫으로 `full` 을 도로 붙인다 |
| TF1·TF3 팔이 안 생긴다 | `--text-prompt-flange` 를 안 줬다. **`--mode all` 로도 자동으로 안 켜진다**(값이 필요하다) |
| TF1 회전이 A1/I1 과 90°·180° 다르다 | `--primary flange` 의 고유 실패 모드. **TF 를 버린다.** 오버레이로 무엇을 집었는지 먼저 볼 것(§37-9c) |
| 시트가 너무 크다 | `sheets --rows 8` 로 페이지를 잘게. 스윕 자체의 `by_image__*` 는 프롬프트 136개에서 **못 쓴다** |
| 판정 행 수가 안 맞는다 | 그 페이지의 이미지 수와 `--picks` 의 `;` 개수가 달라야 한다 → 시트 제목의 `pN/M` 확인 |

## 7. 한 장 요약

```bash
source envs/env.sh
# runs/ 안의 촬영에서 left 만 모으기
DST=assets/real_imgs/zedx_2026xxxx; mkdir -p "$DST"
for SRC in runs/real_zedx_*; do for f in "$SRC"/frame_*/left.png; do
    cp "$f" "$DST/$(basename "$SRC")_$(basename "$(dirname "$f")").png"; done; done

IMGS=assets/real_imgs/zedx_2026xxxx

# ── full 136개 ──────────────────────────────────────────────────────────────
envs/seg_sam3/bin/python tools/sam3_prompt_sweep.py --imgs $IMGS --out runs/psweep_real01 \
    --target full --prompts-json assets/prompts/real_testset.json \
    --confidence 0.05 --full-area-min 0.005 --note "<메모>"
envs/pose/bin/python tools/prompt_sweep_diff.py sheets --run runs/psweep_real01 --imgs $IMGS
#   → diff_p*.png 를 눈으로 보고  (갈린 게 0장이면 §3c 의 slugs 로)
envs/pose/bin/python tools/prompt_sweep_diff.py check --run runs/psweep_real01 --imgs $IMGS \
    --page 1 --picks "…"
envs/pose/bin/python tools/prompt_sweep_diff.py rank --run runs/psweep_real01 \
    --md-out docs/PROMPT_RANKING_real.md

# ── flange 20개  (🔴 --target full,flange · --ref-full-slug · 뒤 3개는 --target flange) ──
envs/seg_sam3/bin/python tools/sam3_prompt_sweep.py --imgs $IMGS --out runs/psweep_real01_fl \
    --target full,flange --prompts-json assets/prompts/flange_real20.json \
    --confidence 0.05 --full-area-min 0.005 --ref-full-slug f002,f005,f007 --note "<메모>"
grep -m1 "flange 기준 full 참조" runs/psweep_real01_fl/report.md   # 🔴 «3개 잡힘» 이어야 한다
envs/pose/bin/python tools/prompt_sweep_diff.py sheets --run runs/psweep_real01_fl \
    --target flange --imgs $IMGS --rows 8
envs/pose/bin/python tools/prompt_sweep_diff.py check  --run runs/psweep_real01_fl \
    --target flange --imgs $IMGS --page 1 --picks "…"
envs/pose/bin/python tools/prompt_sweep_diff.py rank   --run runs/psweep_real01_fl \
    --target flange --combine human --md-out docs/PROMPT_RANKING_FLANGE_real.md

# ── pose (팔 3~4개) ─────────────────────────────────────────────────────────
envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out runs/real01_A \
    --mode all --no-exemplar \
    --text-prompt "<full 1위>" --text-conf 0.05 \
    --text-prompt-flange "<flange 1위>" --text-conf-flange 0.05 \
    --note "<메모>" --true-distance-mm 300
```
