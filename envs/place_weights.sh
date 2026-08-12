#!/usr/bin/env bash
# envs/place_weights.sh — 내려받은 가중치를 각 리포가 기대하는 경로로 연결한다.
#
#   bash envs/place_weights.sh [<소스 디렉토리, 기본 weights/models>]
#
# 복사가 아니라 **심링크**다 (합계 ~25GB). 원본은 소스 디렉토리에 그대로 둔다.
# idempotent — 여러 번 돌려도 안전하다.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
SRC="$(cd "${1:-weights/models}" && pwd)"

link() {  # link <원본> <대상>
  [ -e "$1" ] || { echo "  건너뜀(원본 없음): $1"; return; }
  mkdir -p "$(dirname "$2")"
  ln -sfn "$1" "$2"
  echo "  $2  ->  ${1#$ROOT/}"
}

echo "== FoundationStereo =="
# ⚠️ 브라우저 중복 다운로드로 파일명이 '-001' 로 끝날 수 있다. repo 는 model_best_bp2.pth 를 찾는다.
FS="third_party/FoundationStereo/pretrained_models"
for tag in 23-51-11 11-33-40; do
  ck="$SRC/foundationstereo/$tag/model_best_bp2.pth"
  [ -f "$ck" ] || ck="$SRC/foundationstereo/$tag/model_best_bp2-001.pth"
  rm -f "$FS/$tag/model_best_bp2.pth" "$FS/$tag/cfg.yaml"
  link "$ck" "$FS/$tag/model_best_bp2.pth"
  link "$SRC/foundationstereo/$tag/cfg.yaml" "$FS/$tag/cfg.yaml"
done
link "$SRC/foundationstereo/onnx/foundation_stereo_23-51-11.onnx" "$FS/onnx/foundation_stereo_23-51-11.onnx"

echo "== FoundationPose =="
FP="third_party/FoundationPose/weights"
for tag in 2023-10-28-18-33-37 2024-01-11-20-02-45; do
  rm -f "$FP/$tag/model_best.pth" "$FP/$tag/config.yml"
  link "$SRC/foundationpose/$tag/model_best.pth" "$FP/$tag/model_best.pth"
  link "$SRC/foundationpose/$tag/config.yml" "$FP/$tag/config.yml"
done
if [ -d "$SRC/foundationpose_dataset" ]; then
  for d in "$SRC/foundationpose_dataset"/*/; do
    link "${d%/}" "third_party/FoundationPose/demo_data/$(basename "${d%/}")"
  done
fi

echo "== SAM 3 =="
# sam3 는 파일을 옮길 필요가 없다 — build_sam3_image_model(checkpoint_path=...) 로 로컬 경로를 직접 준다.
# 어댑터가 참조할 표준 위치만 만들어 둔다.
link "$SRC/sam3"   "weights/sam3"
link "$SRC/sam3.1" "weights/sam3.1"

echo
echo "검증: bash envs/check_weights.sh"
