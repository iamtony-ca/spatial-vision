# PIPELINE_PLAN.md — spatial_vision_ws 구현 계획

> 목표 파이프라인
> ```
> camera (Isaac Sim | real stereo)
>      │  left/right RGB + intrinsics + baseline
>      ▼
> [FoundationStereo]   disparity → metric depth
>      ▼
> [Segmentation: SAM6D-ISM | SAM3]   full-obj mask + top-flange mask
>      ▼
> [FoundationPose]  ① 원거리 coarse(전체 CAD)   0.8~1.2m
>                   ② 근접 재추정(top-flange CAD) 0.35~0.5m    # t 1.85 → 0.70mm
>      ▼
> 6D pose (+ eval: GT 대비 R/t error, contour overlay)
> ```
>
> 🔴 **위 거리는 옛 sim 기하(fx 952~1200 @1280×720)다.** ZED X 2.2mm 확정 후 **0.22~0.30m** 로 바뀌었고,
> 🔴🔴 **2026-09-01 실물 n=40 × 3거리로 다시 바뀌었다 — 현행 배포 대역은 `0.56~0.66m` 단일 단계**다
> (`RESULTS.md §44-2·§44-9a`). 28cm 에서 `full` 경로가 **19.4% [14.0, 26.2] 대실패**하고
> **팔 선택으로 못 푼다**. 56·66cm 은 둘 다 **0/40**.
> 🔴 ~~기전은 «잘림 → 초기값이 수렴 분지 경계»~~ → **sim 이 재현하지 못해 «미규명» 으로 되돌아갔다**
> (`§44-24d`). **관측은 유효하고 이유가 열려 있다.**
> 🔴🔴 **그리고 «대역» 은 미정이다** — 35~50cm·66cm 초과를 안 쟀고(§44-18c), sim 씬 고정 사다리에서는
> **오선택을 빼면 KPI 가 전 거리 ~100%** 라 **«거리 최적점» 자체가 분할의 성질**이었다(`§44-24c`, 교훈 #111).
> ★ 거리를 올리는 대가가 없다 — 배포본 `RH1` 은 **정합을 안 쓰므로** §34-9 의 «광각에서 정합 이득
> 0.82×» 가 적용되지 않고, §22 로 `--primary full` 의 t 천장은 **거리 무관**이다.
> ⚠️ **`full` 과 `flange` 의 실패가 배타적**이라(28cm full 5~10/40 ↔ flange 0/40 · 56cm 그 반대)
> **두 경로 교차검증**이 안전망으로 승격됐다. → `RESULTS.md §44`, `docs/CAMERAS.md`
> 전제: 대상 obj 의 3D CAD 를 보유 (`assets/cad/300mm_foup/`). ⚠️ **`foup_300mm/` 은 삭제된 구 경로**다(§1.1) — 현행은 `300mm_foup/`.

**이 문서는 계획·설계 의도**만 담는다. **측정된 결과·검증 수치는 [`RESULTS.md`](RESULTS.md) 가 정본**이다
(수치를 두 곳에 적으면 갈라진다). 라이선스는 [`LICENSES.md`](LICENSES.md), 배경 요구사항은
[`CONSUMER_6DPOSE.md`](CONSUMER_6DPOSE.md).
**신규 객체에 어떤 파이프라인을 골라야 하는가**는 [`PIPELINE_CATALOG.md`](PIPELINE_CATALOG.md) —
이 문서(계획)와 `RESULTS.md`(측정) 사이의 **선택 규칙**을 담당한다.

---

## 0. 이 워크스페이스의 위치

| | |
|---|---|
| `sdg_ws` (형제 ws) | **생산자** — Isaac Sim 기반 범용 SDG 프레임워크. 객체 비종속(`obj_id` 만 앎). |
| **`spatial_vision_ws` (여기)** | **소비자** — 특정 obj(FOUP)에 대한 6D pose 추정 파이프라인. 객체 특이 로직(top flange·2-stage·keypoint)은 **전부 여기 둔다**. |

**standalone 원칙**: sdg_ws 를 import 하지 않는다. 필요한 코드(camera randomizer, BOP writer, intrinsics 세팅 등)는
**복사해서** 이 ws 안에 둔다. 나중에 sdg_ws 로 역통합(stereo rig = SDG 로드맵 §5-6 항목 I)할 가능성은 열어두되,
지금 의존하지 않는다.

---

## 1. 확인된 전제 (2026-08-06 실측)

> ⚠️ **§1.1–1.2 는 구 CAD(`foup_300mm`) 기준이며 2026-08-07 에 대체됐다.** 현행 객체는
> `assets/cad/300mm_foup/300mm_SEMI_FOUP.step` → `assets/obj/foup_300_semi` 이고, 실측·비교는
> [RESULTS.md § 신 CAD 전환](RESULTS.md#-신-cad-전환--300mm-semi-foup-2026-08-07) 이 정본이다.
> 아래는 "무엇을 어떻게 검증했나" 의 기록으로 남긴다.

### 1.1 CAD — `assets/cad/foup_300mm/` (구, 삭제됨)

| 항목 | 값 | 근거 |
|---|---|---|
| `FOUP 300.stp` 단위 | **mm** | STEP `CONVERSION_BASED_UNIT('MILLIMETRE')` |
| `FOUP 300.stl` 단위 | **cm (×10 해야 mm)** | STL bbox 42.5×34.2×33.2 ↔ STEP 425×342×332 |
| `Wafer Cassette.stl` 단위 | **mm** (다름!) | bbox 181×176×153 |
| STEP 구조 | **단일 solid** (PRODUCT 1개, `NEXT_ASSEMBLY_USAGE_OCCURRENCE` 0개, `ADVANCED_FACE` 737개) | 파트 트리 없음 |
| STL 구조 | **단일 connected shell** (19,548 tri, 9,764 vert) | union-find 결과 shell 1개 |
| **up axis** | **+Z** | 웨이퍼 슬롯 = 축//Z 원통 r=150mm(=300mm 웨이퍼), z=104/114/124/134/144 → **10mm 슬롯 피치** |
| mesh bbox (mm) | x[-212.5, 212.5], y[-176, 166], z[-155, 177] | |

### 1.2 ★ top flange 분리 가능 여부 → **가능하다**

파트 단위로는 안 나뉘지만, **기하 규칙 하나로 정확히 분리된다**:

```
top_flange = { z ≥ 155mm } ∧ { sqrt(x²+y²) ≤ 95mm }      # 원점은 이미 flange 중심축 위(x=y=0)
```

확정된 flange 실측 (M1 에서 재검증, `RESULTS.md § M1`):

| flange 실측 | 값 | SEMI E47.1-1106 표준 항목 |
|---|---|---|
| 외곽 테두리(rim) | **r = 95.0mm (ø190)** — 정확히 떨어짐 | ① 외곽 테두리 ✔ |
| 중심 홀 | **r = 20.0mm (ø40)**, 축 //Z. **관통이 아니라 z=167~175 블라인드 포켓(깊이 8mm)** | ② 중심 홀 ✔ |
| 상단 평면 / 두께 | **주 상면 z = 175mm**(면적 18,118mm²), 하면 z = 155mm → 전체 높이 22mm | ③ 높이 ✔ |
| 중심축 | x = y = 0 (obj 원점과 동일 축) | |

즉 **사용자 정정(“FOUP 의 top flange 는 테두리·중심 홀이 실물과 일치, 그 외는 제조사별 상이”)과 CAD 가 일치**한다.
→ 정밀 pose 앵커는 이 세 기하(ø190 rim / ø40 hole / z=175 주 상면) 위에만 둔다. body 는 coarse 초기 pose 전용.

> **M1 정정 (2026-08-07)** — 위 "평면+원통 컷" 규칙은 **불필요했다**:
> - **`z ≥ 155` 평면 컷 하나만으로 완전히 분리된다.** 자른 뒤 연결성분이 정확히 2개로 갈리고
>   (flange r∈[20.00, 95.00] / shell r∈[138.81, 252.30] — **반경 간극 43.8mm**), **양쪽 다 watertight** 로 나온다.
>   삼각형 선택 방식은 경계에 걸치는 249개를 잘못 처리하므로 쓰지 않는다.
> - flange 상세 프로파일: z=155 하면(컷면) → z=167 rim 상단(r 20~95) → **z=175 주 상면(r 20~92, 면적 18,118mm²)**
>   → z=177 중앙 돌기(r 25~33, 정점 24개뿐). **bbox 최댓값 177 은 주 상면이 아니다** — §4.1 원점 정정 참조.
> - 중심 홀은 **관통이 아니라** z=167~175 의 블라인드 포켓(깊이 8mm)이다.

### 1.3 런타임 환경

| 항목 | 상태 | 함의 |
|---|---|---|
| GPU | RTX 5090 32GB, **sm_120**, driver 580 / CUDA 13.0 | **torch cu128 (≥2.7) 강제**. 구버전 cu118 휠 불가 |
| 시스템 python | 3.12.3, **pip / ensurepip 없음** | venv 부트스트랩에 `/isaac-sim/kit/python/bin/python3`(3.12.13, pip 25.3) 또는 `uv` 사용 |
| Isaac 번들 python | 3.12.13, torch **없음** | Isaac 캡처 전용으로만 사용 (`/isaac-sim/python.sh`) |
| 네트워크 | github / huggingface 200 OK | clone·weight 다운로드 가능 |
| 디스크 | `/isaac-sim/volume` 2.5T 여유 | |
| 실카메라 | **없음** (`/dev/video*` 없음, RealSense SDK 없음) | sim 전용으로 시작 (사용자 결정) |

업스트림 확인: `NVlabs/FoundationStereo` 200, `NVlabs/FoundationPose` 200, `JiehongLin/SAM-6D` 200,
`facebookresearch/sam3` 200, `NVlabs/nvdiffrast` 200. HF `nvidia/foundationstereo` 는 **401(gated)** →
라이선스 수락 + HF 토큰 필요.

---

## 2. 설계 원칙

1. **의존성은 ws 안에 격리.** 다른 ws·시스템 python·Isaac 번들 python 을 오염시키지 않는다.
   venv·pip cache·torch/HF cache 를 전부 `spatial_vision_ws/src/` 하위로 고정한다.
2. **모델마다 venv 를 분리한다.** FoundationStereo / FoundationPose / SAM6D / SAM3 는 torch·CUDA ext·python
   버전 요구가 서로 다르다. 한 venv 로 억지로 묶으면 한 모델 업그레이드가 나머지를 깨뜨린다.
3. **⇒ 스테이지 간 통신은 in-process 가 아니라 디스크(작업 디렉토리) 경유.** venv 가 다르면 import 로 못 엮인다.
   각 스테이지는 `python -m spatial_vision.stages.<name> --in <dir> --out <dir>` CLI 진입점을 갖고,
   오케스트레이터가 각 venv 의 인터프리터를 subprocess 로 호출한다. 격리 요구와 파이프라인 구조가 정확히 맞물린다.
   (부수 이득: 스테이지 단위 재실행·중간산출물 검사·성능 프로파일링이 공짜로 된다.)
4. **데이터 계약을 먼저 고정한다.** 스테이지 교체(sim↔real, SAM3↔SAM6D)는 코드가 아니라 config 로.
5. **항상 GT 대비 정량 평가가 가능한 상태를 유지한다.** sim 은 depth·mask·pose GT 가 전부 있다 —
   실환경에서 불가능한 통제실험(§CONSUMER 2.6 의 depth bias 재현 같은)을 여기서 한다.
6. **객체 특이 로직은 이 ws 안에서만.** 단, 파일/디렉토리는 `obj_id` 로 파라미터화해 두 번째 객체 추가가 쉽도록.

---

## 3. 디렉토리 구조 (목표)

> **2026-08-07 ws 재편**: `spatial_vision_ws` → **`spatial_manipulation_ws`**, `src/` 아래가
> **`vision/`(이 파이프라인) + `manipulation/`(로봇 측, 미착수)** 으로 분리됨. 아래 경로는 그 기준.
> pose → 로봇 TCP 로 넘어가는 접점이 같은 ws 안에 생기므로, **pose frame 정의(§4.1)가 두 파트의 공용 계약**이 된다.

```
spatial_manipulation_ws/src/
├── manipulation/                   # 로봇 측 (미착수)
└── vision/
    ├── docs/
    │   ├── CONSUMER_6DPOSE.md      # 배경·요구사항 (기존)
    │   ├── PIPELINE_PLAN.md        # 이 문서 — 계획·설계
    │   ├── RESULTS.md              # ★ 단계별 실행 결과·검증 수치 (정본)
    │   └── LICENSES.md             # 구성요소 라이선스·상업화 경로
    ├── assets/
    │   ├── cad/foup_300mm/         # 원본 CAD (기존, 손대지 않음)
    │   └── obj/foup_300/           # ★ 생성물 (M1)
    │       ├── full.ply            #   전체 형상, mm, 원점 통일 (FoundationPose stage-1)
    │       ├── top_flange.ply      #   flange only, full.ply 와 동일 좌표계 (stage-2)
    │       ├── body.ply            #   full − flange (USD part mask 용, 겹치지 않는 prim)
    │       ├── mesh.usda           #   Isaac 에셋 (body + top_flange 2 prim)
    │       ├── keypoints.json      #   rim/hole 기반 앵커점
    │       └── meta.json           #   단위·원점·bbox·표준부 치수
    ├── spatial_vision/             # 순수 파이썬 패키지 (얇은 오케스트레이션 계층)
    │   ├── contracts.py            # 스테이지 경계의 **유일한 공유 코드** (numpy+opencv 만 의존)
    │   │                           #   CameraParams · depth PNG IO · write_stereo_frame
    │   │                           #   disparity_to_depth_mm · select_index · rotation_angle_deg
    │   ├── pipeline.py             # ⬜ **아직 없다** — config → 스테이지 DAG → subprocess 실행.
    │   │                           #   콜드 스타트 40초 때문에 **배포 선결과제**로 승격됐다(§34-12b)
    │   ├── stages/
    │   │   ├── capture_sim.py      # ✅ Isaac 스테레오 rig 캡처 (isaac python)
    │   │   ├── scene_random.py     # ✅ 조명·distractor·occluder randomizer (M2 확장)
    │   │   ├── capture_real.py     # ✅ ZED X (Jetson·pyzed). rectified L/R + cam.json 만 낸다
    │   │   ├── stereo_torch.py     # ✅ FoundationStereo PyTorch (research only)
    │   │   ├── stereo_onnx.py      # ✅ NGC ONNX (상업 가능)
    │   │   ├── segment_sam6d.py    # ✅ SAM6D ISM 래퍼 (M4)
    │   │   ├── segment_sam3.py     # ✅ SAM3 — 텍스트 / 같은이미지박스 / **exemplar 참조** 3경로 (M4)
    │   │   ├── pose_fp.py          # ✅ FoundationPose 2-stage (M5)
    │   │   └── refine_contour.py   # ✅ **원본 해상도 테두리 정합 + 이동량 게이트** (M5b, §23·§26)
    │   ├── cad/                    # ✅ prepare_obj / verify_obj / **verify_semi**(SEMI 규격 검사) /
    │   │                           #   build_usd / build_semi_flange / build_rim_obj / build_hybrid_obj /
    │   │                           #   perturb_mesh / render_band_masks / measure_symmetry /
    │   │                           #   build_sam3_refs(후보 생성) / select_sam3_refs(§19 선정) / mix_sam3_refs
    │   ├── eval/                   # ✅ verify_stereo(M2) / eval_depth(M3) / eval_seg(M4) / eval_pose(M5) /
    │   │                           #   fuse_pose(G 계열 초기값) / **lr_consistency**(좌우 투영, GT-free) /
    │   │                           #   **group_stats**(프레임×변형 표·그래프·**신호등 traffic.png**) /
    │   │                           #   **scale_check**(실루엣 기반 거리 — `baseline` 비의존, 교훈 #89) /
    │   │                           #   **hybrid_pose**(R=coarse·t=refined 초기값 §27-7 — GT 불필요) /
    │   │                           #   perturb_depth / perturb_image / **perturb_mask**(부품 결손 주입 §37-6) /
    │   │                           #   depth_budget / verify_randomization
    │   └── viz/                    # ✅ overlay_pose(GT 없이도 동작, `--combine` 겹치기 + mm 눈금자) /
    │                               #   **seg_compare**(분할 + 그 pose, 크롭 없음) / diag_sheet(6패널) /
    │                               #   ref_sheet(SAM3 참조) / dim_sheet(치수 도면) / render_mesh /
    │                               #   **result_charts** — 판단용 3종, 러너가 자동 실행 (§35-2p):
    │                               #     `stats/distance.png` 거리 4다리 (baseline↔fx 를 가른다)
    │                               #     `stats/ranking.png`  팔 서열 (|Δdx| 정렬 + 비교불가 팔 격리)
    │                               #     `stats/heatmap.png`  프레임 × 팔 (행 효과 vs 열 효과)
    ├── tools/                      # 실환경 진입점·오케스트레이션 (패키지 밖 단독 스크립트)
    │   ├── make_frame_from_zed.py  # ✅ 실카메라 L/R + 프로파일 → 프레임 디렉토리 (입력은 3파일뿐)
    │   ├── run_group_a.py          # ✅ **A그룹 원샷 러너** — 4 venv 를 subprocess 로 오가며 A1~A4
    │   │                           #   (+`--ism` I그룹 · +`--sam3-text` T그룹, 둘 다 `--primary full`)
    │   │                           #   + GT-free 리포트·진단시트·오버레이(겹치기 포함)·분할+pose 대조
    │   │                           #   · 신호등(stats/traffic.png)·통계·실루엣 거리·run_meta 까지 낸다
    │   │                           #   `--limit-frames N` 으로 앞 N 장만 (새 설정 시험용)
    │   │                           #   ★ `--mode` 로 후보 폭을 정한다: default **9** /
    │   │                             **combo,prompts 15 ← 현행 권장** / wide **23** /
    │   │                             all **35**(참조 스윕 + combo, --ism·--sam3-text 자동). `--list-modes`
    │   │                           #   ★ `--mode prompts` = `full` 프롬프트 여러 개를 **한 런에서**
    │   │                             (기본 현행 4개). 프롬프트마다 `RP1@<tag>`·`RH1@<tag>` (§41-10)
    │   │                           #   ★ `--text-prompt-flange` 로 **TF 경로**(텍스트 flange →
    │   │                             `--primary flange`, §37-9) 추가 → all 이면 **37팔**
    │   │                           #   ★ `--no-exemplar` 로 sim 참조 경로를 빼고 정합 축을 옮긴다(§38-8)
    │   ├── sam3_prompt_sweep.py   # ✅ **SAM3 텍스트 프롬프트 스윕** — 모델 1회 로드로 이미지 ×
    │   │                           #   프롬프트 전수. GT-free 지표 + **육안 시트**(perfect/matrix)
    │   │                           #   `--prompts-json` 목록 교체 · `--rebuild-sheets` 추론 없이
    │   │                           #   재생성 · `--instances` 후보를 하나씩 (§37-2)
    │   ├── inspect_frames.py      # ✅ **프레임마다 한 장** — 마스크 + 최종 pose 를 색 달리해
    │   │                           #   겹친다. `arms`(pose 팔만) / `prompts`(분할까지) / `all`
    │   │                           #   🔴 팔마다 pose 파일 이름이 달라(`hyb_*/pose_coarse` ↔
    │   │                           #   `fp_chull/pose_refined`) 손으로 조립하면 조용히 «없음»
    │   ├── compare_runs.py         # ✅ 런 N개 비교 (설정 diff 먼저 → 지표) + 누적 실험 노트
    │   ├── audit_run.py            # ✅ **배선 감사** — «어느 팔의 숫자가 다른 팔 것은 아닌가» 7항목
    │   │                           #   러너가 자동으로 돌려 `report.md` 「배선 감사」 절에 넣는다
    │   ├── which_arm.py            # ✅ «어느 팔이 무엇을 집었나» 를 **표로** (마스크 면적·중심·pose t)
    │   │                           #   `viz.seg_compare` 의 수치판. 프레임 하나를 파고들 때 쓴다
    │   ├── get_zed_info.py         # ✅ ZED X 실측 intrinsic 덤프
    │   └── zedx_check_pp_convention.py  # ⬜ cx/cy 반픽셀 규약 확인 (미실행)
    ├── third_party/                # git clone (submodule 아님 — 커밋 SHA 를 lock 파일에 기록)
    │   ├── FoundationStereo/  FoundationPose/  SAM-6D/  sam3/
    ├── weights/                    # 체크포인트 (gitignore)
    ├── envs/                       # ★ venv 격리 (gitignore)
    │   ├── env.sh                  #   캐시·CUDA_HOME 경로 고정 (모든 실행 전 source)
    │   ├── bootstrap.sh            #   venv 생성 + 리포 clone + CUDA 조립
    │   ├── link_cuda_libs.sh       #   CUDA math 헤더/lib 연결 (venv 재생성 시 재실행)
    │   ├── place_weights.sh        #   가중치를 각 리포 기대 경로로 심링크
    │   ├── verify.sh / check_weights.sh
    │   ├── cuda/                   #   ws 로컬 CUDA 12.8 (nvcc)
    │   └── stereo/ stereo_onnx/ pose/ seg_sam3/ seg_sam6d/ cad/
    ├── configs/                    # 파이프라인 config (yaml)
    └── runs/                       # 실행별 산출물 (gitignore)
```

**캐시 격리**: 모든 스테이지 실행 시 `XDG_CACHE_HOME`, `PIP_CACHE_DIR`, `TORCH_HOME`, `HF_HOME`,
`TORCH_EXTENSIONS_DIR` 를 `src/vision/.cache/` 하위로 지정 → `~/.cache` 오염 없음(다른 ws 와 완전 분리).

⚠️ `src/<pkg>/` 배치는 colcon 워크스페이스 관례와 같은 모양이다. `manipulation` 이 ROS2 패키지로 갈 경우
**vision 을 ROS2 패키지로 만들지, 순수 파이썬으로 두고 ROS 노드는 얇은 래퍼로만 붙일지**는 미결
(`ur_ws` 는 colcon, 이 파이프라인은 모델별 venv 라 툴체인이 상충 — 후자를 권장). → §7

---

## 4. 데이터 계약 (스테이지 경계)

작업 디렉토리 하나 = 한 프레임(또는 시퀀스). 스테이지는 읽고, 자기 산출물만 더한다.

| 스테이지 | 입력 | 출력 |
|---|---|---|
| capture | — | `left.png`, `right.png`, `cam.json{K_l,K_r,baseline_mm,R,t}`, (sim) `depth_gt.png`, `pose_gt.json`, `mask_gt.png` |
| stereo | `left.png`,`right.png`,`cam.json` | `disparity.npy`(px), `depth.png`(16-bit mm, **0=invalid**), `valid.png`(uint8 mask), `meta_stereo.json` |
| segment | left + (CAD templates) | `mask_full.png`, `mask_flange.png`, `det.json{score,bbox}` |
| pose | left + depth + mask + CAD | `pose.json{R,t,stage,score}`, `overlay.png` |
| eval | 위 전부 + GT | `metrics.json`, 리포트 |

규약: **길이 단위 mm**, depth 는 16-bit PNG(mm), pose 는 `cam_T_obj` (BOP 관례, R 3×3 row-major + t mm).
CAD 원점 정의는 `assets/obj/<id>/meta.json` 에 명시하고 모든 소비자가 그것만 믿는다.

`confidence` 는 **백엔드 의존**이다 — ONNX 백엔드는 confidence 를 내지 않으므로 만들어내지 않고
`meta_stereo.json` 에 `"confidence": null` 로 명시한다. 대신 모든 백엔드가 `valid.png`(유효 픽셀 마스크)를
낸다. 각 스테이지는 `meta_<stage>.json` 에 **어떤 백엔드·가중치·라이선스로 만들어졌는지** 기록한다
(상업 경로에서 산출물의 출처 추적이 필요하다).

### 4.1 ★ pose frame(원점) 규약 — Isaac USD origin 과 분리한다

**결정: pose frame 원점 = top flange **주 상면** 중심. Isaac USD 의 prim origin 은 원본 CAD 원점
그대로 두고 건드리지 않는다.**

> ⚠️ **수치는 CAD 마다 다르다 — 여기 적힌 `(0,0,175)` 는 구 CAD 값이다(§1.1 경고 참조).**
> 현행 `foup_300_semi` 는 **`(0, 0, 344)`** 이고 flange 도 ø190/22mm 가 아니라
> **142×142 사각 외곽 · rim ø183.36 · 홀 ø41.0 · 높이 29mm** 다.
> **소비자는 이 문서의 숫자가 아니라 `assets/obj/<id>/meta.json` 의 `origin` 만 믿는다.**
> 아래 본문의 175·177 은 *규약이 왜 이렇게 정해졌는지* 의 기록으로만 읽는다.

> ⚠️ **정정 (M1, 2026-08-07)**: 초기에 `(0,0,177)` 로 적었으나 이는 mesh bbox 최댓값이었다. 실제 프로파일을
> 보면 **z=177 은 중앙의 작은 돌기(r 25~33mm, 정점 24개)**일 뿐이고, 관측되는 주 상면은 **z=175**
> (r 20~92, 면적 18,118mm²)다. depth-median Z 초기화의 기준은 *관측 표면*이므로 175 가 맞다.
> 2mm 차이지만 §CONSUMER 2.6 의 Z 오차 논의(15mm 급)와 성격이 같아 방치하면 원인 오진을 부른다.
> → `prepare_obj.py` 는 bbox 최댓값이 아니라 **위를 향하는 수평면 중 면적 최대인 평면**을 자동 검출한다.

근거 — 둘은 별개다:
- **pose 가 표현되는 좌표계를 정하는 것은 FoundationPose 에 넘기는 mesh 파일의 좌표계**다. 출력은
  `cam_T_mesh`, 즉 mesh 파일 자기 원점 기준. → `full.ply` / `top_flange.ply` 를 그 프레임으로 export 하면 끝.
- **Isaac 의 prim origin 은 씬 구성·GT 기록용**일 뿐이고, GT 는 한 줄로 옮길 수 있다:
  ```
  d  = (0, 0, 175) mm        # 구 원점에서 본 새 원점의 위치 (object-local)
  t' = t + R·d ,  R' = R     # 회전 불변, 평행이동만  (= sdg_ws objects[].origin 과 동일 연산)
  ```

USD 자체를 옮기지 않는 이유:
- pose randomizer 의 **회전은 prim origin 중심**으로 일어난다. origin 이 flange 상면으로 올라가면 같은
  회전에도 몸체가 크게 휘둘려 바닥 관통·씬 이탈이 생기고, "바닥에 놓기"·"카메라로부터 1.0~2.5m" 같은
  배치 코드가 전부 177mm 어긋난다. **씬 코드 연쇄 수정 vs 한 줄 변환** — 후자가 압도적으로 싸다.
- 물리는 무관: CoM 은 collision geometry 에서 자동 계산되며 pivot 과 독립(단 CoM 을 **수동 지정**하면 body
  frame 기준이므로 함께 고쳐야 한다).

영향 범위:

| 안 바뀜 | 바뀜 |
|---|---|
| RGB/depth 렌더, mask, intrinsic, `gt_info`(bbox·visib_fract), 물리 CoM | **`cam_t_m2c` 만** (R 불변) |

부수 효과: 카메라 look-at 타깃을 origin 으로 잡으면 시선이 177mm 위로 → flange 가 화면 중앙에 와서 오히려
유리하나, 거리 분포가 그만큼 shift 하므로 1.0~2.5m 범위 정의 시 감안한다.

**우리가 원한 이득은 Isaac 과 무관하다**: FoundationPose 의 depth-median Z 초기화 이점(§CONSUMER 2.6-1)은
*mesh 파일의 원점이 관측 표면 근처*일 때 생기는 것이므로, ply 만 그렇게 만들면 USD 를 안 건드려도 얻는다.
(실제 초기화 로직은 M0/M5 에서 FoundationPose 코드로 직접 확인할 것 — 현재 근거는 CONSUMER 문서의 관측.)

⚠️ **덫**: 한 데이터셋 안에 두 규약이 섞이면 **조용히** 틀린다 — mesh 와 GT 의 origin 이 어긋나면 회전은
맞고 t 만 177mm 틀리는데, §CONSUMER 2.6 의 Z 오차(15mm 급) 논의와 성격이 비슷해 **원인을 오진하기 쉽다**.
방어책:
1. `meta.json` 에 `origin_offset_mm` 를 박고 모든 스테이지가 그것만 참조.
2. `full.ply` 와 `top_flange.ply` 는 **반드시 같은 origin**. (2-stage 는 기각됐지만, 전체 pose 에서
   **flange 마스크를 투영**해 얻는 경로가 이 조건 위에 있으므로 규약은 그대로 유효하다.)
3. eval sanity check: 같은 프레임을 full / flange 두 mesh 로 각각 추정 → **t 차이가 0 에 수렴**해야 한다.

보너스: flange 상면 중심은 로봇이 실제로 잡는 지점이라 **`manipulation` 측 TCP 타깃 기준으로도 자연스럽다**.

---

## 5. 마일스톤

### M0 — 런타임 격리 + 리포/가중치 확보  ✅ **완료 (2026-08-07)**

> 결과·검증 수치·함정은 **[RESULTS.md § M0](RESULTS.md#m0--런타임-격리--리포가중치-2026-08-07)**.

- `envs/bootstrap.sh`: `uv`(ws 내부 설치) 로 모델별 venv 생성. 모델이 python 3.10 을 요구하면 uv 가 해당 인터프리터를
  ws 안에 받아온다(시스템 python 3.12 만 있는 제약 우회).
- torch **cu128** 설치 → `torch.cuda.get_device_capability() == (12,0)` 및 간단 matmul 로 sm_120 실동작 확인.
- `third_party/` 4개 clone + **커밋 SHA lock**. 각 repo 의 실제 requirements 를 읽고 반영(추측 금지).
- 가중치: FoundationStereo(HF gated → 토큰 필요), FoundationPose, SAM6D(ISM: SAM/FastSAM + DINOv2), SAM3.
- **검증**: 각 venv 에서 모델 import + 더미 입력 forward 성공.
- **리스크**: FoundationPose 는 `nvdiffrast` + 자체 CUDA extension 을 빌드해야 하고 공식 환경이 구 torch/cu118 기준
  → **sm_120 재빌드가 필요**. 여기가 안 뚫리면 (a) 아키텍처 플래그 강제 빌드, (b) 렌더러 백엔드 교체, (c) 컨테이너
  분리 순으로 폴백. **M0 를 다른 작업보다 먼저 끝내야 뒤가 안 흔들린다.**


### M1 — CAD 준비  ✅ **완료 (2026-08-07)**

> 결과·검증 수치는 **[RESULTS.md § M1](RESULTS.md#m1--cad-준비-2026-08-07)**.

- `stl(cm) → ×10 → mm` 정규화, watertight/법선 점검.
- **flange 컷**(§1.2 규칙)으로 `top_flange.ply` 생성, `full.ply` 와 **동일 좌표계 유지**(변환 금지).
- 원점 정책 결정 및 명문화: FoundationPose 의 depth-median Z 초기화와 정합시키려면 **flange 주 상면 중심(0,0,175)**
  이 유리(§CONSUMER 2.6-1, 2.7.4). full/flange 두 메쉬 모두 같은 원점을 쓴다.
- `keypoints.json`: rim(ø190) 원주 샘플 + 중심 홀(ø40) 중심/원주 + 상면 z — **표준부에만** 앵커.
- **검증**: 두 ply 를 같은 좌표계에서 렌더 → flange 가 full 위에 정확히 겹치는지, 치수 재측정이 §1.2 표와 일치하는지.
- (선택) STEP 에서 면 단위로 정확히 잘라내려면 CAD 커널(pythonocc/FreeCAD)이 필요 — mesh 컷으로 충분한지
  M1 에서 판정하고, 부족하면 그때 도입.


→ **CAD 커널은 불필요**로 판정됐다. trimesh 의 평면 컷 + 연결성분만으로 watertight 한 flange 가 나온다.

### M2 — Sim 스테레오 캡처 (standalone)  ✅ **완료 (2026-08-07)**

> 결과·검증 수치·설계 메모는 **[RESULTS.md § M2](RESULTS.md#m2--isaac-스테레오-rig-캡처-2026-08-07)**.

- `/isaac-sim/python.sh` 로 도는 독립 캡처 스크립트. sdg_ws 에서 **복사**해 올 것:
  intrinsics 직접지정(`sdg/sensors/ideal.py`), camera randomizer, BOP writer, part-level semantic.
- **stereo rig**: 부모 Xform 아래 left/right, `right = left + [baseline, 0, 0]`(rig local X),
  좌우 동일 intrinsic, **randomize 는 rig 단위**(개별 카메라를 움직이면 baseline 이 깨져 stereo 가 무효).
  baseline 은 ZED X(120mm)/X Mini(63mm)/D435(50mm) 를 config 로.
- 뷰 제약: top flange 가 보이는 orientation, 거리 1.0~2.5m (§CONSUMER 2.7.2 프로토콜).
- 출력: left/right RGB + ideal depth GT + disparity GT + full/flange mask + pose GT + intrinsic.
- **검증**: `disparity = fx·baseline/depth` 가 GT depth 와 일치(rectification·baseline 부호 검증).


✅ **M2 확장 완료 (2026-08-07)** — `scene_random.py` 로 **조명·distractor(동일 FOUP 포함)·occluder**
와 가림률 실측(`visib_fract`)을 붙였다. 이것 없이는 §M4 의 "유사 인스턴스 오선택률" 판정 기준을
**측정할 수 없었고**, 실제로 붙이자 M4·M5 결론 다수가 뒤집혔다 — [RESULTS.md § M2 확장](RESULTS.md).

⚠️ **여전히 미구현**: **배경(HDRI) 교체·MDL 기반 PBR 재질 randomization**·물리 낙하 배치.
둘 다 sdg_ws 에 있으니 이식하면 된다. **이 두 축이 sim→real 갭의 핵심**이라 M6 이전 최우선 과제다.

### M3 — Depth: FoundationStereo **(백엔드 2종)**  ✅ **완료 (2026-08-07)**

> 결과(백엔드 비교표·해상도 vs 모델크기 분해·ONNX 실측 사양)는 **[RESULTS.md § M3](RESULTS.md#m3--depth-foundationstereo-백엔드-2종-2026-08-07)**.

- 좌/우 → disparity → metric depth. **sim GT depth 대비 오차 맵**(실환경에선 불가능한 검증).
- 실환경 수치(§CONSUMER 2.7.1: z-MAE 17.6mm vs SDK 24.1mm)와 대조할 sim 기준선 확보.
- 관심 영역별 분해: flange 상면(정밀 경로가 실제로 쓰는 영역) vs 전체.

**★ 백엔드 2종을 같은 계약 뒤에 둔다** (2026-08-07 결정 — 현재는 연구용, 추후 상업화 가능성):

| 백엔드 | 소스 | 라이선스 | 용도 |
|---|---|---|---|
| `stereo_fs_torch` | GitHub `NVlabs/FoundationStereo` + Drive/HF 가중치 (`23-51-11`, ViT-large) | **research only** | **정확도 기준선**. 연구·논문·평가 |
| `stereo_fs_onnx` | **NGC `nvidia/tao/foundationstereo`** deployable ONNX (small) | **NVIDIA Open Model License — 상업 가능** | 상업화 경로. onnxruntime-gpu / TensorRT |

⚠️ **라이선스 청정 경로의 조건**: NGC 가중치가 상업 가능해도 **GitHub repo 코드는 research-only** 다.
따라서 ONNX 어댑터의 전처리(정규화·패딩·rectification)와 후처리(`depth = fx·baseline/disparity`)는
**repo 코드를 쓰지 않고 직접 구현**해야 상업 경로가 성립한다. 이게 어댑터를 지금 넣는 진짜 이유다 —
나중에 붙이면 repo 코드가 이미 파이프라인에 스며들어 분리 비용이 커진다.

- NGC 가중치는 **인증 불필요**(`canGuestDownload: true`) → **gated 가중치를 기다리지 않고 M3 를 먼저 착수 가능**.
- 해상도 제약: fixed `320x736` / `576x960`, dynamic 판은 **ONNX Runtime 전용**(모델카드: dynamic 은 TRT FP16 변환 불가).
- ⚠️ NGC 판은 **TAO 재학습된 별개 변형**이다 — GitHub 체크포인트와 호환되지 않는다(실측: 파라미터 1192 vs 1147,
  이름 겹침 833, `cost_agg.agg_1.0.conv.weight` shape 56×112 ↔ 112×56, 모듈 명명 체계 상이). 서로 교체 불가.
- **평가**: 두 백엔드를 sim GT depth 대비 동일 지표로 비교 → "상업화 시 정확도 손실"을 미리 수치로 확보한다
  (NGC 는 small 변형만 있어 ViT-large 대비 손실이 예상됨).


### M4 — Segmentation  ✅ **완료 (2026-08-07)**

> 결과·프롬프트 표·통제 실험은 **[RESULTS.md § M4](RESULTS.md#m4--segmentation-sam-6d-ism-vs-sam-3-2026-08-07)**.

- SAM6D-ISM: CAD 템플릿 렌더 필요(빌드 스텝) → zero-shot 인스턴스 seg.
- SAM3: exemplar/concept prompt. 문서 §2.7.4 의 관찰(“SAM3 는 top-flange-only 분리가 어려움”)을 sim GT mask 로
  **정량 재확인**한다 — 두 모델 모두 full-obj / flange-only 두 타깃에 대해 IoU 측정.
- 판정 기준: flange-only mask IoU 와, 유사 인스턴스(distractor FOUP) 존재 시 오선택률.

### M5 — Pose: FoundationPose 2-stage  ✅ **완료 (2026-08-07)**

> 결과·통제 실험·계약 확인은 **[RESULTS.md § M5](RESULTS.md#m5--pose-foundationpose-2-stage-2026-08-07)**.
> ⚠️ **결론이 두 번 바뀌었다. 현재 유효한 것은 아래 (2) 다.**
>
> **(1) 2026-08-08 오전 — 기각**: 세 방식 모두 회전이 악화됐다 — 같은 이미지 refine(0.349°→1.282°),
> 근접 flange 단독(18~24°), 근접 + 초기값 전달(0.604°→3.432°). 하이브리드도 KPI 75%.
>
> **(2) 2026-08-08 오후 — 뒤집힘. 근접 flange 단독이 최선이다.**
> 조명을 실내 HDRI 로 좁히고 `top_flange` 를 **검정 고정색**으로 칠하자 근접 flange 마스크가
> IoU 0.905 → **0.983** 이 됐고, 그 순간 **근접 flange 단독 pose 가 R 0.536° / t 0.70mm / 40/40** 으로
> 전 구성 중 최고가 됐다(원거리 단일은 1.85mm). (1) 의 실패 원인은 **원리가 아니라 마스크 품질**이었다.
> - **초기값 전달은 불필요**하다(0.70 → 0.98mm 로 오히려 나빠진다) → hand-eye 정확도에 의존하지 않는다.
> - **근접에서 full CAD 를 쓰면 안 된다** — FOV 이탈로 마스크 IoU 0.434, KPI 50%.
> - 원거리에서만 찍어야 하면 **하이브리드(R=coarse, t=refine)** 가 t 1.18mm 로 최선.
> → **[RESULTS.md § 근접 pose 재실험](RESULTS.md)**.
>
> 설계상 여전히 2단계다 — 어디로 접근할지 알려면 원거리 coarse pose 가 먼저 필요하다.
> 다만 2단계는 *refine* 이 아니라 **근접에서의 재추정**이다.
- 1차: 전체 CAD + full mask + depth → coarse pose (대칭에 가까운 flange 단독의 90°/180° 오추정 방지 — §2.7.4).
- 2차: coarse pose 로 flange 영역 crop → `top_flange.ply` + flange mask 로 refine
  (이때 FoundationPose 의 initial-pose 생성은 skip).
- **평가**: R/t error, ADD/ADD-S, contour overlay. 목표 기준선 = §2.7.3 sim 수치(rot 평균 0.91°/trans 0.95mm).
- 이후 확장(별도): SCFlow2 refinement, keypoint refine(rim 8-corner + PnP).

### M6 — 실환경 **🟡 진행 중 (2026-08-12)**
- ✅ **카메라 확정: ZED X 2.2mm 단독** (Jetson NX + ZED Link). 비교 근거 → `docs/CAMERAS.md`.
- ✅ **`capture_real.py` 구현** — `sl.VIEW.LEFT/RIGHT`(rectified) → `left.png`·`right.png`·`cam.json`.
  계약이 같아 **이하 스테이지 무변경**이라는 설계 의도가 실제로 확인됐다(모사 pyzed 로 종단 검증).
  의존성은 `pyzed`·`numpy`·`cv2` 뿐 — Jetson 에는 우리 venv 가 없다.
- ✅ **캘리브레이션 반영** — ChArUco 가 아니라 **ZED SDK 의 rectified `calibration_parameters`** 를 그대로
  쓴다(`assets/cam/zedx_s48560070_hd1200.json`). sim 이 7자리로 재현됨을 확인(`RESULTS.md §34-0`).
  rectified 는 `disto` 가 0 이라 **왜곡 도메인 갭이 구조적으로 닫힌다** — raw 는 절대 쓰지 않는다.
- ✅ **전 체인 재측정 완료**(n=120) → 배포 구성이 단일 시점으로 재편됐다(`RESULTS.md §34-11`).
- ⬜ **남은 것은 실물 촬영뿐**: ① FOUP 반투명 본체에서 수동 스테레오가 뚫리는가(ZED X 는 IR 프로젝터가
  없다 — **유일하게 카메라 선택을 뒤집을 수 있는 축**) ② cx/cy 반픽셀 규약(`tools/zedx_check_pp_convention.py`).
  ✅ **폴라라이저 확인됨**(후면 "P" 각인 · `RESULTS.md §36-2`) — 운용만 남았다(노출 대신 조명).
  ⏸ 0.25m 접근 동선은 **로봇이 생긴 뒤**로 보류(아래).
- ✅ **실물 형상 실측 완료**(2026-08-12, `RESULTS.md §36`) — §29 가 *"후보 선택보다 상위"* 라 했던
  두 형상 축을 닫았다: **외곽 융기 ○(최악 축이 맞았다)** · **홀 개구 ø49.0(CAD 와 0.08mm)**.
  🔴 단 **홀 주변 융기는 개체마다 다르다**(대부분 있고 가끔 없다) → **CAD 로 맞출 수 있는 축이 아니고**,
  그래서 **`--outer-only`(P9)가 «가장 정확해서» 가 아니라 «유일하게 개체 불변이라서» 배포본**이다.
- ✅ **근접 0.28m 40장 촬영 완료**(2026-08-12). 실행 도구도 준비됨(`tools/run_group_a.py`, `RESULTS.md §35`).
- ✅ **프롬프트 축이 닫혔다** — `full` 4개(§39-30e) · **`flange` 2개**(§41, 실물 3거리에서 20 → 2).
  🔴 재발굴 방아쇠는 **① 검출 0 프레임 ② 개체·조명 변경 ③ 다중 인스턴스 ④ 배포 거리 변경**뿐이다(§41-9a).
  🔴🔴 **flange 경로(TF) 자체가 «선택지» 다**(§41-9b) — `--primary full` 이 이미 KPI 안쪽이고
  (하이브리드 ADD 1.395mm ↔ KPI ≤5mm — ⚠️ ADD 는 `full.ply` 기준이라 flange 좌표계 KPI 보다 **보수적**이다) 실물에서 통과한 유일한 체인(§38)은 flange 마스크를 안 쓴다.
- 🔴🔴 **환경 제약(2026-08-12 사용자 확정): 아직 로봇이 없다** — 카메라 + FOUP 뿐이고 **손으로 움직인다.**
  → **hand-eye 가 «측정 대기» 가 아니라 «존재하지 않는다»** → **1 사이클 촬영 2회 이상은 전부 후순위**이고
  **G0·G9·G10·farfuse 는 원천적으로 불가**다. 지금 돌릴 목록은 **`PIPELINE_CATALOG §9.1★c`**
  (근접 1장 A그룹 / 원거리 1장 B그룹, 대조군은 추가 촬영 0).
  ★ 대신 손 촬영에서만 싼 것이 둘 있다 — **반복도**(고정 후 연속 촬영 = 랜덤 오차 바닥)와
  **`§7.5c` 상대 GT**(물체를 자로 잰 만큼 이동·회전 → **계통 편향 검출**, 로봇 불필요).
- 🔴 **배포 선결과제(정확도와 별개)**: 「스테이지 = 프로세스」 구조로는 요청마다 **콜드 스타트 40초**다
  (ONNX 세션 31.5s + FP 7.1s). **venv 별 상주 서버 + IPC** 가 필요하고 이것이 §3 의 `pipeline.py` 다.
  → `RESULTS.md §34-12b`. 새 머신 세팅은 **`docs/SETUP.md`**.

---

## 6. 리스크 요약

| # | 리스크 | 상태 / 대응 |
|---|---|---|
| R1 | sm_120 에서 FoundationPose CUDA ext / nvdiffrast 빌드 | ✅ **해소(M0)** — model-based 경로엔 커스텀 CUDA 커널 불필요. pytorch3d·nvdiffrast·mycpp 셋만 빌드하면 되고 전부 sm_120 동작 |
| R2 | 모델별 python·torch 버전 충돌 | ✅ **구조적 회피** — venv 분리 + 디스크 경유 통신(§2-3). 실제로 numpy 요구가 충돌함을 확인 |
| R3 | FoundationStereo 가중치 gated(401) | ✅ **해소** — 사용자가 공식 경로로 확보(13/13). 상업 경로는 NGC(무인증) |
| **R4** | top flange 근사 대칭 → 90°/180° 오추정 | ⚠️ **재개방(2026-08-09). 깨끗한 depth 에서만 미발생이다.** 상관 depth 오차 18mm 를 주입하면 근접 flange 단독이 **12/40 뒤집힘**으로 붕괴한다(원거리 `full` 은 0). 원인은 규명됐다 — 방향 정보가 테두리 최대 8.3mm 비대칭에 있는데 **표면의 3.5%, 전부 경계**라 depth 가 뭉개지면 먼저 사라진다. **대응은 회전을 근접에서 받지 않는 것**(G9/G10 결합). → RESULTS §depth 오차 주입 §3, §flange 의 회전 구속 |
| ~~R9~~ | ~~flange 마스크를 segmentation 으로 못 얻는다~~ | ✅ **철회(2026-08-07)** — 구 CAD 의 형상 오류였다. 신 SEMI CAD 에서 ISM 0.921 / SAM3 0.954, 오선택·미검출 0 (RESULTS § 신 CAD 전환) |
| **R5** | **body 는 제조사별 상이 + 투명 재질 존재** | ⚠️ **측정 완료(2026-08-10) — 원래 대응 원칙이 기각됐다.** 원칙은 *"body 는 coarse 전용, 정밀 앵커는 표준부만"* 이었다. 실제로 재보니(`RESULTS.md §20`, 두 번째 실물 CAD 포함) **반대**다: 원거리 `full` **+ refine** 은 body 불일치를 흡수하고(δ=10 에서 40/40, 실측 CAD 로 t 1.23mm), **근접 flange 단독은 δ=2mm 부터 90°/180° 로 뒤집힌다**(δ=5 에서 26.7/40). 이유 — **표준부로 좁히면 비표준 면적과 함께 방향 신호도 줄기 때문**이다(flange 의 방향 정보는 표면의 3.5%·전부 경계). **refine 은 평행이동 편향은 고치지만 실패한 회전은 못 고친다.** 🔴 남은 문제는 **처방 충돌** — refine 을 CAD 불일치에는 켜야 하고 상관 depth 오차에는 꺼야 한다(R4). 어느 쪽이 지배적인지는 real 측정 대기. 후속 후보였던 **rim 밴드 정합**은 측정 후 **기각**(`RESULTS.md §21`) — 원거리 `full`+refine 은 **flange 중간부 불일치에도** δ=10 에서 40/40 이다 |
| R6 | sim→real gap (depth bias, intrinsic 불일치) | ⚠️ **대폭 축소(2026-08-12)** — 실측 intrinsic 을 sim 이 **7자리로 재현**하고, rectified 를 소비하므로 **왜곡 축이 구조적으로 닫힌다**. 배경·재질(R15)·depth 노이즈·CAD 불일치·모션블러·AE 도 측정 완료. **남은 것은 실사진(실텍스처·실조명)뿐** |
| 🔴🔴 **R16** | **sim 에서 만든 SAM3 exemplar 참조가 실물에서 쓸 수 없다** | 🔴 **확정(2026-08-26, 사용자 실물)** — 다른 PC 의 실물 데이터에서 **참조 기반 SAM3 가 전부 실패**했다(`RESULTS.md §38-1`). R14·R15 가 «참조는 배포 조건에 종속된다» 로 예고한 것의 **최종 형태**다 — sim 렌더는 실물의 배포 조건이 아니다. ★ **처방은 텍스트 프롬프트**(T·TF·COMBO 경로)이고, 낱말은 `tools/sam3_prompt_sweep.py` 로 **배포할 사진에서 고른다**(§37). A그룹은 이제 **배포 후보가 아니라 대조군**이다 |
| **R15** | **외관 도메인 갭 (배경·재질)** | ⚠️ **측정 완료(2026-08-08)** — HDRI 14 + 바닥 텍스처 50 + 몸체 PBR(`top_flange` 고정) 하에서 **ISM 경로 40/40 유지**. **SAM3 exemplar 는 IoU 0.862 → 0.382 붕괴**하고, randomize 안 된 flange 에 달라붙는다(예측 픽셀 57%가 flange). **참조를 배포 조건에서 재생성하면 0.872 / 40/40 으로 회복**. → exemplar 자산은 배포 조건에 종속된다 |
| **R7** | **ONNX(상업 경로) 고해상도 OOM** | ⚠️ **완화(2026-08-12)** — `--scale` 로 추론만 줄이고 disparity 는 원본 해상도로 복원한다. 1920×1200 은 `--scale 0.5` 로 운용 중(0.81s/frame). 🔴 그런데 **`--scale` 을 더 줄이면 중앙값은 멀쩡한데 R최대가 180° 로 터진다** → 속도용으로 쓰면 안 된다(`RESULTS.md §34-12c`). 타일 추론·TensorRT EP 는 여전히 미검증 |
| **R18** | **FoundationPose 가 고해상도에서 OOM** | ✅ **해소(2026-08-12)** — 내부가 crop 을 **원본 크기로 되돌리며** 가설 수만큼 warp 해 메모리가 원본 픽셀 수에 비례한다(1920×1200 에서 31GB 초과). §22(crop→160×160 리샘플) 근거로 **`pose_fp --input-scale 0.5`** 를 넣었고 0.5 vs 0.75 결과가 구분 불가임을 확인 |
| **R19** | **사이클 타임 10초** | ⚠️ **신규(2026-08-12, 사용자 제약)** — 추론은 여유(근접 단독 2.6s / 2단계 5.4s)지만 **콜드 스타트 40초**가 실제 위험이다. 그리고 이 제약 때문에 **다중시점 융합(~20s + 이동 5회)이 배포 후보에서 탈락**했다 |
| **R8** | **flange 영역 depth 오차 → pose Z** | ⚠️ **전이는 사실, bias 는 아니었다** — n=4 에서 −2.85mm 로 보이던 것이 **n=40 에서 +2.22mm 로 부호가 뒤집힌다**(sd 6.2, 절반이 음수). 계통 편차가 아니라 **분산**이고 해상도로도 5%만 준다 → 보정 대상이 아니라 **거리·baseline 으로 줄일 값** |
| ~~R12~~ | ~~flange 단독은 회전 구속이 약하다~~ | ✅ **철회(2026-08-08 오후)** — 원인은 형상이 아니라 **마스크 품질**이었다. 검정 flange + 실내조명으로 마스크 IoU 0.905 → **0.983** 이 되자 근접 flange 단독이 **R 0.536°** 로 전 구성 중 최고가 됐다. 판정 임계는 대략 **flange 마스크 IoU ≥0.98** 이다 |
| **R16** | **근접에서 full CAD 를 쓰면 실패한다** | ⚠️ **신규(2026-08-08)** — 0.35~0.5m 에서 FOUP 전체가 FOV 를 벗어나 full 마스크 IoU 0.434, pose KPI **50%**. 근접 단계는 반드시 `top_flange.ply` 로 간다. ⚠️ **원인은 «근접» 이 아니라 «FOV 이탈» 이다** — ZED X 2.2mm(HFOV 105.7°)은 0.45m 부터 FOUP 전체가 들어오므로 **이 리스크의 전제가 렌즈에 딸려 있다.** 다만 §22(crop→160×160)에 따라 근접에서 `full` 을 써도 **네트워크 유효 해상도는 안 좋아진다** → 현행 배포는 그대로 `top_flange` 다 |
| **R13** | **flange 전용 CAD 템플릿은 ISM 에서 변별력이 없다** | ⚠️ **확정(M5 확장)** — "판때기 + 구멍" 이라 오선택 23/40. flange 마스크는 **전체 pose 투영** 또는 **SAM3 flange 참조**로 얻는다 |
| **R14** | **exemplar 참조는 스케일에 민감하다** | ⚠️ **확정(M5 확장)** — 참조와 질의의 투영 면적이 34배 벌어지면 IoU 0.044. 참조는 **배포 작업거리에서** 렌더한다. 시점(방위·고도)은 무관 |

---

## 7. 열린 결정 사항

- ~~**원점**~~ → **확정(2026-08-07)**: pose frame = flange 주 상면 중심, Isaac USD origin 은 불변. §4.1.
  ⚠️ **값은 CAD 마다 다르다** — 현행 `foup_300_semi` 는 `(0,0,344)`. 소비자는 `meta.json` 의 `origin` 을 읽는다.
- **vision 을 ROS2 패키지로 만들 것인가**: `manipulation` 이 colcon/ROS2 로 가면 `src/` 배치가 colcon 관례와
  겹친다. 모델별 venv 와 colcon 툴체인은 상충하므로 **vision 은 순수 파이썬 + ROS 노드는 얇은 래퍼**를 권장.
  `manipulation` 착수 시 확정.
- **SAM3 vs SAM6D** → **재개방(2026-08-07)**. distractor 를 넣자 순위가 뒤집혔고, SAM3 를 텍스트가 아니라
  **exemplar(사전 참조 이미지 + 박스)** 로 쓰는 경로가 새로 생겼다. **둘 다 유지하며 계속 비교한다.**

  | | ISM | SAM3 exemplar |
  |---|---|---|
  | 사전 자산 | CAD 템플릿 42뷰(blenderproc) | 참조 **후보 42장 → 선별 5장** + 박스 |
  | 끝단 성공률 | **40/40** | 38/40 |
  | 속도 | 1535ms | **737ms** (선별 5장 기준 ~1300ms) |
  | 타깃 지정 | `select center` 규칙 필요 | **박스가 곧 지정**(규칙 불필요) |
  | **배경·재질 randomization 하** | **40/40 (자산 그대로)** | 37/40 → 참조 재생성 시 **40/40** |
  | `full` 마스크 IoU | ISM 우세 | 면적 선별 5장으로 좁혀진다 (RESULTS §17·§19) |
  | `flange` 마스크 IoU | 0.382 · **오선택 23/40** ❌ | **0.879~0.983** |
  | **자산의 조건 종속성** | **없음**(CAD 형상 템플릿) | **거리 + 외관 분포에 종속** — 배포 조건이 바뀌면 다시 렌더 |

  **★ 갱신(2026-08-12) — ZED X 광각 기하에서 갈렸다.** 원거리 `full` 에서 **ISM 오선택이 1/120 → 14/120
  으로 급증**했다(광각·근거리라 distractor 가 화면에 더 크게 들어오고 `select center` 가 놓친다).
  **SAM3 exemplar 는 `n-refs 3` 에서 오선택 8/120 이면서 1.6배 빠르다**(925 vs 1499ms), `n-refs 5` 는 5/120.
  → **원거리도 SAM3 exemplar 로 전환**한다. *"어느 백엔드가 낫다" 는 기하에 딸린 결론*이었다
  (`RESULTS.md §34-10`). 근접 `flange` 는 원래부터 SAM3(오선택 1/120).
  ⚠️ 그래도 **둘 다 유지한다**(사용자 지시) — ISM 은 자산이 조건에 종속되지 않는 유일한 백엔드다.

  **갱신(2026-08-10)**: 배경·재질 축은 측정됐고(R15) **갈리지 않았다** — ISM 은 자산 그대로 40/40,
  SAM3 는 참조를 재생성하면 40/40. 남은 실질적 차이는 **자산 관리 부담**뿐이다.
  그리고 `full` 마스크 품질 차이는 **원거리 pose 를 거의 안 바꾼다** — 마스크를 GT 로 치환해도
  이득이 무시할 수준이다(**RESULTS §18**). → **정확도로는 결정이 안 난다. 타깃별로 나눠 쓰는 현행 구성이 옳다**
  (`full`=ISM, 근접 `flange`=SAM3). 사용자 지시에 따라 **둘 다 유지하며 계속 비교한다.**
- ★ **자산을 규격에 맞추는 수정이 하류 성능을 바꾼다 — 설계 결정으로 다뤄야 한다** (2026-08-11, §25)

  `spec15`(홀 ø35 + 실물 융기)로 캡처부터 재실행한 결과, **분할·FoundationPose 는 무감각**한데
  **테두리 정합만** R 중앙 0.216 → 0.425, 꼬리 2.29 → 6.19 로 나빠졌다. 원인을 2×2 로 가르니
  **중심 홀 확대**였다 — 원뿔이 가팔라져(`dr/dz` 0.451 → 0.755) 어두운 깔때기 안에서
  **신호 없는 실루엣 대응이 4,000개 가까이** 생긴다.

  → **"규격을 맞추면 무조건 낫다" 가 아니다.** 규격 준수는 *제조사 편차에 대한 보험*이고,
  그 대가로 *정합 목표에 잡음을 더할 수 있다*. **자산 변경은 반드시 캡처부터 재실행해 하류를 다시 잰다.**

  ⚠️ 그리고 **어느 자산이 옳은지는 sim 이 못 정한다** — 렌더와 CAD 가 같은 메쉬라 불일치가 0 이다.
  규격 준수 자산의 값어치는 **실물이 규격을 따를 때만** 나온다. 실물 스캔 전까지 **두 자산을 함께 유지**한다.

- ★ **테두리 정합의 샘플 구성은 부품 형상에 종속이다** (2026-08-11, §25-4d)

  | 부품 형상 | 권장 |
  |---|---|
  | 융기/능선이 **없는** 평평한 테두리 | **안쪽 실루엣 제외**(`--outer-only`) — R 중앙 0.125, 홀 제외와 사실상 동일 |
  | 융기/능선이 **있는** 테두리 | **전부 사용** — 안쪽 샘플이 **정칙화**로 작동해 꼬리를 지킨다(최대 3.23 vs 7.40) |

  ~~전 구간 공통: `--outer-only` 는 중앙값 최선, 전체는 꼬리 최선(편향-분산).~~
  ~~⚠️ 이 선택으로 꼬리를 고치려 하지 말 것(§26-2).~~
  🔴 **위 표와 두 경고를 모두 철회한다 (2026-08-11, §27-4).** 근거였던 *"전체가 꼬리 최선"* 은
  **n=40 의 표본 잡음**이었다 — n=120 에서 `--outer-only` 가 **중앙값·평균·최댓값·KPI 전부** 낫다.
  새 객체에서 세 구성을 비교하라는 지침은 유효하되, **판정은 n≥120 에서** 한다.

- ★★★ **`--outer-only` 를 기본으로 켠다 — "표준부만 쓴다" 가 처음으로 실측 이득을 냈다** (2026-08-11, §27-4a)

  **결정: 테두리 정합은 최외곽 윤곽만 쓴다.** 정확도 이득(위)에 더해, **flange 내부의 제조사 편차에
  구조적으로 면역**이다 — 규격 띠 3mm 를 고정하고 안쪽만 흔들면 전체 실루엣은 R 중앙 0.246 → 0.410 으로
  단조 열화하는데 `--outer-only` 는 0.189 → 0.174 로 **무감각**하다.

  이것이 §7 의 다른 항목들과 다른 점: **`rim 밴드`(§21)는 면적을 좁혀 방향 신호까지 잃어서 기각**됐지만,
  `--outer-only` 는 **면적이 아니라 안쪽 실루엣만** 뺀다 — 방향 신호(테두리)는 그대로 남는다.
  → 판정 기준 *"불일치 예상치 하에서 방향 신호가 남는가"* 를 통과하는 **첫 구성**이다.

  ★★ **정확한 형태는 `--outer-only` 가 아니라 「테두리 + 중심 홀」이다** (§27-6c). 규격이 잡는 도형은
  **둘**이고(`x46` 외곽, `d63` 중심 홀) **역할이 갈린다** — 회전은 테두리가, 평행이동은 홀이 준다
  (홀은 완전한 원이라 yaw 정보 0). 홀까지 버리면 t 가 0.356 → 0.419mm 로 나빠진다.
  옛 배포 플래그(자산 `spec15`) = `--outer-only --keep-hole-mm 25` → n=120 에서 R 0.192° / t 0.351mm.
  🔴 **현행은 `--outer-only` 단독(홀 제외)이다** — 배포 자산 `r2` 는 **홀 주변에 융기가 있어** 홀 샘플의
  대부분이 «신호 없는 실루엣» 이 되고(대응점의 88%), 홀을 쓰면 게이트 후퇴가 88~93/120 로 무효화된다(§31).
  ZED X 기하에서도 동일하다. → **홀을 쓸지 말지는 «홀 주변 융기 유무» 로 갈리고, 그 판정은
  같은 데이터에 세 전략을 돌려 «게이트 후퇴율» 만 비교하면 GT 없이 된다**(§29·§31-5).
  → 일반 규칙: ***"표준부만 쓴다" 는 규격이 잡는 도형을 전부 쓰고 그 사이만 버리는 것이다.***
  새 객체에서는 먼저 **어느 도형이 공차 항목인지**(`verify_semi` 의 [공차] 목록) 확인하고 거기서 출발한다.

- ★★★ **규격부 안에서도 "무엇을 믿을지" 를 나눈다 — 중심 홀은 지름 말고 중심** (2026-08-11, §28)

  규격부라고 전부 똑같이 믿으면 안 된다. **실물은 제조사마다 홀 최상면 융기 유무로 개구가 달라진다**
  (사용자 확정). 그래서 홀 샘플의 잔차에서 **중앙값을 빼** 지름 성분만 버린다(`--hole-center-mm`) —
  법선이 전부 방사 방향이라 지름 오차는 **상수**이고, 중심 어긋남(`cos θ`)·tilt(`cos 2θ`)는 남는다.
  정확한 CAD 에서 대가는 R 중앙 **0.016°** 뿐인데, 홀이 ø39 로 어긋난 CAD 에서 KPI **16 → 113/120** 이다.

  → 일반 규칙: ***불확실한 것은 "빼는" 게 아니라 "그 자유도만 빼는" 것이 낫다.***
  형상 전체를 버리면(→ rim 밴드, §21) 신호까지 잃지만, **오염된 자유도 하나만** 빼면 나머지는 산다.
  ⚠️ 단 **모델이 실물보다 커야** 한다 — 작으면 샘플이 어두운 안쪽에 떨어져 대응점이 반으로 줄고
  남은 편향이 상수가 아니라 안 듣는다. **CAD 는 예상 실물 최대치 쪽으로 만든다.**

  🔴 **선결 조건이 생겼다**: 규격 띠 **자체가** 1.6mm 어긋나면 `--outer-only` 가 **오히려 나쁘다**
  (KPI 90 vs 74). SEMI `x46 71±1` 은 규격 준수품끼리 2mm 차이를 허용한다 →
  **공칭 규격값으로는 부족하고, 최외곽 윤곽이 서브밀리미터로 맞아야 한다.**
  **규격은 상한을 주지 기하를 주지 않는다** — 실물 스캔/제조사 CAD 가 이 구성의 전제다.

- ★★ **정합 단계는 "받아들일지 말지" 를 스스로 정해야 한다 — 이동량 게이트** (2026-08-11, §26)

  **결정: 테두리 정합은 항상 게이트와 함께 배포한다**(`refine_contour --gate-deg`).
  정합이 초기값에서 τ 넘게 회전하면 결과를 버리고 초기값을 낸다. 이유:

  1. **정합은 초기값에 없던 실패를 만든다.** 융합 초기값 40/40 → 정합 후 38/40 (R 최대 5.3°).
  2. **그 실패는 적합도로 판별할 수 없다** — 실패의 rms 가 성공 범위 안에 완전히 들어간다.
     목적함수가 축퇴 방향으로 평평하기 때문이다. **사전 정보(초기값)와의 불일치만이 신호다.**
  3. **판정이 GT 를 안 쓴다** → 실환경에 그대로 간다.

  → 이것은 `refine_contour` 만의 이야기가 아니라 **국소 최적화 단계 일반의 설계 규칙**이다:
  *"국소 정합기는 개선을 보장하지 않는다. 상류 추정과의 일관성 검사를 붙여 놓고, 못 넘으면 물러난다."*
  G9 의 게이트·G10 의 정족수와 같은 계열이며, 셋 다 **적합도가 아니라 불일치**를 본다.

  ⚠️ **미결**: τ 를 GT 로 골랐다(1.5°). 후보 GT-free 규칙 = *"융합 n시점의 회전 쌍거리 중앙값"* — 미검증.
  ⚠️ 게이트는 실패를 **회피**할 뿐 고치지 않는다. 근본 처방은 여전히 **시점 배치**(경사 ≥20°)다.

- ★★★ **«표준부인가» 보다 «그 부분이 신호를 주는가» 가 먼저다** (2026-08-11, §31)

  §27 은 *"규격이 잡는 도형을 전부 쓰고 그 사이만 버린다"* 로 정리했다. **그 규칙만으로는 부족하다.**
  실물에 가까운 자산(중심 홀 주변 융기 2mm)에서 **중심 홀은 규격부인데도 빼는 것이 맞다** —
  홀이 대응점의 **88%** 를 차지하면서 그 대부분이 **어두운 원뿔 안의 신호 없는 실루엣**이기 때문이다.
  홀을 쓰는 구성은 게이트 후퇴 **88~93/120** 으로 사실상 무효화된다.

  → 판정 순서를 둘로 나눈다:
  **① 그 부분이 규격부인가**(제조사 편차에 안전한가) → **② 그 부분이 실제로 신호를 주는가**(대비·개수).
  ①만 통과하고 ②에서 떨어지는 부분이 있다 — **중심 홀이 그 예**다.

  ⚠️ 그리고 ②는 **자산마다 다시 재야 한다.** 전단(분할·FP)이 무감각하다고 파이프라인 전체가
  무감각한 것이 아니다(교훈 #66). **후보 순위는 배포 자산에서 낸다.**
  ✅ 다행히 ②는 **GT 없이 판정된다** — 게이트 후퇴율 비교(`PIPELINE_CATALOG §9.1g`).

- 🔴 **`refine` 을 켤 것인가 — 두 위험이 반대 방향을 가리킨다** (2026-08-10, R4·R5)

  이것이 지금 **가장 큰 미결 설계 결정**이다. `refine` 은 *"관측이 옳다"* 고 믿고 모델을 관측에 맞추는
  국소 최적화라, **무엇이 틀렸느냐에 따라 부호가 뒤집힌다:**

  | 지배 위험 | refine | 근거 (`RESULTS.md`) |
  |---|---|---|
  | **상관 depth 오차** ≥10mm (데이터가 틀림) | **off** | 켜면 t 평균 52mm (§depth 오차 주입) |
  | **CAD-실물 불일치** (모델이 틀림) | **on** | 끄면 t 20.8mm, 켜면 1.23mm (§20) |

  **둘 다 실재하는 위험이고, 어느 쪽이 지배적인지는 sim 으로 못 정한다.** → M6 선행 측정:
  ① 평면 타깃을 0.5/1.0/1.5m 에서 찍어 depth 잔차의 **상관 길이**, ② 실물 FOUP 스캔 대 CAD **표면거리**.
  그때까지는 **원거리 `full` 을 coarse·refined 둘 다 산출해** 두 결과를 비교 가능하게 남긴다.

  ~~**비표준부(body) 의존을 어디까지 허용할 것인가**~~ → **측정으로 답이 나왔다(2026-08-10).**
  원칙은 *"body 는 coarse 전용, 정밀 앵커는 표준부만"* 이었으나 §20 이 **반대**를 보였다:
  `full`+refine 은 body 불일치를 흡수하고, 근접 flange 단독은 규격 밖 중간부가 2mm 어긋나면 뒤집힌다.
  **표준부인지가 아니라 방향 신호가 남는지가 기준**이다(`PIPELINE_CATALOG §4 규칙 1`).
  후속 후보였던 **rim 밴드 정합**(테두리만)도 측정을 마쳤다(`RESULTS.md §21`) — **기각**이다.
  **실제 규격 띠는 2~3mm**(사용자 확정)이고, 면역은 정의상 성립하지만 그 폭에서 배포 최선이
  **배포 27/40 · 천장 33/40**(GT depth + GT 마스크를 다 줘도) 이다.
  결정적으로 **원거리 `full`+refine 은 규격 띠 3mm 에서도 40/40 · t 1.09mm** 다.

  ⚠️ **이 축은 sim 으로 완결되지 않는다.** sim 은 CAD 와 렌더가 같은 메쉬라 **불일치가 원천적으로 0** 이다.
  교란·하이브리드는 **CAD 만 틀리게 만든 대리 측정**이다 — 도메인 갭 목록에서
  **"CAD-실물 형상 불일치" 를 별도 축**으로 다룬다(배경·재질·센서와 나란히).
- **sdg_ws 역통합**: stereo rig 가 안정화되면 SDG 로드맵 §5-6 으로 올릴지 — M2 이후 판단.
