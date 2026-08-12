#!/usr/bin/env bash
# envs/check_weights.sh — 가중치가 각 리포가 기대하는 위치에 있는지 확인한다.
#   bash envs/check_weights.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"; source envs/env.sh

ok=0; miss=0
chk() {  # chk <설명> <경로> <최소MB>
  if [ -f "$2" ]; then
    mb=$(( $(stat -Lc%s "$2") / 1048576 ))   # -L: 심링크는 대상 크기를 잰다
    if [ "$mb" -ge "$3" ]; then printf '  ✅ %-34s %s (%sMB)\n' "$1" "$2" "$mb"; ok=$((ok+1))
    else printf '  ⚠️  %-34s %s — %sMB, %sMB 이상이어야 함(다운로드 실패?)\n' "$1" "$2" "$mb" "$3"; miss=$((miss+1)); fi
  else printf '  ❌ %-34s %s — 없음\n' "$1" "$2"; miss=$((miss+1)); fi
}

echo "=== FoundationStereo ==="
chk "stereo ckpt (23-51-11)" third_party/FoundationStereo/pretrained_models/23-51-11/model_best_bp2.pth 300
chk "stereo cfg   (23-51-11)" third_party/FoundationStereo/pretrained_models/23-51-11/cfg.yaml 0

echo "=== FoundationPose ==="
chk "refiner ckpt" third_party/FoundationPose/weights/2023-10-28-18-33-37/model_best.pth 50   # 17.0M params ≈ 65MB
chk "refiner cfg"  third_party/FoundationPose/weights/2023-10-28-18-33-37/config.yml 0
chk "scorer ckpt"  third_party/FoundationPose/weights/2024-01-11-20-02-45/model_best.pth 100
chk "scorer cfg"   third_party/FoundationPose/weights/2024-01-11-20-02-45/config.yml 0

echo "=== SAM-6D ISM ==="
ISM=third_party/SAM-6D/SAM-6D/Instance_Segmentation_Model
chk "SAM vit_h"      $ISM/checkpoints/segment-anything/sam_vit_h_4b8939.pth 2000
chk "DINOv2 vitl14"  $ISM/checkpoints/dinov2/dinov2_vitl14_pretrain.pth 500

echo "=== SAM 3 ==="
chk "sam3 ckpt"        weights/sam3/sam3.pt 2000
chk "sam3 config"      weights/sam3/config.json 0
chk "sam3 tokenizer"   weights/sam3/tokenizer.json 0
chk "sam3.1 ckpt(옵션)" weights/sam3.1/sam3.1_multiplex.pt 2000

echo "=== NGC FoundationStereo ONNX (상업 경로) ==="
chk "NGC dynamic onnx" weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx 300

echo
echo "확보 $ok / 누락·불완전 $miss"
[ "$miss" = 0 ] || exit 1
