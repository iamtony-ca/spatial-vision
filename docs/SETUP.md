# SETUP.md — 새 머신에 처음부터 세우기

> 전제: **베이스 Docker 컨테이너가 떠 있고**, 그 안에 **`src/` 내용이 같은 경로로** 들어 있다.
> 기준 경로는 `/isaac-sim/volume/spatial_manipulation_ws/src/vision` (= `$VISION_ROOT`).
> ⚠️ 코드는 경로 독립이다(`env.sh` 가 상대 경로로 `VISION_ROOT` 를 계산한다). 다만 **`weights/` 아래
> 심링크는 절대 경로**라 경로가 다르면 `place_weights.sh` 를 다시 돌려야 한다(아래 3단계).

---

## 0. 무엇을 옮기고 무엇을 다시 만드나

| 디렉토리 | 크기 | 옮기나 | 비고 |
|---|---|---|---|
| `spatial_vision/` `tools/` `configs/` `docs/` `envs/*.sh` | ~수 MB | ✅ **필수** | 코드 |
| `assets/cad/` | 7.9M | ✅ **필수** | 원본 STEP. **재생성 불가** |
| `assets/obj/foup_300_semi_r2/` | ~수백 MB | ✅ **권장** | CAD 에서 재생성 가능하지만 `ism_full`(blenderproc 42장)·`sam3_refs_*`(캡처 필요)는 시간이 든다 |
| `assets/cam/` | 12K | ✅ **필수** | 카메라 프로파일 |
| **`weights/models/`** | **26G** | ✅ **필수** | **라이선스 게이트 수동 다운로드**. 옮기는 게 압도적으로 빠르다 |
| `weights/ngc_foundationstereo/` | 1.2G | ✅ 필수 | NGC 계정 필요 |
| `third_party/repos.lock` | 1K | ✅ 필수 | 커밋 고정 |
| — | | | |
| `envs/` | 12G | ❌ **옮기지 말 것** | venv·CUDA·blender. `bootstrap.sh` 가 다시 만든다 (uv 가 절대경로를 굽는다) |
| `third_party/<repo>/` | 3.8G | ❌ | `bootstrap.sh repos` 가 `repos.lock` 대로 clone |
| `assets/env/` | 780M | ❌ | `fetch_env_assets.sh` 가 받는다 (HDRI·바닥 텍스처) |
| `.cache/` | 12G | ❌ | 자동 생성 |
| `runs/` | 65G | ❌ | 실험 산출물. 재현 명령은 `RESULTS.md` 에 있다 |

**최소 이관 = 코드 + `assets/{cad,obj,cam}` + `weights/{models,ngc_foundationstereo}` ≈ 28GB.**

### 베이스 이미지에 있어야 하는 것

- **Isaac Sim 컨테이너** — `/isaac-sim/python.sh` (번들 python 3.12.13). `capture_sim` 전용
- **NVIDIA 드라이버 + GPU** — RTX 5090(sm_120) 기준. `nvidia-smi` 가 되어야 한다
- **네트워크** — uv·PyPI·GitHub·NVIDIA redist·S3 접근
- `git` `curl` `unzip` `build-essential`(nvcc 가 host 컴파일러를 쓴다)
- ⚠️ **시스템에 nvcc 는 없어도 된다** — `bootstrap.sh` 가 `envs/cuda` 에 CUDA 12.8 을 직접 조립한다

---

## 1. 환경 변수 (모든 작업 전에 매번)

```bash
cd /isaac-sim/volume/spatial_manipulation_ws/src/vision
source envs/env.sh
```

`env.sh` 가 하는 일 — **모든 캐시를 `vision/.cache/` 에 가둔다**:
`XDG_CACHE_HOME` `PIP_CACHE_DIR` `UV_CACHE_DIR` `TORCH_HOME` `HF_HOME` `TORCH_EXTENSIONS_DIR`
`TRITON_CACHE_DIR` `YOLO_CONFIG_DIR` `MPLCONFIGDIR` `CUDA_CACHE_PATH`.
그리고 ws 로컬 `CUDA_HOME=envs/cuda`, `TORCH_CUDA_ARCH_LIST=12.0`(sm_120), `PATH` 에 `envs/bin`.

🔴 **`~/.cache` · 시스템 python · Isaac 번들 python 을 오염시키면 안 된다.** `source` 를 빼먹으면 그렇게 된다.

---

## 2. 런타임 구축 — `bootstrap.sh`

```bash
bash envs/bootstrap.sh          # 전부 (30~90분, 네트워크에 따라)
```

idempotent 라 중단 후 다시 돌려도 된다. 부분 실행:

```bash
bash envs/bootstrap.sh repos        # third_party clone (repos.lock 커밋으로 고정)
bash envs/bootstrap.sh cuda         # envs/cuda 에 CUDA 12.8 조립 (nvcc·cudart·cccl·profiler_api)
bash envs/bootstrap.sh stereo       # FoundationStereo venv
bash envs/bootstrap.sh pose         # FoundationPose venv (pytorch3d·nvdiffrast·mycpp 빌드 — 제일 오래 걸린다)
bash envs/bootstrap.sh seg_sam3     # SAM3 venv (numpy<2)
bash envs/bootstrap.sh seg_sam6d    # SAM-6D ISM venv + blenderproc/blender
bash envs/bootstrap.sh stereo_onnx  # onnxruntime-gpu venv (상업 경로)
bash envs/bootstrap.sh cad          # trimesh·pxr·manifold3d·shapely venv
```

만드는 것: ws 내부 `uv` → 모델별 venv 6종(전부 python 3.12) → torch **cu128** → `third_party` clone/checkout.
**venv 를 분리하는 이유는 의존성이 실제로 충돌하기 때문**이다 — `sam3` 는 `numpy<2`, `FoundationPose` 는 `numpy>=2`.

---

## 3. 가중치 연결 — `place_weights.sh`

```bash
bash envs/place_weights.sh          # 기본 소스: weights/models
bash envs/check_weights.sh          # 13종 존재·크기 확인
```

`weights/models/` 원본을 각 리포가 기대하는 경로로 **심링크**한다(복사 아님, ~25GB).

🔴 **경로가 바뀌었거나 `weights/` 를 새로 넣었으면 반드시 다시 돌린다** — `weights/sam3`·`weights/sam3.1`
심링크가 **절대 경로**라 그대로 옮기면 깨진 링크가 된다.

`check_weights.sh` 가 **13/13** 이어야 한다:

| 그룹 | 항목 |
|---|---|
| FoundationStereo | `23-51-11/model_best_bp2.pth` (3.1G) · `cfg.yaml` |
| FoundationPose | refiner `model_best.pth`(65M)+cfg · scorer `model_best.pth`(181M)+cfg |
| SAM-6D ISM | `sam_vit_h_4b8939.pth`(2.4G) · `dinov2_vitl14_pretrain.pth`(1.2G) |
| SAM 3 | `sam3.pt`(3.3G) · `config.json` · `tokenizer.json` · (옵션) `sam3.1_multiplex.pt`(3.3G) |
| **NGC (상업 경로)** | `deployable_foundation_stereo_s_dynamic_v2.0.onnx`(330M) |

⚠️ `weights/models/` 를 못 가져왔다면 **수동 다운로드**다(전부 라이선스 동의가 필요):
FoundationStereo/FoundationPose 는 각 NVlabs 리포의 배포 링크, SAM3 는 Meta 배포처,
SAM-6D ISM 은 `sam_vit_h`(Meta)·`dinov2_vitl14`(Meta), NGC ONNX 는 **NVIDIA NGC 계정**.
라이선스 조건은 `docs/LICENSES.md` 를 먼저 볼 것 — **상업 경로는 NGC ONNX 뿐**이다.

---

## 4. CUDA 라이브러리 심링크 — `link_cuda_libs.sh`

```bash
bash envs/link_cuda_libs.sh envs/pose
```

🔴 **venv 를 다시 만들 때마다 반드시 재실행한다** — 심링크가 끊어지고, 증상이 import 에러가 아니라
런타임 crash 로 나타나서 원인 찾기가 어렵다.

---

## 5. 환경 자산 내려받기 — `fetch_env_assets.sh`

```bash
bash envs/fetch_env_assets.sh       # HDRI 15 + 바닥 텍스처 50 (≈760MB) → assets/env/
bash envs/fetch_env_assets.sh hdri  # 부분
```

배경·재질 randomization 용. NVIDIA 가 Isaac Sim 용으로 공개한 S3 버킷에서 직접 받는다.
**sim 캡처(`capture_sim $APP`)에만 필요**하고, 실카메라 파이프라인에는 없어도 된다.

---

## 6. 검증 — 여기까지가 «세팅 완료» 의 정의

```bash
bash envs/verify.sh                 # 5단계 스모크. 실패 시 non-zero
```

| 단계 | 확인 내용 |
|---|---|
| 1/5 | `torch` cu128 · **`get_device_capability()==(12,0)`** · fp16 matmul · cudnn conv + backward |
| 2/5 | `nvcc --version` (ws 로컬 `CUDA_HOME`) |
| 3/5 | FoundationStereo import (`core.foundation_stereo`) |
| 4/5 | FoundationPose — **pytorch3d + nvdiffrast 실제 래스터 + `mycpp.cluster_poses` + `estimater`** |
| 5/5 | SAM3 빌더 · SAM-6D ISM |

**pytest 는 없다.** 이 프로젝트의 «테스트» 는 `verify_*` / `eval_*` 스크립트이고 전부 실패 시 non-zero 로 끝난다.

이어서 파이프라인이 실제로 도는지:

```bash
OBJ=assets/obj/foup_300_semi_r2
envs/cad/bin/python  -m spatial_vision.cad.verify_obj  --obj $OBJ     # 3D 표면거리 검사
envs/cad/bin/python  -m spatial_vision.cad.verify_semi --obj $OBJ     # SEMI E47.1 규격 검사
```

---

## 7. 첫 실행 (sim)

```bash
source envs/env.sh
OBJ=assets/obj/foup_300_semi_r2
ZED="--width 1920 --height 1200 --fx 727.5751343 --fy 727.5751343 \
     --cx 960.99988 --cy 604.824219 --baseline-mm 120.201996"   # ⚠️ cx,cy 는 +0.5 (코너 원점)

/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/smoke --frames 4 $ZED --distance-m 0.22 0.30 --elevation-deg 40 70
envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx --in runs/smoke --out runs/smoke_st \
    --scale 0.5 --model weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx
envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 --in runs/smoke --out runs/smoke_seg \
    --target flange --refs $OBJ/sam3_refs_flange_n25 --n-refs 3
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/smoke --out runs/smoke_fp \
    --input-scale 0.5 --obj $OBJ --primary flange --masks runs/smoke_seg \
    --depth stereo --depth-dir runs/smoke_st --no-stage2
envs/pose/bin/python -m spatial_vision.stages.refine_contour --in runs/smoke --pose-dir runs/smoke_fp \
    --pose-name pose_coarse.json --obj $OBJ --fix-z --outer-only --gate-deg 1.5 --out runs/smoke_pose
envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/smoke --obj $OBJ --pred runs/smoke_pose
```

## 8. 첫 실행 (실카메라)

캡처는 **Jetson** 에서, 나머지는 **5090** 에서. → `docs/CAMERAS.md §4`

```bash
# [Jetson] pyzed 가 동작하는 인터프리터로. 필요한 건 pyzed·numpy·cv2 뿐
python3 -m spatial_vision.stages.capture_real \
    --out runs/real01_near --cam assets/cam/zedx_s48560070_hd1200.json \
    --frames 10 --on-key --note "0.25m 근접"
# → runs/real01_near/frame_XXXX/{left.png, right.png, cam.json}  ← 파이프라인 입력은 이게 전부다

# [5090] 위 ⑦ 과 동일한 명령을 --in runs/real01_near 로. 단 eval_* 는 못 돌린다(GT 없음)
```

⚠️ Jetson 에는 우리 venv 가 없다. `capture_real` 은 **`pyzed`·`numpy`·`cv2` 만** 쓰도록 만들어져 있다.
🔴 **`pip install opencv-python` 금지** — numpy>=2 를 끌어와 pyzed 가
*"numpy.core.multiarray failed to import"* 로 죽는다. `apt install python3-opencv` 또는 `pip install --no-deps opencv-python-headless`.

---

## 9. 자주 밟는 함정

| 증상 | 원인 | 조치 |
|---|---|---|
| `~/.cache` 가 커진다 / 다른 ws 가 깨진다 | `source envs/env.sh` 를 빼먹었다 | 항상 먼저 source |
| import 는 되는데 런타임 crash | venv 재생성 후 CUDA 심링크 끊김 | `bash envs/link_cuda_libs.sh envs/pose` |
| `weights/sam3` 가 깨진 링크 | 심링크가 **절대 경로**다 | `bash envs/place_weights.sh` 재실행 |
| `uv venv` 가 에러로 멈춤 | uv 0.9+ 는 기존 venv 에서 멈춘다 | `bootstrap.sh` 가 `--allow-existing` 을 준다. 완전 재생성은 해당 디렉토리를 지우고 실행 |
| `capture_sim` 이 실패했는데 종료코드 0 | Isaac 의 `fastShutdown` 이 `SystemExit` 을 삼킨다 | 이미 `os._exit(code)` 로 강제해 뒀다. 산출물 개수를 함께 확인할 것 |
| FoundationPose OOM (1920×1200) | crop 을 원본 크기로 되돌리며 warp 한다 | **`pose_fp --input-scale 0.5` 필수** |
| ONNX stereo 가 1280×720 이상에서 OOM | Softmax 단일 버퍼 10.2GB | `--scale` 로 줄인다(1920×1200 은 0.5) |
| 스테이지 1회 실행에 40초 | **콜드 스타트** — ONNX 세션 31.5s + FP 7.1s | 배포에서는 **상주 서버 + IPC** 가 필요하다(`RESULTS.md §34-12b`) |
| `stat -c%s` 가 이상한 값 | 심링크 자체 크기 | `stat -Lc%s` |

---

## 10. 자산을 처음부터 다시 만들어야 할 때

`assets/obj/<id>/` 를 못 옮겼거나 CAD 를 바꿨다면:

```bash
OBJ=assets/obj/foup_300_semi_r2
envs/cad/bin/python -m spatial_vision.cad.prepare_obj  --config $OBJ/source.json   # STEP → ply + keypoints
envs/cad/bin/python -m spatial_vision.cad.verify_semi  --obj $OBJ                  # ★ 규격부터 검증
envs/cad/bin/python -m spatial_vision.cad.verify_obj   --obj $OBJ
envs/cad/bin/python -m spatial_vision.cad.build_usd    --obj $OBJ

# ISM 템플릿 (blenderproc 렌더 42장) — obj 종속, 카메라 무관
( cd third_party/SAM-6D/SAM-6D/Render
  "$VISION_ROOT/envs/seg_sam6d/bin/blenderproc" run --blender-install-path "$VISION_ROOT/envs/blender" \
    render_custom_templates.py --cad_path "$VISION_ROOT/$OBJ/full.ply" --output_dir "$VISION_ROOT/$OBJ/ism_full" )

# SAM3 참조 — ⚠️ **거리·조건 종속**이다. 배포 조건에서 캡처해 만들어야 한다
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda --out runs/ref_near \
    --frames 8 --seed 912 $ZED --distance-m 0.22 0.30 --elevation-deg 40 70 $REFAPP
envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs --from runs/ref_near --obj $OBJ \
    --n 3 --target flange --out-name sam3_refs_flange_n25
```

🔴 **자산이 바뀌면 ISM 템플릿·SAM3 참조를 반드시 재생성한다.** 안 하면 조용히 나빠진다.
🔴 **해상도 모드·거리대를 바꿔도 SAM3 참조는 다시 만들어야 한다**(원거리 참조로 근접 질의 → IoU 0.044).
`capture_real --cam <프로파일>` 이 해상도·캘리브레이션 불일치를 잡아 준다(불일치 시 non-zero 종료).

---

## 참고

- 인터프리터 표(어느 venv 로 무엇을 돌리나) · 실행 규칙 → **`src/CLAUDE.md`**
- 설계 원칙·디렉토리 구조 → `docs/PIPELINE_PLAN.md`
- 라이선스·상업 경로 → `docs/LICENSES.md`
- 카메라·시스템 구성 → `docs/CAMERAS.md`
- 측정 수치의 정본 → `docs/RESULTS.md`
