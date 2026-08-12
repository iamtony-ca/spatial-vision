#!/usr/bin/env bash
# 배경·재질 randomization 용 환경 자산을 내려받는다 (M2 확장 2단계).
#
#   bash envs/fetch_env_assets.sh            # 전부
#   bash envs/fetch_env_assets.sh hdri       # HDRI 만
#   bash envs/fetch_env_assets.sh ground     # 바닥 텍스처만
#
# 자산은 NVIDIA 가 Isaac Sim 용으로 공개한 것이고, `isaacsim.storage.native.get_assets_root_path()`
# 가 가리키는 공개 S3 버킷에서 **직접** 받는다. sdg_ws 에도 같은 풀이 있지만 **경로를 참조하지 않는다**
# (standalone 원칙 — 옆 워크스페이스가 없어도 재현돼야 한다).
#
# idempotent: 이미 있고 크기가 0 이 아니면 건너뛴다. 중단 후 재실행해도 된다.
#
# ⚠️ HDRI 15개 ≈ 350MB, 바닥 텍스처 50개 ≈ 410MB.
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0"
HDRI_DIR="assets/env/hdri"   # 카테고리별 하위 디렉토리로 내려간다(Clear/Cloudy/Evening/Indoor/Night)
GROUND_DIR="assets/env/ground"

# HDRI (dome light 배경) — NVIDIA Isaac Sim 자산, assets_root 하위 상대경로
HDRI=(
  "Clear/evening_road_01_4k.hdr|NVIDIA/Assets/Skies/Clear/evening_road_01_4k.hdr"
  "Clear/mealie_road_4k.hdr|NVIDIA/Assets/Skies/Clear/mealie_road_4k.hdr"
  "Clear/noon_grass_4k.hdr|NVIDIA/Assets/Skies/Clear/noon_grass_4k.hdr"
  "Clear/qwantani_4k.hdr|NVIDIA/Assets/Skies/Clear/qwantani_4k.hdr"
  "Clear/sunflowers_4k.hdr|NVIDIA/Assets/Skies/Clear/sunflowers_4k.hdr"
  "Cloudy/champagne_castle_1_4k.hdr|NVIDIA/Assets/Skies/Cloudy/champagne_castle_1_4k.hdr"
  "Cloudy/kloofendal_48d_partly_cloudy_4k.hdr|NVIDIA/Assets/Skies/Cloudy/kloofendal_48d_partly_cloudy_4k.hdr"
  "Evening/evening_road_01_4k.hdr|NVIDIA/Assets/Skies/Evening/evening_road_01_4k.hdr"
  "Indoor/autoshop_01_4k.hdr|NVIDIA/Assets/Skies/Indoor/autoshop_01_4k.hdr"
  "Indoor/carpentry_shop_01_4k.hdr|NVIDIA/Assets/Skies/Indoor/carpentry_shop_01_4k.hdr"
  "Indoor/hotel_room_4k.hdr|NVIDIA/Assets/Skies/Indoor/hotel_room_4k.hdr"
  "Indoor/studio_small_04_4k.hdr|NVIDIA/Assets/Skies/Indoor/studio_small_04_4k.hdr"
  "Indoor/wooden_lounge_4k.hdr|NVIDIA/Assets/Skies/Indoor/wooden_lounge_4k.hdr"
  "Night/kloppenheim_02_4k.hdr|NVIDIA/Assets/Skies/Night/kloppenheim_02_4k.hdr"
  "Night/moonlit_golf_4k.hdr|NVIDIA/Assets/Skies/Night/moonlit_golf_4k.hdr"
)

# 바닥 텍스처 (ground plane 재질)
GROUND=(
  "Ash_BaseColor.png|NVIDIA/Materials/Base/Wood/Ash/Ash_BaseColor.png"
  "Ash_Planks_BaseColor.png|NVIDIA/Materials/Base/Wood/Ash_Planks/Ash_Planks_BaseColor.png"
  "Bamboo_BaseColor.png|NVIDIA/Materials/Base/Wood/Bamboo/Bamboo_BaseColor.png"
  "Bamboo_Planks_BaseColor.png|NVIDIA/Materials/Base/Wood/Bamboo_Planks/Bamboo_Planks_BaseColor.png"
  "Birch_BaseColor.png|NVIDIA/Materials/Base/Wood/Birch/Birch_BaseColor.png"
  "Birch_Planks_BaseColor.png|NVIDIA/Materials/Base/Wood/Birch_Planks/Birch_Planks_BaseColor.png"
  "Cherry_BaseColor.png|NVIDIA/Materials/Base/Wood/Cherry/Cherry_BaseColor.png"
  "Cherry_Planks_BaseColor.png|NVIDIA/Materials/Base/Wood/Cherry_Planks/Cherry_Planks_BaseColor.png"
  "Cork_BaseColor.png|NVIDIA/Materials/Base/Wood/Cork/Cork_BaseColor.png"
  "Mahogany_baseColor.png|NVIDIA/Materials/Base/Wood/Mahogany/Mahogany_baseColor.png"
  "Mahogany_Planks_BaseColor.png|NVIDIA/Materials/Base/Wood/Mahogany_Planks/Mahogany_Planks_BaseColor.png"
  "Oak_BaseColor.png|NVIDIA/Materials/Base/Wood/Oak/Oak_BaseColor.png"
  "Oak_Planks_BaseColor.png|NVIDIA/Materials/Base/Wood/Oak_Planks/Oak_Planks_BaseColor.png"
  "Parquet_Floor_BaseColor.png|NVIDIA/Materials/Base/Wood/Parquet_Floor/Parquet_Floor_BaseColor.png"
  "Plywood_BaseColor.png|NVIDIA/Materials/Base/Wood/Plywood/Plywood_BaseColor.png"
  "Timber_BaseColor.png|NVIDIA/Materials/Base/Wood/Timber/Timber_BaseColor.png"
  "Timber_Cladding_BaseColor.png|NVIDIA/Materials/Base/Wood/Timber_Cladding/Timber_Cladding_BaseColor.png"
  "Walnut_BaseColor.png|NVIDIA/Materials/Base/Wood/Walnut/Walnut_BaseColor.png"
  "Walnut_Planks_BaseColor.png|NVIDIA/Materials/Base/Wood/Walnut_Planks/Walnut_Planks_BaseColor.png"
  "Adobe_Octagon_Dots_BaseColor.png|NVIDIA/Materials/Base/Stone/Adobe_Octagon_Dots/Adobe_Octagon_Dots_BaseColor.png"
  "Ceramic_Smooth_Fired_BaseColor.png|NVIDIA/Materials/Base/Stone/Ceramic_Smooth_Fired/Ceramic_Smooth_Fired_BaseColor.png"
  "Ceramic_Tile_12_BaseColor.png|NVIDIA/Materials/Base/Stone/Ceramic_Tile_12/Ceramic_Tile_12_BaseColor.png"
  "Ceramic_Tile_18_BaseColor.png|NVIDIA/Materials/Base/Stone/Ceramic_Tile_18/Ceramic_Tile_18_BaseColor.png"
  "Ceramic_Tile_6_BaseColor.png|NVIDIA/Materials/Base/Stone/Ceramic_Tile_6/Ceramic_Tile_6_BaseColor.png"
  "Fieldstone_BaseColor.png|NVIDIA/Materials/Base/Stone/Fieldstone/Fieldstone_BaseColor.png"
  "Granite_Dark_BaseColor.png|NVIDIA/Materials/Base/Stone/Granite_Dark/Granite_Dark_BaseColor.png"
  "Granite_Light_BaseColor.png|NVIDIA/Materials/Base/Stone/Granite_Light/Granite_Light_BaseColor.png"
  "Gravel_BaseColor.png|NVIDIA/Materials/Base/Stone/Gravel/Gravel_BaseColor.png"
  "Gravel_River_Rock_BaseColor.png|NVIDIA/Materials/Base/Stone/Gravel_River_Rock/Gravel_River_Rock_BaseColor.png"
  "Marble_BaseColor.png|NVIDIA/Materials/Base/Stone/Marble/Marble_BaseColor.png"
  "Marble_Smooth_BaseColor.png|NVIDIA/Materials/Base/Stone/Marble_Smooth/Marble_Smooth_BaseColor.png"
  "Marble_Tile_12_BaseColor.png|NVIDIA/Materials/Base/Stone/Marble_Tile_12/Marble_Tile_12_BaseColor.png"
  "Marble_Tile_18_BaseColor.png|NVIDIA/Materials/Base/Stone/Marble_Tile_18/Marble_Tile_18_BaseColor.png"
  "Pea_Gravel_BaseColor.png|NVIDIA/Materials/Base/Stone/Pea_Gravel/Pea_Gravel_BaseColor.png"
  "Porcelain_Smooth_BaseColor.png|NVIDIA/Materials/Base/Stone/Porcelain_Smooth/Porcelain_Smooth_BaseColor.png"
  "Porcelain_Tile_4_BaseColor.png|NVIDIA/Materials/Base/Stone/Porcelain_Tile_4/Porcelain_Tile_4_BaseColor.png"
  "Porcelain_Tile_4_Linen_BaseColor.png|NVIDIA/Materials/Base/Stone/Porcelain_Tile_4_Linen/Porcelain_Tile_4_Linen_BaseColor.png"
  "Porcelain_Tile_6_BaseColor.png|NVIDIA/Materials/Base/Stone/Porcelain_Tile_6/Porcelain_Tile_6_BaseColor.png"
  "Porcelain_Tile_6_Linen_BaseColor.png|NVIDIA/Materials/Base/Stone/Porcelain_Tile_6_Linen/Porcelain_Tile_6_Linen_BaseColor.png"
  "Retaining_Block_BaseColor.png|NVIDIA/Materials/Base/Stone/Retaining_Block/Retaining_Block_BaseColor.png"
  "Slate_Tile_BaseColor.png|NVIDIA/Materials/Base/Stone/Slate/Slate_Tile_BaseColor.png"
  "Stone_Wall_BaseColor.png|NVIDIA/Materials/Base/Stone/Stone_Wall/Stone_Wall_BaseColor.png"
  "Terracotta_BaseColor.png|NVIDIA/Materials/Base/Stone/Terracotta/Terracotta_BaseColor.png"
  "Terrazzo_BaseColor.png|NVIDIA/Materials/Base/Stone/Terrazzo/Terrazzo_BaseColor.png"
  "Adobe_Brick_BaseColor.png|NVIDIA/Materials/Base/Masonry/Adobe_Brick/Adobe_Brick_BaseColor.png"
  "Brick_Pavers_BaseColor.png|NVIDIA/Materials/Base/Masonry/Brick_Pavers/Brick_Pavers_BaseColor.png"
  "Brick_Wall_Brown_BaseColor.png|NVIDIA/Materials/Base/Masonry/Brick_Wall_Brown/Brick_Wall_Brown_BaseColor.png"
  "Brick_Wall_Red_BaseColor.png|NVIDIA/Materials/Base/Masonry/Brick_Wall_Red/Brick_Wall_Red_BaseColor.png"
  "textures_aggregate_exposed_diff.jpg|NVIDIA/Materials/vMaterials_2/Ground/textures/aggregate_exposed_diff.jpg"
  "textures_gravel_track_ballast_diff.jpg|NVIDIA/Materials/vMaterials_2/Ground/textures/gravel_track_ballast_diff.jpg"
)

fetch() {   # fetch <dst_dir> <"name|relpath"...>
    local dir="$1"; shift
    mkdir -p "$dir"
    local n_ok=0 n_skip=0 n_fail=0
    for entry in "$@"; do
        local name="${entry%%|*}" rel="${entry#*|}" dst
        dst="$dir/$name"
        mkdir -p "$(dirname "$dst")"
        if [ -s "$dst" ]; then n_skip=$((n_skip + 1)); continue; fi
        if curl -fsSL --retry 3 -o "$dst.part" "$ROOT/$rel"; then
            mv "$dst.part" "$dst"; n_ok=$((n_ok + 1))
            printf '  %-44s %8s\n' "$name" "$(du -h "$dst" | cut -f1)"
        else
            rm -f "$dst.part"; n_fail=$((n_fail + 1))
            echo "  ❌ $name  ($ROOT/$rel)"
        fi
    done
    echo "  → 신규 $n_ok · 기존 $n_skip · 실패 $n_fail   ($dir)"
    [ "$n_fail" -eq 0 ]
}

what="${1:-all}"
rc=0
if [ "$what" = all ] || [ "$what" = hdri ]; then
    echo "── HDRI → $HDRI_DIR"
    fetch "$HDRI_DIR" "${HDRI[@]}" || rc=1
fi
if [ "$what" = all ] || [ "$what" = ground ]; then
    echo "── 바닥 텍스처 → $GROUND_DIR"
    fetch "$GROUND_DIR" "${GROUND[@]}" || rc=1
fi
exit $rc
