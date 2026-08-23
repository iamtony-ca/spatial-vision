# SETUP.md — 새 머신에 처음부터 세우기

> 전제: **베이스 Docker 컨테이너가 떠 있고**, 그 안에 **`src/` 내용이 같은 경로로** 들어 있다.
> 기준 경로는 `/isaac-sim/volume/spatial_manipulation_ws/src/vision` (= `$VISION_ROOT`).
> ⚠️ 코드는 경로 독립이다(`env.sh` 가 상대 경로로 `VISION_ROOT` 를 계산한다). 다만 **`weights/` 아래
> 심링크는 절대 경로**라 경로가 다르면 `place_weights.sh` 를 다시 돌려야 한다(아래 3단계).

---

## 0. 무엇이 어디서 오나 — **조달 경로 4개**

새 머신은 «옛 머신을 통째로 복사» 하지 않는다. 항목마다 **출처가 정해져 있다.**

```
①  git clone           16MB   코드 · 원본 STEP · 카메라 프로파일 · 자산 씨앗 JSON
②a GitHub Release     501MB   우리가 만든 무거운 자산 (ply·usda·ism_full·sam3_refs)
                              현행 태그 **`assets-r4`** (2026-08-17, SAM3 참조 24종 = 거리 6대역 × 외관 4)
②b 수동 이관          가변    실물 캡처 runs/real*  ← 사용자가 직접 옮긴다 (2026-08-12)
③  자동 다운로드       3.9G    NGC ONNX · SAM vit_h · DINOv2   ← 스크립트가 받는다
④  수동(게이트)        6.6G    FoundationStereo · FoundationPose · SAM 3
⑤  재생성             24G+    venv · third_party 코드 · HDRI · 캐시  ← 옮기지 않는다
```

### 0.0 왜 ②를 git 본체에 안 넣나 — **크기가 기준이 아니다**

자산 196MB 는 GitHub 에 **LFS 없이 들어간다**(최대 단일 파일 `mesh.usda` 14.7MB, 한계 100MiB).
그런데 **git 은 히스토리를 영구 보존하고 PNG·PLY 는 델타가 안 먹는다.** 이 프로젝트는 자산이 이미
네 번 바뀌었고(`semi → spec → spec15 → r2`) **바뀔 때마다 `sam3_refs`·`ism_full` 을 재생성해야 한다**
(교훈 #40). git 에 넣으면 매번 ~170MB 가 히스토리에 영구히 쌓이고 되돌릴 수 없다.

| | 무엇 | 기준 |
|---|---|---|
| **git 본체** | 코드 · STEP · cam · 씨앗 JSON | **바뀌면 diff 를 봐야 하는 것.** 텍스트라 델타도 먹는다 |
| **GitHub Release** | ply · usda · ism_full · sam3_refs | **재생성 가능한 스냅샷.** 히스토리 밖 · 파일당 2GB · **지우면 회수된다** |
| **HF dataset** | 실물 캡처 | **계속 늘어나는 데이터.** 부분 다운로드(`--include`)가 된다 |

### 0.1 항목별

| 항목 | 크기 | 출처 | 비고 |
|---|---|---|---|
| `spatial_vision/` `tools/` `configs/` `docs/` `envs/*.sh` `.gitignore` | ~9M | **① git** | |
| `assets/cad/` | 7.9M | **① git** | 원본 STEP. **재생성 불가** |
| `assets/cam/*.json` | 12K | **① git** | 실측 intrinsic. **카메라가 있어야 다시 잰다** |
| `assets/obj/*/[source·meta·keypoints·sam3_prompts·semi_check].json` | 532K | **① git** | 자산 재생성의 씨앗 |
| `third_party/repos.lock` | 1K | **① git** | 커밋 고정 |
| — | | | |
| `assets/obj/foup_300_semi_r2/{*.ply, mesh.usda, views.png}` | 27M | **②a Release** | STEP 에서 재생성 가능(§10) |
| `assets/obj/foup_300_semi_r2/ism_full/` | 69M | **②a Release** | blenderproc 42장 렌더 |
| `assets/obj/foup_300_semi_r2/sam3_refs_*/` | 148M | **②a Release** | 선정 세트 24종(거리 6대역 × 몸체 3종 +혼합). 🔴 **재생성에 Isaac Sim 캡처가 필요**하다 |
| `assets/obj/foup_300_semi_r2/sam3_refs_*_cand/` | 339M | **②a Release** | 후보 풀. **§19 선정 기준을 바꿔 다시 고를 때만** 쓴다 — 급하면 안 풀어도 된다 |
| `runs/real*/` (실물 캡처) | 촬영량 | **②b 수동** | 🔴 **다시 못 찍는다** — 그 자세, 그 조명. `runs/` 는 `.gitignore` 에 있으니 **git 밖에서 백업**할 것 |
| — | | | |
| `weights/ngc_foundationstereo/…_s_dynamic_v2.0.onnx` | 331M | **③ 자동** | `bootstrap.sh`·`fetch_weights.sh` 가 NGC 공개 URL 에서 받는다 |
| `weights/ngc_foundationstereo/…_small_576x960_v2.0.onnx` | 868M | ⚠️ **수동** | **고정 해상도판**(TensorRT 경로용, `docs/LICENSES.md §4`). **13종에 없고 스크립트도 안 받는다** → 안 옮기면 조용히 사라진다. TensorRT 를 안 쓰면 없어도 된다 |
| ISM `sam_vit_h_4b8939.pth` | 2.4G | **③ 자동** | Apache 2.0 · `dl.fbaipublicfiles.com` → 3.5단계 |
| ISM `dinov2_vitl14_pretrain.pth` | 1.2G | **③ 자동** | 동일 |
| — | | | |
| FoundationStereo `23-51-11/{model_best_bp2.pth,cfg.yaml}` | 3.1G | **④ 수동** | NVlabs 배포처. research-only |
| FoundationPose refiner+scorer (+cfg) | 248M | **④ 수동** | NVlabs 배포처. research-only |
| SAM 3 `sam3.pt` + `config.json` + `tokenizer.json` | 3.3G | **④ 수동** | Meta 게이트(HF `HF_TOKEN` 으로 가능) |
| — | | | |
| `envs/` | 12G | **⑤ 재생성** | 🔴 **옮기면 깨진다** — uv 가 venv 에 절대경로를 굽는다 |
| `third_party/<repo>/` 코드 | 3.8G | **⑤ 재생성** | `bootstrap.sh repos` 가 `repos.lock` 대로 clone |
| `assets/env/` | 780M | **⑤ 재생성** | `fetch_env_assets.sh` (sim 캡처용. 실카메라만 쓰면 불필요) |
| `.cache/` `runs/`(실험) | 77G | **⑤ 버린다** | 재현 명령은 `RESULTS.md` |

🔴 **④의 6.6G 만 사람이 옮긴다.** 나머지는 전부 명령으로 재현된다.

⚠️ **`weights/models/` 26G 전부가 필요한 게 아니다.** 실제로 쓰는 건 위 ④ 6.6G 뿐이고 나머지 19G 는
안 쓰는 변형·중복 포맷이다 — `sam3.1`(6.6G, 옵션) · `foundationstereo/11-33-40`(752M) ·
`foundationstereo/onnx`(718M) · `foundationpose_dataset`(1.4G, 데모) · sam3 의 `model.safetensors`(3.3G,
`sam3.pt` 와 같은 가중치의 HF 포맷). **판단 기준은 `check_weights.sh` 의 13종**이다.

### 0.1b ④를 옮기는 두 가지 방법

```bash
# (a) 옛 머신에서 직접 — 가장 단순
cd /isaac-sim/volume/spatial_manipulation_ws/src/vision
rsync -avPR weights/models/foundationstereo/23-51-11 weights/models/foundationpose \
    weights/models/sam3 <새PC>:/<경로>/vision/

# (b) 옛 머신이 없어질 거라면 — HF **private** repo 로 미러
```

🔴 **(b) 는 반드시 private 이어야 한다.** FoundationStereo·FoundationPose 는 NVIDIA Source Code License 로
**research purposes only** 이고 SAM 3 도 재배포 조건이 있다(`docs/LICENSES.md §1·§2`). **공개 재배포는 하지 않는다.**
공개 HF 에 올려도 되는 것은 **②(우리가 만든 것)** 뿐이다.
⚠️ `assets/cad/*.step` 은 **출처를 확인한 뒤** 공개 여부를 정한다 — 외부에서 받은 CAD 면 조건이 붙어 있을 수 있다.

### 0.1c ②a 자산 릴리스 — `envs/pack_assets.sh`

**옛 머신에서** 묶는다. `.gitignore` 경계와 **정확히 같은 것**만 담는다 — 씨앗 JSON 은 git 이
관리하므로 tarball 에 넣지 않는다(풀 때 추적 파일을 덮어써서 «정본이 어느 쪽인가» 가 흐려진다).

```bash
bash envs/pack_assets.sh --list            # 담을 목록만 확인
bash envs/pack_assets.sh                   # → dist/foup_300_semi_r2_assets.tar.gz (+ .sha256)
gh release create assets-r4 dist/*.tar.gz dist/*.sha256 --title "자산 r4"
```

🔴 **`gh` 가 없는 머신이 흔하다**(이 워크스테이션도 없다). REST API 로 하면 설치가 필요 없다 —
**토큰은 `read -rs` 로 받는다**(`export GH_TOKEN=ghp_…` 로 치면 셸 히스토리에 평문으로 남는다):

```bash
read -rsp "PAT: " GH_TOKEN; echo; export GH_TOKEN     # 권한은 Contents: Read and write 하나면 된다
REPO=iamtony-ca/spatial-vision
curl -sS -o /dev/null -w "auth HTTP %{http_code}\n" \
    -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/user      # 200 이어야 한다

git tag -a assets-r4 -m "자산 r4" && git push origin assets-r4
python3 -c 'import json; json.dump({"tag_name":"assets-r4","name":"자산 r4",
    "body":open("dist/RELEASE_NOTES_assets-r4.md").read()},
    open("/tmp/payload.json","w"), ensure_ascii=False)'
curl -sS -X POST "https://api.github.com/repos/$REPO/releases" \
    -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github+json" \
    --data @/tmp/payload.json -o /tmp/rel.json -w "HTTP %{http_code}\n"   # 201
export RELEASE_ID=$(python3 -c 'import json; print(json.load(open("/tmp/rel.json"))["id"])')

for f in dist/foup_300_semi_r2_assets.tar.gz dist/foup_300_semi_r2_assets.tar.gz.sha256; do
  curl -sS --progress-bar -X POST \
    "https://uploads.github.com/repos/$REPO/releases/$RELEASE_ID/assets?name=$(basename $f)" \
    -H "Authorization: Bearer $GH_TOKEN" -H "Content-Type: application/octet-stream" \
    --data-binary "@$f" -o /tmp/up.json -w "HTTP %{http_code}\n"          # 201
done
unset GH_TOKEN
```

⚠️ **curl 응답을 파서로 바로 파이프하지 말 것** — 실패하면 `KeyError: 'id'` 만 보이고 진짜 이유
(`Bad credentials` 등)가 삼켜진다. `-o <파일> -w "HTTP %{http_code}"` 로 **본문과 코드를 따로** 받는다.

**새 머신에서:**

```bash
gh release download assets-r4 --dir dist     # gh 없으면 아래 curl
#   curl -sSL -O https://github.com/$REPO/releases/download/assets-r4/foup_300_semi_r2_assets.tar.gz
#   curl -sSL -O https://github.com/$REPO/releases/download/assets-r4/foup_300_semi_r2_assets.tar.gz.sha256
bash envs/pack_assets.sh --check dist/foup_300_semi_r2_assets.tar.gz    # sha256
tar -C assets/obj -xzf dist/foup_300_semi_r2_assets.tar.gz
envs/pose/bin/python tools/run_group_a.py --list-presets                # 27종 ✅ 확인
```

실측: 582M → **501M**(`assets-r4`, sha256 `b18d9ab1…`). 대부분이 SAM3 참조(선정 148M + 후보 339M)다.
🔴 **업로드는 끝나도 잘렸을 수 있다** — 올린 뒤 **다시 받아서 sha256 을 대조**한다. GitHub 은
잘린 파일도 `state: uploaded` 로 보고한다.
⚠️ `dist/` 는 `.gitignore` 에 있다 — **커밋하는 게 아니라 릴리스로 올린다.**
⚠️ 자산을 재생성하면 **새 태그**를 만든다(다음은 `assets-r5`). 같은 태그에 덮어쓰면 이미 받아 간 쪽의
`--check` 가 조용히 깨진다. 옛 태그를 지우면 용량이 실제로 회수된다.

### 0.2 컨테이너 — 트리는 **호스트**에 두고 bind-mount 한다

🔴 **컨테이너 안에 100GB 를 쌓지 않는다.** 컨테이너를 다시 만들면 전부 날아가고 이미지도 비대해진다.
호스트 디렉토리를 `/isaac-sim/volume` 에 물려서 쓴다 — 지금 트리 경로가 그래서 `/isaac-sim/volume/…` 이다.

```bash
docker run --gpus all --network host -it \
    -v /<호스트경로>:/isaac-sim/volume \
    <isaac-sim 이미지> bash
```

⚠️ **경로를 그대로 유지하는 쪽이 안전하다.** 코드는 경로 독립이지만 `weights/` 아래 심링크는 절대
경로라, 경로가 달라지면 3단계(`place_weights.sh`)를 반드시 다시 돌려야 한다.
⚠️ 드라이버가 **sm_120(RTX 5090)** 을 지원해야 한다 — `nvidia-smi` 와 `verify.sh` 1/5 가 확인해 준다.

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
bash envs/fetch_weights.sh          # ★ 자동 가능한 것 전부 (NGC · SAM vit_h · DINOv2 · SAM3)
bash envs/place_weights.sh          # 기본 소스: weights/models
bash envs/check_weights.sh          # 13종 존재·크기 확인
bash envs/check_weights.sh --sha256 # ★ 내용까지 대조 (weights/MANIFEST.sha256)
```

`fetch_weights.sh` 는 **못 받는 것은 출처를 안내하고 실패한다** — 라이선스 게이트가 걸린
FoundationStereo·FoundationPose 는 Google Drive «폴더» 라 자동화가 불가능하다.
`SAM3` 는 `HF_TOKEN` 이 있으면 자동으로 받는다(Meta 게이트 리포에서 동의 후 토큰 발급).

### 🔴 크기 검사만 믿지 않는다 — `MANIFEST.sha256`

`check_weights.sh` 의 기본 검사는 `≥300MB` 식이라 **잘린 파일·다른 버전·다른 변형을 통과시킨다.**
게이트 걸린 6.6G 는 사람이 브라우저로 받아 옮기므로(중단·재다운로드·`-001` 접미사) 실제로 일어난다.

```bash
bash envs/check_weights.sh --write-manifest   # 🔴 **원본 트리가 살아있을 때** 만든다
bash envs/check_weights.sh --sha256           # 새 머신에서 대조 (불일치면 non-zero)
```

`weights/MANIFEST.sha256` 는 3KB 텍스트라 **git 이 추적한다**(`.gitignore` 에 재포함 규칙이 있다).
⚠️ 대조는 «검사한 건수 / 매니페스트 건수» 를 함께 낸다 — **전부 없어서 0건 검사한 것이
성공으로 보이지 않게** 하기 위해서다.

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

## 3.5 SAM-6D ISM 체크포인트 — **clone 으로 안 따라온다**

🔴 `sam_vit_h`(2.4G)·`dinov2_vitl14`(1.2G)는 **clone 된 디렉토리 안에 나중에 내려받아 두는 파일**이라
git 에 없고, `place_weights.sh` 도 이 둘은 다루지 않는다(그건 FoundationStereo·FoundationPose·SAM3 만
심링크한다). 그래서 **`bootstrap.sh` 만 돌리면 `check_weights.sh` 가 11/13** 이 된다.

```bash
( cd third_party/SAM-6D/SAM-6D/Instance_Segmentation_Model
  ../../../../envs/seg_sam6d/bin/python download_sam.py
  ../../../../envs/seg_sam6d/bin/python download_dinov2.py )
```

✅ 둘 다 **Apache 2.0 · `dl.fbaipublicfiles.com` 공개 URL** 이라 계정도 라이선스 동의도 필요 없다.
(원한다면 `weights/models/` 로 옮기고 `place_weights.sh` 에 링크를 추가해도 된다 — 그러면 이관 세트에 포함된다.)

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

# [Jetson → 5090] 🔴 **이관.** 파이프라인 입력은 프레임당 3파일뿐이라 통째로 옮기면 된다
#   (1920×1200 PNG 쌍 ≈ 프레임당 5~8MB → 20프레임 ≈ 150MB)
rsync -avP runs/real01_near/ <5090>:/isaac-sim/volume/spatial_manipulation_ws/src/vision/runs/real01_near/

# [5090] 옮겨진 게 온전한지 먼저 — **잘린 PNG 는 조용히 틀린 결과를 만든다**
find runs/real01_near -name '*.png' | wc -l      # = 프레임 수 × 2
envs/pose/bin/python -c "
import cv2,glob,sys
bad=[p for p in glob.glob('runs/real01_near/frame_*/*.png') if cv2.imread(p) is None]
print('🔴 못 읽는 파일:', bad) if bad else print('✅ PNG', len(glob.glob('runs/real01_near/frame_*/*.png')), '장 전부 정상')"

# [5090] 🔴 여기서부터 **매번** — 안 하면 ONNX 가 조용히 CPU 로 떨어진다
cd /isaac-sim/volume/spatial_manipulation_ws/src/vision && source envs/env.sh

# [5090] ★ 손으로 잇지 말고 **A그룹 러너**를 쓴다 — 4개 venv 를 알아서 오가고
#        GT-free 리포트(report.md)·그림·배선 감사까지 낸다. 멱등이라 다시 돌려도 없는 것만 채운다.
envs/pose/bin/python tools/run_group_a.py --list-presets     # ① 참조 세트가 있는지 먼저 (인자 불필요)
envs/pose/bin/python tools/run_group_a.py \
    --in runs/real01_near --out runs/real01_A --preset n25orange \
    --text-prompt "orange plastic box" --mode all \
    --note "형광등 2등, 정면, 1차 시도" --true-distance-mm 250    # ② 뒤 둘은 선택 인자
# 여러 번 돌린 뒤 — 설정 diff 를 먼저 내고 지표를 나란히 놓는다 (누적 실험 노트)
envs/pose/bin/python tools/compare_runs.py runs/real0*_A --index runs/runs_index.md
```

★ **이미 PC 에 이미지가 있으면 위를 건너뛰고 §8.1 로 간다** — 복붙 순서와 `--mode` 선택,
그리고 **읽는 순서**가 거기 정리돼 있다.

★ `--preset` 은 **거리대 × 몸체 외관**이다(`n30orange` 식). 🔴 참조가 거리 종속이라 틀리면
조용히 무너진다 — `--list-presets` 로 먼저 확인한다. 🔴 접미사 없는 `n20`·`n25`·`n30` 은
**외관 축 이전의 구 세트**라 새 실험에 쓰지 않는다.
★ `--ism`(CAD 템플릿) · `--sam3-text`(낱말) 은 **추가 촬영 0 인 대조군**이고 둘 다 **`--primary full`**
이라 `mask_flange` 가 비어도 pose 가 나온다 — 검정 몸체에서 실제로 그 상황이 났다(`RESULTS.md §35-2m`).
`--text-prompt` 는 **몸체 색에 맞춘다**(`"black/orange/clear plastic box"`).
★ `--note` 는 `run_meta.json` 에 남아 `compare_runs.py` 가 함께 보여준다. `--true-distance-mm`
(줄자값)을 주면 **FP 추정 z 와 stereo depth 중 어느 쪽이 틀렸는지**까지 갈린다 —
안 줘도 둘끼리는 비교된다(`RESULTS.md §35-2l`).

### 8.1 ★ **이미 이미지가 PC 에 있을 때 — 복붙 순서 5줄**

🔴 **먼저 갈림길 하나** — 이관해 온 것이 무엇이냐에 따라 ②를 **건너뛴다**:

| 옮겨 온 것 | ②(변환) | 왜 |
|---|---|---|
| `capture_real` 산출 디렉토리(`frame_XXXX/{left,right,cam.json}`) | ❌ **불필요** | 이미 우리 규약이다. **③으로 바로 간다** |
| ZED Explorer·`.svo` 추출 등 **임의 파일명 PNG 쌍** | ✅ 필요 | 아래 루프로 프레임 디렉토리를 만든다 |

촬영이 끝나 `left/right` PNG 쌍이 손에 있는 경우(파일명은 아무래도 좋다). **이게 실물 최단 경로다.**

```bash
cd /isaac-sim/volume/spatial_manipulation_ws/src/vision
source envs/env.sh                                   # ① 🔴 빼먹으면 ONNX 가 조용히 CPU 로 떨어진다

# ② PNG 쌍 → 프레임 디렉토리 (파일명 규칙만 본인 것으로 바꾼다)
i=0
for L in /path/to/shots/*_left.png; do
    R="${L/_left/_right}"                            # ← 우측 파일명 규칙
    printf -v FR "frame_%04d" $i
    python3 tools/make_frame_from_zed.py --left "$L" --right "$R" \
        --cam assets/cam/zedx_s48560070_hd1200.json --out runs/real01/$FR || break
    i=$((i+1))
done

envs/pose/bin/python tools/run_group_a.py --list-presets      # ③ 참조 세트 확인 (인자 불필요)

# ④ 전 체인 — stereo·SAM3(exemplar+텍스트)·ISM·FP(±stage2)·정합 6변형·리포트까지 한 번에
#    처음이면 --limit-frames 3 으로 먼저 돌려 설정을 확인하고, 그다음 전체를 돌린다
envs/pose/bin/python tools/run_group_a.py \
    --in runs/real01 --out runs/real01_A --preset n25orange \
    --ism --sam3-text --text-prompt "orange plastic box" \
    --mode wide \
    --note "형광등 2등, 0.28m, 1차" --true-distance-mm 280

# ④′ 🔴🔴 **이게 실물에서 실제로 칠 한 줄이다 — 「후보를 전부 펼친다」 30팔.**
#    ★ `--ism`·`--sam3-text` 는 **`--mode all` 이 자동으로 켠다**(그 둘은 모드가 아니라 별도
#      플래그라, 안 켜지면 경로 둘이 통째로 빠져 30 → 24 가 된다)
#    ★ `--preset` 과 `--text-prompt` 를 **개체 몸체 색**에 함께 맞춘다 (아래 표)
envs/pose/bin/python tools/run_group_a.py \
    --in runs/real01 --out runs/real01_Aall --preset n30black \
    --text-prompt "black plastic box" \
    --mode all \
    --note "형광등 2등, 0.28m, 전팔" --true-distance-mm 280

# ⑤ 두 번째 런부터 — 설정 diff 를 먼저 내고 지표를 나란히 (누적 실험 노트)
envs/pose/bin/python tools/compare_runs.py runs/real0*_A --index runs/runs_index.md
```

★ **몸체 색 → `--preset` · `--text-prompt` 짝** (거리대는 실제 촬영 거리로 바꾼다):

| 몸체 | `--preset` | `--text-prompt` |
|---|---|---|
| 검정 불투명 | `n25black` / `n30black` / `n40black` / `n50black` … | `"black plastic box"` |
| 반투명 주황 | `n30orange` 식 | `"orange plastic box"` |
| 투명 | `n30clear` 식 | `"clear plastic box"` |
| 모르겠다 | `n30mixed` 식 | `"plastic box"` |

**소요 (실측, RTX 5090 · 콜드 스타트 포함)** — 🔴 프레임 수보다 **모드**가 지배한다:

| | 기본 `default` (9팔) | `--mode all` (30팔) |
|---|---|---|
| **8프레임** (실물 운용 규모) | ~1.5분 | **~7분** |
| 20프레임 | 5~6분 | **13.4분** (실측 799·804·816초, 3회) |

멱등이라 다시 돌려도 없는 것만 채운다(`--force` 로 강제, `--only st,A1` 로 부분 실행).
시각 산출물만 다시 그리려면 `--only ov,ovc,segcmp,diag --force`(수 초).
★ **처음 시험은 `--limit-frames 3`** — 설정(참조·프롬프트·거리)이 맞는지부터 1~2분에 확인하고
그다음 전체를 돌린다.

🔴🔴 **표본 경고 — 실물 7~10장은 «꼬리를 못 보는» 크기다.** 무결점이어도 95% 상한은
**n=7 → 실패율 35% · n=10 → 26%** 다(rule of three, 교훈 #58: n=40 무결점이 n=120 에서
110/120 이었던 전례). 7~10장으로 할 수 있는 것은 **«어느 팔이 깨졌나»(고장 검출)** 이고,
**«어느 팔이 더 정확한가»(서열)는 못 낸다.** 후보를 2~3개로 좁힌 뒤 **그 후보만 20~40장**으로
다시 찍는 것이 순서다(§35-2o-4 선택 편향).
⚠️ 그리고 **런 사이 KPI 는 1~3장 그냥 흔들린다**(GPU 비결정론, 교훈 #24 · `RESULTS.md §35-2p-6`) —
7~10장에서 **1~3장 차이는 잡음**이다. 손으로 촬영을 늘리는 편이 항상 싸다.

🔴 **③을 건너뛰지 말 것** — `--preset` 은 **촬영 거리대 × 몸체 외관**이고(`n30orange` 식) SAM3 참조가
거리 종속이라 틀리면 **조용히 무너진다**(원거리 참조로 근접 질의 시 IoU 0.044 전례).
없는 세트를 주면 러너가 **종료코드 2 로 죽는다** — 조용한 실패보다 낫다.
⚠️ `--note`·`--true-distance-mm`(줄자값)은 **선택**이지만 둘 다 주는 게 좋다. 전자는 실험 노트에
남고, 후자는 **거리 사각 대조**를 완성한다. 🔴🔴 **줄자가 특히 중요한 이유**: `FP 추정 z` 와
`stereo depth` 는 **둘 다 `Z = fx·B/disparity`** 라 «독립» 이 아니다 — `fx·B` 가 틀리면 **같은 비율로
같이** 틀린다(교훈 #89). `scale_check`(실루엣)이 `baseline` 축을 열지만 **`fx` 는 순수 스케일이라
어떤 내부 관측으로도 못 잡는다.** 줄자(또는 §7.5c 상대 GT)가 유일한 외부 길이다.
⚠️ **줄자 기준점은 `flange` 상면 중심**이다(pose 원점 규약). 몸체 바닥·받침대를 재면 344mm 급으로
어긋나고 그건 «편향» 이 아니라 «다른 것을 쟀다» 다.
★ **`--mode`** — **후보 파이프라인을 얼마나 넓게 펼치나**(`--list-modes`). 기본 `default` = 9팔로
지금까지와 같다. **`wide` = 18팔**(정합·게이트·초기값·캐스케이드·select·edge) 이 **실물 초반 권장**이고,
**`all` = 30팔**(+ 참조 거리대 스윕 · `--ism`·`--sam3-text` 자동 — ④′)이다. 20프레임 기준 wide +3~4분 · all +4~6분.
⚠️ **`all` 은 «구현된 모드 전부» 이지 «가능한 파이프라인 전부» 가 아니다** — 미구현 축(prompt·band·
stereo·jitter)과 **hand-eye 가 필요한 넷**(P1 2단계 · P2 G9 · P3 5시점 융합 · P4 G9+G10)은 빠진다.
뒤의 넷은 `cam1_T_cam2` 가 있어야 성립하는데 로봇이 없으면 그 값이 **부정확한 게 아니라 존재하지 않는다.**
🔴 넓히기는 «탐색» 이지 «성능 향상» 이 아니다 — 팔 ≥8 이면 리포트가 **선택 편향 경고**를 낸다.
좁힌 뒤에는 **새로 찍은 20~40장**에서 확인한다(§35-2o-4).
★ **그 밖의 인자는 `--help` 가 정본이다.** 운용에서 실제로 쓰는 것만 추리면:

| 인자 | 언제 |
|---|---|
| `--report-only` | 계산 없이 **리포트만** 다시 낸다 (문구·판정을 고친 뒤) |
| `--only <스텝>` / `--force` | 부분 실행 / 산출물이 있어도 다시 |
| `--dry-run` | 무엇이 돌지 **명령만** 찍어 본다 |
| `--stereo-scale` | ONNX 입력 배율. 🔴 기본 0.5 — 1280×720 초과에서 OOM(§34-12) |
| `--text-select` | T그룹 인스턴스 선택 규칙(`center`/`score`). 🔴 `center` 는 «카메라가 타깃을 겨눈다» 는 씬 규약에 기댄다(교훈 #15) |
| `--overlay-frames` / `--overlay-mask-alpha` / `--diag-all` | 시트에 넣을 프레임 수 / 마스크 투명도 / 진단 시트를 전 프레임에 |
| `--refs-sweep` | `--mode refs` 가 돌 참조 프리셋 목록(쉼표). **안 주면 `--preset` 과 같은 외관의 모든 거리대**를 자동으로 잡는다. 🔴 없는 프리셋은 종료코드 2 로 거부 — 조용히 빠지면 «스윕했다고 믿는 반쪽 런» 이 된다 |
| `--refs-sweep-nrefs` | `--mode refs` 에서 흔들 `--n-refs` 값(기본 `1,5`) |
| `--use-prompts-file` | A그룹 SAM3 exemplar 질의에 `assets/obj/<id>/sam3_prompts.json` 의 텍스트를 **같이** 준다. 기본은 안 쓴다 — exemplar 만으로 지정이 끝나기 때문 |
| `--allow-cpu` | `env.sh` 없이 CPU 폴백 허용 (수십 배 느리다 — 교훈 #80) |

★ **`--limit-frames N`** — 앞 N 장만 돌린다(`<out>/_in_first<N>/` 심링크). 새 설정·새 프롬프트를
처음 시험할 때 3~6장으로 먼저 확인하면 4~5분을 1분으로 줄인다.
★ **`--text-conf`**(T그룹 임계값, 기본 `0.15`) — 미검출이 나오면 `0.05` 로 낮춘다. sim 에서 미검출
프레임을 `0.01` 로 다시 뽑으니 **IoU 0.988** 이었다(«분할이 틀린» 게 아니라 «점수만 낮은» 것).
🔴 낮추면 오선택 위험이 오르므로 **`segcmp/seg_compare.png` 의 «이탈» 열(>0.25)로 확인**한다.
⚠️ 입력은 **rectified · PNG 무손실** 이어야 한다. ZED SDK 의 `sl.VIEW.LEFT/RIGHT` 가 정류본이고
`*_UNRECTIFIED` 는 `k1 0.543` 이 살아 있어 `cam.json`(왜곡항 0)과 안 맞는다.
🔴 `make_frame_from_zed.py` 는 **정류를 하지 않는다** — 이미 정류된 것을 받는다고 **가정**한다.

**나온 결과를 읽는 순서** (`runs/real01_A/report.md`):

| 순서 | 볼 것 | 왜 |
|---|---|---|
| **0** | 🔴🔴 `## 배선 감사` | **여기가 ❌ 면 아래를 전부 읽지 말 것.** 배선이 어긋나면 숫자는 «틀린» 게 아니라 **«다른 뜻»** 이 되고 GT 없이는 눈으로 못 잡는다. 러너가 `tools/audit_run.py` 를 자동으로 돌린다 |
| 1 | `## 촬영 진단` + `## 판정` 의 📏 눈금 | **이 런에서 10mm 가 몇 px 인가** — 오버레이를 정량적으로 보게 된다 |
| 2 | 🔴 `overlay_sheet.png` | **GT 가 없으니 «맞는가» 를 보는 유일한 수단.** 지표를 아무리 봐도 «다 같이 틀린» 경우는 여기서만 보인다 |
| 2b | 🔴🔴 `stats/distance.png` | **거리 4다리.** 실루엣만 갈라짐 → `baseline` · 셋이 붙고 줄자만 다름 → **`fx`**. ⚠️ `FP z`·`stereo` 는 «독립» 이 아니다(교훈 #89) |
| 2c | 🔴 `stats/ranking.png` | **팔 서열** — \|Δdx\| 정렬. 🔴 `*all-gated`·`Z-fixed`·`init!=` 꼬리표가 붙은 팔은 **나란히 놓을 수 없다** |
| 2d | `stats/heatmap.png` | 프레임 × 팔. **가로줄 = 어려운 프레임**(오버레이를 열 것) · **세로줄 = 나쁜 팔** |
| 3 | `## 이 값이 상이한가` | sim 대역과 비교. ⚠️ 벗어남이 곧 고장이 아니다(도메인 갭일 수 있다) |
| 4 | `## 이상 프레임` | 기준선 불필요 — **런 자기 자신이 기준**이라 도메인 갭에 면역 |
| 5 | `## 여기부터 보라` → `worst/A1_debug/*/contour_debug.png` | Sobel 이 **물체 경계**를 잡았나, 융기 능선·그림자를 잡았나 |
| 6 | `## 다음에 무엇을 할까` | **촬영 횟수 순** 행동 목록 |
| 7 | `diag/diag_sheet.png` · `diag_trends.png` | «어디서 깨졌는가»(분할·depth·노출) |

증상별 처방 지도는 **`PIPELINE_CATALOG.md §9.1(e)`** 다.

---

⚠️ Jetson 에는 우리 venv 가 없다. `capture_real` 은 **repo import 가 0** 이라 **파일 하나만 복사해도**
돌아간다. 필수는 `pyzed`·`numpy` 뿐이고 `cv2` 는 있으면 쓰고 없으면 ZED SDK 로 저장한다.
🔴 **`pip install opencv-python` 금지** — numpy>=2 를 끌어와 pyzed 가
*"numpy.core.multiarray failed to import"* 로 죽는다. `apt install python3-opencv` 또는 `pip install --no-deps opencv-python-headless`.
🔴 **`LANG` 을 UTF-8 로 잡는다** (`export LANG=C.UTF-8`) — 안 잡으면 파이썬 기본 인코딩이 ASCII 가 되고
한글 문자열에서 죽는다. 코드는 막아 뒀지만 앞으로 올릴 다른 코드가 또 밟는다(횡단 정리 #77).

---

## 9. 자주 밟는 함정

| 증상 | 원인 | 조치 |
|---|---|---|
| `~/.cache` 가 커진다 / 다른 ws 가 깨진다 | `source envs/env.sh` 를 빼먹었다 | 항상 먼저 source |
| import 는 되는데 런타임 crash | venv 재생성 후 CUDA 심링크 끊김 | `bash envs/link_cuda_libs.sh envs/pose` |
| `weights/sam3` 가 깨진 링크 | 심링크가 **절대 경로**다 | `bash envs/place_weights.sh` 재실행 |
| **`bootstrap.sh` 가 Blender 받다 `HTTPError: 401 authenticationrequired`** | **사내망 프록시**가 가로챈 응답이다 — `download.blender.org` 는 인증이 없다 | **무시해도 된다.** `SKIP_BLENDER=1 bash envs/bootstrap.sh` → **§9.1** |
| `uv venv` 가 에러로 멈춤 | uv 0.9+ 는 기존 venv 에서 멈춘다 | `bootstrap.sh` 가 `--allow-existing` 을 준다. 완전 재생성은 해당 디렉토리를 지우고 실행 |
| `capture_sim` 이 실패했는데 종료코드 0 | Isaac 의 `fastShutdown` 이 `SystemExit` 을 삼킨다 | 이미 `os._exit(code)` 로 강제해 뒀다. 산출물 개수를 함께 확인할 것 |
| FoundationPose OOM (1920×1200) | crop 을 원본 크기로 되돌리며 warp 한다 | **`pose_fp --input-scale 0.5` 필수** |
| ONNX stereo 가 1280×720 이상에서 OOM | Softmax 단일 버퍼 10.2GB | `--scale` 로 줄인다(1920×1200 은 0.5) |
| 스테이지 1회 실행에 40초 | **콜드 스타트** — ONNX 세션 31.5s + FP 7.1s | 배포에서는 **상주 서버 + IPC** 가 필요하다(`RESULTS.md §34-12b`) |
| **스테레오가 미칠 듯이 느리다 / `Failed to load library libonnxruntime_providers_cuda.so … libcublasLt.so.12`** | `source envs/env.sh` 를 안 했다 → `LD_LIBRARY_PATH` 에 `envs/cuda/lib64` 가 없어 ONNX 가 **조용히 CPU 로 폴백**한다(결과는 맞고 속도만 죽는다) | `source envs/env.sh` 먼저. `run_group_a.py` 는 이제 **종료코드 2 로 차단**한다(의도적이면 `--allow-cpu`) → 횡단 정리 #80 |
| **`seg_ism` 이 중간 프레임에서 `RuntimeError: Input and output sizes should be greater than 0, but got input (H: 0, W: 30)`** | SAM 이 **높이 0 인 제안**을 내면 ISM 의 `CropResizePad` 가 빈 텐서를 `F.interpolate` 에 넣는다. **한 프레임 때문에 스테이지 전체가 종료**된다 | 고쳐 뒀다(`segment_sam6d.py` 가 퇴화 제안을 거르고 제외 개수를 로그로 찍는다). 옛 체크아웃이면 그 커밋을 받는다 → 횡단 정리 #81 |
| `stat -c%s` 가 이상한 값 | 심링크 자체 크기 | `stat -Lc%s` |
| **Jetson 에서 `UnicodeDecodeError: 'ascii' codec can't decode byte 0xeb`** | `LANG` 이 없어 파이썬 기본 인코딩이 ASCII 다. **이 저장소는 문자열이 전부 한국어**라 구조적으로 노출된다 | `export LANG=C.UTF-8` (또는 `PYTHONUTF8=1`). 코드 쪽은 `encoding="utf-8"` 명시 + stdout 재설정으로 막아 뒀다 → 횡단 정리 #77 |
| 새 머신에서 `assets/cad` 가 `<dst>/cad` 로 들어갔다 | `rsync` 에 `-R` 을 빼먹었다 | §0.1 의 명령을 그대로 쓴다 |

### 9.1 Blender 401 — **넘어가는 게 정답이다**

사내망에서 `bootstrap.sh seg_sam6d` 가 이렇게 죽는 것처럼 보인다:

```
Downloading blender from https://download.blender.org/release/Blender4.2/blender-4.2.1-linux-x64.tar.xz
urllib.error.HTTPError: HTTP Error 401: authenticationrequired
```

🔴 **401 은 blender.org 가 아니라 프록시가 낸 것**이다. 그 서버는 인증을 요구하지 않는다 — 사외 PC 에서는 안 나고 사내에서만 난다.

**Blender 가 필요한 경우는 «새 CAD 로 ISM 템플릿을 다시 렌더할 때» 하나뿐이다.** ISM **추론**은
`blenderproc` 을 import 하지 않는다. 필요한 건 렌더 «결과물»인 `assets/obj/<id>/ism_full/` (42장, 69MB)이고
그건 **②a 자산 릴리스에 들어 있다**(§0.1c). 즉 릴리스를 푼 머신은 Blender 없이 전 파이프라인이 돈다.

`bootstrap.sh` 는 이 실패를 `|| { … }` 로 삼키게 돼 있다(`envs/bootstrap.sh` 의 Blender 프리페치 블록).
traceback 바로 다음 줄에 이게 찍혔으면 **그 런은 정상 완료된 것**이고 뒤의 `stereo_onnx`·`cad` venv 도 다 만들어졌다:

```
⚠️ Blender 다운로드 실패 — **넘어간다**. ISM 추론에는 필요 없다.
```

소음과 1GB 헛시도까지 없애려면:

```bash
SKIP_BLENDER=1 bash envs/bootstrap.sh
bash envs/verify.sh          # 5단계 스모크 — Blender 항목은 애초에 없다
```

**정말 필요해지면 손으로 넣는다** — `envs/blender/blender-4.2.1-linux-x64/` 가 있으면 다운로드를 건너뛴다:

```bash
mkdir -p envs/blender
tar -xJf blender-4.2.1-linux-x64.tar.xz -C envs/blender
ls envs/blender/blender-4.2.1-linux-x64/blender    # 이게 보이면 끝
```

⚠️ **버전은 4.2.1 이어야 한다** — `blenderproc==2.8.0` 이 그 경로명을 기대한다.
⚠️ 첫 실행 때 blenderproc 이 번들 python 에 패키지를 더 깔아 **1.0G → 2.0G** 로 불어난다(PyPI 라 대개 열려 있다).
그것도 막히면 **다 만들어진 `envs/blender/` 를 통째로 rsync** 하는 게 제일 빠르다.

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
