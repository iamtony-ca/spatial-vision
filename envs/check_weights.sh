#!/usr/bin/env bash
# envs/check_weights.sh — 가중치가 각 리포가 기대하는 위치에 있는지 확인한다.
#
#   bash envs/check_weights.sh                   # 존재 + 크기 (빠르다, 기본)
#   bash envs/check_weights.sh --sha256          # weights/MANIFEST.sha256 대조 (~10.6G 해싱)
#   bash envs/check_weights.sh --write-manifest  # 지금 트리를 정본으로 매니페스트 생성
#
# 🔴 **크기 검사만으로는 부족하다.** `≥300MB` 식이라 **잘린 파일·다른 버전·다른 변형**을 통과시킨다.
#    새 머신에서는 게이트 걸린 6.6G 를 사람이 옮기므로(브라우저 재다운로드·중단·`-001` 접미사 등)
#    «같은 파일인가» 를 물을 수단이 필요하다 → 매니페스트.
#    ⚠️ 그래서 **매니페스트는 원본 트리가 살아있을 때 만들어야 한다.**
#
# 이 파일이 **13종 목록의 단일 정본**이다. 항목을 늘리면 매니페스트·fetch 안내가 함께 따라온다.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"; source envs/env.sh

MANIFEST="weights/MANIFEST.sha256"
MODE="size"
case "${1:-}" in
  --sha256)         MODE="sha256" ;;
  --write-manifest) MODE="write" ;;
  "")               ;;
  *) echo "알 수 없는 옵션: $1" >&2; sed -n '3,7p' "$0"; exit 2 ;;
esac

ok=0; miss=0; skip=0
FILES=()          # 매니페스트 대상 (설명이 아니라 «경로» 만 모은다)

# chk  <설명> <경로> <최소MB>   — 필수. 없으면 non-zero 종료
# chko <설명> <경로> <최소MB>   — 옵션. 없어도 성공이다
#   ⚠️ 옵션을 필수와 같이 세면 **정상 세팅이 «실패» 로 보인다** — 새 머신은 sam3.1 을
#      안 옮기는 게 기본이라 매번 걸린다(실측 2026-08-12).
_chk() {  # _chk <필수?> <설명> <경로> <최소MB>
  local req="$1" desc="$2" path="$3" min="$4" mb
  FILES+=("$path")
  if [ -f "$path" ]; then
    mb=$(( $(stat -Lc%s "$path") / 1048576 ))   # -L: 심링크는 대상 크기를 잰다
    if [ "$mb" -ge "$min" ]; then printf '  ✅ %-34s %s (%sMB)\n' "$desc" "$path" "$mb"; ok=$((ok+1)); return; fi
    printf '  ⚠️  %-34s %s — %sMB, %sMB 이상이어야 함(다운로드 실패?)\n' "$desc" "$path" "$mb" "$min"
  elif [ "$req" = 0 ]; then
    printf '  ⏭  %-34s %s — 없음 (옵션이라 넘어간다)\n' "$desc" "$path"; skip=$((skip+1)); return
  else
    printf '  ❌ %-34s %s — 없음\n' "$desc" "$path"
  fi
  [ "$req" = 1 ] && miss=$((miss+1)) || skip=$((skip+1))
}
chk()  { _chk 1 "$@"; }
chko() { _chk 0 "$@"; }

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
chko "sam3.1 ckpt(옵션)" weights/sam3.1/sam3.1_multiplex.pt 2000

echo "=== NGC FoundationStereo ONNX (상업 경로) ==="
chk "NGC dynamic onnx" weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx 300

echo
echo "확보 $ok / 누락·불완전 $miss$([ "$skip" -gt 0 ] && echo " / 옵션 건너뜀 $skip")"

# ── 매니페스트 생성 ───────────────────────────────────────────────────────────
if [ "$MODE" = "write" ]; then
  present=()
  for f in "${FILES[@]}"; do [ -f "$f" ] && present+=("$f"); done
  [ ${#present[@]} -gt 0 ] || { echo "❌ 해싱할 파일이 없다" >&2; exit 1; }
  echo
  echo "== sha256 계산 중 (${#present[@]}개, 수 GB — 1~2분) …"
  # -L 로 심링크를 따라 **내용**을 해싱한다. 경로는 ROOT 기준 상대경로.
  sha256sum "${present[@]}" > "$MANIFEST.tmp"
  mv "$MANIFEST.tmp" "$MANIFEST"
  echo "✅ $MANIFEST  (${#present[@]}개)"
  [ "$miss" = 0 ] || echo "⚠️  누락 $miss 건은 매니페스트에 없다 — 완전한 트리에서 다시 만들 것"
  exit 0
fi

# ── 매니페스트 대조 ───────────────────────────────────────────────────────────
if [ "$MODE" = "sha256" ]; then
  [ -f "$MANIFEST" ] || { echo "❌ $MANIFEST 가 없다 — 원본 트리에서 --write-manifest 로 만든다" >&2; exit 1; }
  total=$(grep -vc '^\s*$' "$MANIFEST")
  echo
  echo "== sha256 대조 ($MANIFEST, $total개) …"
  # --ignore-missing: 옵션 항목(sam3.1)이 없는 머신도 통과시킨다.
  # 🔴 그런데 «전부 없어서 0개 검사» 가 성공으로 보이면 안 되므로 **검사 건수를 세서 확인**한다.
  out="$(sha256sum -c --ignore-missing "$MANIFEST" 2>&1)" || rc=$? ; rc=${rc:-0}
  echo "$out" | grep -v ': OK$' || true
  checked=$(echo "$out" | grep -c ': OK$' || true)
  bad=$(echo "$out" | grep -c ': FAILED' || true)
  echo "  대조 $checked / 매니페스트 $total · 불일치 $bad"
  if [ "$bad" != 0 ]; then
    echo "🔴 내용이 다르다 — 잘린 파일이거나 다른 버전이다. 크기 검사는 이걸 못 잡는다." >&2; exit 1
  fi
  if [ "$checked" -lt "$total" ]; then
    echo "⚠️  $((total - checked))개는 파일이 없어 대조하지 못했다(위 존재 검사 참조)."
  fi
  [ "$miss" = 0 ] || exit 1
  echo "✅ 전부 일치"
  exit 0
fi

[ "$miss" = 0 ] || exit 1
