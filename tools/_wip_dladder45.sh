set -u
cd /isaac-sim/volume/spatial_manipulation_ws/src/vision
source envs/env.sh >/dev/null 2>&1
OBJ=assets/obj/foup_300_semi_r2
CAM="--width 1920 --height 1200 --fx 727.5751343 --fy 727.5751343 --cx 960.99988 --cy 604.824219 --baseline-mm 120.201996"
# 🔴 단일 FOUP — distractor-foups 0. 비FOUP 잡동사니·가림막은 유지한다.
SCENE="--distractors 4 --distractor-foups 0 --distractors-active 2 2 --occluders 3 --occluders-active 2 2"
# ★ 고쳐진 것 둘: ① flange 를 검정 고정색으로 칠한다  ② 배경·조명·바닥 randomization 을 켠다
#   🔴 조명 설정은 **`RESULTS.md:173` 의 검증된 APP 를 그대로** 쓴다. 직접 만든 밴드로는
#      flange 가 갈색(92~122)으로 떴고 전체 HDRI 세트는 야외 주광이 화면을 포화시켰다(66~232).
#      🔴 다만 그 설정은 `--light-fixtures-active 0 2` 라 **조명 0개 프레임**이 나와 새까맸다(3/6).
#      최종: 조명 하한을 2로 올리고 세기·dome 밴드를 좁혔다 → **어두운 프레임 0/10**,
#      씬 밝기 116~237 · flange 중앙 146 · body 136. flange roughness 는 **기본 0.45**(사용자 선택 ②).
FIX="--flange-color 0.03 0.03 0.03"
RAND="--hdri assets/env/hdri/Indoor --ground-material --ground-textures assets/env/ground \
      --light-fixtures 4 --light-fixtures-active 2 4 --fixture-intensity 900 3000 \
      --dome-intensity 150 260 --color-temperature-k 3000 5500"
MODEL=weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx
PROMPT="cube shaped sealed plastic wafer pod"
ZS="0.30 0.40 0.50 0.60 0.70 0.80"
for APP in black; do   # 🔴 black 만 — 나머지 색은 결과 보고 결정 (사용자 방침 2026-09-03)
  P=$(echo $APP | cut -c1 | tr a-z A-Z)          # B / O / C
  for Z in $ZS; do
    T=$(echo $Z | tr -d '.'); C=runs/S45${P}_$T
    LO=$(python3 -c "print(f'{$Z-0.03:.2f}')"); HI=$(python3 -c "print(f'{$Z+0.03:.2f}')")
    if [ ! -f "$C/frame_0049/pose_gt.json" ]; then
      /isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
        --out $C --frames 50 --seed 909 --distance-m $LO $HI --elevation-deg 40 80 \
        --body-appearance $APP $FIX $SCENE $RAND $CAM >/dev/null 2>&1
    fi
    echo "CAP $APP $Z n=$(ls -d $C/frame_* 2>/dev/null|wc -l)"
  done
  for Z in $ZS; do
    T=$(echo $Z | tr -d '.'); C=runs/S45${P}_$T
    [ -f runs/S45${P}_${T}_st/frame_0000/meta_stereo.json ] || \
      envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx --in $C \
        --out runs/S45${P}_${T}_st --scale 0.5 --model $MODEL >/dev/null 2>&1
    # 🔴 score_frac 은 0.9 유지 (사용자 방침 — real 에서 검증 후 결정)
    [ -f runs/S45${P}_${T}_seg/frame_0000/det_full.json ] || \
      envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 --in $C \
        --out runs/S45${P}_${T}_seg --target full --prompt "$PROMPT" --confidence 0.05 \
        --select center --select-score-frac 0.9 >/dev/null 2>&1
  done
  echo "STSEG $APP done"
  for Z in $ZS; do
    T=$(echo $Z | tr -d '.')
    for R in 1 2; do
      O=runs/S45${P}_${T}_p$R; [ -f "$O/meta_pose.json" ] && continue
      envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/S45${P}_$T --out $O --obj $OBJ \
        --masks runs/S45${P}_${T}_seg --depth stereo --depth-dir runs/S45${P}_${T}_st \
        --primary full --flange-mask-from pose --input-scale 0.75 \
        --est-iter 5 --refine-iter 5 >/dev/null 2>&1 || echo "❌ $O"
    done
  done
  echo "DONE $APP"
done
echo ALLDONE
