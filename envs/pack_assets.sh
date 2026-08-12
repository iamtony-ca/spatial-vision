#!/usr/bin/env bash
# envs/pack_assets.sh — 생성된 3D 자산을 **GitHub Release 용 tarball** 로 묶는다.
#
#   bash envs/pack_assets.sh                       # 기본 자산(foup_300_semi_r2)
#   bash envs/pack_assets.sh foup_300_semi_r2 foup_300_semi_spec15
#   bash envs/pack_assets.sh --list                # 담을 파일만 보고 끝
#   bash envs/pack_assets.sh --check dist/xxx.tar.gz   # 받은 파일 무결성 확인
#
# 왜 Release 인가 (LFS 도 아니고 git 본체도 아닌 이유)
#   자산 196MB 는 GitHub 에 **LFS 없이 올라간다**(단일 파일 최대 14.7MB, 한계 100MiB).
#   그런데 **크기가 기준이 아니다** — git 은 히스토리를 영구 보존하고 PNG·PLY 는 델타가 안 먹는다.
#   이 프로젝트는 자산이 이미 네 번 바뀌었고(`semi → spec → spec15 → r2`), 바뀔 때마다
#   **`sam3_refs`·`ism_full` 을 재생성해야 한다**(교훈 #40). git 에 넣으면 매번 ~170MB 가
#   히스토리에 영구히 쌓이고 되돌릴 수 없다.
#   **Release 는 히스토리 밖**이고 파일당 2GB 까지이며 **옛 릴리스를 지우면 용량이 실제로 회수**된다.
#
# 무엇을 담나 — **`.gitignore` 경계와 정확히 같다**
#   담는다:   *.ply · mesh.usda · views.png · ism_full/ · sam3_refs_*/   (재생성 가능·무겁다)
#   안 담는다: source.json · meta*.json · keypoints.json · sam3_prompts.json · semi_check.json
#             → 이건 **git 이 버전 관리하는 «재생성의 씨앗»** 이다. tarball 에 넣으면
#               풀 때 추적 중인 파일을 덮어써서 «어느 쪽이 정본인가» 가 흐려진다.
#
# 🔴 실물 캡처(`runs/real*`)는 여기 담지 않는다 — 세션마다 늘어나는 데이터라 **HF dataset** 이 맞다.
#    릴리스로 관리하면 태그가 수십 개가 되고 부분 다운로드도 안 된다.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

OUT="dist"
MODE="pack"
IDS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --list)  MODE="list"; shift ;;
    --check) MODE="check"; TARBALL="${2:?--check <tarball>}"; shift 2 ;;
    --out)   OUT="${2:?--out <dir>}"; shift 2 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    -*) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
    *)  IDS+=("$1"); shift ;;
  esac
done
[ ${#IDS[@]} -gt 0 ] || IDS=(foup_300_semi_r2)

if [ "$MODE" = "check" ]; then
  [ -f "$TARBALL.sha256" ] || { echo "❌ $TARBALL.sha256 가 없다" >&2; exit 1; }
  ( cd "$(dirname "$TARBALL")" && sha256sum -c "$(basename "$TARBALL").sha256" )
  echo "✅ 무결성 확인"
  exit 0
fi

# git 이 버전 관리하는 «씨앗» — tarball 에서 제외한다 (최상위 depth 1 만)
SEEDS=(source.json 'meta*.json' keypoints.json sam3_prompts.json semi_check.json)

mkdir -p "$OUT"
for id in "${IDS[@]}"; do
  d="assets/obj/$id"
  [ -d "$d" ] || { echo "❌ 없는 자산: $d" >&2; exit 1; }

  # 담을 목록 = 디렉토리 최상위 항목 중 «씨앗» 이 아닌 것 (하위는 통째로 따라간다)
  list=()
  while IFS= read -r p; do
    n="$(basename "$p")"
    skip=0
    for s in "${SEEDS[@]}"; do
      # shellcheck disable=SC2053
      [[ "$n" == $s ]] && { skip=1; break; }
    done
    [ "$skip" = 1 ] || list+=("$id/$n")
  done < <(find "$d" -mindepth 1 -maxdepth 1 | sort)

  [ ${#list[@]} -gt 0 ] || { echo "❌ $id: 담을 게 없다" >&2; exit 1; }

  if [ "$MODE" = "list" ]; then
    echo "== $id — 담을 항목 ${#list[@]}개"
    for p in "${list[@]}"; do printf '  %8s  %s\n' "$(du -sh "assets/obj/$p" | cut -f1)" "$p"; done
    echo "   제외(git 이 관리): $(printf '%s ' "${SEEDS[@]}")"
    continue
  fi

  tgz="$OUT/${id}_assets.tar.gz"
  echo "== $id → $tgz"
  # --sort=name: 같은 입력이면 항목 순서가 고정된다(파일 mtime 이 바뀌면 해시는 바뀐다 —
  #              이 sha256 은 «내용 동일성» 이 아니라 «전송 무결성» 용이다)
  tar --sort=name -C assets/obj -czf "$tgz" "${list[@]}"
  ( cd "$OUT" && sha256sum "$(basename "$tgz")" > "$(basename "$tgz").sha256" )
  printf '   %s  (원본 %s)\n' "$(du -h "$tgz" | cut -f1)" "$(du -sh "$d" | cut -f1)"
  echo "   $(cat "$tgz.sha256")"
done

[ "$MODE" = "list" ] && exit 0

cat <<EOF

다음 — GitHub Release 에 올린다 (\`gh\` 가 있는 곳에서):
  gh release create assets-<태그> $OUT/*.tar.gz $OUT/*.sha256 \\
      --title "자산 <태그>" --notes "obj: ${IDS[*]}"

새 머신에서:
  gh release download assets-<태그> --dir $OUT
  bash envs/pack_assets.sh --check $OUT/${IDS[0]}_assets.tar.gz
  tar -C assets/obj -xzf $OUT/${IDS[0]}_assets.tar.gz

⚠️ 자산을 재생성했으면 **새 태그**를 만든다. 옛 태그를 지우면 용량이 실제로 회수된다.
⚠️ 자산이 바뀌면 \`sam3_refs\`·\`ism_full\` 도 같이 재생성돼 있어야 한다 (교훈 #40).
EOF
