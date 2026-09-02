set -u
cd /isaac-sim/volume/spatial_manipulation_ws/src/vision
source envs/env.sh >/dev/null 2>&1
OBJ=assets/obj/foup_300_semi_r2
CAM="--width 1920 --height 1200 --fx 727.5751343 --fy 727.5751343 --cx 960.99988 --cy 604.824219 --baseline-mm 120.201996"
# 🔴 씬 설정을 «전 거리 동일» 하게 고정한다 — 기존 6세트는 n_foup 이 1↔2 로 달라 거리와 섞여 있었다
SCENE="--distractors 4 --distractor-foups 2 --distractors-active 2 2 --occluders 3 --occluders-active 2 2"
MODEL=weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx
PROMPT="cube shaped sealed plastic wafer pod"
for Z in 0.30 0.40 0.45 0.50 0.55 0.60 0.70 0.85; do
  T=$(echo $Z | tr -d '.'); C=runs/S44L_$T
  LO=$(python3 -c "print(f'{$Z-0.03:.2f}')"); HI=$(python3 -c "print(f'{$Z+0.03:.2f}')")
  if [ ! -d "$C" ]; then
    /isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
      --out $C --frames 80 --seed 808 --distance-m $LO $HI --elevation-deg 40 80 \
      --body-appearance black $SCENE $CAM 2>&1 | tail -1
  fi
  echo "CAP $Z n=$(ls -d $C/frame_* 2>/dev/null|wc -l)"
done
echo CAPDONE
for Z in 0.30 0.40 0.45 0.50 0.55 0.60 0.70 0.85; do
  T=$(echo $Z | tr -d '.'); C=runs/S44L_$T
  [ -f runs/S44L_${T}_st/frame_0000/meta_stereo.json ] || \
    envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx --in $C \
      --out runs/S44L_${T}_st --scale 0.5 --model $MODEL 2>&1 | tail -1
  [ -f runs/S44L_${T}_seg/frame_0000/det.json ] || \
    envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 --in $C \
      --out runs/S44L_${T}_seg --target full --prompt "$PROMPT" --confidence 0.05 \
      --select center --select-score-frac 0.9 2>&1 | tail -1
  echo "ST/SEG $Z"
done
echo STDONE
for Z in 0.30 0.40 0.45 0.50 0.55 0.60 0.70 0.85; do
  T=$(echo $Z | tr -d '.')
  for R in 1 2; do
    O=runs/S44L_${T}_p$R; [ -f "$O/meta_pose.json" ] && continue
    envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/S44L_$T --out $O --obj $OBJ \
      --masks runs/S44L_${T}_seg --depth stereo --depth-dir runs/S44L_${T}_st \
      --primary full --flange-mask-from pose --input-scale 0.75 \
      --est-iter 5 --refine-iter 5 >/dev/null 2>&1 || echo "❌ $O"
  done
  echo "POSE $Z"
done
echo ALLDONE
