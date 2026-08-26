# envs/env.sh — 이 ws 전용 격리 환경 변수. 모든 스테이지 실행 전에 `source` 한다.
#
#   source /isaac-sim/volume/spatial_manipulation_ws/src/vision/envs/env.sh
#
# 목적: python/torch/CUDA 의존성과 모든 캐시를 이 ws 안에 가둔다.
# 다른 ws(sdg_ws, ur_ws, ...)·시스템 python·Isaac 번들 python 을 오염시키지 않는다.

VISION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export VISION_ROOT

# --- 캐시 격리 (~/.cache 를 일절 쓰지 않는다) ---------------------------------
export XDG_CACHE_HOME="$VISION_ROOT/.cache/xdg"
export PIP_CACHE_DIR="$VISION_ROOT/.cache/pip"
export UV_CACHE_DIR="$VISION_ROOT/.cache/uv"
export TORCH_HOME="$VISION_ROOT/.cache/torch"          # torch.hub 체크포인트
export HF_HOME="$VISION_ROOT/.cache/hf"                # huggingface (모델·토큰)
export TORCH_EXTENSIONS_DIR="$VISION_ROOT/.cache/torch_ext"  # JIT CUDA ext 빌드 산출물
export TRITON_CACHE_DIR="$VISION_ROOT/.cache/triton"
export YOLO_CONFIG_DIR="$VISION_ROOT/.cache/ultralytics"  # 안 잡으면 ~/.config/Ultralytics 에 씀
export MPLCONFIGDIR="$VISION_ROOT/.cache/matplotlib"
export CUDA_CACHE_PATH="$VISION_ROOT/.cache/nv"        # PTX JIT 캐시

# --- uv (ws 내부 설치) --------------------------------------------------------
export UV_PYTHON_INSTALL_DIR="$VISION_ROOT/envs/python"  # uv 가 받아오는 인터프리터
export UV_TOOL_DIR="$VISION_ROOT/envs/uv_tools"
export PATH="$VISION_ROOT/envs/bin:$PATH"

# --- CUDA 툴체인 (ws 내부 조립 — 시스템에 nvcc 가 없다) ------------------------
# NVIDIA redist 컴포넌트(cuda_nvcc/cudart/cccl/profiler_api) 를 envs/cuda 에 병합해 만든 CUDA_HOME.
# nvidia-cuda-nvcc-cu12 휠에는 ptxas 만 있고 nvcc 드라이버가 없어서 이렇게 한다.
export CUDA_HOME="$VISION_ROOT/envs/cuda"
export CUDA_PATH="$CUDA_HOME"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

# --- 빌드 (RTX 5090 = sm_120) -------------------------------------------------
export TORCH_CUDA_ARCH_LIST="12.0"
export MAX_JOBS="${MAX_JOBS:-8}"

# --- CUDA 메모리 단편화 완화 ---------------------------------------------------
# 🔴 FoundationPose 는 **프레임마다 메모리가 쌓여** 뒤쪽 프레임에서 OOM 이 난다.
#    1920×1200 · `pose_fp --input-scale 0.75` 는 frame_0002 에서 죽는데(31GiB 카드),
#    이 한 줄이면 **20/20 통과**한다. 실측: 0.5 ✅ · 0.75 ❌→✅ · 1.0 ❌(단일 할당 6.5GiB, 여전히 불가).
#    → §34-12 의 *"1920×1200 은 0.5 필요"* 상한이 **0.75 로 올라간다**(RESULTS §38-4).
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

mkdir -p "$XDG_CACHE_HOME" "$PIP_CACHE_DIR" "$UV_CACHE_DIR" "$TORCH_HOME" \
         "$HF_HOME" "$TORCH_EXTENSIONS_DIR" "$TRITON_CACHE_DIR" "$CUDA_CACHE_PATH" \
         "$UV_PYTHON_INSTALL_DIR" "$VISION_ROOT/envs/bin"

# 모델별 venv 활성화 헬퍼:  venv stereo | pose | seg_sam6d | seg_sam3
venv() { . "$VISION_ROOT/envs/$1/bin/activate"; }
