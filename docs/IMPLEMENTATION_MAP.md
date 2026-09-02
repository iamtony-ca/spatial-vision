# 우리가 구현한 코드 지도 — 배포 구성 `RH1` 이 실제로 부르는 것 (중간보고서용)

> **범위**: *"`RH1` 을 한 번 돌릴 때 **우리 코드** 중 무엇이 실행되나"* 만 다룬다.
> upstream 을 어디까지 건드렸나는 **`RH_RATIONALE.md §9`**, 왜 그렇게 설계했나는 **`§2`·`STAGE2_TRANSLATION.md`**,
> 측정치는 **`RESULTS.md`** 다. **수치를 여기서 새로 만들지 않는다.**
> 코드 확인일 **2026-09-02**.

---

## 0. 🔴 먼저 — 배율이 **셋** 이고 서로 다른 것이다

가장 흔한 혼동이라 맨 앞에 둔다.

| 인자 | 값 | 무엇의 배율인가 | 어디서 정해지나 |
|---|---|---|---|
| `stereo_onnx --scale` | **0.5** | **스테레오 입력 영상** 축소 (ONNX OOM 회피) | 러너 `--stereo-scale` 기본 0.5 (`run_group_a.py:2640`) |
| `pose_fp --input-scale` | **0.75** | **FoundationPose 입력 영상** 축소 | 🔴 **COMBO 는 `"0.75"` 를 코드에 박아 넣는다**(`run_group_a.py:478`) |
| 러너 `--input-scale` | 기본 0.5 | **A·I·T 그룹 전용** | `run_group_a.py:2641` |

★ **`RH1` 의 FP 배율은 `0.75` 다.** 러너 플래그 `--input-scale` 을 바꿔도 **COMBO 팔에는 안 먹는다.**
`RH2` 만 `0.5` 기반이다.

| 팔 | FP 런 | `--input-scale` |
|---|---|---|
| `RP1` / **`RH1`**(하이브리드) | `fp_c075` | **0.75** |
| `RP2` / `RH2`(하이브리드) | `fp_c050` | 0.5 |
| `RP3` (CHULL) | `fp_chull` | 0.75 + `--flange-mask-proj hull` |

⚠️ `0.75` 는 `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` 가 없으면 1920×1200 에서
**frame_0002 부터 OOM** 이다(§38-4). `envs/env.sh` 가 그것을 건다 — **반드시 먼저 source 한다.**

---

## 1. 호출 사슬 (한 장)

```
tools/run_group_a.py                      ← 오케스트레이터. venv 를 subprocess 로 오간다
│                                            (스테이지끼리 in-process 로 못 엮인다 — venv 가 다르다)
├─[envs/stereo_onnx] spatial_vision/stages/stereo_onnx.py   --scale 0.5     → <out>/st/
│     └─ spatial_vision/contracts.py       (write_stereo_frame · 산출물 스키마)
│
├─[envs/seg_sam3]    spatial_vision/stages/segment_sam3.py                  → <out>/seg_txt/
│     └─ spatial_vision/contracts.py       (select_index — center + score_frac 0.9)
│
├─[envs/pose]        spatial_vision/stages/pose_fp.py       --input-scale 0.75  → <out>/fp_c075/
│                                          (--primary full · --flange-mask-from pose · stage2 on)
│
└─[envs/pose]        spatial_vision/eval/hybrid_pose.py                     → <out>/hyb_combo/  ★ RH1
      --r-dir fp_c075 --r-name pose_coarse.json      (회전)
      --t-dir fp_c075 --t-name pose_refined.json     (평행이동)
```

**우리 파일은 다섯이다** — 러너 1 + 스테이지 3 + 병합 1, 그리고 공유 모듈 `contracts.py`.

---

## 2. 파일별 역할과 «우리 / upstream» 경계

| 파일 | venv | 우리가 한 것 | upstream 이 한 것 |
|---|---|---|---|
| `tools/run_group_a.py` | pose | 스텝 정의·멱등 실행·리포트. `RH1` 은 그중 **4스텝** | — |
| `stages/stereo_onnx.py` | stereo_onnx | **전처리(정규화·패딩)·후처리(`depth = fx·B/disparity`)를 직접 구현** · ORT 세션 관리 | 🟢 **없음** — 라이선스 때문에 `third_party/FoundationStereo` 를 **import 하지 않는다**(가중치만 NGC ONNX) |
| `stages/segment_sam3.py` | seg_sam3 | 프롬프트 질의 래핑 · **인스턴스 선택**(`select_index`) · 산출물 규약 | SAM3 모델·`Sam3Processor` (무수정) |
| `stages/pose_fp.py` | pose | **2단계 조립** — 인스턴스 2개 생성 · 씨앗 주입 · flange 마스크 투영 · depth 마스킹 | `FoundationPose` 클래스와 `register`/`track_one` (무수정) |
| `eval/hybrid_pose.py` | pose | **R·t 접합** (85줄, 추론 0) | — |
| `contracts.py` | 전부 | **유일한 공유 코드**(245줄) — 산출물 스키마 + `select_index` + `rotation_angle_deg` | — |

★ **가장 큰 효과를 내는 부품이 가장 작다** — `hybrid_pose.py` 는 **85줄이고 GPU 를 안 쓴다.**
`pose_coarse.json` 의 `R` 과 `pose_refined.json` 의 `t` 를 합쳐 새 JSON 을 쓰는 것이 전부인데,
§38-7 에서 ADD 중앙 **1.395mm** 로 어느 단일 단계보다 1.5~2배 좋았다.

---

## 3. 스테이지별로 «우리 코드가 실제로 하는 일»

### 3.1 `stereo_onnx.py` — upstream 코드 0줄

🔴 **상업화 경로 때문에 구조가 이렇다**(`LICENSES.md`): GitHub `FoundationStereo` 는 research-only 이고
NGC ONNX 가중치만 상업 사용 가능하다. **가중치가 상업 가능해도 repo 코드는 아니므로**
전처리·후처리를 repo 없이 다시 썼다. → **이 파일에 `third_party/FoundationStereo` 를 import 하면
상업 경로가 깨진다.**

산출물: `disparity.npy`(px) · `depth.png`(16-bit mm, **0 = invalid**) · `valid.png` · `meta_stereo.json`.

### 3.2 `segment_sam3.py` — 모델은 그대로, **선택만 우리 것**

SAM3 는 개념에 맞는 **인스턴스 여러 개**를 낸다. *"어느 것이 타깃인가"* 는 모델이 못 푸는 문제라
시스템이 정해야 한다 → `contracts.select_index(rule="center", score_frac=0.9)`.

🔴 **이것이 감사표 #4 — upstream 에 대응물이 없는 유일한 구성요소**다(`RH_RATIONALE §6.4`).
★ 다만 **단일 대상 장면에서는 구조적으로 비활성**이다: 점수 게이트를 통과하는 후보가
**60/60 프레임에서 1개**라 뒤의 두 단계가 결과에 관여하지 않는다(§44-24k).

산출물: `mask_full.png` · `det_full.json` · `meta_segment_full.json`.

### 3.3 `pose_fp.py` — **여기가 우리 설계의 본체**

같은 파일 안 헬퍼: `load_mesh_m`(mm→m) · `project_mask_faces`(삼각형 합집합 투영, 교훈 #20) ·
`pose_to_json` · `to_band` · `relative_cam_transform`.

**stage1** (upstream 용법 그대로)
```python
coarse = est1.register(K=K, rgb=rgb, depth=depth_m, ob_mask=(mask_full > 127), iteration=5)
```
- 메시 `full.ply`, 마스크 = **SAM3 결과**
- 🔴 그 마스크는 **초기값 계산에만** 쓰인다(`estimater.py:184·203·206`). 네트워크에 들어가는
  `rgb`/`depth` 는 **마스킹되지 않는다** — upstream 그대로다.

**stage2** (upstream 에 대응물 없음 — 우리 조립)
```python
mf         = project_mask_faces(mesh_flange, coarse, K, hw)   # ① top_flange.ply 를 coarse pose 로 투영
depth_crop = np.where(mf > 127, depth_m, 0.0)                 # ② 그 밖 depth 를 «측정값 없음» 으로
est2.pose_last = torch.as_tensor(coarse @ T, ...)             # ③ 씨앗 주입 (register 를 건너뛴다)
refined    = est2.track_one(rgb=rgb, depth=depth_crop, K=K, iteration=5)
```
- 메시가 `top_flange.ply` 로 **바뀐다** — 그것이 이득의 원천이다(`STAGE2_TRANSLATION.md`).
- ★ **마스크 출처가 stage1 과 다르다**: stage1 = SAM3, stage2 = **메시 투영**.
  → **`RH1` 은 SAM3 의 flange 검출에 전혀 의존하지 않는다.** flange 프롬프트는 실물에서
  20개 중 **2개**만 살아남았으므로(§41) 이 설계가 그 취약축을 아예 안 밟는다.
- ②③의 근거·측정은 `RH_RATIONALE §9.3·§9.5`.

산출물: `pose_coarse.json` · `pose_refined.json` · `mask_flange_proj.png` · `meta_pose.json`.

### 3.4 `hybrid_pose.py` — 파일 병합

```python
{"R": R["R"], "t_mm": T["t_mm"], "source": "hybrid(R=fp_c075/pose_coarse, t=fp_c075/pose_refined)"}
```
⚠️ 출력 파일명이 **`pose_coarse.json`** 이다(하류 도구가 그 이름을 찾는다). 산출물은
`<out>/frame_*/pose_coarse.json` + `meta_hybrid.json`.
⚠️ 한쪽 디렉토리가 비면 **조용히 0장**을 쓰므로 개수를 반드시 찍는다(`n_written`).

---

## 4. 스테이지 사이 규약 (= 디스크)

venv 가 달라 in-process 로 못 엮이므로 **통신은 파일**이고, 그 경계의 유일한 공유 코드가
`contracts.py`(245줄)다. **numpy + opencv 만 의존**한다 — 어느 venv 에서도 import 돼야 하므로
torch/onnxruntime 을 여기 들이지 않는다.

굳어진 규약(어기면 조용히 틀린다): **길이 mm** · depth 는 **16-bit PNG, 0 = invalid** ·
pose 는 **`cam_T_obj`** · **pose 원점 = flange 주 상면 중심** · **up axis +Z** ·
없는 값을 만들어내지 않는다(ONNX 는 confidence 가 없으므로 `null`).

---

## 5. `RH1` 만 단독으로 돌리는 명령

```bash
cd <ws>/src/vision && source envs/env.sh        # 🔴 필수 — 없으면 0.75 가 OOM

envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx \
    --in <cap> --out <o>/st --scale 0.5 \
    --model weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx

envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 \
    --in <cap> --out <o>/seg_txt --target full \
    --prompt "cube shaped sealed plastic wafer pod" --confidence 0.05 \
    --select center --select-score-frac 0.9

envs/pose/bin/python -m spatial_vision.stages.pose_fp \
    --in <cap> --out <o>/fp_c075 --obj assets/obj/foup_300_semi_r2 \
    --masks <o>/seg_txt --depth stereo --depth-dir <o>/st \
    --primary full --flange-mask-from pose --input-scale 0.75

envs/pose/bin/python -m spatial_vision.eval.hybrid_pose \
    --r-dir <o>/fp_c075 --r-name pose_coarse.json \
    --t-dir <o>/fp_c075 --t-name pose_refined.json --out <o>/hyb_combo
```

---

## 6. 🔴 `RH1` 에 **관여하지 않는** 우리 모듈

러너가 같은 런에서 함께 부르지만 **결과에 들어가지 않는다** — 진단·리포트·다른 팔 전용이다.
보고서에서 «파이프라인» 으로 세면 안 된다.

| 모듈 | 무엇 | 왜 RH1 과 무관한가 |
|---|---|---|
| `stages/refine_contour.py` | 테두리 정합 | **`RH1` 은 정합을 안 쓴다**(§38·D5). A1 등 다른 팔이 쓴다 |
| `eval/lr_consistency.py` | 좌우 투영 일관성 | GT-free **평가** 지표 |
| `eval/scale_check.py` · `eval/group_stats.py` | 거리 네 번째 다리 · 통계 취합 | 리포트 |
| `viz/overlay_pose.py` · `viz/seg_compare.py` · `viz/diag_sheet.py` · `viz/result_charts.py` | 판단용 그림 | 리포트 |
| `stages/segment_sam6d.py` | ISM 경로 | **I 그룹**(대조군) 전용 |
| `stages/stereo_torch.py` | torch 스테레오 | 대조군. 🔴 research-only 라 상업 경로 아님 |

---

## 7. 보고서용 한 문단

> *"제안 파이프라인은 공개 기반모델 세 종(FoundationStereo·SAM3·FoundationPose)을 **소스 수정 없이**
> 조합한다. 구현한 코드는 스테이지 세 개와 병합 모듈 하나, 그리고 스테이지 경계의 데이터 규약
> 모듈 하나다. 스테이지는 서로 다른 가상환경에서 독립 프로세스로 실행되며 디스크를 통해서만
> 통신한다. 기여는 ① 스테레오 상업 경로의 전·후처리 재구현, ② 다중 인스턴스 상황의 대상 선택
> 규칙, ③ 메시를 교체하는 2단계 정합 구성과 그 입력 처리, ④ 두 단계의 회전·평행이동을 결합하는
> 하이브리드 자세 산출이다. 이 중 ④는 상위 구현의 **자세 갱신이 카메라 기준으로 분리(disentangled)
> 되어 있다는 성질**(원논문 §5.3)에 의해 정당화된다."*

⚠️ **같이 적을 것**: 상업 경로는 스테레오 **가중치**에만 열려 있고 repo 코드는 아니다(`LICENSES.md`).
⚠️ 그리고 **§4 한계**(실물 GT 없음 · 계열 안 구분 불가 · CAD 불일치 축)를 반드시 병기한다.
