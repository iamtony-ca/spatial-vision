# §44-23d 기전 검정 — 사다리 «양 끝» 에 `--input-scale 0.5`(= RH2) 를 추가로 돌린다.
# §38-10 이 참이면(전처리 반경이 물리 크기로 커진다) **멀수록 RH1−RH2 차이가 커야** 한다.
# 사다리(_p1/_p2, scale 0.75 = RH1)와 **같은 stereo/seg 를 공유**하므로 pose 만 더 돌리면 된다. 멱등.
set -u
cd /isaac-sim/volume/spatial_manipulation_ws/src/vision
source envs/env.sh >/dev/null 2>&1
OBJ=assets/obj/foup_300_semi_r2
for T in 030 085; do
  for R in 1 2; do
    O=runs/S44L_${T}_q$R; [ -f "$O/meta_pose.json" ] && { echo "SKIP $O"; continue; }
    envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/S44L_$T --out $O --obj $OBJ \
      --masks runs/S44L_${T}_seg --depth stereo --depth-dir runs/S44L_${T}_st \
      --primary full --flange-mask-from pose --input-scale 0.5 \
      --est-iter 5 --refine-iter 5 >/dev/null 2>&1 || echo "❌ $O"
    echo "Q $O n=$(ls -d $O/frame_*/pose_refined.json 2>/dev/null|wc -l)"
  done
done
echo Q_ALLDONE
