#!/usr/bin/env bash
# envs/bootstrap.sh — M0 런타임을 처음부터 재현한다. idempotent.
#
#   bash envs/bootstrap.sh            # 전부
#   bash envs/bootstrap.sh stereo     # 특정 것만 (repos|cuda|stereo|pose|seg_sam3|seg_sam6d|stereo_onnx|cad)
#
# 설계 원칙 (PIPELINE_PLAN.md §2):
#   - 모든 것을 이 ws 안에 가둔다. 시스템 python / 다른 ws / ~/.cache 를 건드리지 않는다.
#   - 모델마다 venv 를 분리한다 (의존성이 실제로 충돌한다: sam3 는 numpy<2, FoundationPose 는 numpy>=2).
#   - 전부 python 3.12 (Isaac Sim 번들 python 3.12.13 과 계열 일치).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source envs/env.sh

PY=3.12
CU_INDEX="https://download.pytorch.org/whl/cu128"   # RTX 5090 = sm_120 → cu128 (torch 2.11)
WHAT="${1:-all}"

have() { [ "$WHAT" = "all" ] || [ "$WHAT" = "$1" ]; }

# --- uv (ws 내부) -------------------------------------------------------------
if [ ! -x "$ROOT/envs/bin/uv" ]; then
  echo "== uv 설치 =="
  UV_INSTALL_DIR="$ROOT/envs/bin" UV_UNMANAGED_INSTALL="$ROOT/envs/bin" \
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV="$ROOT/envs/bin/uv"

# uv 0.9+ 는 venv 가 이미 있으면 에러로 멈춘다 → 재실행 시 idempotent 하지 않다.
# --allow-existing 로 기존 venv 를 보존하고 pip install 이 다시 맞춘다(처음부터 다시 만들려면 지우고 실행).
mkvenv() { $UV venv --python $PY --allow-existing "$1"; }

# --- third_party 리포 ---------------------------------------------------------
if have repos; then
  echo "== third_party clone (repos.lock 고정) =="
  mkdir -p third_party
  while read -r dir url sha _; do
    case "$dir" in ''|\#*) continue;; esac
    if [ ! -d "third_party/$dir/.git" ]; then
      git clone -q "$url" "third_party/$dir"
    fi
    git -C "third_party/$dir" fetch -q origin "$sha" 2>/dev/null || true
    git -C "third_party/$dir" checkout -q "$sha" 2>/dev/null || \
      echo "  ! $dir: $sha 체크아웃 실패 (shallow clone 이면 정상 — 현재 HEAD 유지)"
    echo "  $dir @ $(git -C "third_party/$dir" rev-parse --short HEAD)"
  done < third_party/repos.lock
fi

# --- CUDA_HOME 조립 (시스템에 nvcc 가 없다) -----------------------------------
# nvidia-cuda-nvcc-cu12 휠에는 ptxas 만 있고 nvcc 드라이버가 없어서 redist 컴포넌트를 직접 받는다.
if have cuda && [ ! -x "$ROOT/envs/cuda/bin/nvcc" ]; then
  echo "== CUDA 12.8 툴체인 조립 (ws 로컬) =="
  B=https://developer.download.nvidia.com/compute/cuda/redist
  mkdir -p envs/cuda .cache/dl
  for c in cuda_nvcc/linux-x86_64/cuda_nvcc-linux-x86_64-12.8.93-archive \
           cuda_cudart/linux-x86_64/cuda_cudart-linux-x86_64-12.8.90-archive \
           cuda_cccl/linux-x86_64/cuda_cccl-linux-x86_64-12.8.90-archive \
           cuda_profiler_api/linux-x86_64/cuda_profiler_api-linux-x86_64-12.8.90-archive; do
    f=".cache/dl/$(basename "$c").tar.xz"
    [ -f "$f" ] || curl -sL "$B/$c.tar.xz" -o "$f"
    tar -xf "$f" -C .cache/dl
    cp -rn ".cache/dl/$(basename "$c")"/* envs/cuda/ 2>/dev/null || true
  done
  ln -sfn lib envs/cuda/lib64
  envs/cuda/bin/nvcc --version | tail -1
  # redist 만으로는 CUDA_HOME 이 불완전하다 — cusparse.h·libnvrtc 등 math 계열이 없다.
  # 전체 실행이면 뒤의 pose 섹션이 link_cuda_libs.sh 를 부르지만, `bootstrap.sh cuda` 단독 실행이면
  # 아무도 안 부른다. 그 상태의 증상이 고약하다: 빌드는 물론이고 **ORT 가 에러 없이 CPU EP 로 조용히
  # 폴백**해 stereo_onnx 가 ~38× 느려질 뿐 실패하지 않는다(2026-08-07 실측).
  if [ -x "$ROOT/envs/pose/bin/python" ]; then
    bash envs/link_cuda_libs.sh envs/pose
  else
    echo "  ! envs/pose 가 아직 없어 math 라이브러리를 연결하지 못했다."
    echo "    pose 섹션 실행 시 자동 연결된다. 단독으로 고치려면: bash envs/link_cuda_libs.sh envs/pose"
  fi
fi

# --- venv: stereo (FoundationStereo) -----------------------------------------
if have stereo; then
  echo "== venv stereo =="
  mkvenv envs/stereo
  $UV pip install --python envs/stereo/bin/python --index-url $CU_INDEX torch torchvision
  # 추론 경로가 실제로 import 하는 것만. environment.yml 의 xformers/imgaug/albumentations 는
  # 학습·구버전용이고 FoundationStereo core 는 쓰지 않는다 (dinov2 는 xformers 없으면 자동 폴백).
  $UV pip install --python envs/stereo/bin/python \
    opencv-contrib-python einops imageio omegaconf open3d pandas scipy timm \
    scikit-image trimesh transformations ruamel.yaml huggingface-hub gdown ninja
fi

# --- venv: pose (FoundationPose) ---------------------------------------------
if have pose; then
  echo "== venv pose =="
  mkvenv envs/pose
  $UV pip install --python envs/pose/bin/python --index-url $CU_INDEX torch torchvision
  # pybind11 고정: mycpp 의 ABI 를 결정한다. 미고정 상태에서 3.0.4 → 3.1.0 드리프트가 실측됐다
  # (RESULTS.md § M0 재현성 재검증). requirements.txt 에는 pybind11 이 없어 여기가 유일한 지정점이다.
  $UV pip install --python envs/pose/bin/python \
    -r third_party/FoundationPose/requirements.txt ninja "pybind11==3.1.0" fvcore iopath
  # torch 가 끌어온 nvidia-* 휠의 헤더/라이브러리를 CUDA_HOME 에 연결 (cusparse.h 등)
  bash envs/link_cuda_libs.sh envs/pose
  # ★ 커밋 고정. third_party 는 repos.lock 이 묶지만 이 둘은 pip git 의존이라 별도로 박는다 —
  # 고정하지 않으면 HEAD 를 받아 조용히 다른 것이 깔린다(M0 재현성 재검증, 2026-08-07 실측 SHA).
  # 갱신 시: 아래 SHA 를 바꾸고 `uv cache clean pytorch3d nvdiffrast` 후 재실행해야 실제로 다시 빌드된다.
  PYTORCH3D_SHA=9381c4016376345bb795b97c45a6c2de66db354a   # 0.7.9
  NVDIFFRAST_SHA=253ac4fcea7de5f396371124af597e6cc957bfae  # 0.4.0
  MAX_JOBS=${MAX_JOBS:-12} $UV pip install --python envs/pose/bin/python --no-build-isolation \
    "git+https://github.com/facebookresearch/pytorch3d.git@$PYTORCH3D_SHA" \
    "git+https://github.com/NVlabs/nvdiffrast.git@$NVDIFFRAST_SHA"
  # mycpp (pybind11 + Eigen + Boost, CUDA 아님). venv 파이썬을 강제하지 않으면
  # cmake 가 시스템 python 을 잡아 ABI 가 어긋난 .so 를 만든다.
  VENV="$ROOT/envs/pose"
  PB="$($VENV/bin/python -c 'import pybind11;print(pybind11.get_cmake_dir())')"
  rm -rf third_party/FoundationPose/mycpp/build
  mkdir -p third_party/FoundationPose/mycpp/build
  ( cd third_party/FoundationPose/mycpp/build
    PATH="$VENV/bin:$PATH" cmake .. -DCMAKE_BUILD_TYPE=Release \
      -Dpybind11_DIR="$PB" \
      -DPYTHON_EXECUTABLE="$VENV/bin/python" -DPython_EXECUTABLE="$VENV/bin/python" \
      -DPython3_EXECUTABLE="$VENV/bin/python" \
      -DPython_FIND_VIRTUALENV=ONLY -DPython3_FIND_VIRTUALENV=ONLY >/dev/null
    cmake --build . -j"$(nproc)" >/dev/null )
  ls third_party/FoundationPose/mycpp/build/*.so
fi

# --- venv: seg_sam3 (SAM 3) ---------------------------------------------------
if have seg_sam3; then
  echo "== venv seg_sam3 =="
  mkvenv envs/seg_sam3
  $UV pip install --python envs/seg_sam3/bin/python --index-url $CU_INDEX torch torchvision
  $UV pip install --python envs/seg_sam3/bin/python -e third_party/sam3 \
    einops hydra-core omegaconf psutil pycocotools opencv-python matplotlib pandas scipy python-rapidjson
fi

# --- venv: seg_sam6d (SAM-6D ISM 만) -----------------------------------------
# PEM(pose) 은 쓰지 않는다 → pointnet2 CUDA 확장 빌드 불필요. pose 는 FoundationPose 담당.
# 원본은 python 3.9.6 / pytorch-lightning 1.8.1 이지만 ISM 은 pl.LightningModule 상속만 쓰므로
# 최신 lightning + 3.12 로 동작한다.
if have seg_sam6d; then
  echo "== venv seg_sam6d =="
  mkvenv envs/seg_sam6d
  $UV pip install --python envs/seg_sam6d/bin/python --index-url $CU_INDEX torch torchvision
  $UV pip install --python envs/seg_sam6d/bin/python \
    pytorch-lightning torchmetrics fvcore iopath hydra-core hydra-colorlog omegaconf \
    opencv-python pycocotools matplotlib scipy scikit-image pandas ruamel.yaml pyrender \
    distinctipy imageio trimesh gdown timm onnxruntime
  # ultralytics(FastSAM 경로)는 제외: 현행 버전은 `from ultralytics import yolo` 를 없앴고
  # 8.0.135 는 3.12 를 지원하지 않는다. ISM 은 SAM 경로(configs/model/ISM_sam.yaml)를 쓴다.
  # ⚠️ 2026-08-07 확인: 구 venv 에 ultralytics 가 남아 있었다(AGPL). 재빌드로 제거됨 — docs/LICENSES.md §2.

  # BlenderProc: ISM 은 CAD 를 여러 시점에서 렌더한 **템플릿**이 있어야 zero-shot 매칭을 한다(M4).
  # blenderproc 자체는 CLI 래퍼일 뿐이고 실제 렌더는 Blender 번들 python 에서 돈다.
  # ⚠️ Blender 기본 설치 경로가 `/home_local/$USER/blender/` 라 ws 밖을 오염시킨다 →
  #    실행 시 반드시 `--blender-install-path $VISION_ROOT/envs/blender` 를 준다(아래 프리페치와 동일 경로).
  $UV pip install --python envs/seg_sam6d/bin/python "blenderproc==2.8.0"
  if [ ! -d envs/blender ]; then
    echo "  Blender 다운로드(~1GB) — envs/blender"
    envs/seg_sam6d/bin/blenderproc run --blender-install-path "$ROOT/envs/blender" \
      "$ROOT/envs/blenderproc_smoke.py"
  fi
  ls -d envs/blender/*/ 2>/dev/null | head -1
fi

# --- venv: stereo_onnx (NGC FoundationStereo ONNX — 상업 라이선스 경로) ----------
# GitHub FoundationStereo 는 research-only 라이선스다. NGC/TAO 배포 ONNX 는 NVIDIA Open Model
# License(상업 가능)이고 인증도 불필요. 단 라이선스가 청정하려면 **repo 코드를 쓰면 안 되므로**
# 전처리/후처리를 직접 구현한다 (docs/LICENSES.md §3, PIPELINE_PLAN.md M3).
if have stereo_onnx; then
  echo "== venv stereo_onnx =="
  mkvenv envs/stereo_onnx
  # PyPI 의 onnxruntime-gpu 최신판은 CUDA 13 을 요구한다(libcublasLt.so.13). 우리 CUDA_HOME 은 12.8 →
  # CUDA 12 빌드를 전용 인덱스에서 고정한다. CUDA EP 는 envs/cuda 의 libcudart/cudnn/nvrtc 를 쓴다.
  $UV pip install --python envs/stereo_onnx/bin/python onnx numpy opencv-python-headless
  $UV pip install --python envs/stereo_onnx/bin/python "onnxruntime-gpu==1.22.0" \
    --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/ \
    --extra-index-url https://pypi.org/simple
  bash envs/link_cuda_libs.sh envs/pose   # cuda_nvrtc 포함 — ORT CUDA EP 가 libnvrtc.so.12 를 찾는다
  mkdir -p weights/ngc_foundationstereo
  B=https://api.ngc.nvidia.com/v2/models/nvidia/tao/foundationstereo/versions
  for f in "deployable_foundation_stereo_s_dynamic_v2.0/files/deployable_foundation_stereo_s_dynamic_v2.0.onnx"; do
    o="weights/ngc_foundationstereo/$(basename "$f")"
    [ -f "$o" ] || curl -sL -o "$o" "$B/$f"
  done
  ls -lh weights/ngc_foundationstereo/
fi

# --- venv: cad (M1 메쉬 준비 + USD 저작) --------------------------------------
# torch 가 없는 유일한 venv 다 — M1 은 순수 기하 처리라 GPU 가 필요 없다.
#   trimesh    : STL 로드 / 평면 컷 / 연결성분 / watertight·부피 검사 (M1 의 본체)
#   manifold3d : trimesh 의 boolean·컷 백엔드. 없으면 컷면이 캡되지 않아 watertight 가 깨진다
#   rtree, shapely, networkx, scipy : trimesh 가 근접질의·연결성분·최소자승에 쓰는 선택 의존성
#   usd-core   : build_usd.py 가 pxr 로 USD 를 직접 저작한다 (Isaac 번들 python 을 쓰지 않는 이유는
#                M1 산출물 검증까지 한 인터프리터에서 끝내기 위해서다. asset_converter 미사용)
if have cad; then
  echo "== venv cad =="
  mkvenv envs/cad
  # cascadio: STEP(.step/.stp) 리더. 신 CAD 가 STEP 만 제공하고 trimesh 단독으로는 못 읽는다.
  $UV pip install --python envs/cad/bin/python \
    trimesh manifold3d rtree shapely networkx numpy scipy usd-core cascadio
  envs/cad/bin/python - <<'EOF'
import numpy as np, trimesh
from pxr import Usd, UsdGeom
# 평면 컷이 캡을 만드는지(=manifold3d 백엔드가 살아있는지) 확인한다. M1 의 flange 분리가 이것에 의존한다.
top = trimesh.creation.box((10, 10, 10)).slice_plane([0, 0, 0], [0, 0, 1], cap=True)
assert top.is_watertight, "slice_plane cap 실패 — manifold3d 확인"
assert np.isclose(top.volume, 500.0), top.volume
UsdGeom.Xform.Define(Usd.Stage.CreateInMemory(), "/root")
print(f"  trimesh {trimesh.__version__} | slice_plane cap + usd-core OK")
EOF
fi

echo
echo "완료. 검증: bash envs/verify.sh"
