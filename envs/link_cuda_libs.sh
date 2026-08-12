#!/usr/bin/env bash
# envs/cuda(CUDA_HOME) 에 CUDA math 라이브러리의 헤더/라이브러리를 연결한다.
#
#   bash envs/link_cuda_libs.sh envs/pose
#
# 왜 필요한가: NVIDIA redist 로 조립한 CUDA_HOME 에는 nvcc/cudart/cccl 만 있어서
# cusparse.h·cublas.h 등이 없다 → torch C++ 확장(pytorch3d, nvdiffrast) 빌드가 깨진다.
# torch 가 pip 로 끌어온 nvidia-* 휠에 헤더와 .so 가 들어 있고, **torch 와 ABI 가 정확히 일치**하므로
# 그걸 CUDA_HOME 으로 연결한다. venv 를 다시 만들면 이 스크립트를 다시 돌려야 한다.
set -euo pipefail

VENV="$(cd "${1:?usage: link_cuda_libs.sh <venv-path>}" && pwd)"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CUDA="$ROOT/envs/cuda"
SP="$(ls -d "$VENV"/lib/python3.*/site-packages)/nvidia"

[ -d "$SP" ] || { echo "no nvidia/ in $SP"; exit 1; }
mkdir -p "$CUDA/include" "$CUDA/lib"
ln -sfn lib "$CUDA/lib64"

# 끊어진 심볼릭 링크 정리 (venv 재생성 후)
find "$CUDA/include" "$CUDA/lib" -xtype l -delete 2>/dev/null || true

for d in cublas cusparse cusolver curand cufft nvtx cuda_runtime nvjitlink cudnn cuda_nvrtc; do
  for f in "$SP/$d"/include/*; do
    b="$(basename "$f")"; [ "$b" = "__init__.py" ] && continue
    [ -e "$CUDA/include/$b" ] || ln -s "$f" "$CUDA/include/$b"
  done
  for f in "$SP/$d"/lib/*.so*; do
    b="$(basename "$f")"
    [ -e "$CUDA/lib/$b" ] || ln -s "$f" "$CUDA/lib/$b"
  done
done

# 링커는 -lcusparse → libcusparse.so 를 찾는데 휠은 버전 붙은 .so.N 만 준다 → 비버전 심링크 생성
cd "$CUDA/lib"
for f in libcu*.so.* libcudnn*.so.* libnv*.so.*; do
  case "$f" in *.so.*.*) continue;; esac
  base="${f%%.so.*}"
  [ -e "$base.so" ] || ln -s "$f" "$base.so"
done

echo "CUDA_HOME=$CUDA  <-  $VENV"
echo "  headers: $(ls "$CUDA/include" | wc -l)   libs: $(ls "$CUDA/lib" | wc -l)"
