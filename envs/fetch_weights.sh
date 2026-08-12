#!/usr/bin/env bash
# envs/fetch_weights.sh — 자동으로 받을 수 있는 가중치를 전부 받고, **못 받는 것은 안내하고 실패**한다.
#
#   bash envs/fetch_weights.sh            # 전부 (자동 가능한 것)
#   bash envs/fetch_weights.sh ngc        # 부분: ngc | ism | sam3
#   bash envs/fetch_weights.sh --manual   # 수동 3건의 출처만 출력
#
# 🔴 **13종이 다 자동은 아니다.** 라이선스 게이트가 걸린 것은 사람이 동의해야 받을 수 있고,
#    그게 정확히 «HF 공개 미러를 만들 수 없는» 것들이기도 하다(`docs/LICENSES.md §1·§2`).
#
#   ✅ 자동  NGC ONNX(331M) · SAM vit_h(2.4G) · DINOv2(1.2G)          — 공개 URL, 동의 불필요
#   🔑 반자동 SAM 3(3.3G)                                             — HF 게이트, `HF_TOKEN` 필요
#   🔴 수동  FoundationStereo(3.1G) · FoundationPose(248M)            — Google Drive **폴더**
#
# idempotent: 이미 있고 크기가 맞으면 건너뛴다. 중단 후 다시 돌려도 된다.
# 검증은 `bash envs/check_weights.sh` (크기) / `--sha256` (내용).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"; source envs/env.sh

ISM=third_party/SAM-6D/SAM-6D/Instance_Segmentation_Model
NGC=https://api.ngc.nvidia.com/v2/models/nvidia/tao/foundationstereo/versions
SAM3_REPO="${SAM3_REPO:-facebook/sam3}"   # 게이트 리포. 다르면 환경변수로 덮어쓴다

have() {  # have <경로> <최소MB> — 이미 온전히 있으면 0
  [ -f "$1" ] && [ "$(( $(stat -Lc%s "$1") / 1048576 ))" -ge "$2" ]
}

get() {  # get <url> <출력> <최소MB> <설명>
  if have "$2" "$3"; then echo "  건너뜀(이미 있음): $2"; return; fi
  echo "  ↓ $4"
  mkdir -p "$(dirname "$2")"
  # -C - 로 이어받는다. 실패하면 **부분 파일을 남기지 않는다** — 다음 실행이
  # «있는데 작은» 상태를 보고 헷갈리지 않도록.
  curl -fL --retry 3 -C - -o "$2.part" "$1" || { rm -f "$2.part"; echo "  ❌ 실패: $4" >&2; return 1; }
  mv "$2.part" "$2"
  printf '  ✅ %s (%sMB)\n' "$2" "$(( $(stat -Lc%s "$2") / 1048576 ))"
}

manual_note() {
  cat <<'EOF'

🔴 아래 2건은 **자동으로 못 받는다** — NVlabs 가 Google Drive «폴더» 로 배포하고
   NVIDIA Source Code License(research purposes only) 동의가 전제다.

  FoundationStereo  23-51-11/{model_best_bp2.pth, cfg.yaml}            3.1G
      https://drive.google.com/drive/folders/1VhPebc_mMxWKccrv7pdQLTvXYVcLYpsf
      → weights/models/foundationstereo/23-51-11/ 에 폴더째 넣는다

  FoundationPose    2023-10-28-18-33-37/ (refiner) · 2024-01-11-20-02-45/ (scorer)   248M
      https://drive.google.com/drive/folders/1DFezOAD0oD1BblsXVxqDsl8fj0qzB82i
      → weights/models/foundationpose/ 에 두 폴더를 넣는다

  ⚠️ 브라우저가 중복 다운로드로 `model_best_bp2-001.pth` 처럼 저장하는 일이 흔하다.
     `place_weights.sh` 가 그 이름도 찾아 주지만, **크기와 sha256 을 반드시 확인**할 것.

  넣은 뒤:  bash envs/place_weights.sh && bash envs/check_weights.sh --sha256

  ⚠️ 옛 머신이 있으면 받지 말고 그냥 복사하는 게 빠르다 (`docs/SETUP.md §0.1b`).
EOF
}

WHAT="${1:-all}"
[ "$WHAT" = "--manual" ] && { manual_note; exit 0; }

if [ "$WHAT" = all ] || [ "$WHAT" = ngc ]; then
  echo "== NGC FoundationStereo ONNX (NVIDIA Open Model License — 상업 가능)"
  f=deployable_foundation_stereo_s_dynamic_v2.0.onnx
  get "$NGC/deployable_foundation_stereo_s_dynamic_v2.0/files/$f" \
      "weights/ngc_foundationstereo/$f" 300 "$f"
fi

if [ "$WHAT" = all ] || [ "$WHAT" = ism ]; then
  # 🔴 이 둘은 **clone 에 안 들어 있다** — third_party 안에 나중에 내려받아 두는 파일이고
  #    place_weights.sh 도 다루지 않는다. bootstrap 만 돌리면 13종 중 2종이 빈다.
  echo "== SAM-6D ISM 체크포인트 (Apache 2.0 — 공개 URL)"
  get "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth" \
      "$ISM/checkpoints/segment-anything/sam_vit_h_4b8939.pth" 2000 "SAM vit_h (2.4G)"
  get "https://dl.fbaipublicfiles.com/dinov2/dinov2_vitl14/dinov2_vitl14_pretrain.pth" \
      "$ISM/checkpoints/dinov2/dinov2_vitl14_pretrain.pth" 500 "DINOv2 vitl14 (1.2G)"
fi

if [ "$WHAT" = all ] || [ "$WHAT" = sam3 ]; then
  echo "== SAM 3 (Meta 게이트 — 라이선스 동의 후 HF 토큰 필요)"
  if have weights/models/sam3/sam3.pt 2000; then
    echo "  건너뜀(이미 있음): weights/models/sam3/sam3.pt"
  elif [ -z "${HF_TOKEN:-}" ]; then
    cat <<EOF
  🔑 HF_TOKEN 이 없다. SAM 3 는 Meta 가 게이트한 리포다:
       1) https://huggingface.co/$SAM3_REPO 에서 라이선스에 동의한다
       2) https://huggingface.co/settings/tokens 에서 read 토큰을 만든다
       3) export HF_TOKEN=hf_xxx  하고 다시 실행
     (리포 이름이 다르면 SAM3_REPO=<org/name> 으로 덮어쓴다)
EOF
  else
    # transformers 포맷 리포에서 **우리가 쓰는 파일만** 받는다.
    # ⚠️ model.safetensors(3.3G)는 sam3.pt 와 같은 가중치의 다른 포맷이라 받지 않는다.
    B="https://huggingface.co/$SAM3_REPO/resolve/main"
    mkdir -p weights/models/sam3
    for f in sam3.pt config.json tokenizer.json tokenizer_config.json \
             special_tokens_map.json vocab.json merges.txt processor_config.json; do
      o="weights/models/sam3/$f"
      [ -f "$o" ] && { echo "  건너뜀: $o"; continue; }
      echo "  ↓ $f"
      curl -fL --retry 3 -H "Authorization: Bearer $HF_TOKEN" -o "$o.part" "$B/$f" \
        && mv "$o.part" "$o" \
        || { rm -f "$o.part"; echo "  ⚠️  $f 실패 (필수는 sam3.pt·config.json·tokenizer.json)" >&2; }
    done
  fi
fi

echo
echo "== 연결 + 검증"
echo "  bash envs/place_weights.sh"
echo "  bash envs/check_weights.sh            # 존재·크기"
echo "  bash envs/check_weights.sh --sha256   # 내용 (매니페스트 필요)"
manual_note
