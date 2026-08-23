# RESULTS.md — 단계별 실행 결과 기록

이 문서가 **측정된 사실의 정본**이다. 계획·설계 의도는 `PIPELINE_PLAN.md`, 라이선스는 `LICENSES.md`,
배경 요구사항은 `CONSUMER_6DPOSE.md` 에 있다. 수치를 옮겨 적지 말고 여기만 갱신한다(두 곳에 적으면 갈라진다).

## 문서 지도

| 문서 | 내용 | 언제 |
|---|---|---|
| `PIPELINE_PLAN.md` | 아키텍처·데이터 계약·원점 규약·마일스톤 계획 | 설계를 바꿀 때 |
| **`RESULTS.md`** (이 문서) | **단계별 실행 결과·검증 수치·재현 명령·함정** | "이건 얼마나 잘 되나 / 왜 이렇게 됐나" |
| `LICENSES.md` | 구성요소별 라이선스, 상업화 경로 | 모델·코드 도입 전 |
| `CONSUMER_6DPOSE.md` | 연구과제 배경, 실환경 관측, SDG 되먹임 | 요구사항 근거 |

## ★ KPI (2026-08-07 확정)

| 지표 | 기준 |
|---|---|
| Translation error | **≤ 5mm** |
| Rotation error | **≤ 3°** |

**KPI 를 만족하는 조합을 찾았다** (40프레임, 검출 실패·오선택·KPI 미달을 **전부 실패**로 셈):

| 조합 | 마스크 | 끝단 성공률 |
|---|---|---|
| **fx 952 @1280×720, 거리 0.8~1.2m, baseline 120mm** | **ISM + select center** | **40/40 = 100%** |
| fx 1200, 거리 0.8~1.2m (동일 씬) | ISM + select center | 40/40 = 100% |
| **fx 952, 거리 0.8~1.2m** | SAM3 exemplar 참조 3장 | 38/40 = 95% |
| fx 1400, 거리 0.8~1.2m | ISM + select center | 38/40 = 95% |
| 기준(거리 1.0~2.0m, 텍스트 프롬프트) | SAM3 텍스트 + center | 28/40 = 70% |

🔴🔴 **위 표와 아래 «실제 카메라 요건» 은 옛 sim 기하(fx 952~1200 @1280×720)다.**
**카메라가 ZED X 2.2mm 로 확정**되면서 실측 intrinsic(`fx 727.575 @1920×1200 · B 120.202`)으로
전 체인을 다시 냈고, **거리대·후보 순위·배포 구성이 전부 바뀌었다** → **`§34` 가 현행 정본**이다.
이 절(§1~§33)은 **그 결론에 이르는 경위**로 읽을 것.

옛 요건(참고): ZED 계열(baseline ~120mm), 1280×720, HFOV ~69°, 작업거리 0.8~1.2m.
RealSense D435(baseline 50mm)는 2m 이내로 제한해도 **KPI 57%** 로 부족하다 — §M2 확장 §5.
카메라 비교 정본은 **`docs/CAMERAS.md`**.

**운용 제약은 flange 기준이다** — "FOUP 전체가 FOV 에" 는 요건이 아니다(잘려도 정확도가 떨어지지 않는다).
필요한 것은 **flange 가 온전히 보이고 투영 면적 ≥4,000px** 이다. 근접 하한은 fx1200 에서 **0.35m** — §M5 확장 §3·6.

**★ 더 좋은 조합이 있다 — 근접에서 flange 로 다시 추정한다** (2026-08-08, 이전 결론 정정):
`0.35~0.49m` 에서 **`top_flange.ply` 단독**으로 추정하면 **R 0.536° / t 0.70mm / 40/40** 으로
원거리 단일(1.85mm)보다 **t 가 2.6배 좋다**. 성립 조건은 **실내 조명 · 검정 flange · flange 마스크 IoU ≥0.98**.
초기값 전달은 필요 없다(오히려 나쁘다). 근접에서 **full CAD 를 쓰면 안 된다**(FOV 이탈, KPI 50%).
원거리에서만 찍어야 한다면 **하이브리드(R=coarse, t=refine)** 가 t 1.18mm 로 최선.
→ `§근접 pose 재실험`.

⚠️ **통계적 한계**: 무결점 n=40 의 실패율 95% 상한은 **7.5%** 다. "95% 이상일 가능성이 높다" 까지가
정직한 표현이고, 95% 확정에는 60프레임, **99% 에는 300프레임** 무결점이 필요하다.

⚠️ **여전히 sim→sim 이다** — 다만 **배경(HDRI)·재질 축은 이제 측정됐다**: 같은 조합이
randomization 하에서도 **40/40 유지**(§배경·재질 randomization). 남은 축은 센서 특성과 실사진이다.
SAM3 exemplar 는 **참조를 배포 조건에서 다시 만들어야** 유지된다(안 하면 IoU 0.872 → 0.382).

## 진행 상태

| | 단계 | 상태 | 한 줄 결과 |
|---|---|---|---|
| M0 | 런타임 격리 + 리포/가중치 | ✅ | venv 6종(python 3.12) sm_120 동작, 가중치 13/13, FoundationPose 데모 737프레임 통과 |
| M1 | CAD 준비 | ✅ | **신 CAD**: solid 28개 → flange 1 / wafer 25 / 기타 2, 웨이퍼 ø300×25 체크섬 통과, 두 메쉬 거리 **0.000000mm**, keypoint 이탈 0.0000mm |
| M2 | Isaac 스테레오 rig 캡처 | ✅ | rectification **0.000000° / −120.0000mm**, pose↔depth 오차 **0.000mm** |
| M3 | Depth (백엔드 2종) | ✅ | **신 CAD**: flange_core MAE **3.403mm**(research) / **3.855mm**(상업 경로). 구 CAD 는 1.885/2.812 — 객체·프레임이 달라 직접 비교 불가 |
| M4 | Segmentation | ✅ | **distractor 하에서**: ISM+center IoU **0.936 오선택 0/40**, SAM3 **exemplar** 0.870. 텍스트 프롬프트는 오선택 45% — §M2 확장 |
| ★ | **신 CAD 전환** | ✅ | `300mm_SEMI_FOUP.step` 로 교체. flange 가 **별도 solid**, 웨이퍼 ø300×25 로 단위 검증. M1~M4 재실행 |
| M5 | Pose 2-stage | ✅ | **끝단 40/40 = 100%**(ISM+center, 거리 0.8~1.2m). stage-2 단독은 회전을 3.7배 악화 → 실사용은 **coarse** |
| ★ | **M2 확장(randomizer/distractor)** | ✅ | 조명·방해물·가림 도입, 40×N 프레임. **M4·M5 결론 다수가 여기서 뒤집혔다** |
| ★ | **M5 확장(근접·2단계·flange 전용)** | ✅ | 다단계 pose **기각**. 측면 오차는 해상도 한계가 아님, FOV 요건은 flange 기준 |
| ★★ | **배경·재질 randomization** | ✅ | HDRI 14 + 바닥 50 + 몸체 PBR(**flange 고정**). ISM 경로 **40/40 유지**, SAM3 는 참조 재생성 필요 |
| ★★★ | **근접 pose 재실험** | ✅ | 실내조명 + **검정 flange** 로 **다단계 기각 결론이 뒤집혔다**. 근접 flange 단독 **t 0.70mm** (원거리 1.85mm) |
| M6 | 실환경 | 🟡 | **카메라 확정**(ZED X 2.2mm, §34) · **실물 촬영 완료**(28/40/50cm, 검정 몸체) · 실측 형상 3축 확인(§36) · 러너·리포트·판단 그림 상설화(§35). **남은 것은 실물 데이터 해석과 재촬영**. 🔴 **로봇이 없다** — 촬영 1회 파이프라인만 가능(§35-2m·`PIPELINE_CATALOG §9.1★c`) |

## 재현 (전체)

현행 객체는 **`foup_300_semi`** (소스 `assets/cad/300mm_foup/300mm_SEMI_FOUP.step`). 구 `foup_300` 은
비교 근거로만 남아 있고 **소스 CAD 가 없어 재생성 불가**다 — §신 CAD 전환 참조.

```bash
cd /isaac-sim/volume/spatial_manipulation_ws/src/vision
bash envs/bootstrap.sh                      # M0: venv·CUDA·리포·BlenderProc
bash envs/place_weights.sh                  # 가중치 심링크 (weights/models/ 필요)
bash envs/verify.sh && bash envs/check_weights.sh

source envs/env.sh
OBJ=assets/obj/foup_300_semi
envs/cad/bin/python -m spatial_vision.cad.prepare_obj --config $OBJ/source.json                  # M1
envs/cad/bin/python -m spatial_vision.cad.verify_obj  --obj $OBJ
envs/cad/bin/python -m spatial_vision.cad.build_usd   --obj $OBJ

/isaac-sim/python.sh -m spatial_vision.stages.capture_sim \                                      # M2
    --obj-usd $OBJ/mesh.usda --out runs/semi01 --frames 4
envs/stereo_onnx/bin/python -m spatial_vision.eval.verify_stereo --in runs/semi01 --keypoints $OBJ/keypoints.json

envs/stereo/bin/python      -m spatial_vision.stages.stereo_torch --in runs/semi01 --out runs/semi01_torch   # M3
envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx  --in runs/semi01 --out runs/semi01_onnx_s075 \
    --scale 0.75 --model weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx
envs/stereo_onnx/bin/python -m spatial_vision.eval.eval_depth --gt runs/semi01 \
    --pred runs/semi01_torch runs/semi01_onnx_s075 --out runs/semi_m3_metrics.json

# M4 — CAD 템플릿 렌더(타깃별 1회, ISM 전용) → segmentation 2종 → 평가
( cd third_party/SAM-6D/SAM-6D/Render                                                            # M4
  for t in full:full.ply flange:top_flange.ply; do
    "$VISION_ROOT/envs/seg_sam6d/bin/blenderproc" run --blender-install-path "$VISION_ROOT/envs/blender" \
      render_custom_templates.py --cad_path "$VISION_ROOT/$OBJ/${t#*:}" \
      --output_dir "$VISION_ROOT/$OBJ/ism_${t%%:*}"
  done )
envs/seg_sam6d/bin/python -m spatial_vision.stages.segment_sam6d --in runs/semi01 --out runs/semi01_ism \
    --target full   --templates $OBJ/ism_full   --cad $OBJ/full.ply
envs/seg_sam6d/bin/python -m spatial_vision.stages.segment_sam6d --in runs/semi01 --out runs/semi01_ism \
    --target flange --templates $OBJ/ism_flange --cad $OBJ/top_flange.ply
for t in full flange; do
  envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 --in runs/semi01 --out runs/semi01_sam3 \
      --target $t --prompts-file $OBJ/sam3_prompts.json
done
envs/seg_sam6d/bin/python -m spatial_vision.eval.eval_seg --gt runs/semi01 \
    --pred runs/semi01_ism runs/semi01_sam3 --out runs/semi_m4_metrics.json

# M5 — pose 2-stage. GT depth / 예측 마스크·stereo depth 두 조건을 함께 낸다
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/semi01 --out runs/semi01_pose_gt \      # M5
    --obj $OBJ --depth gt --flange-mask-from pose
envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/semi01 --obj $OBJ \
    --pred runs/semi01_pose_gt --out runs/semi_m5_metrics.json

# ─────────────────────────────────────────────────────────────────────────────
# ★ KPI 를 만족하는 현행 최적 조합 (§M2 확장). 위 4프레임 경로는 이력이고, 실사용은 이쪽이다.
# ─────────────────────────────────────────────────────────────────────────────
# (1) clutter 씬 캡처 — 조명·방해물(동일 FOUP 포함)·가림. flange 는 온전히 보이도록 강제한다
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/work01 --frames 40 --seed 400 --baseline-mm 120 --distance-m 0.8 1.2 \
    --distractors 6 --distractor-foups 3 --distractors-active 2 4 --scatter-radius-m 1.6 \
    --occluders 3 --occluders-active 1 2 --occluder-ray-frac 0.05 0.30 --occluder-size-m 0.05 0.18 \
    --light-fixtures 4 --light-fixtures-active 1 3 --dome-intensity 400 2000 --color-temperature-k 3000 6500

# (2) depth
envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx --in runs/work01 --out runs/work01_onnx \
    --scale 0.75 --model weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx

# (3-a) segmentation — ISM + 타깃 선택 규칙 (현행 최선)
envs/seg_sam6d/bin/python -m spatial_vision.stages.segment_sam6d --in runs/work01 --out runs/work01_ism \
    --target full --templates $OBJ/ism_full --cad $OBJ/full.ply --select center \
    --depth stereo --depth-dir runs/work01_onnx

# (3-b) segmentation — SAM3 exemplar (사전 참조 자산. 자산은 깨끗한 런에서 1회 생성)
envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs --from runs/semi_clean --obj $OBJ --n 3
envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 --in runs/work01 --out runs/work01_sam3 \
    --target full --refs $OBJ/sam3_refs --n-refs 3

# (4) pose + 평가
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/work01 --out runs/work01_pose \
    --obj $OBJ --masks runs/work01_ism --depth stereo --depth-dir runs/work01_onnx --flange-mask-from pose
envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/work01 --obj $OBJ --pred runs/work01_pose

# ─────────────────────────────────────────────────────────────────────────────
# ★★ 현행 최선 — 실내조명 + 검정 flange + 2단계(원거리 coarse → 근접 flange 재추정)
#    자산: bash envs/fetch_env_assets.sh   (HDRI 는 카테고리별 하위 디렉토리로 받는다)
# ─────────────────────────────────────────────────────────────────────────────
APP="--hdri assets/env/hdri/Indoor --ground-material --ground-textures assets/env/ground \
     --body-material --flange-color 0.03 0.03 0.03 \
     --light-fixtures 4 --light-fixtures-active 0 2 --fixture-intensity 300 3000 \
     --dome-intensity 60 250 --color-temperature-k 3000 5500"
CLUT="--distractors 6 --distractor-foups 3 --distractors-active 2 4 --scatter-radius-m 1.6 \
      --occluders 3 --occluders-active 1 2 --occluder-ray-frac 0.05 0.30 --occluder-size-m 0.05 0.18"

# (1) 캡처 — 원거리 / 근접 두 벌
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/dr2_far  --frames 40 --seed 400 --fx 1200 --distance-m 0.8 1.2  $APP $CLUT
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/dr2_near --frames 40 --seed 400 --fx 1200 --distance-m 0.35 0.50 $APP $CLUT

# (2) 참조 자산 — ⚠️ **더 좁은 노출 밴드**로 뜬다. 넓은 밴드면 참조가 새까맣거나 날아간다
REFAPP="--hdri assets/env/hdri/Indoor --ground-material --ground-textures assets/env/ground \
        --body-material --flange-color 0.03 0.03 0.03 \
        --light-fixtures 4 --light-fixtures-active 1 2 --fixture-intensity 600 2200 \
        --dome-intensity 110 210 --color-temperature-k 3500 5200"
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/ref_near2 --frames 8 --seed 912 --fx 1200 --distance-m 0.35 0.50 $REFAPP
envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs --from runs/ref_near2 --obj $OBJ \
    --n 3 --target flange --out-name sam3_refs_flange_near

# ★ 참조 세트는 "후보를 넉넉히 → 면적 기준으로 선별" 이 정본이다 (§19). 균등 간격을 그대로 배포하지 않는다.
#   ① 후보 42장  ② 후보 전부로 프로브 프레임 분할(참조별 마스크 저장)  ③ 면적 상위 5장 선별
envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs --from runs/ref42 --obj $OBJ \
    --n 42 --target full --out-name sam3_refs42
envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 --in runs/probe --out runs/probe_perref \
    --target full --refs $OBJ/sam3_refs42 --refs-mode independent --save-per-ref
envs/seg_sam3/bin/python -m spatial_vision.cad.select_sam3_refs --refs $OBJ/sam3_refs42 \
    --probe runs/probe_perref --obj $OBJ --k 5 --out-name sam3_refs42_top5
# 프로브 20프레임이면 충분하다(IoU 0.887 vs 전체 0.888). GT 불필요. 온보딩 1회 ~3분 40초.
# 추론은 오히려 빨라진다: 42장 10.9s/frame → 5장 1.3s/frame

# (3) depth
envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx --in runs/dr2_far  --out runs/dr2_far_onnx  --scale 0.75 --model weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx
envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx --in runs/dr2_near --out runs/dr2_near_onnx --scale 0.75 --model weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx

# (4) 분할 — 원거리는 ISM(full), 근접은 SAM3 flange(근접 참조). 근접 flange IoU 0.983
envs/seg_sam6d/bin/python -m spatial_vision.stages.segment_sam6d --in runs/dr2_far --out runs/dr2_far_ism \
    --target full --templates $OBJ/ism_full --cad $OBJ/full.ply --select center \
    --depth stereo --depth-dir runs/dr2_far_onnx
envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 --in runs/dr2_near --out runs/dr2_near_sam3fl \
    --target flange --refs $OBJ/sam3_refs_flange_near --n-refs 3

# (5) ① 원거리 coarse  →  ② 근접 flange **재추정**(초기값 전달 없음 — 있으면 오히려 나쁘다)
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_far --out runs/dr2_far_pose \
    --obj $OBJ --masks runs/dr2_far_ism --depth stereo --depth-dir runs/dr2_far_onnx --flange-mask-from pose
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/dr2_near_flonly \
    --obj $OBJ --primary flange --masks runs/dr2_near_sam3fl --depth stereo --depth-dir runs/dr2_near_onnx
envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/dr2_near --obj $OBJ --pred runs/dr2_near_flonly

# 불변식 검사 — "flange 는 고정, body 만 randomize" 를 렌더 픽셀로 확인한다.
# ⚠️ **시점·조명을 고정한 별도 런**에서만 뜻이 있다.
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/dr2_iso --frames 6 --seed 11 --fx 1200 \
    --distance-m 1.0 1.0 --elevation-deg 60 60 --azimuth-deg 0 0 --yaw-jitter-deg 0 \
    --hdri assets/env/hdri/Indoor/hotel_room_4k.hdr --hdri-rotate-deg 0 0 \
    --ground-material --ground-textures assets/env/ground \
    --body-material --flange-color 0.03 0.03 0.03 \
    --dome-intensity 150 150 --color-temperature-k 4500 4500
envs/stereo_onnx/bin/python -m spatial_vision.eval.verify_randomization --in runs/dr2_iso

# ─────────────────────────────────────────────────────────────────────────────
# 기각된 경로 — 재현용 (§M5 확장 §6-7). 채택하지 않는다.
# ─────────────────────────────────────────────────────────────────────────────
# 근접 캡처는 **같은 seed** 로 떠서 프레임을 원거리 런과 짝짓는다(동일 객체 자세, 카메라만 이동)
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/work01_near --frames 40 --seed 400 --baseline-mm 120 --distance-m 0.35 0.50  # 나머지 인자 동일

# (a) flange 단독 근접 pose — 초기값 없음 → R 18~24° 로 붕괴한다
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/work01_near --out runs/work01_flpose \
    --obj $OBJ --primary flange --masks runs/work01_near_sam3fl --depth stereo --depth-dir runs/work01_near_onnx

# (b) 카메라 이동 2단계 — 1차 pose 를 상대 카메라 변환으로 옮겨 초기값으로 준다
#     --rel-from-gt 는 로봇 hand-eye 의 대역이다(객체 pose 가 아니라 카메라 이동만 GT).
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/work01_near --out runs/work01_2stage \
    --obj $OBJ --primary flange --init-from runs/work01_pose --init-capture runs/work01 --rel-from-gt \
    --masks runs/work01_near_sam3fl --depth stereo --depth-dir runs/work01_near_onnx

# 근접 질의용 SAM3 참조는 **근접 런에서 다시** 만든다 — 원거리 참조를 쓰면 IoU 0.044 (§M5 확장 §5)
envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs --from runs/near_clean --obj $OBJ \
    --target flange --n 3 --out-name sam3_refs_flange_near
```

---

# M0 — 런타임 격리 + 리포/가중치 (2026-08-07)

> 🛠 **측정 절이 아니다** — 런타임 구축 기록(venv·CUDA·가중치). 재현 절차는 `docs/SETUP.md`.

## 런타임

| 구성 | 결과 |
|---|---|
| GPU/torch | **torch 2.11.0+cu128, sm_120 정상** — arch_list 에 sm_120 포함, fp16 matmul·cudnn conv·backward·flash SDPA 확인 |
| python | **venv 6종 전부 3.12.3** (`stereo` `pose` `seg_sam3` `seg_sam6d` `stereo_onnx` `cad`). Isaac 번들 python 3.12.13 과 계열 일치 |
| CUDA 툴체인 | 시스템에 nvcc 없음 → NVIDIA redist 컴포넌트로 `envs/cuda` 에 **CUDA 12.8 조립(~81MB)**. sm_120 커널 컴파일·실행 확인 |
| FoundationStereo | import OK (numpy 2.4.4 / open3d 0.19) |
| FoundationPose | pytorch3d 0.7.9(CUDA rasterizer) + nvdiffrast 0.4.0 + mycpp + estimater 전부 OK |
| SAM 3 | 로컬 ckpt 로 **840.5M params GPU 빌드** — 런타임 HF 인증 불필요 |
| SAM-6D ISM | SAM 경로 import OK (lightning 2.6.5) |

`bash envs/verify.sh` → ✅ 통과.

## 가중치 (13/13)

| 모델 | 검증 |
|---|---|
| FoundationStereo `23-51-11` (ViT-large) | 374.5M params, `load_state_dict` **missing=0 / unexpected=0** |
| FoundationStereo `11-33-40` (ViT-small) | 62.4M params, **missing=0 / unexpected=0** |
| FoundationPose refiner / scorer | 17.0M / 16.0M params 로드 OK |
| SAM 3 (+ 3.1) | 840.5M params GPU 빌드 성공 |
| SAM-6D ISM (SAM vit_h 2.4G + DINOv2 vitl14) | 다운로드·배치 완료 |
| NGC FoundationStereo ONNX | 상업 경로용 (무인증) |

**전 스택 end-to-end**: FoundationPose 데모(`mustard0`) **737프레임 EXIT=0**,
det(R)=1.000000~1.000002(전 프레임 정상 회전행렬), z 0.519~0.804m,
**프레임간 이동 median 0.3mm / max 17.8mm**(트래킹 튐 없음).

## M0 에서 걸렸던 것

1. **`nvidia-cuda-nvcc-cu12` 휠에 `nvcc` 가 없다** — `ptxas` 와 nvvm 만. → NVIDIA redist 아카이브로 직접 조립(81MB, 전체 runfile 4GB 불필요).
2. **CUDA math 헤더 부재** — `cusparse.h` 가 없어 pytorch3d·nvdiffrast 빌드 실패. → `link_cuda_libs.sh` 가 torch 의 `nvidia-*` 휠 헤더/`.so` 를 CUDA_HOME 에 심링크(**torch 와 ABI 자동 일치**). 휠은 `.so.12` 만 주므로 링커용 **비버전 `.so`** 도 생성. ⚠️ **venv 재생성 시 링크가 끊어진다** → 재실행 필요.
3. **mycpp 가 시스템 python 으로 빌드된다** — `find_package(pybind11)` 가 venv 를 무시. → `Python_EXECUTABLE`/`*_FIND_VIRTUALENV=ONLY` 강제.
4. **numpy 가 실제로 충돌한다** — sam3 는 `numpy<2`, FoundationPose 는 `numpy>=2`. venv 분리가 필수임이 확인됨.
5. **FastSAM 경로 포기** — 현행 `ultralytics` 가 `from ultralytics import yolo` 를 제거, 원 pin(8.0.135)은 3.12 미지원. ISM 은 **SAM 경로**(원래 기본값) 사용. 부수적으로 AGPL 회피.
6. **SAM-6D PEM 미설치** — pose 는 FoundationPose 담당이라 `pointnet2` CUDA 빌드 불필요.
7. **캐시 유출** — `ultralytics`(`YOLO_CONFIG_DIR`)·`matplotlib`(`MPLCONFIGDIR`) 미지정 시 `~/.config`·`~/.cache` 에 쓴다. `env.sh` 에 추가. `gdown` 은 `~/.cache/gdown` 하드코딩이라 환경변수로 못 막는다.
8. **`stat -c%s` 는 심링크 자체 크기를 잰다** → `check_weights.sh` 는 `stat -Lc%s`.
9. 브라우저 다운로드는 파일명에 **`-001`** 이 붙을 수 있다 → `place_weights.sh` 가 흡수.
10. **`uv venv` 는 venv 가 이미 있으면 에러로 멈춘다**(uv 0.9+) — `bootstrap.sh` 가 표방한 idempotent 가 실제로는 깨져 있었다. `--allow-existing`(`mkvenv()` 헬퍼)로 기존 venv 를 보존하고 `pip install` 이 다시 맞춘다.
11. **venv 를 지워도 CUDA 소스 빌드는 재검증되지 않는다** — uv 가 빌드 산출물을 `.cache/uv/archive-v0/` 에 두고 그대로 꺼내 쓴다(`envs/pose` 삭제 후 재빌드가 **8.3초**). 빌드 경로를 실제로 검증하려면 `uv cache clean pytorch3d nvdiffrast` 를 같이 해야 한다.

## M0 재현성 재검증 (2026-08-07)

`envs/pose` + uv 캐시(444 파일/513.9MB) 를 지우고 `bash envs/bootstrap.sh pose` 재실행 → **EXIT=0, 15.5초**.

| 검사 | 결과 |
|---|---|
| pytorch3d·nvdiffrast **소스 재빌드** | `Building/Built` 확인. `_C.so` 에 `.nv_fatbin` 존재, `knn_points` CUDA 커널 실행 결과가 CPU 와 일치 → **sm_120 코드 실재**(R1 재확인) |
| **빌드 재현성** | 새 `_C.so` 가 이전 것과 **sha256 동일**(`4e01e4ae…`). ccache 없이 bit-identical → 툴체인 고정이 실제로 작동 |
| `link_cuda_libs.sh` | venv 제거 시 CUDA_HOME 심링크 **101개가 끊어짐**을 실측. 재실행이 정리 후 147 headers / 53 libs 로 복구(위 함정 2 의 설계대로) |
| 파급 | 같은 링크를 쓰는 `stereo_onnx` 의 ORT CUDA EP 정상(세션+추론 31.3s) |

**pytorch3d·nvdiffrast 커밋 고정 (2026-08-07 조치)** — 이 둘은 clone 이 아니라 `pip install git+…` 라
`repos.lock` 이 못 잡고 **HEAD 를 받고 있었다**. `bootstrap.sh` pose 섹션에 `PYTORCH3D_SHA=9381c401…`(0.7.9) /
`NVDIFFRAST_SHA=253ac4fc…`(0.4.0) 로 박았다. 고정 후 캐시 정리 → 재빌드 검증: 설치 커밋이 고정값과 일치하고
`_C.so` sha256 이 고정 전과 동일(`4e01e4ae…`), `verify.sh` 통과. 갱신할 곳이 두 군데(`repos.lock` + 이 SHA)라
`repos.lock` 머리말에 상호 참조를 달아 뒀다.

**pybind11 고정 (2026-08-07 조치)** — 미고정 상태에서 **3.0.4 → 3.1.0** 드리프트가 실측됐다. mycpp 의 ABI 를
결정하는 값이고 `FoundationPose/requirements.txt` 에는 없어 `bootstrap.sh` 가 유일한 지정점이므로
`pybind11==3.1.0` 으로 박았다. 재빌드 검증: mycpp `.so` 재생성 + `verify.sh` 통과.

### envs/cuda 재조립 — ★ 조용한 CPU 폴백을 잡아냈다 (2026-08-07)

`envs/cuda` + 캐시된 redist 타르볼을 지우고 `bash envs/bootstrap.sh cuda` **단독** 실행 → 재다운로드 포함 22초,
nvcc 정상. 그런데 **CUDA_HOME 이 불완전했다**: include 90 / lib 9 뿐이고 `cusparse.h`·`libnvrtc.so.12` 가 없다.

⚠️ **증상이 고약하다 — 실패하지 않고 조용히 느려진다.** 이 상태에서 onnxruntime 은 예외를 던지지 않고
**`CUDAExecutionProvider` → `CPUExecutionProvider` 로 말없이 폴백**한다. stereo_onnx 가 ~38× 느려질 뿐
결과는 나오므로(§M3 의 CPU 18.7s vs GPU 488ms) 눈으로는 알 수 없다.

원인은 섹션 간 책임 분리였다: math 라이브러리 연결(`link_cuda_libs.sh`)을 **pose 섹션**만 호출해서,
전체 실행에서는 순서상 문제가 없지만 `bootstrap.sh cuda` 단독 실행에서는 아무도 부르지 않는다.
→ **조치**: cuda 섹션이 끝날 때 `envs/pose` 가 있으면 스스로 연결하고, 없으면(최초 부트스트랩) 안내를 출력한다.

수정 후 재검증: `bootstrap.sh cuda` 단독으로 **include 147 / lib 53** 완성, `nvcc -arch=sm_120` 로 커널을
직접 컴파일·실행 성공, ORT 가 `CUDAExecutionProvider` 유지, `verify.sh` 통과.

### 나머지 5개 venv — uv 캐시 전체 삭제 후 재현 (2026-08-07)

`stereo` `seg_sam3` `seg_sam6d` `stereo_onnx` `cad` 를 치우고 **uv 캐시 16.6GB 를 전부 삭제**한 뒤
섹션별 재빌드. 실제 재다운로드 발생(`Prepared 32 packages in 5m 54s` = torch cu128 등). **EXIT=0.**

| 검사 | 결과 |
|---|---|
| 패키지 구성 | 325개 중 **버전 변경 2건뿐** — `soupsieve 2.9.1 → 2.9.2`(stereo·seg_sam6d, beautifulsoup4 의 간접 의존) |
| 런타임 | `verify.sh` ✅ / `check_weights.sh` 13/13 ✅ / M1 `verify_obj` ✅ |
| **수치 재현** | 재빌드된 `stereo_onnx` 로 M3 재실행 → `flange_core` MAE **2.810mm**(문서 2.812), `disp` MAE **0.1114px**(완전 일치), `obj_core` 6.421(문서 6.422) |
| GPU 비결정성 | disparity 편차 mean **0.000317px** / p99 0.001404 / max 0.042278 — ORT CUDA EP 의 atomics 수준. 지표에는 0.07% 영향 |

⚠️ **재빌드가 잡아낸 것: 구 `seg_sam6d` venv 에 `ultralytics 8.4.115`(+`polars`·`psutil`·`nvidia-ml-py` 등
의존 5개)가 **실제로 설치돼 있었다**.** `bootstrap.sh` 는 이걸 설치하지 않으므로(M0-5 결정) 재빌드본에는 없고,
그 상태로 `verify.sh` 의 ISM 검사가 통과한다 — SAM 경로가 ultralytics 를 쓰지 않음이 실증됐다.
**AGPL-3.0 패키지가 트리에 남아 있던 것이므로 라이선스 문서의 서술과 실제가 어긋나 있었다**(`LICENSES.md` §2 정정).
오래된 venv 는 "설치하지 않기로 한 결정" 이전의 상태를 그대로 이고 간다 — 결정 이후 재빌드하지 않으면 조용히 남는다.

---

# M1 — CAD 준비 (2026-08-07)

> 🛠 **측정 절이 아니다** — CAD 준비 파이프라인. 대상은 **구 자산 `foup_300`** (형상 오류로 폐기 → 「신 CAD 전환」 절).

산출물 `assets/obj/foup_300/`: `full.ply`(19,548 faces, watertight, 5,569.8cm³) ·
`top_flange.ply`(624, watertight, 485.0cm³) · `body.ply`(19,922) · `keypoints.json` · `meta.json` · `mesh.usda` · `views.png`

| 검증 | 결과 |
|---|---|
| **단위** | rim **ø190.00mm**, hole **ø40.00mm** — 기대 표준치와 정확히 일치(`scale 10` 확인) |
| **두 메쉬 좌표계 일치** | flange 정점 → full 표면 거리 **max 0.000000mm** (컷면 캡 69개 제외, 245개 검사) |
| **원점 규약** | flange 주 상면 z = **+0.0000mm**, rim 원 최소자승 중심 **(−0.0000, −0.0000)**, 반경 95.0000mm |
| **분해 정확성** | `body ∪ flange` 부피 = `full` (차이 **0.000cm³**) |

**단위 검증을 표준 치수로 자동화**: rim ø190 / hole ø40 이 허용오차를 벗어나면 스크립트가 실패한다.
오픈 CAD 는 cm/inch 로 오는 일이 흔하고 단위가 틀리면 이후 전부가 조용히 어긋나므로 SEMI 표준 기하를
단위 체크섬으로 쓴다. (mm CAD 를 받으면 `source.json` 의 `scale` 만 `1.0` 으로 바꾸면 된다.)

## M1 에서 뒤집힌 것

1. **원점 `(0,0,177)` → `(0,0,175)`** — 177 은 mesh bbox 최댓값이었으나 실제로는 **중앙의 작은 돌기(r 25~33mm, 정점 24개)** 일 뿐이고, 관측되는 주 상면은 **z=175**(r 20~92, 면적 18,118mm²)다. 2mm 차이지만 §CONSUMER 2.6 의 Z 오차 논의(15mm 급)와 성격이 같다. → 도구가 bbox 최댓값 대신 **위를 향하는 수평면 중 면적 최대**를 자동 검출.
2. **"평면+원통 컷 필요" 는 틀렸다** — `z ≥ 155` **평면 컷 하나**로 연결성분이 정확히 2개로 갈리고(flange r∈[20.00, 95.00] / shell r∈[138.81, 252.30], **반경 간극 43.8mm**), **양쪽 다 watertight**. 삼각형 선택 방식은 경계에 걸치는 249개를 잘못 처리하므로 폐기. CAD 커널(pythonocc/FreeCAD) 도입도 불필요로 판정.

부수 확인: **중심 홀은 관통이 아니라 z=167~175 의 블라인드 포켓(깊이 8mm)**. contour/keypoint 설계 시 홀 안쪽으로 배경이 비치지 않는다.

---

# M2 — Isaac 스테레오 rig 캡처 (2026-08-07)

> 📐 **측정 조건** — 구 자산 `foup_300` · `fx 952 @1280×720 · B 120mm` · 거리 1.05~2.40m · **n=4** · GT depth.

프레임당 산출물: `left.png` `right.png` `cam.json` `depth_gt.png`(16-bit mm) `depth_gt.npy`(float32 mm)
`disparity_gt.npy` `mask_full.png` `mask_flange.png` `pose_gt.json` `meta_capture.json`

| 검사 | 결과 (4 프레임 전부) |
|---|---|
| **[1] rectification** | 좌→우 상대회전 **0.000000°**, 상대이동 **(−120.0000, 0.0000, 0.0000)mm** |
| **[2] photometric warp** | 워프 MAE **1.27~1.61**(0-255), **부호반전 대조군 13.9~17.9** (비율 0.08~0.12) |
| **[3] pose↔depth↔intrinsic** | rim keypoint **16/16 투영, mask 적중 100%**, 평탄면 깊이오차 **median 0.000mm** |

`disparity_gt` 를 만든 식(`fx·B/Z`)으로 다시 검사하면 자기순환이므로, **실제 픽셀 워프**와
**CAD→투영 교차검증**을 독립 지표로 썼다. [2]의 **부호반전 대조군**이 baseline 부호의 실증이다.

캡처 예시(4프레임): 거리 1.05~2.40m, elevation 41.6~72.6°, mask full 19k~97k px, flange 비율 13.6~22.7%.

## M2 에서 잡아낸 것 (둘 다 조용히 틀렸을 것들)

1. **반픽셀 규약** — Isaac 의 `cx = W·(0.5 + offset/aperture)` 는 **코너 원점** 연속 좌표(픽셀 k 의 중심이 k+0.5)인데 OpenCV/BOP 는 **픽셀 중심이 정수 인덱스**다. 그대로 쓰면 정확히 0.5px 어긋나고 경사면에서 깊이 오차로 드러난다 — 실측 **0.21~0.83mm(뷰 경사에 비례)**, `−0.5` 보정 시 **0.0001mm**.
   *진단 결정타*: **바닥면(world z=0)** 에서도 동일한 오프셋(+0.807 / +0.264mm)이 나와 우리 CAD·USD·pose 와 무관한 규약 문제임을 확정. 서브프레임 16→64 로 바꿔도 불변 → 렌더 잡음도 아님.
   → `intrinsics_from_params()` 가 `cam.json` 에 **OpenCV 규약으로 보정해서** 쓴다(원본은 meta 보존).
2. **`astype(uint16)` 는 반올림이 아니라 버림** — depth 가 평균 0.5mm 작게 저장되어 역투영 표면이 카메라 쪽으로 밀린다. `np.rint` 로 수정. → 더불어 **GT 는 양자화하지 않은 `depth_gt.npy`(float32)** 도 저장한다(16-bit PNG 는 소비 계약용, 평가 기준은 float).
3. **USD 카메라는 −Z 전방** — BOP/OpenCV(+Z 전방)로 `diag(1,−1,−1)` 변환이 필요하다. 빼먹으면 pose 의 Z 가 음수가 되어 투영이 전부 카메라 뒤로 간다(sdg_ws `bop_writer.py:46` 과 동일 규약).

## 설계 메모

- `rep.functional.modify.pose(..., look_at_value=)` 의 전방축 규약이 문서화돼 있지 않아 **rig 행렬을 직접 구성**했다. 스테레오는 좌우 상대회전이 0 이어야 성립하므로 규약 추측은 금물.
- USD 는 `build_usd.py` 로 **직접 저작**(asset_converter 미사용) — 변환기가 tessellated 포맷의 단위를 추측하는데 M1 에서 좌표계를 이미 확정했으므로 추측이 낄 여지를 없앴다.
- part mask 를 위해 `body.ply` + `top_flange.ply` 를 **겹치지 않는 별개 prim** 으로 넣는다(semantic 은 prim 단위).
- USD 원점 = pose frame. `PIPELINE_PLAN.md` §4.1 의 `t'=t+R·d` 변환은 **우리가 저작하지 않은 에셋**용 처방이고, 직접 만든 에셋은 한 규약으로 통일해 "두 규약 혼재" 위험을 원천 제거했다.

## 미구현 (M2 범위 밖)

배경·조명·재질 randomization, distractor/occluder, 물리 배치. 현재는 dome light + ground plane + 객체 하나의
**최소 씬** — M2 의 목적이 rig 기하와 GT 배관의 정확성 확인이었기 때문. 대량 생성 시 sdg_ws 에서 randomizer 를 복사.

---

# M3 — Depth: FoundationStereo 백엔드 2종 (2026-08-07)

> 📐 **측정 조건** — 구 자산 `foup_300` · `fx 952 @1280×720` · 거리 1.05~2.40m · **n=4** · 지표는 `flange_core`(마스크 5px 침식).

**측정 조건**: 4 프레임, 거리 1.05~2.40m, `flange_core` = flange mask 를 5px 침식한 면.
평가는 `disparity.npy` 에서 다시 계산한 **float depth**(양자화 회피), GT 는 `depth_gt.npy`.

| 구성 | 모델 | 추론 해상도 | flange_core MAE | disp MAE | ≤1mm | obj_core MAE | 추론 | 라이선스 |
|---|---|---|---|---|---|---|---|---|
| `fs_torch` | ViT-**large** (23-51-11) | 1280×720 | **1.885mm** | 0.0844px | 41.9% | 3.819mm | 1010ms | research only |
| `ngc_onnx` | **small** (NGC) | 960×540 (0.75×) | **2.812mm** (1.49×) | 0.1114px | 26.5% | 6.422mm | 923ms | **상업 가능** |
| `fs_torch` | ViT-large | 640×360 (0.5×) | 4.032mm (2.14×) | 0.1613px | 20.2% | 6.118mm | 534ms | research only |
| `ngc_onnx` | small | 640×360 (0.5×) | 4.838mm (2.57×) | 0.1800px | 15.0% | 8.396mm | 592ms | 상업 가능 |

## ★ 상업 격차는 모델 품질이 아니라 해상도(엔지니어링) 문제다

처음 비교(torch@full vs onnx@0.5)에서 2.57× 격차가 나왔으나 **공정한 비교가 아니었다** — ONNX 가 OOM 으로
축소 추론을 강요당한 상태였다. 통제 실험(torch 도 0.5×)으로 분리하면:

- **해상도 효과**: 같은 ViT-large, full→half → **1.885 → 4.032mm (2.14×)**
- **모델 크기 효과**: 같은 0.5×, large→small → **4.032 → 4.838mm (+20%뿐)**

0.75× 로만 올려도 **1.49×** 까지 좁혀지고, 그 지점에서 **torch@0.5(4.032mm)보다 오히려 낫다.**
→ 상업 경로의 최우선 과제는 모델 교체가 아니라 **메모리/해상도**다.

## 관찰·제약

- ⚠️ **ONNX 1280×720 OOM**: cost-volume attention 의 Softmax 가 단일 버퍼 **10.2GB** 를 요구해 실패(32GB GPU). 0.75×(960×544)까지 가능. 더 올리려면 **타일 추론** 또는 **TensorRT EP**(메모리 재사용).
- **경계가 지표를 지배한다**: `obj` 전체 MAE 5.05mm / P95 16.4mm 인데 `flange_core` 는 1.885mm. 정밀 pose 에 의미 있는 수치를 보려면 **면 기준(침식) 지표**를 봐야 한다.
- **전 구성이 flange 에서 음의 bias(−1.0 ~ −2.4mm)** — 예측이 실제보다 가깝다. M5 에서 pose Z 편향으로 이어질 수 있어 **추적 대상**(§CONSUMER 2.6 의 Z 오차 논의와 같은 성격).
- 이 수치는 **깨끗한 합성 depth 기준**이라 실환경 수치(§CONSUMER 2.7.1: z-MAE 17.6mm)와 직접 비교할 수 없다. M6 에서 같은 지표로 재면 sim→real 격차가 정량화된다.

## ONNX 어댑터 실측 사양 (M0 중 선행 검증)

`deployable_foundation_stereo_s_dynamic_v2.0.onnx` (347MB, 무인증):

| 항목 | 결과 |
|---|---|
| 인터페이스 | 입력 `left_image`/`right_image` float32 NCHW **완전 동적** → 출력 `disparity` `(B,1,H,W)`. opset 17, 53,448 노드 |
| 자립성 | **repo 코드 없이 onnxruntime 만으로 추론 성공** → 라이선스 청정 경로 성립 |
| GPU (sm_120) | 320×736 **488ms**, 576×960 **773ms** (CPU 18.7s 대비 ~38×) |
| 세션 초기화 | **~31s** → 프레임마다 프로세스를 띄우면 안 된다(84프레임에 43분 낭비). 어댑터가 세션 재사용 |
| 전처리 규약 | ⚠️ 그래프에 정규화 상수가 **없다** → 호출자가 `(img/255 − mean)/std`. 실측: raw 0-255 대비 MAE **1.43px** 차, `0-1` vs `imagenet` 은 0.21px. **raw 0-255 금지**. TAO 문서로 최종 확인 필요 |
| 후처리 | `depth = fx · baseline / disparity` (직접 구현) |

⚠️ **NGC 판은 TAO 재학습된 별개 변형** — GitHub 체크포인트와 호환되지 않는다(실측: 파라미터 1192 vs 1147,
이름 겹침 833, `cost_agg.agg_1.0.conv.weight` shape 56×112 ↔ 112×56, 명명 체계 상이). 서로 교체 불가.

**환경 주의**: PyPI 최신 `onnxruntime-gpu` 는 **CUDA 13**(`libcublasLt.so.13`)을 요구하는데 우리 CUDA_HOME 은
12.8 → **CUDA 12 전용 인덱스에서 `onnxruntime-gpu==1.22.0` 고정**. CUDA EP 는 `libnvrtc.so.12` 도 찾으므로
`link_cuda_libs.sh` 에 `cuda_nvrtc` 포함.

---

# M4 — Segmentation: SAM-6D ISM vs SAM 3 (2026-08-07)

> 📐 **측정 조건** — 구 자산 `foup_300` · `runs/sim01` · `fx 952 @1280×720` · 거리 1.05~2.40m · **n=4**.

**측정 조건**: `runs/sim01` 4프레임(거리 1.05~2.40m), GT 는 캡처가 낸 `mask_full.png` / `mask_flange.png`.
ISM 은 SAM 경로(vit_h) + DINOv2 vitl14, CAD 템플릿 42뷰(blenderproc). SAM3 는 로컬 ckpt, bf16 autocast.

| 백엔드 | 타깃 | 검출 | **오선택** | IoU(전체) | IoU(정상분) | precision | recall | 속도 |
|---|---|---|---|---|---|---|---|---|
| **ISM** | full | 4/4 | 0 | **0.982** | 0.982 | 0.983 | 0.999 | 1468ms |
| **SAM3** | full | 4/4 | 0 | 0.939 | 0.939 | **0.999** | 0.939 | **143ms** |
| **ISM** | flange | 4/4 | **1** | 0.643 | 0.858 | 0.715 | 0.678 | 1485ms |
| **SAM3** | flange | **3/4** | 0 | 0.542 | 0.722 | **0.981** | 0.732 | 145ms |

*오선택 = 마스크는 냈는데 IoU<0.1. 검출 실패와 성격이 다른 고장이라 따로 센다.*

## ★ 두 모델이 **서로 다른 방식으로** flange 에서 실패한다

평균 IoU(0.643 vs 0.542)만 보면 비슷해 보이지만 고장의 종류가 다르고, pose 에 미치는 영향도 다르다.

- **ISM — 엉뚱한 것을 고른다.** `frame_0000` 에서 16,656px 를 냈는데 GT(9,435px)와 **교집합이 0**이다
  (P=R=0). 나머지 3프레임은 0.946 / 0.905 / 0.721 로 좋다. 즉 **가끔 완전히 틀린다.**
- **SAM3 — 못 찾거나 덜 찾는다.** `frame_0001` 은 아예 검출 0. 찾은 프레임은 **precision 0.981** 로
  매우 깨끗하지만 `frame_0003` 은 recall 0.342(21,923px 중 7,755px 만).

**pose 입력으로는 이 차이가 결정적이다.** 마스크가 배경을 먹으면(precision↓) depth 가 배경까지 딸려와
초기 translation 이 망가진다. ISM flange 의 precision 0.715 는 **평균 28.5% 가 배경**이라는 뜻이다.
반대로 SAM3 의 실패는 "적게 먹는" 쪽이라 덜 해롭지만, 미검출 프레임은 그냥 못 쓴다.

## ★ 설계 함의 — flange 마스크를 segmentation 에 의존하지 말 것 (M5 로 넘김)

두 모델 모두 4프레임 중 1프레임에서 실패했다(25%). **flange-only 는 zero-shot segmentation 이
안정적으로 풀 문제가 아니다** — CONSUMER_6DPOSE §2.7.4 의 관찰이 sim GT 로 정량 확인됐다.
→ PIPELINE_PLAN §M5 의 2-stage 설계(**coarse pose 로 flange 영역을 crop**)가 이 결과로 뒷받침된다.
flange 마스크는 stage-1 pose 로 `top_flange.ply` 를 투영해 만드는 편이 낫다. **M4 가 공급할 것은
full 마스크이고, flange 는 pose 의 산물로 얻는다.**

full 마스크만 놓고 보면 **ISM 0.982 로 충분**하다. SAM3 는 0.939 로 조금 낮지만 **10× 빠르고 CAD 가
필요 없다** — 새 객체를 즉석에서 넣어보는 용도로는 SAM3, 정확도가 필요하면 ISM.

## 프롬프트 — SAM3 는 도메인 용어를 모른다

| 프롬프트 | 검출 | IoU | | 프롬프트 | 검출 | IoU |
|---|---|---|---|---|---|---|
| `white plastic box` | 4/4 | **0.939** | | `circle on top of the box` | 3/4 | **0.542** |
| `white box` | 4/4 | 0.935 | | `circular handle` | 1/4 | 0.000 |
| `box` | 2/4 | 0.493 | | `handle` | 2/4 | 0.000 |
| `container` | 0/4 | 0.000 | | `flange` / `round metal disc` / `round handle on top` | 0/4 | 0.000 |

⚠️ **`wafer carrier`·`flange`·`plastic container` 는 confidence 를 0.1 까지 낮춰도 검출 0건**이다 —
임계값 문제가 아니라 **개념 자체를 못 잡는다**. 일반적 시각 서술로 가야 한다. 반대로 `handle` 은
2/4 를 "검출"하지만 IoU 0 — **엉뚱한 곳을 자신 있게 집는다**. 검출 수만 보면 안 되는 이유.

## 통제 실험 — GT depth vs stereo depth

ISM 의 geometric score 는 depth 를 쓴다. GT depth(`depth_gt.npy`) 대신 M3 의 stereo 예측
(`runs/sim01_onnx_s075`, flange_core MAE 2.81mm)을 넣으면:

- **선택된 마스크가 전 프레임 동일** → IoU/precision/recall 전부 불변(0.982 / 0.643).
- 최종 score 만 미세하게 움직인다(예: full frame_0001 0.649 → 0.651).

→ **M4 는 이 수준의 depth 오차에 둔감하다.** semantic·appearance score 가 지배하고 geometric 은
순위를 뒤집지 못했다. M5 에서 depth 를 쓸 때는 사정이 다르므로(§M3 의 flange 음의 bias) 별도 확인이 필요하다.

## M4 에서 걸렸던 것

1. **hydra `initialize(config_path=...)` 는 cwd 가 아니라 호출한 모듈 파일 기준**으로 푼다. ISM 밖에서 부르면 `spatial_vision/stages/configs` 를 찾다 죽는다 → `initialize_config_dir`(절대경로). 단 체크포인트 경로는 상대경로라 **chdir 은 여전히 필요**하다.
2. **SAM3 는 bf16 autocast 안에서만 돈다** — 없으면 `mat1 and mat2 must have the same dtype`. README 에 없고 `examples/*.ipynb` 가 전역으로 진입한다. 전역 진입은 다른 스테이지로 새므로 추론 구간에만 건다.
3. **autocast 결과 텐서는 bf16 이라 numpy 가 못 받는다**(`Got unsupported ScalarType BFloat16`) → `.float()` 경유.
4. **BlenderProc 의 Blender 기본 설치 경로가 `/home_local/$USER/blender/`** 로 ws 밖이다 → `--blender-install-path` 필수. `envs/blender/blender-4.2.1-linux-x64`.
5. **예측 마스크 파일명이 GT 와 같다**(`mask_full.png`). `--out` 을 `--in` 과 같게 주면 GT 를 조용히 덮어쓴다 → 두 어댑터가 시작 시 거부한다.

## 한계 (수치를 읽을 때 감안할 것)

- **4프레임뿐**이다. 1프레임 = 25% 라 "4/4 vs 3/4" 같은 차이에 과한 의미를 두면 안 된다.
- **SAM3 프롬프트를 이 4프레임에서 골랐다** → SAM3 쪽에 낙관 편향이 있다. ISM 은 튜닝 파라미터가 없다(기본 `stability_score_thresh=0.97`).
- **distractor 가 없다.** PIPELINE_PLAN §M4 의 판정 기준 중 "유사 인스턴스(distractor FOUP) 존재 시 오선택률" 은 **측정되지 않았다** — M2 의 최소 씬에는 객체가 하나뿐이다. 위 오선택 1건은 distractor 때문이 아니라 같은 객체의 다른 부위를 고른 것이다. **이 기준은 randomizer/distractor 를 붙인 뒤에야 답할 수 있다.**

---

# ★ 신 CAD 전환 — `300mm SEMI FOUP` (2026-08-07)

> 🛠 **측정 절이 아니다** — 자산 교체 기록(`foup_300` → **`foup_300_semi`**). 이 절 **이후의 모든 수치는 신 CAD 기준**이다.

사용자가 "형상이 이상하다" 며 SEMI 규격 CAD 를 새로 제공했다(`assets/cad/300mm_foup/300mm_SEMI_FOUP.step`).
새 obj_id **`foup_300_semi`** 로 만들고 M1~M4 를 다시 돌렸다. 구 `foup_300` 산출물은 비교 근거로 남긴다
(구 **소스** CAD 는 교체 과정에서 삭제됐으므로 구 객체의 M1 재실행은 불가능하다).

## 두 CAD 는 근본적으로 다르다

| 항목 | 구 `FOUP 300.stl/stp` | **신 `300mm_SEMI_FOUP.step`** |
|---|---|---|
| 포맷·단위 | STL(cm) + STEP(mm) | STEP 만. 기하 컨텍스트 **cm**(`#20388 SI_UNIT(.CENTI.,.METRE.)`), cascadio 가 m 로 정규화 → **scale 1000** |
| 구조 | 단일 solid, 파트 트리 없음 | **`MANIFOLD_SOLID_BREP` 28개** = flange 1 + 본체·도어 2 + **웨이퍼 25** |
| up axis | +Z | **+Y** (웨이퍼가 Y 방향 적층) |
| bbox | 425×342×332mm | **356×344×428mm** |
| top flange | 파트 분리 안 됨 → `z≥155` 평면 컷 | ✅ **별도 solid** — 컷 규칙 불필요 |
| flange 외곽 | ø190 원형 rim | **142×142mm 라운드 정사각**(외접 ø183.36), 중심 홀 **ø41**(원뿔 보어), 주 상면 면적 18,306mm²(구 18,118 과 거의 같다) |
| 단위 체크섬 | rim ø190 / hole ø40 | **웨이퍼 ø300 × 25장** — 제조사 불변이고 **개수까지** 맞아야 해 훨씬 강하다 |

`prepare_obj.py` 에 `--split parts` 경로와 `--up-axis` 를 추가했다. 회전을 **분리 전에** 한 번 걸어
이후 로직(원점·keypoints·USD)이 소스별 분기 없이 Z-up 규약 하나로 돌아간다.

## ★ M4 결론이 뒤집혔다 — flange 분리는 되는 문제였다

| 백엔드 | 타깃 | 구 CAD | **신 CAD** |
|---|---|---|---|
| ISM | full | 0.982 | **0.984** |
| ISM | flange | 0.643 (**오선택 1**) | **0.921 (오선택 0)** |
| SAM3 | full | 0.939 | **0.983** |
| SAM3 | flange | 0.542 (**미검출 1**) | **0.954 (4/4)** |

구 CAD 기준으로 내린 **"flange 마스크는 zero-shot segmentation 으로 못 얻는다"(R9) 는 철회한다.**
그건 객체의 성질이 아니라 **틀린 형상의 성질**이었다. 신 CAD 에서는 두 백엔드 모두 flange 를
안정적으로 분리한다(오선택·미검출 0). → M5 의 2-stage 는 여전히 유효하지만, **flange 마스크를
segmentation 에서 받는 선택지가 되살아났다.**

SAM3 프롬프트도 형상을 따라간다: 구 CAD 의 `circle on top of the box` 는 신 CAD 에서 **0/4** 이고,
`small square lid on top of the box` 가 **IoU 0.954** 다. full 은 프롬프트가 아니라 **confidence 가 한계**였다 —
`white plastic box` 로 conf 0.3 이면 3/4(0.741), **conf 0.15 면 4/4(0.983)**.
⚠️ `raised square block on top` 은 **4/4 검출인데 IoU 0.080** 이다(엉뚱한 곳을 자신 있게 집는다).
객체별 프롬프트는 코드가 아니라 `assets/obj/<id>/sam3_prompts.json` 에 둔다(`--prompts-file`).

## M1~M3 재실행 결과

| 단계 | 결과 |
|---|---|
| M1 | solid 28개 → flange 1 / wafer 25 / 기타 2. 웨이퍼 ø300×25 체크섬 통과. 원점 = flange 주 상면 `(0,0,344)`. `verify_obj` ✅ (두 메쉬 거리 0.000000mm, 원점 z=0.0000, keypoint 이탈 0.0000mm) |
| M2 | rectification **0.000000° / −120.0000mm**, 워프비 0.065~0.086, rim 16/16 투영·mask 적중 100%, 평탄면 깊이오차 median **0.000mm** ✅ |
| M3 | `flange_core` MAE **3.403mm**(torch) / **3.855mm**(onnx). ⚠️ 구 CAD 수치(1.885/2.812)와 **직접 비교 불가** — 객체·프레임·거리 분포가 전부 다르다. flange 가 작아져(6,170px vs 9,141px) 경계 비중이 커졌고 음의 bias 도 −2.1/−2.9mm 로 커졌다 |

웨이퍼 25장은 `full.ply` 에서 **제외**하고 `wafers.ply` 로 따로 뒀다(내용물이지 객체가 아니고, 실제 FOUP 은
적재 상태가 매번 다르다). 필요하면 `--keep-wafers` 로 포함한다.

## 이번에 잡은 것

1. **keypoint 가 허공에 떠 있었다** — rim 을 원으로 가정하고 외접반경 원주에 뿌려서, 정사각 flange 에서 16개 중 **12개가 최대 21.3mm 형상 밖**이었다. M2 의 투영 검사는 **2D 실루엣 안에만 들어가면 통과**하므로 이걸 못 잡는다. → 외곽선(볼록껍질)을 등호길이로 샘플하도록 고치고, **`verify_obj` 에 3D 이탈 검사(`[4]`)를 추가**했다.
2. **중심 홀을 메쉬 전체 최소 반경으로 재면 틀린다** — 신 flange 는 원뿔 보어라 목이 ø15, 관측되는 상면 개구부는 ø41 이다. **주 상면 위에서** 재야 한다(원점을 bbox 가 아니라 주 상면으로 잡은 것과 같은 이유). `verify_obj` 가 자기 규칙으로 다시 재다가 갈라진 것도 여기서 드러나 **정의를 `prepare_obj` 한 곳으로** 합쳤다.
3. **capture_sim 이 실패해도 EXIT=0** — Isaac 의 `fastShutdown` 이 `SystemExit` 을 삼킨다. 워밍업 실패로 아무것도 안 만들었는데 셸에는 성공이 찍혔다. → `os._exit(code)` 로 종료 코드를 강제.
4. **캡처 워밍업 30스텝은 콜드 스타트에서 모자라다** — 새 USD 첫 실행에서 실패하고 재실행하면 통과했다("두 번째부터 된다" 는 재현성 고장). → 120스텝 + 진행 로그.
5. **cascadio 는 면 단위로 정점을 분리해 준다** — `merge_vertices()` 없이는 연결성분이 698개(=`ADVANCED_FACE` 수)로 나오고 watertight 가 전부 False 다.

---

# M5 — Pose: FoundationPose 2-stage (2026-08-07)

> 📐 **측정 조건** — `foup_300_semi` · `runs/semi01` · `fx 952 @1280×720` · 거리 1.05~2.40m · **n=4**.

객체 `foup_300_semi`, `runs/semi01` 4프레임(1.05~2.40m). GT 는 캡처의 `pose_gt.json`(`cam_T_obj`, 원점=flange 주 상면).
ADD/ADD-S 는 `full.ply` 에서 4,096점 샘플.

| 구성 | 단계 | R err | t err | tZ | ADD | ADD-S |
|---|---|---|---|---|---|---|
| GT depth | coarse (full) | **0.349°** | 2.327mm | +0.70 | 2.521mm | 1.962mm |
| GT depth | refined (flange) | 1.282° | **1.594mm** | +0.44 | 6.316mm | 4.292mm |
| GT depth | **hybrid (R=coarse, t=refined)** | **0.349°** | **1.594mm** | — | **2.112mm** | **1.590mm** |
| stereo depth | coarse | 0.395° | **3.191mm** | +2.32 | **3.594mm** | 2.802mm |
| stereo depth | refined | 2.378° | 3.517mm | **−2.82** | 10.704mm | 7.074mm |
| stereo depth | hybrid | 0.395° | 3.517mm | — | 3.917mm | 2.980mm |

## ★ stage-2 는 평행이동을 개선하고 **회전을 망친다**

refine 은 t 를 2.327 → **1.594mm** 로 32% 줄이지만 R 을 0.349 → **1.282°** 로 3.7배 키운다.
ADD 가 2.5 → 6.3mm 로 나빠지는 건 회전 때문이다(반경 200mm 에서 1.28° ≈ 4.5mm).

**반복 드리프트가 아니다** — `refine-iter` 1/2/5 에서 R 이 1.107 / 1.259 / 1.282° 로 **처음부터 나쁘다**.
원인은 누적이 아니라 **flange 단독의 회전 구속이 약한 것**이다(근사 대칭). 4프레임 전부에서 같은 방향으로
나빠졌고(coarse 0.20~0.49° → refined 0.65~1.67°), refined 의 dy 가 일관되게 음수다(−0.84~−1.63mm).

→ **처방은 단순하다: 회전은 coarse, 평행이동은 refine 에서 받는다.** 이 하이브리드가 GT depth 에서
ADD **2.112mm** 로 두 단독 구성보다 낫다. flange 주 상면 중심이 곧 로봇 TCP 타깃이므로(§4.1)
"위치는 정밀하게, 방향은 전체 형상으로" 가 과제 목적과도 맞는다.

## ★ R8 — refine 은 flange 영역의 depth 오차를 그대로 물려받는다

| | 값 |
|---|---|
| M3 측정: `ngc_onnx` **flange_core** depth 평균 편차 | **−2.851mm** |
| M5: stereo depth **refined** 평균 dz | **−2.817mm** |
| M5: stereo depth **coarse** 평균 dz (객체 전체 depth 기반) | +2.320mm |

refine 은 flange 영역 depth 만 보므로 **그 영역의 오차가 pose Z 로 1:1 전이된다** — 0.034mm 차이로 일치한다.
이 전이 자체는 확인된 인과다.

⚠️ **다만 이것을 "bias(계통 편차)" 라고 부르면 안 된다 — 아래 §flange depth 오차의 정체 참조.**
평균 −2.851mm 은 프레임별 **−0.406 / −3.957 / −4.802 / −2.516mm** 를 평균한 값이고, 다른 백엔드에서는
같은 프레임의 **부호가 뒤집힌다**. 계통 편차인지 아직 확인되지 않았다.

## ★ flange depth 오차의 정체 — 아직 "bias" 가 아니다

M3 의 평균값(−2.851mm)만 보면 상수 오프셋처럼 보이지만, 프레임별로 풀면 그렇지 않다.

| frame | 거리 | flange_core px | **onnx@0.75 편차** | **torch@1.0 편차** | disparity 편차 |
|---|---|---|---|---|---|
| 0000 | 1401mm | 4,490 | −0.406mm | −2.352mm | +0.0228px |
| 0001 | 2370mm | 1,674 | −3.957mm | **+1.888mm** | +0.0809px |
| 0002 | 2404mm | 1,816 | −4.802mm | −5.513mm | +0.0954px |
| 0003 | 1051mm | 12,338 | −2.516mm | −1.324mm | +0.2608px |

세 가지가 드러난다:

1. **상수가 아니다** — depth 편차가 −0.4 ~ −4.8mm 로 **12배** 벌어진다. disparity 로 환산해도
   0.023~0.261px 로 **11배** 벌어진다. 거리와의 상관은 depth 기준 r=−0.77, disparity 기준 r=−0.49 로
   **어느 쪽도 깨끗한 함수가 아니다.**
2. **백엔드가 바뀌면 부호가 바뀐다** — `frame_0001` 은 onnx −3.957mm, torch **+1.888mm**.
   센서·기하의 계통 오차라면 이럴 수 없다.
3. **해상도 문제가 아니다** — torch@1280×720 의 평균 |편차| 2.769mm vs onnx@960×544 의 2.920mm.
   **5% 차이뿐**이다(R7 의 해상도 지배 관찰은 MAE 에는 해당하지만 **편차에는 해당하지 않는다**).

→ **현재 데이터로는 보정 가능한 계통 편차라고 말할 수 없다.** n=4 에서 평균이 음수로 나온 것에 가깝다.
"보정" 을 논하기 전에 **먼저 계통 성분이 존재하는지 확인할 표본이 필요하다.**

## R4 는 발생하지 않았다

"top flange 근사 대칭 → 90°/180° 오추정"(R4)은 **관측되지 않았다**. 전 프레임 R 오차가 2.4° 미만이고
ADD/ADD-S 비가 1.3~1.5 로 대칭 오추정 특유의 큰 괴리가 없다. 2-stage 의 원래 명분(coarse 로 방향 고정)은
유효했지만, 정작 문제는 오추정이 아니라 **refine 단계의 회전 열화**였다.

## M4 → M5 인계는 병목이 아니다

full 마스크를 **GT 대신 SAM3 예측**(IoU 0.983)으로 바꿔도 결과가 사실상 동일하다:
coarse R **0.349° → 0.355°**, t **2.327 → 2.314mm**. flange 마스크 출처도 마찬가지다 —
coarse pose 투영 1.282° vs segmentation 1.132° 로 둘 다 쓸 만하다.
→ **segmentation 정확도는 이미 충분하고, 남은 오차는 depth 와 refine 알고리즘 쪽에 있다.**

## 목표 기준선 대비

`CONSUMER_6DPOSE.md` §2.7.3 의 sim 수치는 rot 평균 **0.91°** / trans **0.95mm** 다.
우리 최선(GT depth, 하이브리드)은 rot **0.349°**(더 좋다) / trans **1.594mm**(1.7배 나쁘다).
실제 파이프라인 조건(stereo depth, 예측 마스크)에서는 rot **0.395°** / trans **3.191mm**.
⚠️ 같은 객체·같은 프로토콜이 아니므로 직접 비교가 아니라 **자릿수 확인** 용도로만 읽는다.

## M5 에서 확인한 계약 (추측 아님)

- FoundationPose 는 **미터**를 쓴다 — `datareader.py:123` 이 depth PNG 를 `/1e3` 한다. mesh·depth 를 0.001배로 넣고 t 를 mm 로 되돌린다.
- 반환 pose 는 **메쉬 파일 자기 원점 기준**이다 — `best_pose = poses[0] @ get_tf_to_centered_mesh()` 로 내부 centering 이 상쇄된다. PIPELINE_PLAN §4.1 의 전제가 코드로 확인됐다.
- 반면 `pose_last` 는 **centered mesh 기준**이다 → stage-2 시딩은 `pose_last = cam_T_obj @ T(+model_center)` 로 되돌려 넣어야 한다. 이걸 빼먹으면 초기 pose 가 `model_center` 만큼(수십 mm) 어긋난 채 refine 이 시작된다.

## 한계

- **4프레임**. 1프레임이 25% 이고, 회전 열화가 전 프레임 일관적이라는 것 외에는 분포를 말할 수 없다.
- distractor·occluder·재질 randomization 이 없는 **최소 씬**이다(M2 범위). 실환경 난이도는 반영돼 있지 않다.
- ADD 는 `full.ply` 기준이라 **웨이퍼를 제외한 형상**에 대한 값이다.

---

# ★★ M2 확장 — randomizer / distractor 도입 이후 (2026-08-07)

> 📐 **측정 조건** — `foup_300_semi` · **`fx 952/1200/1400 @1280×720 · B 120mm`** · 원거리 0.8~1.2m(일부 1.0~2.0m) · **n=40** · randomizer+distractor.

> **이 절이 M4·M5 의 현행 수치다.** 위의 M4/M5 절은 **4프레임 최소 씬**(객체 하나, 가림·방해물 없음)
> 기준이라 여러 결론이 여기서 뒤집혔다. 옛 절은 "그때 무엇을 어떻게 쟀나" 의 기록으로 남긴다.

## 무엇을 추가했나

`spatial_vision/stages/scene_random.py` (capture_sim 이 옵션으로 사용):

1. **조명** dome 세기·색온도 + 상반구 rect/distant 조명 N개 (프레임마다 그림자 방향이 바뀐다)
2. **distractor** 바닥에 흩뿌리는 방해물. ★ **동일 FOUP 인스턴스 포함** — "유사 인스턴스 오선택률"
   (PIPELINE_PLAN §M4 판정 기준)은 이것 없이 측정 자체가 불가능했다
3. **occluder** 카메라→타깃 시선 위에 놓아 **부분 가림을 보장**. 무작위로 뿌리면 대부분 프레임에서
   아무것도 안 가려 표본이 낭비된다
4. **가림 정량화** clutter 를 숨긴 채 싼 렌더(subframe 1)를 한 번 더 돌려 `visib_fract` 실측

**미구현(sdg_ws 에 있으니 이식 가능)**: HDRI 배경 교체, MDL 기반 PBR 재질 randomization, 물리 낙하 배치.

## 데이터셋

| 런 | 프레임 | 조건 |
|---|---|---|
| `semi_clean` | 40 | 조명만 randomize, 방해물·가림 없음. **참조 자산·depth 특성화용** |
| `semi_rand` | 40 | + distractor 2~4개(동일 FOUP 0~3), occluder 1~2개 |
| `cam_zedx` / `cam_d435` | 40+40 | 동일 seed·동일 씬, **baseline 만** 120 / 50mm |
| `cfgA/B/C` | 40×3 | fx·거리 조합 탐색 |

**전제**: `top flange 는 온전히 보인다`(사용자 지정). occluder 조준점을 몸체로 내리고 프리체크로
강제한다 — flange 가림률 **99.2~100%**(39/40 이 100%), 몸체 가림률 69.6~100%.

## ★ 1. flange depth "bias" 는 없었다 — n=4 의 착시였다

| | onnx@0.75 | torch@1.0 |
|---|---|---|
| **n=4** (semi01) 평균 | **−2.920mm** | −2.055mm |
| **n=40** (semi_clean) 평균 | **+2.220mm** | +1.205mm |
| n=40 표준편차 | 6.161 | 3.672 |
| n=40 95% CI | [+0.311, +4.130] | [+0.067, +2.343] |
| 음수 프레임 | 17/40 | 20/40 |
| 거리 상관 | r=+0.302 | r=+0.054 |

**부호가 뒤집혔다.** 표준편차가 평균의 3배이고 절반이 음수다 — **계통 편차가 아니라 분산**이다.
해상도도 지렛대가 아니다: torch@1280×720 의 평균 |편차| 2.769mm vs onnx@960×544 의 2.920mm — **5% 차이뿐**.

→ 앞서 "보정 전에는 stage-2 금지" 라고 쓴 처방은 **철회**한다. 보정할 계통 성분이 확인되지 않았다.
(R8 의 "M3 오차가 M5 pose Z 로 1:1 전이된다" 는 관계 자체는 유효하다. 전이되는 것이 bias 가 아니라
그 프레임의 오차일 뿐이다.)

## ★ 2. distractor 를 넣자 M4 결론이 또 뒤집혔다 (텍스트 프롬프트 기준)

`semi_rand` 40프레임:

| 백엔드 | 타깃 | 검출 | **오선택** | IoU(전체) | IoU(정상) |
|---|---|---|---|---|---|
| ISM | full | 40/40 | 3 | 0.840 | 0.908 |
| SAM3(텍스트) | full | 36/40 | **18** | 0.434 | **0.965** |
| ISM | flange | 40/40 | 20 | 0.445 | 0.890 |
| SAM3(텍스트) | flange | 34/40 | 17 | 0.279 | 0.657 |

SAM3 는 **맞히면 가장 깨끗한데(0.965) 45% 확률로 엉뚱한 FOUP 을 고른다.** 프롬프트("white plastic box")가
모든 FOUP 에 똑같이 맞으므로 점수 최대 선택이 사실상 임의 선택이 된다. **분할 문제가 아니라 선택 문제**다.

## ★ 3. 타깃 선택 규칙 — 두 번 틀리고 세 번째에 맞았다

| 시도 | 규칙 | 결과 |
|---|---|---|
| 1차 | 중앙 근접만 | 물체의 **작은 파편**을 집음 — ISM IoU **0.009**, recall 0.009 |
| 2차 | + 면적 필터 | 이번엔 **배경(바닥면)** 을 집음 — precision **0.001** |
| **3차** | **점수 상위 → 면적 필터 → 중앙 근접** | ISM IoU **0.936, 오선택 0/40** |

원인은 **점수를 버린 것**이었다. 점수는 "찾는 물체를 닮았는가" 를 담고, 중앙 근접은 동일 인스턴스라
점수가 비슷해진 **동점자 구간의 tie-break** 로만 써야 한다. 규칙은 `contracts.select_index()` 한 곳에
두고 ISM·SAM3 가 공유한다.

⚠️ **1차 버그 상태로 낸 "조합 B 끝단 100%" 는 무효였다** — 점 수준 마스크(recall 0.009) 위에서 pose 가
우연히 나온 값이다. 수정 후 B 는 95%, C 가 100% 로 순위가 바뀌었다.

SAM3(텍스트)에서도 같은 규칙이 오선택 **18 → 1** 로 줄인다(IoU 0.434 → 0.770).

## ★ 4. SAM3 는 exemplar(사전 참조 이미지)로 써야 한다

`PIPELINE_PLAN` §M4 에 "exemplar/concept prompt" 라고 적혀 있었으나 그동안 **concept(텍스트)만** 구현돼
있었다. 코드로 확인한 사실:

- image processor 의 `add_geometric_prompt` 는 박스를 **좌표만** 저장한다(`Prompt(box_embeddings=boxes_cxcywh)`)
  → "지금 set_image 한 이미지의 이 영역" 이라는 뜻이고 **사전 이미지의 박스로는 못 쓴다.**
- 사전 참조를 쓰려면 **참조 N장 + 질의 1장을 한 시퀀스**로 묶어 `build_sam3_video_model` 의
  `add_prompt(frame_idx=0, boxes_xywh=…)` + `propagate_in_video` 로 전파해야 한다. **된다.**
- `add_prompt` 는 호출마다 `reset_state()` 를 부른다 → **여러 프레임에 각각 박스를 걸 수 없다.**
  참조 2번째부터는 프롬프트가 아니라 **추적으로 통과**한다.

**참조 장수** (질의 10프레임):

| 참조 | 평균 IoU | >0.5 | 최저 |
|---|---|---|---|
| 1장 | 0.861 | 9/10 | 0.000 |
| **2장** | **0.958** | **10/10** | 0.878 |
| **3장** | 0.957 | **10/10** | 0.871 |
| 5장 | 0.815 | 8/10 | 0.000 |

⚠️⚠️ **이 절의 "2~3장 최적" 은 폐기됐다 → §17·§19 를 볼 것.**
5장에서 나빠진 것은 참조 수의 성질이 아니라 **사슬 구현의 제약**이었고(`--refs-mode independent` 로
바꾸면 사라진다), *"어느 3장을 고르냐는 영향이 있다"* 는 관찰만 살아남아 **§19 에서 기준으로 정해졌다**
(마스크 면적 중앙값 상위 5장). **순서·시점 유사도가 무관하다**는 것도 유지되지만, 이제
*"그럼 무엇이 유관한가"* 의 답이 있다 — **참조 개별 품질**이다. 아래 표는 **사슬 방식의 이력**으로만 읽는다.

**프롬프트 방식 비교** (`cfgC_close` 40프레임, distractor 포함):

| 방식 | 검출 | 오선택 | IoU(전체) | 속도 |
|---|---|---|---|---|
| 텍스트 + center | 32/40 | 6 | 0.613 | 84ms |
| 같은이미지 박스(±20% 지터) | 40/40 | **21** | 0.218 | 132ms |
| **사전 참조 3장 (exemplar)** | **40/40** | 2 | **0.870** | 737ms |
| ISM + center | 40/40 | **0** | **0.936** | 1535ms |

같은이미지 박스가 최악인 이유: 좌표만 전달되므로 **박스가 조금만 어긋나면 옆 물체를 가리킨다.**
"사전 이미지의 박스" 와 "지금 이미지의 박스" 는 성격이 완전히 다르다.

## ★ 5. 카메라 baseline — ZED 계열이 필요하다

거리 1.0~2.0m, **동일 seed·동일 씬**에서 baseline 만 교체:

| | baseline | flange_core MAE | pose 깊이오차 | R평균 | **KPI 통과** |
|---|---|---|---|---|---|
| **ZED X** | 120mm | **3.423mm** | 2.24mm | 0.720° | **28/35 = 80%** |
| **D435** | 50mm | 6.803mm | 3.80mm | 0.931° | **20/35 = 57%** |

**측면 오차는 거의 같고(2.47 vs 2.74mm) 깊이 오차만 벌어진다.** disparity MAE 는 D435 가 오히려 좋은데
(0.1535 vs 0.1873px) 짧은 baseline 이 야코비안 $Z^2/(f_xB)$ 를 키워 depth 로 환산하면 뒤집힌다.

## ★ 6. KPI 를 만족하는 조합 — 찾았다

오차 모델 $\\sigma_Z \\approx \\dfrac{Z^2}{f_x B}\\sigma_{disp}$ 는 실측과 맞는다(fx 952·B 120·Z 1.5m →
19.7mm/px × 0.187px = 3.7mm vs 측정 3.42mm). 따라서 $f_xB$ 를 키우거나 $Z$ 를 줄이면 된다.
**같은 해상도에서 FOV 만 좁혀도 $f_x$ 가 오른다**(ONNX OOM 을 안 건드린다).

**끝단 성공률** (검출 실패·오선택·KPI 미달을 **전부 실패**로 셈, 40프레임):

| 조합 | 마스크 | 검출 | 대실패 | KPI(검출분) | **끝단** |
|---|---|---|---|---|---|
| **C: fx 952, 거리 0.8~1.2m** | **ISM+center** | 40/40 | **0** | 40/40 | **40/40 = 100%** |
| C | exemplar 참조3장 | 40/40 | 2 | 38/38 | **38/40 = 95%** |
| B: fx 1400, 거리 0.8~1.2m | ISM+center | 40/40 | 1 | 38/39 | 38/40 = 95% |
| 기준: fx 952, 거리 1.0~2.0m | SAM3 텍스트+center | 36/40 | 1 | 28/35 | 28/40 = 70% |

→ **렌즈를 바꾸지 않고 거리만 0.8~1.2m 로 당기는 C 가 최선.** 도입 비용 관점에서도 유리하다.

**절제 실험 — 무엇이 무엇을 고쳤나** (`semi_rand`, 대실패 제외):

| 구성 | 측면오차 | 깊이오차 | KPI |
|---|---|---|---|
| 예측 마스크 + stereo depth | 2.65 | 2.57 | 26/35 (74%) |
| 예측 마스크 + **GT depth** | 2.23 | **0.77** | **35/35 (100%)** |
| **GT 마스크** + stereo depth | 2.73 | 2.41 | 30/40 (75%) |

**대실패는 마스크(선택) 문제, KPI 미달은 depth 문제**로 깨끗하게 갈린다.

**운용 조건** (거리 상한별 KPI 통과율, ZED X 기준):

| 거리 상한 | n | 통과율 | t 최댓값 |
|---|---|---|---|
| ≤1.8m | 20 | 90.0% | 5.80mm |
| ≤2.0m | 27 | 85.2% | 7.51mm |
| ≤2.6m | 35 | 74.3% | 11.15mm |

flange 투영 면적 기준으로는 **≥4,000px 에서 91.7%** — 렌즈·해상도가 바뀌어도 유효한 기준이라 이쪽이 낫다.

## ⚠️ 통계적 한계 — "100%" 를 그대로 믿으면 안 된다

무결점 n 프레임에서 실패율의 95% 상한은 3/n 이다:

| n | 상한 | |
|---|---|---|
| 40 | 7.5% | 지금 위치 |
| 60 | 5.0% | **95% 주장 가능** |
| 300 | 1.0% | **99% 주장 가능** |

지금 40/40 은 "**95% 이상일 가능성이 높다**" 까지가 정직한 표현이다.

## SAM 3.1 — 보류

`sam3.1_multiplex.pt` 를 받아뒀으나 지금은 쓸 이유가 없다.

1. 개선 방향이 다르다 — 핵심은 **Object Multiplex**(H100·128객체에서 ~7배 속도). 정확도는 릴리스 노트가
   "**mixed results**" 라고 명시한다. 우리는 **객체 1개·4프레임 시퀀스**라 이득 조건이 아니다.
2. **배포 코드로 우리 체크포인트가 안 올라간다** — 키가 `tracker.model.*`(457) / `detector.*`(1166)로
   접두사가 붙은 predictor 구조인데 빌더는 접두사 없는 키를 기대한다 → Missing 과 Unexpected 가
   **동시에** 발생(가중치 미적재 신호). predictor 경로로 가면 `init_state() got an unexpected keyword
   argument 'offload_state_to_cpu'` 로 내부 API 도 깨진다.
3. 기준선이 이미 목표를 넘겼다(끝단 95~100%).

## ⚠️ 지금 검증된 것과 아닌 것 (sim→real 관점)

참조와 질의는 **시점·거리·조명이 독립적으로 랜덤화**됐고 구간도 다르다:

| 축 | 참조 3장 | 질의 40장 | |
|---|---|---|---|
| 거리 | 1.65~2.17m | 0.81~1.18m | ✅ 겹치지 않음 |
| 고도/방위 | 45~74° / −165~153° | 41~80° / −175~169° | ✅ |
| dome 세기 | 1506~1958 | 466~1156 | ✅ 질의가 어둡다 |
| 색온도 | 5088~6366K | 3440~5833K | ✅ |
| distractor·가림 | 없음 | 2~4개 / 95~100% | ✅ |
| **배경** | Isaac 기본 GroundPlane | **동일** | ❌ 랜덤 아님 |
| **재질·텍스처** | FOUP USD 재질 고정 | **동일** | ❌ 랜덤 아님 |

→ **이건 sim→sim 이다.** 실환경 갭의 핵심(배경, 재질·반사, 센서 노이즈·블러·자동노출, 렌더러 대 사진)은
아직 시험대에 오르지 않았다. **그리고 그 축들이 정확히 exemplar 방식이 취약할 수 있는 지점**이다 —
참조가 "이렇게 생긴 것" 을 알려주는 방식이라 외관 통계가 벌어지면 흔들릴 수 있다. ISM 은 CAD 형상
템플릿이라 텍스처 의존이 덜할 가능성이 있으나 **이것도 추측이고 데이터가 없다.**

---

# ★★★★ 근접 pose 재실험 — **"다단계 기각" 결론이 뒤집혔다** (2026-08-08)

> 📐 **측정 조건** — `foup_300_semi` · `fx 1200 @1280×720` · **근접 0.35~0.49m** (원거리 0.8~1.2m 대조) · **n=40** · stereo depth.

`§M5 확장` 에서 "근접 2단계는 세 방식 모두 회전이 악화되므로 기각" 이라고 적었다.
**그 결론은 틀렸다** — 정확히는 **당시의 외관 조건에서만 참**이었다. 조건 세 가지를 바꾸자 뒤집혔다:

| 바뀐 것 | 이전 | 이후 |
|---|---|---|
| 조명 | 실외 HDRI 포함, 물체 포화 16~47% | **실내 HDRI 만**, 포화 0.2% |
| `top_flange` 외관 | CAD 기본 재질(몸체와 유사) | **검정 고정색**(실물 FOUP) |
| 근접 flange 마스크 | SAM3, IoU 0.905 | **IoU 0.983 · 오선택 0/40** |

## ★ 결과 — 근접 flange 단독이 **모든 구성 중 최고**다

`dr2_far`(0.8~1.2m) / `dr2_near`(0.35~0.49m), 각 40프레임, fx1200, ISM+center(far) · SAM3 flange(near):

| 구성 | R° | t 평균 | t 중앙 | t 최대 | ADD | KPI |
|---|---|---|---|---|---|---|
| ① far full coarse (원거리 단일) | 0.582 | 1.85 | 1.63 | 4.12 | 2.39 | 40/40 |
| ② far full + 같은이미지 refine | 0.760 | **1.18** | 1.10 | 3.20 | 2.94 | 40/40 |
| ③ far 하이브리드 R=①, t=② | **0.582** | **1.18** | 1.10 | 3.20 | 2.47 | 40/40 |
| ④ ①을 근접 시점으로 전파(refine 없음) | 0.582 | 1.85 | 1.63 | 4.12 | 2.39 | 40/40 |
| **⑤ near flange 단독 (초기값 없음)** | **0.536** | **0.70** | **0.67** | **1.63** | **1.85** | **40/40** |
| ⑥ near flange 단독 + refine | 0.623 | 0.84 | 0.80 | 1.95 | 2.21 | 40/40 |
| ⑦ near flange + 1차 초기값 전달 | 0.624 | 0.98 | 0.85 | 2.50 | 2.23 | 40/40 |
| ⑧ **near full CAD** + 1차 초기값 | 2.285 | 6.61 | 5.02 | 21.74 | 9.00 | **20/40 = 50%** |
| ⑨ 하이브리드 R=④, t=⑦ | 0.582 | 0.98 | 0.85 | 2.50 | 2.17 | 40/40 |

**⑤ 가 ① 대비 t 를 2.6배 줄인다(1.85 → 0.70mm).** 회전도 미세하게 낫다.
이전 실험에서 같은 구성이 **R 18~24°** 였던 것과 정반대다.

## ★ 왜 뒤집혔나 — depth 가 거리를 따라 줄고, 마스크가 그걸 쓸 수 있게 했다

| flange_core | far (0.8~1.2m) | near (0.35~0.49m) |
|---|---|---|
| depth MAE | 1.510mm | **0.699mm** |
| ≤1mm 비율 | 56.1% | **89.4%** |
| disparity MAE | 0.2353px | 0.5691px |

$\\sigma_Z \\propto Z^2$ 이므로 근접의 이득은 원래 있었다. **이전에는 마스크가 그 이득을 못 쓰게 막고 있었다** —
flange 마스크 IoU 0.905(경계가 몸체와 섞임)에서는 pose 가 회전으로 흘렀고, **0.983** 이 되자 곧바로 풀렸다.
검정 flange 가 여기에 직접 기여한다(몸체·배경과 명도 분리 → 경계가 또렷하다).

## ★ 그런데 "2단계 인계" 자체는 여전히 필요 없다

- **⑤(초기값 없음) > ⑦(1차 초기값 전달)** — 초기값을 주면 오히려 나빠진다(0.70 → 0.98mm).
  근접에서 flange 마스크가 정확하면 FoundationPose 의 **전역 등록이 스스로 잘 찾는다.**
- **④ = ①** 이 정확히 일치한다 → 좌표 전파는 오차를 바꾸지 않는다(전과 동일하게 확인됨).
- **⑧ 은 실패한다**(50%). 근접에서는 FOUP 전체가 FOV 를 벗어나 full 마스크 IoU 가 0.434 로 떨어진다.
  → **근접에서는 반드시 `top_flange.ply` 로 추정한다. full CAD 를 쓰면 안 된다.**

즉 정확한 서술은 **"2단계 refine 이 좋다" 가 아니라 "근접에서 flange 로 다시 추정하는 것이 좋다"** 이다.
운용상으로는 여전히 2단계다 — 어디로 접근할지 알려면 원거리 coarse pose 가 먼저 필요하다.

## ★ 원거리만 가능할 때는 하이브리드(③)가 최선

같은이미지 refine 도 이전과 달리 **t 를 36% 개선**한다(1.85 → 1.18mm). R 만 0.582 → 0.760° 로 조금 나빠지므로
**R 은 coarse, t 는 refine** 을 취하면 둘 다 얻는다(③: R 0.582° / t 1.18mm / ADD 2.47).
`§M5 확장` 의 "refine 은 R 을 3.7배 악화" 는 옛 외관 조건의 수치다.

## ⚠️ 한계

- far/near 두 런의 **기하 짝지음이 9/40 에 그친다.** 근접 런의 가림 재시도 루프가 난수를 더 소비해
  시드가 어긋났다. 다만 ④ = ① 이 정확히 성립하므로 **pose 전파는 유효**하고, 각 구성은 자기 런의 GT 로
  평가되므로 표의 수치 자체는 타당하다. "같은 씬을 더 가까이" 라는 해석만 31프레임에서 성립하지 않는다.
- ⑦⑧ 의 상대 카메라 변환은 **GT** 를 썼다(hand-eye 대역). 실제로는 그 오차가 더해진다.
  **⑤ 는 이 문제가 없다** — 초기값을 안 쓰므로 hand-eye 정확도와 무관하다. 실사용에 유리한 성질이다.
- 근접 하한은 여전히 **0.35m**(그 아래에서 flange 가 잘리기 시작한다).

---

# ★★★ 배경·재질 randomization — 도메인 갭 첫 측정 (2026-08-08)

> 📐 **측정 조건** — `foup_300_semi` · `fx 1200 @1280×720` · 원거리 0.8~1.2m · **n=40** · **HDRI 14 + 바닥 텍스처 50 + body PBR** (flange 는 검정 고정).

지금까지 열려 있던 1순위 항목("전부 sim→sim 이다")을 처음으로 시험대에 올렸다.
**배경(HDRI) 교체 + 바닥 재질 + FOUP 몸체 재질**을 도입했다. 요구사항대로 **`top_flange` 는 고정**이다 —
pose 원점이자 SEMI 표준부이고, exemplar 참조·ISM 템플릿이 기대하는 외관이기 때문이다.

자산은 `bash envs/fetch_env_assets.sh` 로 NVIDIA 공개 버킷에서 직접 받는다(HDRI 14 + 바닥 텍스처 50, ≈760MB).
sdg_ws 에도 같은 풀이 있지만 **경로를 참조하지 않는다**(standalone 원칙).

## 실험 설계 — 짝지은 비교여야 의미가 있다

`runs/cfgD_fx1200`(기존 최선, randomization 없음) 대 `runs/dr01`(추가), **동일 seed 400**.

★ 외관 난수를 **별도 스트림**으로 분리했다. 같은 스트림에서 뽑으면 HDRI·재질 추첨이 뒤따르는
**기하 추첨(거리·고도·방위·yaw)을 통째로 밀어** 두 런이 다른 씬이 된다 — 그러면 "배경·재질 때문에
나빠졌다" 를 기하 차이와 분리할 수 없다. 분리 후 **기하 40/40 프레임이 완전히 일치**함을 확인했다.

⚠️ **조명 밴드는 바꿔야 했다.** HDRI 배경이 더해지자 기존 밴드에서 물체 픽셀의 **47%가 포화**됐다
(기준선은 16.7%). `dome 200~600 · fixture 1000~8000` 으로 낮춰 **7.3% / 밝기 203.5** 로 맞췄다
(기준선 16.7% / 205.8). 즉 **노출을 맞춘 상태의 비교**이지, 조명 조건까지 동일한 비교는 아니다.

## ★ 0. "flange 는 고정, body 만" 을 **픽셀로** 검증했다

이건 눈으로 확인할 수 없는 종류의 계약이다 — 재질 바인딩이 한 프림 위로 새면 flange 까지 물드는데
렌더 결과는 여전히 그럴듯해 보인다. 시점·조명을 완전히 고정하고 **몸체 재질만** 흔든 6프레임에서
프레임 쌍마다 |Δ| 를 쟀다(`eval.verify_randomization`):

| 영역 | 프레임 간 평균 \|Δ\| (0~255) |
|---|---|
| body | **23.458** |
| flange core (침식 후) | **0.344** = 0.13% |
| **비** | **68.3×** |

flange 잔여 0.13% 는 **몸체에서 반사된 간접광**이다 — 물리적으로 옳다. 그래서 판정은 절대값이 아니라
**비**로 한다(조명까지 흔들면 두 영역이 함께 변하므로 절대 문턱은 무의미하다).

### ⚠️ 여기서 조용한 실패를 하나 잡았다 — `bind_prims` 는 참조 안 프림에 안 걸린다

`rep.functional.create.material(mdl=..., bind_prims=[body_prim])` 가 **예외 없이 실패한다.**
`material:binding` 관계는 생기는데 **타깃이 비어 있고**, `ComputeBoundMaterial()` 은 None 이다.
첫 측정에서 body |Δ| 가 0.466(렌더 노이즈 수준), 비 1.4× 로 나와서 발견했다.

조건이 명확하다 — **루트 레이어에 스펙이 없는 프림**(참조 안에서만 정의된 프림):

| 대상 | `PrimStack` | `bind_prims` 결과 |
|---|---|---|
| `/World/sphere` (직접 생성) | 루트 레이어 | ✅ 걸린다 |
| `/World/foup` (참조 **루트**) | 루트 레이어 | ✅ 걸린다 — **그러나 flange 까지 물든다** |
| `/World/foup/body` (참조 **내부**) | `mesh.usda` | ❌ **조용히 실패** |

우리 케이스가 정확히 세 번째다. 처방: 재질만 만들고 바인딩은 `UsdShade.MaterialBindingAPI(p).Bind()`
로 **직접** 하고 **반환값과 `ComputeBoundMaterial()` 을 둘 다 확인**한다(`scene_random._make_material`).
추가로 setup 에서 `top_flange` 에 재질이 걸렸는지 검사해 걸렸으면 즉시 실패시킨다.

## ★ 1. 결론 — 형상 기반은 버티고, 외관 기반은 무너진다

| 단계 | 지표 | 기준선(randomization 없음) | **배경·재질 randomization** | |
|---|---|---|---|---|
| depth | flange_core MAE | 2.164mm | **1.379mm** | ✅ **좋아짐** |
| depth | 전체 화면 MAE | 34.404mm | **1.780mm** | ✅ **크게 좋아짐** |
| seg | **ISM** IoU / 오선택 | 0.938 / 0/40 | **0.927 / 0/40** | ✅ 유지 |
| seg | **SAM3 exemplar** IoU / 오선택 | 0.862 / 1/40 | **0.382 / 4/40** | ❌ **붕괴** |
| seg | SAM3 exemplar — **참조 재생성 후** | 〃 | **0.872 / 0/40** | ✅ **회복**(§5) |
| pose | ISM 마스크 R / t | 0.604° / 2.09mm | **0.612° / 2.24mm** | ✅ 유지 |
| pose | ISM 마스크 **끝단** | **40/40 = 100%** | **40/40 = 100%** | ✅ **유지** |
| pose | SAM3 마스크 **끝단** | 38/40 = 95% | 37/40 = 92.5% | ⚠️ 완만 |
| pose | SAM3 — **참조 재생성 후 끝단** | 〃 | **40/40 = 100%** | ✅ **회복**(§5) |

**현행 최선 조합(ISM + select center)은 배경·재질 randomization 하에서도 40/40 을 유지한다.**
이건 예상된 방향이지만 **처음으로 측정된** 것이다.

## ★ 2. depth 가 **좋아졌다** — 기준선이 스테레오에 부당하게 어려웠다

전체 화면 MAE 가 34.4 → 1.78mm, bias 가 +31.7 → −0.28mm 로 바뀌었다. 원인은 **텍스처 없는 바닥**이다:
무지 회색 평면은 스테레오 대응점이 없어 disparity 가 통째로 틀린다(disp MAE 1.054 → 0.182px).
바닥에 PBR 텍스처가 들어가자 정상화됐다.

| 영역 | 기준선 MAE | randomization | disp 기준선 → 후 |
|---|---|---|---|
| 전체 | 34.404mm | **1.780mm** | 1.0543 → **0.1822px** |
| obj_core | 2.276mm | **1.848mm** | 0.3164 → **0.2565px** |
| flange_core | 2.164mm | **1.379mm** | 0.3047 → **0.1975px** |

→ **기존 depth 수치는 비관적이었다.** 실환경의 바닥·물체는 텍스처가 있다. 다만 노출도 함께 개선됐으므로
(포화 16.7% → 7.3%) 두 효과가 섞여 있다 — **텍스처만의 기여로 분리되지 않았다.**

## ★ 3. SAM3 exemplar 는 **randomize 하지 않은 부분에 달라붙는다**

IoU 0.862 → **0.382**, recall 0.941 → **0.409**. 그런데 precision 은 0.909 → 0.880 으로 거의 그대로다 —
**틀린 곳을 잡는 게 아니라 물체의 일부만 잡는다.** 어느 부분인가:

| | 값 | |
|---|---|---|
| 예측 vs GT **full** IoU | 0.382 | |
| 예측 vs GT **flange** IoU | **0.565** | ← 더 높다 |
| 예측 픽셀 중 flange 비율 | **57.0%** | GT 에서의 기대치는 **12.7%** |

**몸체 재질이 참조와 달라지자 exemplar 매칭이 유일하게 안 변한 부분 — flange — 로 후퇴했다.**
"flange 는 고정, body 만 randomize" 라는 설계 선택이 만든 직접적 귀결이고, exemplar 방식이
**외관에 묶여 있다**는 것을 인과적으로 보여준다. ISM 은 CAD **형상** 템플릿이라 같은 조건에서
IoU 0.927 을 유지한다 — 두 방식을 계속 병행해온 이유가 여기서 처음으로 수치가 됐다.

## ★ 4. 그래도 pose 는 덜 무너진다 — 마스크 IoU 와 pose 실패는 다른 축이다

| SAM3 마스크로 pose | R | t 평균 | t 중앙 | **끝단** |
|---|---|---|---|---|
| 기준선 (IoU 0.862) | 0.599° | 20.90mm | 1.94 | **38/40 = 95%** |
| randomization (IoU 0.382) | 4.085° | 41.42mm | 2.22 | **37/40 = 92.5%** |

**마스크 IoU 는 2.3배 나빠졌는데 끝단 성공률은 95% → 92.5% 로 1건 차이다.**
FoundationPose 는 마스크가 **물체 위에 있기만 하면** 부분 마스크를 상당히 견딘다 — 그리고 SAM3 가
후퇴한 곳이 하필 **flange**(=pose 앵커) 여서 남은 부분이 쓸모 있었다.
평균 t 가 20.9/41.4mm 인 것은 대실패 1~2건 때문이고 중앙값은 2mm 대다(#15 와 같은 형태).

→ **IoU 로 pose 실패를 예측하면 안 된다.** 두 지표는 다른 축이다.

## ★★ 5. 처방 — 참조를 **randomization 을 켠 채** 다시 만들면 완전히 회복된다

붕괴의 원인이 "참조와 질의의 외관 분포가 다르다" 라면, 참조를 질의와 같은 분포에서 뽑으면 된다.
`runs/dr01` 과 **다른 seed(901)** 의 랜덤화된 단일객체 런 8프레임에서 참조 3장을 다시 만들었다
(자기순환이 아니다 — 질의 프레임을 참조로 쓰지 않았다):

| 참조 세트 | 검출 | 오선택 | IoU | precision | recall | **pose 끝단** |
|---|---|---|---|---|---|---|
| 클린 씬 3장 (기존 자산) | 39/40 | 4 | 0.382 | 0.880 | 0.409 | 37/40 = 92.5% |
| **랜덤화 씬 3장 (재생성)** | **40/40** | **0** | **0.872** | **0.987** | **0.883** | **40/40 = 100%** |
| (참고) ISM CAD 템플릿 | 40/40 | 0 | 0.927 | 0.981 | 0.945 | 40/40 = 100% |

**완전히 회복될 뿐 아니라 기준선(38/40)보다 좋아졌다.** exemplar 방식의 취약성은 **고칠 수 있는 종류**였다.

⚠️ 다만 **두 가지가 동시에 바뀌었다**: 참조의 외관 분포(클린→랜덤)와 **거리**(1.65~2.17m → 1.04~1.19m,
질의는 0.81~1.18m). §M5 확장 §5 에서 거리 불일치가 치명적일 수 있음을 이미 봤으므로, 회복분 중
얼마가 외관이고 얼마가 거리인지는 **분리되지 않았다.** 다만 **붕괴** 쪽은 깨끗하다 —
동일한 참조로 클린 질의는 0.862, 랜덤 질의는 0.382 였으므로 거리로는 설명되지 않는다.

→ **운영 규칙**: SAM3 참조 자산은 **배포 조건(거리 + 배경·재질 randomization)에서 렌더**한다.
`build_sam3_refs.py --from` 에 랜덤화된 런을 준다.

## ⚠️ 6. 여전히 검증되지 않은 것

랜덤화된 축과 아닌 축을 분리해 둔다:

| 축 | 상태 |
|---|---|
| 배경(HDRI 14종, 회전 0~360°) | ✅ |
| 바닥 재질·텍스처(50종) | ✅ |
| FOUP **몸체** 색·거칠기·금속성 (타깃·distractor 독립) | ✅ |
| **`top_flange` 외관** | ❌ **의도적으로 고정**(요구사항) |
| 몸체 텍스처 | ⬜ `--body-textures` 로 가능하나 미측정 |
| 센서 노이즈·모션블러·자동노출 | ❌ |
| 렌더러 대 실제 사진 | ❌ |
| 실제 카메라 intrinsic·왜곡 | ❌ (M6) |

→ **여전히 sim→sim 이다.** 다만 "배경·재질" 축은 이제 **비어 있지 않다.**

---

# ★★ M5 확장 — 근접 / 2단계 / flange 전용 (2026-08-08)

> 📐 **측정 조건** — `foup_300_semi` · **`fx 952/1200/1400 @1280×720`** · 거리 0.35~0.50m ~ 1.0~1.4m 여러 조합 · **n=40**.

> ⚠️ **이 절의 §6·§7 결론(다단계 기각)은 이후 뒤집혔다.** 조명·flange 외관·마스크 품질을 바꾸자
> 근접 flange 단독이 **최고 성능**이 됐다(t 1.85 → **0.70mm**). **`§근접 pose 재실험` 을 먼저 볼 것.**
> 아래 수치는 "옛 외관 조건에서는 이랬다" 는 기록으로만 유효하다. §1~§5(측면 오차·FOV·전용 자산·참조 거리)는
> 그대로 유효하다.

물음은 하나였다: **"1m 에서 1차 pose 를 잡고, 더 다가가서 2차로 정밀화하면 정확해지지 않나?"**
(FoundationPose 의 같은-이미지 2-stage 를 **카메라를 실제로 움직이는** 방식으로 바꾼 것.)

답은 **아니다** 였다. 그 과정에서 측면 오차의 정체, FOV 가정, flange 전용 자산의 비대칭이 함께 드러났다.

## ★ 1. 측면 오차 ~1.7mm 는 해상도 한계가 **아니다**

대실패를 뺀 프레임에서 t 오차를 **측면(√(dx²+dy²))·깊이(|dz|)** 로 분해하고, 측면 오차를
`px = 측면mm × fx / Z` 로 픽셀 환산했다:

| 구성 | fx | Z 중앙 | 측면 mm | 깊이 mm | **환산 px** |
|---|---|---|---|---|---|
| A fx952 0.8~1.2m | 952 | 1.00m | 1.89 | 1.30 | 1.80 |
| B fx1400 0.8~1.2m | 1400 | 1.00m | 1.65 | 1.21 | **2.32** |
| C fx1200 0.8~1.2m | 1200 | 1.00m | 1.66 | 1.11 | 1.99 |
| D fx1200 1.0~1.4m | 1200 | 1.20m | 2.01 | 1.09 | 2.00 |
| F fx952 0.5~0.7m | 952 | 0.59m | 1.57 | 0.79 | **2.51** |
| G fx952 0.71~0.9m | 952 | 0.83m | 1.29 | 1.08 | 1.51 |

**mm 는 1.3~2.0 로 거의 일정한데 환산 px 는 1.5~2.5 로 흔들린다.** 해상도가 한계라면 반대여야 한다
(px 가 상수이고 mm 가 `Z/fx` 를 따라 줄어야 한다). 즉 이 오차는 **객체 좌표계에서 대략 고정된 정합
한계**이고, **fx 를 올리거나 거리를 줄여도 줄지 않는다.** 픽셀 해상도를 더 부어도 되찾을 게 없다.

깊이 오차만 거리를 따라 줄어든다(1.30 → 0.79mm). 근접의 이득은 **깊이축에만** 있다.

## ★ 2. 조합 재평가 — fx 를 올려도 이득이 없다

`ISM + select center` 마스크, GT 아닌 stereo depth, 40프레임. **coarse** 기준(refine 은 §M5 참조):

| 구성 | R° | t 평균 | t 중앙 | ADD | **끝단** |
|---|---|---|---|---|---|
| A fx952 0.8~1.2m | 0.618 | 2.39 | 2.41 | 2.92 | **40/40 = 100%** |
| **C fx1200 0.8~1.2m** | **0.604** | **2.09** | **2.01** | **2.85** | **40/40 = 100%** |
| D fx1200 1.0~1.4m | 0.633 | 2.48 | 2.11 | 2.95 | 39/40 = 97.5% |
| E fx952 0.8~1.2m · exemplar 3장 | 0.626 | 2.25 | 2.06 | 3.03 | 38/40 = 95% |
| B fx1400 0.8~1.2m | 4.577 | 14.43 | 2.15 | 17.03 | 38/40 = 95% |
| F fx952 0.50~0.70m | 0.714 | 2.00 | 1.71 | 2.96 | 39/40 = 97.5% |
| G fx952 0.71~0.90m | 5.079 | 21.23 | 1.90 | 22.03 | 39/40 = 97.5% |

- **A 와 C 의 차이는 오차범위다**(2.39 vs 2.09mm, 둘 다 40/40). fx 952→1200 은 사실상 무의미하고,
  §1 이 그 이유를 설명한다. **렌즈를 바꿀 이유가 없다.**
- **B(fx1400)·G 의 평균이 큰 것은 성능 저하가 아니라 각 1프레임의 오선택이다** — 중앙값은 2.15/1.90mm 로
  멀쩡하다. 두 실패 프레임의 마스크 IoU 는 **0.001 / 0.000** (`cfgB…/frame_0028`, `near07…/frame_0008`).
  → **남은 실패는 전부 마스크 선택 문제다.** depth·pose 문제가 아니다(§M2 확장 절제 실험과 일치).
- 근접(F, 0.5~0.7m)이 t 를 2.39 → 2.00mm 로 조금 낮추지만 **KPI 통과 수를 늘리지는 못한다.**

## ★ 3. "FOUP 전체가 FOV 에 들어와야 한다" 는 **필요조건이 아니다**

작업 가정이었지만 데이터가 반증했다. `mask_full` 이 이미지 테두리에 닿으면 "잘림" 으로 셌다
(대실패 제외):

| 구성 | 온전 프레임 | 잘린 프레임 |
|---|---|---|
| C fx1200 0.8~1.2m | n=13 · t **2.34**mm · R 0.684° | n=27 · t **1.97**mm · R 0.566° |
| B fx1400 0.8~1.2m | n=8 · t 2.67mm · R 0.842° | n=31 · t **2.29**mm · R 0.610° |
| F fx952 0.5~0.7m | n=5 · t 2.64mm · R 1.028° | n=35 · t **1.90**mm · R 0.669° |

**잘린 쪽이 오히려 근소하게 정확하다.** 잘림이 곧 "가깝다 = 투영 면적이 크다" 와 같은 방향이기 때문이고,
FoundationPose 는 마스크만 옳으면 부분 관측을 문제없이 다룬다. C 는 27/40 이 잘렸는데도 **40/40** 이다.

→ **운용 제약은 "FOUP 전체" 가 아니라 "flange 가 온전히, 충분한 면적으로" 다.** 전 구성에서
flange 잘림은 0/40 이었다(§6 의 0.3~0.5m 구간만 3/40). 기존 기준 **flange 투영 ≥4,000px** 이 유효하다.

## ★ 4. flange 전용 자산 — SAM3 는 되고 ISM 은 **안 된다**

"flange 만 가리키는 참조/템플릿을 주면 flange 마스크가 더 좋아지지 않나" 를 시험했다
(fx952, 0.8~1.2m, 40프레임, 타깃 = flange):

| 방식 | 검출 | **오선택** | IoU(전체) | IoU(정상) | precision | recall |
|---|---|---|---|---|---|---|
| **SAM3 exemplar — flange 참조 3장** | 40/40 | **0** | **0.879** | 0.879 | 0.986 | 0.891 |
| **ISM — flange 전용 CAD 템플릿** | 40/40 | **23** | 0.382 | 0.898 | 0.389 | 0.420 |

**정상 프레임의 IoU 는 거의 같다(0.879 vs 0.898). 갈리는 것은 오선택 23/40 이다.**
ISM 은 CAD 형상 렌더와 매칭하는데, flange 만 떼면 **"위에서 본 판때기 + 구멍"** 이라 변별력이 사라져
distractor FOUP 의 flange 나 배경 평면을 자신 있게 집는다. exemplar 는 참조 이미지가 곧 지정이라
이 문제가 없다.

→ **비대칭이 확인됐다**: ISM 은 **전체 형상 템플릿**으로만 써야 하고(전체 타깃 오선택 0/40),
flange 마스크가 따로 필요하면 **전체 pose 에서 투영**하거나 **SAM3 flange 참조**를 쓴다.

## ★ 5. 참조 이미지는 **배포 거리에서** 만들어야 한다

앞서 "참조 시점은 무관하다" 고 적었는데(§M2 확장 §4), **거리에는 해당하지 않는다.**
0.3~0.5m 질의 40프레임에 참조만 바꿨다:

| 참조 세트 | 참조 거리 | 오선택 | IoU |
|---|---|---|---|
| 원거리 참조(기존 자산) | 1.65~2.17m | **40/40** | **0.044** |
| 근접 참조(재생성) | 0.35~0.49m | 0 | **0.905** |

flange 투영 면적이 **34배** 차이 나면 같은 물체로 보지 않는다. **"시점(방위·고도)은 무관, 거리(스케일)는
치명적"** 이 정확한 표현이다. → `build_sam3_refs.py` 는 **배포 작업거리에서 렌더한 런**으로 돌린다.

## ★ 6. 근접 flange **단독** pose 는 붕괴한다

0.3~0.5m 에서 flange 만으로 pose 를 잡아 봤다(초기값 없음, 40프레임):

| 마스크 | R° | t mm |
|---|---|---|
| flange 마스크 (a) | **24.24** | 87.71 |
| flange 마스크 (b, IoU 0.905) | **18.17** | 17.05 |

**마스크 품질 문제가 아니다**(IoU 0.905 인데도 18°). flange 는 원판 + 중심 홀 + 약한 비대칭이라
**Z 축 회전 구속이 거의 없다.** 마스크를 아무리 잘 줘도 해가 축 주위로 퍼진다.
이 구간은 `mask_full` 이 40/40 잘리므로(§3) 전체 pose 로 대체할 수도 없다.

**근접 작업 하한**: fx1200 에서 **0.35m**. 그 아래에서는 flange 자체가 FOV 를 벗어나기 시작한다
(0.3~0.5m 구간에서 flange 잘림 3/40).

## ★ 7. 카메라 이동 2단계 — 하이브리드까지 해도 **1차만 못하다**

> ⚠️ **이 절의 결론은 폐기됐다.** → `§근접 pose 재실험`(2026-08-08) 과 `§flange 의 회전 구속`(2026-08-09).
> 표의 수치 자체(`cfgD_2stage`)는 유효하지만 **해석이 둘 다 틀렸다**:
> ① 원인은 "flange 의 약한 회전 구속" 이 아니다 — 이 런의 **90° 대칭 혼동은 0/40** 이고,
>    형상에는 최대 8.3mm 의 비대칭이 실재한다.
> ② "다단계 채택 안 함" 은 반대로 뒤집혔다 — **근접 flange 단독 재추정이 모든 구성 중 최고**다
>    (R 0.536° / t 0.70mm / 40/40). 이 절이 실패한 것은 **1차 초기값을 전달했기 때문**이다.
> 아래는 기록 보존용으로만 남긴다.

같은 씬을 원거리(0.81~1.18m)와 근접(0.35~0.50m) **두 번** 캡처해 프레임을 짝지었다(동일 seed·동일
객체 자세). 1차 pose 를 상대 카메라 변환으로 근접 시점에 옮겨 초기값으로 주고, flange 로 refine 했다.

| 구성 | R° | t 평균 | t 중앙 | t 최대 | ADD | **KPI** |
|---|---|---|---|---|---|---|
| **① 1차 full (원거리)** | **0.604** | **2.09** | 2.01 | **4.40** | **2.69** | **40/40 = 100%** |
| ② ①을 근접 시점으로 전파(refine 없음) | 0.604 | 2.09 | 2.01 | 4.40 | 2.69 | **40/40 = 100%** |
| ③ 근접 flange refine (②를 초기값으로) | 3.432 | 2.97 | **1.64** | 11.58 | 13.48 | 24/40 = 60% |
| ④ 하이브리드 R=①, t=③ | 0.604 | 2.97 | 1.64 | 11.58 | 3.91 | 30/40 = 75% |

**①과 ②가 완전히 같다** — 좌표 변환은 정확도를 바꾸지 않는다(변환이 정확함의 확인이기도 하다).
그리고 **③의 refine 이 넣는 것은 이득이 아니라 손해다.**

**하이브리드가 안 되는 이유**: ③의 t **중앙값은 1.64mm 로 ①(2.01mm)보다 좋지만 평균은 2.97mm 로
나쁘다.** 분포가 오른쪽으로 길다 — 대부분 프레임은 개선되고 일부가 크게 틀어져 KPI 를 깎는다
(t 최대 4.40 → 11.58mm). **중앙값만 보고 우열을 판단하면 정반대 처방이 나온다.**

⚠️ 상대 카메라 변환 `T = cam2_T_obj_gt · inv(cam1_T_obj_gt)` 는 **GT 를 썼다** — 실제로는 로봇
hand-eye 로 얻어야 하고, 그 오차가 위 수치에 **추가로** 얹힌다. 즉 위 표는 2단계에 **가장 유리한** 조건이다.

### 결론 — 2단계는 세 번 시도해 세 번 같은 벽에 부딪혔다

| 시도 | 결과 |
|---|---|
| 같은 이미지에서 flange refine (§M5) | R 0.349° → **1.282°** 악화 |
| 근접에서 flange 단독 추정 (§6) | R **18~24°** (회전 구속 붕괴) |
| 근접 + 1차 초기값 전달 + refine (§7) | R 0.604° → **3.432°** 악화 |

원인은 일관되게 **flange 형상의 약한 회전 구속**이고, 초기값을 아무리 정확히 줘도 refine 단계가
그 초기값에서 회전을 끌고 나간다. **다단계 pose 는 채택하지 않는다.**
로봇이 근접해야 한다면 **원거리 pose 를 좌표변환해서 쓰면 된다**(② = 100%).

남은 여지: refine 을 **회전 고정·평행이동만** 최적화하도록 바꾸면 §1 이 보인 근접의 깊이 이득
(1.30 → 0.79mm)만 취할 수 있다. FoundationPose 의 refiner 는 6DoF 를 함께 푸는 구조라 그대로는 안 되고,
flange 영역 depth 의 평면/축 맞춤을 별도로 짜야 한다. **다만 지금 이득은 최대 0.5mm 이고 KPI 여유는
2.9mm 다** — 우선순위가 낮다.

---

# ★★★ flange 의 회전 구속을 실제로 재봤다 — "약하다" 는 **부정확했다** (2026-08-09)

> 📐 **측정 조건** — `foup_300_semi` 메쉬 기하 분석 + `runs/dr2_near`(`fx 1200 @1280×720`, 근접 0.35~0.50m, **n=40**).

`§M5 확장 §6-7` 이 근접 flange pose 의 실패 원인을 **"flange 형상의 약한 회전 구속"** 이라고 적었다.
CAD 로 직접 측정하니 **원인 규정이 틀렸다.** 형상에는 방향 정보가 있고, 실패는 다른 이유였다.

측정 방법: `top_flange.ply` 를 Z 축으로 θ 회전시켜 원래 형상과의 표면거리를 잰다.
차이가 작으면 = 그 각도로 착각해도 관측이 같다 = 회전이 구속되지 않는다.

## ★ 1. 외곽 테두리는 4중 대칭이 **아니다**

`r(φ)` 를 사분면별로 접어서 비교(단위 mm):

| 사분면 내 방위 | Q1 | Q2 | Q3 | Q4 | **편차** |
|---|---|---|---|---|---|
| 0° (변 중앙) | 66.00 | 66.00 | 66.00 | 66.00 | 0.00 |
| 30° | 82.92 | 85.44 | 82.40 | 84.52 | 3.04 |
| 35° | 83.36 | 88.19 | 83.36 | 87.72 | 4.83 |
| 40~50° (모서리) | 91.57 | 91.57 | 91.57 | 91.57 | 0.00 |
| 60° | 84.52 | 82.71 | 82.59 | 85.95 | 3.36 |
| **65°** | 81.32 | 74.55 | 74.53 | 82.85 | **8.32** |
| 70° | 78.12 | 74.94 | 74.94 | 79.75 | 4.81 |

**모서리와 변 중앙은 정확히 4중 대칭인데, 그 사이 모따기 구간이 사분면마다 최대 8.3mm 다르다.**
비대칭 구간 7군데, 호길이 4~29mm. 중심 홀은 진원도 0.009mm 의 완전한 원이라 **yaw 정보가 0** 이다 —
방향은 전적으로 테두리에서만 나온다.

> ⚠️ **함정**: 처음에 0.4mm 격자에서 "4중 대칭 잔차 median 0.00mm" 만 보고 *완전 대칭*이라고 결론냈다.
> 같은 출력의 `max 5.83mm` 를 무시한 것이다. **§횡단 정리 6번(평균이 고장을 숨긴다)을 그대로 밟았다.**
> 물체 프레임이 아닌 `trimesh.to_2D()` 프레임에서 재면 중심이 어긋나 **가짜 비대칭**이 나온다
> (최대반경 91.68 → 99.90 으로 어긋나는 것이 신호다). 회전 대칭은 **반드시 pose 원점 기준으로** 잰다.

## ★ 2. 그런데 그 정보는 표면의 3.5% 뿐이고, 전부 **경계**에 있다

| θ | median | p95 | p99 | max |
|---|---|---|---|---|
| **90°** | 0.0000 | **0.0035** | 2.80 | 4.68 |
| 180° | 0.0000 | 0.0022 | 2.81 | 4.71 |
| 45° (대조) | 0.616 | 14.34 | 20.2 | 21.9 |

**표면의 96.5% 는 90° 돌려도 동일하다.** 대칭을 깨는 3.5% 의 위치:

- Z −8~0mm, 반경 55~89mm — **상판 아래 단차/언더컷**
- 그중 상면(Z > −1mm, 위에서 보이는 곳)에 있는 것은 전체 표면의 **0.167%**
- 위에서 본 높이맵: 가시 면적의 **93.5% 가 0.22mm 이내 단일 평면**, 90° 회전 시 높이가 1mm 이상
  달라지는 영역은 **1.9mm² (0.01%)**

비교로 `full.ply` 는 어떤 차수의 대칭도 없다(최소 잔차 21.0mm). 90° 회전 시 면적 **20.7%** 가 1mm 이상
달라지고 평균 |Δz| 가 **5.46mm** 다 — flange 대비 회전 신호가 **340배**.

## ★ 3. 실측이 확인해준다 — 정보는 충분하고, 실제로 쓰인다

`pose_gt` 대비 R 오차, 그리고 **물체 Z축 90° 배수를 허용했을 때의 잔여 오차**로 대칭 혼동을 분리:

| 런 | R med | R avg | R max | **90°/180° 혼동** |
|---|---|---|---|---|
| `dr2_near_flonly` coarse (현행 최선) | 0.505 | **0.536** | 1.13 | **0/40** |
| `cfgD_2stage` coarse (§7 의 3.432°) | 1.796 | 3.432 | 11.62 | **0/40** |
| `flange_near_pose` coarse (옛 조건) | 3.502 | 24.240 | 176.6 | **5/40** |

- **현행 최선은 40프레임 전부 대칭 혼동 0건.** 테두리의 8mm 비대칭이 실제로 쓰이고 있다.
- **`§7` 이 인용한 3.432° 도 혼동 0건이었다** → 애초에 대칭 문제가 아니었다. 원인은 §근접 pose 재실험이
  이미 밝힌 대로 **1차 초기값을 전달한 것 자체**다(⑤ 0.70mm > ⑦ 0.98mm).
- 옛 조건에서는 실제로 붕괴했다: `frame_0009` 91.90° → 90° 대칭해 기준 잔여 7.14°,
  `frame_0000` 176.58° → 180° 기준 잔여 18.72°.

**같은 CAD·같은 형상인데 결과가 갈렸다** = 형상이 아니라 **관측 품질**이 변수다.

## ★★ 4. 그래서 `flange 마스크 IoU ≥ 0.98` 조건의 근거가 설명된다

yaw 를 정하는 신호는 표면의 3.5%, 전부 **테두리 경계**에 몰려 있다. 마스크 경계가 흔들리면
**가장 먼저 사라지는 것이 정확히 그 부분**이다. flange 면적 19,700mm² 에서 IoU 2% 오차 ≈ 400mm² 로,
비대칭 신호 총량과 같은 자릿수다.

→ **회전 안정성의 지렛대는 refiner 가 아니라 테두리 마스크 경계 품질이다.**

## 재현

```bash
# 회전 대칭 잔차 / 테두리 r(φ) / 90° 를 깨는 기하의 위치
envs/cad/bin/python -m spatial_vision.cad.measure_symmetry --obj assets/obj/foup_300_semi
```

---

# ★★★ 실카메라 depth 오차 예산 — D435 실측 17mm 의 정체 (2026-08-09)

> 🔬 **sim 이 아니다 — 실측 D435 데이터 기반 역산**(σ_disp·`fx·B` 예산). ⚠️ 카메라 간 외삽은 「sim D435 재현 실험」 절에서 **철회**됐다.

실환경 예비 측정(사용자 보고): **RealSense D435 + FoundationStereo 로 Z 오차 ≈ 17mm.**
KPI(5mm)의 3.4배다. 계산해보면 **FoundationStereo 의 실패가 아니라 D435 의 baseline 한계**다.

## ★ 1. 17mm 를 시차 오차로 역산하면 정상 성능이다

D435 는 IR쌍 baseline 50mm, depth FOV 87° → `fx ≈ 674 @1280×720`, 따라서 `fx·B = 33,700`.
`σ_Z = Z²/(fx·B) · σ_disp` 이므로:

| 측정 거리였다면 | 필요한 σ_disp |
|---|---|
| 0.8m | 0.895 px |
| **1.0m** | **0.573 px** |
| 1.2m | 0.398 px |

**0.4~0.9px 는 학습 기반 스테레오로서 정상~우수하다.** 알고리즘은 제 몫을 했다.

## ★ 2. 카메라별 증폭 배율 — D435 는 우리 검증 조합보다 4.3배 불리하다

시차 1px 오차가 만드는 깊이 오차(mm):

| 카메라 | fx@1280×720 | B mm | fx·B | 상대 | 0.4m | 0.6m | 1.0m | 1.5m |
|---|---|---|---|---|---|---|---|---|
| **D435** | 674 | 50 | 33,700 | 0.23× | 4.7 | 10.7 | **29.7** | 66.8 |
| D455 | 674 | 95 | 64,030 | 0.44× | 2.5 | 5.6 | 15.6 | 35.1 |
| ZED 2i (4mm) | 1050 | 120 | 126,000 | 0.88× | 1.3 | 2.9 | 7.9 | 17.9 |
| **ZED X (4mm)** ← sim 검증 조합 | 1200 | 120 | 144,000 | 1.00× | 1.1 | 2.5 | **6.9** | 15.6 |

## ★ 3. "Z 만 크게 튄다" 도 baseline 으로 설명된다

같은 픽셀 오차가 Z 와 X/Y 에 미치는 영향 비는 정확히 **Z / baseline**:

| | 0.4m | 0.6m | 1.0m | 1.5m |
|---|---|---|---|---|
| D435 (B=50) | 8.0× | 12.0× | **20.0×** | 30.0× |
| ZED X (B=120) | 3.3× | 5.0× | 8.3× | 12.5× |

`CONSUMER_6DPOSE.md §2.6` 의 *"X/Y·rotation 은 안정적, Z 만 크게 튄다(mean ~15mm)"* 는 이상 증상이
아니라 **baseline 50mm 카메라의 정상 거동**이다. 별도 원인을 찾을 필요가 없다.

## ★★ 4. D435 는 1m 에서 5mm KPI 를 만족할 수 없다

KPI 예산을 depth 가 전부 쓴다고 볼 때의 최대 작업거리(괄호는 예산 절반만 쓸 때):

| σ_disp | D435 | D455 | ZED 2i | ZED X |
|---|---|---|---|---|
| 0.3 px | 0.75m (0.53) | 1.03m (0.73) | 1.45m (1.02) | 1.55m (1.10) |
| **0.5 px** | **0.58m (0.41)** | 0.80m (0.57) | 1.12m (0.79) | 1.20m (0.85) |
| 0.9 px | 0.43m (0.31) | 0.60m (0.42) | 0.84m (0.59) | 0.89m (0.63) |

측면 오차 ~1.7mm 가 따로 있으므로 **실제로는 괄호 쪽 값을 봐야 한다.**
D435 로 1m 에서 5mm 를 맞추려면 σ_disp **0.17px** 이 필요한데 실사진에서는 도달 불가능하다.
→ **카메라를 바꾸거나 가까이 가는 것 외에 방법이 없다.** refiner 로는 못 고친다(관측 바닥이다).

## ⚠️ 5. ~~sim 수치와의 정합~~ — **이 절의 외삽은 틀렸다** (2026-08-09 정정)

여기에 *"같은 σ_disp(0.573px)를 ZED X @0.43m 에 대입하면 0.74mm → sim 실측 0.70mm 와 일치.
따라서 카메라 기하만 맞추면 sim 을 실환경 예측에 쓸 수 있다"* 라고 적었다.
**sim 에서 D435 기하를 직접 캡처해 재보니 두 전제가 모두 깨졌다.**
→ `§ sim D435 재현 실험`. 요약:

1. **σ_disp 는 카메라 간에 전이되지 않는다.** 시차가 큰 카메라일수록 절대 px 오차도 크다
   (1.0m 에서 D435 0.086px vs ZED X 0.207px). `fx·B` 4.27배의 이득이 실제로는 **1.7~2.1배**다.
2. **거리 지수가 2 가 아니라 ~0.8~1.0 이다.** σ_disp 가 거리에 따라 줄어 Z² 를 상쇄한다.
3. **카메라 기하를 맞춰도 sim 이 실환경보다 4.5~11.6배 좋다.** 0.70mm 와 0.74mm 가 맞아떨어진 것은
   **두 오차가 상쇄된 우연**이었다.

`§1~4`(σ_disp 역산, 카메라별 fx·B 표, Z/baseline 비, D435 의 거리 한계)는 유효하다 — 그것들은
**같은 카메라 안에서의** 관계이거나 상한 계산이다. 무효인 것은 **카메라를 건너뛴 외삽**뿐이다.

## ⚠️ 6. 이 결론은 "17mm 이 랜덤 산포" 라는 가정 위에 있다

계통 편향이면 처방이 완전히 달라진다. **거리 의존성이 세 원인을 구분한다:**

| 원인 | 거리 의존성 | 거리 2배면 | 처방 |
|---|---|---|---|
| 시차 랜덤오차 | ∝ Z² | 4배 | 카메라(baseline)·거리 |
| **baseline 스케일 오차** | ∝ Z | 2배 | **재캘리브레이션** (카메라 바꿔도 안 나음) |
| 고정 오프셋(원점·정렬) | ∝ Z⁰ | 그대로 | 원점 규약 점검 |

1.0m 에서 17mm 를 스케일 오차로 설명하려면 **baseline 이 0.85mm(1.7%) 틀어진 것**과 동등하다 —
D435 공장 캘리브레이션 드리프트로 충분히 가능한 크기다.

**진단**: 같은 물체를 0.5 / 1.0 / 1.5m 에서 재고 오차의 **거리 지수**를 맞춘다. M6 최우선 항목.

미확인 요인 하나 더: **D435 IR 프로젝터 도트 패턴**. FoundationStereo 는 자연 이미지로 학습돼
인공 도트가 방해가 될 수 있다(고전 스테레오는 반대로 이득). 껐다/켰다 비교로 σ_disp 개선 여지를 알 수 있다.

## SCFlow2 (pose refinement) 검토 — **지금은 도입하지 않는다**

`CONSUMER_6DPOSE.md §2.4` 가 SCFlow2 를 검토한 맥락은 **실환경 Z 오차 ~15mm** 였다. 현재 sim 최선은
**0.70mm** 로 전제가 두 자릿수 바뀌었다. 도입하지 않는 이유:

1. **이미 관측 노이즈 바닥이다.** 근접 flange_core depth MAE 0.699mm ≈ pose t 오차 0.70mm.
   refiner 는 관측에 없는 정보를 만들지 못한다. 더 내려가려면 depth 를 개선해야 한다.
2. **남은 실패 모드가 사정권 밖이다.** KPI 를 실제로 깨는 것은 중앙값이 아니라 꼬리이고
   (`dr01_pose_sam3` t med 2.22 / **mean 41.42**), 그 정체는 오선택과 90° 뒤집힘이다.
   refiner 는 국소 최적화라 잘못된 basin 을 벗어나지 못한다 — **틀린 물체를 더 정확히 맞출 뿐이다.**
3. **plug-and-play 가 아니었다.** 문서 자체가 *"0.8m/2.0m 합성데이터 추가학습 → median 감소"*,
   *"측면 view 는 초기보다 저하"* 라고 적고 있다. 거리별 재학습 파이프라인 + 시야각 제한이 추가된다.

**재검토 조건**: M6 실측에서 오차가 KPI 근처로 커질 때. 다만 그 원인이 §6 의 *계통 편향*이면
**refiner 로는 못 고친다**(편향된 depth 에 물체를 맞춰 놓을 뿐) — 먼저 §6 진단을 해야 한다.

## 재현

```bash
envs/cad/bin/python -m spatial_vision.eval.depth_budget      # 위 표 전부
```

---

# ★★★★ depth 오차 주입 실험 — **파이프라인 순위가 뒤집힌다** (2026-08-09)

> 📐 **측정 조건** — `foup_300_semi` · `runs/dr2_*`(`fx 1200 @1280×720`) · 원거리 0.8~1.2m / 근접 0.35~0.50m · **n=40** · **depth 에 오차 주입**(iid·상관·scale·offset).

"실환경 depth 가 17mm 급으로 나쁘다면 어느 파이프라인이 살아남는가" 를 직접 측정했다.
sim depth(`dr2_*_onnx`)에 통제된 오차를 주입하고 pose 까지 다시 돌렸다. **각 런은 자기 GT 로 평가**한다.

## 실험 설계

| 파이프라인 | 거리 | 1단계 메쉬 | 마스크 | 비고 |
|---|---|---|---|---|
| **P1** | 0.96m | `full.ply` | ISM | 원거리 단일 |
| **P2** | 0.43m | `top_flange.ply` | SAM3 flange | 근접 단독 — **깨끗한 데이터의 최선** |
| **P3** | 0.43m | `full.ply` + 1차 초기값 | ISM | 근접 2단계(→ flange refine) |

오차 성격 4종(§실카메라 depth 오차 예산 §6 의 거리 지수 p 에 대응):

| 모드 | 내용 | 대응 |
|---|---|---|
| `iid` | 시차 백색잡음 | p≈2, 상관 0 — **낙관적 하한** |
| `corr` | 시차 상관잡음(`--corr-px`) | p≈2, 상관 유 — **실제 스테레오에 가장 가깝다** |
| `scale` | Z ×= (1+s) | p≈1 — baseline 스케일 |
| `offset` | Z += c | p≈0 — 고정 오프셋 |

크기는 **flange 영역 평균 |ΔZ|** 로 보정한다(`--target-mm`, 달성치를 항상 기록).

## ★★ 1. 크기보다 **상관 길이**가 지배한다

flange 는 근접에서 ~142,000px 다. 픽셀 독립 잡음은 √142000 ≈ **378배**로 평균화되어 pose 에 거의
도달하지 않는다. 실제 스테레오 오차는 패치 단위로 함께 밀리므로 이 축이 사실상의 주 변수다.

**같은 17mm, 상관 길이만 바꿨을 때의 KPI(40프레임):**

| | `iid` | `corr20` | `corr60` | `corr200` |
|---|---|---|---|---|
| P1 coarse | 24/40 | **23/40** | **14/40** | **6/40** |
| P2 coarse | **33/40** | 4/40 | 3/40 | 3/40 |
| P3 refined | **36/40** | 3/40 | 0/40 | 3/40 |

**iid 에서는 근접(P2·P3)이 이기고, 상관이 조금이라도 생기면 원거리(P1)가 압도한다.**
→ **iid 노이즈로 강건성을 평가하면 정반대 결론이 나온다.** 노이즈 모델을 잘못 고르면 처방이 뒤집힌다.

## ★★★ 2. 깨끗한 데이터의 챔피언이 가장 취약하다

`corr60` 크기 스윕, KPI(t≤5mm & R≤3°) / 40:

| 주입 ΔZ | **P1** coarse | **P2** coarse | **P3** refined |
|---|---|---|---|
| 0 (clean) | 40/40 | **40/40** | 40/40 |
| 2.2mm | 40/40 | **40/40** | **40/40** |
| 3.2mm | **40/40** | 38/40 | 38/40 |
| 5.4mm | **35/40** | 33/40 | 31/40 |
| 10.8mm | **24/40** | 16/40 | 13/40 |
| **18.4mm** | **14/40** | 3/40 | 0/40 |
| 26.9mm | **9/40** | 0/40 | 0/40 |
| 42.9mm | 2/40 | 0/40 | 0/40 |

깨끗할 때 P2(0.536° / 0.70mm)가 P1(0.582° / 1.85mm)보다 **2.6배 정확한데**,
depth 가 나빠지면 **P1 이 4~5배 더 많은 프레임을 지킨다.** 순위가 완전히 뒤집힌다.

## ★★★ 3. 이유 — P2 는 **90° 대칭으로 무너지고**, P1 은 부드럽게 밀린다

`corr60` 에서의 **90°/180° 대칭 혼동 건수**:

| 주입 ΔZ | P1 | P2 | P3 |
|---|---|---|---|
| ≤5.4mm | 0 | 0 | 0 |
| 10.8mm | 0 | **3** | 0 |
| 18.4mm | 0 | **12** | 0 |
| 26.9mm | 0 | **21** | 0 |
| 42.9mm | 6 | **22** | 0 |

P2 는 `R med 18.4° / max 179.3°` 로 **완전히 뒤집힌다.** P1 은 같은 조건에서 `R med 1.36° / max 6.10°` 로
회전을 끝까지 지킨다(t 만 밀린다).

**§flange 의 회전 구속과 정확히 맞물린다**: flange 의 yaw 정보는 표면의 3.5%뿐이고 전부 경계에 있다.
depth 가 상관을 갖고 뭉개지면 그 3.5%가 먼저 사라져 90° 극소점으로 떨어진다.
`full.ply` 는 회전 신호가 340배라 같은 오염에도 버틴다.

> **"가장 정확한 구성" 과 "가장 강건한 구성" 이 다르다.** 깨끗한 sim 수치만으로 배포 구성을 고르면 안 된다.

## ★★ 4. 계통 오차(scale·offset)는 **그대로 통과한다** — 어떤 pose 단계도 못 고친다

17mm 주입 시:

| | R med | **t med** | KPI |
|---|---|---|---|
| P1 `scale17` coarse | 0.605 | **17.25** | 0/40 |
| P1 `offset17` coarse | 0.557 | **16.01** | 0/40 |
| P3 `offset17` refined | 1.543 | **16.29** | 0/40 |

**회전은 멀쩡한데(0.56~1.5°) t 오차가 주입량과 정확히 같다.** 계통 depth 편향은 물체를 통째로 밀어놓을 뿐
회전을 해치지 않으며, **refine 을 해도 그대로 남는다**(refiner 는 편향된 depth 에 물체를 맞춘다).

→ **§SCFlow2 판단의 실증**: 계통 편향은 refiner 로 못 고친다. **캘리브레이션으로만 고친다.**
→ M6 에서 §실카메라 depth 오차 예산 §6 의 거리 지수 진단이 왜 최우선인지가 이것으로 확정된다.

## ★★ 5. refine 은 depth 가 나쁠 때 **적극적으로 해롭다**

| P1 (원거리) | coarse | refined |
|---|---|---|
| clean | 40/40 | 40/40 |
| `corr60_2` | 40/40 | 38/40 |
| `corr60_5` | **35/40** | 22/40 |
| **`corr20_17`** | **23/40** | **2/40** (t 평균 **51.95mm**) |
| `corr60_10` | **24/40** | 3/40 |

깨끗할 때 t 를 1.85 → 1.18mm 로 개선하던 바로 그 refine 이, 상관 오차가 들어오면 **t 를 52mm 로 날린다.**
refine 은 depth 를 신뢰하는 국소 최적화라 오염된 depth 를 그대로 따라간다.

**단, iid 에서는 반대다** — P3 refined 가 `iid17` 에서 36/40 으로 최고다. **오차 성격에 따라 부호가 바뀐다.**

## ★ 6. 결론 — 배포 권고

| depth 상관오차 | 권고 구성 |
|---|---|
| **≤ 3mm** | **P2 근접 flange 단독** (0.536° / 0.70mm) — 최고 정확도 |
| 3~10mm | P1 원거리 full **coarse**, refine 끄기 |
| **≥ 10mm** | **P1 원거리 full coarse 만.** 근접 flange 는 쓰면 안 된다(대칭 붕괴) |
| 계통 편향 | **어떤 구성으로도 못 고친다** — 캘리브레이션 선행 |

**운용 권고**: 원거리 full coarse 를 **항상** 돌려 안전망으로 두고(회전이 절대 안 뒤집힌다),
**depth 품질이 검증된 경우에만** 근접 flange 로 정밀화한다. 두 결과의 회전이 90° 배수로 어긋나면
근접 결과를 버린다 — 무료로 얻는 일관성 검사다.

**KPI 5mm 를 지키려면 상관 depth 오차가 ≤3mm 여야 한다.** §실카메라 depth 오차 예산 표와 합치면
ZED X @0.43m(예측 0.74mm)는 여유가 크고, D435 @1.0m(17mm)는 어떤 파이프라인으로도 불가능하다.

## ★★ 7. 분할 축을 닫았다 — **ISM 마스크는 depth 오염에 사실상 불변이다**

위 실험은 마스크를 깨끗한 depth 로 만든 것으로 고정했다. **ISM 이 depth 를 입력으로 받으므로 P1·P3 의
강건성이 과대평가일 것**이라고 예상하고, 오염된 depth 로 ISM 을 **다시 돌려**(12런) 완전 결합을 측정했다.
**예상이 틀렸다.**

| 교란 | far ISM IoU | 검출 | 오선택 | near ISM IoU |
|---|---|---|---|---|
| clean | **0.9146** | 40/40 | 0 | 0.4342 |
| `corr60_5` | **0.9146** | 40/40 | 0 | 0.4342 |
| `corr60_10` | **0.9146** | 40/40 | 0 | 0.4457 |
| `corr60_17` | **0.9146** | 40/40 | 0 | 0.4457 |
| `corr60_25` | **0.9146** | 40/40 | 0 | 0.4457 |
| `iid17` | **0.9146** | 40/40 | 0 | 0.4468 |
| `offset17` | **0.9146** | 40/40 | 0 | 0.4342 |

**24mm 오염에서도 far 마스크가 40/40 프레임 픽셀단위로 동일하다.**

depth 가 무시된 것은 아니다 — 로그의 점수는 실제로 달라진다(`frame_0003` clean 0.744 → `offset17` 0.736).
**proposal 자체는 SAM(RGB)이 만들고 depth 는 순위에만 관여하는데, 그 순위가 뒤집히지 않았다.**

pose 까지 결합해도 결과가 바뀌지 않는다 (P = 고정 마스크, Q = 오염 마스크):

| 교란 | P1 KPI | **Q1 KPI** | P3 KPI | **Q3 KPI** |
|---|---|---|---|---|
| clean | 40/40 | 40/40 | 40/40 | 40/40 |
| `corr60_5` | 35/40 | **35/40** | 31/40 | **31/40** |
| `corr60_10` | 24/40 | **24/40** | 13/40 | **14/40** |
| `corr60_17` | 14/40 | **14/40** | 0/40 | **0/40** |
| `corr60_25` | 9/40 | **8/40** | 0/40 | **0/40** |
| `iid17` | 24/40 | **24/40** | 36/40 | **36/40** |

최대 차이 **1프레임**. → **§1~6 의 결론은 그대로 유효하다.**

> **부수 결론**: 기대했던 "ISM 은 depth 를 쓰니 depth 오염에 취약, SAM3 는 RGB 전용이라 면역" 이라는
> 백엔드 구분점은 **존재하지 않는다.** 두 백엔드 모두 마스크 기하는 RGB 가 만든다.
> ISM 의 depth 사용은 **순위 결정에만** 관여하고 그 순위는 24mm 오염에도 안정적이다.
> 두 백엔드의 실질적 차이는 여전히 **자산 관리 부담**뿐이다(§열려 있음 6).

## ⚠️ 8. 남은 한계 — 과대해석 금지

- 상관잡음은 **가우시안 평활 백색잡음이라는 대용 모델**이다. 실제 스테레오 오차의 공간 구조는 미측정이다.
  M6 에서 실제 오차장의 상관 길이를 재야 이 표를 실환경에 대응시킬 수 있다.
- 이미 좋은 sim 스테레오 위에 **덧씌운** 오차다. 실카메라의 오차는 구조가 다를 수 있다.
- n=40 — 40/40 의 실패율 95% 상한은 여전히 7.5%다(§통계적 한계).

## ★★★ 9. 거리 × 메쉬 2×2 — 무엇이 회전 붕괴를 부르는가 (GT 마스크 고정)

`§1~6` 의 P1(원거리+full) vs P2(근접+flange) 비교는 **거리와 메쉬가 교란**돼 있었다.
네 조합을 **GT 마스크**로 돌려(분할 품질까지 제거) 분리했다. 각 셀 `KPI / R med° / t med mm / 뒤집힘`:

| 교란 | 원거리 0.96m + **full** | 원거리 0.96m + **flange** | 근접 0.43m + **full** | 근접 0.43m + **flange** |
|---|---|---|---|---|
| clean | 40/40 · 0.52 · 1.6 · **0** | 39/40 · 0.55 · 0.9 · 1 | 32/40 · 0.90 · 3.5 · 0 | **40/40 · 0.53 · 0.7 · 0** |
| `corr60_5` | **36/40** · 0.66 · 2.5 · **0** | 18/40 · 2.01 · 3.4 · 3 | 22/40 · 1.37 · 4.8 · 0 | 34/40 · 1.68 · 2.1 · 0 |
| `corr60_17` | **14/40** · 1.20 · 6.0 · **0** | 1/40 · 5.40 · 11.4 · 6 | 4/40 · 3.97 · 16.1 · 8 | 3/40 · 32.90 · 15.2 · **17** |
| `corr60_25` | **7/40** · 1.53 · 9.3 · **0** | 3/40 · 10.21 · 19.4 · 9 | 1/40 · 40.16 · 106 · 13 | 0/40 · 65.85 · 49.6 · **20** |
| `iid17` | 26/40 · 0.72 · 4.0 · 0 | 28/40 · 1.43 · 3.4 · 2 | 22/40 · 1.38 · 4.8 · 1 | **36/40** · 1.25 · 2.8 · **0** |
| `offset17` | 0/40 · 0.64 · 15.8 · 0 | 0/40 · 1.05 · 16.4 · 2 | 0/40 · 1.42 · 18.0 · 0 | 0/40 · 1.89 · 16.1 · 0 |

**분리된 결론:**

1. **회전 붕괴는 거리가 아니라 `메쉬` 의 성질이다.** `원거리+flange` 는 가까이 가지 않았는데도
   오염 시 **3→6→9건** 뒤집힌다. 반대로 **`원거리+full` 은 전 조건에서 뒤집힘 0** 이다.
   → `§3` 의 해석(테두리 3.5% 신호가 먼저 사라진다)이 거리와 무관하게 성립함을 확인한다.
2. **거리는 `t` 정확도를 정한다.** clean 에서 `근접+flange` 0.7mm < `원거리+flange` 0.9mm
   < `원거리+full` 1.6mm. 두 축의 역할이 완전히 다르다.
3. **`근접+full` 도 뒤집힌다(8~13건).** 0.43m 에서는 FOUP 몸체가 FOV 를 벗어나 **실질적으로 flange 만
   보이므로** flange 케이스로 퇴화한다. clean 에서도 32/40 에 그친다(t 3.5mm).
4. ★ **초기값 전달이 회전 붕괴를 막는다.** 같은 `근접+full` 인데 1차 pose 를 초기값으로 준 P3 는
   `corr60_17`·`corr60_25` 에서 **뒤집힘 0** 인 반면, 초기값 없는 이 셀은 8·13 건이다.
   **clean 에서 해로웠던 초기값 전달(0.98 vs 0.70mm)이 depth 가 나쁠 때는 회전을 붙잡아 준다.**
   → §근접 pose 재실험의 "초기값 전달은 불필요(오히려 나쁨)" 은 **깨끗한 depth 조건에서만** 참이다.

> **정리**: `full` 메쉬 = 회전 보험, `근접` = 평행이동 정밀도, `초기값 전달` = 회전 보험(대체재).
> 셋은 서로 다른 것을 사주며, depth 품질이 어느 것을 사야 하는지를 결정한다.

## ★ 10. 하이브리드(R=coarse, t=refined)

기존 산출물에서 계산했다. **iid 에서만 이득이고 상관 오차에서는 손해다:**

| P1 (원거리) | coarse | refined | **하이브리드** |
|---|---|---|---|
| clean | 40/40 | 40/40 | 40/40 |
| `iid17` | 24/40 | 27/40 | **32/40** ✅ |
| `corr60_10` | **24/40** | 3/40 | 15/40 ❌ |
| `corr20_17` | **23/40** | 2/40 | 2/40 ❌ |

하이브리드는 refine 의 t 를 그대로 쓰므로 **refine 이 나쁜 조건에서는 같이 나쁘다.** 회전만 지킬 뿐이다.

## ★★★★ 11. 근접 시점 처리 계열 G0~G9 — **2단계의 이득을 지키는 방법을 찾았다**

2단계의 목적은 **파지 정확도 향상**이다(`PIPELINE_CATALOG.md §2.1b`). 따라서 기준선은
"원거리 단일" 이 아니라 **G0 = 원거리 pose 를 근접 시점으로 좌표변환(재추정 안 함)** 이어야 한다.
근접 관측을 어떻게 쓰는지만 바꿔 비교했다. **추가 pose 런 없이 기존 산출물의 조합으로 계산**했다.

| 코드 | 근접 시점 처리 |
|---|---|
| **G0** | 재추정 안 함 — 원거리 pose 를 좌표변환 (**기준선**) |
| **G1** | 근접 부품 단독 재추정 (= `P2`) |
| **G7** | R = G0, t = G1 (회전·평행이동 분리) |
| **G5** | 교차검증 — `∠(R_G0, R_G1) > τ` 면 G1 폐기 → G0 |
| **★G9** | 교차검증 통과 시 **[R=G0, t=G1]**, 실패 시 G0 전체 |

KPI/40 (괄호는 t 중앙값 mm), τ=3°:

| 교란 | G0 | G1 | G7 | G5 | **★G9** |
|---|---|---|---|---|---|
| **clean** | 40 (1.6) | 40 (**0.7**) | 40 (0.7) | 40 (0.7) | **40 (R 0.55° / t 0.70)** |
| `corr60_2` | 40 (2.0) | 40 (1.1) | 40 (1.1) | 40 (1.1) | **40 (1.1)** |
| `corr60_3` | **40** (2.1) | 38 (1.2) | 39 | 38 | 39 (1.2) |
| `corr60_5` | 35 (2.6) | 33 (1.9) | 36 | **37** | 36 (2.1) |
| `corr60_10` | 24 (4.0) | 16 (6.1) | 19 | **26** | **26** (3.2) |
| `corr60_17` | **14** (6.7) | 3 (14.9) | 6 | **14** | **14** (7.6) |
| `corr60_25` | **9** (9.6) | 0 (51.5) | 0 | 8 | 8 (9.9) |
| `iid17` | 24 (3.8) | 33 (3.0) | **36** | 35 | 35 (2.9) |
| `corr20_17` | **23** (4.3) | 4 (9.8) | 11 | 17 | 17 (6.1) |
| `corr200_17` | 6 (9.1) | 3 (7.9) | **7** | 7 | 7 (9.5) |

### ★ 1. 근접 재추정은 **깨끗한 depth 에서 실제로 이득이다**

`clean` 에서 **t 중앙값 1.6 → 0.70mm (2.3배)**, 회전은 동일(0.55°). 2단계를 도입한 원래 목적
— *근접해서 파지 정확도를 높인다* — 이 데이터로 확인된다. 유효 구간은 **상관 depth 오차 ≤2mm**.

### ★★ 2. G9 가 그 이득을 **취약성 없이** 가져온다

G1 단독은 `corr60_17` 에서 **3/40 으로 붕괴**한다(회전 뒤집힘 12건). **G9 는 같은 조건에서 14/40 —
G0 와 동일**하다. 즉 **이득은 G1 만큼, 손실은 G0 만큼**이다.

- **회전을 근접에서 가져오지 않는다**(G7 성분) → 부품 대칭에 의한 뒤집힘이 원천 차단된다.
- **둘이 어긋나면 근접을 통째로 버린다**(G5 성분) → 평행이동까지 오염된 경우를 걸러낸다.
- 두 성분이 **다른 실패 모드**를 막는다. G7 단독은 `corr60_17` 에서 6/40, G5 단독은 14/40, 합쳐 14/40.

### ★ 3. 임계 τ 는 **3° 가 최적**

| τ | `corr60_5` | `corr60_10` | `iid17` | `corr20_17` |
|---|---|---|---|---|
| **3°** | **37** | **26** | **35** | **17** |
| 5° | 33 | 23 | 34 | 13 |
| 10° | 33 | 20 | 34 | 12 |

τ 를 키우면 오염된 G1 을 통과시켜 손해다. **객체의 회전 정확도 기대치(여기서는 ~0.5°)의 수 배**로
잡는 것이 합리적이며, 객체마다 `measure_symmetry` 와 clean 실측에서 정해야 한다.

### ⚠️ 4. 한계

- **G0 의 좌표변환에 GT 를 썼다**(hand-eye 대역). 실제로는 hand-eye 오차가 **G0·G7·G9 의 회전에
  직접 더해진다.** G1 은 이 문제가 없다 — **G9 는 hand-eye 정확도에 의존하는 구성이다.**
  hand-eye 회전 오차가 τ(3°)에 근접하면 교차검증이 무의미해진다. **M6 에서 실측 hand-eye 오차를
  재기 전에는 G9 의 실환경 성능을 알 수 없다.**
- 가장 심한 오염(`corr60_25`·`corr20_17`)에서는 여전히 **G0 단독이 최선**이다.
- 계통 편향(`scale`·`offset`)에서는 전부 0/40 — 이 계열로 해결되지 않는다.

### 5. 권고

| 상관 depth 오차 | 구성 |
|---|---|
| ≤2mm | **G9** (또는 G1) — t 0.70mm |
| 2~10mm | **G9** — 전 구간에서 G0·G1 이상 |
| ≥15mm | **G0** 단독 |
| 계통 편향 | 캘리브레이션 선행 |

**G9 를 기본으로 하되 `hand-eye 회전 오차 << τ` 가 성립하는지 먼저 확인한다.**

## ★★★ 12. G6 다중 프레임 융합 검정 — **예측대로 무효다** (2026-08-09)

**사전 예측**(`PIPELINE_CATALOG.md §7.2d`): *"정지 씬의 스테레오 오차는 결정적 공간 패턴이므로
프레임을 더 찍어도 같은 오차가 반복된다 → 평균화가 안 듣는다."* 이를 직접 검정했다.

**설계**: 같은 프레임을 8회 복제하되 **이미지 레벨 센서 잡음만** 독립적으로 더한다(정지 카메라가
연속 촬영할 때 프레임 간에 실제로 달라지는 것). 6장면 × 8반복 = 48프레임, σ ∈ {0, 2, 5} DN.
**대조군**: 같은 장면의 depth 에 **독립적인** `corr60` 오차 8개 realization (오차가 독립이면
평균화가 √8 로 들어야 한다 — 메커니즘 확인).

### ★ 1. depth 오차장은 반복해도 같다

| σ(이미지) | 단일프레임 MAE | 8회평균 MAE | **이득** | **반복 간 오차장 상관** |
|---|---|---|---|---|
| 0 (동일 이미지) | 0.726mm | 0.725mm | **1.00×** | **0.998** |
| 2 | 1.542mm | 1.485mm | **1.04×** | **0.869** |
| 5 (강함) | 4.033mm | 3.966mm | **1.02×** | **0.812** |

**센서 잡음을 σ=5 DN 까지 올려도 오차장이 81% 상관**이다. 8회 평균해도 2~4% 만 준다.

### ★★ 2. pose 융합도 같은 결론

회전은 chordal 평균, 평행이동은 중앙값으로 융합:

| 구성 | 단일 R° | 융합 R° | 이득 | 단일 t | 융합 t | 이득 | **장면 내 t 산포** |
|---|---|---|---|---|---|---|---|
| σ=0 | 0.569 | 0.566 | 1.00× | 0.84 | 0.83 | 1.01× | **0.042mm** |
| σ=2 | 0.658 | 0.649 | 1.01× | 0.87 | 0.85 | 1.02× | **0.199mm** |
| σ=5 | 0.654 | 0.640 | 1.02× | 0.89 | 0.86 | 1.04× | 0.181mm |
| **★독립 realization(대조군)** | 1.402 | **0.767** | **1.83×** | 1.71 | **1.04** | **1.65×** | **1.571mm** |

**장면 내 pose 산포가 0.18~0.20mm 인데 오차 자체는 0.87mm** — 즉 8번 찍어도 **거의 같은 답**이 나온다.
평균할 것이 없다. 대조군에서 산포가 **1.571mm(8배)** 로 뛰고 그제서야 융합이 1.65~1.83× 듣는다.

> **결론: G6(정지 다중 프레임 융합)은 채택하지 않는다.** 이득 1~4% 는 프레임 획득·처리 비용을
> 정당화하지 못한다. **평균화는 오차가 독립일 때만 듣는데, 정지 관측은 독립이 아니다.**

### ★ 3. 다만 G10(다중 **시점**)의 근거는 오히려 강해졌다

대조군이 곧 "오차가 탈상관된 경우" 의 대리 실험이고, 거기서는 **1.65~1.83× 이득**이 실재했다.
시점을 바꾸면 시차 패턴이 바뀌어 오차가 탈상관되므로 **G10 은 이 정도 이득을 기대할 수 있다.**
⚠️ 단 이론 상한 √8=2.83× 에 못 미치는데, **결정적 성분(형상·재질에서 오는 계통 오차)이 남기 때문**이다.
시점을 바꿔도 그 성분은 안 준다. **G10 의 상한도 2× 를 크게 넘지 못할 것으로 본다.**

### 4. 예측 검증 결과

| 예측 | 실측 | 판정 |
|---|---|---|
| 정지 다중 프레임은 상관 오차에 거의 무효 | 이득 1.00~1.04× | **적중** |
| 이득은 시간적 노이즈 성분에만 √n | 센서잡음 성분이 작아 실제 이득 미미 | **적중** |
| G10 이 G6 보다 효과적 | 탈상관 대조군에서 1.65~1.83× | **간접 지지** |

## ★★ 13. F5(exemplar 지정) 검정 — **예측이 빗나갔다, 채택하지 않는다** (2026-08-09)

**사전 예측**(`PIPELINE_CATALOG.md §7.2d`): *"ISM 의 제안·점수는 그대로 두고 선택만 exemplar 박스로
바꾸면 **마스크 IoU 는 불변이고 오선택만 사라진다**"*(근거 B2). **두 절반 모두 틀렸다.**

구현: `segment_sam6d --select exemplar --exemplar-dir <SAM3 런>` — ISM 제안 중 SAM3 exemplar
마스크와 **IoU 최대**인 것을 고른다. 참조는 배포조건 자산 `sam3_refs_dr`.

### ★ 1. 분할 — 오선택이 **줄지 않고 늘었다**

| 씬 | 백엔드 | 검출 | **오선택** | IoU(전체) | IoU(정상) |
|---|---|---|---|---|---|
| 중앙(`dr2_far`) | F1 `select center` | 40/40 | **0** | 0.915 | 0.915 |
| | F3 `select score` | 40/40 | **0** | 0.915 | 0.915 |
| | **F5 exemplar** | 40/40 | **1** | 0.898 | 0.921 |
| | SAM3 단독 | 40/40 | 1 | 0.848 | 0.870 |
| 오프센터(+260px) | F1 `center` | 40/40 | **0** | 0.903 | 0.903 |
| | **F5 exemplar** | 40/40 | **0** | 0.911 | 0.911 |
| | SAM3 단독 | 40/40 | 0 | 0.877 | 0.877 |

**F5 의 오선택 프레임(`frame_0020`)은 SAM3 의 오선택 프레임과 동일하다.**
→ **exemplar 지정은 지정 출처의 오류를 1:1 로 물려받는다.** 모델을 하나 더 얹은 만큼 실패 원인도 하나 늘었다.

### ★★ 2. 전제가 틀렸다 — `select center` 는 **부담이 아니었다**

| 씬 | `center` 와 `score` 가 같은 제안을 고른 프레임 | `center` 와 `exemplar` |
|---|---|---|
| 중앙 | **38/40** | 36/40 |
| 오프센터 | **40/40** | 37/40 |

**타깃을 화면 중앙에서 270px 밀어내도 `select center` 는 오선택 0** 이었다.
`select_index` 는 *점수 상위 → 면적 → 중앙근접* 이라 **점수가 이미 결정적이면 중앙 규칙은 발동하지 않는다.**
ISM 의 CAD 템플릿 점수가 동일 인스턴스 씬에서도 타깃을 가려낸다.

> **§M2 확장의 "오선택 45%" 는 SAM3 *텍스트 프롬프트* 의 문제였지 ISM 의 문제가 아니었다.**
> 이 구분을 놓치고 "`select center` 는 자기순환이라 위험" 을 ISM 에까지 확대 적용한 것이 예측 실패의 원인이다.

### 3. pose 까지 — 한 번도 F1 을 못 이긴다

| 교란 | F1+G9 | **F5+G9** | 차이 |
|---|---|---|---|
| clean | **40/40** (R 0.55 / t 0.67) | 39/40 (R 0.55 / t 0.67) | −1 |
| `corr60_5` | **36/40** | 35/40 | −1 |
| `corr60_17` | **14/40** | 13/40 | −1 |

정확히 **F5 가 오선택한 1프레임**만큼 진다. → **F5 는 채택하지 않는다.**

### ⚠️ 4. 이 검정의 한계

오프센터 테스트는 **주점(cx) 이동**으로 만들었다. 물체가 화면에서 밀려나는 것은 재현했지만,
**ISM 점수가 선호하는 대상은 바뀌지 않는다.** 점수 여유가 큰 씬이면 중앙 타이브레이크가 애초에
발동하지 않으므로, 이 실험은 *"중앙 규칙이 필요한 상황"* 을 만들어내지는 못했다.
**"`select center` 가 절대 안전하다" 로 일반화하면 안 된다** — 다만 **이 씬 구성에서는 부담이 아니었다.**

### 5. 예측 검증 성적 갱신

| 예측 | 실측 | 판정 |
|---|---|---|
| G6 정지 다중프레임 무효 | 1.00~1.04× | **적중** |
| F5 마스크 IoU 불변 | 0.915 → 0.921 (정상 프레임) | **부분 적중**(근사 불변) |
| F5 오선택 제거 | 0 → **1 (증가)** | **빗나감** |

→ **논문·코드 근거는 "무엇이 가능한가" 는 잘 예측하지만 "무엇이 문제인가" 는 못 예측한다.**
B2(제안 풀이 RGB)는 맞았고, 그로부터 **IoU 불변**은 맞혔다. 틀린 것은 *"오선택이 문제다"* 라는
**전제**였고, 그 전제는 코드가 아니라 **이전 실측의 오독**에서 왔다.

## ★★ 14. G11(RGB 실루엣 회전) 검정 — **신호가 모자란다, 기각** (2026-08-09)

**사전 예측**: *"RGB 실루엣으로 대칭 후보를 고르면 depth 오염과 무관하게 뒤집힘을 원천 제거"*.

먼저 **성립 가능성**을 GT pose 로 측정했다(삼각형 래스터 실루엣 vs SAM3 마스크):

| | 값 |
|---|---|
| 정답 실루엣 IoU | 0.9789 |
| 최선 대칭후보 IoU | 0.9755 |
| **ΔIoU (정답−대칭)** | **+0.0034** (최소 +0.0006, 음수 0/40) |
| 렌더 상한(GT 마스크 대비) | 0.9936 → **마스크 오차 ≈ 0.015** |
| GT pose 로 실루엣만 써서 정답 선택 | **40/40** |

**여유(0.0034)가 마스크 오차(0.015)의 1/4** 이다. GT pose 에서는 오차가 **공통모드로 상쇄**돼 40/40 이
나오지만, 추정 pose 를 쓰면 잔여 오정렬이 그 상쇄를 깨뜨린다. 실제로:

| 교란 | G1 KPI / R med / 뒤집힘 | G11 적용 후 |
|---|---|---|
| clean | 40/40 · 0.50° · 0 | **39/40** · 0.50° · **1** |
| `corr60_10` | 16/40 · 2.57° · 3 | 15/40 · 2.72° · **6** |
| `corr60_17` | 3/40 · 18.36° · 12 | 4/40 · **4.74°** · 13 |
| `corr60_25` | 0/40 · 88.50° · 21 | 0/40 · 94.03° · **30** |

2D 중심정렬을 넣어 평행이동 오차를 제거해도(위 표) **clean 이 깨지고**(40→39) 심한 오염에서 악화된다.
`corr60_17` 의 R 중앙값만 18.36→4.74° 로 크게 좋아질 뿐 KPI 는 그대로다. → **채택하지 않는다.**

> **예측 실패의 원인 — 내가 이미 계산해 둔 숫자를 쓰지 않았다.**
> `§7.2d` 에 *"부품 회전 단서는 crop 에서 2~5px"*, `§ depth 오차 주입 §3` 에 *"90° 회전 시 실루엣 차이 1.18%"*
> 라고 적어 놓고, G11 예측에는 **신호 크기를 대입하지 않았다.** 메커니즘(RGB 는 depth 에 면역)은 맞았고
> **크기 검토를 빠뜨린 것**이 실패다. → **예측에는 반드시 신호/잡음 비를 붙인다.**

---

# ★★★★ 15. G10 다중 시점 융합 — **인라이어 합의를 붙이면 강력하다** (2026-08-09)

> 📐 **측정 조건** — `foup_300_semi` · `runs/dr2_*`(`fx 1200 @1280×720`) · **n=40** 산출물의 조합(새 런 없음) · 시점 융합 n=1/5/8.

시점이 다른 추정들을 물체 프레임 오차 `E = inv(cam_T_obj_gt) @ cam_T_obj_est` 로 바꾸면 공통 좌표계에서
융합할 수 있다. 회전은 chordal 평균, 평행이동은 중앙값. 무작위 시점조합 400회.

## ★ 1. 단순 융합은 뒤집힘에 무너진다

| 교란 | n=1 | n=5 | n=8 |
|---|---|---|---|
| clean | 0.50° / 0.67mm | 0.26 / 0.39 | **0.22 / 0.32** |
| `corr60_5` | 1.75 / 1.93 | 0.81 / 1.24 | 0.64 / 0.95 |
| `corr60_10` | 2.57 / 6.06 | 2.34 / 2.84 | **3.49** / 2.62 ← 회전 악화 |
| `corr60_17` | 18.36 / 14.89 | 16.39 / 13.45 | 12.66 / 15.71 |

**뒤집힌 추정이 섞이면 회전 평균이 두 봉우리 사이로 떨어진다.** 융합은 오차가 **단봉일 때만** 듣는다.

## ★★ 2. 인라이어 합의(회전 5° 이내 최대 군집만 융합)를 넣으면 뒤집힌다

| 교란 | n=1 | n=8 단순 | **n=8 인라이어** |
|---|---|---|---|
| clean | 0.50 / 0.67 | 0.22 / 0.32 | **0.21 / 0.31** |
| `corr60_10` | 2.57 / 6.06 | 3.49 / 2.62 | **0.88 / 2.12** |
| **`corr60_17`** | **18.36 / 14.89** | 12.66 / 15.71 | **1.07 / 7.03** ← R **17배** 개선 |
| `corr60_25` | 88.50 / 51.45 | 29.60 / 47.15 | 43.76 / 43.14 (실패) |

## ★★★ 3. KPI 달성률 — 단일 추정 대비

| 교란 | n=1 (G1) | n=3 | n=5 | **★n=8** | (참고) F1+G9 |
|---|---|---|---|---|---|
| clean | 100% | 100% | 100% | **100%** | 100% |
| `corr60_5` | 82.5% | 99.2% | 100% | **100%** | 90% |
| `corr60_10` | 40.0% | 62.7% | 77.5% | **89.2%** | 65% |
| `corr60_17` | 7.5% | 13.0% | 23.0% | **27.8%** | **35%** |
| `corr20_17` | 10.0% | 18.2% | 26.5% | **27.5%** | — |
| `iid17` | 82.5% | 98.8% | 100% | **100%** | 87.5% |
| `corr60_25` | 0% | 0% | 0% | 0% | — |

> **상관 오차 ~10mm 까지는 G10(n≥5, 인라이어)이 G9 를 이긴다.** 그보다 심하면 G9 가 낫다
> (대부분의 추정이 뒤집혀 최대 군집 자체가 틀린 봉우리가 되기 때문).
> **두 방법은 서로 배타적이지 않다** — G9 의 게이트(원거리 pose 기준)와 G10 의 시점 융합은 결합 가능하다.

## ⚠️ 4. 한계 — 반드시 함께 읽을 것

- **hand-eye 에 의존한다.** 시점 융합은 추정을 공통 프레임으로 옮겨야 하고, 그 변환에 GT 를 썼다.
  실제로는 hand-eye 오차가 **모든 시점에 계통적으로** 들어가므로 **평균으로 안 없어진다.**
  인라이어 임계 5° 도 `hand-eye 오차 << 5°` 를 전제한다.
- **프록시 실험이다.** 물체 자세를 고정하고 카메라만 옮긴 캡처가 아니라, **서로 다른 프레임의 오차 변환을
  융합**했다. 시점 다양성이라는 성질은 같지만 "같은 물체를 여러 각도에서" 를 문자 그대로 재현하지는 않았다.
- **비용**: n=8 은 로봇이 8개 자세로 이동해야 한다. `corr60_10` 에서 n=3 은 62.7%, n=5 는 77.5% 로
  **수확체감**이 있다. 실환경 사이클 타임과 맞바꿔야 한다.
- `corr60_25` 에서는 어떤 n 으로도 0% — **융합은 다수가 옳을 때만 듣는다.**

## 5. 예측 검증 성적 (누적)

| 예측 | 실측 | 판정 |
|---|---|---|
| G6 정지 다중프레임 무효 | 1.00~1.04× | **적중** |
| G10 이 G6 보다 효과적, 상한 ~2× | 단순 융합 2.0~2.3×, **인라이어 시 R 17×** | **적중(상한은 과소평가)** |
| F5 오선택 제거 | 0 → 1 증가 | **빗나감** |
| G11 뒤집힘 원천 제거 | 오히려 증가 | **빗나감** |
| **N4** 분할을 개선해도 원거리 pose 는 거의 안 변한다 (마스크는 crop+t초기값에만 쓰인다) | GT 마스크로 바꿔도 t 중앙 **0.085mm**, refined **0** | **적중** (§18) |
| **SAM3 참조 20장 포화** | **조건부였다** — 균등 간격일 때만. 면적 기준 **5장**이 20장을 이긴다 | **빗나감** (§19) |
| **`top-k`(GT 기반)가 선택 기준의 상한** | GT 없는 **면적 기준이 더 낫다**(0.889 vs 0.846) | **빗나감** (§19) |

**7전 4승 3패.** 실패의 성격이 두 가지로 갈린다:
- **신호/잡음 비를 대입하지 않았다** (F5·G11) — 메커니즘은 맞았는데 크기를 안 쟀다.
- **표본의 분산을 안 봤다** (`top-k`) — 더 정확한 기준이 더 불안정할 수 있다는 걸 놓쳤다.
- **조건을 안 붙였다** (참조 20장) — *"이 방식으로 뽑을 때"* 라는 전제가 결론에 안 들어갔다.

이 프로젝트가 반복해서 밟는 세 유형이다(횡단 정리 #12·#22·#35·#37).

---

# ★★★ 17. SAM3 참조 장수 — **"2~3장 최적" 은 사슬 방식의 한계였다** (2026-08-09)

> 📐 **측정 조건** — `foup_300_semi` · `runs/dr2_far`(`fx 1200 @1280×720`, 0.8~1.2m) · **n=40** · SAM3 참조 장수 스윕.

`§M2 확장 §4` 가 *"참조 2~3장이 최적, 5장은 오히려 나빠진다"* 라고 적었다. 코드를 보니 원인이
참조 수가 아니라 **구조**였다: `segment_frame_refs` 는 `[참조…, 질의]` 를 **한 시퀀스**로 잇고
`add_prompt` 를 **frame 0 에만** 건다 → 나머지 참조는 **추적으로 통과**하므로 사슬이 길수록 끊긴다.

**검정**: ① 참조 42장 세트를 배포조건에서 새로 캡처(`runs/ref42` → `sam3_refs42`),
② **참조마다 독립 질의(사슬 길이 2) 후 픽셀 과반 융합**하는 경로를 구현(`--refs-mode independent`),
③ ISM 이 쓰는 **바로 그 42장 CAD 렌더**를 SAM3 참조로 변환(`sam3_refs_cad`).

## ★ 결과 (`dr2_far` 40프레임, 타깃 `full`)

| 방식 | 참조 | 검출 | **오선택** | IoU(전체) | IoU(정상) | precision | recall |
|---|---|---|---|---|---|---|---|
| **ISM (CAD 템플릿 42)** | 42 | 40/40 | **0** | **0.915** | 0.915 | 0.987 | **0.927** |
| SAM3 사슬 (`sam3_refs_dr`) | 3 | 40/40 | 1 | 0.848 | 0.870 | 0.941 | 0.882 |
| SAM3 **사슬** | 3 | 40/40 | 1 | 0.784 | 0.804 | 0.911 | 0.831 |
| SAM3 **사슬** | **8** | **0/40** | — | **0.000** | — | — | — |
| SAM3 **사슬** | 20 / 42 | **0/40** | — | **0.000** | — | — | — |
| SAM3 독립+과반 | 3 | 40/40 | 6 | 0.686 | 0.806 | 0.804 | 0.722 |
| SAM3 독립+과반 | 8 | 40/40 | 2 | 0.778 | 0.817 | 0.962 | 0.807 |
| **SAM3 독립+과반** | **20** | 40/40 | **0** | **0.819** | 0.819 | 0.965 | 0.846 |
| SAM3 독립+과반 | 42 | 39/40 | 0 | 0.798 | 0.819 | 0.960 | 0.848 |
| SAM3 독립, **CAD 렌더 참조** | 42 | 40/40 | **5** | 0.728 | **0.832** | 0.854 | 0.770 |
| SAM3 사슬, CAD 렌더 참조 | 42 | **0/40** | — | 0.000 | — | — | — |

## ★★ 1. 사슬 방식은 8장에서 **완전히 붕괴**한다

3장에서 40/40 검출이던 것이 **8·20·42장 모두 0/40** 이다. "5장은 나빠진다" 정도가 아니라
**추적 사슬이 아예 끊긴다.** → 기존 "2~3장 최적" 은 **참조 수의 성질이 아니라 구현의 제약**이었다.

## ★★ 2. 독립 질의로 바꾸면 참조 수에 따라 **단조 개선**된다

| 참조 | 3 | 8 | **20** | 42 |
|---|---|---|---|---|
| 오선택 | 6 | 2 | **0** | 0 |
| IoU(전체) | 0.686 | 0.778 | **0.819** | 0.798 |

**20장에서 포화**하고 42장은 미세하게 떨어진다(1프레임 미검출).

⚠️ **이 결론에는 조건이 빠져 있었다 → §19.** 여기서 "참조 k장" 은 `refs[:k]` 즉 **균등 간격 순서**다.
**선택 기준을 바꾸면 5장이 20장을 이긴다**(면적 기준 0.888 vs 균등 20장 0.819).
*"많을수록 좋다"* 가 아니라 *"균등 간격으로 뽑으면 많이 넣어야 나쁜 장이 희석된다"* 였다.

## ★★★ 3. 그래도 ISM 을 못 이긴다 — 갈리는 것은 **recall**

최선의 SAM3(독립 20장) **IoU 0.819** vs ISM **0.915**.
precision 은 0.965 vs 0.987 로 비슷한데 **recall 이 0.846 vs 0.927** 로 벌어진다
→ **SAM3 가 물체를 덜 잡는다(과소분할).** 참조를 20장까지 늘려도 이 성질은 안 없어진다.

## ★★ 4. CAD 렌더를 SAM3 참조로 쓰면 실패한다

ISM 이 쓰는 **동일한 42장**을 SAM3 참조로 변환하니 오선택 **5/40**(사슬은 0/40 검출).
흥미롭게도 **맞힌 프레임의 IoU 는 0.832 로 sim 참조(0.819)보다 높다** — 마스크 품질이 아니라
**어느 것을 타깃으로 볼지**가 무너진다. 배경 없는 512×512 합성 렌더는 SAM3 의 참조로는 도메인이 안 맞는다.

> **이것이 두 백엔드의 구조적 차이다.**
> **ISM 은 CAD 렌더를 참조로 직접 쓸 수 있고, SAM3 는 못 쓴다.**
> SAM3 는 배포 조건에서 찍은 실사 참조가 필요하며, 그 참조는 거리·외형 조건이 바뀌면 다시 만들어야 한다.

## 5. 정리 — 백본 세대가 아니라 **참조의 종류**가 갈랐다

| | ISM (SAM1 기반) | SAM3 |
|---|---|---|
| 참조 | **3D CAD** — 뷰스피어 완비, 조건 무관 | 2D 실사 — 시점·거리·외형 조건 종속 |
| `full` 타깃 | **0.915 / 오선택 0** | 0.819 / 오선택 0 (참조 20장 필요) |
| `flange` 타깃 | 0.382 / **오선택 23/40** ❌ | **0.879~0.983 / 오선택 0** |

**더 새로운 범용 모델이, CAD 라는 추가 정보를 못 써서 `full` 에서 진다.**
반대로 형상이 단순한 `flange` 에서는 ISM 의 형상 대조가 변별력을 잃어 SAM3 가 압도한다.
→ **타깃에 따라 나눠 쓰는 현행 구성이 옳다.**

## 재현

```bash
# 참조 42장 (배포조건)
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/ref42 --frames 42 --seed 777 --fx 1200 --distance-m 0.80 1.20 $APP
envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs --from runs/ref42 --obj $OBJ \
    --n 42 --target full --out-name sam3_refs42

# 독립 질의 + 픽셀 과반 융합
envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 --in runs/dr2_far --out runs/s3_indep20 \
    --target full --refs $OBJ/sam3_refs42 --n-refs 20 --refs-mode independent --refs-fuse vote
```

⚠️ 독립 질의는 참조 수에 비례해 느리다 (참조당 ~0.26s/frame → 20장이면 ~5s/frame).

---

# ★★★★★ 16. G9 + G10 결합 — **새로운 최선** (2026-08-09)

> 📐 **측정 조건** — `foup_300_semi` · `runs/dr2_*`(`fx 1200 @1280×720`) · **n=40** · 무작위 5시점 조합 400회.

G9(원거리 기준 게이트)와 G10(다중 시점 융합)은 **서로 다른 실패 모드**를 막으므로 결합했다.
물체 프레임 오차 `E0 = inv(gt_far) @ est_far`, `E1 = inv(gt_near) @ est_near` 로 통일해 n=5 시점을 융합.

**결합 규칙**
1. 회전 = **원거리 추정 5개의 chordal 평균** (원거리 full 은 절대 안 뒤집힌다)
2. 각 시점에서 `∠(R_E0, R_E1) ≤ 3°` 인 근접 추정을 인라이어로 선별
3. **인라이어가 과반(≥3)이면** 평행이동 = 그 근접 추정들의 중앙값, **아니면 원거리 평행이동**으로 후퇴

★ 3의 **정족수**가 핵심이다. 게이트는 회전만 검사하는데 쓰는 것은 평행이동이라,
통과 수가 적으면 *"회전은 맞았지만 t 는 오염된"* 추정을 채택해 버린다(정족수 없이는
`corr20_17` 에서 31.5% → 정족수 적용 시 **80.5%**).

## ★ 1. KPI 달성률 (n=5, 무작위 시점조합 400회)

| 교란 | G0 단일 | G1 단일 | G9 단일 | G10 | **원거리 융합** | **★결합+정족** |
|---|---|---|---|---|---|---|
| clean | 100% | 100% | 100% | 100% | 100% | **100%** |
| `corr60_5` | 87.2% | 83.0% | 90.0% | 99.8% | 100% | **100%** |
| `corr60_10` | 58.8% | 37.5% | 63.2% | 75.0% | **97.8%** | 89.5% |
| `corr60_17` | 34.2% | 8.8% | 35.8% | 22.8% | **68.2%** | 67.2% |
| `corr60_25` | 23.5% | 0% | 22.2% | 0% | **26.8%** | 26.8% |
| `corr20_17` | 58.0% | 10.8% | 44.0% | 27.8% | **94.0%** | 80.5% |
| `iid17` | 62.0% | 84.5% | 89.5% | 100% | 98.0% | **100%** |

## ★★ 2. 실제 오차 — KPI 는 100%에서 포화되므로 반드시 함께 본다

오차 중앙값 (R° / t mm):

| 교란 | G0 단일 | G1 단일 | G9 단일 | 원거리 융합 | **★결합+정족** |
|---|---|---|---|---|---|
| **clean** | 0.56 / 1.69 | 0.50 / 0.65 | 0.56 / 0.65 | **0.24** / 1.07 | **0.24 / 0.39** |
| `corr60_5` | 0.68 / 2.56 | 1.76 / 1.85 | 0.68 / 2.20 | 0.34 / 1.33 | **0.34 / 1.23** |
| `corr60_10` | 0.96 / 3.96 | 2.64 / 6.06 | 0.96 / 3.22 | **0.54 / 1.93** | 0.54 / 2.23 |
| `corr60_17` | 1.37 / 6.12 | 18.96 / 15.15 | 1.37 / 7.58 | **0.81 / 3.65** | 0.81 / 3.71 |
| `corr20_17` | 0.93 / 4.40 | 4.52 / 9.20 | 0.93 / 5.96 | **0.50 / 2.14** | 0.50 / 2.67 |

**clean 에서 R 0.24° / t 0.39mm** — 지금까지의 최선(G9 0.56° / 0.65mm)을 **회전 2.3배, 평행이동 1.7배** 앞선다.

## ★★★ 3. 가장 놀라운 것 — **근접 추정 없이 원거리만 융합해도 거의 최고다**

`corr60_10` 이상에서는 **원거리 full 추정 5개를 융합한 것**이 결합보다 낫거나 같다.
원거리 추정은 **회전이 절대 안 뒤집히고 오차가 단봉**이라 융합이 그대로 듣는다.
근접 부품 추정은 per-shot 정확도가 높지만 **다봉(뒤집힘)** 이라 융합 이득을 못 살린다.

> **정리**: 다중 시점이 가능하면 **근접 재추정의 가치가 크게 줄어든다.**
> 근접이 여전히 이기는 곳은 **깨끗한 depth 뿐**이고(t 0.39 vs 1.07mm), 거기서만 결합이 의미 있다.

## 4. 권고 (갱신)

| 조건 | 구성 | 기대 |
|---|---|---|
| 다중 시점 가능 + depth 양호(≤5mm) | **F1 + G9/G10 결합 (n=5)** | R 0.24° / t 0.39mm |
| 다중 시점 가능 + depth 불량(≥10mm) | **F1 + 원거리 full 5시점 융합** | R 0.54~0.81° / t 1.9~3.7mm |
| 단일 시점만 | **F1 + G9** | R 0.56° / t 0.65mm |
| 계통 편향 | 불가 — 캘리브레이션 선행 | — |

## ⚠️ 5. 한계

- **hand-eye 에 의존한다.** 시점 융합·게이트 모두 공통 프레임 이송이 필요하고 실험은 GT 를 썼다.
  hand-eye 오차는 **모든 시점에 계통적으로** 들어가 **평균으로 안 없어진다** — 융합 이득의 상한을 정한다.
- **프록시**: 물체 고정 + 카메라만 이동한 캡처가 아니라 프레임별 오차 변환을 융합했다.
- **비용**: n=5 는 로봇 자세 5개. 사이클 타임과 맞바꿔야 한다.
- `corr60_25` 는 어떤 구성도 27% 미만 — **융합은 다수가 옳을 때만 듣는다.**

## 재현

```bash
# G11 성립 가능성 (실루엣 판별력) / G10 융합 — 둘 다 기존 산출물 조합, 새 런 불필요
#   실루엣: 삼각형별 fillConvexPoly (fillPoly 일괄은 even-odd 로 상쇄됨)
#   G10:    E = inv(pose_gt) @ pose_est 를 물체 프레임에서 평균 (회전 chordal, 위치 중앙값)
#           + 인라이어: 회전 5° 이내 최대 군집만
```

---

## 재현

```bash
envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 --in runs/dr2_far --out runs/dr2_far_sam3 \
    --target full --refs $OBJ/sam3_refs_dr --n-refs 3
envs/seg_sam6d/bin/python -m spatial_vision.stages.segment_sam6d --in runs/dr2_far --out runs/dr2_far_ism_f5 \
    --target full --templates $OBJ/ism_full --cad $OBJ/full.ply \
    --select exemplar --exemplar-dir runs/dr2_far_sam3 --depth stereo --depth-dir runs/dr2_far_onnx

# G6 — 같은 프레임을 센서잡음만 바꿔 8회 복제 → stereo → pose → 융합
#   (스크립트는 세션 스크래치패드. 핵심은 left/right 에 N(0,σ) 를 더해 복제하는 것)

# 근접 시점 계열 G0~G9 (추가 pose 런 불필요 — 기존 산출물 조합)
#   G0 = (near_gt @ inv(far_gt)) @ far_pred,  G1 = near 부품 pose
#   G9 = ∠(R_G0,R_G1) ≤ 3° 면 [R=G0, t=G1], 아니면 G0

# 거리 × 메쉬 2×2 (GT 마스크)
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_far --out runs/gridR_far_flange_clean \
    --obj $OBJ --primary flange --depth stereo --depth-dir runs/dr2_far_onnx

# 오차 주입 (모드·크기·상관길이를 바꿔가며)
envs/stereo_onnx/bin/python -m spatial_vision.eval.perturb_depth \
    --in runs/dr2_near_onnx --capture runs/dr2_near --out runs/pert/near_corr60_17 \
    --mode corr --corr-px 60 --target-mm 17 --calib-mask mask_flange.png

# P1 / P2 / P3 (--depth-dir 로 교란된 depth 를 물린다)
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_far  --out runs/pose_P1_corr60_17 \
    --obj $OBJ --masks runs/dr2_far_ism  --depth stereo --depth-dir runs/pert/far_corr60_17 --flange-mask-from pose
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/pose_P2_corr60_17 \
    --obj $OBJ --primary flange --masks runs/dr2_near_sam3fl --depth stereo --depth-dir runs/pert/near_corr60_17
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/pose_P3_corr60_17 \
    --obj $OBJ --masks runs/dr2_near_ism --depth stereo --depth-dir runs/pert/near_corr60_17 \
    --init-from runs/dr2_far_pose --init-capture runs/dr2_far --rel-from-gt
```

⚠️ `--rel-from-gt` 를 쓸 때 **`--init-capture` 를 반드시 준다**. 없으면 `pose_gt.json` 을 pose 런에서
찾다가 전 프레임을 조용히 건너뛰고 **빈 산출물에 `meta_pose.json` 만 남긴다**(종료코드 0).

⚠️ **Isaac Sim 캡처와 FoundationPose 를 동시에 돌리지 않는다.** 2×2 그리드의 9런이 GPU 경합으로
**첫 프레임에서 조용히 죽었다**(로그가 초기화 직후 끊기고 빈 디렉토리만 남는다). 산출 프레임 수를
세어 확인한다: `ls runs/<out>/frame_*/pose_coarse.json | wc -l`.

---

# ★★★★ sim D435 재현 실험 — **실환경 예측 모델이 두 군데 틀렸다** (2026-08-09)

> 📐 **측정 조건** — `foup_300_semi` · **D435 기하(`fx 674 · B 50mm`) 를 sim 에서 직접 캡처** · ZED X(`fx 1200 · B 120mm`)와 같은 seed·거리로 짝지음 · **n=20**.

실측 D435 17mm 를 sim 과 직접 대조하기 위해, **sim 에서 D435 기하로 캡처**해 같은 FoundationStereo
(NGC ONNX)를 돌렸다. ZED X 를 **같은 seed·같은 거리대**로 짝지어 캡처해 카메라 기하만 분리했다.
clutter 없음, 20프레임 × 3 거리대 × 2 카메라 = 6 캡처. 지표는 **프레임별 flange_core MAE 의 중앙값**
(§횡단 16 — 평균은 이상치에 끌린다).

## ★ 1. 결과

| 카메라 | 0.50m | 1.01m | 1.59m | **거리 지수 p** |
|---|---|---|---|---|
| **D435** (fx674, B50) | 1.463mm | 2.599mm | 3.738mm | **0.81** |
| **ZED X** (fx1200, B120) | 0.688mm | 1.455mm | 2.191mm | **1.01** |

## ★★ 2. 정정 A — **거리 지수는 2 가 아니라 ~0.8~1.0 이다**

`σ_Z = Z²/(fx·B)·σ_disp` 는 **σ_disp 가 거리에 무관할 때만** p=2 를 준다. 실제로는 σ_disp 가
거리에 따라 **줄어든다**(D435: 0.197 → 0.086 → 0.050 px). 시차가 작아질수록 절대 px 오차도 작아진다.

→ **근접의 이득은 Z² 가 아니라 대략 선형이다.** 프로젝트의 기존 데이터도 이미 그랬다:
far(0.8~1.2m) 1.510mm → near(0.35~0.5m) 0.699mm 는 지수 **0.88** 이다.
`§근접 pose 재실험` 의 *"σ_Z ∝ Z² 이므로 근접의 이득은 원래 있었다"* 는 **이득의 크기를 과장**한다.

⚠️ 이 지수는 **M6 진단(편향 vs 산포)의 기준을 바꾼다.** "p≈2 면 랜덤, p≈1 이면 baseline 스케일" 이라고
적었는데, **학습 기반 스테레오는 랜덤 오차인데도 p≈1 이 나온다.** 거리 지수만으로는 둘을 구분할 수 없다.
→ **편향은 부호로 판별해야 한다**(bias 항이 거리에 따라 부호를 유지하는가).

## ★★ 3. 정정 B — **`fx·B` 이득이 4.27배가 아니라 1.7~2.1배다**

| 거리 | D435 | ZED X | 실제 이득 | `fx·B` 예측 |
|---|---|---|---|---|
| 0.50m | 1.463 | 0.688 | **2.13×** | 4.27× |
| 1.01m | 2.599 | 1.455 | **1.79×** | 4.27× |
| 1.59m | 3.738 | 2.191 | **1.71×** | 4.27× |

**σ_disp 가 카메라 간에 전이되지 않는다** — 시차가 큰 카메라일수록 절대 px 오차가 크다
(1.01m: D435 0.086px vs ZED X 0.207px). 학습 기반 스테레오의 오차는 시차에 **대략 비례**하는 성분을
갖는다. `fx·B` 표(§실카메라 depth 오차 예산 §2)는 **같은 σ_disp 가정 하의 상한**으로만 읽어야 한다.

## ★★★ 4. 그리고 — **카메라 기하를 맞춰도 sim 이 훨씬 좋다**

| 거리 | sim D435 | 실측 D435 | 비 | sim σ_disp | 실측 σ_disp |
|---|---|---|---|---|---|
| 0.50m | 1.46mm | 17mm | **11.6×** | 0.197px | 2.292px |
| **1.01m** | **2.60mm** | **17mm** | **6.5×** | **0.086px** | **0.562px** |
| 1.59m | 3.74mm | 17mm | 4.5× | 0.050px | 0.227px |

**실측 거리가 어디였든 sim 이 4.5~11.6배 낙관적이다.** 카메라 기하는 sim→real 갭의 **일부일 뿐**이고,
남은 4~12배는 **센서 노이즈·실제 텍스처·조명·IR 프로젝터·캘리브레이션·모션블러** 등이다.

> ⚠️ 앞서 *"실측이 4.3배 불리한 카메라로 이루어졌을 뿐, 기하를 맞추면 sim 을 예측에 쓸 수 있다"* 고
> 적었다. **틀렸다.** 0.74mm(외삽)와 0.70mm(sim)가 맞아떨어진 것은 정정 A·B 두 오차가 **상쇄된 우연**이다.

**실환경 ZED X @0.43m 재추정**: sim 값 ~0.59mm 에 sim→real 계수 6.5배를 적용하면 **≈3.8mm**.
KPI 5mm 안이지만 여유가 거의 없고, `§depth 오차 주입` 의 "상관 오차 ≤3mm 필요" 기준에는 **미달**이다.
(계수 6.5 가 카메라를 건너뛰어 전이된다는 보장은 없다 — M6 에서 실측해야 한다.)

## ⚠️ 5. 부수 관측 — ZED X 근접에서 프레임 단위 불안정

`cam_zedx_b05`(0.4~0.6m)는 프레임 MAE 중앙값 0.688mm 인데 **4/20 프레임이 8~18mm 로 터진다**
(D435 는 최대 2.36mm 로 균일). 시차 범위 초과를 의심했으나 상관이 약하다(r=+0.35 — 시차 320px 인데
멀쩡한 프레임이 있다). **미해명**. 근접 ZED X 를 배포하려면 이 꼬리를 규명해야 한다.

## 재현

```bash
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/cam_d435_b10 --frames 20 --seed 501 --fx 674 --baseline-mm 50 --distance-m 0.80 1.20 $APP
envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx --in runs/cam_d435_b10 \
    --out runs/cam_d435_b10_onnx --scale 0.75 --model weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx
envs/stereo_onnx/bin/python -m spatial_vision.eval.eval_depth --gt runs/cam_d435_b10 --pred runs/cam_d435_b10_onnx
```

⚠️ `eval_depth` 의 집계는 **전 픽셀 평균**이라 이상치 프레임에 끌린다. 카메라 비교는
**프레임별 MAE 의 중앙값**으로 봐야 한다(ZED X @0.5m: 전체평균 3.08mm vs 프레임중앙 0.688mm).

---

# ★★★★ 18. 분할의 상한선 — **원거리 pose 에서 마스크는 병목이 아니다** (2026-08-10)

> 📐 **측정 조건** — `foup_300_semi` · `runs/dr2_far`(`fx 1200 @1280×720`, 0.8~1.2m) · **n=40** · **clean depth 한정**(마스크를 GT 로 치환한 대조).

새 분할 백엔드(NOCTIS) 도입을 검토하다가, **그 전에 답해야 할 질문**이 있었다:
*"분할을 완벽하게 만들면 pose 가 얼마나 좋아지나?"* 이득의 **상한**을 직접 쟀다.

**설계**: `dr2_far` 40프레임, depth·pose 설정을 전부 고정하고 **마스크만** 교체.
ISM 예측 마스크(IoU 0.915) → **GT 마스크(IoU 1.0)**.

## ★ 1. 결과 — 완벽한 분할의 이득이 t 중앙값 0.085mm 다

| 단계 | 마스크 | KPI | R 중앙 | R max | **t 중앙** | t 평균 | t max |
|---|---|---|---|---|---|---|---|
| coarse | ISM 0.915 | 40/40 | 0.545 | 1.799 | **1.634** | 1.847 | 4.122 |
| coarse | **GT 1.0** | 40/40 | 0.521 | 1.769 | **1.549** | 1.759 | 3.676 |
| refined | ISM 0.915 | 40/40 | 0.637 | 2.058 | **1.102** | 1.182 | 3.204 |
| refined | **GT 1.0** | 40/40 | 0.601 | 1.881 | **1.100** | 1.187 | 2.959 |

coarse 에서 **t 중앙 −5.2% / R 중앙 −4.4%**, refined 에서는 **t 중앙 −0.002mm(사실상 0)** 이고
평균은 오히려 미세하게 나빠진다. KPI 는 네 구성 모두 **40/40 으로 이미 천장**이다.

> **IoU 0.915 를 1.0 으로 만들어도 KPI 5mm 기준으로 의미 없는 변화다.**
> 원거리 `full` 의 오차 1.63mm 는 분할이 아니라 **depth 와 FoundationPose 자체**에서 온다.

이유는 코드에 있다 — FoundationPose 는 마스크를 **crop 범위**와 **t 초기값**(마스크 내 depth 중앙값)
에만 쓴다. crop 은 `mesh 지름 × 1.2` 로 정규화되므로 마스크가 조금 커도 작아도 같은 crop 이 나오고,
t 초기값은 어차피 이후 refine 이 고친다.

## ★★ 2. 그래서 분할 백엔드 교체는 정확도 근거를 잃는다

| 후보 | 우리 `full` IoU 대비 | 이 실험이 말하는 것 |
|---|---|---|
| ISM (현행) | 0.915 | 기준 |
| NOCTIS (BOP AP +3.9 vs SAM-6D) | 기대 0.93~0.94 | 위 0.085mm 의 **3분의 1** — 도입 근거 없음 |
| 완벽한 분할 | 1.000 | **0.085mm** |

→ `PIPELINE_CATALOG.md §2.2` 에 NOCTIS 미채택 근거로 등록.

## ⚠️ 3. 이 측정이 덮지 못하는 두 곳 — 일반화 금지

1. **clean 에서만 쟀다.** 꼬리는 개선된다(coarse t max 4.122 → 3.676, −11%). depth 가 오염돼
   **꼬리가 KPI 를 결정하는 구간**에서는 이 결론이 성립하는지 모른다.
2. **근접 `flange` 단계는 별개다.** 거긴 성립 조건이 `flange 마스크 IoU ≥0.98` 이고
   (§flange 의 회전 구속) 마스크 품질이 실제로 지배한다. **"마스크는 안 중요하다" 로 읽으면 안 된다 —
   원거리 `full` 에서만 그렇다.**

## 재현

```bash
# 같은 depth·같은 설정에서 마스크만 GT 로 (--masks 를 빼면 --in 의 GT 마스크를 쓴다)
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_far --out runs/dr2_far_pose_gtmask \
    --obj $OBJ --depth stereo --depth-dir runs/dr2_far_onnx --flange-mask-from pose
envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/dr2_far --obj $OBJ --pred runs/dr2_far_pose_gtmask
# 대조군은 runs/dr2_far_pose (동일 명령 + --masks runs/dr2_far_ism)
```

---

# ★★★ 19. SAM3 참조 **선택 기준** — 장수보다 어느 장을 고르냐다 (2026-08-10)

> 📐 **측정 조건** — `foup_300_semi` · `runs/dr2_far`(`fx 1200 @1280×720`) · **n=40**(프로브 20) · 참조 후보 42장 → 선별.

§17 이 *"독립 질의는 20장까지 단조 개선"* 이라고 적었는데, 그건 `refs[:k]`(= 균등 간격 순서)를
쓴 결과였다. **선택 기준 자체를 바꾸면 그림이 달라진다.**

**설계**: `runs/s3_perref` 에 참조별 마스크를 저장해 두었으므로 **어떤 부분집합의 픽셀 과반 융합이든
재추론 없이** 평가된다. `dr2_far` 40프레임 × 참조 42장.

## ★ 1. 참조마다 품질이 크게 다르다

```
참조별 단독 IoU:  최소 0.531  중앙 0.743  최대 0.865   (표준편차 0.090)
```

## ★★ 2. 결과 (2겹 교차검증 — 홀수 프레임으로 고르고 짝수로 평가, 그 반대도)

| 기준 | k=3 | k=5 | k=8 | k=12 |
|---|---|---|---|---|
| random | 0.739 | 0.780 | 0.770 | 0.786 |
| **linspace (현행 `build_sam3_refs`)** | **0.709** | 0.770 | **0.721** | 0.814 |
| **top-k** (참조별 단독 IoU 상위) | 0.805 | **0.846** | 0.832 | 0.782 |
| diverse (뷰스피어 farthest-point) | 0.754 | 0.757 | 0.794 | 0.801 |
| greedy (융합 IoU 를 가장 올리는 것부터) | 0.804 | 0.820 | 0.814 | 0.808 |
| 전체 42장 | — | — | — | 0.798 |

세 가지가 나온다:

1. **현행 `linspace` 가 random 보다 나쁘다** (k=3: 0.709 vs 0.739, k=8: 0.721 vs 0.770).
   균등 간격은 좋은 참조와 나쁜 참조를 **무차별하게** 섞는다.
2. **시점 다양성(diverse 0.757)보다 개별 품질(top-k 0.846)이 중요하다.**
   §M2 확장의 *"순서·시점은 무관"* 과 일관되며, 이제 **무엇이 유관한지**가 나왔다.
3. ★ **참조를 더 넣는 게 항상 좋지 않다** — top-k 는 **k=5 에서 최고**이고 k=12 에서 0.782 로 떨어진다.
   전체 42장은 0.798. **나쁜 참조가 과반 투표를 오염시킨다.**

> **참조 수를 늘리는 것보다 좋은 5장을 고르는 것이 낫다.**
> 이것이 §17 의 *"20장까지 단조 개선"* 을 조건부로 만든다 — **균등 간격으로 뽑을 때만** 그렇다.

## ★★★ 3. 과적합을 확인했다 — 교차검증 전에는 수치가 부풀어 있었다

| 기준 | 같은 프레임으로 고르고 평가(과적합) | **교차검증** | 낙폭 |
|---|---|---|---|
| top-k k=5 | 0.889 | **0.846** | −0.043 |
| greedy k=5 | 0.896 | **0.820** | −0.076 |

**개별 참조는 전이되지 않는다** — 두 겹이 고른 인덱스의 겹침이 top-k k=5 에서 **0/5** 다.
*"이 5장이 좋다"* 는 못 옮기고 *"질 좋은 5장을 고르는 절차"* 만 옮긴다. `greedy` 가 더 크게
떨어진 것도 같은 이유다(부분집합에 더 강하게 맞춘다).

⚠️ **이 프로젝트의 반복 함정이다** — 선택과 평가에 같은 데이터를 쓰면 순위가 뒤집힌다.
교훈 #28 로 등록.

## ★★★★ 4. GT 없이 고르는 법 — **마스크 면적**이 oracle 을 그대로 재현한다

`top-k` 는 참조별 단독 IoU 를 쓰는데 그건 정답 마스크가 있어야 잰다 — **실환경에서는 못 쓴다.**
GT 를 안 쓰는 대리 기준 3종을 같은 2겹 교차검증으로 비교했다.

| 기준 | GT 필요 | k=3 | **k=5** | k=8 | oracle 과 순위상관 |
|---|---|---|---|---|---|
| oracle — 단독 IoU 상위 | **필요** | 0.805 | 0.846 | 0.832 | 1.000 |
| consensus — 42장 과반을 유사정답으로 | 불필요 | 0.777 | 0.777 | 0.787 | 0.607 |
| agree — 다른 참조들과의 평균 IoU | 불필요 | 0.757 | 0.789 | 0.781 | 0.568 |
| **★ area — 마스크 면적 중앙값 상위** | **불필요** | 0.868 | **0.889** | 0.790 | **0.688** |
| linspace (현행) | 불필요 | 0.709 | 0.770 | 0.721 | — |

**`area` 가 oracle 을 이긴다** (0.889 vs 0.846). 고른 참조도 **5장 중 4장이 oracle 과 같다**
(area `{7,19,22,37,38}` vs oracle `{4,7,19,22,38}`).

### 왜 면적이 듣는가 — 우리 실패가 과소분할이기 때문이다

| 면적과의 순위상관 | 값 |
|---|---|
| **recall** | **+0.750** |
| IoU | +0.688 |
| precision | +0.486 |

참조별 평균이 **precision 0.846 / recall 0.752** — 즉 **덜 잡는 것이 주된 실패**다.
이 구간에서 *"많이 잡는 참조"* 는 곧 *"recall 높은 참조"* 이고, 면적이 그 대리지표가 된다.

### ★★ 게다가 면적은 **오선택도 거른다** — 우리 오선택이 "파편" 이기 때문

| | 값 |
|---|---|
| 면적↔오선택 순위상관 | **−0.666** |
| 면적 **상위** 5장의 오선택 합 | **7** |
| 면적 **하위** 5장의 오선택 합 | **56** |
| ★ 오선택한 마스크의 면적 중앙값 | **46,429px** vs 정상 187,902px = **0.25배** |

우리 오선택은 *"다른 FOUP 을 깨끗하게 잘랐다"* 가 아니라 **파편을 집은 것**이라 면적이 4분의 1이다.
그래서 면적 하나로 recall 과 오선택을 **동시에** 거른다.

⚠️ **이건 실패 모드에 의존하는 성질이다.** 오선택이 *"동일 크기의 다른 인스턴스"* 형태로 나타나면
(SAM3 텍스트 프롬프트의 45% 오선택이 그런 유형이었다) **면적은 전혀 못 거른다.**
→ 신규 객체에 적용하기 전에 **오선택이 파편형인지 인스턴스형인지** 확인한다.

융합 결과가 이를 그대로 보여준다:

| 선택 | IoU | precision | **recall** | 오선택 |
|---|---|---|---|---|
| linspace k=5 (현행) | 0.770 | 0.908 | 0.800 | 2 |
| oracle(GT) k=5 | 0.889 | 0.939 | 0.948 | **0** |
| **★ area k=5** | **0.888** | 0.935 | **0.950** | **0** |
| area k=8 | 0.801 | 0.910 | 0.854 | 1 |
| 전체 42장 | 0.798 | 0.936 | 0.827 | 1 |

precision 은 거의 안 변하는데 **recall 이 0.800 → 0.950 으로 뛴다.**

### ★ recall 결손의 정체 — 검출 실패가 아니라 **부품 단위 결손**이고 **flange 에 집중**된다

면적 상위 5장 융합 마스크에서 놓친 픽셀(FN)을 해부했다:

| | 값 |
|---|---|
| **검출 실패(오선택) 프레임** | **0/40** — 물체는 항상 찾는다 |
| FN 중 **경계 5px 이내** | 17.6% → **나머지 82.4% 는 내부/부품 단위** |
| 부위별 recall | **flange 0.844** vs body 0.968 |
| FN 픽셀의 부위 분포 | **flange 43.6%** / body 56.4% |
| (참고) GT 면적 비중 | flange **13.5%** |

> **flange 는 면적의 13.5% 인데 놓친 픽셀의 43.6% 를 차지한다 — 3.2배 과대표집이다.**

즉 recall 0.75~0.85 는 *"물체를 못 찾았다"* 가 아니라 *"찾았는데 **윗판을 잘 빠뜨린다**"* 이다.
경계가 얇게 깎이는 문제(17.6%)가 아니라 **부품을 통째로 놓치는 문제**다.

⚠️ 이것은 **원거리 `full` 타깃**의 이야기이고, §18 에 따라 **원거리 pose 에는 거의 영향이 없다.**
그러나 *"원거리에서 flange 를 SAM3 로 따로 뽑는다"* 는 경로를 고려한다면 이 수치가 경고다
(근접 flange 는 근접 참조로 IoU 0.983 — 별개의 설정이다).

### ⚠️ 성립 조건 — precision 이 포화돼 있을 때만이다

어떤 참조가 **과대분할**(배경까지 삼킴)하면 면적이 커지면서 precision 이 무너진다 — 그때는 이 기준이
정확히 최악의 참조를 고른다. 지금은 안전 구간이다:

```
GT 면적 중앙값 204,336px | 참조 면적 0.69x ~ 1.06x | GT 를 넘는 참조 4/42 (최대 1.06x)
```

→ **가드**: 참조 면적 중앙값이 **42장 합의 마스크 면적을 크게(예: 1.2배) 넘으면 제외**한다.
합의 마스크는 GT 가 아니므로 이 가드도 배포 가능하다. 현재 데이터에서는 제외되는 참조가 없다.

### ⚠️ 그리고 왜 oracle 을 **이기는가** — 정확한 기준이 불안정할 수 있다

oracle 은 겹당 20프레임으로 추정하는 **분산이 큰** 통계라 선택 자체가 흔들린다(두 겹 겹침 0/5).
면적은 분산이 훨씬 작아 **교차검증 수치와 전체 데이터 수치가 거의 같다**(0.889 vs 0.888).
**노이즈가 큰 정확한 기준이 안정적인 근사 기준에게 진다** — 교훈 #37.

### 처방

> **배포 기준: 참조 후보들을 각각 단독으로 써서 검증 프레임 몇 장을 분할하고,
> 나온 마스크 면적의 중앙값이 큰 순으로 5장.** GT 불필요. 면적 가드 1.2× 적용.

⚠️ **객체 1종에서만 유도됐다.** precision 이 포화되지 않는 객체(반사면·투명체 등 과대분할이 흔한 경우)
에서는 성립하지 않을 수 있다. 신규 객체에는 **면적과 precision 의 관계를 먼저 확인**하고 적용한다.

## 재현

```bash
# 참조별 마스크를 남기는 런 (재추론 없이 부분집합 평가를 하기 위한 전제)
envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 --in runs/dr2_far --out runs/s3_perref \
    --target full --refs $OBJ/sam3_refs42 --refs-mode independent --refs-fuse vote --save-per-ref
# 부분집합 평가는 세션 스크래치패드 스크립트(refsel.py / refcv.py). 핵심은
#   부분집합 융합 = M[frame, idx].sum(0) * 2 > len(idx)   (픽셀 과반)
#   선택은 train fold 에서, 평가는 test fold 에서 — 같은 프레임을 쓰면 안 된다
```

---

# 🔴🔴 20. CAD-실물 형상 불일치 — **body 는 refine 이 흡수하고, flange 는 못 한다** (2026-08-10)

> 📐 **측정 조건** — `foup_300_semi` + 교란 CAD/`foup_300_hybrid` · `fx 1200 @1280×720` · 원거리 0.8~1.2m / 근접 0.35~0.50m · **n=40** · **CAD 만 틀리게 만든 대리 측정**.

`full` 은 비표준부(body)를 포함하는데 **body 는 제조사마다 다르다**(사용자 확정, **cm 급**).
그런데 실측 최선 구성들이 **회전을 원거리 `full` 에서** 가져온다. 그 대가를 처음으로 쟀다.

> ⚠️ **이 절의 제목과 결론은 한 번 뒤집혔다.** 최초 판은 `coarse` 만 보고
> *"원거리 `full` 경로가 실제 제조사 편차에서 무너진다"* 였다. **틀렸다** — §2·§5 참조. 횡단 정리 #38.

## ★ 1. 먼저 실제 편차를 쟀다 — 두 번째 FOUP CAD 와의 표면거리

사용자가 제공한 참고 CAD(`assets/cad/foup-300mm_check_only_body/FOUP 300.stl`, cm 단위)와 비교.
축 대응은 **24가지 축정렬 회전 전수 탐색 + 병진 Powell 최적화**로 정했다 — 둘 다 **Z-up**,
**Z 축 270° 회전 + 병진 (3.58, 0.06, 0.13)mm**.

> 🔴 **이 정렬은 처음에 180° 틀렸었다**(사용자가 `views_compare.png` 의 XY 뷰에서 발견).
> 회전마다 병진을 따로 재최적화해 같은 방법으로 재보면 **90° 중앙 7.95mm / 270° 5.57mm** —
> 외곽이 대략 대칭이라 **표면거리로는 잘 안 갈린다.** 아래 수치는 **정정 후**의 것이다. 횡단 정리 #39.

우리 `full.ply` 표면에서 면적 균등 샘플 18만점(시드 3개 합침) → 상대 메쉬까지의 표면거리:

| 영역 | 중앙 | 평균 | p95 | >10mm |
|---|---|---|---|---|
| flange (표준부) | **4.87mm** | 5.05mm | 10.19mm | 5.4% |
| **body (비표준부)** | **6.13mm** | **10.76mm** | **35.5mm** | **39.3%** |
| 전체 | 5.94mm | 10.53mm | 35.1mm | 37.9% |

외곽 치수 차 **15 / 3 / 12mm**(x/y/z), 볼록껍질 부피 46.3 L vs 39.2 L(**15%**),
표면적 2.033 vs 1.685 m²(**17%**).
→ **cm 급이 확인된다.** 이 값이 아래 δ 의 눈금을 정해준다.
⚠️ **flange 도 중앙 4.87mm 어긋난다** — SEMI 는 **테두리와 중심 홀만** 규정한다. 단 이 CAD 의 flange 는
사용자가 *"이상하다"* 고 한 것이라 **상한으로** 읽는다. 이 값이 §4 의 δ=5 눈금을 정한다.

## ★★★ 2. 교란 실험 — CAD 만 틀리게 하고 관측은 그대로

`spatial_vision.cad.perturb_mesh` 로 **body 정점만** 저주파 장(파장 = 물체 크기 급)을 따라 법선 방향
±δ 밀고 **flange 는 고정**(AABB 안 변위 0, 경계 30mm smoothstep). 네 δ 모두 watertight,
**flange 정점 이동 0**. 관측(`dr2_far` 40프레임, ISM 마스크, stereo depth)은 **그대로** 두고
FoundationPose 에 주는 CAD 만 바꿨다. δ 당 시드 3개.

원거리 `full`, KPI(t≤5mm & R≤3°). **coarse 와 refined 를 반드시 함께 본다:**

| δ(평균 변위) | coarse KPI | coarse t중앙 | **refined KPI** | **refined t중앙** | refined R중앙 | 뒤집힘 |
|---|---|---|---|---|---|---|
| **0 (기준)** | 40/40 | 1.634 | **40/40** | **1.102** | 0.637 | 0 |
| 2mm | 39.3/40 | 2.750 | **40/40** | **1.060** | 0.646 | 0 |
| **5mm** (실제 중앙값) | 21.3/40 | 4.949 | **40/40** | **1.071** | 0.691 | 0 |
| **10mm** | 1.7/40 | 9.104 | **40/40** | **1.028** | 0.725 | 0 |
| **20mm** | 0/40 | 19.072 | **37.3/40** | **1.049** | 0.760 | 2.0 |

### ★★★ refine 이 body 형상 불일치를 **거의 완전히 흡수한다**

coarse 의 t 오차는 δ 를 **1:1 로 통과**한다(δ 10 → 9.1mm). 그런데 **refine 을 거치면 δ 와 무관하게
t 중앙 ≈ 1.05mm 로 돌아온다** — δ=10 에서도 **40/40** 이다.

⚠️⚠️ **이 절은 처음에 coarse 만 보고 *"어떤 pose 후처리로도 못 고친다"* 고 적었다. 틀렸다.**
계통 depth 편향과 서명이 **비슷해 보였을 뿐** 성질이 다르다:

| | 계통 depth 편향 | **CAD 형상 불일치** |
|---|---|---|
| 관측 자체 | **틀렸다**(전부 밀림) | **맞다** |
| 틀린 것 | 데이터 | **모델** |
| refine | ❌ 편향된 depth 에 맞출 뿐 | ✅ **옳은 관측에 모델을 맞춰 보정한다** |

coarse 가 나쁜 이유는 초기값이다 — `guess_translation` 이 마스크 내 depth 중앙값과 메쉬 크기로
중심을 잡는데, 모양이 다르면 그 추정이 밀린다. **refine 반복이 그걸 회수한다.**

→ **횡단 정리 #16(중앙값만 보고 우열을 정하면 처방이 뒤집힌다)의 재발이다.**
이번엔 통계가 아니라 **단계**를 하나만 봤다.

### ⚠️ 다만 회전 여유는 준다

refined R 중앙이 0.637 → 0.760° 로 는다(δ=20). KPI 3° 대비 여유는 크지만 **단조 증가**하고,
δ=20 에서 **뒤집힘 2건**이 나온다. body 편차가 아주 크면 결국 무너진다.

## ⚠️ 3. 시드 분산이 크다 — **크기만큼 "어떻게 다른가" 가 중요하다**

δ=5mm 한 조건 안에서 KPI 가 **34/40 · 28/40 · 2/40** 으로 갈린다. 같은 평균 변위라도
**어느 방향으로 어떻게 휘었는지**가 결과를 지배한다. → **δ 하나로 요약하면 안 된다.**

## ★★★★ 4. flange **중간부** 교란 — 여기는 refine 도 못 살린다

> ⚠️ **이 절의 교란은 "테두리 고정" 이 아니다** (§21-4 에서 검산). 외곽선 **곡선 하나**만 0 으로 두고
> 12mm taper 하므로, δ=10 에서 폭 20mm 테두리 띠 **안쪽 정점이 평균 5.55mm**(최대 27.4mm) 움직인다.
> 즉 아래 수치는 *"규격부까지 함께 어긋났을 때"* 다 — 띠 전체를 고정하면 훨씬 완만하다(§21-4). 횡단 정리 #42.

테두리(r=71)와 중심 홀(r=20.5)은 고정하고 **그 사이만** 교란(taper 12mm).
`top_flange.ply` 는 정점이 1,819개뿐이고 대부분 경계에 몰려 있어 **6mm 로 세분화**한 뒤 교란했다
(안 하면 움직일 정점이 177개뿐이라 형상 변화가 아니라 스파이크가 된다). 근접 flange 단독(G1), 40프레임:

| δ | coarse KPI | refined KPI | refined t중앙 | **refined R중앙** | **뒤집힘** |
|---|---|---|---|---|---|
| 원본 | 40/40 | 40/40 | 0.666 | 0.505 | 0 |
| **세분화만**(대조군) | 40/40 | 40/40 | 0.814 | 0.553 | 0 |
| **2mm** | 38.3/40 | 38.3/40 | 1.269 | 0.848 | **1.7** |
| **5mm** (실제 중앙값) | 28.7/40 | **26.7/40** | 2.555 | 1.834 | **10.0** |
| **10mm** | 0.7/40 | **1.3/40** | 7.094 | **75.9** | **22.0** |

세분화 대조군이 40/40 이므로 열화는 전부 교란 탓이다.

### ★★ body 와 **파괴 방식이 다르다 — 그래서 refine 이 안 듣는다**

| | body 교란 | **flange 교란** |
|---|---|---|
| δ=2 뒤집힘 | 0 | **1.7** |
| δ=5 뒤집힘 | 0 | **10.0** |
| δ=10 뒤집힘 | 0 | **22.0 (55%)** |
| 파괴 양상 | t 가 밀림 → **refine 이 회수** | **90°/180° 붕괴** → refine 은 **틀린 극소점을 정련**할 뿐 |

**flange 는 δ=2mm 에서 이미 뒤집히기 시작한다.** 이유는 §flange 의 회전 구속과 같다 —
방향 정보가 **표면의 3.5%, 전부 테두리 경계**에 있어서, 중간부가 흔들리면 그 미약한 신호가 묻힌다.
`full` 은 회전 신호가 340배라 형상이 밀려도 방향을 지킨다.

> **refine 은 평행이동 편향을 고치지 실패한 회전을 못 고친다.**

## ★★★★★ 5. 하이브리드 — **실제 다른 제조사 body 로 검증** (합성 교란보다 이쪽이 정본)

`spatial_vision.cad.build_hybrid_obj` 로 **제공 CAD 의 body + 우리 `top_flange.ply`(바이트 동일)** 를
합쳐 `assets/obj/foup_300_hybrid` 를 만들고, **그것을 씬 객체로 렌더**한 뒤 **우리 CAD 로 추정**했다
(= 실환경의 *"물체는 남의 것, CAD 는 우리 것"*). 분할 템플릿도 우리 CAD 것을 써서 **분할 열화까지 포함**된다.

| 구성 | KPI | R중앙 | t중앙 | t평균 | 뒤집힘 |
|---|---|---|---|---|---|
| 기준씬 + 우리 CAD (coarse) | 40/40 | 0.545 | 1.634 | 1.847 | 0 |
| 기준씬 + 우리 CAD (refined) | 40/40 | 0.637 | 1.102 | 1.182 | 0 |
| **하이브리드씬 + 우리 CAD (coarse)** | **0/40** | 1.961 | **20.793** | 21.079 | 0 |
| **★하이브리드씬 + 우리 CAD (refined)** | **40/40** | 0.695 | **1.228** | 1.284 | 0 |
| 대조: 하이브리드씬 + 하이브리드 CAD (coarse) | 39/40 | 0.643 | 2.436 | 2.572 | 0 |
| 대조: 〃 (refined) | 40/40 | 0.725 | 1.156 | 1.238 | 0 |

**refined 에서 우리 CAD(1.228mm)와 정답 CAD(1.156mm)의 차이가 0.07mm 다.** 합성 교란의 결론과 일치한다.

### ★★ 분할은 전혀 안 무너진다

우리 CAD 템플릿으로 **남의 body** 를 찾았는데 **IoU 0.991 / 검출 40/40 / 오선택 0** 이다
(우리 씬에서의 0.915보다 오히려 높다). **ISM 은 CAD 형상 불일치에 강건하다.**

## ⚠️ 6. 한계 — 반드시 함께 읽을 것

1. **하이브리드의 flange 는 우리 것 그대로다.** 실제로는 flange 도 **중앙 4.87mm** 어긋난다(§1).
   위 §4 가 그 축을 따로 쟀고, **거기서는 refine 이 안 듣는다.**
2. **저주파 합성 교란은 실제보다 가혹하다** — 모든 정점을 한 방향으로 함께 민다. 실제 제조사 차이는
   **국소 구조**(측면 래치·외곽 곡률)라 정합에 덜 해롭다. coarse 수치를 실제 값으로 읽으면 안 된다.
3. **δ=20 에서 뒤집힘 2건**이 나온다 — refine 의 흡수력에도 한계가 있다.
4. **한 쌍의 CAD 로만 쟀다.** 제조사가 더 다양하면 어떤 축이 튀는지 모른다.

## 7. 이것이 바꾸는 것

| | §20 최초 결론(coarse만) | **정정** |
|---|---|---|
| 원거리 `full` + refine | "제조사 바뀌면 무효" | ✅ **body 불일치에 강건**(δ≤10 에서 40/40, 실측 CAD 로도 1.23mm) |
| 원거리 `full` coarse only | — | ❌ **t 가 δ 를 1:1 통과** — refine 을 끄면 안 된다 |
| G1 근접 flange | "CAD 불일치에 유일하게 강건" | ❌ **철회.** flange 도 어긋나고, **δ=2mm 에서 뒤집히기 시작**한다 |
| 분할 | "더 나쁠 것" | ✅ **영향 없음** (IoU 0.991) |

> ★ **처방이 뒤집힌다: 상관 depth 오차에는 refine 을 꺼야 하고, CAD 불일치에는 refine 을 켜야 한다.**
> 두 위험이 같은 스위치의 반대 방향을 가리킨다 — 어느 쪽이 지배적인지 **실환경에서 먼저 재야** 한다.

### ★ 사용자의 원래 설계 의도와의 대조 (2026-08-10, 기록용)

사용자가 앞선 실험들에서 **2단계 / 근접 `top_flange` 단독**을 계속 밀었던 이유 중 하나가
**"body 도 제조사마다 다르다"** 였다(사용자 확인). 이 측정이 그 판단을 반반으로 가른다:

| | 판정 |
|---|---|
| **위협 인식** | ✅ **맞았다.** body 편차는 실재하고 cm 급이며, **sim 은 이 축을 원천적으로 못 본다**(렌더=CAD). 제 측정은 이 축이 존재하지 않는 세계에서 나온 것이었다 |
| **완화책 선택** | ❌ **역효과다.** flange 로 좁히면 노출되는 **비표준 면적은 줄지만 회전 신호도 같이 줄어**, δ=2mm 에서 뒤집히기 시작한다. `full`+refine 은 δ=10 에서도 40/40 |

핵심은 **면적비가 아니라 신호비**다. `full` 은 형상이 밀려도 남는 방향 신호가 340배라 버티고,
flange 는 신호가 테두리 경계에만 있어 중간부 교란에 묻힌다.

→ **그래서 다음 후보는 "flange 로 간다" 가 아니라 "테두리에만 정합한다"(rim 밴드)** 다.
`top_flange` 전체가 표준부인 게 아니라 **테두리와 중심 홀만** 표준부이므로, 중간부를 마스크에서
빼고 rim 밴드만 쓰면 *표준부 순수성*과 *방향 신호 보존*을 동시에 노릴 수 있다. **미측정.**

## 재현

```bash
for d in 2 5 10 20; do for s in 0 1 2; do
  envs/cad/bin/python -m spatial_vision.cad.perturb_mesh --obj $OBJ --delta-mm $d --seed $s \
      --out runs/mesh_pert/d${d}_s${s}
  envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_far --out runs/mp_pose_d${d}_s${s} \
      --obj runs/mesh_pert/d${d}_s${s} --masks runs/dr2_far_ism --depth stereo \
      --depth-dir runs/dr2_far_onnx --flange-mask-from pose
  envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/dr2_far --obj $OBJ \
      --pred runs/mp_pose_d${d}_s${s}          # ⚠️ eval 의 --obj 는 **참 CAD** 여야 한다
done; done

# --- §4 flange 중간부 교란 (테두리·중심 홀 고정). 근접 런 dr2_near, G1 구성 ---
#     ⚠️ --subdivide-mm 6 없이 하면 움직일 정점이 177개뿐이라 스파이크가 된다
for d in 0 2 5 10; do for s in 0 1 2; do
  envs/cad/bin/python -m spatial_vision.cad.perturb_mesh --obj $OBJ --region flange \
      --delta-mm $d --seed $s --taper-mm 12 --subdivide-mm 6 --out runs/mesh_pert/fl${d}_s${s}
  envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/fp_pose_fl${d}_s${s} \
      --obj runs/mesh_pert/fl${d}_s${s} --primary flange --masks runs/dr2_near_sam3fl \
      --depth stereo --depth-dir runs/dr2_near_onnx
  envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/dr2_near --obj $OBJ \
      --pred runs/fp_pose_fl${d}_s${s}
done; done

# --- §5 하이브리드 (실제 남의 body + 우리 flange). 씬 객체는 하이브리드, CAD 는 우리 것 ---
HYB=assets/obj/foup_300_hybrid
envs/cad/bin/python -m spatial_vision.cad.build_hybrid_obj --obj $OBJ \
    --body-cad "assets/cad/foup-300mm_check_only_body/FOUP 300.stl" --body-scale 10 --out $HYB
envs/cad/bin/python -m spatial_vision.cad.build_usd --obj $HYB
# ⚠️ USD 를 다시 만들었으면 **캡처부터** 다시 한다. 옛 USD 로 찍은 프레임에 새 메쉬로 pose 를 내면
#    R 오차 179.7° 가 나온다(실제로 한 번 겪었다). `stat -c %y` 로 mesh.usda 와 frame 의 시각을 대조할 것.
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $HYB/mesh.usda \
    --out runs/hyb_far --frames 40 --seed 2024 --fx 1200 --distance-m 0.8 1.2 \
    --hdri assets/env/hdri/Indoor --ground-material --ground-textures assets/env/ground \
    --body-material --flange-color 0.03 0.03 0.03 --light-fixtures 4 --light-fixtures-active 1 3 \
    --fixture-intensity 600 2200 --dome-intensity 110 210 --color-temperature-k 3500 5200
envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx --in runs/hyb_far --out runs/hyb_far_onnx \
    --scale 0.75 --model weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx
# 분할 템플릿도 **우리 CAD** 것 — 실환경의 "남의 물체를 우리 템플릿으로 찾는다" 를 그대로 재현
envs/seg_sam6d/bin/python -m spatial_vision.stages.segment_sam6d --in runs/hyb_far --out runs/hyb_far_ism \
    --target full --templates $OBJ/ism_full --cad $OBJ/full.ply --select center \
    --depth stereo --depth-dir runs/hyb_far_onnx
#   ourcad = 우리 CAD(실험) / hybcad = 정답 CAD(대조군). eval 의 --obj 는 **항상 참 CAD**($OBJ) 다
for tag_cad in "ourcad $OBJ" "hybcad $HYB"; do
  set -- $tag_cad
  envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/hyb_far --out runs/hyb_far_pose_$1 \
      --obj $2 --masks runs/hyb_far_ism --depth stereo --depth-dir runs/hyb_far_onnx --flange-mask-from pose
  envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/hyb_far --obj $OBJ --pred runs/hyb_far_pose_$1
done

# 두 CAD 비교: 24개 축정렬 회전 전수 탐색 → 병진 Powell 최적화 → trimesh.proximity.signed_distance
#   ⚠️ 표본 25만점은 OOM(exit 137). 6만점 × 시드 3개로 나눠 모은다.
#   ⚠️ 정렬은 **지표로 확정하지 말 것** — `views_compare.png` 의 XY 뷰를 눈으로 볼 것(#39)
```

**산출물 경로** (사용자 직접 확인용)

| 경로 | 내용 |
|---|---|
| `assets/obj/foup_300_hybrid/` | `full.ply` `body.ply` `top_flange.ply`(원본 바이트 동일) `mesh.usda` `views_compare.png` |
| `runs/hyb_far/frame_0000..0039/` | `left.png` `right.png` `mask_full.png` `mask_flange.png` `pose_gt.json` |
| `runs/hyb_far_ism/` | 분할 결과 + `metrics_seg.json` (IoU 0.991) |
| `runs/hyb_far_pose_ourcad/` | **우리 CAD 추정** — `overlay.png` `metrics_pose.json` |
| `runs/hyb_far_pose_hybcad/` | 정답 CAD 대조군 |
| `runs/mesh_pert/{d,fl}<δ>_s<seed>/` | 교란 메쉬 + `meta_perturb.json`(달성 δ·고정영역 검사) |

---

# ★★ 21. rim 밴드 정합 — **면역은 실재하지만 값이 비싸고, 원거리 `full` 이 공짜로 이긴다** (2026-08-10)

> 📐 **측정 조건** — `foup_300_semi_rim*` (밴드 폭 1~30mm) · `runs/dr2_near`(`fx 1200 @1280×720`, 0.35~0.50m) · **n=40**.

§20 이 남긴 후보(`PIPELINE_CATALOG §2.2 S⑤`)를 측정했다. 가설은
*"`top_flange` 전체가 아니라 **테두리 밴드만** 정합에 쓰면 표준부 순수성과 방향 신호를 동시에 지킨다"* 였다.
근거는 둘 — SEMI 는 **테두리와 중심 홀만** 규정하고(§20-1: flange 도 중앙 4.87mm 어긋난다),
flange 의 **방향 정보는 전부 테두리**에 있다(중심 홀은 완전한 원이라 yaw 정보 0).

**결론: 가설의 두 전제는 모두 맞았고, 그런데도 채택하지 않는다.** 아래 §5 가 이유다.

> ⚠️ **이 절은 밴드 폭을 한 번 고쳐서 다시 쟀다.** 초기 판은 10~30mm 로 재고 *"30mm 가 손익분기"* 라고
> 적었는데, **실제 규격 띠는 2~3mm** 다(사용자 확정 — §2). 결론(기각)은 같지만 **격차가 더 벌어졌다.**

## 1. 어떻게 "테두리만" 정합하는가 — **모델과 마스크를 같은 도형으로 자른다**

| 쪽 | 도구 | 방법 |
|---|---|---|
| **모델** | `cad.build_rim_obj --band-mm W` | XY 외곽선을 안쪽으로 W mm **offset** 한 띠를 프리즘으로 밀어 flange 와 boolean 교집합 → `top_flange.ply` 를 밴드로 교체한 obj (`full.ply` 는 원본 바이트 그대로) |
| **관측** | `pose_fp --mask-band-mm W` | ① coarse: flange 마스크를 반지름 `w_px = W·fx/Z` 원판으로 **침식**해 뺀 고리 (**GT 불필요**) ② refine: coarse pose 로 밴드 메쉬를 **삼각형 합집합 투영**(원근 단축까지 정확) |

**반드시 둘 다 잘라야 한다.** depth 는 마스크 밖이 0 으로 지워지므로 — 모델만 바꾸면 마스크에 남은
중간부 depth 를 정합기가 *없는 표면*에 맞추려 들고, 마스크만 줄이면 모델이 중간부를 렌더해 *빈 관측*과 비교한다.

⚠️ **반경으로 자르면 안 된다.** 이 flange 외곽은 원이 아니라 **모서리 라운드된 정사각형**(변 142)이고
변 중앙·모서리마다 **오목한 노치**가 있다. 반경 컷은 모서리만 남기고 변 중앙을 날리며,
**볼록껍질**로 잡으면 노치 위에 다리를 놓아 노치 근방을 빠뜨린다(§3b). 진짜 윤곽선까지의 거리로 잘라야
영상의 **원판 침식**과 같은 도형이 된다 — `--outline {true,hull}` 로 둘 다 만들 수 있다.

(20mm 부터는 아래쪽 보스가 통째로 들어와 표면적이 뛴다 — 그건 이미 표준부가 아니다. §2 참조.)

## ★ 2. 실제 규격 띠는 **2~3mm** 다 — 첫 실험의 10~30mm 는 표준부가 아니었다

⚠️ **이 절은 한 번 다시 쟀다.** 처음에는 밴드를 10·15·20·30mm 로 잡고 *"30mm 가 손익분기"* 라고 적었는데,
사용자가 `rim_band_compare.png` 를 보고 **"rim30 은 이미 다른 FOUP 에서 달라지는 부분까지 포함한다,
실제 테두리 두께는 2~3mm"** 라고 지적했다(2026-08-10). 맞다 — 규격이 잡는 것은 **테두리와 중심 홀**이고
*"테두리 규격이 맞으면 그 안쪽은 제조사마다 조금씩 다르다"*. 30mm 짜리 띠는 표준부가 아니므로
**"30mm 가 손익분기" 는 무의미한 문장**이었다. 아래는 실제 폭(1·2·3·5mm)으로 다시 잰 것이고,
10~30mm 는 *"규격 띠가 그만큼 넓다면"* 의 민감도 곡선으로만 남긴다.

밴드 폭별 크기(**전부 진짜 윤곽 기준으로 통일**) — XY 면적 / 표면적 비율: `1mm` 2.9/15.7% ·
`2mm` 5.7/17.4% · `3mm` 8.6/19.1% · `5mm` 14.1/22.3% · `10mm` 27.1/30.1% · `15mm` 39.2/45.2% ·
`20mm` 50.3/71.9% · `30mm` 69.2/81.8%.
**XY 면적은 3%인데 표면적은 16% 다** — 바깥 **측벽**(높이 8mm)이 통째로 남기 때문이고,
방향 신호도 거기 있다. 그래서 1mm 밴드도 완전히 무력하지는 않다.

## ★★ 3. 실제 폭에서의 성능 — **최선 33/40. 어떤 구성도 KPI 를 못 채운다**

근접 `dr2_near` 40프레임, `--primary flange`. 마스크를 세 경로로 나눴다: **GT 정확 투영**(⚠️ 자기순환, 상한) /
**침식**(GT-free, 배포) / **G9 구조**(원거리 coarse 로 초기화 후 근접 밴드로 refine). 전부 refined 기준:

| 모델 | 마스크 | KPI | R중앙 | t중앙 | 뒤집힘 |
|---|---|---|---|---|---|
| **flange 전체**(기준 G1) | SAM3 | **40/40** | **0.618** | **0.801** | 0 |
| `rim1` | GT 투영 | 27/40 | 2.242 | 2.540 | 1 (90°) |
| `rim1` | 침식 | **14/40** | 4.000 | 3.628 | 2 |
| `rim1` | G9 | 25/40 (coarse 27) | 2.160 | 2.024 | **0** |
| `rim2` | GT 투영 | 30/40 | 2.207 | 3.028 | **0** |
| `rim2` | 침식 | 18/40 | 2.970 | 2.672 | 0 |
| `rim2` | G9 | 24/40 (coarse 27) | 2.139 | 2.490 | **0** |
| `rim3` | GT 투영 | 28/40 | 2.293 | 3.348 | 1 |
| `rim3` | 침식 | 19/40 | 3.101 | 2.554 | 1 |
| `rim3` | G9 | 24/40 (coarse 25) | 2.179 | 2.913 | **0** |
| `rim2`+홀띠 2mm | G9 | 24/40 | 2.636 | **1.541** | 0 |
| `rim3`+홀띠 3mm | G9 | 20/40 | 2.718 | 1.720 | 0 |
| `rim5` | GT 투영 / 침식 | 24/40 / 25/40 | 2.59 / 2.02 | 3.37 / 2.80 | 0 |
| `rim10` | GT 투영 | 30/40 | 1.892 | 2.279 | 2 |
| `rim15` | GT 투영 | 28/40 | 1.765 | 2.987 | **7** |
| `rim20` | GT 투영 / 침식 | 38/40 / 37/40 | 1.98 / 2.13 | 1.99 / 2.11 | 0 |
| `rim30`(표준부 아님) | GT 투영 / 침식 | **40/40** | 0.69 | 1.15 / 1.03 | 0 |
| **`rim3` (볼록껍질 밴드)** | GT 투영 | **31/40** | 1.947 | 2.827 | 1 |
| 〃 | **GT depth** | **33/40** | 1.841 | 2.724 | **0** |

읽히는 것 넷.

1. **coarse 가 t 에서 6~8mm 밀린다.** FoundationPose 의 `guess_translation` 이 마스크와 **메쉬 크기**로
   중심을 잡는데 고리 메쉬는 그 추정이 구조적으로 틀린다. **얇은 밴드는 초기값을 스스로 잡으면 안 된다** —
   G9(원거리 초기화)가 **뒤집힘 0** 으로 유일하게 안정적이다.
2. **여기서는 마스크가 병목이다.** 넓은 밴드(30mm)에서는 침식과 GT 투영이 같았는데(t 1.045 vs 1.053),
   **1~3mm 에서는 갈린다**(27~30 → 14~19). 밴드가 **3~8px** 라 SAM3 경계 오차에 통째로 잡아먹힌다.
3. **중심 홀 띠는 t 만 고친다.** `rim3`+홀띠로 t 가 2.91 → **1.72mm** 로 가장 좋아지는데 R 은 2.7° 그대로다.
   **홀은 완전한 원이라 yaw 정보가 0** — 예측대로이고, KPI 는 R 에서 막힌다.
4. **최선이 33/40 (82.5%)** 이다. GT depth + GT 마스크라는 **두 겹의 자기순환**을 다 줘도 KPI 40/40 에 못 간다.

### ⚠️ 3b. 테두리를 **정확히** 따라가면 오히려 나빠진다 — 이유는 아직 모른다

처음 구현은 XY 윤곽을 **볼록껍질**로 잡았는데, 사용자가 렌더를 보고 **"중간중간 뾰족하게 파인 부분(노치)이
rim 으로 처리가 안 됐다, 테두리 모양을 그대로 따야 한다"** 고 지적했다(2026-08-10). **맞는 지적이다** —
이 테두리에는 변 중앙·모서리마다 오목한 노치가 있고 볼록껍질은 그 위에 다리를 놓아 **노치 근방을 통째로
빠뜨린다**(윤곽 면적 차 200mm²). `trimesh.path.polygons.projected` 로 진짜 윤곽을 쓰도록 고쳤다.

그런데 **고친 쪽이 일관되게 조금 나쁘다**(GT 투영 마스크, refined):

| W | 진짜 윤곽 | 볼록껍질 |
|---|---|---|
| 1mm | 27/40 · t 2.540 | **32/40** · t 2.125 |
| 2mm | 30/40 · t 3.028 · **뒤집힘 0** | 31/40 · t 2.663 · 뒤집힘 1 |
| 3mm | 28/40 · t 3.348 | **31/40** · t 2.827 |
| 3mm, G9 | 24/40 · t 2.913 | **28/40** · t 2.225 |

두 가지 설명을 배제했다.

- **실행 편차 아니다** — 같은 명령 3회 반복이 **마지막 자리까지 동일**했다.
  ⚠️ **정정 (2026-08-19)**: 그때의 관측은 맞지만 *"FoundationPose 는 결정론적"* 이라는 **결론은
  틀렸다.** FP 는 **이분적**이라 여러 번 같다가도 어긋난다 — 같은 입력에서 **ΔR 중앙 0.146° ·
  최대 0.662°**(`§35-2l-6`, 교훈 #86). **여기 결론(실행 편차 아님) 자체는 유지된다** —
  이 표의 차이는 27↔32/40 급으로 재실행 잡음(0.15°)보다 훨씬 크다.
- **경계 depth 오차 아니다** — `--depth gt` 로 바꿔도 순서가 같다(27/40 vs **33/40**).
- **정보 부족도 아니다** — `measure_symmetry` 로 재면 진짜 윤곽 쪽이 **90° 대칭을 깨는 표면 14.43%**
  (위에서 보이는 것 2.04%)로 볼록껍질(8.27% / 0.85%)보다 **오히려 많다.** 노치는 방향 신호가 맞다.

즉 **정보는 늘었는데 정합이 나빠진다.** 남은 가설은 정합기 쪽 — 그리고 **§22 가 그 눈금을 재줬다**:
FoundationPose refiner 의 crop 은 `diameter×1.2` 를 160×160 으로 줄이므로 여기서 **1px = 1.38mm** 이고,
**밴드 폭 3mm 는 2.2px · 노치 깊이 4mm 는 약 3px** 다. 미세 구조가 해상도 바닥에 있다.
⚠️ 밴드를 좁혀도 diameter 가 안 줄어 **유효 해상도는 전혀 안 좋아진다**(§22-2). **정황이지 인과 증명은 아니다.** 두 밴드 모두 KPI 에 못 가므로 이 축을 더 파지 않았다 — 기록만 남긴다.
→ `--outline hull` 로 대조군을 재현할 수 있다.


## ★★★ 4. 그래도 면역은 실재한다 — **규격 띠 3mm 에서 flange 전체 모델은 붕괴한다**

`perturb_mesh --region flange --rim-band-mm W` 로 **폭 W 의 띠 전체**를 고정하고 안쪽만 교란한다
(밴드 안 변위 **정확히 0.000mm** — 검증함). W=3 이 사용자가 확정한 실제 값이다. 근접, 시드 3개 평균:

| 규격 띠 | δ | **model = flange 전체** (coarse KPI / 뒤집힘 / R중앙) | model = 밴드 (δ 무관) |
|---|---|---|---|
| **3mm (실제)** | **5** (실측 중앙값) | **25.7/40** · 9.7 · 2.196° | `rim3` **31/40**(GT 마스크) / 24/40(침식) |
| **3mm** | **10** | **0.3/40** · **23.0** · **89.4°** ← 붕괴 | 〃 |
| 20mm | 5 | 36.0/40 · 4.0 · 0.916° | `rim20` 39/40 |
| 20mm | 10 | 27.0/40 · 9.7 · 1.823° | 〃 |
| 30mm | 5 | 38.7/40 · 1.3 · 0.551° | `rim30` 40/40 |
| 30mm | 10 | 36.3/40 · 3.7 · 0.830° | 〃 |

**규격 띠가 좁을수록 flange 전체 모델의 손해가 급격히 커진다** — 당연하다, 변하는 면적이 늘어난다.
실제 값(3mm)에서 δ=10 이면 **90° 로 통째로 돌아간다**(R 중앙 89.4°, 뒤집힘 23/40).
→ **근접 flange 계열 안에서만 보면 `rim3` 가 이긴다.** 이건 첫 판(20/30mm)보다 훨씬 큰 차이다.

## ★★★★★ 5. 그런데 **원거리 `full`+refine 은 규격 띠 3mm 에서도 무영향이다**

`--region flange_in_full` 로 **`full.ply` 안의** flange 만(body·3mm 테두리 고정) 교란하고
원거리 `dr2_far` 40프레임 · ISM 마스크로 쟀다. 시드 3개 평균:

| 규격 띠 | δ | coarse KPI | **refined KPI** | **R중앙** | **t중앙** | 뒤집힘 |
|---|---|---|---|---|---|---|
| — | 0 (대조군) | 40/40 | **40/40** | 0.682 | 1.111 | 0 |
| **3mm** | **5** | 38.7/40 | **40/40** | 0.669 | **1.083** | **0** |
| **3mm** | **10** | 39.3/40 | **40/40** | **0.633** | **1.087** | **0** |
| 20mm | 5 | 39.7/40 | 40/40 | 0.665 | 1.120 | 0 |
| 20mm | 10 | 39.7/40 | 40/40 | 0.635 | 1.094 | 0 |

**flange 가 통째로(3mm 테두리만 빼고) δ=10 으로 어긋나도 대조군과 구분이 안 된다.**
flange 는 `full` 표면의 일부일 뿐이고 회전 신호가 340배라 묻힌다. §20 의 body 교란과 같은 구조다.

> 그래서 결론은 밴드 폭을 고쳐도 바뀌지 않는다 — 오히려 **격차가 벌어진다**:
> 실제 규격 폭에서 근접 계열은 **배포 27/40 · 천장 33/40** 인데,
> 원거리 `full`+refine 은 **같은 불일치 하에서 40/40 · t 1.09mm** 다.

## ★★ 6. 상관 depth 오차 하의 밴드 — **개선 없다**

`eval.perturb_depth --mode corr --corr-px 60` 로 근접 depth 를 오염시켰다. 대조군은 기존 G1
(`pose_P2_corr60_*`). coarse 기준:

| 실제 평균 \|ΔZ\| | flange 전체 | `rim3` (G9 구조) | `rim20` | `rim30` |
|---|---|---|---|---|
| 0 (clean) | **40/40** · 0 · t 0.67 | 25/40 · 0 · t 2.13 | 38/40 · 0 · t 1.99 | 40/40 · 0 · t 1.03 |
| 3.25mm | 38/40 · 0 · 1.25 | 27/40 · 0 · 2.27 | 30/40 · 1 · 3.28 | **40/40** · 0 · 1.44 |
| 5.41mm | 33/40 · 0 · 1.93 | 21/40 · 0 · 2.33 | **18/40** · 2 · 4.29 | 32/40 · 0 · 2.15 |
| 10.81mm | 16/40 · **4** · 6.06 | 13/40 · **0** · 3.47 | **5/40** · 8 · 12.16 | 12/40 · 3 · 5.65 |
| 18.35mm | 3/40 · 15 | — | 1/40 · 13 | 4/40 · 13 |
| 26.94mm | 0/40 · 22 | — | 0/40 · 26 | 2/40 · 21 |

- **`rim20` 은 가설대로 더 나쁘다** — 좁은 고리는 상관 오차를 평균화하지 못한다.
- **`rim3`+G9 는 모든 수준에서 뒤집힘 0 을 유지하지만 KPI 는 계속 낮다**(clean 에서 이미 25/40). ⚠️ 뒤집힘 0 은 **원거리 초기화의 효과**이고
  밴드의 효과가 아니다(같은 초기화를 준 flange 전체 대조군을 안 돌렸다 — **귀속 미확정**).
- 어느 구성도 ≥10mm 에서 살아남지 못한다. **밴드가 이 축을 바꾸지 않는다.**

### ⚠️ 18mm 에서 보인 `rim30` 의 "뒤집힘 우위" 는 **잡음 시드 하나의 착시였다**

첫 시드에서 뒤집힘 **9 vs 15** 가 나와 *"밴드가 회전을 40% 더 지킨다"* 로 읽힐 뻔했다. 시드를 늘리니:

| 잡음 시드 | flange 전체 (뒤집힘 / KPI) | `rim30` (뒤집힘 / KPI) |
|---|---|---|
| 12345 (18.35mm) | 15 / 3 | **13** / 4 |
| 777 (18.50mm) | **8** / 8 | 12 / 6 |
| 20260810 (18.88mm) | 15 / 6 | **10** / 5 |
| **평균** | **12.7 / 5.7** | **11.7 / 5.0** |

⚠️ 위 시드별 값은 **볼록껍질 밴드**로 낸 것이고, 진짜 윤곽으로 통일한 뒤 시드 12345 는 9 → 13 이 됐다.
순서가 시드마다 뒤집힌다는 **결론은 그대로**다(오히려 강화된다).

**순서가 시드마다 뒤집힌다** → 차이는 잡음이다. 횡단 정리 #12 의 재발이다(이번엔 프레임 수가 아니라
**잡음 실현 1개**를 봤다). → **오염 실험은 잡음 시드를 최소 3개** 돌린다.

## 7. 판정과 남는 쓸모

| | 판정 |
|---|---|
| *"밴드만 쓰면 표준부 순수성을 지킨다"* | ✅ 맞다 — 정의상 불일치 0 |
| *"규격 띠는 2~3mm 다"* (사용자) | ✅ **맞다. 첫 실험의 10~30mm 는 표준부가 아니었다** — "30mm 손익분기" 는 철회 |
| *"근접 계열 안에서는 밴드가 낫다"* | ✅ **실제 폭에서 훨씬 크게 맞다** — δ=10 에서 flange 전체는 0.3/40, `rim3` 는 31/40 |
| *"테두리에 방향 신호가 있으니 밴드로도 충분하다"* | ❌ **부족하다.** 실제 폭에서 배포 **27/40**(원거리 초기화 필수), GT depth+GT 마스크를 다 줘도 **천장 33/40** |
| *"테두리 모양을 그대로 따야 한다"* (사용자) | ✅ **기하는 맞는 지적** — 볼록껍질이 노치를 빠뜨리고 있었다. 다만 고치니 **성능은 오히려 조금 나빠졌다**(§3b, 원인 미규명) |
| *"밴드는 depth 오염에 더 강할 것"* | ❌ 아니다 (§6) |
| *"그러므로 rim 밴드로 가야 한다"* | ❌ **기각.** 원거리 `full`+refine 이 **같은 불일치 하에서 40/40 · t 1.09mm** (§5) |
| 남는 쓸모 | flange 불일치가 실측으로 크게 확인되고 **원거리를 못 쓰는** 배치에서, `rim3` **+ 원거리 초기화**가 근접 단독보다 낫다 |

⚠️ **한계** — (a) 불일치는 **CAD 만 틀리게 만든 대리 측정**이다 — 실물 스캔이 정본이다(§20-6).
(b) 전부 n=40. (c) `rim3` 의 뒤집힘 0 이 밴드 때문인지 원거리 초기화 때문인지 **귀속이 미확정**이다.
(d) 실제 규격 띠 폭 2~3mm 는 **사용자 확정치**이고 SEMI 문서로 재확인하지 않았다.

## 재현

```bash
OBJ=assets/obj/foup_300_semi
# --- 밴드 obj (모델 쪽). **1·2·3mm 가 실제 규격 폭**, 5~30 은 민감도 곡선용 ---
#     ⚠️ 기본 --outline true 는 노치까지 따라간다. --outline hull 은 볼록껍질 대조군(§3b)
for w in 1 2 3 5 10 15 20 30; do
  envs/cad/bin/python -m spatial_vision.cad.build_rim_obj --obj $OBJ --band-mm $w \
      --out assets/obj/foup_300_semi_rim$w
  envs/cad/bin/python -m spatial_vision.cad.build_rim_obj --obj $OBJ --band-mm $w --outline hull \
      --out assets/obj/foup_300_semi_rim${w}hull
done
# 최외곽 테두리 + **중심 원**을 둘 다 남기는 변형 (규격은 이 둘이다)
envs/cad/bin/python -m spatial_vision.cad.build_rim_obj --obj $OBJ --band-mm 3 --hole-band-mm 3 \
    --out assets/obj/foup_300_semi_rim3h3
# --- ② 배포 경로: 침식 마스크(GT 불필요). 모델과 **같은 폭**을 줘야 한다 ---
for w in 1 2 3 5 15 20 30; do
  envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/rim_erode_w$w \
      --obj assets/obj/foup_300_semi_rim$w --primary flange --masks runs/dr2_near_sam3fl \
      --mask-band-mm $w --depth stereo --depth-dir runs/dr2_near_onnx
  envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/dr2_near --obj $OBJ --pred runs/rim_erode_w$w
done
# --- ① 상한 대조군: GT pose 로 밴드를 정확 투영한 마스크 (⚠️ 자기순환, 상한 전용) ---
envs/cad/bin/python -m spatial_vision.cad.render_band_masks --capture runs/dr2_near \
    --obj assets/obj/foup_300_semi_rim20 --pose gt --out runs/rim_maskgt_w20
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/rim_gtmask_w20 \
    --obj assets/obj/foup_300_semi_rim20 --primary flange --masks runs/rim_maskgt_w20 \
    --flange-mask-from seg --depth stereo --depth-dir runs/dr2_near_onnx
# --- ③ 배포 최선: G9 구조 — 원거리 coarse 로 초기화하고 근접 밴드로 refine.
#     얇은 밴드는 `guess_translation` 이 구조적으로 틀리므로 **초기값을 스스로 잡으면 안 된다** ---
for w in 1 2 3; do
  envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/rim_g9_w$w \
      --obj assets/obj/foup_300_semi_rim$w --primary flange --masks runs/dr2_near_sam3fl --mask-band-mm $w \
      --depth stereo --depth-dir runs/dr2_near_onnx \
      --init-from runs/dr2_far_pose --init-capture runs/dr2_far --rel-from-gt
done
# 홀 띠를 쓰면 마스크에도 같은 원판을 더해야 한다 (--mask-hub-r-mm = r_hole + W)
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/rim_g9_rim3h3 \
    --obj assets/obj/foup_300_semi_rim3h3 --primary flange --masks runs/dr2_near_sam3fl \
    --mask-band-mm 3 --mask-hub-r-mm 23 --depth stereo --depth-dir runs/dr2_near_onnx \
    --init-from runs/dr2_far_pose --init-capture runs/dr2_far --rel-from-gt
# §3b 원인 배제: 실행 편차(3회 반복 → 마지막 자리까지 동일) · 경계 depth(--depth gt) · 정보량
envs/cad/bin/python -m spatial_vision.cad.measure_symmetry --obj assets/obj/foup_300_semi_rim3 --meshes top_flange

# --- §4 규격 밴드를 **띠 전체로** 고정한 교란 (model=flange 전체 쪽 손해를 잰다) ---
for W in 3 20 30; do for d in 5 10; do for s in 0 1 2; do   # W=3 이 실제 값
  envs/cad/bin/python -m spatial_vision.cad.perturb_mesh --obj $OBJ --region flange \
      --rim-band-mm $W --delta-mm $d --seed $s --taper-mm 12 --subdivide-mm 6 \
      --out runs/mesh_pert/rb${W}_d${d}_s${s}
  envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/rimpert_full_rb${W}_d${d}_s${s} \
      --obj runs/mesh_pert/rb${W}_d${d}_s${s} --primary flange --masks runs/rim_maskgt_full \
      --flange-mask-from seg --depth stereo --depth-dir runs/dr2_near_onnx
done; done; done

# --- §5 원거리 `full` 대조군. ⚠️ full.ply 를 통째로 6mm 세분화하면 2.2M 삼각형 → nvdiffrast OOM.
#     `--region flange_in_full` 은 flange 성분만 세분화한다(별개 solid 라 T-junction 없음) ---
for W in 3 20; do for d in 0 5 10; do for s in 0 1 2; do
  envs/cad/bin/python -m spatial_vision.cad.perturb_mesh --obj $OBJ --region flange_in_full \
      --rim-band-mm $W --delta-mm $d --seed $s --taper-mm 12 --subdivide-mm 6 \
      --out runs/mesh_pert/fif${W}_d${d}_s${s}
  envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_far --out runs/rimpert_far_fif${W}_d${d}_s${s} \
      --obj runs/mesh_pert/fif${W}_d${d}_s${s} --masks runs/dr2_far_ism --depth stereo \
      --depth-dir runs/dr2_far_onnx --flange-mask-from pose
done; done; done

# --- §6 상관 depth 오차 하의 밴드. 오염 depth 는 `runs/pert/near_corr60_<mm>` 를 재사용한다 ---
#     대조군 `runs/pose_P2_corr60_<mm>` = 같은 depth 의 flange 전체(G1) — 새로 돌릴 필요 없다
for lv in 3 5 10 17 25; do for w in 20 30; do
  envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/rimcorr_w${w}_c${lv} \
      --obj assets/obj/foup_300_semi_rim$w --primary flange --masks runs/dr2_near_sam3fl \
      --mask-band-mm $w --depth stereo --depth-dir runs/pert/near_corr60_$lv
done; done
# ⚠️ 잡음 시드 하나로 판정하지 말 것 — 18mm 에서 순서가 시드마다 뒤집힌다(§6)
for sd in 777 20260810; do
  envs/stereo_onnx/bin/python -m spatial_vision.eval.perturb_depth --in runs/dr2_near_onnx \
      --capture runs/dr2_near --out runs/pert/near_corr60_17_s$sd --mode corr --corr-px 60 \
      --target-mm 17 --seed $sd
done
# 실제 폭(3mm)은 G9 구조로. 오염된 **원거리** pose 로 초기화해야 공정하다
for lv in 3 5 10; do
  envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/dr2_near --out runs/rimcorr_g9w3_c$lv \
      --obj assets/obj/foup_300_semi_rim3 --primary flange --masks runs/dr2_near_sam3fl --mask-band-mm 3 \
      --depth stereo --depth-dir runs/pert/near_corr60_$lv \
      --init-from runs/pose_P1_corr60_$lv --init-capture runs/dr2_far --rel-from-gt
done
```

**산출물 경로** (사용자 직접 확인용)

| 경로 | 내용 |
|---|---|
| `assets/obj/rim_band_compare.png` | 밴드 폭별 3면 비교 렌더(10~30mm) — 회색 = 원본 `top_flange`, 빨강 = 남긴 밴드 |
| **`assets/obj/rim_band_compare_thin.png`** | **실제 규격 폭(1·2·3mm) + 홀 띠 비교 렌더, top 뷰** — 노치를 따라가는지 여기서 본다. 정본 |
| `assets/obj/foup_300_semi_rim{1,2,3,5,10,15,20,30}/` | 밴드 obj + `meta_rim.json`(면적비·watertight) |
| `assets/obj/foup_300_semi_rim{1,2,3}hull/` | 볼록껍질 대조군(§3b) |
| `assets/obj/foup_300_semi_rim{2h2,3h3,20h32}/` | 중심 홀 띠를 함께 남긴 변형 |
| `runs/rim_erode_w{15,20,30}/` | 배포 경로(침식 마스크) — 프레임마다 `mask_band.png` `mask_flange_proj.png` |
| `runs/rim_maskgt_w*/`, `runs/rim_gtmask_w*/` | 상한 대조군 (GT 투영 마스크) |
| `runs/rim_g9_w{1,2,3}/`, `runs/rim_g9_rim{2h2,3h3}/` | 원거리 초기화 + 근접 밴드 refine (**뒤집힘 0 구성**) |
| **`runs/<pose런>/overlay_sheet.png`** | **육안 검사용 컨택트 시트** — GT 빨강 / 예측 초록 / 사용 마스크 파랑. `spatial_vision.viz.overlay_pose` 로 어느 런에든 만든다 |
| `runs/mesh_pert/perturb_heatmap.png` | 교란 메쉬의 **정점 변위 히트맵**(파랑=고정, 빨강=최대) — 무엇을 고정했는지 눈으로 확인 |
| `runs/pert/depth_corruption_compare.png` | clean / 5.4mm / 18.4mm 오염 depth 컬러맵 비교 |
| `runs/dr2_near_flonly/mask_hull_vs_faces.png` | **투영 마스크 볼록껍질 vs 삼각형합집합** — 노치가 메워지는 것을 확대해서 본다(교훈 #47) |

> ⚠️ **밴드 obj 는 전부 `--outline true` 로 다시 지었다**(2026-08-10). 처음엔 `rim1~3` 만 고치고
> `rim5~30` 은 볼록껍질 시절 것을 그대로 두어 **표 안에 두 규약이 섞여 있었다**(사용자 지적).
> 통일 후 넓은 밴드가 나빠졌다 — `rim10` 37→30/40, **`rim15` 39→28/40(뒤집힘 0→7)**,
> `rim20`·`rim30` 은 불변. §3b 의 방향(진짜 윤곽이 더 나쁘다)과 일치하고 **결론은 그대로**다.
> 자산이 어느 규약인지는 `meta_rim.json` 의 `outline`·`outline_area_mm2`(진짜 19626 / 껍질 19826)로 판별한다.

> ⚠️ **`pose_fp --flange-mask-proj` 의 기본값이 `faces` 로 바뀌었다**(2026-08-10, 교훈 #47).
> 이전 결과는 전부 `hull` 로 낸 것이고, 재실행하면 refined 가 미세하게 달라진다
> (근접 G1 R 0.618→0.597 · t 0.801→0.827 / 원거리 R 0.637→0.645 · t 1.102→1.070, **KPI 는 40/40 불변**).
> 옛 수치를 재현하려면 `--flange-mask-proj hull` 을 준다. 대조 런: `runs/proj_faces_{near,far}`.
| `runs/mesh_pert/rb{3,20,30}_d<δ>_s<seed>/` | 띠 전체를 고정한 flange 교란 (**rb3 이 실제 값**) |
| `runs/mesh_pert/fif{3,20}_d<δ>_s<seed>/` | `full.ply` 안의 flange 만 교란 (테두리·body 고정) |
| `runs/rimcorr_w{20,30}_c<mm>/` | 상관 depth 오차 하의 밴드 (대조군 `runs/pose_P2_corr60_<mm>`) |
| `runs/rimcorr_g9w3_c<mm>/` | 실제 폭(3mm) + G9 구조의 오염 하 성적 |
| `runs/rimcorr_{flange,w30}_c17_s<seed>/` | 18mm 잡음 시드 3개 재현 — 순서가 뒤집히는 것을 보인 근거 |

---

# ★★ 22. crop·resize 가 만드는 **유효 해상도 천장** (2026-08-10, 코드 확인)

> 🛠 **측정 절이 아니다** — FoundationPose **코드 확인**으로 얻은 해상도 천장(`diameter × crop_ratio / 160`). 거리·`fx` 와 무관한 구조적 값이다.

*"crop 하면 FOUP 이 잘리지 않나, resize 하면 비율이 깨지지 않나"* 라는 질문에서 출발해 실제 코드를 읽었다.
**잘림·비율은 (거의) 문제가 아니고, 진짜 병목은 160×160 이다.**

## 1. FoundationPose — 정사각 crop, diameter 기준 (코드 근거)

`third_party/FoundationPose/Utils.py:579 compute_crop_window_tf_batch`, `method='box_3d'`:
`radius = mesh_diameter * crop_ratio / 2` 를 **카메라 X/Y 로 밀어 투영**하고
`left/right/top/bottom = center ± radius` → **중심 = pose 원점 투영, 정사각**. 그래서 비율은 안 깨진다.

| | 가중치 | `crop_ratio` | `input_resize` |
|---|---|---|---|
| refiner | `2023-10-28-18-33-37` | **1.2** | **160×160** |
| scorer | `2024-01-11-20-02-45` | **1.1** | **160×160** |

## ★★ 2. 유효 해상도는 **거리·카메라와 무관**하다 — 오직 메쉬 diameter 가 정한다

crop 변 = `D·r·fx/Z` px 이고 그것을 160 으로 줄이므로

> **네트워크 입력의 1px = `D × crop_ratio / 160` mm.** `Z` 도 `fx` 도 들어가지 않는다.

거리·해상도는 **버려지는 정보량(축소 배율)** 만 바꾼다. 우리 자산·런 기준(fx 1200):

| 모델 | diameter | 거리 | crop | 축소 | **crop mm/px** | 원본 mm/px |
|---|---|---|---|---|---|---|
| `full.ply` (원거리) | **579.0mm** | 937mm | 890px | 5.56× | **4.34** | 0.78 |
| `top_flange.ply` (근접) | 183.5mm | 437mm | 605px | 3.78× | **1.38** | 0.36 |
| `rim3` 밴드 (근접) | 183.5mm | 437mm | 605px | 3.78× | **1.38** | 0.36 |

- **`full` 은 4.34mm/px 다.** FOUP 을 "350mm" 로 잡으면 2.2mm/px 가 나오지만, `diameter` 는
  **표면 두 점 사이 최대 거리(3D 대각선)** 라 실제로는 **579mm** 다. 2배 비관적으로 봐야 한다.
- **2단계의 해상도 이득은 3.16배**(4.34 → 1.38). 거리 때문이 아니라 **diameter 가 3.16배 작아서**다.
- ⚠️ **`rim3` 밴드는 diameter 가 `top_flange` 와 같다** — 고리라서 외곽 지름이 안 줄기 때문이다.
  **밴드를 좁혀도 유효 해상도는 하나도 안 좋아진다.**

### ★★★ 이것이 §21-3b 의 미규명 가설을 정량화한다

`rim3` 밴드 폭 3mm → 네트워크 입력에서 **3 / 1.38 = 2.2 px**. 노치 깊이 ~4mm → **약 3px**.
즉 **모델 전체가 2px 짜리 고리**로 들어간다. 얇은 밴드가 천장 33/40 에 걸린 것도,
**진짜 윤곽으로 노치를 살려도 나아지지 않은 것도** 이 눈금과 일치한다(노치가 해상도 바닥에 있다).
⚠️ 여전히 **정황이지 인과 증명은 아니다** — 증명하려면 `input_resize` 를 키워 재학습해야 한다.

## ⚠️ 3. "이미지 경계 초과는 예외" 가 아니다 — 원거리에서는 **상시**다

crop 변이 890px 인데 이미지 높이는 **720px** 다. FP 와 같은 공식으로 40프레임을 재보니:

| 런 | crop 변 중앙 | 이미지 밖 비율 중앙 / 최대 | 초과 프레임 |
|---|---|---|---|
| `dr2_far` (`full`) | 890px | **19.1% / 30.7%** | **38/40** |
| `dr2_near` (`flange`) | 605px | 0.0% / 4.5% | 6/40 |

**원거리 최선 구성은 매 프레임 crop 의 1/5 가 패딩인 채로 40/40 을 낸다.**
→ *"물체를 화면 중앙에 두면 회피된다"* 는 **틀렸다.** crop 이 이미지보다 커서 구도로는 못 피한다
(세로 FOV 를 넓히거나 거리를 늘려야 한다). 그리고 **실측상 해롭지 않았다** — 횡단 정리 #17
(잘린 프레임이 오히려 근소하게 정확)과 같은 방향이다.

## ⚠️ 4. SAM3 는 **letterbox 가 아니다** — 비율을 깨는 정사각 리사이즈다

`third_party/sam3/sam3/model/sam3_image_processor.py:24` → `v2.Resize(size=(1008, 1008))`.
우리 입력 1280×720 이 **1008×1008 로 강제**되어 **세로로 1.78배 늘어난 상태**로 네트워크에 들어간다
(마스크는 `original_height/width` 로 역보간되어 나오므로 **출력 기하는 정상**).
학습도 같은 변환이라 in-distribution 이지만, **함의가 하나 있다**:

> 화면비가 바뀌면 왜곡 배율이 바뀐다. **SAM3 exemplar 참조는 배포와 같은 화면비에서 만들어야 한다** —
> 이미 알려진 *"참조는 배포 조건(거리·randomization)에서 만들어야 한다"* 에 **화면비 축이 추가**된다.

**SAM-6D ISM 은 letterbox 가 맞다** — `ResizeLongestSide`(비율 유지 + 패딩) + `CropResizePad`.

## 5. 무엇이 바뀌나

| 우려 | 판정 |
|---|---|
| crop 으로 물체가 잘림 | ❌ diameter 기준이라 형상은 안 잘린다 |
| resize 로 비율 깨짐 (FP) | ❌ 정사각 crop |
| resize 로 비율 깨짐 (**SAM3**) | ✅ **깨진다**(1.78×). 출력은 정상이나 **참조 화면비를 맞춰야 한다** |
| 이미지 경계 초과 | ✅ **원거리 38/40 프레임에서 발생.** 구도로 회피 불가, 다만 실측상 무해 |
| **해상도 손실** | ✅ **실재. `full` 4.34mm/px 가 진짜 천장이다** |

→ 고해상도 카메라의 이득이 FP 단계에서 사라진다는 것은 우리가 이미 독립적으로 봤다:
**fx 952 → 1200 → 1400 에서 측면 오차가 줄지 않는다**(§ M5 확장). 이 절이 그 이유를 설명한다.
**미측정 후속**: `input_resize` 를 320 으로 올리면(학습 분포 밖) 어떻게 되는가.

## 재현

```bash
# crop mm/px = diameter × crop_ratio / 160.  diameter 는 FP 와 같은 방식(centering 후 볼록껍질 최대거리)
# crop 창이 이미지를 넘는지는 Utils.py 의 box_3d 공식을 그대로 옮겨 프레임마다 계산한다.
grep -n "radius = mesh_diameter" third_party/FoundationPose/Utils.py
grep -H "input_resize\|crop_ratio" third_party/FoundationPose/weights/*/config.yml
grep -n "v2.Resize" third_party/sam3/sam3/model/sam3_image_processor.py
```

---

# ★★★★★ 23. 원본 해상도 **테두리 정합** — 단일 시점 최선을 갱신했고, **depth 오염에 거의 면역**이다 (2026-08-10)

> 📐 **측정 조건** — `foup_300_semi` · `runs/ctr_*`(`fx 1200 @1280×720`) · 근접 0.35~0.50m / 원거리 0.8~1.2m · **n=40** · clean + 상관 오염 depth.

§22 가 *"FoundationPose 는 관측 해상도의 4~12배를 버린다"* 를 보였다. 그 버려진 해상도를
**FP 밖에서** 쓰는 스테이지를 만들어 시험했다: `spatial_vision.stages.refine_contour`.

## 1. 방법 — occluding contour(실루엣 모서리) 6-DoF 정합

1. 현재 pose 에서 **실루엣 모서리**를 찾는다(인접 두 면의 앞/뒤향이 갈리는 edge). 래스터화 불필요이고
   **바깥 테두리와 중심 홀 테두리가 자동으로** 잡힌다 — 둘 다 SEMI 표준부다.
2. 모서리를 투영해 샘플하고, 각 점에서 **법선 방향으로 원본 이미지의 방향미분이 극대**인 곳을 찾는다
   (포물선 보간으로 서브픽셀).
3. 잔차 = (투영점 − 관측 edge)·법선 → 6-DoF **Huber 강건 최소제곱**, 재투영하며 8회 반복.

★ **GT 를 안 쓴다**(입력 = `left.png` + `cam.json` + 초기 pose). ★ **표준부만** 쓴다(`top_flange.ply`).
★ **research-only 코드 의존 없음**(numpy/opencv/scipy/trimesh) → 상업 경로가 안 깨진다.
★ 40프레임 **1.3초** (FP 는 29초).

### ⚠️ 두 번의 실패에서 배운 설계 조건 — **GT 에서 출발시켜 편향을 쟀다**

정합기가 옳다면 **GT 를 초기값으로 주면 안 움직여야 한다.** 그 진단이 두 버그를 잡았다:

| 구성 | GT 에서 출발했을 때 이동 | 원인 |
|---|---|---|
| 전역 최대 gradient | R **1.105°** / t **1.354mm** | **그림자 경계**가 물체 경계보다 강해 거기로 끌렸다 |
| + 극성 요구 · **가장 가까운 국소최대** | R 0.422° / t 1.004mm | 남은 편향은 대부분 **tZ −0.81mm** |
| + `--fix-z` (Z 는 depth 에서) | R 0.416° / t **0.245mm** | 평면 테두리는 Z 를 약하게 구속한다 |

극성도 **프레임마다 자동 판정**한다(`--polarity auto`, 기본). 실측: 밖−안 밝기차 중앙 **+67** 인데
**`frame_0021` 만 −87 로 역전**돼 있다(램프 정면, 검정 flange 가 배경보다 밝다) — 40프레임 중 1건.
→ 근거 이미지 `runs/dr2_near/polarity_evidence.png`.

> ⚠️ **최초 서술은 틀렸다.** 나는 *"frame_0023 이 밝아서 고정 극성이 실패했다"* 고 적었는데,
> `frame_0023` 은 역전이 아니다(밖−안 **+43**). 프레임별로 다시 재보면:
>
> | | KPI | R중앙 | t중앙 | 최악 프레임 |
> |---|---|---|---|---|
> | 고정 `bright_out` | 39/40 | 0.216 | 0.357 | `0010` **3.05°** · `0023` 2.67° |
> | **`auto`** | **40/40** | 0.216 | 0.357 | `0021` **2.29°** · `0018` 2.20° |
>
> **중앙값은 완전히 같고 바뀌는 것은 "어느 프레임이 실패하느냐" 뿐이다.**
> 게다가 역전 프레임 `0021` 에서 고정 극성이 **좋아 보였던 이유는 정합을 안 했기 때문**이다 —
> 유효 대응점을 못 찾아 초기값(0.84°)에서 0.89° 로 사실상 무동작이었다. `auto` 로 제대로 정합하면
> **2.29° 로 오히려 나빠진다.** 즉 `0021` 은 극성 문제가 아니라 **정합 자체가 어려운 프레임**이다.
> 횡단 정리 #49.

## ★★★ 2. 깨끗한 depth, 근접 — **단일 시점 최선을 갱신했다**

`dr2_near` 40프레임, 초기값 = `dr2_near_flonly`(FP 근접 flange refined):

| 구성 | R중앙 | R최대 | t중앙 | t최대 | KPI | 뒤집힘 |
|---|---|---|---|---|---|---|
| 입력 (FP refined) | 0.618 | 1.51 | 0.801 | 1.95 | 40/40 | 0 |
| **테두리 정합 + `--fix-z`** | **0.216** | 2.29 | **0.357** | **1.92** | **40/40** | 0 |
| 테두리 정합 (Z 도 자유) | 0.164 | 5.41 | 0.504 | 5.87 | 37/40 | 0 |

**R 2.9배 · t 2.2배 개선.** 참고로 이 프로젝트의 종전 최선은 **G9+G10 5시점 융합 R 0.24° / t 0.39mm**
였다 — **단일 시점이 그것을 넘었다.**
→ 깨끗한 depth 에서는 **Z 를 묶는 쪽(`--fix-z`)이 낫다**(꼬리가 5.87 → 1.92mm).

## ★★★★★ 3. 오염 depth — **거의 면역이다**

같은 정합을 오염 depth 로 낸 FP pose 위에 올렸다(`pose_P2_corr60_*` 가 초기값):

| 실제 평균 \|ΔZ\| | 입력 FP (KPI · R중앙 · t중앙) | **테두리 정합 (Z 자유)** |
|---|---|---|
| 0 (clean) | 40/40 · 0.618 · 0.801 | 37/40 · **0.164** · 0.504 |
| 3.25mm | 38/40 · 1.294 · 1.480 | 37/40 · **0.163** · **0.461** |
| 5.41mm | 32/40 · 1.836 · 2.204 | **37/40** · **0.164** · **0.476** |
| **10.81mm** | 13/40 · 2.625 · 5.731 | **32/40** · **0.201** · **0.497** |
| 18.35mm | 0/40 · 12.40 · 31.51 | **15/40** · 4.485 · 6.357 |

> **중앙값이 오염과 거의 무관하다** — 10.81mm 오염에서도 R 0.201° / t 0.497mm 로
> **clean 과 같다.** 이미지만 보기 때문이다.

남은 실패는 **초기값이 이미 뒤집힌 프레임**이다(10.81mm 에서 4건, 18.35mm 에서 15건).
실루엣 정합은 국소 수렴이라 90° 오추정을 못 고친다 — 뒤집힘 수와 KPI 미달 수가 정확히 대응한다.

★ **오염 하에서는 `--fix-z` 를 쓰면 안 된다**(10.81mm 에서 18/40 vs 자유 32/40). Z 를 depth 에서
가져오면 오염을 그대로 상속한다. → **깨끗하면 묶고, 오염되면 푼다.**

### ★ 부수 소득 — **GT 없이 depth 품질을 재는 지표**

`|Z_contour − Z_depth|` 는 **GT 없이** 계산되고, 위 표에서 보듯 오염과 함께 커진다.
`PIPELINE_CATALOG §7.5` 의 GT-free 지표 목록에 추가할 후보다. **미검증**(상관계수를 아직 안 쟀다).

## ⚠️ 4. 원거리에서는 **오히려 나빠진다**

`dr2_far`(0.8~1.2m)에서 같은 것을 하면:

| 정합 메쉬 | R중앙 | t중앙 | KPI |
|---|---|---|---|
| 입력 (FP `full` refined) | 0.637 | 1.102 | 40/40 |
| `top_flange.ply` 테두리 | 1.230 | 1.124 | **32/40** |
| `full.ply` 실루엣 | 1.666 | 2.248 | **32/40** |

물체가 작아 edge 가 약하고(flange 181px), `full` 실루엣은 배경·그림자 잡음이 많다.
→ **테두리 정합은 근접 전용이다.** 이는 근접 2단계 구조를 다시 한 번 정당화한다.

> 🔴 **정정 (2026-08-20, §35-2m-6).** 이 결론은 **몸체 외관에 딸린 조건부**다. 50cm 에서
> `black` 은 KPI 20→11/20 으로 무너지지만 **`orange` 는 R ×1.5 · `clear` 는 ×2.0 개선**된다.
> 여기서 «원거리 악화» 로 본 것은 몸체 randomize 조건이었다. **거리가 아니라 «외곽에 밝기 경계가
> 있는가»(§35-2i)가 축**이고, 켤지 말지는 **정합 이동량 t 중앙 ≥10mm** 로 GT 없이 판정한다.

## ★★★ 5. CAD-실물 불일치 하 — **테두리만 쓰면 중간부 불일치에 거의 면역, 그러나 테두리가 틀리면 못 버틴다**

정합기 **고유의 편향**만 보려면 **GT 를 초기값으로** 줘야 한다(#48) — FP 초기값을 쓰면
`flange_all` δ=5 에서 FP 자체가 90° 로 붕괴해(3.3/40, 뒤집힘 24) 정합기 얘기를 못 한다.
`--region flange_all` 을 추가해 **테두리·중심 홀까지 전부** 어긋나게 한 교란도 만들었다. 시드 3개:

| CAD 상태 | 기본(전체 실루엣) R중앙 / t중앙 / KPI | **`--rim-only-mm 3`** |
|---|---|---|
| **참 CAD**(하한) | 0.180 / 0.126 / 40/40 | **0.146 / 0.114 / 40/40** |
| 테두리 규격 준수, **중간부 δ=10** (`rb3`) | 1.598 / 0.574 / 28.3 | **0.247 / 0.144 / 38.0** |
| flange **전체** δ=1 (`fa`) | 2.599 / 0.960 / 22.3 | 1.906 / 0.863 / 28.3 |
| flange **전체** δ=2 | 4.585 / 1.777 / 13.3 | 3.685 / 1.678 / 18.0 |
| flange **전체** δ=5 | 7.370 / 2.274 / 4.3 | — |
| flange **전체** δ=10 | 8.008 / 2.777 / 4.7 | — |

- ⚠️ **테두리를 고정해도 기본 설정은 면역이 아니다** — 실루엣에 **중심 홀 테두리와 중간부 융기**가
  섞여 들어오기 때문이다(δ=10 에서 R 1.598°).
- ★ **`--rim-only-mm 3`**(샘플을 XY 외곽선 3mm 이내로 제한)을 켜면 **R 0.247° / t 0.144mm** 로
  거의 면역이 된다. **깨끗한 경우에는 공짜다** — 참 CAD·FP 초기값 실사용에서 켜나 끄나
  R 0.218 vs 0.216 · t 0.357 · **40/40 동일**. → **기본으로 켜는 것이 맞다.**
- ❌ **테두리 자체가 어긋나면 못 버틴다**: δ=1mm 에 R 1.9°, **δ=2mm 에 3.7°(KPI 미달)**.

> **배포 조건이 하나로 좁혀진다 — 테두리 외곽 공차가 대략 ≲1mm 여야 한다.**
> 이 값은 SEMI 규격 문서(또는 실물 측정)에서 와야 하며, **아직 확인하지 않았다.**
> §20-1 이 잰 두 CAD 의 flange 중앙 4.87mm 는 *"이상하다"* 고 한 CAD 라 **상한**으로 읽어야 한다.

## 5b. 이것이 바꾸는 것

| | 이전 | **지금** |
|---|---|---|
| 단일 시점 최선 | G1 R 0.505 / t 0.666 | **R 0.216 / t 0.357** (40/40) |
| 전체 최선 | G9+G10 5시점 R 0.24 / t 0.39 | **단일 시점이 동등 이상** |
| 상관 depth 오차 대응 | *"≥10mm 면 원거리 coarse 만"* | **근접 테두리 정합이 R 을 0.2° 로 지킨다** — 남는 문제는 **초기 뒤집힘**뿐 |
| 160×160 병목 | 우회 불가로 봄 | **FP 밖에서 우회했다** |

⚠️ **한계** — (a) **초기값 필수**, 90° 뒤집힘은 못 고친다(그래서 원거리 `full` coarse 안전망은 여전히 필요하다).
(b) n=40. (c) **sim 렌더의 edge 는 실물보다 깨끗하다** — 모션블러·노출·질감이 있는 실사진에서 다시 재야 한다.
(d) CAD-실물 불일치 하에서는 **미측정** — 테두리는 표준부지만 §21 처럼 다시 재야 한다.

## 재현

```bash
envs/cad/bin/python -m spatial_vision.stages.refine_contour \
    --in runs/dr2_near --pose-dir runs/dr2_near_flonly --pose-name pose_refined.json \
    --obj assets/obj/foup_300_semi --mesh top_flange.ply --out runs/ctr_near_fz --fix-z
envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/dr2_near \
    --obj assets/obj/foup_300_semi --pred runs/ctr_near_fz     # coarse=입력, refined=정합 결과
# ⚠️ 정합기 검증은 **GT 를 초기값으로** 주고 "안 움직이는가" 로 한다 — 편향을 이 방법으로 두 번 잡았다
# 오염 depth 에서는 --fix-z 를 빼야 한다 (Z 를 depth 에서 상속하면 안 된다)
envs/cad/bin/python -m spatial_vision.viz.overlay_pose --capture runs/dr2_near \
    --pred runs/ctr_near_fz --obj assets/obj/foup_300_semi --frames 6 --out runs/ctr_near_fz/overlay_sheet.png
```

**산출물 경로**

| 경로 | 내용 |
|---|---|
| `runs/ctr_near_fz/` | **깨끗 depth 최선** (40/40 · R 0.216 · t 0.357) + `overlay_sheet.png` |
| `runs/ctr_near_free/` | Z 자유 변형 |
| `runs/ctr_near_rim3/` | `--rim-only-mm 3` 실사용 (깨끗 depth) |
| `runs/famis_{fp,ctr}_fa_d{5,10}_s*/` | flange 전체 불일치 + FP 초기값 (FP 가 먼저 무너지는 것을 보인 런) |
| `runs/mesh_pert/fa_d{1,2,5,10}_s*/` | **flange 전체 교란** 메쉬(테두리 포함) |
| `runs/ctr_corr{3,5,10,17}_{fz,free}/` | 오염 depth 하 (+`overlay_sheet.png` in `ctr_corr10_free`) |
| `runs/ctr_far/`, `runs/ctr_far_full/` | 원거리 (악화 확인) |
| `runs/*/meta_contour.json` | 프레임별 대응점 수·rms(px)·이동량 |
| **`runs/dr2_near/polarity_evidence.png`** | **극성 근거** — flange 안/배경 밝기 실측. `frame_0021` 만 역전 |

---

# ★★★ 24. SEMI E47.1 규격 대조 — **무엇이 공차이고 무엇이 자유인가** (2026-08-10, 원문 검토)

> 🛠 **측정 절이 아니다** — SEMI E47.1 **원문 대조**와 규격 대조 자산(`foup_300_semi_spec{,15}`) 생성 기록.

사용자가 `docs/semi/` 에 규격 원문(8p PDF)과 **Figure 12 Top Robotic Handling Flange** 캡처를 넣어줬다.
그동안 *"테두리와 중심 홀만 규격"* 은 사용자 구두 확인이었는데 **문서로 확정됐다.**

## 1. 도면 규약 — 굵은 선 = 공차가 있는 면

§6.7 원문: *"the heaviest lines are used for surfaces that **have tolerances**
(not surfaces that have only maximum or only minimum dimensions)"*.
Figure 12 에서 **굵은 선은 바깥 테두리 윤곽과 중심 홀**이고, 나머지는 ≤/≥ 봉투(envelope)다.

| 구분 | 치수 | 값 |
|---|---|---|
| **공차 있음** (굵은 선) | `x46` `y46` 외곽 반폭 | **71 ± 1 mm** |
| | `x45` `y45` 챔퍼 시작 | **65.3 ± 1 mm** |
| | `x41` `y41` 노치 위치 | **30 ± 1 mm** |
| | `x42` `x43` 노치 간격 | **50 ± 1 mm** |
| | `θ` 노치 각 (16×) | **45 ± 0.5°** |
| | **`d63` 중심 홀** | **ø35 ± 0.1 mm** ← 테두리보다 **10배 조임** |
| | `x69` | 7.6 ± 0.1 mm · `β` 45±1° · `γ` 52±1° |
| **봉투만** (제조사 자유) | `x44` `y44` ≤53 · `y68` ≤55 · `x47` `y47` ≥58 · `r63` ≤66 · `z48` ≥15 · `z49` ≤8 · `z50` ≥5 · `r59` ≤6 | — |

★ 그리고 §6.1: *"The **orientation notches** on the robotic handling flange are **different for each of the
four sides**."* → **노치는 규격이 정한 방향(yaw) 특징**이다. §22 에서 *"노치가 해상도 바닥에 있다"* 고 했던
그 구조가 규격상 **유일하게 방향을 주는 표준 특징**이라는 뜻이다.

## ★★ 2. 이것이 테두리 정합의 배포 조건을 확정한다

§23-5 에서 *"테두리 외곽 공차가 ≲1mm 여야 한다"* 를 미확인으로 남겼는데, **규격값이 정확히 ±1mm 다.**

| 규격 공차 | 우리 측정(§23-5, GT 초기화 · `--rim-only-mm 3`) |
|---|---|
| 테두리 ±1mm | δ=1mm 에서 **R 1.906° / t 0.863mm / KPI 28.3-40** |
| (부품 간 최악 2mm) | δ=2mm 에서 **R 3.685° / KPI 18/40 — KPI 미달** |

> 🔴 **공차 한계에서 아슬아슬하다.** 다만 **우리 δ 는 비관적**이다 — 교란은 윤곽을 **무작위로 휘게**
> 하는데, 공차 안의 실제 부품은 대체로 *올바른 형상의 균일한 크기 오차*에 가깝고 그건 t/스케일로
> 흡수된다. **"공차 안이면 안전하다" 도 "위험하다" 도 아직 말할 수 없다** —
> 필요한 것은 **실물 여러 대의 테두리 실측**(균일 오차인가 형상 왜곡인가)이다.

★ **중심 홀이 ø35 ±0.1 로 10배 조이다** → 병진(x/y/Z) 앵커로는 홀이 테두리보다 훨씬 낫다.
방향(yaw)은 홀이 완전한 원이라 0 이므로, **"병진은 홀 · 회전은 테두리"** 가 규격이 지시하는 구조다.
⚠️ 단 아래 §3 때문에 **지금 CAD 로는 홀을 쓰면 안 된다.**

## 🔴 3. 우리 CAD 가 규격과 어긋난다 — **챔퍼는 확정, 홀은 재측정함**

`docs/semi/our_cad_vs_semi.png`(상면 윤곽 + 규격 눈금) · `docs/semi/our_flange_section.png`(y=0 단면) ·
**`docs/semi/section_semi_vs_ours.png`(규격 단면도와 우리 단면을 같은 축척으로 나란히 — 정본)**.

| 항목 | SEMI | 우리 CAD | 판정 |
|---|---|---|---|
| 외곽 반폭 `x46`/`y46` | 71 ± 1 | **71.00** | ✅ |
| **챔퍼 시작** = `x47`/`y47` | **≥ 58** (봉투) | **58.00** (네 변 모두) | ✅ **준수** |
| `x45`/`y45` | 65.3 ± 1 (중심→노치 모서리, 사용자 판독) | 노치 파임 깊이 5.0mm → 변 위 노치 모서리는 \|좌표\|=66 | ⚠️ 65.3 vs 66 — **1σ 안(±1)이나 대응 확정 필요** |
| **노치 배치** | 0 + 30±1 + 50±1, 변마다 다름 | **동일** (아래 절) | ✅ |
| **중심 홀 `d63`** | **ø35 ± 0.1**, **상판 밑면(=상면에서 `z49` 아래) 기준** | 상판 밑면 `z=−5.0` 에서 **ø31.2** (상면 개구 ø41.0, ø35 는 `z=−3.0` 에서 지난다) | ❌ **3.8mm 작다** (공차 ±0.1 의 38배) |
| 원뿔 벽 각 (`γ` 후보) | γ = 52 ± 1° | 수평에서 **44.9°** (dr/dz = 1.002) | ⚠️ γ 의 기준면 미확인 |
| 상판 두께 (`z50` ≥5 후보) | ≥ 5 | 허브부 7.0 · **주 환상부 5.0** · 외곽 립 **2.0** | ⚠️ 외곽 립이 2mm — `z50` 이 어디를 가리키는지 확인 필요 |

> ⚠️ **`d63` 은 최상면이 아니라 상판 밑면 기준이다**(사용자 정정). 우리 CAD 의 홀은 z=0 에서 ø41 →
> **z=−3.0mm 에서 ø35** 를 지나 계속 좁아지고, 상판 밑면(z=−5.0)에서는 **ø31** 이다.
> 즉 *"어느 깊이에서 재느냐"* 를 규격대로 잡으면 **맞지 않는다.**

> 🔴 **정정(2026-08-10, 사용자 지적).** 나는 처음에 `x45=65.3±1` 을 **챔퍼 시작**으로 읽고
> *"우리 CAD 58 은 7.3mm 규격 위반"* 이라고 보고했다. **틀렸다.** 도면을 확대해 보면
> **`x47/y47 ≥58` 이 챔퍼 시작**(윗변이 코너 챔퍼와 만나는 점)이고, **`x45` 는 중심에서
> (코너 챔퍼 위의) **노치 모서리**까지의 거리다. → **우리 CAD 의 58.00 은 규격을 지킨다.**
> 이 절의 "챔퍼 위반" 주장은 **철회**한다. 횡단 정리 #50.

### ✅ 노치 — **규격과 일치한다** (내가 "코너 노치가 없다" 고 한 것도 오독이었다)

도면을 확대해 보면 `orientation notch`·`position notch` 는 **직선 변 위**의 V 홈이고
**코너 챔퍼는 노치 없는 민짜 45° 대각선**이다(θ=45±0.5° 16× 는 **노치의 각도**). 우리 CAD 도 같다.
변별 노치 위치를 재보니 (`docs/semi/our_cad_notches.png`, 파임 깊이 전부 5.0mm):

| 변 | 우리 CAD 노치 위치 | SEMI |
|---|---|---|
| −x (좌) | **0**, −50 | position notch @ 0, `y41`=30±1 … |
| +x (우) | **0**, −30, +50 | — |
| +y (상) | **0**, +30 | `x41`=30±1, `x42`=50±1 |
| −y (하) | **0** | `x43`=50±1 |

**모든 변에 0 위치 노치 + 30/50 조합이 변마다 다르다** → 규격의
*"orientation notches are different for each of the four sides"* 를 만족하고,
30·50 이라는 **값도 규격 그대로**다. → **yaw 신호는 규격대로 있다.** 횡단 정리 #50.

### ★ 실물 관측 — 최외곽 테두리가 **솟아 있고 라운드 처리**돼 있다 (사용자, 미반영)

실물 top flange 는 **최외곽 테두리가 상판(5mm)보다 약 2mm 더 높고**, 그 높이를 **1~2.5mm 폭**으로
유지하다가 **라운드**되며 `z49` 로 내려간다. **우리 CAD 에는 이 융기가 없다**(외곽부 상면이 z=0 으로 평평).
함의:
- **테두리 정합(§23)에 직접 영향** — 실루엣 바깥 경계가 *라운드된 융기의 능선*이 된다.
  라운드 면은 계단이 아니라 **밝기 기울기**를 만들므로 edge 위치가 조명에 따라 흔들린다.
  §23 에서 참 CAD 로도 남았던 **잔여 편향(GT 출발 R 0.416°/t 0.245mm)** 이 실물에서는 더 커질 소지가 있다.
- 원점 규약은 안전하다 — `dominant_top_plane` 은 **면적 최대** 평면을 고르므로 융기가 아니라 주 상면을
  계속 고른다(bbox 최댓값을 썼다면 융기를 집었을 것이다 — 교훈 #2 가 이미 막아둔 지점).

### ⚠️ *"최대 반경"* 은 규격에 없다 — 내가 유도한 값이었다

앞선 보고에서 *"최대 반경 96.46 vs 우리 91.68"* 이라고 적었는데, **SEMI 문서에 그런 치수는 없다.**
`x46=71` 과 `x45=65.3` 에서 모서리 꼭짓점을 `(71, 65.3)` 으로 **가정해 계산한 값**이다.
우리 쪽 91.68 도 `meta.json` 의 `rim_radius_mm`(정점 최대 반경)일 뿐이다.
→ **두 값 모두 규격 항목이 아니므로 이 줄은 근거로 쓰면 안 된다.** 챔퍼 불일치(65.3 vs 58)가
같은 사실을 **규격 항목으로** 말해 준다.

🔴 **부수 문제**: `prepare_obj.measure_standard_features` 가 결과를 `standard_features_semi_e47_1_1106`
키에 넣는데, 그 안의 `rim_radius_mm`·`rim_diameter_mm` 는 **SEMI 치수가 아니다**(외접 반경).
정작 규격이 정한 `x45`·`x41`·`x42`·`d63`(상판 밑면)·`θ` 는 **재지 않는다.**
→ 규격 준수 검사를 하려면 이 함수부터 고쳐야 한다.

## ★ 3b. 규격·실물에 맞춘 새 obj 를 만들었다 — `assets/obj/foup_300_semi_spec`

**원본 `foup_300_semi` 는 그대로 둔다**(사용자 지시). `spatial_vision.cad.build_semi_flange` 가
`top_flange` 만 고쳐 새 obj 를 만든다. body·wafers 는 원본 바이트 그대로다.

| 고친 것 | 원본 | **신규** | 근거 |
|---|---|---|---|
| 중심 홀 @상판 밑면 | ø31.00 | **ø34.92** (SEMI 35±0.1 안) | 규격 `d63` |
| 상면 개구 | ø41.00 | **ø45.04** (=35+2·z49, 45° 원뿔) | 위의 귀결 |
| 최외곽 테두리 | 평평 | **+2.0mm 융기, 1.75mm 유지 후 2.5mm 라운드** | **실물 관측**(사용자) — 규격 항목 아님 |
| `z49` 상판 두께 · 외곽 71 · 노치 · `β` | — | **불변**(원래 규격 준수) | — |

검증: `verify_obj` **M1 통과** — 두 메쉬 동일 좌표계, **주 상면 z=0 유지**(면적 15,407mm²),
keypoint 32개 전부 형상 위(이탈 0.0000mm). `docs/semi/rim_raise_before_after.png` 로 융기를 눈으로 볼 수 있다.

⚠️ **알려진 한계**
- 면 수가 늘었다: flange 3,634 → **100,233**, full 33,722 → **130,321**. 융기 라운드(2.5mm)와
  홀 벽을 표현하려면 1.2mm 세분화가 필요했다. nvdiffrast 한계(2.2M, 교훈 #43)보다는 한참 아래다.
- **watertight 가 아니다**(T-junction 5,151/152,925 모서리). 변위 띠만 세분화한 결과인데
  **변위가 0 인 지점에서 경계를 끊었으므로 기하학적 틈은 없다.** `trimesh.contains` 로 단면을
  뽑아 확인했다. boolean 연산이 필요한 후속 도구에서는 주의할 것.
- 상판 밑면 **아래**(평탄 바닥 `x69`=7.6±0.1, 2차 원뿔 `γ`=52±1°)는 **모델링하지 않았다** —
  위에서 내려다보면 안 보이고 원본에도 그 구조가 없다.
- 융기 파라미터(2.0 / 1.75 / 2.5mm)는 **실물 구두 관측**이지 측정치가 아니다. 실측하면 갱신할 것.

🔴 **이 obj 로는 캡처부터 다시 돌려야 한다**(교훈 #40). 필요한 것: `build_usd`(완료) →
`capture_sim` → `stereo_onnx` → **ISM 템플릿 재렌더 / SAM3 참조 재생성**(둘 다 obj 종속) → pose.
**옛 런(`dr2_*`)과 섞어 쓰면 안 된다.**

## 4. 무엇을 해야 하나

1. ~~규격 준수 CAD 확보~~ → ✅ **완료**: `assets/obj/foup_300_semi_spec` (§3b). 다음은 **캡처부터 재실행**.
2. **홀을 정합에 넣는다**(그 CAD 에서). ø35±0.1 은 우리가 가진 **가장 조인 특징**이고 병진을 강하게 잡는다.
3. **실물 테두리 실측** — 공차 ±1mm 안의 편차가 **균일 크기 오차인지 형상 왜곡인지**. 이 답이
   §23 의 δ=1mm 수치를 실제 위험으로 볼지 아닐지를 정한다.
4. **노치를 명시적으로 쓴다** — 규격이 네 변을 다르게 정의한 유일한 방향 특징인데, 지금은
   실루엣의 일부로만 들어간다(§22: 입력 해상도에서 2~3px).
5. **`prepare_obj` 의 표준부 측정을 규격 항목으로 바꾼다** — `x45`·`x41`·`x42`·`θ`·`d63`(상판 밑면 기준)을
   재고 공차 위반을 `verify_obj` 가 걸러야 한다. 지금은 규격이 아닌 값(외접 반경)을 규격인 것처럼 기록한다.

---

# ★★★ 25. 규격 자산 `spec15` 로 캡처부터 재실행 — **테두리 정합이 나빠진다** (2026-08-11)

> 📐 **측정 조건** — **자산 `foup_300_semi_spec15`(규격 홀 ø35 + 융기 없음)** · `fx 1200 @1280×720` · 근접 0.35~0.50m · **n=40** · 캡처부터 재실행.

§24 에서 만든 규격·실물 준수 자산(`foup_300_semi_spec15`: 중심 홀 ø35.04 + 최외곽 융기 2mm/라운드 2.5mm,
세분화 1.5mm)으로 **캡처부터 전 체인**을 다시 돌렸다. 자산이 바뀌면 ISM 템플릿·SAM3 참조도
obj 종속이라 함께 재생성했다(교훈 #40).

## 1. 앞단은 그대로다

| 단계 | `dr2_*`(구 자산) | **`s15_*`(spec15)** |
|---|---|---|
| 원거리 분할 ISM `full` | IoU 0.915 · 오선택 0 | **IoU 0.932 · 오선택 0** |
| 근접 분할 SAM3 `flange` | IoU 0.983 · 오선택 0 | **IoU 0.983 · 오선택 0** |
| 원거리 `full` pose refined | 40/40 | **40/40** (R 평균 0.711 / t 평균 1.198) |
| 근접 `flange` pose refined | 40/40 | **40/40** (R 평균 0.715 / t 평균 1.096) |

분할·FoundationPose 는 자산 교체에 **무감각**하다. 갈리는 것은 테두리 정합뿐이다.

## ⚠️ 1b. 먼저 — `eval_pose` 표는 **평균**이다

§23 의 최선 수치(R 0.216 / t 0.357)는 **중앙값**인데, 초판 보고에서 `spec15` 는 표 값(평균)을
그대로 인용해 나란히 놓았다. **다른 통계끼리 비교한 것이다.** 아래는 전부 같은 코드·같은 설정으로
다시 돌려 통계를 맞춘 값이다. (열화 자체는 실재했고 크기만 과장돼 있었다.)

## ★★ 2. 테두리 정합만 나빠진다 — 그리고 **꼬리**가 나빠진다

`refine_contour --fix-z`, 초기값 = 근접 `flange` FP 결과. n=40.

| refined | 구 자산 `foup_300_semi` | **`spec15`** |
|---|---|---|
| R 중앙 / 평균 / **최대** | 0.216 / 0.424 / **2.29** | 0.425 / 1.048 / **6.19** |
| t 중앙 / 평균 / 최대 | 0.357 / 0.483 / 1.92 | 0.595 / 0.711 / 2.64 |
| KPI | **40/40** | **36/40** |

### 2a. 오차는 거의 전부 **면외 tilt** 다

오차 회전 `E = R_gt^T R_pred` 의 축을 물체 법선 성분(면내 yaw)과 나머지(tilt)로 분해:

```
yaw 중앙 0.08°     tilt 중앙 0.39°
```

평평한 판은 **정면에 가까울수록 기울기가 윤곽을 거의 안 바꾼다** — 구조적으로 약한 자유도다.
시선 경사각(물체 법선과 시선의 각)으로 층화하면 그 구간이 정확히 취약하다:

| GT 초기화 | 경사 <20° (n=11) | 경사 ≥20° (n=29) |
|---|---|---|
| 구 자산 | R 중앙 0.336 / **최대 1.65** | 0.123 / 2.39 |
| **`spec15`** | R 중앙 0.571 / **최대 5.28** | 0.219 / 2.86 |

**GT 에서 출발시켜도 같다** → 초기화가 아니라 **정합 목표 자체**의 문제다(교훈 #48 의 방법).

### 2b. 원인은 "edge 편향" 이 아니다 — **샘플 구성**이 바뀌었다

§24-3b 에서 *"라운드 면이 밝기 기울기를 만들어 edge 위치를 민다"* 고 예측했는데 **틀렸다.**
GT pose 에서 잰 부호 있는 잔차의 계통 편향은 두 자산이 같다(|중앙| 0.046px vs 0.037px).

실제로 바뀐 것은 **실루엣의 개수**다. 융기 테두리는 외곽선 말고도 **능선을 따라 물체 안쪽에
고리**를 만든다. 프레임당 실루엣 샘플이 **121 → 9,087** 로 늘고, 그중

```
바깥 윤곽  1,852점 (유효 1,714)      안쪽 능선  7,235점 (유효 2,886)
```

즉 **유효 대응의 63%가 안쪽 능선에서 온다.** 검정 flange 위 검정 능선이라 대비가 약하다.
→ `docs/semi/contour_edge_compare.png` (구 자산은 계단 하나, `spec15` 는 램프 + 안쪽 고리)

## ★ 3. `--outer-only` — 바깥 윤곽만 쓰면 **중앙값은 좋아지고 꼬리는 나빠진다**

`refine_contour --outer-only` 를 추가했다(실루엣 **선분**으로 닫힌 고리를 만들고 이미지 바깥에서
flood fill → 바깥 영역에 맞닿은 획만 채택. 볼록성 가정 없음).

| `spec15` (n=40) | 전체 실루엣 | **outer-only** |
|---|---|---|
| GT초기화 R 중앙 / 최대 / KPI | 0.261 / 5.28 / 38 | **0.136** / 7.94 / 35 |
| FP초기화 R 중앙 / 최대 / KPI | 0.425 / 6.19 / 36 | 0.425 / **5.44** / 36 |

**편향-분산 맞바꿈이다.** 안쪽 능선 샘플은 중앙값을 나쁘게 하지만 꼬리를 잡아준다.
outer-only 중앙값 0.136° 는 **구 자산(0.180°)보다도 좋다** — 정보는 바깥 윤곽에 있고,
안쪽 고리는 **정칙화** 역할을 한다.

⚠️ 첫 구현은 **무효였다** — 샘플을 점으로 찍어 고리를 만드니 획에 틈이 생겨 flood 가 새고
9,087개가 전부 "바깥" 으로 통과했다. 두 런의 수치가 소수점까지 같은 것이 신호였다(교훈 #51).

## ★★★ 4. 융기 파라미터 스윕 — **가설이 셋 다 틀렸다**

*"융기의 라운드가 원인"* 을 검증하려고 라운드 폭만 바꾼 자산 3종과 **융기를 뺀 대조군**을 만들어
각각 40프레임씩 새로 캡처했다. ⚠️ **네 캡처의 카메라 pose 는 완전히 동일하다**(Δ=0.000° / 0.000mm) —
seed 가 같으면 자산이 바뀌어도 씬이 재현된다. 즉 아래 차이는 **순수하게 자산**이다.

| 자산 | 샘플 | R 중앙 | R 평균 | **R 최대** | t 중앙 | KPI | 대응점 |
|---|---|---|---|---|---|---|---|
| 구 자산 (구 CAD·융기 없음·판 8mm·홀 ø31) | 전체 | 0.180 | 0.387 | **2.39** | 0.126 | **40/40** | 112 |
| **`flat`** (홀 ø35 + 판 5mm, 융기 **없음**) | 전체 | 0.316 | 1.067 | **10.69** | 0.061 | 37/40 | 4,048 |
| `flat` | outer | 0.150 | 0.447 | 3.99 | 0.103 | 39/40 | 451 |
| `r10` 라운드 1.0mm | 전체 | 0.257 | 0.756 | 4.89 | 0.078 | 38/40 | 5,659 |
| **`r25` 라운드 2.5mm (=`spec15`)** | 전체 | 0.261 | 0.708 | 5.28 | 0.077 | 38/40 | 5,580 |
| `r40` 라운드 4.0mm | 전체 | **0.178** | 0.573 | **3.23** | 0.064 | **39/40** | 5,467 |
| `r40` | outer | **0.128** | 0.776 | 7.01 | 0.079 | 37/40 | 1,762 |

전부 GT 초기화 · `--fix-z` (정합 목표만 본다).

**① 라운드 폭은 원인이 아니다** — 넓힐수록 **좋아진다**(R 최대 4.89 → 5.28 → **3.23**).
**② 융기 자체도 원인이 아니다** — 융기를 뺀 `flat` 이 **가장 나쁘다**(R 최대 10.69). 융기는 **도움**이 된다.
**③ 세분화 밀도도 아니다** — `--max-samples` 로 형상은 그대로 두고 대응점만 솎아내도 회복되지 않는다:

| `flat` 대응점 | 4,048(전체) | 627 | 209 | 63 |
|---|---|---|---|---|
| R 중앙 | 0.316 | 0.336 | 0.329 | **0.477** |
| R 최대 | 10.69 | 9.81 | 8.57 | 8.95 |

구 자산 수준(112점)까지 줄여도 **0.180 / 2.39 로 돌아가지 않는다.**

### 4b. 안쪽 고리는 무엇인가 — 잡음도 아니고 숨은 모서리도 아니다

두 가설을 측정으로 배제했다:
- **수치 잡음(면이 시선과 나란해 앞/뒤가 흔들림)?** ❌ 실루엣 edge 의 **98.6%가 `max|cos| > 0.2`** —
  한쪽 면은 확실히 카메라를 보고 다른 쪽은 확실히 등지고 있다. 진짜 기하다.
- **자기 가림(보이지 않는 뒷면 모서리)?** ❌ z-buffer 로 재니 가려진 샘플은 **9~13%** 뿐이다.

즉 안쪽 고리는 **진짜이고 보이는** 실루엣인데(융기가 없는 `flat` 에도 있다 — flange 밑단 단차)
**검정 flange 위 검정 단차라 이미지 신호가 없다.** `--outer-only` 가 `flat` 의 꼬리를
10.69 → 3.99 로 잡는 것이 이 해석과 맞는다.

### ★★ 4c. 원인은 **중심 홀 확대**다 (2×2)

`flat` 과 구 자산의 차이는 **① 중심 홀 ø31 → ø35(원뿔 재성형)** 과 **② 상판 두께 8.0 → 5.0mm** 뿐이다.
각각만 적용한 자산을 만들어 캡처했다(카메라 pose 동일).

| 자산 | R 중앙 | R 평균 | R 최대 | t 중앙 | KPI | 대응점 |
|---|---|---|---|---|---|---|
| 구 자산 (홀 ø31 · 판 8mm) | 0.180 | 0.387 | **2.39** | 0.126 | **40/40** | **112** |
| **홀만 ø35** (판 8mm) | **0.366** | 1.089 | 9.87 | 0.062 | 36/40 | **4,065** |
| 판만 5mm (홀 ø31) | 0.181 | 0.702 | 12.12 | 0.139 | 39/40 | 453 |
| 둘 다 (`flat`) | 0.316 | 1.067 | 10.69 | 0.061 | 37/40 | 4,048 |

**홀을 ø35 로 키우면 대응점이 112 → 4,065 로 폭증하고 그 86%가 홀 안(r<25mm)에 있다.**
판 두께만 바꾼 쪽은 중앙값이 구 자산과 같다(0.181 vs 0.180). 홀 확대는 원뿔을 가파르게 만들고
(`dr/dz` 0.451 → **0.755**) 그만큼 원뿔면이 시선과 나란해져 **어두운 깔때기 안에서 실루엣 모서리가
대량으로** 생긴다. ⚠️ 홀 경계 자체는 **완벽한 원**이다(방위 72구간 반경 진폭 0.000mm) — 우리 수정이
톱니를 만든 것이 아니다.

⚠️ 반대로 **t 는 홀이 있을 때 더 좋다**(0.126 → 0.062mm). 홀은 원이라 yaw 정보는 0 이지만
**병진은 잘 잡는다**(§M5 확장의 관찰과 일치).

### ★★★ 4d. 그래서 무엇을 빼야 하나 — **융기 유무가 처방을 뒤집는다**

`--no-hole-mm 30`(홀만 제외) 과 `--outer-only`(안쪽 실루엣 전부 제외)를 갈라서 쟀다.

| 자산 | 구성 | R 중앙 | R 최대 | t 중앙 | KPI | 대응점 |
|---|---|---|---|---|---|---|
| 구 자산 | — | 0.180 | **2.39** | 0.126 | **40/40** | 112 |
| **융기 없음**(홀 ø35·판 8mm) | 전체 | 0.366 | 9.87 | 0.062 | 36/40 | 4,065 |
| | 홀만 제외 | 0.167 | 5.02 | 0.107 | 39/40 | 447 |
| | **outer-only** | **0.125** | 4.13 | 0.085 | 39/40 | 445 |
| **융기 2.5mm**(`spec15`) | 전체 | 0.261 | 5.28 | 0.077 | 38/40 | 5,580 |
| | 홀만 제외 | 0.249 | 7.64 | 0.161 | 36/40 | 2,046 |
| | outer-only | 0.136 | 7.94 | 0.094 | 35/40 | 1,775 |
| **융기 4.0mm**(`r40`) | **전체** | 0.178 | **3.23** | 0.064 | **39/40** | 5,467 |
| | 홀만 제외 | 0.209 | 7.40 | 0.130 | 38/40 | 1,899 |
| | outer-only | **0.128** | 7.01 | 0.079 | 37/40 | 1,762 |

- **융기가 없으면 홀을 빼는 게 맞다.** 홀 제외 ≈ outer-only(447 vs 445) — 홀이 곧 안쪽 실루엣 전부다.
- **융기가 있으면 뒤집힌다.** 홀을 빼면 오히려 나빠진다(`r40` 최대 3.23 → 7.40). 홀 샘플이 **정칙화**로 작동한다.
- 전 구간에서 **outer-only 는 중앙값 최선, 전체는 꼬리 최선**이다 — 편향-분산 맞바꿈이 일관된다.
- ⚠️ **어느 구성도 꼬리에서 구 자산(2.39°)을 못 이긴다.** 남은 실패는 §25-2a 의 **정면 시점 tilt 축퇴**라
  **샘플 선택으로는 안 고쳐진다**. 기하(시점 배치) 문제다.

## 5. 무엇이 확정되고 무엇이 남았나

**확정**
1. 분할·FoundationPose 는 규격 자산 교체에 **무감각**하다(§25-1).
2. 테두리 정합만 나빠지고, 원인은 **중심 홀 확대**다 — 융기도, 라운드 폭도, 세분화 밀도도 아니다.
3. 남은 실패의 형태는 **면외 tilt**이고 **정면에 가까운 시점**에 몰린다.
4. ⚠️ **`--outer-only` 를 기본으로 봐야 한다** — 이 권고가 §26-2 에서 한 번 뒤집혔다가
   **§27-4 에서 다시 확정됐다**(n=40 이 잡음이었다). 여기에 **이동량 게이트**(§26-3)를 함께 건다.

**남은 것** (첫 항목은 §26 에서 닫혔다)
- ~~FP 초기화 하에서는 outer-only 이득이 안 보인다(0.425 → 0.425)~~ → **§26 에서 측정 완료.**
  진단은 맞았다(초기값 오차가 지배한다). 다만 처방은 outer-only 가 아니라 **게이트**였다.
- 정면 시점 tilt 축퇴는 **시점 배치**로 푸는 문제다(경사 ≥20° 를 요구할 수 있는지).
  게이트는 이 실패를 **회피**할 뿐 고치지 않는다(§26-6).
- 융기 실측값(2mm/1.75mm/2.5mm)은 **사용자 육안 관측**이다 — 실물 스캔으로 확정해야 한다.

## 재현 (§25)

```bash
OBJ=assets/obj/foup_300_semi_spec15
APP=... CLUT=...        # § 현행 최선 의 것을 그대로 쓴다

# (1) 규격 자산 전 체인 — 캡처부터
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/s15_near --frames 40 --seed 400 --fx 1200 --distance-m 0.35 0.50 $APP $CLUT
#   ⚠️ seed 가 같으면 **자산이 달라도 카메라 pose 가 동일**하다 → 자산 A/B 가 통제된다

# (2) 스윕 자산 (원본 불변)
envs/cad/bin/python -m spatial_vision.cad.build_semi_flange --obj assets/obj/foup_300_semi \
    --out assets/obj/foup_300_semi_s15_r40  --rim-plate-mm 5 --subdivide-mm 1.5 --rim-round-mm 4.0
envs/cad/bin/python -m spatial_vision.cad.build_semi_flange --obj assets/obj/foup_300_semi \
    --out assets/obj/foup_300_semi_s15_flat --rim-plate-mm 5 --subdivide-mm 1.5 --no-rim
envs/cad/bin/python -m spatial_vision.cad.build_semi_flange --obj assets/obj/foup_300_semi \
    --out assets/obj/foup_300_semi_s15_holeonly  --subdivide-mm 1.5 --no-rim              # 홀만
envs/cad/bin/python -m spatial_vision.cad.build_semi_flange --obj assets/obj/foup_300_semi \
    --out assets/obj/foup_300_semi_s15_plateonly --subdivide-mm 1.5 --no-rim --no-hole --rim-plate-mm 5
envs/cad/bin/python -m spatial_vision.cad.build_usd   --obj assets/obj/foup_300_semi_s15_<tag>
envs/cad/bin/python -m spatial_vision.cad.verify_semi --obj assets/obj/foup_300_semi_s15_<tag>

# (3) 정합 목표만 보는 진단 — **GT 초기화** (stereo·분할·FP 불필요, 40프레임 2초)
envs/pose/bin/python -m spatial_vision.stages.refine_contour --in runs/s15_near --pose-dir runs/s15_near \
    --pose-name pose_gt.json --obj $OBJ --fix-z [--outer-only | --no-hole-mm 30 | --max-samples N] \
    --out runs/s15_near_gt
envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/s15_near --obj $OBJ --pred runs/s15_near_gt

# (4) 눈으로 — 대응점·잔차
envs/pose/bin/python -m spatial_vision.stages.refine_contour ... --debug   # frame_*/contour_debug.png
envs/cad/bin/python -m spatial_vision.viz.overlay_pose --capture runs/s15_near --pred runs/s15_near_ctr_all \
    --obj $OBJ --worst 6 --out runs/s15_near_ctr_all/overlay_worst.png     # --worst 는 지표에서 꼬리를 고른다
```

⚠️ `eval_pose` 표의 R/t 는 **평균**이다. 중앙값은 `metrics_pose.json` 의 `frames` 에서 직접 낸다.

---

# ★★★★★ 26. 테두리 정합의 **초기값 의존**과 **이동량 게이트** — 새로운 최선 (2026-08-11)

> 📐 **측정 조건** — `spec15` · `fx 1200 @1280×720` · 근접 0.35~0.50m · **n=40** · clean + 상관 10mm 오염.

§25-5 가 남긴 질문 — *"`--outer-only` 이득이 FP 초기화에서 안 보인다(0.425 → 0.425).
초기값 오차가 지배하니 G9/G10 융합 초기값과 결합해 다시 재야 한다"* — 을 닫는다.
**닫혔고, 답은 `--outer-only` 가 아니라 게이트였다.**

G 계열 초기값을 파일로 낼 수 있게 `spatial_vision.eval.fuse_pose` 를 만들었다(§11·§15·§16 의
계산이 그동안 세션 스크래치패드에만 있었다). 모든 런은 `spec15` · 근접 0.35~0.5m ·
`top_flange.ply` · `--fix-z` · 40프레임이고, **아래 R/t 는 전부 중앙값**이다(평균·최댓값은 별도 열).

## ★ 1. 초기값 사다리 — 원거리 5시점 융합이 회전을 절반으로 줄인다

정합에 넣기 **전**의 초기값 품질(clean depth):

| 초기값 | R중앙 | R평균 | R최대 | t중앙 | t평균 | KPI |
|---|---|---|---|---|---|---|
| **G0** 원거리 `full` 이송 | 0.711 | 0.858 | 2.454 | 1.198 | 1.369 | 40/40 |
| **G1** 근접 flange FP | 0.715 | 0.832 | 2.268 | 1.096 | 1.164 | 40/40 |
| **G9** 게이트 | 0.711 | 0.858 | 2.454 | 1.096 | 1.166 | 40/40 |
| **원거리 융합 n=5** | **0.373** | 0.418 | **0.904** | 0.689 | 0.742 | 40/40 |
| **G9+G10** | 0.373 | 0.418 | 0.904 | 0.819 | 0.833 | 40/40 |

§16 의 구조가 이 자산에서도 그대로 재현된다 — **융합이 회전을 1.9배 줄인다.**
⚠️ 다만 **§16 과 달리 근접 t 를 채택해도 이득이 없다**(0.819 vs 융합만 0.689). `dr2` 에서는
근접 flange t 가 원거리보다 2.6배 정확했는데(0.65 vs 1.69) `spec15` 에서는 1.096 vs 1.198 로
거의 같다. 근접 재추정의 가치는 **자산·거리 조합마다 다시 재야 한다.**

## ★★ 2. `--outer-only` — 이득은 되살아나지만 **꼬리 손해는 초기값과 무관**하다

정합 후(게이트 없음). 전체 실루엣 vs `--outer-only`:

| 초기값 | 전체 R중앙 | 전체 R최대 | 전체 KPI | outer R중앙 | outer R최대 | outer KPI |
|---|---|---|---|---|---|---|
| G0 | 0.466 | 5.406 | 37/40 | 0.515 | 8.630 | 34/40 |
| G1 (FP 근접) | 0.425 | 6.194 | 36/40 | 0.425 | 5.436 | 36/40 |
| G9 | 0.362 | 6.196 | 37/40 | 0.512 | 8.343 | 33/40 |
| **원거리 융합 n=5** | 0.351 | 5.299 | 38/40 | **0.265** | **8.414** | 36/40 |
| G9+G10 | 0.353 | 5.073 | 38/40 | 0.322 | 8.103 | 35/40 |
| (상한) GT | 0.261 | 5.281 | 38/40 | **0.136** | **7.944** | 35/40 |

- ✅ **가설은 맞았다** — 초기값이 좋아질수록 `--outer-only` 의 중앙값 이득이 살아난다
  (G0 −11% → 융합 +25% → GT +48%). 초기값 오차가 지배한다는 §25-5 의 진단이 확인됐다.
- ~~❌ 그래도 채택하지 않는다 — 꼬리 손해가 초기값과 무관하게 일정하다(R 최대 5.1~6.2 → 7.9~8.6,
  KPI 항상 −2~3). 기본값 off 확정.~~
  🔴 **철회한다 (§27-4).** 이 표는 **n=40** 이고 그 꼬리는 **표본 잡음**이었다 — **n=120 에서
  중앙값·평균·최댓값·KPI 가 전부 outer-only 쪽이 낫다**(21.04° → 6.23°, 110 → 115/120).
  게다가 **flange 내부 제조사 편차에 구조적으로 면역**이다(§27-4a). **채택 권고로 바뀐다.**

## ★★★★★ 3. 진짜 발견 — **이동량 게이트**. 남은 실패는 전부 "많이 움직인" 프레임이다

정합이 **초기값에 없던 실패를 만든다**(융합 초기 40/40 → 정합 후 38/40). 그런데 그 프레임들은
초기값에서 **크게 회전한다**:

| 융합 초기값 | 초기값 R오차 → 정합 후 | 초기값 대비 이동 |
|---|---|---|
| frame_0000 | 0.30° → **5.30°** | **5.06°** / 1.45mm |
| frame_0023 | 0.67° → **3.11°** | **3.26°** / 0.99mm |
| 나머지 38프레임 (전부 성공) | — | 중앙 **0.59°**, 최대 **3.35°** |

→ *"초기값 대비 회전 이동량이 τ 를 넘으면 정합 결과를 버리고 초기값을 그대로 낸다."*
**비교 대상이 GT 가 아니라 초기값이라 실환경에 그대로 간다.** `refine_contour --gate-deg` 로 구현했고
버려진 결과는 `pose_contour_raw.json` 에 남는다(τ 를 나중에 다시 잡을 수 있게).

### ★★ 3a. 잔차로는 못 잡는다 — 이동량으로만 잡힌다

| | rms (px) | 대응점 | 이동 |
|---|---|---|---|
| 실패 2프레임 | 1.51 (1.14~1.88) | 5,371 | 1.22mm |
| 성공 38프레임 | 1.37 (**0.64~2.81**) | 5,576 | 0.64mm |

**실패의 rms 가 성공의 범위 안에 완전히 들어간다.** 목적함수가 그 방향으로 거의 평평해서
(면외 tilt 축퇴, §25-2a) 5° 틀린 pose 도 관측 edge 에 잘 맞는다 — `docs/semi/gate_frame0000_debug.png`
에서 노랑(정합)이 초록(GT)에서 벌어져 있는데 `d median +0.06px`, `rms 1.14` 다.
**적합도로는 원리적으로 판별할 수 없고, 사전 정보(초기값)로만 판별된다.**

### ★★ 3b. τ 스윕 — 1.0~3.0° 어디서든 40/40

원거리 융합 초기값, clean:

| τ | 후퇴 | R중앙 | R평균 | R최대 | t중앙 | t평균 | KPI |
|---|---|---|---|---|---|---|---|
| 0.5° | 23 | 0.363 | 0.393 | 0.904 | 0.525 | 0.600 | 40/40 |
| **1.5°** | 6 | **0.253** | 0.374 | 1.171 | **0.367** | 0.455 | **40/40** |
| 3.0° | 3 | 0.332 | 0.516 | 2.704 | 0.348 | 0.455 | 40/40 |
| ∞ (끄기) | 0 | 0.351 | 0.766 | **5.299** | 0.316 | 0.384 | **38/40** |

τ 가 너무 작으면(0.5°) 좋은 정합까지 버려 초기값으로 되돌아간다. **1.0~3.0 이 평평한 고원**이다.
⚠️ **τ 는 GT 로 골랐다.** 다만 **GT 없이 같은 눈금을 얻는 방법이 있다** — 융합에 쓴 5시점 추정의
**서로 간 회전 쌍거리**가 중앙 **1.164°**(최대의 중앙 2.09°)로 τ 와 같은 크기다.
*"τ ≈ 융합 산포"* 는 그럴듯한 GT-free 규칙이지만 **사후 관찰**이라 별도 검증이 필요하다.

### ★★★ 3c. 게이트를 걸면 전 구성이 40/40 으로 회복된다 — **새 최선**

τ=1.5°:

| 구성 | 후퇴 | R중앙 | R평균 | R최대 | t중앙 | t평균 | KPI |
|---|---|---|---|---|---|---|---|
| **★ 원거리 융합 n=5 + 정합 + 게이트** | 6 | **0.253** | 0.374 | 1.171 | **0.367** | 0.455 | **40/40** |
| 　+ `--outer-only` | 8 | 0.253 | **0.275** | **1.151** | 0.447 | 0.506 | 40/40 |
| G9+G10 + 정합 + 게이트 | 6 | 0.264 | 0.374 | 1.009 | 0.665 | 0.644 | 40/40 |
| G9 + 정합 + 게이트 | 12 | 0.462 | 0.686 | 2.454 | 0.698 | 0.902 | 40/40 |
| **단일 시점** G1(FP 근접) + 정합 + 게이트 | 7 | 0.425 | 0.676 | 2.541 | 0.675 | 0.822 | 40/40 |
| (상한) GT + 정합 + 게이트 | 6 | 0.133 | 0.272 | 1.066 | 0.046 | 0.091 | 40/40 |

- **다중 시점 최선 = R 0.253° / t 0.367mm / 40/40.** 초기값(0.373 / 0.689)보다 **R 1.5배 · t 1.9배**
  좋아지면서 KPI 를 잃지 않는다.
- **단일 시점 최선 = R 0.425° / t 0.675mm / 40/40** — 초기값(0.715 / 1.096) 대비 R 1.7배 · t 1.6배.
  이 경로는 **hand-eye 도 GT 도 전혀 안 쓴다**(FP 근접 flange + 정합 + 게이트).
- 게이트를 걸면 `--outer-only` 는 **R 평균·최댓값에서 근소 우세, t 에서 열세**로 무승부가 된다
  → 굳이 켤 이유가 없다(2절 결론 유지).

## ★★★★ 4. 오염 depth(상관 10mm)에서도 유효하다 — 정합이 t 를 1.7배 줄인다

⚠️ **오염 조건에서는 FP 의 `refine` 을 끄고 `pose_coarse.json` 을 쓴다**(§20·CLAUDE.md 의 처방).
`refined` 를 쓰면 원거리 KPI 가 26/40 → **2/40** 으로 무너진다. 초기값은 전부 coarse 로 만들었다.

| 구성 | R중앙 | R평균 | R최대 | t중앙 | t평균 | KPI |
|---|---|---|---|---|---|---|
| G0 원거리 `full` coarse 단일 | 0.891 | 1.089 | 2.939 | 3.732 | 4.400 | 26/40 |
| G1 근접 flange coarse 단일 | 2.822 | 7.887 | **179.6** | 5.512 | 6.154 | 11/40 |
| 원거리 융합 n=5 (초기값) | 0.532 | 0.534 | 1.188 | 2.368 | 2.430 | **40/40** |
| 　+ 정합 (게이트 없음) | 0.693 | 1.272 | 11.607 | **1.248** | 1.358 | 38/40 |
| **★ + 정합 + 게이트 1.5°** | 0.539 | 0.577 | 1.300 | 1.574 | 1.713 | **40/40** |
| 　+ 정합 + 게이트 3.0° | 0.671 | 0.887 | 2.868 | **1.405** | 1.439 | **40/40** |
| G0 + 정합 + 게이트 3.0° | 1.088 | 1.255 | 3.231 | 2.535 | 3.280 | 29/40 |
| G1 단일 + 정합 (게이트 없음) | 1.688 | 6.792 | **177.4** | 5.218 | 5.850 | 15/40 |

- ✅ **테두리 정합은 오염 depth 하에서도 t 를 2.37 → 1.41~1.57mm 로 줄인다**(1.5~1.7배).
  RGB 만 쓰므로 오염은 **초기값을 통해서만** 들어온다 — §23-3 의 "거의 면역" 이 융합 초기값과
  결합해도 유지된다.
- ✅ **τ=1.5° 가 clean 과 오염 양쪽에서 40/40** 이다. 게이트 상수를 조건마다 바꿀 필요가 없다.
- 🔴 **단일 시점 근접 경로는 오염에서 무너지고 정합이 못 살린다**(11/40 → 15/40, R 최대 177°).
  180° 뒤집힘은 국소 수렴으로 못 고친다 — **원거리 coarse 안전망은 계속 필요하다**(§23 재확인).
- ⚠️ **게이트가 오염에서는 더 많이 후퇴한다**(clean 6/40 → 오염 12/40). 초기값이 나쁠수록 정합이
  많이 움직여야 하는데 게이트는 그걸 막는다 — **이득의 상한을 게이트가 정한다.**

## 5. 정리 — 배포 권고 갱신

| 조건 | 구성 | 기대 (중앙값) |
|---|---|---|
| 다중 시점 + depth 양호 | **원거리 `full` n=5 융합 → 근접 테두리 정합 → 게이트 τ=1.5°** | R **0.253°** / t **0.367mm** · 40/40 |
| 다중 시점 + depth 오염(~10mm) | 같은 구성, FP 는 **coarse** | R 0.539° / t 1.574mm · 40/40 |
| 단일 시점만 | **FP 근접 flange → 정합 → 게이트** (hand-eye 불필요) | R 0.425° / t 0.675mm · 40/40 |
| 단일 시점 + depth 오염 | ❌ 불가 — 원거리 안전망 필수 | 15/40 |

## ⚠️ 6. 한계

- **융합·이송은 GT 를 hand-eye 대역으로 쓴다**(§16-5 와 같은 프록시). 단일 시점 경로만 프록시가 없다.
- **τ 선택에 GT 를 썼다.** 적용 자체는 GT-free 지만 상수는 실환경에서 다시 잡아야 한다(3b).
- **게이트는 실패를 고치지 않고 회피한다.** 후퇴한 프레임의 정확도는 초기값 그대로다.
  ~~근본 처방은 시점 배치다.~~ → **철회 (§27-1·3).** 경사 ≥20° 를 강제해도 꼬리가 안 없어지고,
  반대로 **축퇴 구간(경사 10~18°)조차 게이트만 걸면 40/40** 이다. 시점 배치로 풀 문제가 아니었다.
- ~~n=40 · 무결점 40/40 의 실패율 95% 상한은 7.5% 다.~~ → **실현됐다 (§27-2).** 같은 구성이
  **n=120 에서 110/120 (8.3% 실패)** 다. 이 절의 40/40 은 전부 *"≤7.5%"* 로 읽어야 한다.
- 오염은 `corr60 / 10mm` **한 점만** 쟀다. 17·25mm 는 안 쟀다.

## 재현 (§26)

```bash
OBJ=assets/obj/foup_300_semi_spec15

# (1) G 계열 초기값을 **파일로** 만든다 (기존 pose 산출물의 조합 — 새 FP 런 불필요)
envs/pose/bin/python -m spatial_vision.eval.fuse_pose --near runs/s15_near --far runs/s15_far \
    --near-pred runs/s15_near_flonly --far-pred runs/s15_far_pose \
    --mode farfuse --n-views 5 --out runs/s15_init_farfuse
#   --mode g0|g1|g9|farfuse|g9g10|jitter,  오염 조건이면 --pred-name pose_coarse.json

# (2) 정합 + 이동량 게이트
envs/pose/bin/python -m spatial_vision.stages.refine_contour --in runs/s15_near \
    --pose-dir runs/s15_init_farfuse --pose-name pose_init.json --obj $OBJ \
    --fix-z --gate-deg 1.5 --out runs/s15_ctrg_farfuse_all
envs/pose/bin/python -m spatial_vision.eval.eval_pose --gt runs/s15_near --obj $OBJ \
    --pred runs/s15_ctrg_farfuse_all

# (3) 오염 depth — ⚠️ 보정 마스크를 §11·§16 과 맞춰야 한다 (mask_flange.png). 그리고 **coarse** 를 쓴다
envs/stereo_onnx/bin/python -m spatial_vision.eval.perturb_depth --in runs/s15_far_onnx \
    --capture runs/s15_far --out runs/pert/s15_far_corr60_10 --mode corr --corr-px 60 \
    --target-mm 10 --calib-mask mask_flange.png
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/s15_far --out runs/s15_far_pose_c10 \
    --obj $OBJ --masks runs/s15_far_ism --depth stereo --depth-dir runs/pert/s15_far_corr60_10 \
    --flange-mask-from pose

# (4) 눈으로 — 게이트에 걸린 프레임
#   docs/semi/gate_frame0000_debug.png  (refine_contour --debug: 노랑=정합, 초록=GT)
#       → R 5.30° 틀렸는데 d median +0.06px · rms 1.14px 다. 3a 의 그림 근거.
#   docs/semi/gate_rejected_raw.png / gate_kept_init.png  (overlay_pose: **빨강=GT**, 초록=예측)
#       → frame_0000 은 R 5.30° 인데 두 윤곽이 거의 겹친다 — 정면 시점 tilt 축퇴의 실물.
```

⚠️ **두 시각화의 색 규약이 반대다** — `refine_contour --debug` 는 **초록=GT**,
`viz.overlay_pose` 는 **빨강=GT**. 둘 다 이미지에 범례를 찍으므로 **색을 말로 옮기지 말고
범례째로 인용**할 것(횡단 정리 #57).

---

# ★★★★★ 27. 표본 120 · 시점 통제 · CAD 불일치로 다시 재니 **결론 셋이 뒤집혔다** (2026-08-11)

> 📐 **측정 조건** — `spec15` · `fx 1200 @1280×720` · 원거리 0.8~1.2m / 근접 0.35~0.50m · **n=120** · 시선 경사 통제(`--elevation-deg`).

실물 스캔 없이 CAD 만으로 갈 수 있는 데까지 밀어붙인 결과다. 새 캡처 두 벌:

| 런 | 프레임 | 시선 경사 | 목적 |
|---|---|---|---|
| `obl20_near` | **120** | **20~50°** (elevation 40~70) | 시점 배치 가설 + 표본 확대 |
| `obl10_near` | 40 | 10~18° (elevation 72~80) | 축퇴 구간 단독 |

⚠️ **`시선 경사 = 90 − elevation` 이 정확히 성립한다**(실측 최대 차 **0.000°**, 상관 1.0000).
`--elevation-deg` 로 경사를 직접 통제할 수 있다 — 이걸로 이하가 전부 통제 실험이 된다.

## ❌ 1. 시점 배치 가설 — **기각.** 경사 ≥20° 를 강제해도 꼬리가 안 없어진다

§25-2a 는 실패가 **경사 <20°** 에 몰린다고 봤고, §25-5 는 *"시점 배치 문제"* 로 넘겼다. 직접 쟀다
(GT 초기화 진단, 게이트 없음):

| 캡처 | n | R중앙 | R평균 | R최대 | KPI |
|---|---|---|---|---|---|
| 기존 `s15_near` (경사 10~49) | 40 | 0.261 | 0.708 | 5.281 | 38/40 |
| **경사 20~50 으로 제한** | **120** | 0.246 | 1.060 | **21.038** | **110/120 (91.7%)** |
| 경사 10~18 만 | 40 | 0.296 | 1.677 | 9.925 | 30/40 |

- **경사를 20° 이상으로 강제해도 91.7% 다.** 기존 38/40(95%)과 통계적으로 구분되지 않는다
  (38/40 의 95% 신뢰구간은 83~99%).
- 경사가 **영향은 준다** — 10~18° 단독은 75% 로 뚜렷이 나쁘다. 하지만 **≥20° 로 자른다고 꼬리가
  사라지지는 않는다.** 축퇴는 경사 30~50° 에도 있다(74/79).

## 🔴 2. **"40/40" 은 표본 한계였다** — n=120 에서 진짜 실패율이 드러난다

문서 전반의 무결점 40/40 에 붙여 온 경고(*"실패율 95% 상한 7.5%"*)가 **그대로 실현됐다**:
게이트 없는 테두리 정합은 n=120 에서 **8.3% 실패**(10/120)다. 7.5% 상한과 일치한다.

> **n=40 의 무결점을 "무결점" 으로 읽으면 안 된다.** 이 프로젝트의 모든 40/40 은
> *"실패율 ≤7.5%"* 로 읽어야 한다. → 횡단 정리 #58.

## ✅ 3. 게이트는 n=120 에서도 무결점이고, **경사와 무관**하다

| 구성 (GT 초기, `--gate-deg 1.5`) | n | 후퇴 | R중앙 | R최대 | t중앙 | KPI |
|---|---|---|---|---|---|---|
| 경사 20~50 · 전체 실루엣 | 120 | 20 | 0.137 | 1.451 | 0.062 | **120/120** |
| 경사 20~50 · **`--outer-only`** | 120 | 19 | **0.108** | **1.400** | **0.055** | **120/120** |
| 경사 10~18 · 전체 실루엣 | 40 | 11 | 0.136 | 1.288 | 0.035 | **40/40** |

**축퇴 구간(경사 10~18°)조차 게이트만 걸면 무결점이다.** → **시점 배치로 풀 문제가 아니었고,
게이트로 이미 풀렸다.** §25-5·§26-6 의 *"근본 처방은 시점 배치"* 는 **철회**한다.

## ★★★★ 4. `--outer-only` — **기각을 철회한다. 채택 권고로 바꾼다** (사용자 지적, 2026-08-11)

§26-2 에서 *"중앙값만 좋아지고 꼬리를 판다"* 며 기각했다. **n=40 이 뒤집혀 있었다.**

| n=120, GT 초기 | R중앙 | R평균 | R최대 | **yaw중앙** | t중앙 | KPI |
|---|---|---|---|---|---|---|
| 전체 실루엣 (게이트X) | 0.246 | 1.060 | 21.038 | 0.081 | 0.128 | 110/120 |
| **`--outer-only`** (게이트X) | **0.189** | **0.708** | **6.231** | **0.029** | 0.132 | **115/120** |
| 전체 실루엣 + 게이트 | 0.137 | 0.259 | 1.451 | 0.046 | 0.062 | 120/120 |
| **`--outer-only` + 게이트** | **0.108** | 0.265 | **1.400** | **0.013** | **0.055** | 120/120 |

⚠️ **정정 주석 (2026-08-19)** — 이 표의 **`yaw중앙` 0.013~0.081° 는 회전각 계산의 잡음 바닥 근처**다.
당시 쓰던 `arccos((tr−1)/2)` 는 항등 근처에서 **자기 비교에도 p90 0.028°** 를 낸다(교훈 #85).
**R중앙(0.108~0.246°)과 KPI·최댓값 비교는 그대로 유효**하지만, **yaw 열의 «3.5배» 는 배수로 인용하지
말 것**. 재측정하려면 `contracts.rotation_angle_deg` 로 다시 내야 한다.
⚠️ 그리고 이 표는 **GT 초기값**이다 — 게이트가 걸린 행은 «GT 로의 후퇴» 라 교훈 #62 의 착시 구간이다.
**절대값이 아니라 «게이트X 행끼리»** 비교한다.

**중앙값·평균·최댓값·KPI 가 전부 낫다.** 특히 **면내 yaw 가 3.5배 정확하다**(0.046 → 0.013) —
방향 정보는 테두리에서 오는데(§flange 의 회전 구속) 안쪽 실루엣이 그걸 희석하고 있었다.
n=40 에서 *"꼬리를 판다"* 고 본 것은 표본 잡음이었다(횡단 정리 #12 의 재발, 이번엔 **내가** 밟았다).

### ★★★★★ 4a. 그리고 사용자 논지가 맞다 — **flange 내부 제조사 편차에 구조적으로 면역이다**

사용자 주장: *"최외곽은 규격화되어 있으니 최종 refinement 에서 정밀도를 높이는 데 쓸 수 있다."*
**sim 이 원리적으로 못 보던 축**이라(렌더와 CAD 가 같은 메쉬) CAD 만 틀리게 만들어 쟀다.
`perturb_mesh --region flange --rim-band-mm 3` — **규격 띠 3mm 정점을 `0.0000mm` 로 고정**하고
그 안쪽만 저주파로 흔들었다(게이트 없음, n=120):

| flange 내부 불일치 δ | 전체 R중앙 | 전체 KPI | **outer R중앙** | **outer KPI** |
|---|---|---|---|---|
| 0 (CAD 일치) | 0.246 | 110/120 | 0.189 | 115/120 |
| 1.05mm | 0.349 | 106/120 | 0.206 | 115/120 |
| 2.62mm | **0.410** | **103/120** | **0.174** | 113/120 |

**전체 실루엣은 δ 에 단조 열화(+67%), `--outer-only` 는 완전 무감각**(0.189 → 0.206 → 0.174,
변화가 잡음 수준). 게이트를 걸면 정확도는 양쪽 다 보호되지만 **후퇴율에 차이가 남는다** —
전체는 20 → 28 → **34**, outer 는 19 → 18 → **19**. 게이트가 *"오염됐다"* 를 세고 있는 것이다.

⚠️ δ=10 요청 조건은 **무효**다 — 내부가 고정 테두리 **밖으로 삐져나와** XY 윤곽 면적이 +18% 커졌다
(19,621 → 23,217mm²). 교란이 "내부만" 이 아니게 되므로 시험이 성립하지 않는다. δ2·δ5 만 쓴다.

### 🔴 4b. 면역의 **조건** — 규격 띠 자체가 어긋나면 둘 다 무너지고 outer 가 **더** 나쁘다

SEMI 는 외곽 반폭을 `x46 71±1` 로 잡는다 → **규격을 지킨 두 부품끼리도 최대 2mm 다를 수 있다.**
그 경우를 `--region flange_all` 로 모사했다(테두리까지 함께 흔든다):

| 규격 띠 실제 이동 | 전체 R중앙 / KPI | outer R중앙 / KPI |
|---|---|---|
| 0.78mm | 1.914 / 101 | 1.814 / 101 |
| 1.57mm | 2.203 / **90** | 2.554 / **74** |

**테두리가 1.6mm 어긋나면 outer-only 가 오히려 나쁘다** — 유일하게 보는 신호가 그 테두리라서다.
→ **`--outer-only` 의 이득은 "우리 CAD 의 최외곽 윤곽이 실물과 서브밀리미터로 맞을 때" 성립한다.**
**규격 공칭값(±1mm)만으로는 부족하다** — 근접 조건에서 1mm = 2.71px 이고 정합 잔차는 1.14px 다.
규격은 **상한을 주지 기하를 주지 않는다.** 실물 스캔이나 제조사 CAD 가 필요한 지점이 바로 여기다.

## ✅ 5. τ 를 GT 없이 정할 수 있다 — **융합 산포 규칙이 성립한다**

§26-3b 의 *"τ ≈ 융합 n시점의 회전 쌍거리 중앙값"* 을 검정했다(원거리 융합 초기값, n=40):

| 규칙 | clean τ / KPI | 오염 corr60_10 τ / KPI |
|---|---|---|
| 게이트 없음 | — / 38 | — / 38 |
| 고정 τ=1.5° (GT 로 고름) | 1.50 / **40** | 1.50 / **40** |
| **★ τ = 산포(전역 중앙)** | **1.16 / 40** | **1.45 / 40** |
| ★ τ = 산포(프레임별) | 1.16 / 40 | 1.45 / 40 |
| τ = 2×산포 | 2.33 / 40 | 2.90 / 40 |
| τ = 0.5×산포 | 0.58 / 40 | 0.73 / 40 |

산포 규칙이 **GT 로 고른 1.5° 와 0.05~0.35° 안에서 일치**하고, **0.5×~2× 어디로 잡아도 40/40** 이다.
게이트는 τ 에 둔감하고, **눈금은 융합이 스스로 제공한다.** → 실환경에서 τ 를 GT 없이 정할 수 있다.

## ★★★★★ 6. 전 체인 n=120 — **최종 배포 구성은 "규격부만"(테두리 + 중심 홀)이다**

`obl20_far`(120프레임, 0.8~1.2m, 같은 seed·경사대)를 추가로 찍어 캡처→스테레오→분할→FP→융합→
정합→게이트를 전부 다시 돌렸다. **문서 전체에서 처음으로 n=120 전 체인이다.**

### 6a. 전단(분할·FP)에서도 n=40 이 숨기던 것이 나온다

| 단계 | n=40 (`s15`) | **n=120 (`obl20`)** |
|---|---|---|
| ISM `full` IoU / 오선택 | 0.932 / **0** | 0.902 / **1** |
| SAM3 `flange` IoU / 오선택 | 0.983 / 0 | 0.982 / **0** |
| 원거리 `full` FP | 40/40 | **119/120** (R 최대 **139.7°**, t 1020mm) |
| 근접 `flange` FP | 40/40 | 120/120 |

**유일한 원거리 대실패는 분할 오선택이다** — `frame_0076` 에서 `select center` 가 배경을 집었다
(pred 634,362px vs GT 161,561px, precision **0.0006**). **횡단 정리 #15 가 경고한 바로 그 실패가
n=120 에서 처음 발현**했다. 발생률 1/120 ≈ 0.8%.
✅ **원거리 5시점 융합의 인라이어 합의가 이걸 흡수한다** — 융합 초기값의 R 최대는 **1.092°** 다.

### ★★★ 6b. 최종 표 (n=120, 원거리 융합 n=5 초기값, `--gate-deg 1.5`)

| 구성 | R중앙 | R평균 | R최대 | t중앙 | t평균 | KPI |
|---|---|---|---|---|---|---|
| 초기값(융합)만 | 0.428 | 0.444 | 1.092 | 0.761 | 0.773 | 120/120 |
| + 정합 (전체 실루엣) | 0.246 | 0.349 | **1.442** | 0.356 | 0.442 | 120/120 |
| + 정합 (`--outer-only`) | 0.224 | 0.372 | 1.712 | 0.419 | 0.493 | 120/120 |
| **★ + 정합 (규격부 = 테두리 + 홀)** | **0.192** | **0.315** | 1.559 | **0.351** | **0.441** | **120/120** |
| (게이트 없음, 전체) | 0.290 | 1.118 | 20.796 | 0.314 | 0.398 | **109/120** |
| (게이트 없음, outer) | 0.235 | 0.803 | 7.653 | 0.445 | 0.646 | **113/120** |
| 단일 시점 G1 + 정합 + 게이트 | 0.367 | 0.573 | 2.922 | 0.678 | 0.833 | 120/120 |

### ★★★★ 6c. **회전은 테두리가, 평행이동은 중심 홀이 준다** — 둘 다 규격부다

`--outer-only` 는 회전을 개선하면서 **평행이동을 악화**시킨다(t 0.356 → 0.419). 이유는 §21 이
이미 말했다 — **중심 홀은 완전한 원이라 yaw 정보가 0 이지만 x/y 를 강하게 구속한다.**

그런데 **중심 홀도 SEMI 규격부다**(`d63 ø35±0.1`). 빼야 할 것은 홀이 아니라 **비규격인 중간부**뿐이다.
그래서 `--keep-hole-mm` 를 추가했다 — *"`--outer-only` 를 쓰되 중심 반경 R 안은 남긴다."*
`--outer-only --keep-hole-mm 25` 가 **R 중앙·R 평균·t 중앙을 동시에 최선**으로 만든다(위 표).

> **"표준부만 쓴다"(§2.1b)의 정확한 구현은 `--outer-only` 가 아니라 "테두리 + 홀" 이다.**
> 규격이 잡는 **두 도형을 다 쓰고, 그 사이만 버린다.**

그리고 면역도 유지된다(GT 초기, 게이트 없음, flange 내부만 교란):

| 내부 불일치 δ | 규격부 R중앙 | 규격부 KPI |
|---|---|---|
| 0 | 0.166 | 110/120 |
| 1.05mm | 0.172 | 110/120 |
| 2.62mm | 0.151 | 110/120 |

(비교: 전체 실루엣은 같은 조건에서 0.246 → 0.410 으로 열화한다.)

### ⚠️ 6d. 한계

- `--keep-hole-mm 25` 와 `30` 이 **소수점까지 같다** — 홀 실루엣이 전부 r<25 안이라 R 을 키워도
  샘플이 안 늘어난다. 필터가 포화한 것이지 무효인 것은 아니다(전체 대비 대응점 수는 분명히 다르다).
- **far/near 캡처는 카메라가 짝지어져 있지 않다**(elevation 최대 차 27.9°). 기존 `s15`·`dr2` 쌍도
  마찬가지(33.6°)이며, G 계열은 **물체 프레임 오차**로 정의돼 있어 성립한다 — 다만 §16-5 가 밝힌
  *"물체 고정 + 카메라만 이동" 이 아닌 프록시* 라는 점은 그대로다.
- 120프레임 무결점의 실패율 95% 상한은 **2.5%** 다(40프레임의 7.5%에서 개선). 99% 확정에는 여전히 300 필요.

## ★★★★★ 7. **FP 의 `refine` 을 초기값으로 어떻게 쓰느냐가 정합 결과를 바꾼다** (n=120)

§26·§27-6 은 초기값을 만들 때 늘 `pose_refined.json` 을 썼다. **틀린 기본값이었다.**

| 산출 단계 | 원거리 `full` R / t | 근접 `flange` R / t |
|---|---|---|
| `pose_coarse.json` | **0.549** / 1.713 | **0.510 / 0.928** |
| `pose_refined.json` | 0.737 / **1.280** | 0.656 / 1.104 |

- **원거리는 고전적 맞바꿈**이다 — refine 이 회전을 악화시키고 평행이동을 개선한다(횡단 정리 #6).
- 🔴 **근접 `flange` 는 refine 이 R·t 를 둘 다 악화시킨다.** n=40(`s15`)에서도 같다
  (0.438/0.865 → 0.715/1.096). **근접 단계에서는 refine 을 끄는 것이 맞다.**

### ★★ 7a. 그래서 초기값을 바꾸면 정합 결과가 따라 좋아진다

| 구성 (n=120, 규격부 정합 + 게이트 1.5°) | R중앙 | R평균 | R최대 | t중앙 | KPI |
|---|---|---|---|---|---|
| **단일 시점** P5, 초기 = 근접 refined | 0.367 | 0.573 | 2.922 | 0.678 | 120/120 |
| **★단일 시점** P5c, 초기 = 근접 **coarse** | **0.245** | **0.425** | **2.123** | **0.642** | 120/120 |
| 융합 초기 = 원거리 refined (P7) | 0.192 | 0.315 | 1.559 | **0.351** | 120/120 |
| 융합 초기 = 원거리 coarse | 0.209 | 0.304 | 1.549 | 0.537 | 120/120 |
| **★★융합 초기 = 하이브리드**(R=coarse, t=refined) **P7h** | **0.184** | **0.283** | 1.683 | **0.325** | **120/120** |

- **단일 시점 경로가 R 1.5배 좋아진다**(0.367 → 0.245). 이 경로는 **hand-eye 도 다중 시점도 안 쓴다**
  → 프록시가 하나도 없는 구성인데 P7 에 R 이 근접한다.
- **하이브리드 초기값이 새 최선**이다: `fuse_pose --pred-name pose_coarse.json --pred-name-t pose_refined.json`.
  §10 이 이미 찾아 둔 *"회전은 coarse, 평행이동은 refine"* 패턴을 **융합 초기값에 적용**한 것이다.
  융합 자체도 그렇다 — coarse 융합 R **0.263** vs refined 융합 0.428, t 는 0.933 vs **0.761**.

> **정리: `refine` 은 켜냐 끄냐가 아니라 «어느 자유도를 어디서 받을 것인가» 다.**
> 회전은 coarse 에서, 평행이동은 refined 에서 받는다. 이 규칙이 원거리·근접·융합 **세 곳 모두**에서 성립한다.

⚠️ 이 표는 **clean depth** 다. 오염 조건에서는 refined 자체가 붕괴하므로(§26-4) coarse 만 쓴다 —
그러면 하이브리드는 자동으로 coarse 단독이 된다.

## 재현 (§27)

```bash
OBJ=assets/obj/foup_300_semi_spec15
APP=... CLUT=...        # § 현행 최선 의 것

# (1) 시선 경사를 통제한 캡처 — **경사 = 90 − elevation** (실측 차 0.000°)
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/obl20_near --frames 120 --seed 700 --fx 1200 --distance-m 0.35 0.50 \
    --elevation-deg 40 70 $APP $CLUT      # 원거리는 --out runs/obl20_far --distance-m 0.8 1.2

# (2) CAD 불일치 대리 측정 — **규격 띠 3mm 를 0.0000mm 로 고정**하고 안쪽만 교란
envs/cad/bin/python -m spatial_vision.cad.perturb_mesh --obj $OBJ --region flange \
    --rim-band-mm 3 --delta-mm 5 --seed 0 --out runs/mesh_pert/s15fl5
#   ⚠️ δ=10 은 무효다 — 내부가 고정 테두리 밖으로 나가 XY 윤곽 면적이 +18% 커진다. 항상 확인할 것:
#      outline_xy(perturbed).area 가 원본과 0.5% 안에 있어야 시험이 성립한다.
#   ⚠️ 규격 띠까지 흔들려면 --region flange_all (면역의 상한을 재는 대조군)

# (3) ★ 배포 구성 — 규격부(테두리 + 중심 홀)만 + 이동량 게이트
envs/pose/bin/python -m spatial_vision.eval.fuse_pose --near runs/obl20_near --far runs/obl20_far \
    --near-pred runs/obl20_near_flonly --far-pred runs/obl20_far_pose \
    --mode farfuse --n-views 5 --out runs/obl20_init_farfuse
envs/pose/bin/python -m spatial_vision.stages.refine_contour --in runs/obl20_near \
    --pose-dir runs/obl20_init_farfuse --pose-name pose_init.json --obj $OBJ \
    --fix-z --outer-only --keep-hole-mm 25 --gate-deg 1.5 --out runs/obl20_dep_spec25

# (4) 진단 — GT 초기화면 캡처만 있으면 된다(스테레오·분할·FP 불필요, 120프레임 5초)
envs/pose/bin/python -m spatial_vision.stages.refine_contour --in runs/obl20_near \
    --pose-dir runs/obl20_near --pose-name pose_gt.json --obj $OBJ --fix-z --out runs/obl20_ctr_gt
```

⚠️ **n=40 으로 꼬리를 비교하지 말 것** — 이 절의 결론 셋이 전부 거기서 뒤집혔다(횡단 정리 #58).

---

# ★★★★★ 28. 중심 홀은 **지름을 믿지 말고 중심만 쓴다** (사용자 제안, 2026-08-11)

> 📐 **측정 조건** — `spec15` + 홀 지름 변형 CAD(ø33~41) · `fx 1200 @1280×720` · **n=120**. ⚠️ **모델 CAD 만 바꾼 대리 측정**(렌더는 `spec15` 고정).

사용자 확정 사실: *"실물 FOUP 은 제조사마다 중심 홀 최상면에 융기가 있는 것과 없는 것이 있어서
영상에서 따는 홀 크기가 조금씩 달라진다."* → §27-6c 가 채택한 **홀 윤곽 정합은 그 편차를 그대로
먹는다.** 제안은 *"크기는 무시하고 홀의 중심점만 쓰자"* 였다. 구현하고 쟀다.

## 1. 구현 — 잔차에서 **중앙값만 뺀다**

`refine_contour --hole-center-mm R` : 중심에서 반경 R 안(=중심 홀) 샘플의 법선 잔차 `d` 에서
**중앙값을 뺀다.** 홀 실루엣의 법선은 전부 **방사 방향**이므로
- **지름 오차** → `d` 에 **상수** 성분 → 중앙값 제거로 **1차 상쇄**
- **중심 어긋남** → `cos(θ−φ)` (평균 0) → **남는다**
- **면외 tilt** → `cos 2θ` (평균 0) → **남는다**

타원 중심을 따로 추정할 필요가 없다. 3줄이고 비용이 0 이다.

## ★★★★ 2. CAD 홀 지름만 틀리게 만든 통제 실험 (n=120, GT 초기, 게이트 없음)

렌더는 `spec15`(ø35.04) 고정. **모델 CAD 만** `build_semi_flange --hole-d63` 로 바꿨다
(나머지 기하는 정점 단위로 동일 — 최대 차 2.000mm 가 전부 홀에서 온다).

| 모델 CAD 홀 | 대응점 | **윤곽 모드** R중앙 / KPI | **★중심 모드** R중앙 / KPI |
|---|---|---|---|
| ø33 (실물보다 **작음**) | 2,848 | 1.838 / 75 | **2.916 / 63** ❌ |
| **ø35 (정확)** | 5,011 | 0.166 / 110 | 0.164 / 109 |
| ø37 (**큼**, +1mm 반경) | 8,874 | 3.619 / **48** | **0.201 / 111** ✅ |
| ø39 (**큼**, +2mm 반경) | 9,665 | **7.222 / 16** | **0.293 / 113** ✅ |

- ✅ **제안이 맞다** — 모델 홀이 실물보다 클 때 윤곽 모드는 **KPI 16/120 으로 붕괴**하는데
  중심 모드는 **113/120 으로 거의 완전 면역**이다. **홀 지름 오차 ±2mm 를 통째로 무력화한다.**
- ✅ **정확한 CAD 에서 비용이 0 이다**(0.166 → 0.164). 켜 두지 않을 이유가 없다.
- ❌ **모델 홀이 실물보다 작으면 안 듣는다** — 오히려 나쁘다(75 → 63).

### ★★ 2a. 비대칭의 원인은 **대응점 수**다 (2,848 vs 9,665)

- **모델 홀이 크면** 샘플이 홀 **바깥 판 위**에 떨어지고, 법선 탐색(±8px ≈ 3mm)이 진짜 홀 테두리를
  **일관되게** 되찾는다 → 편향이 **상수**라 중앙값 제거가 정확히 지운다. 대응점이 오히려 **늘어난다**.
- **모델 홀이 작으면** 샘플이 **어두운 깔때기 안**에 떨어져 `min_grad` 미달로 절반이 탈락한다
  (5,011 → 2,848). 살아남은 것만 편향돼 **상수가 아니고**, 중앙값 제거가 오히려 참 신호를 깎는다.

## ★★★ 3. 그래서 설계 규칙이 나온다 — **CAD 홀을 일부러 크게 잡는다**

> **모델 홀 지름 ≥ 예상 실물 최대치**로 만들고 `--hole-center-mm` 을 켠다.
> 차이는 **법선 탐색 반경(`--search-px`) 안**에 있어야 한다(여기서 8px ≈ 3mm).

ø39(+2mm 반경)로 일부러 키운 CAD + 중심 모드가 **KPI 113/120 으로 정확한 CAD(110)보다 오히려 높다.**
지름을 모를 때 **크게 잡는 쪽이 안전 방향**이라는 뜻이다.

## 4. 배포 구성에서의 비용 (n=120, 융합 초기 + 게이트, CAD 정확)

| 구성 | R중앙 | R평균 | R최대 | t중앙 | KPI |
|---|---|---|---|---|---|
| 전체 실루엣 | 0.246 | 0.349 | 1.442 | 0.356 | 120/120 |
| 규격부(홀 **윤곽**) | **0.192** | **0.315** | 1.559 | 0.351 | 120/120 |
| **★규격부(홀 중심)** | 0.208 | 0.329 | 1.676 | 0.356 | 120/120 |

**정확한 CAD 에서 중심 모드의 대가는 R 중앙 0.016° 뿐**이고 t·KPI 는 동일하다.
불확실한 실물 홀 지름에 대한 보험으로 **싸다** → **기본으로 켠다.**

## 🔴🔴 5. **정정 — `d63` 는 밑면 치수다. 카메라가 보는 것은 최상면 개구이고, 규격이 안 잡는다**
(사용자 지적, 2026-08-11)

위 2절이 `--hole-d63` 로 실험해 놓고 *"홀 ø35 = 정확"* 이라고 적은 것은 **부정확하다.**
`d63` 은 **상판 밑면**에서의 치수이고, 실루엣에 나타나는 것은 **최상면 개구**다:

| CAD | `d63` (밑면) | **최상면 개구** |
|---|---|---|
| `foup_300_semi` (구) | ø31 | ø41 |
| **`spec15` (현행)** | ø35 | **ø45** |
| hole37 / hole39 / hole41 | ø37 / ø39 / ø41 | ø47 / ø49 / **ø51** |

`β=45°` 이므로 `최상면 = d63 + 2 × (홀 위 재료 두께)`. 현행은 35 + 2×5 = **45**.
**사용자 실측은 ~50mm** 다 → **홀 주변 융기 ≈2.5mm**(45 + 2×2.5 = 50)로 정확히 설명된다.
사용자 확정 사실 *"제조사마다 홀 최상면 융기가 있는 것과 없는 것이 있다"* 와 일치한다.

### 🔴 5a. 최상면 개구는 **규격이 잡지 않는다** — ø45~ø51 이 전부 준수품이다

- `d63` **공차** ø35±0.1 (밑면)
- `z49` **봉투** ≤8 (공차가 아니다 — 5~8 어디든 준수)
- 홀 주변 융기 — **규격 항목 자체가 없다**

→ `최상면 개구 = 35 + 2·(5~8) = **45~51**`, 융기가 있으면 더. **6mm 폭이 자유롭다.**
근접 조건(fx 1200, Z 442)에서 1mm = **2.72px** 이므로 반경 3mm 차 = **8.1px** — 기본 탐색(±8px)과 같다.

### ★★★★ 5b. 그래서 **현행 CAD 는 "안 듣는 방향"의 끝에 있다**

2절의 결론은 *"모델 홀이 실물보다 커야 중심 모드가 듣는다"* 였는데, 현행 `spec15`(ø45)는
실측(~50)보다 **작다**. 모델 개구를 실측 상한(ø51)에 맞춘 뒤 **거꾸로** 재보면(렌더 ø45 = 모델이 6mm 큼):

| 전략 (n=120, 융합 초기, 게이트 1.5°) | CAD 정확 R중앙 / t중앙 | **개구 6mm 차 R중앙 / t중앙** | 후퇴 (정확 → 6mm차) |
|---|---|---|---|
| 홀 **윤곽** | **0.192 / 0.351** | 0.428 / 0.755 | 24 → **113/120** |
| 홀 **중심** | 0.208 / 0.356 | 0.449 / 0.443 | 23 → 38/120 |
| 홀 **제외**(`--outer-only` 단독) | 0.224 / 0.419 | **0.224 / 0.419** | 20 → **20/120** |

- **KPI 는 셋 다 120/120** — 게이트가 지킨다. 갈리는 것은 **정확도와 후퇴율**이다.
- 🔴 **6mm 차에서 홀 윤곽은 초기값(0.428/0.761)과 사실상 같아진다** — **113/120 이 후퇴**해서
  *정합이 아무 일도 안 한 것*과 다름없다.
- ✅ **6mm 차에서는 홀을 아예 빼는 것이 R·t 둘 다 최선**이다(0.224/0.419). 홀 기하와 무관하므로
  **CAD 정확 케이스와 소수점까지 동일**하다 — 구조적 면역.
- 중심 모드는 **중간 영역**(±2mm)에서 최고다(§28-2: KPI 16 → 113). 6mm 는 그 범위를 넘는다.

### ★★★★★ 5c. **게이트 후퇴율이 홀 불일치의 GT-free 진단기다**

위 표 오른쪽 열이 핵심이다 — **홀 윤곽 모드의 후퇴율이 24 → 113/120 으로 폭증**한다.
GT 가 없어도 **같은 데이터에 세 모드를 돌려 후퇴율만 비교하면** CAD 홀이 실물과 맞는지 알 수 있다:

| 관측 | 뜻 | 조치 |
|---|---|---|
| 세 모드 후퇴율이 비슷 (~20%) | CAD 홀이 실물과 맞다 | **홀 윤곽** (최고 정확도) |
| 윤곽만 폭증, 중심은 보통 | 지름이 어긋난다 (±2mm 급) | **홀 중심** |
| 윤곽·중심 둘 다 폭증 | 개구가 크게 다르다 (≥5mm) | **홀 제외** |

### ★ 5d. 처방 — **캘리퍼 한 번이면 최선 구성이 복구된다**

최상면 개구는 **버니어 캘리퍼로 직접 잴 수 있다**. 전체 3D 스캔이 필요 없다.
재서 CAD 를 맞추면 `홀 윤곽`(R 0.192 / t 0.351)로 돌아가고, 못 재면 `홀 제외`(0.224 / 0.419)로
간다 — **대가는 R 0.032° / t 0.068mm** 다. 즉 **이 한 치수를 재는 값어치가 그만큼**이다.

⚠️ 그리고 **규격이 안 잡는 치수라 "규격 준수 CAD" 로는 해결되지 않는다.** 개별 실물마다 다르다.

## ⚠️ 6. 한계

- **여전히 CAD 교란 대리 측정이다.** 실제 제조사별 홀 개구 분포는 실물 스캔이 있어야 안다.
- 융기 유무는 **개구 크기**뿐 아니라 **테두리 밝기 프로파일**도 바꾼다 — 후자는 안 쟀다.
- 탐색 반경을 넘는 지름 오차(여기서 >3mm)는 이 방법으로 못 잡는다. `--search-px` 를 키우면 중심 모드는
  좋아지고(KPI 96 → 99) **윤곽 모드는 더 나빠진다**(24 → 3) — 잘못된 예측이 더 멀리까지 끌려간다.
- **홀 주변 융기의 밝기 프로파일**은 안 쟀다. 융기는 개구 크기뿐 아니라 edge 의 모양도 바꾼다.

## 재현 (§28)

```bash
# 모델 홀만 다른 CAD (렌더는 spec15 그대로 — 나머지 기하 동일)
envs/cad/bin/python -m spatial_vision.cad.build_semi_flange --obj assets/obj/foup_300_semi \
    --out runs/mesh_pert/hole39 --hole-d63 39 --rim-plate-mm 5 --subdivide-mm 1.5
envs/cad/bin/python -m spatial_vision.cad.verify_semi --obj runs/mesh_pert/hole39   # d63 위반이 뜨는 게 정상

# 중심 모드
envs/pose/bin/python -m spatial_vision.stages.refine_contour --in runs/obl20_near \
    --pose-dir runs/obl20_near --pose-name pose_gt.json --obj runs/mesh_pert/hole39 --fix-z \
    --outer-only --keep-hole-mm 25 --hole-center-mm 25 --out runs/obl20_h39_center
```

---

# ★★★★★ 29. 실물 변이 매트릭스 — **어느 형상 축을 맞춰야 하는가** (2026-08-11)

> 📐 **측정 조건** — **렌더 자산 `fv_h{0,1,2}r{0,2}`**(홀 융기 × 외곽 융기) · `fx 1200 @1280×720` · **n=120** · seed 동일(카메라 pose 차 0.0000°).

사용자 방침: *"실물 테스트는 나중에 한다. sim 에서 다양한 조합으로 후보를 추려 우선순위를 매긴다."*
그래서 지금까지의 **CAD 만 교란한 대리 측정**을 넘어, **변이를 렌더 자산 쪽에 넣고** 캡처부터 다시 했다.

## 1. 설계 — 실물 변이를 자산으로 만든다

`build_semi_flange --hole-raise-mm` 을 추가했다(45° 원뿔이 위로 연장돼 **개구가 `2×raise` 커진다**).

| 자산(=실물) | 홀 융기 | 외곽 융기(림) | 최상면 개구 |
|---|---|---|---|
| `fv_h0r2` | 0 | 2mm | ø45.00 |
| `fv_h2r2` | **2mm** | 2mm | **ø48.92** |
| `fv_h0r0` | 0 | **0** | ø45.00 |
| `fv_h2r0` | **2mm** | **0** | **ø48.92** |

각 **120프레임 · seed 700 동일** → **카메라 pose 가 자산 간 완전히 동일**하다(elevation 차 **0.0000°**).
배포 CAD 5종 × 전략 4종 × 초기값 2종으로 돌렸다. 초기값 `jit` = **R 0.428° / t 0.761mm 고정 교란**
(원거리 5시점 융합 초기값의 실측 오차 급). 눈으로 볼 것: `docs/semi/hole_ridge_capture.png`.

⚠️ **GT 초기값 행은 읽으면 안 된다** — 게이트가 걸리면 결과 = 초기값 = GT 라서 `R 0.001°` 가 나온다.
*"정합이 거의 전부 기각됐다"* 를 *"완벽하다"* 로 읽는 착시다(후퇴 88~118/120). → 횡단 정리 #62.
**봐야 할 것은 초기값 대비 이득 배수와 후퇴율**이다.

## ★★★★ 2. 결과 — 이득 배수 (초기값 R 0.428° 대비), 괄호는 게이트 후퇴/120

| 배포 CAD | 전략 | 홀0/림2 | 홀2/림2 | **홀0/림0** | **홀2/림0** | 최악 이득 |
|---|---|---|---|---|---|---|
| `h0r2` (현행) | 홀 윤곽 | **×1.77** (22) | ×1.00 (69) | **×0.45** (32) | ×1.00 (69) | 0.45 |
| `h0r2` | 홀 중심 | **×2.02** (20) | ×1.00 (55) | ×0.43 (35) | ×1.00 (85) | 0.43 |
| `h0r2` | **홀 제외** | ×1.51 (21) | **×1.61** (22) | ×0.45 (25) | ×0.46 (25) | 0.45 |
| `h0r2` | 전체 실루엣 | ×1.38 (21) | ×1.00 (59) | ×0.46 (25) | ×1.00 (69) | 0.46 |
| `h1r2`·`h2r2` | 홀 윤곽/전체 | ×1.00 (84~118) | ×1.00 | ×1.00 | ×1.00 | **1.00** |
| **`h0r0`·`h2r0`** | **홀 제외** | ×0.46 (37) | ×0.47 (42) | **×1.92** (4) | **×2.01** (4) | 0.46 |
| `h0r0` | 홀 윤곽 | ×0.71 (26) | ×1.00 (108) | **×1.47** (23) | ×1.00 (97) | 0.71 |

## 🔴 3. **최악 축은 홀이 아니라 「외곽 융기(림) 유무」다**

- **림이 어긋나면 전 전략이 ×0.43~0.47** — 즉 **정합이 초기값보다 나쁘게 만든다.**
  그리고 🔴 **게이트가 못 막는다**(후퇴 25~42 뿐). 오차가 폭주가 아니라 **일관된 편향**이라
  이동량이 τ 를 안 넘는다. §26-3 의 게이트는 *축퇴형 폭주* 전용이고 **계통 편향에는 무력**하다.
- **림을 맞추면 매트릭스 전체 최고 이득이 나온다** — `h0r0` CAD + `h0r0`/`h2r0` 자산에서
  **×1.92~2.01, 후퇴 4/120**. 후퇴가 4 라는 것은 *"정합이 거의 모든 프레임에서 채택됐다"* 는 뜻이다.
- **림은 육안으로 바로 보인다** — 홀 개구(캘리퍼 필요)보다 훨씬 싼 선행 측정이다.

## ★★★ 4. 홀 축은 「제외」가 유일하게 견딘다 — 그리고 **크게 잡으면 "무해하지만 무용"**

- 홀 개구가 어긋난 자산(`h2r2`)에서 **홀 제외만 ×1.61 로 이득을 유지**한다.
  나머지는 **×1.00**(후퇴 55~69) — 정합이 통째로 기각돼 **초기값 그대로**다.
- **CAD 홀을 크게 잡으면**(`h1r2`/`h2r2`) 전 자산에서 **×1.00 · 후퇴 84~118** 이다.
  **손해도 없고 이득도 없다.** 최악 기준으로는 1위지만 *"정합을 안 켠 것"* 과 같다.
  → **최악 기준 순위가 "아무것도 안 하기" 를 위로 올린다.** 지표의 함정이 아니라 실제 위험 구조다 —
  **이득 배수를 함께 보지 않으면 이 순위에 속는다**(횡단 정리 #63).
- 홀 제외 행은 **모델의 홀 지름과 무관하게 소수점까지 같다**(구조적 면역 재확인).

## ★★★★★ 5. 그래서 실물 준비 체크리스트가 두 줄로 떨어진다

| # | 무엇을 | 어떻게 | 틀리면 |
|---|---|---|---|
| **1** | **외곽 테두리 융기 유무** | **육안** (있으면 2mm 급 단차가 보인다) | 정합이 **해롭다** (×0.45), 게이트도 못 막는다 |
| **2** | **최상면 중심 홀 개구** | **캘리퍼** | 이득이 사라진다 (×1.00) — 해롭진 않다 |

- **둘 다 맞추면**: 홀 윤곽 ×1.77~1.92 (최고 정확도)
- **1만 맞추고 2 를 모르면**: **홀 제외** ×1.92~2.01 ← **권장 기본값**
- **1도 확신 못 하면**: CAD 홀을 크게 잡아 **정합을 스스로 기각시킨다**(×1.00, 무해) —
  또는 **정합을 끄고 융합 초기값만 쓴다.** 둘이 같은 결과다.

## ⚠️ 6. 한계

- 림 융기 높이는 **2mm 한 점**만 봤다(사용자 육안 관측치). 1mm·3mm 중간값은 안 쟀다.
- 초기값은 **등방 jitter 프록시**다. 실제 융합 초기값의 오차는 방향 구조가 있을 수 있다.
- **자산 4종 모두 우리 CAD 계열에서 파생**됐다 — 진짜 타사 FOUP 의 형상 차이는 여기 없다(§20-5 의
  하이브리드가 그쪽 축이다).
- `--hole-raise-mm` 로 만든 융기는 **flat 1.75 / round 2.5** 로 최외곽 융기와 같은 프로파일을 가정했다.

## 재현 (§29)

```bash
B="envs/cad/bin/python -m spatial_vision.cad.build_semi_flange --obj assets/obj/foup_300_semi \
   --rim-plate-mm 5 --subdivide-mm 1.5"
$B --out assets/obj/fv_h2r2 --hole-raise-mm 2            # 홀 융기 2mm (개구 ø45 → ø48.92)
$B --out assets/obj/fv_h0r0 --hole-raise-mm 0 --no-rim   # 외곽 융기 없음
# ⚠️ seed 를 자산 간 동일하게 → 카메라 pose 가 같아져 A/B 가 통제된다 (elevation 차 0.0000° 확인)
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd assets/obj/fv_h2r2/mesh.usda \
    --out runs/fv_h2r2_near --frames 120 --seed 700 --fx 1200 --distance-m 0.35 0.50 --elevation-deg 40 70 ...
# 초기값 프록시 (융합 초기값 오차 급) → 렌더 자산 × 배포 CAD × 전략
envs/pose/bin/python -m spatial_vision.eval.fuse_pose --near runs/fv_h2r2_near --mode jitter \
    --jitter-deg 0.428 --jitter-mm 0.761 --seed 11 --out runs/fv_h2r2_jit
envs/pose/bin/python -m spatial_vision.stages.refine_contour --in runs/fv_h2r2_near \
    --pose-dir runs/fv_h2r2_jit --pose-name pose_init.json --obj assets/obj/fv_h0r2 \
    --fix-z --gate-deg 1.5 --outer-only --out runs/mx/h2r2__h0r2__exclude__jit
```

---

# ★★★★ 30. SEMI **E47.1-1101** 원문 대조 — `z49`·`d63` 정의 확정, 융기 2mm 자산 검증 (2026-08-11)

> 🛠 **측정 절이 아니다** — SEMI **E47.1-1101 원문** 대조와 융기 2mm 자산 `foup_300_semi_r2` 규격 검증(메쉬 실측).

사용자가 `docs/semi/SEMI E47.1-1101 …` 을 추가했다. **-1106 보다 설명이 상세**하다(치수 정의를
*"어디에서 어디까지"* 로 문장으로 적어 둔 표가 있다). ⚠️ **치수 값 자체는 -1106 이 최신**이므로
값은 -1106, **정의는 -1101** 로 읽는다.

## 1. 원문이 확정해 준 것 (p15 치수표)

| 기호 | 값 | **from** | **to** |
|---|---|---|---|
| `z47` | 210 ± 1 mm | external horizontal datum plane | **bottom of robotic handling flange** |
| `z48` | ≥ 15 mm | bottom of flange | encroachment of box top underneath flange |
| **`z49`** | **≤ 8 mm** | **bottom of** robotic handling flange | **top of** robotic handling flange and upper door frame volume |
| `z50` | ≥ 5 mm | bottom of flange | encroachment underneath **the center hole** |
| **`d63`** | **ø35 ± 0.1** | 중심(nominal wafer center line) | 중심 홀 **at height `z47`** |
| `x45` | 65.3 ± 1 | bilateral datum plane | 측면 position·orientation 노치 **최근접점** |
| `x69` | 7.6 ± 0.1 | bilateral datum plane | **kinematic grooves** 의 경사면 시작 |

**두 가지가 확정됐다:**
1. **`z49` 는 flange 의 «밑면→윗면» 전체 두께**이고 **8mm 이하 봉투**다. **융기를 포함한다.**
   → 사용자 실측 *"융기까지 해서 7mm"* 는 **규격 준수**다. 융기 추가는 정당하다.
2. **`d63` 은 `z47`, 즉 flange 밑면에서** 잰다 → **윗면 융기는 `d63` 에 영향을 주지 않는다.**

## 🔴 2. 그래서 검사기 두 곳이 틀려 있었다

| 항목 | 전 | 후 |
|---|---|---|
| `z49` | `0.55×half` 반경에서 판 두께 → **5.0** | **융기 포함 최대 두께** = `z_top_max − z_bot` → **7.0** |
| `d63` | `z_top − z49` 높이에서 측정 | **flange 밑면(`z_bot`)** 에서 측정 |

전자는 **봉투 검사를 무의미하게** 만들고 있었다 — 융기를 안 지나는 반경에서 재니 융기가 아무리
높아도 5.0 이 나온다. 후자는 융기가 생기면 **판 아래로 내려가** 엉뚱한 곳을 잰다.
→ 횡단 정리 #65.

## ✅ 3. 융기 2mm(최외곽 + 중심 홀) 자산 — **SEMI 전 항목 통과**

`assets/obj/foup_300_semi_r2` (`--rim-raise-mm 2 --hole-raise-mm 2 --rim-plate-mm 5 --subdivide-mm 1.5`):

| 항목 | 규격 | 실측 | |
|---|---|---|---|
| `x46` 외곽 반폭 | 71 ± 1 | 71.00 | ✅ |
| **`d63` 중심 홀 (밑면)** | **ø35 ± 0.1** | **35.08** | ✅ |
| `θ` 노치각 | 45 ± 0.5° | 45.00 | ✅ |
| `β` 원뿔각 | 45 ± 1° | 44.933 | ✅ |
| 노치 위치 | 0 / ±30±1 / ±50±1 | 통과 | ✅ |
| 노치 4면 상이 | 필수 | True | ✅ |
| `x47` 챔퍼 시작 | ≥ 58 | 58.00 | ✅ |
| **`z49` 두께 (융기 포함)** | **≤ 8** | **7.00** | ✅ |

**`d63` 은 융기 유무와 무관하게 35.08 로 동일**하다(`fv_h0r2`·`fv_h2r2`·`r2` 셋 다) — 융기가
윗면에만 얹히고 `d63` 은 밑면에서 재기 때문이다. **질문에 대한 답: 여전히 만족한다.**

⚠️ 최상면 개구는 융기 때문에 **ø45.00 → ø48.92** 로 커진다. 이것은 **규격 항목이 아니다**(§28-5).

## 🔴 4. keypoint 도 한 곳 틀려 있었다

`center_hole_circle` 이 **주 상면(z=0)에서만** 홀을 찾고 있었다. 융기가 홀 둘레를 z=+2 로 들어올리면
주 상면이 홀에 닿지 않아 **융기 바깥 경계(ø53.05)를 홀로 잡는다**. → `verify_obj` 가 0.21mm 이탈로 실패.
**`z ≥ z_top` 전체에서 최소 반경**으로 고쳤다 → ø48.92 @ z=+1.96, 이탈 **0.0041mm** 로 통과.
`measure_standard_features` 에도 같은 버그가 있어 함께 고쳤다(`meta.json` 재생성).

## ⚠️ 5. **`x69 = 7.6 ± 0.1` — 해석 미결로 남긴다** (2026-08-11, 사용자와 함께 검토 후 보류)

사용자 해석: *"상판 중심선에서 노치의 경사면이 시작되는 거리"*. 우리 노치를 실측했다(+x 변, y=0 노치):

| 항목 | 실측 | 규격 | |
|---|---|---|---|
| `x45` 노치 최근접점 | **66.001** | 65.3 ± 1 | ✅ (검사기에 추가함) |
| 노치 깊이 | 5.000 | — | |
| 벽 기울기(직선 변 기준) | **45.0°** | `θ` 45 ± 0.5 | ✅ |
| **경사면 시작 \|y\|** | **5.000** | `x69` 7.6 ± 0.1 ? | ❓ **2.6mm 차** |

🔴 **그런데 세 항목이 동시에 성립하지 않는다** — 이것이 해석을 확정 못 하는 이유다:
- 경사면 시작 7.6 + 벽 45° → 깊이 7.6 → 최근접점 **63.4**. 그런데 `x45` 는 64.3~66.3 이다.
- 경사면 시작 7.6 + 깊이 5.7(`x45` 공칭) → 벽 **36.9°**. 그런데 `θ` 는 45±0.5° 다.
→ `x69`·`x45`·`θ` 중 **적어도 하나는 다른 것을 가리킨다.** 후보: ⓐ `θ` 가 벽-변 각이 아님
ⓑ 노치 입구에 **리드인 챔퍼**가 있고 그 바깥 끝이 7.6 ⓒ `x69` 는 노치가 아닌 **별개의 kinematic groove**.

**사용자 가설 검정**(*"융기 부분까지 포함된 값 아닐까"*) — **기각**. 높이를 바꿔 재면:

| 절단 높이 | 겉보기 깊이 | **경사면 시작 \|y\|** |
|---|---|---|
| 주 상면 z=0 | 5.000 | **5.000** |
| 융기 중턱 z=+1 | 8.127 | **5.000** |
| 융기 꼭대기 z=+2 | 6.663 | **4.986** |

**깊이는 높이마다 크게 달라지지만 «경사면 시작» 은 5.0 에서 안 움직인다** — 융기를 포함해도 7.6 이 안 된다.

⚠️ 원문 PDF 는 **스캔(JBIG2)** 이라 그림을 렌더할 수 없고, 추출 본문은 OCR 이라 실제로
`"x69 =7 6±0 , 1"` 처럼 깨져 있다. **도면 오독으로 거짓 위반을 보고한 전력**(횡단 정리 #50) 때문에
**위반으로 판정하지 않는다.** 측정값은 `notch_angled_start_mm` 로 **INFO 기록만** 하고,
해석이 확정되면 공차 항목으로 승격한다.

⚠️ **다만 남겨 둘 위험**: 이건 **상판 외곽 윤곽**의 형상이고, §29 가 *"외곽 윤곽이 어긋나면 테두리
정합이 오히려 해롭다(×0.45)"* 로 확인한 **바로 그 축**이다. 실물 노치를 캘리퍼로 재면 바로 닫힌다.

### 5b. kinematic grooves 자체는 우리 CAD 에 없다
`r 28~60` 상면이 **전 방위에서 z=0 평탄**이다(실측) — 홈이 없다. 실물에 있으면 **상면에 추가
실루엣**이 생기므로 `--outer-only`(안쪽 실루엣 제외)를 쓰는 또 하나의 근거가 된다.

## 재현 (§30)

```bash
envs/cad/bin/python -m spatial_vision.cad.build_semi_flange --obj assets/obj/foup_300_semi \
    --out assets/obj/foup_300_semi_r2 --rim-plate-mm 5 --subdivide-mm 1.5 \
    --rim-raise-mm 2 --hole-raise-mm 2
envs/cad/bin/python -m spatial_vision.cad.verify_semi --obj assets/obj/foup_300_semi_r2 \
    --json-out assets/obj/foup_300_semi_r2/semi_check.json
envs/cad/bin/python -m spatial_vision.cad.verify_obj  --obj assets/obj/foup_300_semi_r2
envs/cad/bin/python -m spatial_vision.cad.build_usd   --obj assets/obj/foup_300_semi_r2

# 치수 기입 도면 (5패널, 값은 전부 메쉬 실측 · 위반은 빨강)
# ⚠️ 인터프리터가 **envs/pose** 다 — cad venv 에는 matplotlib 이 없다
envs/pose/bin/python -m spatial_vision.viz.dim_sheet --obj assets/obj/foup_300_semi_r2 \
    --out docs/semi/dim_foup_300_semi_r2.png
```

## 6. 눈으로 확인 — 치수 도면

| 파일 | 자산 |
|---|---|
| `docs/semi/dim_foup_300_semi.png` | 원본 — **`d63` 31.03 위반(빨강)**, 융기 없음, z49 5.00 |
| `docs/semi/dim_foup_300_semi_spec15.png` | 규격 대조본 — 최외곽 융기만, 개구 ø44.95 |
| **`docs/semi/dim_foup_300_semi_r2.png`** | **융기 2mm 둘 다 — 전 항목 통과**, 개구 ø48.95 |

⚠️ 측정에서 세 번 헛짚었고 전부 **단면으로 재서** 고쳤다:
`z_bot` 을 정점 최소 z 로 잡으면 아래로 뻗은 벽(−29mm)을 집는다 ·
`d63` 을 정점으로 재면 원뿔 벽에 그 높이 정점이 없어 45.1 이 나온다 ·
`x47` 을 z=0 정점으로 재면 **융기 때문에 그 높이가 비어** NaN 이 된다.
→ **테셀레이션에 의존하지 않는 측정은 정점이 아니라 «평면 절단» 으로 한다.**

---

# ★★★★★ 31. 규격 자산 `r2`(융기 2곳)로 전 체인 재실행 — **배포 권고가 P7h → P9 로 뒤집혔다** (2026-08-11)

> 📐 **측정 조건** — **자산 `foup_300_semi_r2`(융기 2곳 — 현행 배포 자산)** · `fx 1200 @1280×720` · 원거리 0.8~1.2m / 근접 0.35~0.50m · **n=120** · seed·경사대를 `spec15` 와 동일하게 둔 **통제 비교**.

§30 에서 만든 **`foup_300_semi_r2`**(최외곽 융기 2mm + **중심 홀 융기 2mm**, SEMI 전 항목 통과)로
캡처부터 후보 산출까지 다시 돌렸다. 지금까지의 수치는 전부 `spec15`(홀 융기 **없음**) 기준이었다.

**통제**: seed 700 · 경사 40~70° · 조명 설정을 `obl20`(=spec15)과 **동일**하게 두어 **자산만 바뀐 비교**다.
⚠️ 자산이 바뀌면 **ISM 템플릿·SAM3 참조도 재생성**해야 한다(교훈 #40) — 42뷰 재렌더 + 참조 8장 재캡처.

## 1. 전단(분할·FoundationPose)은 무감각하다 — FP 는 오히려 약간 낫다

| | `spec15` | **`r2`** |
|---|---|---|
| ISM 원거리 `full` IoU / 오선택 | 0.902 / **1**/120 | 0.908 / **1**/120 |
| SAM3 근접 `flange` IoU / 오선택 | 0.982 / 0 | 0.982 / 0 |
| 원거리 `full` FP coarse | 0.549° / 1.713mm / 118 | **0.520 / 1.774 / 119** |
| 근접 `flange` FP coarse | 0.510 / 0.928 / 120 | **0.447 / 0.926 / 120** |

§25 의 *"분할·FP 는 자산 교체에 무감각"* 이 홀 융기에서도 성립한다.

## 🔴 2. 그런데 **테두리 정합이 무너진다** — 홀을 쓰는 모든 구성에서

| 후보 | `spec15` R / t | **`r2` R / t** | **`r2` 게이트 후퇴** | 대응점 |
|---|---|---|---|---|
| P5c 단일+정합 | 0.245 / 0.642 | 0.497 / 0.888 | **91**/120 | 13,874 |
| P6 융합+전체 실루엣 | 0.246 / 0.356 | 0.407 / 0.838 | **93**/120 | 14,217 |
| P7 융합+규격부 | 0.192 / 0.351 | 0.398 / 0.838 | **92**/120 | 13,875 |
| P7h 하이브리드+규격부 | **0.184 / 0.325** | 0.294 / 0.831 | **88**/120 | 13,890 |
| P8 홀 중심 | 0.208 / 0.356 | 0.300 / 0.839 | 79/120 | 14,350 |
| **★P9 홀 제외** | 0.224 / 0.419 | **0.241 / 0.549** | **24**/120 | **1,701** |

- **KPI 는 전부 120/120** — 게이트가 지킨다. 갈리는 것은 *"정합이 실제로 채택되는가"* 이고,
  **후퇴율이 그것을 그대로 보여준다**: 홀을 쓰면 88~93/120 이 기각돼 **결과가 초기값과 거의 같다.**
- **초기값이 나빠서가 아니다** — FP 는 `r2` 에서 오히려 좋다(1절). 정합 목적함수 자체의 문제다.

## ★★★ 3. 원인 — **홀이 대응점의 88%를 먹는다**

대응점 중앙값이 홀 포함 **13,875~14,350** vs 홀 제외 **1,701** 이다. 즉 **12,200개(88%)가 홀 샘플**이고,
융기로 개구가 ø45.0 → **ø48.9** 로 커지면서 원뿔이 더 깊고 어두워져 그 대부분이 **신호 없는 실루엣**이다.
§25-4c 가 `spec15` 에서 찾은 *"홀 확대(ø41→ø45)가 원인"* 이 **융기로 한 단계 더 증폭**된 것이다.

⚠️ **`--hole-center-mm` 로는 못 살린다**(후퇴 79/120). 그건 **지름 오차를 지우는** 장치이지
**신호 없는 샘플을 지우는** 장치가 아니다 — 두 문제를 혼동하지 말 것.

## ★★★★ 4. 배포 권고 (갱신)

> **실물 중심 홀 주변에 융기가 있으면 → `P9`**
> `원거리 full n=5 융합 → 근접 테두리 정합 --outer-only(홀 제외) → 이동량 게이트 1.5°`
> **R 0.241° / t 0.549mm / 120-120**

`spec15`(융기 없음)에서는 P7h(0.184/0.325)가 최선이었다 — **자산이 권고를 바꾼다.**
그리고 **P9 는 두 자산에서 거의 같다**(0.224/0.419 ↔ 0.241/0.549) → **자산을 모를 때의 기본값**이다.

## ★★★★★ 5. §29 가 설계한 **GT-free 진단이 실제로 작동했다**

§29 는 *"같은 데이터에 세 전략을 돌려 **게이트 후퇴율**만 비교하면 CAD-실물 형상 차이를 정답 없이
감지한다"* 고 했다. 여기서 그대로 발현됐다 — **24 vs 88~93** 은 GT 없이도 오해할 수 없는 차이다.

| 후퇴율 관측 | 뜻 | 조치 |
|---|---|---|
| 세 전략이 비슷 (~20%) | 홀 형상이 맞고 신호도 있다 | **P7**(최고 정확도) |
| 홀 쓰는 것만 급증 (>60%) | 홀이 신호를 안 준다(융기·깊은 원뿔) | **P9** |

**실환경에서 홀 융기 유무를 몰라도 이 비교만으로 결정된다.** 세 런은 플래그만 바꾸면 되므로 무료다.

## ⚠️ 6. 한계

- 홀 융기 **2mm 한 점**만 봤다(사용자 육안 관측치). 1mm 중간값에서 어디서 뒤집히는지는 안 쟀다.
- `r2` 는 최외곽 융기와 홀 융기를 **같은 프로파일**(flat 1.75 / round 2.5)로 가정했다.
- 오염 depth·CAD 불일치와의 **동시 조건**은 `r2` 에서 안 쟀다(§26-4 는 `spec15` 기준).

## 재현 (§31)

```bash
OBJ=assets/obj/foup_300_semi_r2
# ⚠️ 자산이 바뀌면 ISM 템플릿·SAM3 참조도 **재생성**한다 (교훈 #40)
( cd third_party/SAM-6D/SAM-6D/Render
  "$VISION_ROOT/envs/seg_sam6d/bin/blenderproc" run --blender-install-path "$VISION_ROOT/envs/blender" \
    render_custom_templates.py --cad_path "$VISION_ROOT/$OBJ/full.ply" --output_dir "$VISION_ROOT/$OBJ/ism_full" )
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda --out runs/r2_ref_near \
    --frames 8 --seed 912 --fx 1200 --distance-m 0.35 0.50 --elevation-deg 40 70 $REFAPP
envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs --from runs/r2_ref_near --obj $OBJ \
    --n 3 --target flange --out-name sam3_refs_flange_near

# 캡처는 seed·경사대를 obl20 과 동일하게 → 자산만 바뀐 통제 비교
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda --out runs/r2_near \
    --frames 120 --seed 700 --fx 1200 --distance-m 0.35 0.50 --elevation-deg 40 70 $APP $CLUT

# ★ 배포 후보 P9
envs/pose/bin/python -m spatial_vision.eval.fuse_pose --near runs/r2_near --far runs/r2_far \
    --near-pred runs/r2_near_flonly --far-pred runs/r2_far_pose \
    --pred-name pose_coarse.json --pred-name-t pose_refined.json --mode farfuse --out runs/r2_init_hyb
envs/pose/bin/python -m spatial_vision.stages.refine_contour --in runs/r2_near --pose-dir runs/r2_init_hyb \
    --pose-name pose_init.json --obj $OBJ --fix-z --outer-only --gate-deg 1.5 --out runs/r2_cand_P9
```

---

# ★★★★★ 32. 동시 주입 (depth 오염 × CAD 불일치) — **`refine` 최대 미결을 «판정 절차» 로 닫는다** (2026-08-11)

> 📐 **측정 조건** — `r2` · `fx 1200 @1280×720` · **n=120** · **depth 오염(상관 10mm) × CAD 불일치(body δ10mm) 동시 주입**. ⚠️ 결론은 **주입 비율**에 달렸다.

지금까지 두 위험을 **따로** 걸어서 처방이 정반대로 나왔다: 상관 depth 오차 → `refine` **off**(§11),
CAD-실물 불일치 → **on**(§20). *"어느 쪽이 지배적인지는 sim 으로 못 정한다"* 가 문서 전체의
🔴 **최대 미결**이었다. **둘을 같이 걸어 봤다.**

**설계** (배포 자산 `r2`, n=120, 캡처·분할은 §31 것 재사용):
- **depth**: 깨끗 / `corr60` 오염 (실제 |ΔZ| 원거리 **7.27mm** · 근접 **9.66mm**)
- **CAD 불일치**: 모델만 틀리게 — 원거리 **body δ10.0mm**, 근접 **flange 중간부 δ2.78mm**(규격 띠 3mm 고정)
- `pose_fp` 가 `coarse`·`refined` 를 **둘 다 쓰므로** `refine` on/off 는 추가 런 없이 나온다.

## 1. FoundationPose — 두 위험이 정말 반대로 작용하고, **동시에는 CAD 가 이긴다**

**원거리 `full`** (R중앙° / t중앙mm / KPI):

| 조건 | coarse (refine **off**) | refined (refine **on**) |
|---|---|---|
| 깨끗 / CAD 정확 | 0.506 / 1.928 / 119 | 0.687 / 1.419 / **120** |
| 깨끗 / **CAD 불일치** | 2.189 / 8.194 / **16** ❌ | 0.640 / 1.451 / **120** ✅ |
| **오염** / CAD 정확 | 0.839 / 2.853 / **98** ✅ | 2.632 / 3.895 / **44** ❌ |
| **오염 / CAD 불일치** | 2.343 / 8.494 / **16** | 2.481 / 3.876 / **46** ✅ |

- **§11 과 §20 이 각각 재현된다** — CAD 불일치엔 on(120 vs 16), depth 오염엔 off(98 vs 44).
- ★ **동시 조건에서는 `on` 이 낫다**(46 vs 16). 이 주입 크기에서는 **CAD 불일치가 지배**한다.
  ⚠️ 단 이건 *"body δ10mm vs depth 10mm"* 라는 **내가 고른 비율**에 달렸다 — 절대적 서열이 아니다.

**근접 `flange`**:

| 조건 | coarse | refined |
|---|---|---|
| 깨끗 / CAD 정확 | 0.447 / 0.916 / **120** | 0.585 / 1.211 / 119 |
| 깨끗 / **CAD 불일치** | **89.09°** / 4.640 / **7** 💀 | **88.99°** / 5.925 / **2** 💀 |
| **오염** / CAD 정확 | 2.079 / 3.533 / 68 | 2.114 / 3.528 / 62 |
| **오염 / CAD 불일치** | **89.69°** / 10.614 / **4** 💀 | **90.29°** / 15.826 / **1** 💀 |

🔴 **flange 중간부가 2.78mm 만 어긋나도 근접 재추정이 90° 로 완전히 뒤집힌다** — `refine` 과 무관하다.
§20 의 *"flange 는 δ2 부터 뒤집힌다"* 가 배포 자산에서 **더 심하게** 재현됐다.
→ **근접 flange FP 를 단독으로 신뢰하면 안 된다. 원거리 안전망은 협상 대상이 아니다.**

## ★★★★★ 2. 그런데 **게이트 후퇴율이 `refine` on/off 를 GT 없이 골라준다**

배포 체인(원거리 5시점 융합 → **P9** 근접 테두리 정합 홀 제외 → 게이트 1.5°)을
**융합 초기값을 coarse 로 만든 것 / refined 로 만든 것** 두 벌로 돌렸다:

| 조건 | **coarse 초기** 후퇴 / R·t / KPI | **refined 초기** 후퇴 / R·t / KPI | 후퇴가 고른 쪽 | 정답? |
|---|---|---|---|---|
| 깨끗 / 정확 | **20** · 0.234/0.574 · **120** | 24 · 0.259/0.568 · **120** | coarse | ✅ (동률) |
| 깨끗 / 불일치 | 57 · 1.225/0.809 · 120 | **19** · **0.319/0.595** · 120 | refined | ✅ |
| 오염 / 정확 | **36** · **0.467/1.362** · **120** | 73 · 1.083/1.960 · 95 | coarse | ✅ |
| 오염 / 불일치 | 112 · 1.348/**6.977** · **23** | **68** · **1.005/2.031** · **91** | refined | ✅ |

> ★★★ **4/4 적중.** *"coarse·refined 초기값을 둘 다 만들고, **게이트 후퇴율이 낮은 쪽**을 쓴다."*
> **GT 가 필요 없고, 추가 촬영도 필요 없다**(같은 데이터에 플래그만 바꾼 두 런).

**🔴 최대 미결이 «고정된 답» 이 아니라 «판정 절차» 로 닫혔다.** 어느 위험이 지배적인지 미리 알 필요가
없다 — 현장에서 두 벌 돌려 후퇴율을 비교하면 된다.

## 3. 배포 체인의 버티는 범위

- **세 조건에서 120/120** 을 유지한다(깨끗/정확 · 깨끗/불일치 · 오염/정확).
- **동시 조건만 무너진다** — 그리고 그건 **초기값이 이미 무너진 것**이지(t 6.977mm) 정합의 실패가 아니다.
  refined 초기로 바꾸면 **91/120 · t 2.031mm** 로 회복된다.
- 후퇴율이 **20 → 57 → 36 → 112** 로 조건의 나쁨을 그대로 따라간다 — **런타임 신뢰도 지표로 쓸 수 있다.**

## ⚠️ 4. 한계

- **주입 비율이 결론을 정한다.** *"동시에는 CAD 가 이긴다"* 는 body δ10mm ↔ depth 10mm 라는 **내가 고른
  비율**에서의 결과다. 실물 비율은 M6 선행 측정(depth 상관길이·실물 스캔 표면거리)에서만 나온다.
- CAD 불일치는 여전히 **모델만 교란한 대리 측정**이다(렌더는 참 형상).
- 오염은 `corr60 / 10mm` **한 점**. 17·25mm 는 안 쟀다.
- flange 중간부 교란은 **규격 띠 3mm 를 고정**한 것이다 — 띠까지 어긋나면 §27-4b 대로 더 나쁘다.

## 재현 (§32)

```bash
OBJ=assets/obj/foup_300_semi_r2
envs/cad/bin/python -m spatial_vision.cad.perturb_mesh --obj $OBJ --region body \
    --delta-mm 10 --seed 0 --out runs/mesh_pert/r2_body10
envs/cad/bin/python -m spatial_vision.cad.perturb_mesh --obj $OBJ --region flange --rim-band-mm 3 \
    --delta-mm 5 --seed 0 --out runs/mesh_pert/r2_fl5
envs/stereo_onnx/bin/python -m spatial_vision.eval.perturb_depth --in runs/r2_far_onnx \
    --capture runs/r2_far --out runs/pert/r2_far_c10 --mode corr --corr-px 60 --target-mm 10 \
    --calib-mask mask_flange.png
# pose_fp 는 coarse·refined 를 둘 다 쓴다 → refine on/off 비교에 추가 런이 필요 없다
# 초기값을 coarse / refined 두 벌로 만들고 **게이트 후퇴율이 낮은 쪽**을 고른다
envs/pose/bin/python -m spatial_vision.eval.fuse_pose ... --pred-name pose_coarse.json  --out runs/j_init_...
envs/pose/bin/python -m spatial_vision.eval.fuse_pose ... --pred-name pose_refined.json --out runs/j_initR_...
```

---

# ★★★★ 33. 모션블러 · 자동노출 — **도메인 갭 마지막 sim 축. 배포 체인은 버틴다** (2026-08-11)

> 📐 **측정 조건** — `r2` · `fx 1200 @1280×720` · **n=120** · 기존 캡처에 **모션블러(2/4/8px)·AE** 를 후처리 주입(`eval.perturb_image`).

남아 있던 도메인 갭 축이다. 둘 다 **센서/이미지 단계** 효과이므로 `eval/perturb_depth` 와 같은 구조의
**이미지 교란 스테이지 `eval/perturb_image`** 로 만들었다 — 기존 캡처에 얹으므로 **재캡처가 없다.**

**설계**
- `left.png`/`right.png` 만 바꾸고 **GT(`depth_gt`·`mask_*`·`pose_gt`)는 그대로 복사**한다 —
  블러·노출은 카메라 효과이지 물체가 움직인 게 아니다. 바뀐 이미지로 stereo 를 다시 돌리면
  **depth 열화까지 자동으로** 따라온다.
- ⚠️ **좌우에 같은 커널·같은 게인**을 쓴다. 리그가 통째로 움직이고 실제 스테레오 카메라도 AE 를
  동기화한다 — 따로 걸면 **있지도 않은 시차 오차**를 만든다.
- ⚠️ **AE 는 게인만 올리면 낙관적인 흉내다.** 실센서는 게인이 판독 노이즈를 **같이 증폭**한다
  (`--ae-noise-dn`). 우리 sim 은 AE 가 없어 프레임 밝기가 **17.7~212.9** 로 요동친다(실측) —
  즉 **AE 는 해로울 수도 이로울 수도 있다.**

## 1. 물리 눈금 — 1px 이 얼마인가

| | 1px | 블러 2px | 블러 4px | 블러 8px |
|---|---|---|---|---|
| **근접** (fx 1200, Z 388mm) | **0.324mm** | 0.65 | **1.29** | 2.59 |
| **원거리** (fx 1200, Z 902mm) | **0.752mm** | 1.50 | 3.01 | 6.02 |

근접에서 **블러 4px 을 만드는 조건**: 노출 5ms 면 259mm/s · 10ms 면 129mm/s · 20ms 면 65mm/s.
→ **4px 은 "접근하며 멈추지 않고 찍는" 현실적 수준**, 8px 은 빠르거나 노출이 긴 경우다.

## 2. 정합 단계만 (GT 초기화 진단, P9, n=120) — **4px 까지 무영향**

| 조건 | R중앙 | t중앙 | KPI | 후퇴 | 대응점 |
|---|---|---|---|---|---|
| 원본 | **0.105** | 0.054 | 120/120 | 20 | 1,712 |
| 블러 2px | 0.110 | 0.063 | 120/120 | 20 | 1,703 |
| 블러 4px | 0.112 | 0.081 | 120/120 | 21 | 1,683 |
| 블러 **8px** | **0.278** | 0.268 | 120/120 | 15 | **1,582** |
| AE (노이즈 0) | 0.142 | 0.073 | 120/120 | **16** | 1,754 |
| AE + 노이즈 1DN | 0.131 | 0.072 | 120/120 | 16 | 1,754 |
| AE + 노이즈 2DN | 0.143 | 0.073 | 120/120 | 15 | 1,759 |
| 블러4 + AE + 노이즈 | 0.150 | 0.101 | 120/120 | 20 | 1,745 |

- ★ **대칭 블러는 에지 위치를 안 옮긴다** — 계단을 대칭으로 뭉개도 기울기 봉우리는 제자리다.
  그래서 4px(1.29mm)까지 사실상 무영향이다. 8px 의 열화는 흐려져서가 아니라 **융기 능선과 외곽선이
  섞여** 대응점이 줄기 때문이다(1,712 → 1,582).
- ★ **AE 노이즈가 안 아프다** — 게인 20× 에서 판독 노이즈를 20~40DN 으로 올려도 R 0.142 → 0.143.
  대응점 1,700개 + Huber 강건 추정이라 **픽셀 노이즈가 평균화**된다.
- ✅ **AE 는 오히려 후퇴율을 낮춘다**(20 → 16). 어두운 프레임(평균 33)을 평균 124 로 살리기 때문이다.

## ★★★ 3. 전 체인 — **꼬리를 때리지 중앙값을 때리지 않는다**

**분할: 거의 무영향**

| 조건 | ISM 원거리 IoU / 오선택 | SAM3 근접 IoU / 오선택 |
|---|---|---|
| 원본 | 0.908 / 1 | 0.982 / 0 |
| 블러4+AE | 0.903 / 1 | 0.979 / 0 |
| 블러8 | 0.901 / 1 | 0.976 / 0 |

**depth (stereo 재실행)** — ⚠️ **평균과 중앙값이 반대로 간다**(횡단 정리 #16 의 재발):
flange_core 중앙값 **0.356 → 0.516 → 0.540mm** 로 나빠지는데 **MAE 는 2.190 → 1.080 → 0.817mm 로
좋아진다.** 블러가 **이상치를 뭉개서** 평균을 낮추는 것이다. **중앙값이 정직한 쪽**이다.

**FoundationPose — 중앙값은 그대로인데 꼬리가 폭발한다**

| 조건 | 원거리 coarse R중앙 / **R최대** / **t최대** / KPI | 근접 coarse R중앙 / **R최대** / KPI |
|---|---|---|
| 원본 | 0.520 / **2.12** / **5.25** / 119 | 0.447 / **1.07** / 120 |
| 블러4+AE | 0.528 / **30.91** / **557.9** / 115 | 0.496 / 1.91 / 119 |
| 블러8 | 0.523 / **111.56** / **651.9** / 114 | 0.484 / **89.82** / 119 |

**중앙값은 거의 안 움직이는데 최댓값이 두 자릿수 배로 뛴다.** 블러는 *"전반적으로 조금 나쁘게"* 가
아니라 *"몇 프레임을 완전히 날리는"* 방식으로 작용한다.

## ★★★★ 4. 그런데 **배포 체인은 버틴다** — 융합이 꼬리를 흡수한다

| 조건 | 융합 초기값 R중앙 / R최대 | **P9 최종** R중앙 / t중앙 / KPI | 후퇴 |
|---|---|---|---|
| 원본 | 0.264 / **0.740** | **0.241 / 0.549 / 120-120** | 20 |
| 블러4+AE | 0.305 / **0.770** | **0.279 / 0.613 / 120-120** | 20 |
| 블러8 | 0.279 / **0.658** | **0.335 / 0.828 / 120-120** | 21 |

- ★★ **원거리 단일 추정의 R 최대가 111° 인데 5시점 융합 초기값의 R 최대는 0.658° 다.**
  **인라이어 합의가 블러가 만든 대실패를 통째로 걸러낸다** — §31 의 분할 오선택에 이어 **두 번째로
  안전망이 작동한 실례**다.
- **배포 체인은 세 조건 모두 120/120.** 열화는 R 1.4배 · t 1.5배로 **완만하다.**
- **후퇴율이 20 / 20 / 21 로 안 변한다** — 정합 자체는 멀쩡하다는 뜻이고, GT-free 진단이
  *"이건 CAD 문제가 아니다"* 를 올바르게 말해 준다(CAD 불일치일 때는 57~112 로 튄다, §32).

## 5. 정리 — **도메인 갭 sim 축이 닫혔다**

| 축 | 상태 | 결론 |
|---|---|---|
| 배경 HDRI · 재질 | 측정 완료 | 40/40 유지 |
| 센서 노이즈 (depth) | 측정 완료 | 상관 오차가 지배, §26·§32 |
| CAD-실물 불일치 | 측정 완료(대리) | §20·§27·§29·§32 |
| **모션블러** | **측정 완료** | **4px 무영향 · 8px 에서 FP 꼬리 폭발, 융합이 흡수** |
| **자동노출** | **측정 완료** | **무해, 오히려 약간 이롭다**(어두운 프레임 대비 회복) |

**남은 것은 실사진·실카메라 intrinsic 뿐이다(M6).**

## ⚠️ 6. 한계

- 블러를 **후처리 선형 커널**로 흉내냈다. 실제 모션블러는 셔터 동안의 **궤적 적분**이라 회전 성분이
  섞이면 커널이 위치마다 다르다(공간 변화 커널). 여기서는 **전역 균일 커널**이다.
- AE 의 **측광·수렴 동역학**은 없다 — 프레임마다 즉시 목표에 맞춘다. 실카메라는 몇 프레임에 걸쳐
  수렴하므로 **급격한 조명 변화 직후 몇 장이 잘못 노출**된다. 그 전이 구간은 안 쟀다.
- 롤링 셔터 없음. 실제로는 블러와 롤링 셔터 왜곡이 함께 온다.

## 재현 (§33)

```bash
envs/stereo_onnx/bin/python -m spatial_vision.eval.perturb_image --in runs/r2_near \
    --out runs/pert/r2_near_blur4aen1 --blur-px 4 --ae --ae-noise-dn 1.0
# ⚠️ 좌우에 같은 커널·게인. GT 는 복사. 이후 stereo 부터 다시 돌린다 (depth 열화가 따라온다)
envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx --in runs/pert/r2_near_blur4aen1 ...
# 정합만 빠르게 보려면 GT 초기화 진단 (stereo·분할·FP 불필요, 120프레임 10초)
envs/pose/bin/python -m spatial_vision.stages.refine_contour --in runs/pert/r2_near_blur4aen1 \
    --pose-dir runs/r2_near --pose-name pose_gt.json --obj $OBJ --fix-z --outer-only --gate-deg 1.5 \
    --out runs/img_gt_blur4aen1
```

# 횡단 정리 — "조용히 틀렸을 것들"

> 🛠 **측정 절이 아니다** — 전 절을 가로지르는 **오류 패턴 89건**. 새 실험 설계 전에 훑을 것.

파이프라인 전체에서 **눈으로는 안 보이고 수치로만 드러나는** 오류가 반복해서 나왔다. 공통 교훈:
**단위·규약·양자화는 반드시 독립적인 방법으로 교차검증한다.**

| # | 증상 | 진짜 원인 | 어떻게 잡았나 |
|---|---|---|---|
| 1 | STL 이 4cm 짜리 물체로 보임 | STL 은 cm, STEP 은 mm | 두 파일 bbox 비교 + SEMI 표준치(ø190/ø40) 대조 |
| 2 | 원점이 2mm 위 | bbox 최댓값(177)은 작은 돌기, 주 상면은 175 | 위 방향 수평면의 **면적** 가중 |
| 3 | 투영이 전부 카메라 뒤 | USD −Z 전방 vs OpenCV +Z 전방 | keypoint 투영이 0/16 |
| 4 | depth 가 0.5mm 작음 | `astype(uint16)` 가 버림 | 역투영 표면 z 의 **부호 있는** 편차 |
| 5 | 경사면에서 0.2~0.8mm 오차 | Isaac cx 는 코너 원점, OpenCV 는 픽셀 중심 (0.5px) | **바닥면(z=0) 대조군** + 서브프레임 불변성 |
| 6 | ONNX 가 2.57× 나쁨 | 해상도 강제 축소(OOM). 모델 차이는 +20% | **통제 실험**(torch 도 같은 해상도로) |
| 7 | 3면도에서 flange 가 몸체 한가운데 | 렌더마다 자기 bbox 로 정규화 | 공통 bbox 로 투영 |
| 8 | flange IoU 평균 0.643 — "그럭저럭" 으로 읽힘 | 4프레임 중 1건이 **IoU 0**(오선택), 나머지는 0.86 | 평균 대신 **오선택 건수를 따로** 셈 |
| 9 | SAM3 가 `handle` 로 2/4 "검출" | 엉뚱한 곳을 자신 있게 집음 | 검출 수가 아니라 **GT 대비 IoU** 로 판정 |
| 10 | 2-stage refine 이 t 를 32% 개선 | R 은 3.7배 악화 — ADD 로 보면 2.5배 손해 | **R·t 를 분리해서** 보고 ADD 로 합산 판정 |
| 11 | keypoint 16/16 이 마스크에 적중 | 3D 로는 12개가 최대 21.3mm 밖 | 2D 투영이 아니라 **3D 표면거리**로 검사 |
| 12 | flange depth 에 −2.85mm 계통 편차 | **n=4 의 착시** — n=40 에서 부호가 뒤집힘(+2.22) | 평균 전에 **표본 수와 표준편차**를 본다 |
| 13 | 마스크 IoU 0.98 인데 pose 가 1.5m 틀림 | **다른 FOUP** 을 잡음(오선택) | IoU 평균이 아니라 **오선택 건수**를 따로 |
| 14 | "끝단 100%" | 파편 마스크(recall 0.009) 위의 우연 | 마스크 품질과 pose 결과를 **각각** 확인 |
| 15 | 평균 t 오차 85mm → KPI 대실패로 읽힘 | 3프레임이 다른 물체(중앙값은 3.8mm) | **중앙값 + 대실패 건수**를 함께 낸다 |
| 16 | 2차 refine 이 t 중앙값을 2.01→1.64mm 개선 | 평균은 2.09→2.97 **악화**(오른쪽 꼬리), KPI 100%→60% | 중앙값·평균·**최댓값**을 **함께** 본다 |
| 17 | "FOUP 전체가 FOV 에 들어와야 한다" 를 요건으로 전제 | 잘린 프레임이 오히려 근소하게 정확. 요건은 **flange 쪽**이었다 | 가정을 전제로 두지 말고 **잘림 여부로 층화**해서 잰다 |
| 18 | "참조 시점은 무관" → 거리도 무관으로 확대 해석 | 스케일 34배 차이에서 IoU **0.044** | 참조와 질의의 **거리 분포를 따로** 대조 |
| 19 | fx 를 올리면 측면 오차(mm)가 줄 것으로 기대 | 오차는 객체 좌표계에서 고정 — px 로 환산하면 오히려 는다 | 오차를 **mm 와 px 양쪽으로** 환산해 본다 |
| 20 | 회전 대칭 잔차 median 0.00 → "완전 대칭" 으로 결론 | 같은 출력의 **max 5.83mm** 를 무시. 실제로는 사분면별 8.3mm 비대칭 | 대칭·정합 지표는 **median 이 아니라 max** 로 판정한다 |
| 21 | `trimesh.to_2D()` 단면에서 잰 테두리가 비대칭으로 나옴 | 임의 2D 프레임이라 **중심이 어긋남**(최대반경 91.68→99.90) | 회전 대칭은 **pose 원점 기준**으로만 잰다 |
| 22 | depth 노이즈를 iid 로 주입해 "근접 구성이 강건" 으로 결론 | 142,000px 이 √n=378배 평균화. **상관을 주면 순위가 뒤집힌다** | 센서 오차는 **공간 상관 길이**를 축으로 넣어 시험한다 |
| 23 | `--rel-from-gt` 런이 종료코드 0 인데 산출물이 빔 | `--init-capture` 누락 → `pose_gt.json` 못 찾고 전 프레임 건너뜀 | 프레임 처리 **건수를 종료코드와 별도로** 확인한다 |
| 24 | `σ_Z ∝ Z²` 로 근접 이득을 예측 | **σ_disp 가 거리에 따라 준다** — 실측 지수 0.8~1.0 | 모델을 쓰기 전에 **지수를 실측**한다 |
| 25 | `fx·B` 4.27배 → 오차 4.27배 개선으로 외삽 | σ_disp 가 **카메라 간 전이되지 않는다**(시차에 비례) | 카메라를 건너뛴 외삽은 **양쪽을 다 재서** 확인한다 |
| 26 | sim 예측 0.74mm 이 sim 실측 0.70mm 와 일치 → 모델 검증됐다고 판단 | 두 오차(#24·#25)가 **상쇄된 우연** | 일치는 검증이 아니다 — **독립 경로로 각 항을 따로** 확인 |
| 27 | Isaac Sim 캡처와 pose 를 동시 실행 | GPU 경합으로 9런이 **첫 프레임에서 조용히 사망**(빈 디렉토리) | 산출 **프레임 수**를 세어 종료코드와 별도 확인 |
| 28 | 재질을 바인딩했는데 렌더가 그대로 | `bind_prims` 가 **참조 안 프림에 조용히 실패**(관계는 생기고 타깃이 빔) | `Bind()` 반환값 + `ComputeBoundMaterial()` 을 **둘 다** 확인 |
| 29 | HDRI 정규화를 켰는데 프레임이 검거나 날아감 | `IMREAD_ANYDEPTH\|IMREAD_COLOR` 로 읽은 float HDR 을 16-bit 로 오인 → **14개 중 11개 평균이 0** | dtype 으로 판단하고, 평균 0 이면 **예외를 던진다**(게인 1.0 으로 넘기지 않는다) |
| 30 | randomization 을 켜니 씬이 통째로 달라짐 | 외관 추첨이 **뒤따르는 기하 추첨을 밀었다** | 외관은 **별도 난수 스트림**. 기하 40/40 일치를 확인 |
| 31 | HDRI 를 켠 채 기존 조명 밴드를 유지 | 물체 픽셀 **47% 포화** (기준선 16.7%) | 밴드를 바꾼 뒤 **포화율·밝기를 실측해** 맞춘다 |
| 32 | 배경 randomization 이 depth 를 개선 | 무지 바닥이 스테레오에 **부당하게 어려웠다**(대응점 없음) | 기준선이 쉬운지 어려운지도 **의심 대상**이다 |
| 33 | "근접 flange pose 는 원리적으로 안 된다(R 18~24°)" 로 **기각** | 원인은 원리가 아니라 **마스크 품질**이었다. IoU 0.905 → 0.983 이 되자 R 0.536° | **기각 결론에는 조건을 명시**한다. "안 된다" 가 아니라 "이 조건에서는 안 된다" |
| 34 | 시드를 맞췄는데 두 런의 기하가 어긋남 | **가림 재시도 루프가 난수를 더 소비**한다(재시도 횟수가 씬마다 다르다) | 짝지음이 필요하면 **실제로 일치하는지 세어 본다**(9/40 이었다) |
| 35 | 참조 선택 기준 `top-k` 가 IoU 0.889 → "현행보다 훨씬 낫다" | **평가에 쓴 같은 40프레임으로 골랐다**(과적합). 교차검증하니 0.846, `greedy` 는 0.896→0.820 | 선택과 평가는 **다른 프레임**으로. 기준이 살아남아도 **고른 항목 자체는 전이되지 않는다**(겹침 0/5) |
| 36 | 분할 IoU 를 올리면 pose 가 좋아질 것으로 전제하고 새 백엔드를 검토 | 마스크를 **GT(IoU 1.0)로 바꿔도** t 중앙 0.085mm 개선, refined 는 0 | 개선을 도입하기 전에 **그 축의 상한선**을 먼저 잰다(GT 로 치환해 보면 공짜다) |
| 37 | GT 가 필요한 `top-k` 를 최선의 참조 선택 기준으로 확정 | GT 없는 **면적 기준이 오히려 더 낫다**(0.889 vs 0.846) — oracle 은 20프레임 추정이라 **분산이 크다** | **정확한 기준이 불안정할 수 있다.** 대리지표를 배제하기 전에 **분산까지 비교**한다 |
| 38 | CAD 불일치가 "후처리로 못 고치는 계통 오차" 라고 결론 | **coarse 만 봤다.** refined 는 δ=10 에서도 **40/40 / t 1.03mm** 로 흡수한다 | #16 의 재발 — 이번엔 통계가 아니라 **단계**를 하나만 봤다. **coarse·refined 를 항상 같이 낸다** |
| 39 | 두 CAD 정렬을 표면거리 최소화로만 정하고 하이브리드를 만듦 | **180° 뒤집혀 있었다**(사용자가 XY 뷰에서 발견). 외곽이 대략 대칭이라 90°(중앙 7.95mm)와 270°(5.57mm)가 잘 안 갈린다 | 대칭에 가까운 물체의 정렬은 **지표로 못 정한다** — **방향 특징을 눈으로** 확인하고, 회전 규약(`V@R.T` vs `R@V`)을 옮길 때 **부호를 재검증**한다 |
| 40 | 하이브리드 CAD 를 고치고 pose 만 다시 돌림 | 캡처는 **옛 USD**(02:12), pose 는 새 메쉬(02:16) → R 오차 **179.7°** | 자산을 고치면 **어느 단계부터 무효인지** 따진다. `stat -c %y` 로 자산과 산출물의 시각을 대조 |
| 41 | 밴드(고리) 실루엣을 `cv2.fillPoly(m, tri, 255)` 한 번으로 그림 | fillPoly 는 여러 윤곽을 **짝홀 규칙**으로 합쳐 **겹치는 삼각형이 서로 상쇄**된다 — 내부에 구멍이 뚫렸다 | **포함관계로 검산한다**: full flange 실루엣(47k px)이 그 부분집합인 밴드(65k px)보다 **작게** 나온 것이 신호였다. 합집합이 필요하면 삼각형마다 `fillConvexPoly` |
| 42 | §20-4 를 *"flange **중간부** 교란"* 으로 읽음 | 그 교란은 외곽선 **곡선 하나**만 고정하고 12mm taper 해서, **테두리 안쪽도 평균 5.55mm 움직이고 있었다**(δ10, 20mm 밴드 기준) | *"무엇을 고정했나"* 를 **말이 아니라 수치로** 검산한다 — 고정하려는 영역의 실제 최대·평균 변위를 찍는다. 띠를 고정하려면 `--rim-band-mm` 처럼 **띠 전체**를 0 으로 |
| 43 | 교란용으로 `full.ply` 를 `--subdivide-mm 6` 세분화 | 33,722 → **2,223,422 삼각형** → nvdiffrast `cudaMalloc` 실패. 첫 프레임만 나오고 조용히 끝남 | 세분화는 **필요한 성분에만** 건다(flange 는 `full.ply` 안에서 별개 solid 라 T-junction 없음). 전처리 뒤 **면 수를 로그로** 남긴다 |
| 44 | 오염 depth 18mm 에서 `rim30` 이 뒤집힘을 9 vs 15 로 줄여 "밴드가 회전을 더 지킨다" 로 읽음 | **잡음 실현 1개였다.** 시드를 3개로 늘리니 15/8/15 vs 9/12/10 — **순서가 시드마다 뒤집힌다** | #12 의 재발(이번엔 프레임 수가 아니라 **잡음 시드**). **주입 실험은 시드 최소 3개**, 시드별 값을 함께 낸다 |
| 45 | rim 밴드 폭을 10·15·20·30mm 로 잡고 *"30mm 가 손익분기"* 라고 결론 | **실제 규격 띠는 2~3mm** 다(사용자). 30mm 짜리 띠는 애초에 표준부가 아니라 **문장 자체가 무의미**했다. 다시 재니 δ=10 에서 flange 전체가 0.3/40 으로 붕괴 — 격차가 훨씬 컸다 | **규격 치수는 도면·전문가에게 확인하고 시작한다.** 스윕 범위를 스스로 정할 때 *"이 값이 실제로 그럴 법한가"* 를 자산 렌더로 **먼저 눈으로** 대조한다(#39 와 같은 경로) |
| 46 | flange 윤곽을 **볼록껍질**로 잡고 테두리 밴드를 만듦 | 이 테두리에는 변 중앙·모서리마다 **오목한 노치**가 있어 껍질이 그 위에 다리를 놓는다 — 밴드가 노치 근방을 통째로 빠뜨렸다(윤곽 면적 차 200mm², 90° 대칭을 깨는 표면 8.3% vs 14.4%) | *"이 형상이 볼록한가"* 를 **가정하지 말고 검산한다**(껍질 면적 vs 투영 면적). 사용자가 렌더에서 발견했다 — 자산 렌더를 **먼저 보여주는** 절차가 실제로 잡아낸 두 번째 사례(#39) |
| 47 | stage-2 투영 마스크를 `cv2.convexHull` 로 만듦 — *"flange 실루엣은 볼록"* 이라고 주석까지 달아둠 | **테두리에 오목한 노치가 있다**(#46 과 같은 잘못된 전제, 다른 파일). 마스크가 GT 대비 평균 **1.55%**(최대 2.18%) 부풀어 배경 depth 가 refine 에 들어갔다. 사용자가 overlay 와 마스크를 대조해 발견 | **같은 잘못된 가정이 여러 파일에 복제된다** — 하나를 고치면 `grep convexHull` 로 형제를 찾는다. 영향은 재보니 무시할 수준(KPI 40/40 불변, R 0.618→0.597 / t 0.801→0.827)이지만 **"안전해서" 가 아니라 "재봤더니" 다** |
| 48 | 새 정합기(테두리)를 만들고 FP 결과 위에 올려 개선을 확인 | **목표 자체가 편향돼 있었다** — GT 를 초기값으로 주니 R 1.105° / t 1.354mm 나 움직였다(그림자 경계로 끌림) | **정합기는 GT 를 초기값으로 줘서 검증한다** — *"안 움직이는가"*. 개선폭만 보면 편향된 목표로 우연히 좋아진 것을 못 가른다 |
| 49 | `--polarity auto` 로 바꿔 KPI 39→40/40 이 되자 *"조명 때문에 밝았던 프레임이 고쳐졌다"* 고 서술 | **프레임을 안 봤다.** 실제로 역전된 건 다른 프레임(`0021`)이고, 그 프레임은 auto 로 **더 나빠졌다**. 중앙값은 양쪽이 동일하고 **실패 프레임만 바뀌었다** | 총계가 좋아졌다고 **원인을 서술하지 않는다** — **프레임 단위로 누가 좋아지고 누가 나빠졌는지** 확인하고, 근거 데이터(밝기 실측)를 함께 남긴다 |
| 50 | 규격 도면의 치수 기호를 **문맥으로 추정**해 우리 CAD 를 *"7.3mm 위반"* 이라고 보고 | `x45`(공차)는 챔퍼 시작이 아니라 **노치 모서리**까지의 거리였고, 챔퍼 시작은 `x47 ≥58`(봉투)이었다 — 우리 CAD 58.00 은 **준수**다. 앞서 *"최대 반경"* 도 규격에 없는 유도값이었다 | **도면 기호는 확대해서 화살표 끝점을 확인하기 전에 인용하지 않는다.** 규격 대조는 *"어느 점에서 어느 점까지"* 를 그림으로 남기고, 애매하면 **위반 주장 대신 확인 요청**으로 적는다 |

| 51 | 새 필터(`--outer-only`)를 붙이고 A/B 를 돌렸는데 개선이 없어 *"안쪽 능선 샘플은 이미 걸러지고 있다"* 고 결론 | **필터가 아예 동작하지 않았다.** 샘플을 점으로 찍어 고리를 만드니 획에 틈이 생겨 flood fill 이 새고 9,087개가 전부 통과했다. 선분으로 그리자 1,852 vs 7,235 로 갈렸고 결론이 뒤집혔다 | **A/B 가 소수점까지 같으면 그건 "차이 없음" 이 아니라 "적용 안 됨" 이다.** 필터를 넣으면 항상 **남은 개수를 로그로** 남기고, 먼저 그 수가 변했는지 본다 |
| 52 | `verify_semi` 가 우리 자산에 *"노치가 4면 모두 같다"* 는 위반을 냄 | `build_rim_obj.outline_polygon` 이 투영 실패 시 **조용히 볼록껍질로 물러나** 노치가 메워진 윤곽을 하류로 흘렸다 — #46·#47 과 **같은 가정이 세 번째 파일에서**, 이번엔 *대체 경로*의 형태로 | **틀린 값을 조용히 돌려주는 fallback 을 만들지 않는다.** 대체 경로도 같은 정의를 만족해야 한다(여기서는 삼각형 합집합으로 진짜 윤곽 복구). 못 만족하면 **예외로 죽는 게 낫다** |
| 53 | 같은 형상인데 자산에 따라 `verify_semi` 결과가 갈림(노치 위치·θ) | 검출기가 **윤곽 정점 밀도에 의존**했다: ⓐ 고정 8mm 여유로 잘라 챔퍼 진입 정점이 노치로 잡히고 ⓑ 묶음 간격 2mm 가 노치 폭(2.5mm)보다 좁아 노치 하나가 셋으로 쪼개졌다 | 기하 검사기는 **테셀레이션 불변**이어야 한다. 경계는 고정 상수가 아니라 **실측값**(챔퍼 시작)으로 잡고, 묶음 간격은 **규격이 보장하는 최소 간격**(노치 간 20mm)에서 정한다. 검사기는 **성긴 메쉬와 촘촘한 메쉬 양쪽**으로 회귀한다 |

| 54 | 위치 인자로 새 옵션(`outer`)을 함수에 추가하면서 **호출부만 고침** | `draw_debug(..., rim_mask, args.outer_only)` 의 `args.outer_only` 가 시그니처의 **`tile` 자리**로 들어갔다 → `2*tile = 0` 으로 `cv2.resize` 가 죽거나(False) 2×2 이미지가 나왔다(True) | 인자가 4개를 넘는 함수는 **키워드로 넘긴다.** 새 파라미터는 **기본값 있는 것들보다 앞**에 넣고, 추가 직후 그 함수를 **실제로 한 번 호출**해 본다(이 버그는 `--debug` 를 켠 런에서만 드러났다) |
| 55 | 오염 depth 하 새 실험의 원거리 KPI 가 **1/40** — §11 의 같은 조건 24/40 과 20배 차이 | ⓐ §11·§16 은 오염 조건에서 **`pose_coarse.json`(refine off)** 을 썼는데 나는 `refined` 를 봤다(2/40 vs 26/40) ⓑ 교란 보정 마스크가 달랐다(`mask_full` 이라 17% 세게 들어갔다) | **옛 절의 수치와 나란히 놓으려면 그 절의 재현 명령을 먼저 읽는다.** 특히 **어느 단계 산출물을 봤는지**(coarse/refined)와 **교란 보정 기준**은 표에 안 적혀 있어도 결과를 20배 바꾼다. 20배 차이가 나면 처방이 아니라 **비교 조건**부터 의심한다 |
| 56 | 정합 실패 프레임을 **적합도(rms)로** 걸러내려 함 | 실패의 rms(1.14~1.88px)가 성공의 범위(0.64~2.81px) **안에 완전히 들어간다.** 목적함수가 그 방향으로 평평해서(면외 tilt 축퇴) 5° 틀린 pose 도 관측에 잘 맞는다 | **축퇴 방향의 실패는 적합도로 원리적으로 판별할 수 없다.** 판별은 **사전 정보와의 불일치**(초기값 대비 이동량)로 해야 한다 — 그리고 그 판정은 GT 를 안 쓰므로 실환경에 그대로 간다 |
| 57 | 두 시각화 도구가 **GT 를 반대 색으로** 그림 (`overlay_pose` 빨강 / `refine_contour --debug` 초록) | 도구를 따로 만들면서 색을 각자 정했다. 시트를 *"초록이 GT"* 라고 말로 인용하면 **다른 쪽 시트를 정반대로 읽는다** | **범례를 이미지에 찍고, 색을 말로 옮기지 않는다.** 규약을 통일하는 것보다 **자기설명적인 그림**이 안전하다(옛 시트가 이미 흩어져 있어 규약을 바꾸면 과거 증거가 거짓말이 된다) |
| 58 | 무결점 **40/40** 을 여러 절에서 *"실패 0"* 처럼 인용 | 같은 구성을 **n=120** 으로 재니 **110/120 (8.3% 실패)** 였다. 40/40 의 실패율 95% 상한이 정확히 7.5% 였고 **경고를 적어 두고도 본문에서는 무결점처럼 읽었다** | **n=40 무결점 = "실패율 ≤7.5%"** 로만 읽는다. 구성 간 우열을 **꼬리(최댓값·KPI)로** 가릴 때는 n=40 이 부족하다 — 처방을 바꾸기 전에 표본을 늘린다 |
| 59 | 사용자가 밀던 `--outer-only` 를 n=40 근거로 **기각**했다 | ⓐ n=40 의 꼬리가 잡음이었다(n=120 에서 **모든 통계가 반대**로 나온다) ⓑ 사용자 논지는 **제조사 편차 면역**이었는데 나는 **sim 정확도**로만 반박했다 — sim 은 렌더와 CAD 가 같은 메쉬라 **그 축을 원천적으로 못 본다** | **기각하기 전에 "이 주장이 sim 에서 측정 가능한 축인가" 를 먼저 묻는다.** 측정 불가 축이면 기각이 아니라 **대리 측정을 설계**한다(여기서는 CAD 만 교란). 그리고 꼬리로 기각할 때는 표본부터 본다(#58) |
| 60 | 분할 오선택률을 **0/40 → "오선택 없음"** 으로 읽었다 | n=120 에서 **1건** 나왔다 — `select center` 가 배경을 집었고(pred 634k px, precision 0.0006) 그 한 프레임이 원거리 pose 를 **R 139.7° / t 1020mm** 로 날렸다. 횡단 정리 #15 가 예고한 실패가 표본이 커지자 발현한 것 | **드문 대실패는 표본이 커져야 보인다.** 발생률 ~1% 짜리 사건은 n=40 에서 60% 확률로 안 나타난다. 안전망(융합 인라이어 합의)이 그걸 흡수하는지를 **설계 시점에** 확인해 둔다 — 여기서는 흡수했다(융합 초기값 R 최대 1.09°) |
| 61 | 홀 실험을 `--hole-d63` 로 돌려놓고 표에 *"홀 ø35 = 정확"* 이라고 적었다 | `d63` 은 **상판 밑면** 치수이고 카메라가 보는 것은 **최상면 개구**(우리 CAD ø45, 실측 ~ø50)다. 규격은 밑면만 공차로 잡고 **최상면은 `z49`(봉투 ≤8)와 융기(규격 없음)에 좌우돼 ø45~ø51 로 자유롭다** | **규격 치수를 인용할 때 "어느 면에서 잰 값인가" 를 함께 적는다.** 그리고 정합기에 중요한 것은 규격이 잡는 면이 아니라 **카메라에 보이는 면**이다 — 둘이 다르면 규격 준수는 아무것도 보장하지 않는다 |
| 62 | 자산 매트릭스에서 `R 0.001° / KPI 120` 을 보고 *"완벽한 조합"* 이라 읽을 뻔했다 | **게이트가 걸리면 결과 = 초기값**이고 그 초기값이 GT 라서 완벽해 보인 것이다(후퇴 88~118/120). 즉 *"정합이 거의 전부 기각됨"* 을 *"정합이 완벽함"* 으로 읽는 착시 | **후퇴 장치가 있는 파이프라인은 절대 성능만 보면 안 된다.** 항상 **초기값 대비 이득 배수 + 후퇴율**을 함께 낸다. 그리고 **진단용 초기값(GT)으로 성능표를 만들지 않는다** — 후퇴가 GT 로의 후퇴가 되어 지표를 오염시킨다 |
| 63 | 최악(worst-case) 기준 순위에서 *"CAD 홀을 크게 잡기"* 가 1위로 올라왔다 | 그 조합은 **정합이 전 프레임 기각돼 이득이 정확히 ×1.00** 이다 — 손해도 이득도 없는 *"아무것도 안 하기"* 인데, 다른 조합이 어떤 자산에서 ×0.45 로 **해로워서** 상대적으로 1위가 됐다 | **최악 기준은 "해롭지 않기" 를 "좋기" 로 착각시킨다.** 이득 배수를 같은 표에 두고, `×1.00` 은 **"작동 안 함"** 으로 명시한다. 안전한 무용지물이 답일 때도 있지만 **그렇다고 말해야** 한다 |
| 64 | 이동량 게이트가 모든 CAD 불일치를 막아 줄 것이라 기대했다 | **외곽 융기 유무 불일치는 못 막는다**(후퇴 25~42 뿐, 이득 ×0.45). 오차가 **폭주가 아니라 일관된 편향**이라 이동량이 τ 를 안 넘는다 | **후퇴 장치는 자기가 보는 양(여기서는 이동량)으로 표현되는 실패만 잡는다.** 계통 편향은 이동량이 작아서 통과한다 — **편향형 실패에는 별도의 검출기**(모델-실물 형상 확인)가 필요하다 |
| 65 | `z49 ≤ 8` 봉투 검사가 **항상 통과**했다 — 융기를 2mm 얹어도 5.0 이 나왔다 | 검사기가 `0.55×half` 반경에서 판 두께를 쟀는데 **거기엔 융기가 없다.** 규격 원문(E47.1-1101)은 `z49` 를 **flange 밑면→윗면 전체**로 정의한다 — 즉 **최대 두께**를 재야 봉투 검사가 성립한다 | **봉투(≤/≥) 항목은 «최악값» 을 재야 한다.** 대표점 한 곳에서 재면 검사가 조용히 무효가 된다. 그리고 **정의의 from/to 를 원문 문장으로 확인**한다 — 값만 있는 도면표로는 어디를 재는지 알 수 없다 |
| 66 | 자산을 바꾼 뒤에도 **후보 순위는 옛 자산 기준**으로 들고 있었다 | 홀 융기 2mm 를 넣자 최선이 **P7h → P9 로 뒤집혔다**(홀을 쓰는 구성은 게이트 후퇴 88~93/120 으로 사실상 무효화). 전단(분할·FP)은 무감각해서 **자산 교체가 안전해 보였다** | **자산이 바뀌면 «전단이 무감각하다» 를 «파이프라인이 무감각하다» 로 읽지 않는다.** 하류 단계는 형상의 다른 부분에 의존한다 — **후보 순위는 배포 자산에서 다시 낸다** |
| 67 | 🔴 최대 미결(`refine` on/off)을 **하나의 정답으로** 정하려 1년 가까이 붙들었다 | 두 위험이 반대 방향을 가리켜 **고정된 답이 존재하지 않는다.** 그런데 **게이트 후퇴율이 어느 쪽이 맞는지 4/4 로 알려준다** — 둘 다 돌려서 후퇴율 낮은 쪽을 쓰면 된다 | **«어느 설정이 맞나» 를 못 정하겠으면 «어느 설정이 맞는지 런타임에 판정하는 신호» 를 찾는다.** 특히 후퇴/기각 장치가 있으면 **그 발동률 자체가 설정 선택기**가 된다 — GT 없이 |
| 68 | 블러의 영향을 **중앙값으로** 보고 *"거의 무해"* 라 읽을 뻔했다 | 원거리 FP 의 R 중앙값은 0.520 → 0.523 으로 안 움직이는데 **R 최대는 2.1 → 111.6°, t 최대는 5.3 → 651.9mm** 다. 블러는 *"전반적으로 조금 나쁘게"* 가 아니라 **"몇 프레임을 완전히 날리는"** 방식으로 작용한다 | **센서 열화는 중앙값이 아니라 꼬리로 나타난다.** 그리고 그 꼬리는 **다중 시점 융합의 인라이어 합의가 흡수**한다(초기값 R 최대 0.66°) — 열화 축을 평가할 때 **단일 추정과 안전망 뒤를 반드시 따로** 본다 |
| 69 | depth 열화를 MAE 로 보니 블러가 **개선**하는 것으로 나왔다 | 블러가 **이상치를 뭉개서** MAE 2.190 → 0.817mm 로 낮춘다. 같은 데이터의 **중앙값은 0.356 → 0.540mm 로 나빠진다** — 정직한 쪽은 중앙값이다 | 횡단 정리 #16 의 재발. **평활화 계열 교란은 평균 지표를 좋게 만든다** — 평활화가 개입하는 실험에서는 평균을 지표로 쓰지 않는다 |
| 70 | 해상도를 1280×720 → **1920×1200 으로 2.25배** 늘렸으니 테두리 정합이 더 정밀해질 거라 예상했다 | **정반대였다.** ZED X 2.2mm 는 HFOV 105° 광각이라 같은 거리에서 **물체가 화면을 덜 채운다** — flange 등가 지름이 413px → **264px** 로 오히려 1.56배 작아졌고, 정합기의 자체 오차 바닥이 t 0.132 → **1.120mm(8.5배)** 로 무너졌다 | **정합 정밀도를 지배하는 것은 «화소 수» 가 아니라 «물체가 차지하는 픽셀 수» 다.** 카메라를 바꿀 때 해상도만 보고 판단하지 않는다 — `mm/px` 와 **대상의 투영 크기**를 함께 계산한다 |
| 71 | 새 카메라 기하에서 테두리 정합의 이득이 전부 1.00 이하로 나왔는데 «게이트 τ 를 더 조여야 하나 / `--search-px` 를 줄여야 하나» 로 파라미터를 헤맸다 | 파라미터 문제가 아니었다. **GT 를 초기값으로 주고 게이트 없이 돌리는 «정합기 자체 오차 바닥» 측정**(#48)이 한 번에 갈랐다 — 바닥이 R 0.384°/t 1.120mm 인데 초기값이 이미 0.274°/0.443mm 였다. **개선할 여지 자체가 없었다** | **후처리 단계를 튜닝하기 전에 그 단계의 «자체 정밀도 바닥» 을 먼저 잰다.** 바닥이 입력보다 나쁘면 어떤 파라미터로도 이득이 안 난다 — 스윕은 낭비다 |
| 72 | 1920×1200 캡처를 FoundationPose 에 넣자 31GB GPU 가 OOM 났다. *"고해상도를 못 쓴다"* 로 결론낼 뻔했다 | FP 내부(`h5_dataset.transform_depth_to_xyzmap`)가 crop 을 **원본 크기로 되돌리며** 가설 수만큼 warp 해서 메모리가 **원본 픽셀 수에 비례**한다. 그런데 §22 에 따르면 crop 은 어차피 **160×160 으로 리샘플**되므로 **원본 해상도는 네트워크 정확도와 무관**하다 | **자원 한계에 부딪히면 «그 자원이 정확도에 기여하는가» 를 먼저 확인한다.** 여기서는 안 했다 → `--input-scale 0.5` 로 해결(0.5 vs 0.75 결과 구분 불가). ⚠️ 축소 시 반픽셀은 `c' = (c+0.5)·s − 0.5`, depth 는 `INTER_NEAREST` |
| 73 | 광각 때문에 정합이 무효화되자 **카메라를 바꿔야 하나** 를 검토했다 | 레버는 `fx` 와 `Z` 둘뿐이고 `fx` 는 렌즈로 고정이라 **`Z` 만 남는다.** 근접을 0.40 → 0.26m 로 당기니 flange 등가지름 264 → **419px** 로 옛 조건을 회복했고 정합 이득이 **0.82× → 1.66× 로 부호가 뒤집혔다** | **«이 구성은 안 된다» 를 «이 카메라는 안 된다» 로 확대하지 않는다.** 운용 파라미터(거리·자세)를 먼저 훑는다. 그리고 내가 쓴 «선명 하한» 은 `c=1.5px` 기준의 보수값이었고 §33 은 **4px 까지 무해**하다고 이미 재 놨었다 — **자기 문서의 기존 측정을 먼저 조회할 것** |
| 74 | 더 가까이 갈수록 좋아지길래 0.18~0.24m 까지 당겼다 | **바닥이 있었다.** 정합기 자체 바닥은 계속 좋아지는데(0.163°) FP 가 다시 뒤집히고(R최대 173°) SAM3 오선택이 1 → 4 로 늘었다. 원인은 **baseline 120mm 이 거리에 비해 커지는 것** — 스테레오 미중첩 25%, 좌우 시선 벌어짐 33°, depth RMSE 3.4 → 16.8mm | **단조 개선을 외삽하지 않는다.** 근접의 이득(해상도)과 손해(스테레오 기하)는 방향이 반대라 **어딘가에 최적점이 있다** — 끝까지 밀어서 찾는다. 그리고 여기서도 **depth 중앙값은 좋아지는데 RMSE 가 터졌다**(#69 재발) |
| 75 | *"far 는 대략 pose 니 느슨한 KPI 로 충분하다"* 를 검증하려 3단계 기준을 만들었다 | **셋 다 107/120 으로 같았다.** 오차 분포가 이분법적(성공 횡 ≤4.4mm / 실패 ≥447mm, **102배 간격**)이라 임계값이 아무 역할을 안 한다. 병목은 «정밀도» 가 아니라 «다른 물체를 집음» 이었다 | **기준을 완화하기 전에 실패의 «형태» 를 본다.** 연속 분포면 완화가 듣고, 이분법이면 안 듣는다. 그리고 이분법이면 **분리가 쉽다는 뜻**이기도 하다 — 여기서는 «사전 위치 ±100mm» 가드가 13/13 을 걸러냈다 |
| 76 | 사이클 타임 예산을 «추론 시간» 으로만 계산했다 | 실제 위험은 **콜드 스타트 40초**(ONNX 세션 31.5s + FP 7.1s)였다. 실험은 120프레임에 분산돼 안 보였고, 배포는 요청당 프로세스를 띄운다 | **성능 예산은 «정상 상태» 가 아니라 «호출 단위» 로 잰다.** 배치 실험의 프레임당 평균은 1회 호출 비용을 감춘다 — 초기화·모델 로드·I/O 를 **1회 기준으로** 다시 더한다 |
| 77 | `capture_real.py` 를 Jetson 에서 처음 돌리자 `UnicodeDecodeError: 'ascii' codec can't decode byte 0xeb` 로 죽었다. 5090 에서는 100% 잘 돌던 코드다 | Jetson 에 `LANG` 이 안 잡혀 있어 파이썬 기본 인코딩이 **ASCII** 였다(PEP 538 의 C 로케일 강제 변환도 항상 걸리지는 않는다). `Path.read_text()`·`write_text()` 는 **로케일 기본 인코딩**을 쓴다. **이 저장소는 문서·주석·문자열이 전부 한국어라 이 함정에 구조적으로 노출돼 있다.** 게다가 세 곳이 순차적으로 터진다 — ① 프로파일 읽기 ② `ensure_ascii=False` 로 meta 쓰기(**모든 프레임을 저장한 뒤** 마지막에 죽어 캡처가 통째로 날아간다) ③ 한글 `print` (`UnicodeEncodeError`) | **다른 기계에서 도는 코드는 로케일을 가정하지 않는다.** 파일 IO 는 전부 `encoding="utf-8"` 을 명시하고, 진입점에서 `sys.stdout/stderr.reconfigure(encoding="utf-8")` 로 출력을 고정한다. ⚠️ **«내 기계에서 되니까» 가 검증이 아니다** — 대상 환경을 재현해서(`LC_ALL=C PYTHONUTF8=0`) 확인한다. 급하면 `PYTHONUTF8=1` 로 우회 가능하지만 **코드가 환경에 의존하는 상태는 남는다** |
| 78 | 새 PC 에서 `bash envs/bootstrap.sh` 가 33행 `envs/bin/uv: No such file or directory` 로 죽었다. 바로 위에 «uv 설치» 가 성공한 것처럼 찍혀 있었다 | **환경변수가 파이프를 건너가지 않았다.** `VAR=x curl … \| sh` 는 `VAR` 을 **`curl` 에만** 걸고, 설치 스크립트(`sh`)는 못 봐서 uv 를 기본값 `~/.local/bin` 에 넣는다 — `envs/bin/uv` 는 안 생기고 **덤으로 `~` 를 오염**시킨다(우리 최우선 원칙 위반). 옛 머신에는 uv 가 이미 있어 `if [ ! -x ]` 가 통째로 건너뛰었다 → **1년간 안 드러났다** | **«한 번 성공하면 다시 안 밟는 경로» 는 새 머신에서만 드러난다 — 그래서 새 머신 세팅 자체가 검증이다.** 실제로 같은 날 잠복 버그 4건이 한꺼번에 나왔다(uv 파이프 · `repos.lock` 이 `.gitignore` 디렉토리 제외에 먹힘 · 옵션 가중치가 종료코드 1 · `verify_semi` 홀 높이). 그리고 **설치 결과는 «성공한 것처럼 보이는 로그» 가 아니라 산출물 존재로 확인한다** — `[ -x "$UV" ] \|\|` 실패-확성 가드를 넣었다 |
| 79 | Blender 다운로드가 사내 프록시에 막혀 `HTTP 401` 이 났고, 그 바람에 **뒤의 `stereo_onnx`·`cad` venv 까지 통째로 안 만들어졌다** | `set -e` 하에서 **선택적 프리페치가 필수 단계를 죽였다.** 게다가 Blender 는 애초에 세팅에 필요 없다 — ISM **추론**은 blenderproc 을 import 조차 안 하고, 필요한 건 렌더된 템플릿(`ism_full`)이며 그건 자산 릴리스에 들어 있다. **새 CAD 로 템플릿을 다시 렌더할 때만** 필요하다 | **부트스트랩에서 «있으면 좋은 것» 과 «없으면 안 되는 것» 을 코드로 구분한다.** 전자는 `\|\| true` + 안내 메시지로 격리한다 — 안 그러면 한 항목의 네트워크 사정이 전체 세팅을 막는다. 그리고 **의존성을 넣기 전에 «어느 단계가 이걸 실제로 import 하는가» 를 확인**한다: 여기서는 생성 단계와 소비 단계가 달랐다 → `SKIP_BLENDER=1` · `docs/SETUP.md §9.1` |
| 80 | `source envs/env.sh` 를 빼먹고 러너를 돌렸더니 **ONNX 가 조용히 CPU 로 폴백**했다. 결과는 맞는데 스테레오가 수십 배 느려져 «원래 이만큼 걸리나 보다» 로 넘어갈 뻔했다 | `LD_LIBRARY_PATH` 에 `envs/cuda/lib64` 가 없으면 `libcublasLt.so.12` 를 못 찾아 `CUDAExecutionProvider` **생성에 실패하고 경고만 찍은 뒤 CPU 로 계속 간다.** 🔴 **«틀리지 않지만 쓸 수 없게 되는» 고장**이라 결과 검증으로는 절대 안 잡힌다 — 20프레임 × 거리 5대역 × 외관이면 하루가 날아간다 | **성능이 조용히 무너지는 경로는 «경고» 가 아니라 «차단» 으로 막는다.** `run_group_a.py` 가 실행 전에 `LD_LIBRARY_PATH` 를 검사해 **종료코드 2** 로 죽고, 의도적 CPU 실행은 `--allow-cpu` 로만 허용한다. 일반화: **폴백은 «있다» 는 사실보다 «조용하다» 는 사실이 위험하다** — 라이브러리가 성능 폴백을 경고로만 알리면 그 위에 우리 층의 차단을 얹는다 |
| 81 | `n30` 캡처에서 `seg_ism` 이 `RuntimeError: Input and output sizes should be greater than 0, but got input (H: 0, W: 30)` 로 죽었다. **`frame_0000` 은 통과하고 `frame_0001` 에서 스테이지가 통째로 종료**됐다. 같은 코드가 `n25` 20프레임에서는 멀쩡했다 | SAM 이 **높이 0 인 제안**을 하나 내면 ISM 의 `CropResizePad` 가 그 상자로 crop 한 뒤 빈 텐서를 `F.interpolate` 에 넣는다. **퇴화 제안이 나오냐 마냐는 장면 운(運)** 이라 대역·프레임을 바꾸면 잠복이 풀린다 — 실제로 고친 뒤 네 런 전부에서 **프레임당 1개씩** 걸러졌다 | **상류 추론 루프에 우리 입력이 그대로 들어가면, 퇴화 입력은 우리 층에서 거른다**(third_party 는 안 고친다 — 재현성·라이선스). `segment_sam6d.py` 가 `boxes` 의 폭·높이 ≥1 을 확인하고 **제외 개수를 로그로 찍는다**(교훈 #21). 일반화: **«프레임 하나의 예외가 스테이지 전체를 죽이는» 구조를 먼저 의심한다** — 20프레임 배치에서 1건 실패는 5% 손실이어야지 100% 손실이면 안 된다 |
| 82 | 거리대를 고르려고 GT-free **게이트 후퇴율**을 봤다. `n25 → n30` 에서 후퇴율이 45% → **65%** 로 올라 «n30 이 나쁘다» 로 읽혔다 | **GT 로는 정반대였다** — 같은 구간에서 ISM 경로가 12/20 → **17/20**, R 중앙 1.133 → **0.542** 로 좋아졌다. 후퇴율은 *"초기값에서 얼마나 움직였나"* 이지 *"맞나"* 가 아니다. **초기값이 좋아지면 정합이 덜 움직이고, 안 움직인 프레임도 후퇴로 세어진다** | **후퇴율은 «같은 초기값 위에서 플래그만 바꾼» 비교에만 쓴다**(A2a/A2b/A1 처럼 — §29·§31 에서 실제로 작동했다). **초기값 자체가 달라지는 비교**(거리대·분할 백엔드·카메라)에는 **원리적으로 무효**다. 그런 비교의 GT-free 근거는 **좌우 투영 일관성 + 오버레이 육안**뿐이고, 그것도 R 은 잘 못 본다(§35-2h) |
| 83 | 정합기의 **포획 반경**을 `‖Δt‖` 로 쟀다. 횡 1mm 만 흔들어도 `t 2.75mm` 가 나와 *"횡이 가장 약한 축이고 1mm 도 회수 못 한다"* 로 적었다(§35-2j) | **노름이 축을 가렸다.** 분해하니 **Z 2.70mm + 횡 0.86mm** 였고, 횡 성분은 **바닥값(0.93mm)까지 완전히 회수**돼 있었다. 평면 테두리는 Z 구속이 구조적으로 약해 어느 축을 흔들든 **Z 표류가 노름을 지배**한다. 그 상태로 «탐색폭을 넓혀도 소용없다» 는 오진이 나왔고, 축을 분해하자 **넓히면 횡 포획이 4 → 24mm 로 6배** 넓어지는 게 드러났다(§35-2k) | **벡터 오차는 «크기» 가 아니라 «축» 으로 잰다.** 자유도마다 구속 강도가 다르면(우리는 횡 ≪ Z) 노름은 **가장 약한 축의 지표**가 되고 나머지를 못 보게 한다. 교훈 #6(*"평균이 고장을 숨긴다"*)의 공간판이다 — **`t` 를 볼 때는 항상 `hypot(dx,dy)` 와 `dz` 를 따로** 낸다. ⚠️ KPI(`t ≤5mm`)도 노름이라 같은 함정이 있다: **KPI 는 판정용이고 진단용이 아니다** |
| 84 | GT 없이 z 편향을 잡으려고 «FP 추정 z» 와 «flange 마스크 안 depth **중앙값**» 을 비교하는 진단을 넣었다. 첫 실행에서 **+6.5mm 어긋남**이 나와 «FP 가 틀렸다» 로 읽힐 뻔했다 | **틀린 건 아무것도 없었다.** sim GT 로 재니 FP 는 +0.28mm 로 정확했고, **GT depth 로 재도 중앙값은 pose 원점 z 보다 −6.92mm** 였다. 원근 때문에 **가까운 쪽이 픽셀을 더 차지**하고 융기(+2mm)·홀 깔때기가 섞여서 생기는 **구조적 차이**다 — 즉 **두 양이 애초에 같은 것이 아니었다.** 그대로 뒀으면 실물 런마다 거짓 경보가 떴을 것이다 | **두 값을 비교하기 전에 «같은 양인가» 를 먼저 확인한다.** 이름이 비슷하다고(«거리» ↔ «depth») 같은 양이 아니다 — 기준점·가중·표본 영역이 다르면 **오차가 0 이어도 차이가 난다.** ★ 검증법은 **GT 를 양쪽에 넣어 보는 것**이다(교훈 #48 의 일반형): 오차가 0 인 데이터에서 차이가 남으면 그건 «편향» 이 아니라 «정의» 다. 처방은 **정의를 맞추는 것** — 여기서는 depth 에 평면을 적합해 **원점이 투영되는 시선 위에서** 평가하니 −0.81mm 로 떨어졌다. ⚠️ **새 진단기는 그 자체가 검증 대상이다** — 진단기가 낸 첫 경보를 «발견» 으로 보고하기 전에 알려진 정답에서 돌려 볼 것 |
| 85 | 파이프라인이 **결정론적인가**를 확인하려고 같은 입력을 두 번 돌리고 pose 를 비교했다. FoundationPose 가 **ΔR 0.019°**, 테두리 정합이 **0.033°** 로 나와 «비결정론» 이라고 적을 뻔했다 | **출력 파일이 바이트 단위로 동일**했다(sha256 일치). 차이는 비교 함수 `rot_deg` 가 만들어낸 것이다 — `arccos((tr−1)/2)` 는 **항등 근처에서 오차를 제곱근으로 증폭**한다. 저장된 R 은 9자리 반올림·`dR@R0` 누적으로 정확히 직교가 아니고(`\|RᵀR−I\| ~ 3e-7`), `cosθ = 1−ε` 에서 `θ ≈ √(2ε)` 가 되어 **같은 행렬을 자기 자신과 비교해도 0.03°** 가 나온다(n=240 실측: p90 **0.028°** · 최대 **0.049°**) | **비교 «대상» 보다 비교 «함수» 를 먼저 검증한다** — `f(x, x) == 0` 인지부터 본다. 공짜이고 이번엔 그 한 줄이 잘못된 결론을 막았다. 처방은 `θ = atan2(sinθ, cosθ)`(반대칭 성분에서 sinθ 를 직접 얻어 1차로 정확하다) — 자기 비교가 **정확히 0**, 0.001°·179.9° 양 끝에서 기존 식과 일치, scipy 불필요. **같은 식이 7군데 복제**돼 있어(교훈 #20) `contracts.rotation_angle_deg` 로 모으고 전부 교체했다. ⚠️ 영향 범위: 일상 비교(0.2~0.5°)는 최대 0.0025° 차로 무해하지만 **결정론 검사 · GT-초기값 검증(교훈 #48) · 0.05° 미만을 주장하는 모든 수치**는 이 잡음이 지배한다 |
| 86 | #85 를 고친 뒤 «결정론» 을 다시 확인했다. 같은 입력으로 **두 번** 돌려 바이트 동일이 나오자 *"두 스테이지 모두 완전 결정론"* 이라고 문서에 적었다 | **세 번째 런이 달랐다.** FoundationPose 는 **이분적**이다 — 두 런이 바이트 동일하기도 하고 **ΔR 중앙 0.146°·최대 0.662°** 벗어나기도 한다(cuDNN 알고리즘 자동선택 추정). `stereo_onnx` 는 **매번** 다르고(20/20), `refine_contour`(CPU)만 진짜 결정론이다. 🔴 **FP 의 재실행 잡음이 우리가 보고해 온 R 중앙값(0.19~0.45°)과 같은 자릿수**라 «설정 효과» 로 오독할 수 있었다 | **«같다» 는 표본 2개로 못 보인다 — «다르다» 만 1개로 보인다.** 부정 명제(비결정론)는 반례 하나로 증명되지만 긍정 명제(결정론)는 반복으로만 지지된다. **최소 3~4회**, 그리고 «다를 수 있는 이유» (GPU autotune·스레드)를 아는 단계는 더 많이 돌린다. ★ 실용적 처방은 «결정론인가» 가 아니라 **«재실행 잡음 바닥이 얼마인가»** 를 재는 것이다 — 그 숫자가 있어야 런 간 차이를 해석할 수 있다. ✅ 우리 A/B 대부분은 **같은 `fp_ns2` 산출물을 공유**해서 영향이 없다. **FP 를 다시 돌린 비교만** 이 바닥을 깔아야 한다 |
| 87 | GT 없이 «이 프레임만 다르다» 를 찾으려고 프레임별 지표에 **강건 z-score**(중앙값·MAD)를 걸었다 | **두 군데서 무너졌다.** ① sim 의 `valid_all` 은 값의 대부분이 정확히 1.0 이라 **MAD=0** 이 되고 z 가 **209** 로 발산했다 — «강건» 통계인데 척도가 붕괴한 것이다. ② 좌우 Δdx 는 20장 중 **6장이 −1.5~−4.6px 로 뭉쳐** 있어 그 6장이 전부 이상치로 찍혔다. 그건 «소수의 사고» 가 아니라 **«30% 가 다르게 동작한다»** 는 뜻인데, 이상치로 보고하면 «프레임 몇 장 문제» 로 오독하게 된다 | **강건 통계도 척도가 0 이 되면 안 강건하다** — 척도에 `max(MAD, IQR, 0.02·\|중앙값\|)` 처럼 **바닥을 깐다**(z 209 → 8.1). 그리고 **«이상치» 는 소수일 때만 이상치다** — 한 지표에서 25% 넘게 걸리면 그건 분포가 갈라진 것이므로 **별도 항목으로 보고**하고 처방도 다르게 한다(프레임 열기 ❌ / 조건 축 상관 보기 ✅). ★ 검증은 **알려진 정답에 대고** 한다 — GT 로 재니 플래그된 5장의 R 오차가 나머지의 **3.6배**(0.597 vs 0.168°)로 플래그가 실제로 유의미함이 확인됐다. #84 와 같은 교훈의 반복이다: **새 진단기는 그 자체가 검증 대상이다** |
| 88 | 실물에서 pose 가 하나도 안 나왔다. `diag_sheet` 의 6번 패널이 「없음」이라 «파이프라인이 실패했다» 로 읽었고, 앞 패널의 `mask_full` 이 멀쩡해 보여 «정합 단계가 문제» 라고 진단했다 | **두 겹으로 틀렸다.** ① 진짜 원인은 훨씬 앞이다 — 러너 A그룹은 `pose_fp --primary flange` 라 `mask_flange` 가 필수인데 SAM3 exemplar 가 빈 마스크를 냈고, `pose_fp` 가 프레임을 건너뛰어 **정합은 실행조차 안 됐다.** 예전에 통과했던 손 명령은 `--primary full` 이라 그 마스크를 아예 안 읽는다. ② 게다가 **같은 런의 `I1` 에는 pose 가 20개 있었다** — `diag`·`ov` 가 `A1` 이라는 **문자열을 명령에 박아** 넘기고 있어서 안 보였을 뿐이다 | **«시트가 비었다» 와 «계산이 실패했다» 는 다른 사건이다** — 진단 도구가 가리키는 경로부터 확인한다(`ls <out>/*/frame_*/pose_*.json \| wc -l` 한 줄). ★ 더 일반적으로 **진단 UI 에 산출물 경로를 상수로 박지 않는다**: 팔이 여럿인 파이프라인에서 한 팔이 죽으면 UI 가 «전부 죽었다» 로 보이게 만든다. 처방은 **실행 직전 지연 평가**(`Step.resolve()`)로 살아 있는 산출물을 고르되 **대체 사실을 로그로 남기는 것** — 조용히 바꾸면 교훈 #22(«틀린 값을 조용히 돌려주는 fallback»)가 UI 층에서 재발한다. 🔴 그리고 **계산에는 후퇴를 넣지 않았다**: `A1`(flange)과 `I1`(full)은 §22 유효 해상도가 3배 달라 **바꿔 쓸 수 있는 값이 아니다** — 자동 대체는 리포트의 t 를 런마다 다른 뜻으로 만든다 |
| 89 | GT 없이 거리를 검증하려고 «FP 추정 z» 와 «stereo depth 평면적합» 을 대조하고, 리포트에 **«두 독립 추정이 맞는다 ✅»** 라고 찍고 있었다. 실제로 sim 에서 둘이 1.7mm 안에 들어와 «거리는 문제없다» 로 읽었다 | **«독립» 이 애초에 틀린 말이었다.** 두 값의 **뿌리가 같다** — 둘 다 `Z = fx·B/disparity` 에서 나온다. `fx·B` 가 `s` 배 틀리면 둘 다 `s` 배 틀리므로 이 대조는 **캘리브레이션 축에 원리적으로 무반응**이다. 게다가 투영 크기까지 같이 스케일돼 **오버레이 윤곽이 완벽히 붙은 채로** 거리만 틀린다 — 좌우 일관성·게이트·평면 잔차 어느 것도 반응하지 않는다 | **«두 값이 맞는다» 를 쓰기 전에 «무엇을 공유하는가» 를 먼저 적는다.** 공유 인자가 있으면 그 인자에는 무반응이고, 그때 ✅ 를 찍으면 **없는 안전을 보고하는 것**이다. 처방은 ① 문구를 «다른 경로(단 `fx·B` 공유)» 로 정정 ② **`baseline` 을 안 쓰는 세 번째 관측**을 추가(`eval.scale_check` — 실루엣 크기, §35-2n-6) ③ 🔴 그래도 **`fx` 는 순수 스케일이라 어떤 내부 관측으로도 못 잡는다** → 외부 길이(줄자·§7.5c 상대 GT)가 유일하다고 명시. ⚠️ 새 지표는 **일부러 틀려서** 반응을 확인한다(#8) — ×1.2 주입 시 601mm → 507mm(참 502)로 되돌리는 것까지 봤다. 관련: #26(«같은 양인가»)의 형제 — 그쪽은 «정의가 다른 두 값», 이쪽은 «정의는 같은데 입력을 공유하는 두 값» 이다 |

# 추적 중인 항목

> 🛠 **측정 절이 아니다** — 미해결 항목. ⚠️ **옛 기하 기준으로 쌓인 목록**이다 — 현행은 `CLAUDE.md` 「★ 지금 열린 것」.

## 해결됨
- ~~distractor 하에서의 오선택률~~ → **측정됨**: 텍스트 프롬프트 45%, `select center` 로 1/40, ISM+center 0/40 (§M2 확장 §2-3).
- ~~flange 마스크 획득 경로~~ → **무관**: 투영 vs segmentation 둘 다 쓸 만하다.
- ~~flange depth 음의 bias~~ → **없었다**: n=4 의 착시. n=40 에서 부호가 뒤집힌다 (§M2 확장 §1).
- ~~다단계(근접 2차) pose~~ → **채택함(정정)**: 근접 flange **단독 재추정**이 최고다 — R 0.536° / t 0.70mm / 40/40
  (§근접 pose 재실험 ⑤). §M5 확장 §7 의 "채택 안 함" 은 **1차 초기값을 전달한 변형**에만 해당한다.
- ~~stage-2 회전 열화의 원인 = flange 의 약한 회전 구속~~ → **틀린 규정**: 테두리는 사분면별 최대 8.3mm 비대칭이고,
  현행 최선은 90° 혼동 **0/40**. 진짜 변수는 **테두리 마스크 경계 품질**이다 (§flange 의 회전 구속).
- ~~실환경 Z 오차 17mm 의 원인~~ → **D435 의 baseline 한계**: σ_disp 0.57px 는 정상 성능. `fx·B` 가
  ZED X 대비 0.23배라 1m 에서 1px = 29.7mm 가 된다. D435 는 1m 에서 KPI 만족 불가 (§실카메라 depth 오차 예산).
- ~~오염된 depth 하에서 ISM 이 SAM3 보다 불리할 것~~ → **차이 없다**: 24mm 오염에서도 far ISM 마스크가
  **40/40 픽셀단위 동일**(IoU 0.9146 불변). proposal 은 SAM(RGB)이 만들고 depth 는 순위에만 관여한다.
  두 백엔드의 실질적 차이는 여전히 **자산 관리 부담**뿐이다 (§depth 오차 주입 §7).
- ~~측면 오차 ~2mm 의 정체~~ → **해상도 한계가 아니다**: 객체 좌표계 고정 정합 한계. fx·거리로 안 준다 (§M5 확장 §1).
- ~~렌즈(fx) 상향~~ → **이득 없음**: fx 952 = 1200(둘 다 40/40), 1400 은 오히려 손해 (§M5 확장 §2).
- ~~flange 전용 ISM 템플릿~~ → **쓰면 안 된다**: 오선택 23/40. flange 마스크는 투영 또는 SAM3 참조로 (§M5 확장 §4).

## 열려 있음 (우선순위 순)

0. 🔴 **CAD-실물 형상 불일치 — 측정 완료(§20), 그러나 처방이 상관 depth 오차와 충돌한다.**
   **flange 는 테두리·중심 홀만 SEMI 규격이고, 중간부도 body 도 제조사마다 다르다**(사용자 확정).
   §20 이 그 대가를 쟀고, **결론은 원래 우려와 반대**였다:

   | 구성 | body 불일치 | flange 중간부 불일치 | 상관 depth 오차 |
   |---|---|---|---|
   | 원거리 `full` **coarse** | ❌ t 가 δ 를 1:1 통과 | — | ✅ 유일하게 버팀 |
   | 원거리 `full` **refined** | ✅ **40/40, t 1.03mm** (실측 CAD 로 1.23mm) | — | ❌ t 평균 52mm |
   | G1 근접 flange | — | ❌ **δ=2mm 부터 뒤집힘**, δ=10 에서 22/40 | ❌ 12/40 뒤집힘 |

   🔴 **남은 미해결은 "어느 위험이 지배적인가" 다.** refine 스위치가 두 위험에서 **반대 방향**을 가리키고,
   상관 depth 오차의 실측치가 없으면 결정할 수 없다 → 아래 1·M6 1순위와 같은 측정이다.
   ⚠️ **sim 은 이 축을 원천적으로 못 잡는다** — 렌더와 CAD 가 같은 메쉬라 불일치가 0 이다.
   교란·하이브리드는 **대리 측정**이고, 진짜 값은 실물 스캔(S④)에서만 나온다.
   → **rim 밴드 정합은 측정을 마쳤다(§21) — 기각이다.** 면역은 실재하지만(정의상 불일치 0) 좁힐수록
   방향 신호를 잃고(≤15mm 뒤집힘), 무엇보다 **원거리 `full`+refine 이 flange 중간부 불일치에 애초에
   둔감**하다(δ=10 에서 40/40 · t 1.09mm). **상관 depth 오차에도 개선이 없어**(§21-6) 기각이 확정됐다.
1. ★ **sim→real 도메인 갭** — 배경·재질 축은 **구현·측정 완료**(§배경·재질 randomization): ISM 경로는 40/40 유지,
   SAM3 는 참조를 배포 조건에서 다시 만들면 40/40. 남은 축은 **센서 노이즈·모션블러·자동노출·실사진**과
   실카메라 intrinsic 이다(M6). `top_flange` 외관은 요구사항에 따라 **의도적으로 고정**돼 있다.
2. ★ **표본 부족** — 최고 조합이 40/40 이지만 실패율 95% 상한은 7.5% 다. **95% 확정에 60, 99% 에 300프레임** 무결점 필요.
   randomization 런도 40프레임이라 같은 한계를 갖는다.
3. **`select center` 의 전제** — "카메라가 타깃을 겨눈다" 는 씬 규약이고 sim 이 그렇게 생성돼 **자기순환**이다.
   실환경에서는 고정 카메라 배치로 성립시키거나 다른 지정 수단(작업 지시·추적 연속성)이 필요하다.
   SAM3 exemplar 는 박스가 곧 지정이라 이 규칙이 필요 없다 — 구조적 장점.
4. ~~**참조 세트 선택 기준**~~ → **정해졌고 구현됐다**(§19): **마스크 면적 중앙값 상위 5장**(GT 불필요,
   면적 가드 1.2×). IoU 0.770 → **0.888**, 오선택 2 → **0**. 현행 `linspace` 는 random 보다도 나쁘다.
   → **`spatial_vision.cad.select_sam3_refs`** 로 구현. `build_sam3_refs.py` 는 **후보 생성용으로 유지**
   한다(사용자 지시) — 후보 세트가 남아 있어야 기준을 바꿔 다시 고를 수 있다.
   산출: `assets/obj/foup_300_semi/sam3_refs42_top5/` (고른 참조 22·38·7·19·37).
   ⚠️ 객체 1종에서만 유도됐고 **precision 포화가 전제**다 — 신규 객체는 면적↔precision 관계를 먼저 확인한다.
   **거리와 외관 분포는 무관하지 않다** — 참조는 **배포 조건(거리 + randomization)에서** 렌더해야 한다
   (§M5 확장 §5, §배경·재질 §5). 작업거리가 여러 대역이면 대역별 세트가 필요한지는 아직 미측정이다.
   회복 실험에서 거리와 외관이 **동시에** 바뀌어 기여도가 분리되지 않았다.
5. **`top_flange` 외관 고정의 대가** — SAM3 exemplar 가 randomize 안 된 부분(flange)에 달라붙는 현상이
   관측됐다(예측 픽셀의 57%가 flange, 기대치 12.7%). 참조 재생성으로 해소되지만, flange 까지 randomize 하는
   변형(요구사항 밖)이 더 나은지는 측정하지 않았다.
6. **분할 백엔드 미확정** — ISM(정확·느림·CAD 템플릿 필요) vs SAM3 exemplar(빠름·지정 불필요·참조 3장).
   **둘 다 유지하며 계속 비교한다**(사용자 지시). 배경·재질 축에서는 **둘 다 40/40** 이었다 —
   단 SAM3 는 **참조를 배포 조건에서 다시 만들어야** 그렇다. ISM 은 자산 재생성이 필요 없다(형상 템플릿).
   이 "자산 관리 부담" 차이가 지금까지 나온 가장 실질적인 구분점이다.
7. **ONNX 고해상도** — 1280×720 에서 Softmax 단일 버퍼 10.2GB OOM. 타일 추론 또는 TensorRT EP.
   ZED X 의 1920×1200 을 살리려면 선결 과제다.
8. **`--provider tensorrt`** — 코드 경로만 있고 실행 검증 안 됨.
9. **ONNX 전처리 정규화** — TAO 문서로 최종 확인(현재 ImageNet, 실용 영향 0.21px).
10. **SAM 3.1** — 체크포인트 키 접두사 불일치 + 내부 API 버그로 미적재. 다객체·속도가 병목이 되면 재검토.
11. ★ **실카메라 depth 오차의 성격 — 편향인가 산포인가** (M6 최우선). D435 실측 17mm 이 ∝Z² 이면 카메라·거리로
    해결되고, ∝Z 면 재캘리브레이션 문제이며 카메라를 바꿔도 안 낫는다. **0.5/1.0/1.5m 3점 측정**으로 지수를
    맞추는 것이 M6 의 첫 실험이어야 한다 (§실카메라 depth 오차 예산 §6).
12. ★ **실제 depth 오차의 공간 상관 길이** — 주입 실험에서 **크기보다 상관 길이가 지배**했다(§depth 오차 주입).
    iid 면 근접 flange 가 이기고 상관이 있으면 원거리 full 이 압도한다 — **노이즈 모델이 처방을 뒤집는다.**
    M6 에서 실측 오차장의 상관 길이를 재야 실험 표를 실환경에 대응시킬 수 있다.
13. **테두리 마스크 경계 품질** — 회전 정보의 3.5%가 전부 경계에 있으므로 여기가 회전 안정성의 지렛대다.
    IoU 0.98 이 왜 그 숫자인지는 설명됐지만, **경계 품질을 직접 개선하는 수단**(erosion 보정·서브픽셀 경계·
    RGB 에지 결합)은 아직 시도하지 않았다.
12. **오선택 잔여분** — 최고 조합에서는 0/40 이지만 fx1400·0.71~0.9m 구성에서는 각 1/40 이 남는다.
    `select center` 가 아닌 지정 수단(exemplar 박스·작업 지시)이 구조적으로 더 안전하다.

---

# ★★★★★ 34. ZED X 2.2mm 실카메라 기하 — **배포 구성이 «근접 단독 + 정합 + 게이트» 로 재편된다** (2026-08-11~12)

> 📐 **측정 조건** — **자산 `foup_300_semi_r2` · ZED X 2.2mm 실측 intrinsic(`fx 727.575 @1920×1200 · B 120.202mm`)** · 원거리 0.55~0.70/0.90~1.10m · 근접 0.18~0.45m · **n=120**. ★ **현행 정본.**

> **읽는 순서**: §0~§7 이 카메라 기하 재측정, **§8~§13 이 운용 제약(단일시점·10초) 반영 후의 현행 결론**이다.
> ⚠️ §5(G9+G10 융합)는 정확도로는 최선이지만 **10초 제약에 탈락**했다 — §8 에서 폐기된다.
> ⚠️ §4(«테두리 정합이 해롭다»)는 **근접 0.35~0.45m 조건의 결론**이고 **§9 에서 거리를 당기자 뒤집힌다.**

보유 카메라(D405·D435·D455·**ZED X**) 비교 끝에 **ZED X 2.2mm 단독**을 골랐고(→ `CAMERAS.md`),
Jetson NX 에 물린 **실물 카메라의 캘리브레이션을 그대로 sim 에 넣어** 전 체인을 다시 쟀다.
자산 `foup_300_semi_r2`, seed 700, 경사대 elevation 40~70°, **n=120**.

## 0. 실측 intrinsic 과 sim 재현

`pyzed` → `camera_configuration.calibration_parameters`(**rectified**), HD1200:

| | 실측 (ZED SDK) | sim `cam.json` | 차 |
|---|---|---|---|
| `fx` = `fy` | 727.5751343 | 727.5751493 | 1.5e-5 |
| `cx` | 960.49988 | 960.4998801 | 1e-7 |
| `cy` | **604.324219** | 604.3242190 | 0 |
| `baseline` | **120.201996** mm | 120.201996 | 0 |
| `disto` (rectified) | **전부 0** | (핀홀) | — |

- 프로파일은 **`assets/cam/zedx_s48560070_hd1200.json`** 에 박았다. 숫자를 복붙하지 말고 이걸 쓴다.
- 🔴 **`capture_sim --cx/--cy` 는 코너 원점 규약**이라 OpenCV 값에 **+0.5** 해서 넣는다(횡단 정리 #1).
  도움말에 못 박았다. 프로파일의 `capture_sim_args` 가 이미 보정된 값이다.
- ★★ **rectified 의 `disto` 가 0 이다** = 우리 sim 의 핀홀 모델과 동형. raw 는 `k1 0.543` 의 강한 배럴인데
  SDK 가 흡수한다 → *"왜곡·rectification 잔차는 sim 주입 경로가 없다"* 던 잔여 축이 **rectified 만
  소비한다는 조건 하에** 대부분 닫힌다.
- ⚠️ **`cy` 가 중심에서 4.32px 어긋나 있다** — 근접에서 **2.08mm** 다. 이제 sim 에 그대로 들어간다.
- ⚠️ ZED 의 cx/cy 가 코너 원점인지 픽셀 중심인지는 **문서에 명시가 없다**(0.5px = 0.24mm).
  `tools/zedx_check_pp_convention.py` 로 실물에서 판정한다. `cx_left == cx_right` 라 **depth 에는 영향 0**.

## 1. depth — 거리 단축이 실제로 작동한다

| 세트 | 거리 | `flange_core` 중앙 | `obj_core` 중앙 | **σ_disp** |
|---|---|---|---|---|
| `zx_near` | 0.35~0.45m | **1.256mm** | 0.626mm | 0.947px |
| **`zx_far`** | **0.55~0.70m** | 2.272mm | 1.351mm | 0.581px |
| `zx_far10` | 0.90~1.10m | 3.080mm | 3.006mm | 0.321px |

★ **σ_disp 0.32~0.95px 는 데이터시트가 함의하는 값과 맞는다** — ZED X 2.2mm 스펙 `<0.8% @2m`(=16mm)를
`σ_Z = Z²σ/(fx·B)` 에 넣으면 **σ_disp ≈ 0.35px** 다. 벤더 스펙과 우리 실측이 같은 물리량을 가리킨다.

## 2. 🔴 분할 — 광각·근거리에서 ISM 오선택이 급증한다

| 백엔드 · 거리 | IoU(전체) | IoU(정상) | **오선택** | recall |
|---|---|---|---|---|
| (기준) ISM `full` — r2, fx1200@1280×720, 0.8~1.2m | 0.908 | — | **1**/120 | — |
| ISM `full` @**0.55~0.70m** | 0.798 | 0.903 | **14**/120 🔴 | 0.815 |
| ISM `full` @0.90~1.10m | 0.857 | 0.894 | 5/120 | 0.900 |
| SAM3 `flange` @0.35~0.45m | **0.970** | 0.978 | **1**/120 | 0.973 |
| SAM3 `flange` @0.28~0.35m | **0.972** | 0.980 | 1/120 | 0.974 |

**HFOV 105° 광각 + 근거리**라 같은 인스턴스 distractor 가 화면에 더 많이·크게 들어오고
`select center` 가 타깃을 놓친다. 함정 #15·*"`select center` 의 전제는 자기순환"* 이 **광각에서 표면화**됐다.
SAM3 근접(exemplar)은 무영향 — **박스가 곧 지정**이라 이 문제가 구조적으로 없다.

## ★★ 3. 그런데 5시점 융합이 그 오선택을 전부 흡수한다 (안전망 **세 번째** 실례)

| 구성 | R중앙 | **R최대** | t중앙 | **t최대** | KPI |
|---|---|---|---|---|---|
| 원거리 단일 coarse @0.55~0.70 | 0.571 | **179.34** | 2.018 | **1530.4** | 107/120 |
| 원거리 단일 coarse @0.90~1.10 | 0.592 | 157.84 | 2.686 | 1557.4 | 103/120 |
| 근접 flange coarse @0.35~0.45 | 0.466 | 151.13 | 0.798 | 1601.4 | 119/120 |
| 근접 flange coarse @0.28~0.35 | 0.468 | 179.37 | **0.697** | 780.8 | 118/120 |
| **원거리 5시점 융합(하이브리드) @0.55~0.70** | **0.274** | **0.56** | 1.103 | 2.1 | **120/120** |
| 원거리 5시점 융합 @0.90~1.10 | 0.279 | 0.71 | **1.967** | 4.0 | 120/120 |
| **★ G9+G10 (융합 R + 정족수 근접 t)** | **0.274** | **0.56** | **0.443** | **0.8** | **120/120** |

- **단일 R최대 179° → 융합 R최대 0.56°.** §31(분할 오선택 1건)·§33(블러 꼬리)에 이은 세 번째다.
- ★ **거리 비교(사용자 요청)**: 0.55~0.70 이 0.90~1.10 대비 **t 를 1.78배 개선**(1.103 vs 1.967), R 은 동률.
  `fx·B` 가 0.607× 로 줄어든 손해를 **거리 단축이 되갚는다**. → **원거리 0.55~0.70m 채택.**
- ★★ **평행이동은 근접에서 받는다** — G9+G10 이 t 를 1.103 → **0.443mm (2.5배)**, t최대 2.1 → **0.8mm**.
  근접 거리는 0.28~0.35 와 0.35~0.45 가 **0.443 vs 0.445 로 동일** → 더 당길 이유가 없다.

## 🔴🔴 4. 테두리 정합이 **근접 0.35~0.45m 에서** 해롭다 — 원인은 «물체 픽셀 수»

> ★ **이 결론은 거리 조건부다.** §9 에서 근접을 **0.22~0.30m** 로 당기면 이득이 ×0.82 → **×1.66** 으로 뒤집힌다.

| 후보 (융합 초기값 대비) | R중앙 | t중앙 | 후퇴 | **이득** |
|---|---|---|---|---|
| **초기값 (융합 하이브리드)** | **0.274** | 1.103 | — | — |
| P7h 테두리+홀 | 0.299 | 1.143 | 100/120 | R ×0.92 |
| P8 홀 중심 | 0.400 | 1.269 | 68 | ×0.69 |
| **P9 홀 제외** | 0.333 | 1.235 | 35 | ×0.82 |
| P9 `--search-px` 3/4/5/6/12 | 0.324~0.354 | 1.19~1.26 | 17~45 | ×0.77~0.85 |
| G9+G10 위에 정합 (게이트 0.5) | 0.239 | **0.765** | 53 | R ×1.15 / **t ×0.58** |

**전부 이득 1.00 이하** — §29 의 언어로 *"작동 안 함"* 이 아니라 **해롭다**. τ 를 조이면 단조롭게
*"안 하는 쪽"* 으로 수렴한다(τ=0.3 → 후퇴 91~102/120, 결과 ≈ 초기값).

### ★★★ 원인 — GT 초기값 검증(횡단 정리 #48)이 정확히 잡아냈다

정합기에 **GT 를 초기값으로 주고 게이트 없이** 돌린 «자체 오차 바닥»:

| 기하 | **flange 등가 지름** | mm/px | **R중앙** | **t중앙** | KPI |
|---|---|---|---|---|---|
| r2 fx1200@1280×720, 0.35~0.50m | **413px** | 0.324 | **0.188°** | **0.132mm** | 115/120 |
| ZED X fx728@1920×1200, 0.35~0.45m | **264px** | 0.481 | 0.384° | **1.120mm** | 105/120 |
| ZED X fx728@1920×1200, 0.28~0.35m | 343px | 0.385 | 0.291° | 0.859mm | 111/120 |

- 🔴 **해상도를 2.25배 늘렸는데 flange 는 픽셀로 1.56배 작아졌다** — HFOV 105° 광각이라 물체가
  화면을 덜 채운다. **화소 수가 아니라 «물체가 차지하는 픽셀 수»가 지배한다.**
- **t 바닥이 0.132 → 1.120mm 로 8.5배** 나빠진다(픽셀 눈금 변화 1.48배보다 **초선형**).
  2mm 외곽 융기가 외곽선에서 6.2px → **4.2px** 로 붙어 능선과 실루엣이 섞이는 것이 유력한 기전이다(§33-2 와 같은 계열).
- **정합기 바닥(0.384/1.120)이 G9+G10 결과(0.274/0.443)보다 나쁘다 → 개선할 여지 자체가 없다.**
- ⚠️ 근접을 0.28~0.35m 로 당겨도(343px) 바닥이 0.291/0.859 로 **여전히 부족**하다. 0.27m 가 초점 하한이라
  더 당길 수도 없다. **이 카메라에서는 구조적으로 안 된다.**
- ⚠️ *"1920×1200 이 1280×720 보다 유리하다"* 던 예상은 **틀렸다**. 광각 렌즈가 물체 픽셀을 깎는다.

## ⚠️ 5. 다중시점 융합 구성 — **참고용. 배포 후보 아니다** (§8 에서 폐기)

```
원거리 0.55~0.70m · full · FP coarse × 5시점 → G9+G10 융합 → 테두리 정합 없음   # ← 폐기됨
```
> **R 중앙 0.274° / t 중앙 0.443mm / 120-120** (R최대 0.56° · t최대 0.8mm)

여기까지가 *"정확도만 보면 최선"* 이었다. **그런데 §8 의 두 제약(사이클 타임 10초 · 다중시점은 최후 수단)
아래에서는 쓸 수 없다** — 계산만 ~20초에 로봇 이동이 4회 더 붙는다.
★ **배포 구성은 §8~§12 를 볼 것.**

## ⚠️ 6. FoundationPose 가 1920×1200 에서 OOM 난다 → `--input-scale` 신설

```
torch.OutOfMemoryError: Tried to allocate 2.16 GiB (31.33 GiB GPU, 1.75 GiB free)
  h5_dataset.py:159 transform_depth_to_xyzmap → kornia.warp_perspective(dsize=(H_ori, W_ori))
```
FP 는 crop 을 **원본 크기로 되돌리며** 가설 수만큼 warp 한다 → 메모리가 **원본 픽셀 수에 비례**.

★ **§22 가 처방을 준다** — crop 은 `diameter × ratio` 를 **160×160 으로 리샘플**하므로 네트워크가 보는
해상도는 원본과 무관하다. `pose_fp --input-scale 0.5`(rgb·depth·mask·K 동시 축소)로 해결.
**실증**: 근접 flange coarse 가 `0.5` 에서 R중앙 0.466 / `0.75` 에서 0.485 — **구분 불가**.
- ⚠️ 반픽셀: `c' = (c+0.5)·s − 0.5`. `c·s` 로 쓰면 0.5·(1−s)px 이 어긋난다(#1 계열).
- ⚠️ depth 는 **`INTER_NEAREST`** — 평균을 내면 경계에 실재하지 않는 거리가 생긴다.

## 🔴🔴 8. 두 운용 제약이 배포 구성을 다시 뒤집는다 (사용자 확정, 2026-08-11)

1. **다중시점 융합은 «최후의 수단»** — 로봇이 원거리 5시점을 도는 비용이 크다.
   **항상 가능한 기본은 `far ×1 → near ×1 → 테두리 정합 → 게이트`** 다.
2. **전체 파이프라인 10초 이내** — 넘기는 것도 최후의 수단이다.
3. **사전에 FOUP 대략 위치를 아는 경우가 있다** → 그때는 **far 를 생략하고 near 로 직행**.

★ 그리고 **1차(far)의 역할은 정밀 pose 가 아니라 «접근 유도»** 다 — 회전이 나쁘면 버리고 t 만 써도 된다.

→ 이 제약 아래에서 §5(G9+G10)는 **탈락**하고, 아래 §11 이 배포 구성이 된다.

## ★★★ 9. 근접 거리 스윕 — **0.22~0.30m 가 최적점이고, 더 가면 다시 나빠진다**

광각(HFOV 105.7°) 때문에 물체 픽셀이 준 것이 §4 의 원인이었으므로 **거리를 당겨 되찾을 수 있는지** 쟀다.
⚠️ *"선명 하한 244mm"* 는 착란원 `c=1.5px` 기준의 보수적 값이고, §33 은 **블러 4px 까지 무해**하다고
이미 쟀다 — 그래서 그 아래까지 내려갈 수 있다.

| 근접 거리 | **flange 등가지름** | depth 중앙 | 정합기 바닥 R/t | SAM3 오선택 | **FP R최대** | 최종 KPI |
|---|---|---|---|---|---|---|
| 0.35~0.45m | 264px | 1.256mm | 0.384 / 1.120 | 1/120 | 151° | 119/120 |
| 0.28~0.35m | 343px | 0.721mm | 0.291 / 0.859 | 1/120 | 179° | 118/120 |
| **★ 0.22~0.30m** | **419px** | 0.532mm | **0.220 / 0.670** | **1**/120 | **1.40°** | **119/120** |
| 0.18~0.24m | 523px | 0.310mm | **0.163 / 0.529** | 4/120 | 173° | 116/120 |

- ★ **0.22~0.30m 에서만 FP 대실패가 0 이다**(R최대 1.40°). flange 가 커져 마스크·depth 가 좋아진 결과다.
- 🔴 **0.18~0.24m 는 정합기 바닥은 계속 좋아지는데 전체가 나빠진다** — baseline 120mm 이 거리에 비해
  커져서 **스테레오 미중첩 25% · 좌우 시선 벌어짐 33°** 가 된다. depth 중앙값은 0.310mm 로 좋아지지만
  **RMSE 가 3.4 → 16.8mm 로 꼬리가 터지고**(bias +1.82mm) SAM3 오선택도 1 → 4 로 는다.
  → **거리를 당기는 것에는 바닥이 있고, 그 바닥은 baseline 이 정한다.**
- 정합기 자체 바닥(GT 초기값)이 **등가 지름에 거의 비례**한다: 264px 0.384° → 419px 0.220° → 523px 0.163°.
  옛 기하(413px)의 0.188° 를 419px 에서 되찾았다 → §4 의 진단(«물체 픽셀 수»)이 실증됐다.

## ★★★ 10. 원거리 분할 — SAM3 exemplar 가 ISM 의 오선택을 절반 이하로 줄인다

§3 의 **ISM 오선택 14/120** 이 단일 시점 경로의 유일한 병목이었다. §19 의 «면적 중앙값 상위 5장» 선택
(GT 불필요)을 새 기하에 그대로 적용했다 — 후보 24장 → probe 분할(`--save-per-ref`) → 상위 5장.

| 원거리 분할 | 시간/frame | **오선택** | IoU(전체) | recall | **접근 KPI 통과** |
|---|---|---|---|---|---|
| ISM `full` (기준) | 1,499ms | **14**/120 | 0.798 | 0.815 | 107/120 |
| **SAM3 exemplar `n-refs 3`** | **925ms** | **8**/120 | 0.883 | 0.913 | 111/120 |
| SAM3 exemplar `n-refs 5` | 1,527ms | **5**/120 | **0.903** | 0.933 | **114**/120 |

- ★ **`n-refs 3` 이 ISM 보다 1.6배 빠르면서 오선택은 절반**이다 → 시간 예산까지 보면 **실용 최적**.
- 검출 실패가 1/120 있는데 이건 **런타임에 감지되는** 실패다(재시도).
- ⚠️ §19 는 `full` 에서 SAM3 가 ISM 을 recall 로 못 이겼다고 했다. **광각에서 뒤집혔다** — ISM 이
  0.815 로 무너졌고 SAM3 는 0.913 이다. *"어느 백엔드가 낫다" 는 기하에 딸린 결론*이다.

### 10b. ★★ 오선택은 «사전 위치» 로 완벽히 걸러진다

far 오차 분포가 **이분법적**이다 — 성공군 107건의 횡오차 **최대 4.4mm**, 실패군 13건의 횡오차
**최소 447.3mm**. **102배 간격에 중간이 텅 비어 있다.**

| 사전 위치 가드 | 성공 유지 | 실패 통과 |
|---|---|---|
| ±100mm | **107/107** | **0/13** |
| ±400mm | 107/107 | 0/13 |

**로드포트 좌표 수준(±수십 cm)만 알아도 오선택이 전부 걸러진다.** 튜닝할 상수가 사실상 없다.
⚠️ 가드는 **걸러낼 뿐 고치지 못한다** — 기각된 프레임은 재시도로 간다. 재시도를 줄이려면 §10 이 필요하다.

### 10c. far 전용 KPI 는 만들어도 통과율을 못 올린다

*"far 는 대략적 pose 니 느슨한 KPI 로 충분하다"* 를 검증했다. 근접 단계 성립 조건에서 역산한 기준
(횡 ≤80mm · 축 ≤40mm · **tilt ≤15° · yaw 무관**)으로 재면:

| 기준 | 통과 |
|---|---|
| 빡빡 (횡40·축20·tilt8°) | 107/120 |
| 권장 (횡80·축40·tilt15°) | 107/120 |
| 느슨 (횡120·축60·tilt25°) | 107/120 |
| (참고) 기존 KPI 3°/5mm | 107/120 |

**전부 같다.** 요구를 느슨하게 해도 소용이 없는 이유는 §10b 의 이분법이다 — 실패가 «약간 틀림» 이
아니라 «다른 물체» 라서 임계값으로 구제되지 않는다. **처방은 KPI 완화가 아니라 분할 교정 + 위치 가드다.**
★ 다만 **yaw 는 진짜로 무관**하다(실패 13건 중 tilt 가 큰 건 3건뿐, 나머지는 자세는 멀쩡하고 위치만 틀림).

## ★★★★★ 11. 배포 구성 (갱신) — 단일 시점

```
[A] 위치를 알 때 — far 생략
    근접 0.22~0.30m → SAM3 flange exemplar → FoundationPose(--no-stage2) → 테두리 정합(--outer-only) → 게이트 1.5°
```
> **R 중앙 0.273° / t 중앙 0.770mm / 119-120** (R최대 2.39° · t최대 6.26mm · 후퇴 14/120)
> **hand-eye 불필요 · 다중시점 불필요 · 로봇 이동 0회**

```
[B] 위치를 모를 때 — 2단계
    원거리 0.55~0.70m → SAM3 full exemplar(n-refs 3) → FP(--no-stage2) → **사전위치 ±100mm 가드**
      → (접근) → [A]
```
> 원거리는 **접근 유도 전용**(횡 ≤80mm · tilt ≤15° · yaw 무관), 최종 정확도는 [A] 가 낸다.

- 유일한 KPI 실패는 t 6.26mm 인 1프레임이다.
- **정합이 R 을 1.6배 개선한다**(0.453 → 0.273). §4 에서 «해롭다» 였던 것이 **거리를 당기자 뒤집혔다.**
- 게이트 τ=1.5° 가 3.0° 보다 낫다(후퇴 14 vs 4, R최대 2.39 vs 2.49 — τ 를 열면 나쁜 정합이 통과한다).

## ★★★★ 12. 시간 예산 — 10초 제약

실측(RTX 5090, **모델 상주** 가정):

| 단계 | 시간 |
|---|---|
| 캡처 + Jetson→5090 전송 (1920×1200 PNG ×2 ≈ 14MB) | ~0.10s |
| stereo FoundationStereo ONNX `--scale 0.5` | **0.81s** |
| SAM3 flange exemplar (근접) | **0.63s** |
| SAM3 `full` exemplar `n-refs 3` (원거리) | 0.93s |
| ISM `full` (원거리) — 대조 | 1.50s |
| FoundationPose `--no-stage2` 근접 / 원거리 | **0.95 / 1.02s** |
| 테두리 정합 + 게이트 | **0.09s** |

| 파이프라인 | 계산 | 로봇 이동 | 판정 |
|---|---|---|---|
| **[A] 근접 단독** | **2.6s** | 0회 | ✅ 여유 3.8배 |
| **[B] far×1 → near×1** | **5.4s** | 1회 | ✅ 여유 1.9배 |
| (참고) far×5 융합 | ~20s | 5회 | 🔴 초과 |

### 🔴 12b. 진짜 위험은 계산이 아니라 **콜드 스타트 40초**

```
세션 준비 31.5s   ← stereo_onnx (ONNX Runtime CUDA EP, 동적 shape 그래프 최적화)
초기화    7.1s   ← pose_fp (FoundationPose / nvdiffrast·warp 커널 컴파일)
```
현재 아키텍처는 **「스테이지 = 프로세스, 통신 = 디스크」**(venv 가 달라서)라 **pose 요청마다 프로세스를
띄우면 매번 40초**다. 실험에서는 120프레임에 분산돼 안 보였다(횡단 정리 #9 가 경고한 그것).
→ **venv 별 상주 서버 + IPC 가 배포 선결과제**다. `PIPELINE_PLAN.md` 의 `pipeline.py` 미구현 항목이
**성능 요구사항으로 승격**된다. 보조 수단: ONNX `optimized_model_filepath` 캐시 · TensorRT EP 엔진
캐시(코드 경로만 있고 미검증) · 동적 shape → 고정 shape.

### 12c. 속도 최적화 — **`--no-stage2` 만 채택**

| 변경 | FP ms | R중앙 | **R최대** | t최대 | KPI |
|---|---|---|---|---|---|
| 기준 (stage2 · iter5 · scale 0.5) | 1054 | 0.304 | **1.80** | 6.16 | 119/120 |
| **★ `--no-stage2`** | **952** | **0.273** | 2.39 | 6.26 | **119/120** |
| + `--est-iter 3` | 652 | 0.285 | **89.91** 🔴 | 61.5 | 117/120 |
| + `--est-iter 2` | 521 | 0.272 | **78.63** 🔴 | 58.7 | 118/120 |
| + stereo `--scale 0.35` | 942 | 0.336 | **179.98** 🔴 | 2.23 | 119/120 |
| + stereo `--scale 0.25` | 952 | 0.446 | 2.15 | 2.71 | 120/120 |

- ★ **`--no-stage2` 는 100ms 를 아끼면서 R 중앙값까지 개선**한다(§27-7 재현 — 근접 flange 는 refine 이
  R·t 를 둘 다 악화시킨다). **공짜 이득이라 무조건 켠다.**
- 🔴 **나머지는 중앙값은 멀쩡한데 최대값이 터진다**(R최대 1.8° → 90~180°). 횡단 정리 #68 그대로다.
  **10초 예산에 여유가 있으므로 살 이유가 없다.**
- 원거리도 `--no-stage2` 채택 — `refined` 가 t 를 1.60 → 1.06mm 개선하지만 **접근 허용치가 ±80mm 라
  통과율이 111/120 로 동일**하다. 100ms 만 아낀다.
- ⚠️ **§32 의 «refine on/off 판정 절차» 는 폐기되지 않았다.** `--no-stage2` 는 **깨끗·정확 조건의 기본값**이고,
  §32 는 *"coarse·refined 초기값을 둘 다 만들어 **게이트 후퇴율이 낮은 쪽**을 쓴다"* 는 **진단 절차**다.
  실물에서 정합 후퇴율이 급등하면(=CAD 불일치 의심) `--no-stage2` 를 빼고 한 번 더 돌려 비교한다 —
  **비용은 100ms + 런 1회**. 두 문장은 «기본값» 과 «이상 시 진단» 으로 층이 다르다.

## 13. 실환경 입력 계약 — **이미지 2장이 전부다**

```
frame_XXXX/
  left.png    ← sl.VIEW.LEFT  (rectified · PNG 무손실 · BGR8)
  right.png   ← sl.VIEW.RIGHT
  cam.json    ← 카메라 프로파일에서 나오는 고정값 (fx fy cx cy baseline_mm width height)
```
`depth_gt.npy` · `mask_*.png` · `pose_gt.json` 은 **sim GT 전용**이고 실물에는 없어도 된다
(대신 `eval_*` 를 못 돌린다 — 실환경 절대 오차 측정 불가라는 기존 제약 그대로).
도구 2종:
- **`spatial_vision.stages.capture_real`** — Jetson 에서 ZED X 를 직접 찍어 위 3파일을 낸다.
  `sl.VIEW.LEFT/RIGHT`(rectified) · PNG 무손실 BGR8 · `DEPTH_MODE.NONE` · `--warmup` 으로 AE 수렴 대기 ·
  프레임별 exposure/gain 을 meta 에 기록. 🔴 **`--cam <프로파일>` 대조에 실패하면 non-zero 로 죽는다** —
  해상도 모드나 개체가 바뀌면 SAM3 참조·ISM 템플릿이 전부 무효인데 산출물로는 안 보이기 때문이다.
  의존성은 `pyzed`·`numpy`·`cv2` 뿐(Jetson 에 우리 venv 가 없다).
- **`tools/make_frame_from_zed.py`** — 이미 찍어 둔 좌/우 PNG + 프로파일 → 프레임 디렉토리.
  해상도 불일치와 JPEG 입력을 거부한다.

⚠️ 검증: `pyzed` 를 모사해 **카메라 없이 종단 확인**했다 — capture_real → stereo → SAM3 → FP →
테두리 정합까지 돌아 `pose_refined.json` 이 나오고, 프로파일 불일치는 종료코드 1 로 실패한다.

★ **한 벌의 데이터(far 1장 + near 1장 = PNG 4장)에서 아래가 전부 오프라인으로 나온다** — 실물 테스트는
**자세를 다시 잡지 않고** 후보를 순차로 돌려 비교하면 된다:
분할 3종(ISM / SAM3 n3 / SAM3 n5) × pose 2종(coarse / refined) × 조합 3종(G0 / G1 / G9) ×
정합 4종(끔 / `--outer-only` / `+--keep-hole-mm` / `+--hole-center-mm`) × 게이트 τ.
⚠️ **G0·G9 는 far→near 카메라 변환(로봇 kinematics)이 필요**하고 **G1 은 필요 없다.**
⚠️ **real 에는 GT 가 없다** → 서열화는 GT-free 지표로만: **게이트 후퇴율** · G0↔G1 불일치율 ·
좌우 투영 일관성 · 파지 성공률.

🔴 **현재 실험 환경에는 로봇이 없다**(사용자 확정 2026-08-12) — 카메라 + FOUP 뿐이고 손으로 움직인다.
그래서 위 «far 1장 + near 1장» 조차 **1 사이클 촬영 2회**라 후순위이고, **G0·G9 는 원천적으로 불가**다
(카메라 상대 pose 가 아예 없다). **지금 돌릴 수 있는 것은 «근접 1장» 또는 «원거리 1장» 단독 경로**이고,
거기서 분할 3종 · pose 2종 · 정합 4종 · 게이트 τ 는 **추가 촬영 0** 으로 전부 붙는다.
→ 실행 목록은 `PIPELINE_CATALOG §9.1★c`, 계통 편향 측정은 `§7.5c 상대 GT`.

## 7. 한계

- **sim→sim 이다.** 바뀐 것은 카메라 기하뿐이고 실사진·실조명·실물 형상은 여전히 미측정이다.
- ⚠️ §9 의 근접 최적점(0.22~0.30m)은 **로봇 동선상 접근 가능한지 미확인**이다. ZED X 는
  163.4×31.8×36.7mm 라 0.25m 접근이면 하우징이 FOUP 상부 공간을 상당히 차지한다.
- ISM 오선택 14/120 은 **distractor 구성(같은 FOUP 3개)에 의존**한다. 실환경 배치가 다르면 값이 달라진다.
- G9+G10 의 시점 간 상대 pose 는 **GT 프록시**다.
- 근접 0.28~0.35m 는 `zx_far` 와 **카메라가 짝지어져 있지 않다**(§27-6 과 같은 한계).

## 재현 (§34)

```bash
OBJ=assets/obj/foup_300_semi_r2
ZED="--width 1920 --height 1200 --fx 727.5751343 --fy 727.5751343 \
     --cx 960.99988 --cy 604.824219 --baseline-mm 120.201996"   # cx,cy 는 +0.5 (코너 원점)
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda --out runs/zx_far \
    --frames 120 --seed 700 $ZED --distance-m 0.55 0.70 --elevation-deg 40 70 $APP $CLUT
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda --out runs/zx_near \
    --frames 120 --seed 700 $ZED --distance-m 0.35 0.45 --elevation-deg 40 70 $APP $CLUT
envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx --in runs/zx_far --out runs/zx_far_st \
    --scale 0.5 --model weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx
# ⚠️ SAM3 참조는 **거리 종속** — 새 기하에서 재생성
envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs --from runs/zx_ref_near --obj $OBJ \
    --n 3 --target flange --out-name sam3_refs_flange_near_zx
# ⚠️ FP 는 --input-scale 0.5 필수 (없으면 OOM)
envs/pose/bin/python -m spatial_vision.stages.pose_fp --in runs/zx_far --out runs/zx_far_pose \
    --input-scale 0.5 --obj $OBJ --masks runs/zx_far_ism --depth stereo --depth-dir runs/zx_far_st \
    --flange-mask-from pose
# ★ 배포 구성
envs/pose/bin/python -m spatial_vision.eval.fuse_pose --near runs/zx_near --far runs/zx_far \
    --near-pred runs/zx_near_flonly --far-pred runs/zx_far_pose \
    --pred-name pose_coarse.json --pred-name-t pose_refined.json --mode g9g10 --n-views 5 \
    --out runs/zx_near_g9g10
# 정합기 자체 바닥 확인 (횡단 정리 #48) — 정합을 켤지 말지는 이걸로 판단한다
envs/pose/bin/python -m spatial_vision.eval.fuse_pose --near runs/zx_near --near-pred runs/zx_near \
    --pred-name pose_gt.json --mode jitter --jitter-deg 0 --jitter-mm 0 --out runs/zx_init_gt
envs/pose/bin/python -m spatial_vision.stages.refine_contour --in runs/zx_near --pose-dir runs/zx_init_gt \
    --pose-name pose_init.json --obj $OBJ --fix-z --outer-only --out runs/zx_gtinit
```

# ★★★ 35. A그룹 실행 도구 — 러너 + **좌우 투영 일관성** (2026-08-12)

로봇이 없어 «촬영 1회» 파이프라인만 돌릴 수 있게 되면서(§34-13 · `PIPELINE_CATALOG §9.1★c`),
**촬영 한 벌의 값어치를 최대화하는 도구**를 먼저 만들었다. 정확도 결과가 아니라 **실행 인프라**다.

## 35-1. `spatial_vision.eval.lr_consistency` — GT 없이 pose 를 채점한다

실환경에는 GT 가 없다. 기존 GT-free 지표 중 **게이트 후퇴율**은 *"폭주했는가"* 만 말하고
*"맞는가"* 는 못 말한다 — 계통 편향은 이동량에 안 걸린다(횡단 정리 #64). 그 빈틈을 메운다.

**정합은 왼쪽 이미지만 보고 한다** → 같은 pose 를 오른쪽에 투영한 결과는 **독립 관측**이다.
좌·우 각각에서 실루엣 잔차를 재고 그것을 설명하는 2D 평행이동 `(dx, dy)` 를 Huber 로 푼 뒤,
`Δdx = dx_R − dx_L` 을 깊이로 환산한다 — `dz = −Z²·Δdx/(fx·B)`. `dz > 0` = 모델이 더 멀다고 추정.

**부호·감도 검증** (`--z-shift-mm`, `runs/zx_near` GT pose 에 Z 를 일부러 주입, 3프레임):

| 주입 | frame_0000 | frame_0001 | frame_0002 |
|---|---|---|---|
| **0mm** | −1.18 | −0.91 | −2.55 |
| **+5mm** | **+4.40** | +0.03 | **+2.94** |
| **−5mm** | **−4.51** | −1.20 | **−6.27** |

- ✅ **부호가 맞다.** 5mm 급 Z 오차에 확실히 반응한다.
- 🔴 **절대값을 쓰면 안 된다** — 주입 0 에서도 `dz ≈ −1~−2.5mm` 의 **기준선 편향**이 있다.
  융기 라운드가 계단이 아니라 밝기 기울기를 만들어 관측 edge 가 참 실루엣에서 밀려 있기 때문이다
  (`residuals_at` 이 원래 재던 값). **이 편향은 모든 변형에 똑같이 실리므로 변형 간 비교로는 상쇄된다.**
- 🔴 **프레임 하나의 분해능이 ±1~2mm 급**이고 `frame_0001` 처럼 반응이 죽는 프레임이 있다
  (법선 분포 조건수가 나쁜 시점). **≥10~20 프레임의 중앙값**으로만 서열화한다 — 러너가 강제한다.
- ⚠️ 용도는 *"A1 과 A3 중 어느 쪽이 오른쪽 이미지와 더 맞는가"* 이지 *"오차가 몇 mm 인가"* 가 아니다.

## 35-2. `tools/run_group_a.py` — 촬영 1벌 → A1~A4 + GT-free 리포트

`st → seg → fp_ns2 / fp_s2 → {A1, A2a, A2b, A4} → lr×5` 를 4개 venv 를 오가며 subprocess 로 돌리고
`report.md` 를 낸다. **멱등**(산출물 있으면 건너뜀, `--force`/`--only` 로 제어), 프레임 레이아웃이
`frame_XXXX/` 가 아니면 **거부**한다(`pose_fp --depth-dir` 경로 규약과 어긋나면 조용히 틀린 depth 를 읽는다).

⚠️ **이 절은 최초판(2026-08-13)이다.** 이후 러너가 상당히 커졌다 — 아래 하위 절이 정본이다:
`--ism`(I그룹 `seg_ism`·`fp_ism`·`I1`·`I3`) **§35-2g** · 오버레이 **§35-2b** · 진단시트/추이 **§35-2c** ·
통계 한 벌 **§35-2d** · 참조 시트 **§35-2e** · **결과 산출물 6종 §35-2n**(겹치기·분할+pose·신호등·눈금자·cam 점검·실루엣 거리) ·
**실험 노트·거리 대조 §35-2l** ·
**「여기부터 보라」·「다음에 무엇을」 §35-2l-5** · **결정론 §35-2l-6** · **「이 값이 상이한가」 §35-2l-8**.
현재 산출물은 `report.{md,json}` · `run_meta.json` · `diag/` · `overlay/` · `stats/` · `lr/` · `worst/` 다.

**스모크 — `runs/zx_n25` 3프레임에서 GT 파일을 지우고**(= 실환경과 같은 입력 3개뿐) 전 체인 **83.9초**
(ONNX·SAM3·FP 콜드 스타트 전부 포함):

| 변형 | 게이트 후퇴 | 대응점 | rms px | 이동 ° 중앙/최대 | 좌우 \|Δdx\| px |
|---|---|---|---|---|---|
| A3 정합 off | — | — | — | — | 0.294 |
| **A1 홀 제외 (배포본)** | **0/3** | **1,740** | **0.615** | 0.42 / 1.25 | **0.221** |
| A2a 홀 윤곽 (규격부) | 1/3 | 13,630 | 1.839 | 0.97 / 7.85 | 1.792 |
| A2b 홀 중심 | 2/3 | 14,316 | 1.564 | 1.78 / 3.36 | 0.360 |
| A4 refine 초기값 | 1/3 | 1,740 | 1.522 | 1.34 / 1.93 | 0.681 |

- ✅ **§31 을 그대로 재현한다** — 대응점 A2a 13,630 / A1 1,740 은 §31 의 13,890 / 1,701 과 같고,
  홀을 쓰는 구성만 후퇴하는 패턴도 같다. 러너가 기존 결론을 왜곡하지 않는다는 확인이다.
- ✅ 촬영 진단도 맞다 — flange 등가지름 **376px**(목표 419 의 0.90×), FP 추정 거리 **272mm**(최적 220~300).
- 🔴 **판정 문구를 한 번 고쳤다** — 초판은 «홀 윤곽·중심이 둘 다 폭증» 을 *"최상면 개구가 CAD 와 다르다"*
  로만 읽었는데, **이 데이터는 CAD 가 정확한 sim** 이다. 같은 패턴이 §31 의 **홀 융기 깔때기**에서도 난다.
  → 러너는 이제 **두 원인을 나란히 제시하고 «처방은 둘 다 홀 제외로 같다»** 고 말한다.
  ⚠️ 구분은 캘리퍼 값어치에만 영향이 있다 — **융기가 원인이면 개구를 재도 안 돌아온다.**

## ★★ 35-2g. `--ism` — SAM-6D ISM 을 **pose 경로에** 붙였다 (I그룹) (2026-08-17, 사용자 요청)

지금까지 러너에서 ISM 은 **진단 전용**이었다(`seg_full`, pose 에 안 쓰임). 사용자 요청으로
**I그룹 = CAD 템플릿 단독 경로**를 pose 까지 잇는다. **추가 촬영 0 · 플래그 하나.**

```
seg_ism   segment_sam6d --target full --select score    ← SAM3 비의존
fp_ism    pose_fp --primary full --no-stage2 --masks seg_ism
I1        refine_contour --outer-only --gate-deg 1.5    ← A1 과 정합 조건 동일
I3        정합 off (= fp_ism/pose_coarse.json)          ← I1 의 이득 분모
```

⚠️ **이름을 `I` 로 쓴다** — `PIPELINE_CATALOG §9.1★c` 의 **B그룹(원거리)에 이미 B1·B3 이 있다**
(B1 분할 백엔드 3종 / B3 원거리 정합 반증). 여기 I1·I3 은 **근접·같은 촬영**에서 A1·A3 과
짝을 이루는 것이라 별개다.

🔴 **목적은 «어느 쪽이 정확한가» 가 아니라 «도메인 갭이 어디에 오는가» 다** (사용자 근거).
**SAM3 참조는 sim 렌더**라 실사진과 갭이 있을 수 있고, **ISM 템플릿은 CAD 형상**이라 그 축이 없다.
`RESULTS.md` 의 모든 수치가 sim→sim 이고 **남은 축이 실사진뿐**인 상황에서, 두 백엔드를 나란히
돌리면 그 축이 **결과 차이로** 드러난다. 그래서 두 경로가 **독립**이어야 한다:

- `--select score`(ISM 자체 점수)를 쓴다. 진단용 `seg_full` 처럼 **SAM3 마스크를 exemplar 로 받으면
  비교가 성립하지 않는다.** `--select center` 도 금지다(교훈 #15: 파편·배경을 집는다).
- A그룹과 **stereo depth 만 공유**한다. 분할도 pose 도 따로 간다.
- 정합·게이트는 **A1 과 똑같이** 준다(`--outer-only`, τ=1.5°). 앞단 차이만 남기기 위해서다.

⚠️ **A1 ↔ I1 은 분할뿐 아니라 pose 메쉬도 다르다** — I1 은 `--primary full`(`full.ply`)이고
A1 은 `--primary flange`(`top_flange.ply`)다. **ISM 은 `full` 만 쓸 수 있다** —
flange 전용 ISM 템플릿은 오선택 23/40 으로 이미 기각됐다(flange 만 떼면 형상 변별력이 사라진다).
그래서 리포트는 **방향만** 말하고 «분할 백엔드의 차이» 로 단정하지 않는다.

★ **ISM 템플릿은 거리 무관이다** — `ism_full/` 은 CAD 렌더라 거리대마다 다시 만들 필요가 없다.
**SAM3 참조와 정확히 반대 성질**이고(거리 종속, §34-6), 이것이 자산 관리 부담의 실질적 차이다.
🔴 **«자산이 거리 무관» 을 «성능이 거리 무관» 으로 읽으면 안 된다** — `§35-2h` 에서 ISM 경로가
0.22~0.30m 12/20 → 0.28~0.35m **17/20** 으로 갈렸다. 템플릿은 `full` 전체 형상이라 **물체가 화면
밖으로 잘리면 어느 제안도 안 맞는다.** 자산은 재생성이 필요 없어도 **거리대 선택은 여전히 필요**하다.

리포트 판정 (GT-free):

| 조건 | 읽는 법 |
|---|---|
| `I1` 좌우 \|Δdx\| < `A1` × 0.8 | 🔴 **SAM3 참조의 도메인 갭이 실재한다** → 실사진 참조 재생성 / ISM 채택 |
| `I1` > `A1` × 1.25 | ✅ sim 참조가 실물에 전이됐다 → 배포본 [A] 유지 |
| 그 사이 | ⚠️ *"갭이 없다"* 가 아니라 *"이 표본으로 못 가른다"* |

## ★★★ 35-2h. 「가짜 실물」 전 체인 검증 — ISM 포함 · **거리 2대역** (2026-08-17, n30 추가 2026-08-18)

sim 캡처에서 **`left.png`·`right.png`·`cam.json` 셋만 남긴 사본**으로 전 체인을 돌렸다. GT 를 «지운» 게
아니라 **애초에 안 준다** — 지우기만 하면 *"있으면 쓰고 없으면 만다"* 는 코드를 못 잡는다.
그리고 sim 이므로 **원본 GT 로 사후 채점**할 수 있다. 실환경에서는 불가능한 검사다.

조건: `foup_300_semi_r2` · ZED X 기하 · `--elevation-deg 35 70` · **n=20** · **seed 303**
(참조 세트는 seed 101 → 자기 참조 검증의 순환을 피한다) · 전 체인 **4분 24초** · 몸체 `black`/`orange`.
**거리만 바꾼 통제 비교** — `n25` 0.22~0.30m ↔ **`n30` 0.28~0.35m**. seed 가 같아 방위·고도가 동일하다.

**GT 대조 (R중앙° / t중앙mm · KPI, KPI = R≤3° ∧ t≤5mm)**

| 구성 | `black` n25 | **`black` n30** | `orange` n25 | `orange` n30 |
|---|---|---|---|---|
| SAM3 → FP `flange` coarse (A3) | 0.598 / 1.047 · **20/20** | 0.746 / 1.030 · **20/20** | 0.535 / 0.679 · **20/20** | 0.604 / 0.707 · **20/20** |
| **+ 테두리 정합 (A1)** | 0.377 / 1.356 · 19/20 | 0.738 / 1.111 · 19/20 | **0.225 / 0.729 · 20/20** | 0.312 / 0.980 · 19/20 |
| + 정합 `--fix-z` | 0.971 / 1.224 · 20/20 | 0.746 / 1.095 · **20/20** | 0.318 / 0.815 · 20/20 | 0.415 / 0.860 · **20/20** |
| ISM → FP `full` coarse (I3) | 1.133 / 4.260 · 12/20 | **0.542 / 3.132 · 17/20** | 3.395 / 24.30 · 5/20 ⚠️무효 | 2.604 / 15.81 · 4/20 ⚠️무효 |
| + 테두리 정합 (I1) | 0.848 / 4.528 · 10/20 | 0.677 / 3.289 · **18/20** | 3.395 / 24.30 · 6/20 ⚠️무효 | 2.604 / 15.81 · 4/20 ⚠️무효 |

- ✅ **파이프라인은 정상 동작한다.** `orange` n25 의 SAM3 경로가 **R 0.225° / t 0.729mm · 20/20** 으로
  §34-11 배포 구성 [A](R 0.273 / t 0.770 · 119/120)를 재현한다.
- ★ **정합 이득이 몸체 외관에 달렸다** — `orange` 는 R 0.535 → **0.225 (2.4배)** 이고 t 대가가 없다.
  `black` 은 R 0.598 → 0.377 인데 **t 최대가 10.1mm 로 터진다**(KPI 이탈 1). 몸체와 flange 가 같은
  검정이면 **테두리에 밝기 경계가 없다** — 정합이 쓰는 바로 그 신호다(§35-2f 의 «black 최난이도» 의 pose 측 귀결).
  ★ **갱신 — 「이득이 작다」가 아니라 「0.7mm 안쪽으로 계통 편향된다」다** → **§35-2i**.
- ★★★ **ISM 은 «근접에서 나쁘다» 가 아니라 «너무 가까우면 나쁘다» 였다** (n30 추가로 갱신).
  `black` 에서 **12/20 → 17/20**, R 중앙 1.133 → **0.542** 로 뛴다. **그 구간에서 ISM 의 R 이 SAM3
  flange 경로(0.746)를 이긴다.** 초판의 *"근접 정확도가 구조적으로 낮다"* 는 **R 에 대해서는 철회**한다.
  ★ **다만 t 는 그대로 3배 나쁘다**(3.13 vs 1.03mm) — §22 의 유효 해상도(`full` 4.34 / `flange`
  1.38 mm/px = **3.16배**)가 예측하는 값이고 **거리를 바꿔도 안 변한다**(A5: crop 이 `diameter × ratio`
  라 거리 무관). → **ISM 은 회전이 강하고 평행이동이 약하다.** 교차검증용으로는 오히려 좋은 성질이다.
- ★★ **거리 의존의 정체 = 화면 밖으로 나간 형상.** GT pose 로 `full.ply` 정점을 투영해 쟀다:

  | | 화면 밖 정점 비율 중앙 | 최대 | 온전한 프레임 |
  |---|---|---|---|
  | n25 (0.22~0.30m) | **1.7%** | 5.9% | **0/20** |
  | n30 (0.28~0.35m) | 0.7% | 3.0% | 2/20 |

  ISM 은 **`full.ply` 전체 형상**으로 대조하므로 물체가 잘리면 어느 제안도 템플릿과 안 맞는다.
  SAM3 `flange` 경로는 이 축에 노출되지 않고 실제로 두 대역 차이가 거의 없다(0.598↔0.746).
  ⚠️ **상관이지 인과 증명이 아니다** — 거리도 함께 바뀌었다. 가르려면 «조준점을 몸체 중간으로 내려
  같은 거리에서 잘림만 없앤» 캡처가 필요하다.
  🔴 **잘림은 거리가 아니라 «원점 규약» 이 만든다** — pose 원점이 flange **상면** 중심이고 카메라가
  그 점을 겨누는데 몸체는 아래로 344mm 뻗어 있다. 그래서 잘리는 변은 **항상 아래쪽 하나**다.
  실물에서 «30cm 에 전체가 들어온다» 면 조준점이 더 낮은 것이다 — 배포 시 맞춰야 할 축이다.
- 🔴🔴 **`orange`·`clear` 런으로는 `full` 경로를 «평가할 수 없다»** — §35-2f 는 *"`mask_full`·`depth_gt`
  를 GT 로 쓰면 안 된다"* 까지 적었는데 **더 강한 진술이 필요하다.** seed 가 같아 `pose_gt` 는 소수점까지
  같은데(기하 통제 성립) `mask_full` 이 **886,864 → 152,506 화소**로 몸체가 통째로 사라지고 `depth_gt`
  중앙이 **518 → 623mm** 로 배경을 본다. RGB 자체도 cutout opacity 로 렌더돼 스테레오 정합에
  물리적이지 않다. **표의 `orange` ISM 을 «반투명 FOUP 에서 ISM 이 무너진다» 로 읽으면 안 된다** —
  sim 렌더 결함이다. 그 축의 실제 답은 **열린 항목 #1**(실물 반투명에서 수동 스테레오가 뚫리는가)이다.
- ★ **그리고 그 실패는 «분할» 이 아니다** (2026-08-18 에 갈랐다). 처음에 프레임 하나(`n25 orange`
  `frame_0010`)를 보고 *"ISM 이 몸체 앞 경사면 파편을 집었다"* 고 진단했는데 **20프레임 전체로는 틀렸다**:
  GT `mask_flange`(반투명에서도 유효한 유일한 GT)에 대한 **flange recall 중앙 0.998**, recall<0.5 인
  프레임은 n25 6/20 · n30 3/20 뿐이다. **마스크가 정상(recall 1.000 · 면적 62만)인데도 t 12~22mm 로
  틀리는 프레임이 다수**다 → 원인은 `--primary full` 이 의존하는 **몸체 depth** 다.
  ⚠️ 한 프레임의 진단을 런 전체로 일반화하면 안 된다(횡단 정리 #14 의 재발형).
- ⚠️ **GT-free 지표의 한계가 실측으로 드러났다** — 리포트는 좌우 \|Δdx\|(1.66→2.83px)로
  *"A3 정합이 해롭다"* 고 판정했는데 GT 로 보면 **절반만 맞다**: t 는 나빠졌지만 **R 은 1.6배 좋아졌다.**
  **좌우 투영 일관성은 t 에 민감하고 R 은 잘 못 본다.** 실물에서 이 지표 하나로 정합 채택을 정하면
  회전 이득을 놓친다 — **오버레이 육안 검사와 함께** 봐야 한다.
- 🔴🔴 **게이트 후퇴율로 거리대를 고르면 안 된다** (n30 에서 드러났다). ISM 이 12/20 → 17/20 으로
  좋아진 바로 그 구간에서 **후퇴율은 45% → 65% 로 올랐다.** 후퇴율은 *"초기값에서 얼마나 움직였나"*
  이고 초기값이 좋아지면 덜 움직인다 — **정확도와 반대로 갈 수 있다.** → 횡단 정리 #82.

  | | A1 후퇴 / lr \|Δdx\| | I1 후퇴 / lr \|Δdx\| |
  |---|---|---|
  | n25 black | 55% / 2.83px | 45% / 2.74px |
  | n30 black | 70% / 1.35px | **65% / 1.53px** |
- ⚠️ 재현: `strip_gt.py`(입력 3개만 복사) → `run_group_a.py --ism --preset n25black|n30black|…`
  → `eval.eval_pose --gt <원본캡처> --pred <out>/A1 <out>/A1z <out>/I1 <out>/I1z`.
  `--fix-z` 계열(`A1z`·`I1z`)은 러너 인자가 아니라 **`refine_contour` 를 따로 한 번 더** 돌린 것이다
  (`--fix-z` 는 러너에서 전역 플래그다).
  🔴 **`eval_pose` 표는 평균**이다(§25-1b) — §34-11 의 중앙값과 나란히 놓기 전에 `metrics_pose.json`
  의 `frames[]` 에서 중앙값을 다시 내야 한다. 초판에서 실제로 이 실수를 했다.
- 🔴 **n30 첫 실행은 `seg_ism` 이 죽어서 실패했다** — SAM 이 높이 0 인 제안을 하나 내면 ISM 의
  `CropResizePad` 가 `F.interpolate` 에서 터진다(`input (H: 0, W: 30)`). **frame_0001 에서 스테이지
  전체가 종료**됐다. `segment_sam6d.py` 에서 퇴화 제안을 거르도록 고쳤다 → 횡단 정리 #81.
- 산출물: `runs/fakereal_A`·`fakereal_oA`(n25) · `runs/fakereal30A`·`fakereal30oA`(n30) ·
  원본 캡처 `runs/fakereal_d25{,o}`·`runs/fakereal_d30{,o}`.

## ★★★ 35-2i. 정합기 자체 편향 — **«black 은 이득이 없다» 가 아니라 «0.7mm 안쪽으로 계통 편향된다»** (2026-08-18)

§35-2h 의 `black` 결과(정합 이득 거의 없음, t 최대 10.1mm)를 *"대비가 없어서"* 로만 적어 뒀는데,
**GT 초기값 검증**(횡단 정리 #48)으로 다시 재니 **부호와 크기가 나왔다.** 게이트는 끄고 돌린다.

```bash
refine_contour --in runs/fakereal_d30 --pose-dir runs/fakereal_d30 --pose-name pose_gt.json \
               --obj assets/obj/foup_300_semi_r2 --mesh top_flange.ply --outer-only --out …_gtstart
```

| 조건 (n=20) | GT 출발 R중앙 / 최대 | t중앙 / 최대 | **`gt_bias_px`** |
|---|---|---|---|
| n25 `orange` | **0.177°** / 1.284 | 0.69 / 5.11mm | **−0.04px** |
| n30 `orange` | 0.251° / 1.803 | 0.93 / 9.74mm | −0.35px |
| n25 `black` | **2.040°** / 5.658 | 2.92 / 9.17mm | **−2.04px** |
| n30 `black` | 1.575° / 4.465 | 4.26 / 12.71mm | **−2.16px** |

- ★★★ **갈리는 축은 거리가 아니라 몸체 외관이다.** `orange` 는 두 대역 모두 바닥이 0.18~0.25° 로
  §34-4 의 같은 측정(ZED X 0.28~0.35m, **0.291° / 0.859mm**, 몸체 randomize)과 **일치한다** —
  독립 재현이다. `black` 만 **6~8배** 나쁘다.
- ★★ **`gt_bias_px` 가 원인을 직접 가리킨다.** 이건 `residuals_at()` 이 **GT pose 의 참 실루엣**에서
  잰 부호 있는 잔차(바깥이 +)다. `black` 에서 **−2.1px = 0.7mm 안쪽**이고 `orange` 는 0 이다.
  → **실루엣 계산은 맞다. 틀린 것은 «이미지의 어디가 그 실루엣인가» 다.**
  검정 flange 가 검정 몸체 위에 있으면 바깥 경계에 밝기 차가 없어서 `find_edges` 가 대신
  **융기 능선**(외곽선 안쪽 4~6px, §34-4)을 잡고, 정합기는 그 잘못된 목표로 **성실하게 수렴**한다.
- 🔴 **그래서 «이득이 작다» 가 아니라 «계통 편향» 이다.** 편향은 프레임마다 같은 방향이라
  **게이트가 못 막는다**(§29 의 최악 축과 같은 성질). `black` 에서는 정합을 **끄는 편이 안전**하다.
- ⚠️ **real 에서는 이 진단을 못 한다** — GT 가 없다. 대리 수단은 **좌우 투영 일관성**(정합 후 늘면
  의심)과 **오버레이 육안**, 그리고 **몸체 외관이 flange 와 같은 색인지 눈으로 확인**하는 것뿐이다.
  🔴 실물 FOUP 몸체 3종 중 **검정 불투명이 이 조건에 정확히 해당**한다(§35-2f 의 «black 최난이도»).
- ⚠️ 이 표는 **`--outer-only` 기준**이다. 전체 실루엣으로 재면 융기 능선이 대응점의 대부분이 되어
  다른 값이 나온다 — 두 설정을 섞어 인용하지 말 것.
- 산출물: `runs/fakereal_d25_gtstart` · `runs/fakereal30_gtstart` · `runs/fakereal_d25o_gtstart` ·
  `runs/fakereal_d30o_gtstart` · 디버그 이미지 `runs/fakereal30_dbg/frame_*/contour_debug.png`.

## ★★★ 35-2j. 테두리 정합의 **포획 반경** — 자유도마다 열 배 다르다 (2026-08-19)

*"`--search-px 8` 밖은 못 본다면 어디까지 고쳐지나"* 를 **유도가 아니라 측정**으로 냈다.
GT 를 알려진 양만큼 흔들어 초기값으로 주고 되돌아오는지 본다(게이트 끔, `--outer-only`).
몸체는 **`orange`** 다 — `black` 은 정합기 자체가 편향돼 있어(§35-2i) 포획 반경 측정이 오염된다.
`runs/fakereal_d30o` n=20 · Z 중앙 313mm · **1px = 0.430mm** · flange 투영 반경 213px.
**바닥(교란 0) = R 0.251° / t 0.93mm.**

| 교란 | 정합 후 R중앙 / t중앙 | KPI | 판정 |
|---|---|---|---|
| **yaw** 0.5·1·2° | 0.273 / 0.265 / **0.284°** · t 0.95 | 18·19·19 | ✅ **완전 회수** — 바닥과 구분 안 됨 |
| yaw 4° | 0.991° / 2.08mm | 13/20 | ⚠️ 부분 |
| yaw 8° | 3.070° / 7.27mm | 5/20 | ❌ |
| **tilt** 0.5·1·2° | 0.251 / 0.256 / 0.512° | 19·19·19 | ✅ **완전 회수** |
| tilt 4·8° | 1.065 / 1.968° | 13 · 9 | ⚠️ 서서히 무너진다(yaw 보다 관대) |
| **Z** 2·5mm | 0.332 / 0.990° · t 1.42 / 3.37mm | 19 · 16 | ✅ |
| Z 10·20·40mm | t 6.69 / 17.05 / 19.76mm | 6 · 0 · 0 | ❌ 10mm 부터 |
| 🔴 **횡 1mm** | **0.568° / 2.75mm** | 16/20 | ❌ **바닥보다 나쁘다** |
| 횡 2·4·8mm | 0.841 / 1.577 / 2.409° · t 4.13 / 4.73 / 6.37mm | 15 · 11 · 6 | ❌ |
| 횡 16·32mm | 9.050 / 8.528° | 0 · 0 | ❌ |

⚠️ **위 표의 `t` 는 전부 `‖Δt‖` 다** — 어느 축을 흔들든 **Z 표류가 이 값을 지배**한다(§35-2k-2).
  «횡» 행을 «횡방향 성능» 으로 읽으면 안 된다.

- 🔴🔴 ~~**가장 약한 축은 «횡방향 평행이동» 이고, 그 이유는 탐색 반경이 아니다.**~~
  → **절반만 맞았다 (2026-08-19 정정, §35-2k-2).** 축을 분해하니 횡 1mm 교란의 `t 2.75mm` 는
  **Z 2.70mm + 횡 0.86mm** 였고, **횡 성분은 바닥값(0.93mm)까지 완전히 회수**돼 있었다.
  즉 «회수 안 됨» 은 **노름이 만든 착시**다(교훈 #83). 그리고 *"이유는 탐색 반경이 아니다"* 도
  틀렸다 — 탐색폭을 24px 로 넓히면 **횡 포획 반경이 4mm → 16~24mm 로 넓어진다**(§35-2k-2).
  ✅ **살아남는 부분**: 횡 교란이 **R 을 0.251 → 0.568° 로 오염**시키는 것은 사실이고, 원인도
  맞다 — 평면형 윤곽에서 **횡 이동 ↔ 면외 tilt ↔ Z 가 약한 원근 하에서 축퇴**하고, 정합기가
  횡 오프셋을 **tilt 로 설명해 버린다.** `--fix-z` 처방(아래)도 그대로 유효하다.
- ★★★ **`--fix-z` 가 그 축퇴를 끊는다** — Z 를 초기값에 묶으면 횡방향이 되살아난다:

  | 교란 | 기본 | **`--fix-z`** |
  |---|---|---|
  | 횡 1mm | 0.568° / 2.75mm · 16/20 | **0.273° / 0.83mm · 20/20** |
  | 횡 2mm | 0.841° / 4.13mm · 15/20 | **0.529° / 0.83mm · 18/20** |
  | 횡 4mm | 1.577° / 4.73mm · 11/20 | 1.795° / **1.39mm** · 13/20 |
  - 즉 `--fix-z` 는 *"Z 정보가 없으니 포기한다"* 가 아니라 **«3자 축퇴에서 한 변수를 빼서 나머지
    둘을 식별 가능하게 만드는»** 장치다. 초기 Z 가 믿을 만할 때만(= FP depth 가 정상일 때) 쓴다.
- ★ **회전은 «완전 회수» 가 되는데 평행이동은 안 된다** — 이것이 §27-7 의
  *"회전은 coarse, 평행이동은 refined 에서 받는다"* 와 §35-2h 의 *"정합이 R 을 1.5~2배 개선하고
  t 는 그대로거나 나빠진다"* 의 **기전**이다. **테두리 정합의 일은 회전을 고치는 것이고,
  평행이동은 이미 맞아 있어야 한다.** FoundationPose 가 t 1.0mm 급을 주므로 성립한다.
- ✅ **게이트가 이 실패를 잡는다** — 횡 4mm 교란에서 정합은 **1.577°** 회전하는데 τ=1.5° 를 넘는다.
  ⚠️ 단 횡 1~2mm(0.57~0.84°)는 **못 걸러진다.** 게이트는 폭주를 막지 축퇴를 못 막는다.
- ⚠️ **거리에 따라 눈금이 바뀐다.** 같은 `--search-px 8` 이 n25(Z 258mm)에서 ±2.83mm,
  n30(Z 313mm)에서 ±3.44mm 다. 자유도별 환산(n25 기준): 횡 ±2.8mm · 면내 yaw **±1.8°**
  (`8/259px`) · 시선 Z **±8.0mm**(`8/259 × 258mm`). **Z 가 가장 관대하고 횡이 가장 빡빡하다.**
- 재현: `scratchpad/capture_range.py`(GT 교란 → `refine_contour` → GT 대비 채점).
- 🔴🔴 **위 표의 «횡» 행은 `‖Δt‖` 로 잰 것이고, 그건 Z 표류가 지배한다 — 축을 분해하면 결론이
  바뀐다.** 횡 1mm 교란의 `t 2.75mm` 중 **2.70mm 가 Z** 이고 횡 성분은 **0.86mm**(= 바닥)다.
  즉 *"횡이 가장 약한 축"* 은 **부분적으로 노름이 만든 착시**다 → **§35-2k** 에서 다시 낸다(교훈 #83).

## ★★★★ 35-2k. 포획 반경은 «탐색폭» 이 아니라 «단계» 로 넓힌다 — **코드 0줄로 횡 4mm → 24mm** (2026-08-19)

실물에서 *"t 가 10mm 넘게, 특히 +x 로 틀린다"* 는 관측이 나왔다(사용자). §35-2j 의 포획 반경
(횡 ~2mm)이면 **정합기가 그 오차를 볼 수조차 없다.** 그래서 *"`--search-px` 를 그냥 키우면 되나"* 를
먼저 쟀다 — **기존 코드 무수정, 인자만 바꾼 세 실험**이다.

### 35-2k-1. 넓히면 «좋은 초기값» 에서 손해다 — 그리고 24~32px 에서 포화한다

`runs/zx_n25`(n=120) + `runs/zx_n25_flonly/pose_coarse.json` 초기값 + `--outer-only`.
게이트는 **사후 적용**(`meta_contour.json` 의 `moved_deg`)이라 폭당 런 1회다.

| `--search-px` | 후퇴(τ1.5) | 대응점 | rms | R 중앙 | KPI(게이트 없음) |
|---|---|---|---|---|---|
| **8** (현행) | 18 | 1764 | **0.705px** | **0.220** | **109/120** |
| 12 | 21 | 1784 | 1.234 | 0.246 | 105 |
| 16 | 28 | 1794 | 1.544 | 0.262 | 101 |
| 24 | 31 | 1798 | 1.620 | 0.363 | 99 |
| 32 / 40 / 56 | 33 | 1800 / 1802 / 1803 | 1.642 / 1.642 / 1.692 | 0.363 | 98 |

- **넓힌 만큼 «먼 가짜 대응» 이 들어온다** — rms 2.3배, R 중앙 65% 악화. 대응점 수는 2% 밖에
  안 변하므로 **표본 효과가 아니다.**
- ★ **24~32px 에서 포화한다.** ⚠️ 교훈 #21(*"소수점까지 같으면 적용 안 된 것"*)을 먼저 의심했는데
  **적용은 됐다** — rms 최대가 8.43 / 9.09 / 9.27 로 다르고 대응점도 1800 → 1803 으로 는다.
  **진짜 포화**이고 원인은 `find_edges` 의 **「예측에 가장 가까운 국소최대」** 규칙이다 —
  더 가까운 후보가 있으면 아무리 넓혀도 그게 계속 뽑힌다. **탐색폭은 포획 반경의 상한을 못 올린다.**
- 비용은 거의 안 는다(12.7 → 14.3s / 120프레임). 병목이 프로파일 샘플링이 아니다.

### 35-2k-2. 🔴 그런데 **횡만 떼어 보면** 포획 반경이 실제로 넓어진다

`runs/fakereal_d30o`(orange, n=20) GT 교란. **회수 = 횡오차 ≤2mm & R ≤3°**.

| 횡 교란 | s8 횡 / 회수 | **s24 횡 / 회수** | s40 횡 / 회수 |
|---|---|---|---|
| 4mm | 1.08mm · 15/20 | 0.99 · 15/20 | 1.04 · 15/20 |
| **8mm** | 3.73mm · **7/20** | **1.29 · 12/20** | 1.30 · 12/20 |
| **16mm** | 13.87mm · **0/20** | **1.97 · 10/20** | 1.98 · 9/20 |
| 24mm | 21.52 · 0/20 | 12.94 · 1/20 | **4.71 · 6/20** |
| 32mm | 29.51 · 0/20 | 21.66 · 0/20 | — · 0/20 |

- ★★★ **횡 포획 반경 4mm → 16~24mm.** 32mm 가 벽이다.
- 🔴 **`‖Δt‖` 로 보면 이게 안 보인다** — 평면 테두리는 Z 구속이 약해 **Z 표류가 노름을 지배**한다.
  §35-2j 가 *"횡 1mm 도 회수 안 됨(t 2.75mm)"* 이라고 읽은 것의 실체는 **Z 2.70mm + 횡 0.86mm** 다.
  → 교훈 **#83**.
- **Z 는 어떤 탐색폭으로도 못 고친다**(20mm 교란 → 잔여 17.4mm, 전 폭 동일). 예상대로이고
  `--fix-z` 로 FP 에서 받는 것이 맞다는 §35-2j 의 처방은 그대로다.
- ★ **Z 가 20mm 틀려도 횡은 1.5mm 로 멀쩡하다** — 두 축이 사실상 분리돼 있다.
- 회전 포획 반경(yaw·tilt 모두 ~4°)은 **탐색폭과 무관**하다. 넓히기가 사는 곳은 **평행이동뿐**이다.

### ★★★ 35-2k-3. 처방 = **coarse-to-fine 캐스케이드**. 새 모듈이 아니라 **호출 3회**다

`--pose-dir` 를 이어 붙이면 된다 — 1단 출력이 2단 입력이다.

| 구성 | R 중앙 | 횡 중앙 | t 중앙 | KPI(n=120) | 횡 16mm | 횡 24mm |
|---|---|---|---|---|---|---|
| 초기값(FP flange coarse) | 0.447 | — | 0.676 | 119/120 | — | — |
| **s8 단독** (현행 배포) | **0.220** | 0.682 | 0.710 | 117 | **0/20** | 0/20 |
| s24 단독 | 0.301 | 0.684 | 0.726 | 117 | 10/20 | 1/20 |
| 2단 24@4 → 8@8 | 0.223 | 0.673 | 0.700 | **118** | 7/20 | 0/20 |
| 2단 32@4 → 12@8 | 0.272 | 0.682 | 0.719 | 116 | **10/20** | **7/20** |
| **★3단 32@4 → 12@4 → 8@8** | 0.243 | **0.668** | **0.697** | **118** | 9/20 | 6/20 |

```bash
R() { envs/pose/bin/python -m spatial_vision.stages.refine_contour \
      --in "$1" --pose-dir "$2" --pose-name "$3" --obj assets/obj/foup_300_semi_r2 \
      --mesh top_flange.ply --outer-only --search-px "$4" --iters "$5" --out "$6"; }
R $CAP $FP   pose_coarse.json  32 4 $O/c1
R $CAP $O/c1 pose_refined.json 12 4 $O/c2
R $CAP $O/c2 pose_refined.json  8 8 $O/c3      # ← 게이트는 여기만
```

- **3단이 양쪽을 거의 다 가져간다** — 정밀도는 s8 급(KPI 118 로 최고, 횡·t 최소), 포획 반경은 s40 급.
- 비용 **106 → 250ms/프레임**(120프레임 30.0s). 10초 예산에서 무시할 수준이다.
- 🔴 **게이트 기준점을 손봐야 배포할 수 있다** — 현행 코드는 각 단이 **자기 입력** 대비 이동량을
  재므로 3단으로 쓰면 게이트가 1·2단 이동을 못 본다. 위 표의 후퇴율은 **최초 FP 초기값 대비로
  사후 재계산**한 값이다(18 → 34). 러너에서 처리하거나 `--gate-ref-dir` 를 추가한다.
  ✅ **둘 다 구현됐다 (2026-08-22, §35-2o-3)** — `refine_contour --gate-ref-dir` 신설, 러너 `--mode cascade`
  가 `Ccas_s1 → Ccas_s2 → Ccas` 로 자동 구성하며 마지막 단의 게이트 기준을 **최초 FP 초기값**으로 맞춘다.
  🔴🔴 **다만 «배포 경로가 아니다» 는 그대로다 — 오히려 강화됐다.** 아래 §35-2k-6 참조.

### 35-2k-4. 🔴 정직하게 짚을 것 둘

- **이 데이터셋에서 정합의 이득은 R 에만 있다.** 초기값이 이미 t 0.676mm 인데 정합 후 0.697mm 로
  **약간 나빠지고** KPI 는 119 → 118 이다. R 은 0.447 → 0.243 으로 **1.8배** 좋아진다.
  → §35-2j 의 *"테두리 정합의 일은 회전을 고치는 것"* 이 n=120 에서 재확인됐다.
- **이 캐스케이드가 실물 +x 를 고칠지는 «원인» 에 달렸다:**

  | 10mm 의 원인 | 캐스케이드가 고치나 |
  |---|---|
  | FP 초기 pose 가 횡으로 밀렸다 | ✅ **고친다** — 정확히 4 → 24mm 로 넓힌 구간 |
  | 캘리브레이션(`cx`·정류)이 틀렸다 | ❌ **오히려 굳힌다** — 모델도 같은 K 로 투영되므로 정합기가 그 오차를 «맞다» 고 보고 3D 로 옮겨 담는다 |
  | depth/Z 편향이 횡으로 샌다 | ❌ Z 는 정합기가 못 고친다(§35-2k-2) |

  **원인 판별이 선행이다** — 오버레이(24px 밀렸나) · `cam.json` 의 `disto`(정류본인가) ·
  진단 시트의 depth 패널. 원인이 ②면 캐스케이드는 문제를 **감춘다**.

### 35-2k-5. Phase 1(거리변환 정합기) 판단 — **보류**

애초 목표였던 «10mm 급 포획» 을 **코드 0줄로 달성**했다. 남은 격차는 **32mm 벽** 하나이고,
FP 가 32mm 틀리면 그건 정합기가 아니라 앞단 문제다. 거리변환(Chamfer) 모듈의 순이득은
**① 법선 직선 밖의 대응(회전 오차) ② 접선 미끄러짐** 둘로 좁혀졌고, 둘 다 지금 병목이 아니다.

재현: `scratchpad/p0_sweep.sh` · `p0_score.py` · `p0_caprange.py` · `p0_decomp.py` ·
`p0_cascade.py` · `p0_cascade2.py`. 산출물 `scratchpad/pA|pB|pC|pC2/`.

### 🔴🔴 35-2k-6. **조건이 바뀌면 이 튜닝이 뒤집힌다** — 50cm 검정에서 캐스케이드는 **최하위** (2026-08-23)

위 §35-2k 는 전부 **깨끗한 sim · 근접(0.22~0.30m) · 몸체 randomize** 조건에서 잰 것이다.
`--mode all` 30팔 전수 스윕(`runs/ALL20`·`ALL20B`, **50cm · 검정 몸체 · n=20**)에서 재보니:

| | 좌우 \|Δdx\| | 이동량 t 중앙 | **GT KPI** |
|---|---|---|---|
| `Ccas` 캐스케이드 `32→12→8` | **3.13px (30팔 중 최하위)** | 18.5mm | **0/20** |
| `A1` 단일 `8px` | 1.72px | 17.3mm | 11/20 |
| `A3` 정합 off | 0.70px | — | **20/20** |

- 🔴 **넓은 탐색폭이 «엉뚱한 에지를 더 멀리서 찾아오는» 쪽으로 작동한다.** 검정 몸체는 flange 와
  같은 색이라 외곽에 밝기 경계가 없고(§35-2i), 그 조건에서 탐색을 넓히면 융기 능선·그림자까지
  후보에 들어온다. **포획 반경을 넓히는 것은 «찾을 것이 거기 있을 때만» 이득**이다.
- ★ **§35-2k 를 인용할 때 조건을 함께 인용할 것** — *"캐스케이드가 횡 포획을 4 → 24mm 로 넓힌다"* 는
  참이지만, **그 앞에 «정합기가 물체 경계를 제대로 잡고 있을 때» 가 붙는다.**
- ✅ 판정은 GT 없이 된다 — 리포트의 «이동량 t 중앙 ≥10mm» 규칙이 `Ccas` 를 포함한 정합 팔 27개를
  전부 🔴 로 찍었고, 실제로 정합을 끈 3팔이 최상위였다(§35-2p-5).
- ⚠️ 이것이 §35-2k 를 **철회**하는 것은 아니다. 두 측정은 **다른 조건**이고, 둘 다 참이다 —
  기록해야 하는 것은 *"어느 조건에서"* 다(교훈 #33 «"안 된다" 에는 항상 조건을 붙인다»).

## ★★★ 35-2l. 실험 노트와 **거리 대조** — 시행착오를 위한 산출물 (2026-08-19)

> ⚠️ **갱신 (2026-08-22)** — 여기서 «거리 삼각 대조» 라 부른 것은 **네 다리로 늘었다**(§35-2n-6).
> 아래의 `FP z` 와 `stereo depth` 는 **뿌리가 같아 «독립» 이 아니다** — 교훈 #89.

실물은 한 번에 안 된다. 거리·조명·참조·플래그를 바꿔 가며 여러 번 돌리는데, 지금까지는
**무엇을 바꿨는지가 어디에도 안 남았고** 런 간 비교가 손으로만 됐다. 셋을 붙였다.

### 35-2l-1. `<out>/run_meta.json` — 이 런이 무엇이었는가

날짜·시각 · `--note` 자유 메모 · 전체 CLI 인자 · 참조 세트와 **출처 메타**(없으면 «없다» 를 명시) ·
**자산·`cam.json`·사진의 내용 해시** · 소요 시간. 런 시작 시점에 먼저 쓰므로 중간에 죽어도 남는다.
⚠️ **git 정보는 넣지 않는다**(사용자 방침). *"어떤 상태였나"* 는 **내용 해시**로 대신한다 —
커밋 여부와 무관하게 «같은 사진·같은 CAD·같은 참조였나» 가 확정된다.

### 35-2l-2. `tools/compare_runs.py` — 런 N개를 한 표로

```bash
envs/pose/bin/python tools/compare_runs.py runs/r01_A runs/r02_A --index runs/runs_index.md
```
**① 설정 diff 를 먼저** 낸다(무엇이 달랐는지 모르면 지표를 못 읽는다) → ② 촬영 진단 → ③ 변형별 지표.
🔴 **`obj`·`preset`·`refs`·`input_scale` 등이 다르면 «초기값이 달라지는 비교»** 로 판정하고
**게이트 후퇴율 무효 경고**를 자동으로 단다(교훈 #82). `--index` 는 한 줄씩 **누적**되는 실험 노트다.

### ★★ 35-2l-3. 거리 대조 — GT 없이 **z 편향**을 잡는다  (→ 네 번째 다리는 §35-2n-6)

`--true-distance-mm` (**선택**) 을 주면 **FP 추정 z · stereo depth · 줄자 실측** 셋을 대조한다.
안 주면 앞의 **둘만** 비교한다 — 그것만으로도 *"둘 중 하나가 틀렸다"* 는 갈린다.

| | n25 orange | n30 orange |
|---|---|---|
| FP 추정 z | 258mm | 313mm |
| stereo depth (평면적합) | 257 | 311 |
| **차** | **+0.8** | **+1.1** |
| flange 평면 rms | 0.38mm | **0.37mm** ← 기준선 |

- ★ **`flange 평면 잔차 rms` 가 «depth 가 맞는가» 의 정량 지표다.** 🔴 `valid.png` 100% 는
  «뚫렸다» 를 뜻하지 않는다 — 범위 검사일 뿐이라 틀린 값도 유효로 센다. **sim 깨끗 기준선 0.37mm**
  이고, 실물에서 3mm 를 넘으면 **열린 항목 #1** 이 그 자리에서 걸린다.
- ★ **눈금을 리포트 머리에 박는다** — *"이 런의 1px = 0.430mm, **10mm = 23px**"*. 오버레이를
  정량적으로 볼 수 있게 된다(«24px 밀렸나» 가 2D 문제와 3D 문제를 가르는 첫 갈림길이다).
- ★ **`좌우 Δdx` 를 부호까지 낸다** — `lr_consistency` 가 이미 계산해 두는데 리포트가 `abs_median`
  만 읽고 있었다. **부호가 한쪽으로 쏠리면 계통 편향**이고 게이트가 못 막는 축이다(§29·§35-2i).

### 🔴 35-2l-4. 이 진단이 처음에 **거짓 경보**를 냈다 — 교훈 #84

첫 구현은 «flange 마스크 안 depth **중앙값**» 을 FP 의 z 와 비교했고 **+6.5mm 어긋남**을 보고했다.
sim GT 로 확인하니 **틀린 건 아무것도 없었다**:

| | 값 | GT pose z 대비 |
|---|---|---|
| GT pose z | 313.0mm | — |
| FP 추정 z | 312.8 | **+0.28** ✅ |
| stereo depth 중앙값 | 301.0 | −6.37 |
| **GT depth 중앙값** | 302.1 | **−6.92** ← 오차가 아니라 기하 차 |

**두 양이 애초에 같은 것이 아니었다.** 원근 때문에 **가까운 쪽이 픽셀을 더 차지**하고 융기(+2mm)와
홀 깔때기가 섞여서, 마스크 안 depth 중앙값은 pose 원점 z 보다 구조적으로 ~7mm 작다.
→ **평면을 적합해 «원점이 투영되는 시선 위에서» 평가**하도록 고쳤다: **311.3mm (GT 대비 −0.81mm)**,
FP − 평면 **+1.09mm**. 덤으로 평면 rms 가 나온다.

### ★★ 35-2l-5. 「여기부터 보라」 + 「다음에 무엇을」 (2026-08-19)

리포트에 두 절이 더 붙는다. **둘 다 GT 없이 계산되고 실물 첫 런부터 나온다.**

- **`## 여기부터 보라`** — GT-free 지표별 최악 프레임을 뽑아 **걸린 이유와 함께** 표로 낸다
  (게이트 후퇴 · 이동량 · rms · 대응점 최소 · 좌우 불일치 · 평면 잔차 · FP−depth · 마스크 크기 이탈).
  **여러 지표에 걸린 프레임을 먼저** 놓는다 — 그게 진짜 볼 값어치가 있는 장이다.
  ⚠️ **순위 기반이지 임계값 기반이 아니다** — 정상인 런에서도 «상대적으로 가장 나쁜» 장은 나온다.
  ★ 그 프레임들만 **심링크한 임시 디렉토리**에 `refine_contour --debug` 를 다시 돌려
  **`<out>/worst/A1_debug/frame_*/contour_debug.png`** 를 낸다 — `refine_contour` 는 한 줄도 안 고친다.
  🔴 **이 그림이 «Sobel 이 물체 경계를 잡았나 · 융기 능선을 잡았나 · 그림자를 잡았나» 를 보는 유일한
  수단**이고, §35-2i 의 검정 몸체 계통 편향을 실물에서 대리 관측하는 통로다.
- **`## 다음에 무엇을 할까`** — 진단이 아니라 **행동**을, **비용(촬영 횟수) 순**으로. 로봇이 없어
  손으로 찍으므로 «촬영 0» 과 «촬영 2» 의 차이가 크기 때문이다.
  ⚠️ 규칙은 **지금까지 sim 에서 본 실패 유형만** 안다 — 목록이 짧다고 «문제 없음» 이 아니다.

### 🔴🔴 35-2l-6. 결정론 — **스테이지마다 다르고, GPU 단계는 비결정론적이다** (2026-08-19)

⚠️ **이 절은 정정본이다.** 처음에 두 번씩 돌려 보고 *"두 스테이지 모두 완전 결정론"* 이라고 적었는데
**표본 2개로 내린 오판**이었다 — FoundationPose 는 같은 결과를 낼 때도, 안 낼 때도 있다(교훈 #86).

같은 입력(픽셀·`cam.json` 전부 동일)으로 **새 프로세스에서** 여러 번 돌려 바이트 비교했다. n=20.

| 스테이지 | 결정론 | 재실행 차이 |
|---|---|---|
| **`stereo_onnx`** (GPU·ONNX) | 🔴 **아니다** — 20/20 프레임 매번 다름 | disparity 중앙 **0.016px**(≈0.015mm) · 최대 69.6px(경계 픽셀) |
| **`pose_fp`** (GPU·torch) | 🔴 **아니다 — 이분적**. 두 런이 바이트 동일하기도, 0.15° 벗어나기도 한다 | **ΔR 중앙 0.146° · p90 0.343° · 최대 0.662°** / Δt 중앙 0.106mm · 최대 0.592mm |
| **`refine_contour`** (CPU·numpy/scipy) | ✅ **완전 결정론** — 4회 전부 바이트 동일 | 0 |

- 🔴🔴 **FP 의 재실행 잡음(ΔR 0.15°)이 우리가 보고해 온 R 중앙값(0.19~0.45°)과 같은 자릿수다.**
  → **FP 를 다시 돌린 두 런의 R 차이가 0.15° 미만이면 그것은 설정 효과의 증거가 아니다.**
- ✅ **다행히 문서의 A/B 대부분은 영향이 없다** — A1/A2a/A2b/A4·정합 플래그 비교는 **같은
  `fp_ns2` 산출물을 초기값으로 공유**한다. 영향을 받는 것은 **FP 를 다시 돌린 비교**뿐이다.
- ★ **테두리 정합이 그 잡음을 대부분 흡수한다** — FP 가 0.04~0.43° 흔들려도 정합 후 차이는
  **0.000~0.004°** 다. ⚠️ 단 **가끔 증폭한다**: 20프레임 중 2장에서 1.43°/2.4mm, 1.34°/3.1mm
  (초기값이 달라져 다른 국소최소로 갔다). **정합기는 평균적으로 안정화하지만 보장하지는 않는다.**
- ⚠️ **원인 추정**: cuDNN/ONNX Runtime 의 **알고리즘 자동선택**이 프로세스마다 다를 수 있다
  (타이밍 기반 autotune·TF32). 결과가 **이분적**인 것이 그 특징이다 — 완전 랜덤이 아니라
  «몇 개의 결과 중 하나» 다. 재현이 꼭 필요하면 산출물을 보관한다(재실행으로는 못 되돌린다).
- 🔴 **`compare_runs.py` 사용 지침**: 두 런이 같은 설정인데도 다르면 **먼저 이 잡음 바닥을 의심**한다.
  `cam.json` 이 8번째 자리만 달라도(우리 실측: `make_frame_from_zed` 는 프로파일 공칭값을,
  sim 캡처는 렌더 실측값을 쓴다 — 상대차 2e-8) FP 출력이 최대 0.43° 갈렸다.
  **FP 는 가설 argmax 를 고르므로 근소한 차가 «불연속 점프» 로 나타난다.**

### 35-2l-7. 비교 함수 자체가 틀려 있었다 → 교훈 #85

위 결정론 검사를 처음 돌렸을 때 «ΔR 0.019°/0.033°» 가 나왔는데 **파일은 바이트 동일**이었다.
`arccos((tr−1)/2)` 가 항등 근처에서 오차를 **제곱근으로 증폭**한 것이다(자기 비교 p90 0.028°).
`contracts.rotation_angle_deg`(atan2)로 모으고 **7군데를 전부 교체**했다.
✅ 회귀: `eval_pose` 의 `zx_n25_flonly` R 0.509 / t 0.767 (교체 전과 0.001° 차).

### ★★★ 35-2l-8. **«이 값이 상이한가»** 를 두 방식으로 본다 (2026-08-19)

GT 가 없어서 못 하는 것은 **절대 오차 분석 하나뿐**이다. *"서로 같아야 할 값이 다르다"* 와
*"이 프레임만 다르다"* 는 GT 없이 된다. 리포트에 두 절을 더 붙였다.

**(a) `## 이 값이 상이한가 — sim 기준선 대조`** — 임계값이 판정 «문장 안» 에 박혀 있어 한눈에
안 보이던 것을 **대역과 실측을 나란히** 놓은 표로 바꿨다(8항목: 평면잔차 · FP−depth · 주변유효율 ·
A1 후퇴/대응점/잔차/이동량/좌우Δdx).
- 🔴 **«정상 범위» 가 아니라 «sim 에서 잰 값» 이다.** 벗어남이 곧 고장이 아니라 **도메인 갭일 수도**
  있다 — 표는 판정을 대신하지 않고 **비교 대상**을 준다.
- 출처는 orange 몸체 **조건 2개(n25·n30) × n=20** 뿐이라 대역이 좁다. **첫 실물 런 이후 real 값으로
  갱신**한다(`tools/run_group_a.py` 의 `SIM_BASELINE_*`).
- ⚠️ 실물에서 **가장 먼저 벌어질 값은 `flange 평면 잔차`**(sim 0.37mm)다 — 스테레오 관통 품질이고
  «얼마나» 큰지가 정보다.

**(b) `## 이상 프레임 (분포 기준)`** — 프레임별 지표에 **강건 z-score**(중앙값·MAD/IQR)를 걸어
*"이 프레임만 다르다"* 를 찾는다. ★ **기준선이 필요 없다 — 런 자기 자신이 기준이라 도메인 갭에
구조적으로 면역**이고, 실물 첫 런부터 그대로 작동한다.
- ★ `## 여기부터 보라`(순위 기반)와 **다른 도구다**: 저기는 정상인 런에서도 뭔가 나오고,
  여기는 **아무것도 안 나오는 게 정상**이며 **나오면 그 자체가 신호**다.
- ✅ **GT 로 검증했다** — `e2e_A`(n=20)에서 플래그된 5장의 **R 오차 중앙 0.597° vs 나머지 0.168°
  (3.6배)**. GT 를 전혀 안 쓰고 계산했는데 실제로 나쁜 프레임을 집었다.
  ⚠️ **t 는 갈리지 않았다**(0.749 vs 0.727mm) — §35-2j 의 *"테두리 정합은 회전 정합기"* 와 일관된다.

🔴 **만들면서 밟은 함정 둘 (→ 교훈 #87)**
1. **MAD 가 붕괴한다.** sim 의 `valid_all` 은 값의 대부분이 정확히 1.0 이라 MAD=0 → **z 가 209** 로
   발산했다. → 척도를 `max(MAD, IQR, 0.02·|중앙값|)` 로 깔았다(z 8.1 로 정상화).
2. **꼬리를 이상치로 오독한다.** 좌우 Δdx 가 20장 중 **6장에서 −1.5~−4.6px** 로 뭉쳐 있었다.
   그건 «소수의 사고» 가 아니라 «30% 가 다르게 동작한다» 는 뜻이다. → **한 지표에서 25% 넘게
   걸리면 이상치 표에서 빼고 «분포가 갈라진 지표» 로 따로 보고**한다. 프레임 몇 장을 열어서는
   안 풀리고 **조건 축(자세·거리·조명)** 을 봐야 하는 문제이기 때문이다.

🔴 **여전히 남는 사각지대**: (a)(b) 둘 다 **«다 같이 틀린» 경우를 못 잡는다.** 모든 내부 지표가
«자기 일관성» 이라 캘리브레이션이나 CAD 형상이 틀리면 전부 사이좋게 틀린 채 일관된다
(§35-2i 의 검정 몸체 −2px 편향이 실례다). **그 축을 보는 건 오버레이 육안뿐이다.**

## ★★★★★ 35-2m. **실물에서 실제로 통과한 경로는 `--primary full` 이었다** — 러너 A그룹이 막힌 이유 (2026-08-20)

사용자가 다른 PC 에서 러너로 실물(28·40·50cm)을 돌렸는데 **pose 가 아예 안 나왔다.**
그런데 **같은 실물 데이터로 예전에 손 명령으로는 통과했었다.** 두 명령을 나란히 놓으니 원인이 하나였다.

```
손 명령 (통과)   pose_fp --primary full   --no-stage2   →  mask_full.png 만 읽는다
러너 A그룹 (실패) pose_fp --primary flange --no-stage2   →  mask_flange.png 가 필수
```
`pose_fp.py:255` 가 그 갈림길이고, 마스크가 비면 `L310` 에서 **프레임을 통째로 건너뛴다**
→ pose 없음 → 정합 미실행 → `diag_sheet` 「없음」. **정합의 문제가 아니라 정합에 도달을 못 한 것**이다.

⚠️ **«예전엔 top flange 로 pose 가 됐다» 는 기억은 정확하지 않다** — pose 는 `full` 메쉬로 냈고
`overlay_flange.py`(사용자가 그 PC 에서 만든 미커밋 도구)로 flange 를 **그려서** 확인한 것이다.

### 35-2m-1. sim 으로 세 거리를 그대로 재현했다

`fakereal30`(기존) + **신규 캡처 `fr_d40`·`fr_d50`**(seed 303 · `black` · elevation 35~70° ·
HDRI·바닥재질·조명 fixture 를 `fakereal` 과 동일하게, 거리만 0.35~0.45 / 0.45~0.55). n=20.
z 중앙 397 / 497mm. GT 를 지운 사본 `fr40`·`fr50` 에 손 명령을 그대로 돌리고 **원본으로 사후 채점**했다.

| 거리 | 분할 | 검출 | R 중앙 / 최대 | t 중앙 / 최대 | KPI |
|---|---|---|---|---|---|
| 28cm (`fakereal30`) | ISM (CAD 템플릿) | 20/20 | 0.590° / 1.39° | 2.869 / 8.61mm | 17/20 |
| 40cm (`fr40`) | SAM3 **텍스트** conf 0.10 | 19/20 | 0.438° / 1.26° | 2.559 / 5.58mm | 18/20 |
| 40cm | SAM3 텍스트 conf **0.05** | **20/20** | 0.499° / 1.15° | 2.200 / 6.23mm | 19/20 |
| 50cm (`fr50`) | SAM3 텍스트 conf 0.15 | 17/20 | 0.597° / 1.09° | 2.471 / 4.45mm | 17/20 |
| 50cm | SAM3 텍스트 conf **0.05** | **20/20** | 0.459° / 0.96° | 2.407 / 4.55mm | **20/20** |

- ✅ **`--primary full` 은 세 거리 모두 끝까지 돈다.** 28cm 는 §35-2h 의 `black`/n30(17/20)을 **정확히 재현**한다.
- ★★ **거리를 늘려도 t 가 안 나빠진다** (2.87 → 2.20 → 2.41mm). **§22 의 예측 그대로다** — FP 의 crop 이
  `diameter × crop_ratio` 정사각이라 유효 해상도가 **거리와 무관**하다(`full` 4.34mm/px). 
  🔴 그래서 **t 2~3mm 는 «거리를 바꿔서» 못 줄인다.** KPI 5mm 안이지만 여유가 적고, 줄이려면
  `--primary flange`(1.38mm/px)나 테두리 정합이 필요하다 — 그게 지금 막힌 경로다.
  ⚠️ 28cm 가 오히려 조금 나쁜 것은 §35-2h 의 **잘림**(pose 원점이 flange 상면, 몸체가 아래로 화면 밖)과 일관된다.

### 35-2m-2. 미검출은 confidence 만의 문제였고, 낮춰도 대가가 없다

사용자 관측 *"0.15 는 2/10 미검출"* 이 sim 에서 **3/20** 으로 재현됐다. 그리고 **마스크가 나쁜 게 아니라
검출 0**(`n_instances 0`, `score 0.0`)이다 — 마스크 품질은 임계값에 무감각하다:

| 50cm | 검출 | IoU 중앙 | IoU 최소 | 오선택(IoU<0.5) |
|---|---|---|---|---|
| conf 0.15 | 17/20 | 0.986 | 0.946 | 0 |
| conf 0.10 | 18/20 | 0.986 | 0.946 | 0 |
| **conf 0.05** | **20/20** | 0.986 | 0.885 | **0** |

> 🔴 **정정 (2026-08-22) — «기본값을 0.05 로 내려도 된다» 는 철회했다. 기본값은 `0.15` 다.**
> 위 표의 **«오선택 0» 이 공허한 측정**이었다. 그 캡처의 `meta_capture.json` 을 확인하니
> `distractors {n_shown: 0}` · `occluders {n_shown: 0}` — **애초에 오선택할 대상이 없는 씬**이다.
> 「낮춰도 오선택이 안 는다」를 **방해물 없는 데이터로 보인 것**이라 실물에 전이되지 않는다.
> → 러너 기본값은 **0.15 유지**, `--text-conf` 로 낮추되 **`segcmp` 의 «이탈» 열(>0.25)로 확인**한다.
> ⚠️ 이건 교훈 #13(«IoU 평균은 오선택을 숨긴다»)의 변형이다 — 이번엔 지표가 아니라 **씬**이 숨겼다.

**마스크 품질은 임계값에 무감각하다는 부분은 그대로 유효하다** — 오히려 재확인됐다.
sim 50cm 6프레임(§35-2n 검증 런)에서 `frame_0003` 만 `score 0.099 < 0.15` 로 미검출인데,
`--text-conf 0.01` 로 다시 뽑으면 그 프레임의 GT 대비 **IoU 0.988 · precision 1.000** 으로
6장 중 최상급이다. **«분할이 틀린» 게 아니라 «자신감 점수만 낮은» 것이다.**
- 그 6장의 점수: `0.391 / 0.738 / 0.162 / **0.099** / 0.641 / 0.271` — **0.15 바로 위·아래에
  두 장이 붙어 있다.** 이 씬에서 0.15 는 벼랑 끝이다.
- ⚠️ **왜 그 프레임만 낮은지는 단일 축으로 설명이 안 된다.** 씬 밝기 40(둘째로 어둡다)·물체 대비 31
  인데, `frame_0000` 은 대비 26 으로 더 나쁜데도 0.391 이다. → **임계값을 예측하려 하지 말고
  낮춘 뒤 오선택을 따로 거른다.**
- ✅ 안전망은 작동한다 — 같은 프레임에서 `fp_ns2`·`fp_ism`·`A1`~`A4`·`I1` 은 전부 pose 를 냈다.
  **T 하나만 빠진 것**이고 T 는 «참조 없이 낱말로 되는가» 를 보는 대조군이다.

⚠️ 위 표는 **sim 몸체가 검정이고 프롬프트가 `"black plastic box"`** 라 잘 맞은 조건이다. 실물 몸체가
민트색이면 **conf 를 내리기 전에 프롬프트부터** 바꿔야 한다(`"mint green plastic box"` / `"plastic box"`).

### 35-2m-3. 손 명령 ↔ 러너 — 무엇이 다른가

| 축 | 손 명령 3벌 | `run_group_a.py` |
|---|---|---|
| 목적 | **«끝까지 도는가»** 스모크 | **후보 서열화** — 한 벌 데이터로 변형 5~9개 |
| 분할 | 하나만 (ISM **또는** SAM3 텍스트) | SAM3 **exemplar** flange + (`--ism`) ISM full + 진단용 SAM3 full |
| SAM3 방식 | **텍스트 프롬프트** (`--prompt`·`--confidence`) | **참조 이미지** (`--refs`) — 텍스트 경로는 **없다** |
| pose 메쉬 | `full` | `flange`(A계열) + `full`(I계열) |
| stage2 | off 하나 | **둘 다**(`fp_ns2`/`fp_s2`) — §32 판정에 둘이 다 필요 |
| 테두리 정합 | 없음 | 4~5 변형 + 게이트 |
| GT-free 지표 | 없음 | 좌우 일관성 · 후퇴율 · **거리 사각** · 신호등 · 이상 프레임 · 반복도 |
| 산출 | overlay png | `report.md` · `stats/` · `diag/` · `run_meta.json` |
| 재현 | 명령을 기억해야 | `run_meta.json` + `compare_runs.py` |

- 🔴 **손 명령의 28cm 는 러너의 부분집합이다** — `--only st,seg_ism,fp_ism` 이 정확히 그것이고,
  거기에 `I1`(정합+게이트)이 더 붙는다. **40/50cm 의 텍스트 경로는 러너에 아예 없다.**
- ★ 그래서 실물 재실행은 `--ism` 을 켜고 **`I1`/`I3` 행을 읽는다.** A계열이 비는 것은 정상이다.

### 35-2m-4. 러너의 진단 시트가 «없는 팔» 을 가리키고 있었다 (고침)

`run_group_a.py` 의 `ov`·`diag` 가 `A1`·`seg_full` 을 **문자열로 박아** 넘기고 있었다.
SAM3 flange 가 비면 `A1` 이 안 만들어지는데 **같은 런의 `I1` 에는 pose 가 20개 있어도** 시트는
`A1` 만 보고 「없음」을 그린다. 사용자가 본 화면이 이것이다.

- **고친 방식**: `Step.cmd` 를 **지연 평가**(`Step.resolve()`)로 바꿔 **스텝 실행 직전**에 살아 있는
  산출물을 고른다. `_live_preds` / `_live_pose_dir` / `_live_seg` 세 헬퍼.
- ★ **대체할 때 반드시 이유를 로그로 남긴다** — 조용히 바꾸면 «A1 이 성공했다» 로 오독된다
  (§35-2 의 `segment_sam6d` exemplar 후퇴 버그와 같은 함정):
  ```
  [ov]   ⚠️ pose 가 없는 팔은 뺀다: fp_ns2, A1, A2a, A2b, A4
  [diag] ⚠️ `seg_full` 에 mask_full.png 이 없다 → **`seg_ism`** 을 쓴다
         ⚠️ `A1` 에 pose 가 없다 → 진단 시트는 **`I1`** 을 가리킨다
  ```
- 🔴 **`--seg-flange` 는 일부러 안 바꿨다** — 비어 있음 자체가 정보다(3번 패널 「없음」이 옳다).
- 🔴 **계산에는 손대지 않았다.** A1 과 I1 은 **바꿔 쓸 수 있는 물건이 아니다**(§22: `full` 은 t 가 3배
  나쁘다). 파이프라인에 조용한 후퇴를 넣으면 리포트의 t 가 런마다 다른 뜻이 된다.
  **둘 다 돌리고 둘 다 남기되, 자동 선택은 하지 않는다.**
- 🔴 **덤으로 `viz.overlay_pose` 의 실제 버그 하나** — `--pred` 가 **하나뿐이면** 프레임별 이미지에서
  범례 바 폭(`ncol × tile`)과 행 폭(`예측수 × tile`)이 어긋나 `np.concatenate` 가 터진다.
  예측 2개 이상이면 안 드러나서 지금까지 보이지 않았다. → 행 폭을 따로 계산(`Wf`)하도록 고쳤다.

### ★★★★ 35-2m-5. **T그룹 신설** — SAM3 를 «참조 없이 낱말로» 돌리는 팔 (`--sam3-text`)

실물에서 통과한 원거리 경로가 **SAM3 텍스트 프롬프트**였는데 러너에 그 경로가 없었다. 붙였다.
```
seg_txt  segment_sam3 --target full --prompt "…" --confidence 0.05 --select center
fp_txt   pose_fp --primary full --no-stage2 --masks seg_txt
T1 / T3  I1/I3 과 **정합 조건 동일** (--outer-only, 게이트 1.5°)
```
🔴 **A/I/T 세 팔이 무엇을 묻는지가 다르다**: A 는 *"참조 사진과 닮았나"*, I 는 *"CAD 형상과 맞나"*,
T 는 *"이 낱말에 맞나"*. **T 는 참조 자산의 도메인 갭이 원천적으로 없다** — 그래서 A 의 대조군으로
I 보다 오히려 가깝다(둘 다 SAM3 · 같은 가중치, 조건부만 다르다).

**50cm `black` n=20 전 팔 동시 실행** (`runs/T50`, 세 팔이 stereo 만 공유):

| 경로 | R 중앙 / 최대 | t 중앙 / 최대 | KPI |
|---|---|---|---|
| **A3** exemplar flange → FP `flange` | 0.972° / 1.81° | **1.442** / 2.06mm | **20/20** |
| A1 = A3 + 정합 + 게이트 | 1.037° / 1.84° | 2.008 / **30.83**mm | 11/20 |
| **I3** ISM full → FP `full` | **0.452°** / 1.00° | 2.270 / 4.55mm | **20/20** |
| I1 = I3 + 정합 + 게이트 | 0.562° / 1.61° | 4.448 / **30.84**mm | 11/20 |
| **T3** 텍스트 full → FP `full` | **0.470°** / 0.99° | 2.266 / 4.62mm | **20/20** |
| T1 = T3 + 정합 + 게이트 | 0.570° / 1.54° | 4.163 / **30.83**mm | 12/20 |

- ✅ **T3 ≈ I3 이다** (R 0.470↔0.452 · t 2.266↔2.270). 마스크가 둘 다 좋으면 `--primary full` 의
  성능은 **분할 백엔드가 아니라 유효 해상도가 정한다**(§22). T그룹 구현 검증으로 충분하다.
- ★ **§35-2h 의 «ISM 은 회전이 강하고 평행이동이 약하다» 가 그대로 재현**된다 — `full` 계열은
  R 0.45~0.47 로 `flange`(0.972)의 **2배 좋고**, t 는 2.27 로 `flange`(1.442)의 **1.6배 나쁘다.**
  🔴 이건 텍스트/ISM 의 성질이 아니라 **`--primary full` 의 성질**이다.

### 🔴🔴 35-2m-6. 테두리 정합이 50cm 에서 KPI 를 반으로 떨어뜨린다 — **그런데 축은 «거리» 가 아니라 «몸체 대비» 였다**

> 🔴 **초판 정정 (2026-08-20).** 이 절을 *"원거리에서 정합이 해롭다"* 로 적었다. **틀렸다** —
> 검정 몸체 하나만 재고 일반화한 것이다. 같은 거리·같은 시점에서 **주황·투명은 정합이 이득**이다.
> 남는 것은 «어떻게 깨지는가»(아래 진단 3개)이고, «언제 깨지는가» 는 **거리가 아니라 외관**이다.
> → 교훈 #33 의 재발(*"기각 결론에는 조건을 명시한다"*). 사용자가 주황·투명을 재보라고 해서 잡혔다.

**50cm · 세 외관 · 각 n=20 · seed 303 동일**(카메라 pose 가 소수점까지 같아 **자산만 바뀐 통제 비교**):

| 외관 | 이동 R 중앙 | **이동 t 중앙** | 게이트 후퇴 | A3→A1 R | A3→A1 t | KPI |
|---|---|---|---|---|---|---|
| **black** | 2.40° | **17.48mm** | 11/20 | 0.972 → 1.037 | 1.442 → 2.008 | **20 → 11** ❌ |
| **orange** | 0.80° | **1.70mm** | 6/20 | 0.601 → **0.398** | 1.096 → 1.290 | 20 → 19 ✅ |
| **clear** | 0.52° | **1.75mm** | 1/20 | 0.462 → **0.232** | 1.163 → 1.445 | **20 → 20** ✅ |

- ★★★ **주황·투명은 50cm 에서도 R 이 1.5~2.0배 좋아진다**(0.601→0.398 · 0.462→0.232). t 대가는 0.2~0.3mm.
  **§23 의 «정합은 근접 전용» 도 조건부로 읽어야 한다** — 거기서 본 원거리 악화는 몸체 randomize 조건이었다.
- 🔴 **`black` 만 무너진다** — §35-2i 의 계통 편향 조건 그대로다(몸체와 flange 가 같은 검정 →
  외곽에 밝기 경계가 없어 `find_edges` 가 융기 능선을 잡는다). **거리가 그 편향을 증폭**할 뿐이다
  (28cm 이동 t 6.2mm 중립 → 50cm 17.5mm 해로움).
- ⚠️ **A3→A1 만 유효한 비교다.** 주황·투명 런의 I·T 행(`--primary full`)은 **sim 렌더 결함**으로 무효다
  (cutout opacity 로 `mask_full == mask_flange`, 몸체 depth 가 배경을 본다 — §35-2h).
  실제로 `clear` 의 I3/T3 는 R 최대 141~154°·t 최대 437~479mm 로 터진다. **분할 문제가 아니다.**

**아래는 `black` 에서의 «어떻게 깨지는가» 진단이고, 그 부분은 유효하다:**

- 🔴 **실패는 초기값이 아니라 이미지가 만든다.** `frame_0004` 는 초기값이 세 팔 모두 정상
  (t 2.06 / 2.39 / 2.91mm)인데 정합 후 **전부 30.8mm**(30.83 / 30.84 / 30.83 — 소수점까지 같다).
  KPI 이탈 프레임도 9/9/8 중 **교집합 7개**다. **세 초기값이 같은 잘못된 국소최적으로 수렴한다.**
- 🔴🔴 **게이트가 구조적으로 못 막는다 — `--gate-deg` 는 «회전» 만 본다.**
  실패 프레임의 **R 은 멀쩡하다**(1.02~1.06°, τ=1.5° 미만). 틀린 건 t 뿐이다.
  §29 의 *"게이트는 축퇴형 폭주 전용이고 계통 편향에는 무력"* 이 **자유도 차원에서** 재현된 것이다.
- ❌ **평행이동 게이트(`τ_mm`)는 답이 아니다.** 넣어 보면 τ≤6mm 에서 20/20 이 회복되는데
  **채택이 0~2 프레임**이다 — 살리는 게 아니라 끄는 것이다. 근접(28cm)에서는 τ 를 어떻게 잡아도
  KPI 가 17~18 로 평평해 **아무 일도 안 한다.** 즉 τ_mm 은 «좋은 정합/나쁜 정합» 을 못 가른다.

  | τ_mm | 50cm I1 채택 / KPI | 28cm I1 채택 / KPI |
  |---|---|---|
  | 없음 | 20 / **11**–20 | 20 / 18–20 |
  | 10 | 6 / 15–20 | 15 / 18–20 |
  | 6 | 1 / **20**–20 | 9 / 17–20 |
  | 2 | 0 / 20–20 | 0 / 17–20 |

- ★★★★ **대신 «런 단위 GT-free 진단» 이 네 조건에서 깨끗하게 갈린다** — **정합 이동량 t 의 중앙값**:

  | 조건 | 이동량 t 중앙 | 정합 효과 |
  |---|---|---|
  | 28cm black | 6.2mm | 중립 (17 → 18/20) |
  | **50cm black** | **17.5mm** | **해롭다 (20 → 11/20)** |
  | 50cm orange | **1.7mm** | 이득 (R ×1.5) |
  | 50cm clear | **1.8mm** | 이득 (R ×2.0) |

  → **규칙: 이동량 t 중앙이 10mm 를 넘으면 그 런에서는 정합을 쓰지 않는다.**
  GT 불필요·추가 촬영 불필요이고 러너가 이미 그 값을 낸다(`stats/metrics_long.csv`).
  ✅ **정정 후에도 살아남았다** — 이 규칙은 «거리» 가 아니라 «정합기가 신호를 찾았나» 를 재기 때문에
  축을 잘못 짚은 초판에서도 옳은 답을 냈다. 이동 R 중앙(2.40 vs 0.52~0.80°)·게이트 후퇴(11 vs 1~6)도 같이 갈린다.
- ✅ 새로운 것은 ① **깨질 때의 크기**(KPI 반토막), ② **게이트가 왜 못 막는지**(자유도 불일치),
  ③ 켤지 말지를 **GT 없이 판정하는 값**이다. ❌ 폐기: *"원거리에서는 끈다"*.
- ⚠️ **조건**: 세 외관 × 50cm(+ black 만 28cm) · 각 n=20 · 몸체 고정색. **주황·투명은 sim 렌더 결함
  때문에 `flange` 경로로만 잴 수 있었다** — 실물 반투명에서 수동 스테레오가 뚫리는지는 여전히 열린 항목 #1 이다.

### 35-2m-7. 실물에서 먼저 확인할 한 줄

```bash
ls runs/<출력>/I1/frame_*/pose_refined.json | wc -l      # 0 이면 진짜 실패, 20 이면 시트만 잘못 가리킨 것
```

- 산출물: `runs/R28chk`(28cm 재현) · `runs/fr_d40`·`fr_d50`(GT 포함 캡처) · `runs/fr40`·`fr50`(입력 3개만) ·
  `runs/R{40,50}_{st,seg,pose}` · conf 0.05 계열 `runs/R{40,50}_{seg_c05,pose_c05}` ·
  오버레이 `runs/R{40,50}_viz`.
- ⚠️ 위 R/t 는 **중앙값**이다(`eval_pose` 표는 평균 — §25-1b). 나란히 놓기 전에 통계를 맞출 것.

## ★★★ 35-2n. 결과 산출물 6종 추가 — **오버레이 겹치기 · 분할+pose · 신호등 · mm 눈금자 · `cam.json` 점검 · 실루엣 거리** (2026-08-22)

실물 1차 실행에서 *"결과를 직관적으로 이해하기 어렵다"* 가 나와 (사용자 요청) 여섯 가지를 더했다.
**전부 추가 촬영 0** 이고, 기존 산출물을 다시 그리거나(`--only ov,ovc,segcmp`) 이미 디스크에 있는
값을 다시 읽는다(`--only scale,stats`). 6프레임 기준 시각 3~9초 + 실루엣 6초.

| # | 산출물 | 무엇을 여는가 |
|---|---|---|
| ① | `overlay_combo.png` | coarse↔refined·경로별 FP 어긋남을 **같은 화소 위에서** |
| ② | `segcmp/seg_compare.png` | 「분할이 틀렸나 pose 가 틀렸나」 |
| ③ | `stats/traffic.png` | 프레임 × 변형에서 **깨진 칸 찾기** (순위표 아님) |
| ④ | mm 눈금자 | 「몇 mm 어긋났나」를 **읽는다** |
| ⑤ | `cam.json` 무결성 경고 | 캘리브레이션 오류 — **모든 GT-free 지표를 통과하는 축** |
| ⑥ | `scale_check.json` | **`baseline` 비의존** 거리 관측 (거리 대조의 네 번째 다리) |

### 35-2n-1. `overlay_combo.png` — coarse·refined·경로별 FP 를 **한 이미지에**

`viz.overlay_pose --combine`. 타일을 나눠 그리면 *"coarse 와 refined 가 얼마나 어긋나는가"* 를
**눈으로 못 잰다** — 같은 화소 위에 놓아야 보인다. 분할 백엔드별 FP 차이도 같은 이유다.

- 들어가는 것: `fp_ns2`·`fp_ism`·`fp_txt` 의 **coarse** + 정합 팔 전부(A1·A2a·A2b·A4·I1·T1) = 최대 9.
- **주석 줄의 색 = 그 예측의 윤곽 색.** 색 규약을 이미지 밖에서 설명하지 않는다.
- 주석: `z` · `mv<도>d/<mm>` (초기값 대비 이동량) · `[G]`(게이트 후퇴) · pose 가 없으면 **`없음`**.
- ⚠️ 마스크는 안 깐다(윤곽이 여럿이라 가려진다) · 축 삼각대는 **첫 예측 하나만** 그린다.

### ★★ 35-2n-2. `segcmp/seg_compare.png` — 분할 **+ 그 pose** 를 한 화면에

`viz.seg_compare`. `--seg` 로 마스크를(채움+실선, `[M]`), **`--pose` 로 그 경로의 FP pose 투영을**
(점선+기울인 십자, `[P]`) 같은 타일에 겹친다. 🔴 **크롭하지 않는다** — 질문이 *"화면 «어디» 를
집었나"* 라서 크롭하면 답이 통째로 사라진다.

🔴 **이 시트만이 두 실패를 가른다.** 마스크만 보던 때에는 구분이 안 됐다:

| 증상 | 판정 | 처방 |
|---|---|---|
| 채움도 점선도 **딴 데** 있다 | ①「분할이 엉뚱한 걸 집었다」 | 참조 세트·프롬프트·**거리대**(preset) |
| 채움은 물체 위인데 **점선만** 어긋났다 | ②「마스크는 맞는데 pose 가 틀렸다」 | depth·초기값·CAD |

**처방이 정반대**라 이 구분이 실물에서 가장 비싸다. 실제로 실물 50cm 에서 ISM 이 화면 가장자리의
작은 물체를 집었고(면적 0.64% · 이탈 0.56) 텍스트 경로만 맞게 집었다(7.03% · 0.06) — ①이었다.

- 기준선: **흰 십자 = 화면 중심**, **회색 타원 = 중심 이탈 0.25**(§34-10 «사전 위치 가드» 를 화면
  좌표로 옮긴 것). 타원 밖에 작게 찍힌 팔이 오선택이다.
- 🔴 **pose 투영은 `full.ply` 로 한다** — 겹쳐 볼 마스크가 `mask_full` 이라 `top_flange` 로 투영하면
  «pose 가 마스크 안에 드는가» 를 못 잰다. 두 메쉬는 **원점이 같아서**(규약) 같은 pose 를 그대로 쓴다.
  검증: sim 50cm 에서 `mask_full` 11.24% vs `I_pose` 11.35% · `T_pose` 11.36% 로 맞물린다.
  `A_exemplar_flange` 행만 flange(1.68%)라 작은 것이 정상이다.
- ⚠️ **pose 팔레트를 마스크와 분리했다** — 이어 쓰면 5번째가 연두라 1번째 초록과 구분이 안 됐다.
- ⚠️ 투영 코드는 `overlay_pose` 에서 **import** 한다. 복제하면 한쪽만 고치게 된다(교훈 #20·#22).

### ★ 35-2n-3. mm 눈금자 — *"몇 mm 어긋났나"* 를 **읽는다**

오버레이 좌하단에 **물체 평면 기준 눈금자**를 그린다(기본 켬, `--no-scalebar` 로 끔).

- 실물에서 관측한 *"10mm 정도 오차"* 같은 판단을 눈대중이 아니라 **자로** 하게 만든다.
  GT 가 없으니 오차를 숫자로 못 내는데, 그 빈자리를 절반쯤 메운다.
- 🔴 **밖에서 환산할 수 없어서 이미지 안에 박는다** — 크롭 박스가 프레임마다 달라
  «이 시트는 1px 이 몇 mm» 가 프레임마다 다르다.
- **10 칸**으로 쪼갠다(5칸이면 100mm 자의 한 칸이 20mm 라 정작 판정하려는 10mm 를 못 읽는다).
  함께 찍는 `원본 1px = N mm` 가 진짜 측정 분해능(`Z/fx`)이다 — sim 50cm 에서 0.68mm/px.
- ⚠️ **물체 평면(pose 의 `z`)에서만 맞다.** 원근이 있어 더 앞/뒤 화소에는 안 맞는다.
- ⚠️ pose 가 없는 타일에는 안 그린다(깊이를 모르면 눈금이 뜻이 없다).

### ★★ 35-2n-4. 신호등 — 프레임 × 변형 (`stats/traffic.png`, 2026-08-22)

`eval.group_stats` 가 **(프레임 × [촬영 3열 + 변형])** 격자를 낸다. 🟢 정상 · 🟡 주의 · 🔴 고장 ·
⬛ pose 없음. **칸의 숫자는 판정을 내린 그 값**이다(이동 mm / 이동 ° / 좌우 px / GATE / 대응점).
`summary.md` 에 한글 표, `summary.json` 에 기계 판독본, `traffic.png` 에 그림(라벨은 영문).

🔴🔴 **«순위표» 가 아니라 «고장 표시» 다 — 이건 구현 선택이 아니라 원리적 한계다.**
GT 가 없으면 *살아남은 것들 중* 어느 쪽이 더 정확한지는 **프레임 단위로 못 정한다**:

| 지표 | 왜 프레임별 순위에 못 쓰나 |
|---|---|
| 적합도 `rms px` | 실패의 rms(1.14~1.88)가 성공 범위(0.64~2.81) **안에 완전히 들어간다** — §26, 교훈 #56 |
| 좌우 일관성 | 프레임당 분해능 **±1~2mm** → «≥20프레임 중앙값으로만 서열화» (§35) |
| 게이트 후퇴 | 「폭주했나」만 말한다. **계통 편향은 안 걸린다** (교훈 #64) |
| 후퇴율로 A↔I↔T 비교 | **무효** — 초기값이 다른 비교다 (교훈 #82) |

→ **서열화는 런 단위(변형 비교 표)에서만**, 이 격자는 «깨진 칸 찾기» 까지다.
- 촬영 3열(노출·마스크·depth)은 **런 자기 자신 기준 강건 z-score** 라 sim 기준선이 필요 없고
  **도메인 갭에 면역**이다(§35-2l-8b 와 같은 설계). 변형 열만 절대 눈금을 쓰고, 그 눈금은
  §35-2m-6(이동 10/20mm) 과 §35(좌우 2/5px) 에서 왔다.
- ⚠️ **🔴 칸이 없다 = «전부 맞다» 가 아니다** — «다 같이 같은 방향으로 틀린» 경우는 이 표가
  원리적으로 못 잡는다(오버레이 육안이 그 몫).

### ★ 35-2n-5. `cam.json` 무결성 경고 (2026-08-22)

리포트 「판정」 첫 줄에 `📷 카메라 — 1920×1200 · fx · B · fx·B · HFOV · 왜곡` 을 찍고,
아래 넷을 **경고로만** 낸다. 🔴 **어떤 경우에도 실행을 막지 않는다**(사용자 방침).

| 검사 | 왜 |
|---|---|
| `left.png` 크기 ↔ `cam.json` `width/height` | 다른 해상도의 프로파일을 복사하면 **`fx` 가 그 비율로 틀리고 거리가 통째로 스케일된다** |
| 왜곡 계수 전부 0 인가 | raw 를 넣으면 ZED X 2.2mm 는 `k1 0.54` 라 전 체인 무효 |
| `fx≈fy` · `cx≈W/2` · `baseline_mm>0` | rectified 쌍의 기본 성질 |

🔴 **캘리브레이션 오류는 모든 GT-free 지표를 통과한다** — `fx·B` 가 `s` 배 틀리면 거리도 `s` 배
틀리는데 투영 크기까지 같이 스케일돼 **오버레이 윤곽이 완벽히 붙은 채로** 거리만 틀린다.
그래서 «입력이 애초에 맞는가» 를 파일 수준에서 한 번 보는 것이 유일하게 싼 방어다.

### ★★★ 35-2n-6. 네 번째 다리 — **실루엣이 말하는 거리** (`eval.scale_check`, 2026-08-22)

🔴 기존 「거리 삼각 대조」의 세 다리 중 **둘이 같은 뿌리**였다: `FP 추정 z` 와 `stereo depth` 는
**둘 다 `Z = fx·B/disparity`** 다. 아무리 잘 맞아도 `fx·B` 가 틀렸으면 사이좋게 틀린다.

```
Z_실루엣 = Z_pose × (모델을 pose 에 놓고 투영한 등가지름) / (관측 마스크 등가지름)
```
물체의 화면상 크기는 `d_px = D_mm·fx/Z` 라 **`baseline` 을 안 쓴다** → stereo 와 독립이다.

- ✅ **부호·응답 검증** (자기순환 금지, 교훈 #8): sim 50cm(참 z **502.2mm**) 의 pose `t` 에
  **×1.2** 를 주입하면 `pose z 601mm → 실루엣 507mm`(비 0.848, 예상 0.833). 방향·크기 모두 맞다.
  남는 1%는 실루엣이 순수 스케일이 아니어서 생기는 잔차 → **수 % 급 경보기**로 쓴다.
- 대조군(주입 0): `FP 502 · stereo 500 · 실루엣 497 · 줄자 500` — 넷이 5mm 안에 모인다.
- 🔴🔴 **`fx` 오차는 이 검사로도 원리적으로 못 잡는다** — 거리와 투영 크기가 **같은 비율로**
  틀려 정확히 상쇄된다(순수 스케일). **`fx` 를 검증하는 관측은 줄자(또는 §7.5c 상대 GT)뿐이다.**
  이 도구가 여는 것은 **`baseline`·시차 스케일** 축이다.
- ⚠️ 마스크와 메쉬가 **같은 대상**이어야 한다(`mask_full`↔`full.ply`). 섞으면 비가 무의미하다(교훈 #26).
- ⚠️ 잘린 프레임 제외(`--max-edge-frac 0.02`) · IQR>0.10 이면 «마스크 품질이 널뛴다» 로 보고 값을 안 쓴다.
- ⚠️ FP 는 마스크도 함께 맞추므로 이미 일부 타협했을 수 있다 → 어긋남은 **하한**으로 읽는다.
- 🔴 **요약 거리는 `median(z_pose) × median(비)` 로 낸다** — 프레임별 `z_실루엣` 의 중앙값을 쓰면 안 된다.
  **곱의 중앙값 ≠ 중앙값의 곱**이라 «보고한 비» 와 «보고한 거리» 가 서로 안 맞는다. 첫 구현이 그랬고
  감사에서 잡았다: **비 1.004 인데 거리 483mm**(pose 499mm 보다 16mm 작음) — 한 프레임의 비 0.769 와
  프레임 간 z 산포 62mm 가 엇갈린 결과다. 고친 뒤 501mm 로 비와 맞는다.
- ★ **비가 1 에서 15% 넘게 벗어난 프레임 수(`n_ratio_outlier`)를 따로 센다** — 거의 항상 **마스크가
  틀린 것**(오선택·부품 결손·그림자)이고, 중앙값이 가려 버리므로 **개수를 보고해야** 한다(교훈 #13 의 형제).
- ⚠️ `n < 6` 이면 «지시적으로만» 이라고 붙인다 — 중앙값·IQR 이 불안정하다.

### 🔴 35-2n-7. 문서·산출물 감사에서 잡은 것 (2026-08-22)

산출물을 늘린 김에 **«리포트가 찍는 값·문구가 실제로 믿을 만한가»** 를 전수로 훑었다.
값 자체는 전부 맞았고(아래 ①), **문구 두 개가 없는 안전을 보고하고 있었다**(②③).

**① 수치 대조는 전부 통과** — `runs/VIZCHK3`(sim 50cm, 참 z **502.2mm**)에서
`report.md` ↔ `report.json` ↔ `stats/metrics_long.csv` ↔ `stats/summary.json` ↔ `traffic` 격자를
기계로 재계산해 대조했다. 리포트 표의 5개 값 · 변형 6종의 n/후퇴/이동° 중앙 · **신호등 36칸 전부 일치.**
거리 세 다리도 참값의 5mm 안이다(FP −0.7 · stereo −2.3 · 실루엣 −4.8mm).

**② «두 독립 추정이 맞는다 ✅» 를 철회했다** → 교훈 **#89**. `FP z` 와 `stereo depth` 는
**둘 다 `fx·B/disparity`** 라 캘리브레이션 축에 무반응인데 ✅ 를 찍고 있었다. 문구를
«다른 경로 (⚠️ `fx·B` 는 공유)» 로 고치고, `baseline` 비의존 다리(§35-2n-6)를 추가했다.

**③ «후퇴율 100%» 인 변형의 지표는 «그 변형» 이 아니다** — 표에 **⬛/`*`** 표시를 넣었다.
게이트가 전 프레임에서 정합을 버리면 최종 pose = 초기 pose 이므로, `A2b 홀 중심 |Δdx| 0.90` 은
*"홀 중심 모드가 낸 값"* 이 아니라 *"그 모드가 **한 번도 안 쓰인** 값"* 이다. 실제로 그 런에서
`A2a`·`A2b`·`A3` 의 좌우 값이 **소수점까지 같다**(0.9012) — 교훈 #21 이 **표 층에서 재발**한 것이다.
→ 이 행으로 말할 수 있는 것은 «이 조건에서는 정합이 전혀 채택되지 않았다» 까지다.

### 35-2n-8. 검증

`runs/VIZCHK` (= `runs/fr50` 를 «입력 3파일만» 으로 10프레임, `n50black` + `--ism --sam3-text`).
8종 시트 전부 생성 확인 · `overlay_sheet` 9열 · `overlay_combo` 9예측 · `segcmp` 분할 4 + pose 3 ·
`traffic.png` (프레임 × [촬영3 + 변형6]) · `scale_check.json`.
전 체인 새 런 `runs/VIZCHK3`(6프레임) 도 종료코드 0 · 산출물 전부 생성.
미검출 프레임에 `없음`/`검출 없음` 이 정직하게 찍히는 것까지 확인했다(conf 0.15 에서 `fp_txt` 8/10).

## ★★★★ 35-2o. **`--mode` — 후보 파이프라인을 넓게 펼친다** (2026-08-22, 사용자 제안)

*"실물로 하다 보면 현재 9가지가 베스트가 아닐 수 있고, 결국 더 다양한 조합을 시도하며 실물 기준
최적을 찾아야 한다. 특히 실물 초반에 이 작업이 중요하다."* (사용자) → 러너에 **`--mode`** 를 넣었다.
**기본값 `default` 는 기존 9팔 그대로**이고, 모드를 겹치면 늘어난다(`--mode contour,init`).

### 35-2o-1. 무엇이 싸고 무엇이 비싼가 — 설계가 여기서 나온다

10프레임·콜드스타트 포함 실측:

| 팔 종류 | 비용 | 왜 |
|---|---|---|
| **정합 변형 1개** | **5초** | FP 재계산이 없다 — 디스크의 초기값 위에 다시 정합만 한다 |
| 분할 1개 | 13초 | |
| FP 1개 | 18초 | |

→ **정합·게이트 축은 10개를 붙여도 50초다.** 여기부터 넓히는 것이 맞고, 실물에서 지금 문제인
*"t 가 10mm 밀린다"* 도 정확히 이 축이다.

### 35-2o-2. 모드

| 모드 | 추가 팔 | 20프레임 추가비용 | 무엇을 여는가 |
|---|---|---|---|
| `quick` | 0 | −40초 | 정합 팔 전부 뺀다. A3·I3·T3 만 — 「끝까지 도는가」 + 분할 3종 |
| `default` | 4~6 | 기준 | **현행 9팔** (A1·A2a·A2b·A4 +I1 +T1) |
| `contour` | +5~6 | +50~60초 | 탐색폭 16/32px · 게이트 0/0.75/3.0° · `--fix-z` 반대쪽 |
| `init` | +1 | +15초 | **하이브리드 초기값**(R=coarse · t=refined, §27-7) — 단일 시점 R 1.5배 |
| `cascade` | +1 | +35초 | coarse-to-fine 32→12→8 (§35-2k-3) — 횡 포획 4 → 24mm |
| `primary` | +1 | +40초 | A 경로를 `--primary full` 로도 (§22 대조) |
| `edge` | +5 | +25초 | 🔴 정합기가 **어느 밝기 경계를 잡는가**: `--polarity` 3종 × `--min-grad` 2종 |
| `refs` | +N | +36초/개 | 🔴 SAM3 **참조 거리대 스윕** (`--refs-sweep`) + `--n-refs` |
| `wide` | +13~14 | +3~4분 | = default + contour·init·cascade·primary·**edge**. **실물 초반 권장** |
| `all` | 전부 | +4~6분 | quick 을 뺀 전부 (refs 스윕 포함). ★ **`--ism`·`--sam3-text` 도 자동으로 켠다** |

⚠️ **`wide` 에 `refs` 는 안 들어간다** — 참조 스윕만 분할·FP 를 통째로 다시 돌아 비용이 자릿수로
다르고, 게다가 **초기값이 달라지는 비교**라 성격이 다르다(교훈 #82). 필요하면 `--mode wide,refs`.

### ★★★ 35-2o-2b. `edge` — 검정 몸체의 «어느 경계를 잡는가»

§35-2i 에서 GT 초기값 검증으로 갈랐듯이, **검정 위 검정**이면 바깥 경계에 밝기 차가 없어
`find_edges` 가 **융기 능선**(안쪽 4~6px)을 잡고 정합기가 그리로 성실히 수렴한다
(`gt_bias_px` −2.04, 프레임마다 같은 방향이라 **게이트가 못 막는다**).
그런데 «어느 경계를 고르나» 노브(`--polarity`·`--min-grad`)를 **한 번도 흔들어 본 적이 없었다.**

| 팔 | 설정 | 뜻 |
|---|---|---|
| `Ed` | `--polarity dark_out` | 물체가 바깥보다 어둡다고 **고정** |
| `Eb` | `--polarity bright_out` | 물체가 바깥보다 밝다고 고정 |
| `Ea` | `--polarity any` | 부호를 안 본다 |
| `Eg3` | `--min-grad 3.0` | 약한 에지를 버린다 (융기 능선 배제 시도) |
| `Eg05` | `--min-grad 0.5` | 약한 에지를 허용 (검정 위 검정에선 진짜 외곽도 약하다) |

✅ **첫 런에서 바로 신호가 나왔다** (sim 50cm black, n=4): `Eb`(bright_out) 이동량 **23.5mm** 🔴 vs
`Ed`·`Ea` 6.2~6.7mm, `Ea`(any) 는 rms **0.962** 로 최저. **극성이 실제로 결과를 가른다** —
기본 `auto` 가 프레임마다 스스로 고르는데, 그 선택이 옳은지는 지금까지 확인한 적이 없었다.

### ★★★ 35-2o-2c. `refs` — 참조 거리대를 데이터가 고르게 한다

참조는 **거리 종속**이라 틀리면 조용히 무너진다(원거리 참조로 근접 질의 시 IoU 0.044).
실물에서 «몇 cm 인지» 를 우리가 모를 수 있으므로(«50cm 인 줄 알았는데 ~70cm» 의심), 스윕한다.

```bash
--mode refs --refs-sweep n30black,n40black,n50black,n70black
#   생략하면 `--preset` 과 **같은 외관의 모든 거리대**를 자동으로 잡는다
```
- 🔴 **없는 프리셋·없는 참조 디렉토리는 종료코드 2 로 거부**한다. 조용히 빠지면 «그 거리대가
  나쁘다» 로 오독된다(교훈 #22 의 스윕판).
- 🔴 **이 스윕을 게이트 후퇴율로 판정하면 안 된다**(교훈 #82) — 참조가 바뀌면 마스크가 바뀌고
  **FP 초기값 자체가 달라진다.** 그래서 리포트에 **분할 쪽 지표**로 된 별도 표를 낸다:
  **검출율 · flange 면적 중앙 · 중심 이탈 중앙**. 팔 라벨에도 `⚠️초기값다름` 을 박는다.
- 읽는 법: ① 검출율이 먼저(0 이면 그 거리대가 안 맞는 것) ② **중심 이탈 >0.25 면 엉뚱한 물체**
  ③ 면적은 **거리의 대리** — `2·√(면적/π)` 로 등가지름을 내 목표 419px(§34-9)과 대조하면
  «실제 거리가 몇인가» 가 나온다.

`--list-modes` 로 확인한다. 오타는 **종료코드 2 로 거부**한다 — 조용히 무시하면 «넓혔다고 믿는
좁은 런» 이 나온다.

### 35-2o-3. 곁들여 구현한 것 둘

- **`refine_contour --gate-ref-dir`** (문서에 ⬜ 미구현으로 남아 있던 것). 캐스케이드를 `--pose-dir`
  로 이어 붙이면 마지막 단의 이동량이 **«직전 단 대비»** 라 한 번에 돌린 팔의 «FP 초기값 대비» 와
  **다른 양**이 된다(교훈 #26) — 그대로 한 표에 놓으면 캐스케이드만 후퇴율이 낮아 보인다.
  기준점을 최초 FP 로 맞춘다. 🔴 **후퇴 자체는 여전히 `--pose-dir` 로** 한다(최초 FP 로 돌아가면
  앞 단이 회수한 것까지 버린다).
- **`eval.hybrid_pose`** — 회전은 `coarse`, 평행이동은 `refined`(§27-7). 기존 `eval.fuse_pose` 가
  같은 일을 하지만 **`--near` 에 `pose_gt.json` 을 요구해 실환경에서 못 쓴다.** 이건 GT 를 안 쓴다.

### 🔴🔴 35-2o-4. 넓히면 «선택 편향» 이 같이 커진다 — 리포트가 경고한다

팔이 늘수록 **잡음만으로도 한 팔이 앞서 보인다.** n=20 에서 팔 18개를 돌리고 «가장 좋아 보이는 것» 을
고르면 그건 대개 그 표본에의 과적합이다. 리포트는 **팔 ≥8 이면 표 바로 밑에** 경고를 찍는다:

- ✅ **사전 정의 규칙**으로 판정한다 — 정합 on/off = 이동량 t 중앙 ≥10mm(§35-2m-6) · refine on/off =
  §32 후퇴율. 사후 선택보다 항상 낫다.
- ✅ 축 하나씩, **같은 초기값 위에서만** 비교한다(A1↔A2a↔A2b, A1↔A4).
  경로 간(A↔I↔T)은 초기값이 달라 **후퇴율로 비교하면 안 된다**(교훈 #82).
- ✅ **좁히는 법**: 넓힌 런에서 후보를 2~3개로 줄인 뒤, 그 후보만 **새로 찍은 20~40장**에서 확인한다.
  같은 데이터에서 고르고 같은 데이터에서 검증하면 그건 검증이 아니다.

### 🔴 35-2o-5. 넓히자마자 함정이 하나 나왔다 — `--fix-z` 의 이동량

sim 50cm 6프레임 `--mode wide`(18팔)에서 **`Cz`(--fix-z) 만 이동량 1.32mm** 였다(다른 팔 8~13mm).
«유일하게 건강한 팔» 처럼 보이는데 **틀린 독법**이다 — `--fix-z` 는 Z 를 묶으므로 `moved_mm` 이
구조적으로 작다. *"정합이 잘 맞았다"* 가 아니라 ***"움직일 수 없었다"*** 다.
→ 표에 **`⚠️Z고정`** 을 붙이고 🔴 판정을 빼며, 판정문에도 경고를 넣었다.
**`--fix-z` 의 우열은 좌우 |Δdx| 와 오버레이로 본다.** (교훈 #26 이 새 축에서 재발한 자리다.)

### ★★★★★ 35-2o-6. sim 20프레임 전체 스윕 — **GT 로 채점해 판정 규칙을 검증했다**

`runs/SWEEP20` · `--mode wide,refs`(참조 5종 자동 스윕) · n=20 · **30팔** · 20분.
sim 이므로 원본 `runs/fr_d50` 의 GT 로 **사후 채점**할 수 있다 — 실환경에서는 불가능한 검사다.

**GT 실제 서열 (KPI = R≤3° 且 t≤5mm)**

| 팔 | R 중앙 | R 최대 | t 중앙 | KPI |
|---|---|---|---|---|
| **`I3` ISM 정합 off** | **0.402** | 0.90 | 2.42 | **20/20** |
| **`Cz` --fix-z** | 0.955 | 1.92 | **1.51** | **20/20** |
| **`A3` 정합 off** | 0.987 | 1.28 | 1.43 | **20/20** |
| `A2a` 홀 윤곽 | 1.021 | 1.28 | 1.46 | 18/20 |
| `T3` 텍스트 정합 off | 0.400 | 1.02 | 2.37 | 17/17 |
| … `A1` 배포본 | 1.028 | 1.84 | 2.24 | 11/20 |
| `Ea` 극성 any | 1.118 | 2.32 | 6.18 | 8/20 |
| `Cg0` 게이트 off | 1.769 | 4.23 | 17.27 | **0/20** |
| `Ccas` 캐스케이드 | 1.835 | 4.25 | 18.48 | **0/20** |

✅ **리포트의 GT-free 판정이 그대로 맞았다** — *"A1/I1/T1 정합을 쓰지 말 것(이동량 17.7/15.9/16.0mm
≥10mm) → A3/I3/T3 으로"* 라고 냈는데, 실제 최상위가 정확히 **A3·I3·T3** 이다. **GT 없이 옳은 답을 냈다.**

### 🔴🔴 35-2o-6b. 지표별 «실제 KPI 와의 상관» — 셋 중 하나만 쓸 만하다

30팔 × KPI 로 상관을 냈다 (**음수 = 지표가 작을수록 정확 = 지표가 옳다**):

| GT-free 지표 | r | 판정 |
|---|---|---|
| **좌우 \|Δdx\|** | **−0.94** | ★★★ **팔 서열을 거의 그대로 예측한다.** 우열을 가려야 하면 이것 |
| 정합 rms | **−0.05** | 🔴 **사실상 무관** — 교훈 #56 의 실증. rms 로 고르면 안 된다 |
| 게이트 후퇴율 | **+0.82** | 🔴🔴 **부호가 반대다** — 아래 |
| 이동량 t 중앙 | −0.32 | 약하다. 단 **런 단위 on/off 판정**(≥10mm)에는 유효했다 |

🔴🔴 **«후퇴율이 낮은 팔이 좋은 팔» 이 아니다.** 후퇴 = «정합을 안 쓰고 초기값을 냈다» 이므로,
**정합이 해로운 조건에서는 많이 버릴수록 정확해진다.** 후퇴율은 «정합이 얼마나 개입했나» 의
역지표일 뿐 **품질 지표가 아니다.** → §32 판정 절차(후퇴율 낮은 쪽)는 **«같은 정합 설정에서
초기값만 바꾼» 비교에만** 쓴다. 리포트에 이 경고를 표 밑에 박았다.

⚠️ `Ea`(극성 any)가 **후퇴율 40%(최저) · rms 1.132(최저) · 이동량 10.56mm(최저)** 로 세 지표에서
1등인데 **KPI 는 8/20 으로 하위권**이다. 세 지표만 보고 골랐으면 정확히 틀렸을 것이고,
**좌우 \|Δdx\| 2.40(나쁨)만이 옳게 가리켰다.**

✅ 반대로 `Cz`(--fix-z)는 이동량 규칙을 **적용하면 안 되는** 팔인데(§35-2o-5), 좌우 \|Δdx\| **0.73**
(정합 켠 팔 중 최저)이 그것이 20/20 임을 옳게 가리켰다 — «`--fix-z` 의 우열은 좌우 \|Δdx\| 로
본다» 는 처방이 실제로 작동했다.

### 🔴 35-2o-6c. 참조 스윕 표에 **사각지대**가 있었다 — 고쳤다

`n25black` 참조가 스윕 표에서 **검출 20/20 · 면적 중앙 35,982 · 이탈 중앙 0.015** 로 완벽해
보였는데, GT 로 채점하니 **3프레임이 90~115° 뒤집혀 KPI 9/20**(전체 최하위권)이었다.
원인은 한 프레임의 마스크가 **5,234px**(중앙의 0.15배)로 쪼그라든 것 — **중앙값이 통째로 가렸다.**
**교훈 #6·#13(«평균·중앙값이 고장을 숨긴다»)이 내가 방금 쓴 표에서 그대로 재발했다.**

→ 표에 **`면적 최소` · `쪼그라든 장`(중앙의 0.5배 미만) · `이탈 최대`** 를 추가했다.
고친 표에서 `n25black` 은 **쪼그라든 장 1 🔴 · 이탈 최대 0.288 🔴** 로 즉시 걸린다.

### 🔴 35-2o-7. 전 산출물 교차 검증에서 결함 둘을 더 잡았다 (2026-08-23)

`--mode all`(= `wide,refs`)로 30팔을 낸 뒤 **모든 산출물이 30팔을 빠짐없이 담고 있는지** 기계로
대조했다. 값은 전부 맞았지만 **구조적 누락 둘**이 나왔다.

**① 🔴 «정합 off» 팔(A3·I3·T3)이 통계 한 벌에서 통째로 빠져 있었다.**
그 셋은 `<out>/A3/` 같은 자기 디렉토리가 없고 pose 가 `fp_ns2/pose_coarse.json` 에 있다.
러너가 `group_stats --variants` 에 **정합 팔만** 넘기고 있어서, `metrics_long.csv`·`summary.json`·
신호등에서 빠졌다. 🔴 **하필 GT 채점에서 1~3위였던 팔들**이다 — 「분석용 CSV 에 승자가 없는」
상태였다. → `group_stats --alias A3=fp_ns2:pose_coarse.json` 을 만들어 붙였다.
고친 뒤 **CSV 30변형 · 신호등 30변형**으로 전부 들어온다.

**② 🔴 겹쳐 그린 오버레이가 30팔에서 못 쓰게 됐다.**
팔레트가 8색이라 색이 **4번 순환**하고, 주석 30줄(16px)이 타일 460px 를 **통째로 덮어** 물체가
안 보였다. → **역할을 나눴다**: `overlay_combo.png` 는 **항상 `default` 팔만**(경로별 FP coarse 3 +
A1·A2a·A2b·A4 + I1 + T1 = 9), 늘어난 팔은 **열로 나란히** 놓는 `overlay_sheet.png` 에서 본다.
안전망으로 `overlay_pose --max-combine`(기본 8)을 두고, 잘리면 **로그와 범례 양쪽**에 밝힌다
(조용히 자르면 교훈 #22).

**통과한 검사** — `runs/SWEEP20`(30팔 × 20프레임):

| 검사 | 결과 |
|---|---|
| 팔 × 산출물(csv·신호등·summary·lr·report 표) | ✅ 30/30 전부 포함 |
| `summary.json` ↔ `metrics_long.csv` (n·후퇴·이동°·\|Δdx\| 중앙) | ✅ 전부 일치 |
| `report.md` 변형 표 ↔ `summary.json` | ✅ 전부 일치 |
| 신호등 격자 ↔ CSV 재계산 | ✅ **600칸** 전부 일치 |
| `report.md` 거리 3종 ↔ `report.json`·`scale_check.json` | ✅ 496 / 494 / 490 일치 |
| 시각 산출물 14종 존재 | ✅ 전부 |
| `overlay_sheet` 열 수 | ✅ **30열** (= 팔 수) |

### 🔴 35-2o-8. `--mode all` 이 «전부» 가 아니었다 (2026-08-23, 고침)

**I그룹(ISM)·T그룹(텍스트)은 `--mode` 가 아니라 별도 플래그**(`--ism`·`--sam3-text`)다. 그래서
`--mode all` 만 주면 **경로 둘이 통째로 빠져** 팔이 30 → 24 가 됐다. **이름이 약속을 안 지킨 것**이라
`all` 이 두 플래그를 **자동으로 켜게** 고쳤고, 조용히 바꾸지 않도록 **켰다는 사실을 로그로 남긴다**.
`wide` 는 강제하지 않고 **꺼져 있으면 경고만** 낸다(그쪽은 정합 축이 목적이라 강제가 과하다).

⚠️ **그래도 «all» 은 «구현된 모드 전부» 이지 «가능한 파이프라인 전부» 가 아니다.** 남은 것:

| 남은 것 | 왜 |
|---|---|
| `prompt`(텍스트 낱말 스윕) · `band`(rim) · `stereo`(`--scale`) · `jitter`(포획 반경) · `init2` | **미구현** — 후보로만 적어 뒀다(§35-2o-2 표 밖) |
| P1 2단계 · P2(G9) · P3(5시점 융합) · P4(G9+G10) | **구조적 불가** — 촬영 2회 이상 또는 hand-eye. `cam1_T_cam2` 가 «부정확» 한 게 아니라 **존재하지 않는다** |
| GT 대비 R/t/KPI | **실물에는 원리적으로 없다.** sim 런에서는 `eval_pose` 로 사후 채점할 수 있고 §35-2o-6 이 그 결과다 — 러너가 자동으로 하지는 않는다 |

⚠️ **러너가 쓰는 «문서» 는 `report.md` 와 `stats/summary.md` 둘뿐이다** — 그 런의 리포트이지
**프로젝트 문서(`docs/*.md`)가 아니다.** `RESULTS.md`·`CLAUDE.md` 갱신은 사람이 한다.

### 35-2o-9. 검증

`runs/MODECHK`(sim 50cm 6프레임, `--mode wide --ism --sam3-text`) — **18팔 전부 생성**,
오버레이 **18열**, 신호등 **18열**, 선택 편향 경고 작동, `--fix-z` 가드 작동.
`runs/MODE2`(4프레임, `--mode wide,refs --refs-sweep n30black,n40black,n70black`) —
**28팔**(오버레이 28열 · 신호등 25변형 + FP coarse 3), 참조 스윕 표 생성.
✅ **기본값 회귀 확인**: `--mode` 를 안 주면 변형 6 + FP coarse 3 = **기존 9팔 그대로**다.
부수 확인: `Cg0`/`Cg07`/`Cg3` 는 대응점·rms·이동량이 **완전히 같고 후퇴율만 다르다**(0% / 83% / 33%)
— 게이트가 «정합을 바꾸는 것» 이 아니라 «채택 여부만 정하는 것» 임이 그대로 보인다.

## ★★★★ 35-2p. 판단용 그림 3종 — **`spatial_vision.viz.result_charts`** (2026-08-23)

**동기 (사용자)**: *"다른 PC 에서 결과만 보고 **직관적으로 판단**할 수 있고, 필요한 부분은
자세히 들여다보며 **스스로 분석**할 수 있어야 한다."* 산출 데이터(CSV·JSON)는 이미 다 있으니
**시각화만** 더한다. 추가 촬영 0 · 추가 계산 0(기존 산출물 재사용) · 20프레임 30팔에 **2초**.

러너가 `report.json` 을 쓴 **직후** 자동으로 돌고, `report.md` 「직접 분석할 것」 **맨 앞**에
읽는 법과 함께 꽂힌다. 단독 실행도 된다:
`envs/pose/bin/python -m spatial_vision.viz.result_charts --root runs/<out>`

### ★★★ 35-2p-1. `stats/distance.png` — 거리 4다리를 **선으로** 겹친다

지금까지 거리 대조는 리포트의 **글 몇 줄**이었다. 그런데 이 축은 **`fx·B` 오차**를 보는 축이고,
🔴 **네 다리 중 둘은 원리적으로 «같이 틀린다»**(`FP z` · `stereo depth` 는 둘 다 `Z = fx·B/disparity`,
교훈 #89). 그래서 *"어느 선이 어디서 갈라지는가"* 가 판정이고, 그건 겹쳐 그려야 보인다.

- 위 칸 = 네 선(+ **중앙값 상자**), 아래 칸 = **FP 대비 차** + KPI ±5mm 밴드.
- **읽는 법**: 실루엣만 갈라짐 → `baseline` · 셋이 붙었는데 줄자만 다름 → **`fx`**(내부 관측
  전부를 통과하는 순수 스케일) · 넷 다 맞으면 ✅.
- ⚠️ **줄자는 «한 값» 이다** — 프레임마다 거리가 달랐으면 `tape − FP` 는 오차가 아니라 자세 변화다.
  그래서 **z 산포 >10mm 면 그 선을 안 그리고** 범례에 이유를 적는다(교훈 #26 의 정신: 비교 전에
  «같은 양인가»부터 묻는다). 그때는 중앙값 상자만 비교한다.
- ⚠️ 이상치 하나가 축을 다 먹지 않게 아래 칸은 **강건 범위로 자르되**, 잘린 점의 **개수와 최댓값을
  글로 남긴다**(조용히 숨기지 않는다).
- 🔴🔴 **초판이 «경로를 섞어» 그리고 있었다 (2026-08-23 고침, 교훈 #26 재발).**
  `FP z` 는 `fp_ns2`(A 경로)에서 오는데 `scale_check` 는 **`fp_ism`(I 경로)** 의 pose 를 쓴다.
  그런데 아래 칸에서 `실루엣 − FP z` 를 그렸으니 **두 경로의 z 차가 실루엣 잔차에 섞였다**
  (`runs/ALL20` 실측: 참값 **+0.75mm** 를 **+1.50mm** 로 보고). 게다가 중앙값 상자는
  실루엣 12장 ↔ FP 20장으로 **부분집합까지 달랐다**(485 vs 496 = 11mm 처럼 보였다).
  이 런은 두 경로가 0.4mm 차라 피해가 작았지만, **20mm 어긋난 런이었다면 «실루엣이 갈라졌다
  → baseline 이 틀렸다» 는 정반대 처방**이 나온다. → 세 가지를 고쳤다:
  **① 잔차는 «그 자신이 쓴 pose» 와만 뺀다**(`실루엣 − pose[fp_ism]`) **② 경로가 다르면
  그 pose 선과 «경로 차» 선을 함께 그리고 빨간 경고를 박는다** **③ 중앙값은 «실루엣이 쓸 수
  있었던 프레임» 부분집합에서 낸다**(전 프레임 값은 따로 병기). 출처를 알 수 있도록 러너가
  `report.json` 에 **`capture_pose_dir`** 을 남긴다.
- ✅ `runs/ALL20`(sim 50cm, n=20, 줄자 500) 고친 뒤: 같은 12프레임에서 **FP 488 · stereo 486 ·
  실루엣 485 · pose[fp_ism] 488 · 줄자 500**, 실루엣 잔차 **+0.75mm** — 리포트의 «비 1.0015» 와 같은 양이다.
- ✅ `runs/SWEEP20`(sim 50cm, n=20, 줄자 500): 중앙 **FP 496 · stereo 494 · 실루엣 485 · 줄자 500**.
  아래 칸에서 `stereo − FP` 가 **−2mm 안팎의 일정한 편향**(랜덤 산포 아님)으로 즉시 보이고,
  실루엣은 ±2mm 로 흩어지되 KPI 밴드 안이다. **frame_2 의 실루엣 −116mm** 는 §35-2n-6 이
  «비 이상 1장» 으로 세던 것과 같은 프레임이다 — 표에서는 숫자 하나였는데 그림에서는 못 놓친다.

### ★★★ 35-2p-2. `stats/ranking.png` — 팔 서열을 **정렬해서** 낸다

좌우 |Δdx| 는 **팔 서열을 맞히는 유일한 GT-free 지표**인데(r = −0.94, §35-2o-6b)
`variants.png` 4패널 중 **한 칸의 상자그림**이라 30팔이면 x축이 뭉개져 못 읽었다.

- |Δdx| **중앙값 오름차순** 가로 막대(위가 1등), 수염 = p90, 옆에 `med / p90 / gate%`.
- 🔴 **비교 불가 팔을 색과 꼬리표로 격리**한다 — `*gated NN% (med=init)` · `Z-fixed`(이동량·dz 가
  구조적으로 작다, §35-2o-5) · `init!=`(참조가 달라 **초기값 자체가 다른** 비교, 교훈 #82).
  표시가 붙은 팔은 나란히 놓으면 안 된다.
- 🔴🔴 **문턱은 «100%» 가 아니라 «과반» 이다** (2026-08-23 정정, `runs/ALL20` 에서 발견).
  처음에는 *전량 후퇴* 만 표시했는데, **후퇴율 50% 를 넘으면 중앙값 자체가 후퇴 프레임에서
  나오므로** 그 막대는 «그 팔의 결과» 가 아니라 사실상 **초기값**이다. 실제로 A2a(후퇴 19/20)의
  \|Δdx\| 중앙이 A3(정합 off)와 **소수점까지 같게**(0.695px) 나왔는데 100% 기준만 걸어 뒀더니
  **정확히 그 오독을 못 막았다** — 교훈 #21(«소수점까지 같으면 «차이 없음» 이 아니라 «적용 안 됨»»)의
  재발이다. → `gate ≥50%` 를 회색 + `med=init` 으로 바꿨다.
- ⚠️ 함께 찍는 `gate %` 는 **품질 지표가 아니다**(r = **+0.82**, 부호 반대) — 범례 제목에 박아 뒀다.
- ✅ **§35-2o-6 의 GT 채점을 그림이 그대로 재현한다** (`runs/ALL20`, `--mode all` 30팔 · n=20).
  문턱을 고치고 나니 **«비교 가능»(파랑) 이 6팔로 줄고, 그 상위 3이 T3 0.63 · A3 0.70 · I3 0.77 —
  GT 채점 1~3위(T3 17/17 · A3 20/20 · I3 19/20)와 정확히 일치**한다.
  나머지 24팔은 전부 «중앙값이 초기값» 이거나 «초기값이 다름» 이라 회색·갈색으로 빠진다.

### ★★ 35-2p-3. `stats/heatmap.png` — 프레임 × 팔, **행 효과와 열 효과를 가른다**

상자그림은 «어느 프레임» 과 «어느 팔» 을 뭉갠다. 히트맵 + **주변 중앙값 띠**가 그 둘을 분리한다.

- 왼쪽 = |Δdx|, 오른쪽 = 정합 이동량. 흰 점 = 게이트 후퇴 · 빈 칸 = 그 팔이 안 내는 값
  (정합을 안 하는 A3·I3·T3 의 이동량) · 색은 **p95 에서 자른다**(꼬리 하나가 색을 다 먹지 않게).
- **오른쪽 띠 = 프레임 중앙값(행)** · **아래 띠 = 팔 중앙값(열)**. 가로줄이 뜨면 «그 프레임이 어렵다»,
  세로줄이 뜨면 «그 팔이 나쁘다».
- ✅ `SWEEP20` 에서 **frame 4·8·16 이 전 팔에 걸쳐 어두운 가로줄**로 나온다 — 팔을 아무리 바꿔도
  안 되는 프레임이라 **오버레이를 열어야 할 대상**이고, 팔 비교에서는 빼고 봐야 한다.
- 🔴 **프레임 단위 «순위표» 가 아니다** — GT 없이 살아남은 것들 중 우열은 프레임 단위로 원리적으로
  못 정한다(#56·#64). 이 그림은 **패턴을 찾아 그 프레임을 열기 위한** 것이다.

### 🔴 35-2p-4. 곁들여 잡은 결함 — `--report-only` 가 **줄자를 버리고 있었다**

`--true-distance-mm` 없이 `--report-only` 로 다시 내면 `report.json` 의 `true_distance_mm` 이
`null` 이 됐다. **줄자는 그 «촬영» 의 물리량이지 그 «실행» 의 인자가 아니다** — 그리고
**`fx` 축을 보는 유일한 외부 다리**라 사라지면 거리 사각 대조가 통째로 반쪽이 된다.
→ 없으면 `run_meta.json` 에 남은 값을 **물려받고 그 사실을 로그로 남긴다.**

### ★★★ 35-2p-5. `--mode all` 전수 검증 — `runs/ALL20` (2026-08-23)

**한 줄로 30팔을 다 돌렸다**(sim 50cm `black` 20프레임, 콜드 스타트 포함 **815.6초 = 13.6분**):

```bash
envs/pose/bin/python tools/run_group_a.py --in runs/fr50 --out runs/ALL20 \
    --preset n50black --mode all --text-prompt "black plastic box" --true-distance-mm 500
```

- ✅ **`--mode all` 이 경로까지 켠다** — `--ism`·`--sam3-text` 를 안 줬는데 로그가
  *"`--mode all` → --ism (I그룹) 를 켠다"* 를 찍고 30팔이 나왔다(§35-2o-8 수정 확인).
- ✅ **GT-free 판정 3건이 전부 맞았다** (GT 채점으로 사후 확인):

  | 리포트가 GT 없이 내린 판정 | GT 채점 |
  |---|---|
  | *"A1·I1·T1 정합을 쓰지 말 것 — 이동량 t 중앙 16~17mm"* → **A3·I3·T3 로 결론** | **A3 20/20 · I3 19/20 · T3 17/17** vs A1 11/20 · I1 12/20 · T1 11/17 ✅ |
  | *"§32 절차 → coarse (`--no-stage2` 유지)"* | A3(coarse) 20/20 vs A4(refined 초기) **11/20** ✅ |
  | 참조 스윕: `n25black` 만 **쪼그라든 장 1 · 이탈 최대 0.288** 🔴 | `R_n25black` **KPI 7/20 · R 최대 119.5°** — 30팔 중 최악권 ✅ |

- ✅ **`ranking.png` 상위 = GT 상위** (위 §35-2p-2). ⚠️ 단 **문턱을 고친 뒤에야** 그렇다.
- 🔴 **`Ccas`(캐스케이드)가 30팔 중 최하위**(\|Δdx\| 3.13px · GT **0/20** · t 중앙 18.5mm)다.
  §35-2k 에서 **깨끗한 sim 근접**에 맞춰 튜닝한 구성인데 **50cm 검정 몸체**에서는 넓은 탐색폭이
  그대로 «엉뚱한 에지를 더 멀리서 찾아오는» 쪽으로 작동한다. **조건이 바뀌면 튜닝값이 뒤집힌다.**
- ⚠️ 이 런 전체가 *"검정 몸체 50cm 에서는 정합을 끈다"* 는 §35-2m-6 판정의 재확인이다 —
  **정합을 켠 27팔이 전부 정합을 끈 3팔보다 나쁘다.** 넓히기의 값어치는 «이길 팔을 찾는 것» 이
  아니라 **«끄는 게 맞다는 것을 27가지 방법으로 확인하는 것»** 이었다.
- 🔴 **선택 편향 경고가 작동**했다(팔 30 × 프레임 20). 위 결론을 확정하려면 **새로 찍은 20~40장**이 필요하다.

#### ★★★★ 「결과가 엉키지 않았나」 배선 감사 → **`tools/audit_run.py` 로 상설화** (사용자 질문, 2026-08-23)

*"같은 결과를 다른 파이프라인에 그려 준 경우는 없나"* — 주장하지 않고 **기계로 확인**했고,
**일회성 확인으로 두지 않고 도구로 만들어 러너에 물렸다**(손으로 하는 검사는 결국 안 하게 된다).
`report.md` 의 **맨 앞 관문**(「배선 감사」 절)으로 들어가고, 실패하면 **종료코드 1** 이다.
⚠️ **«배선» 검사지 «정확도» 검사가 아니다** — 값이 맞는지는 GT 가 있어야 하고 real 에는 GT 가 없다.

| 검사 | 결과 |
|---|---|
| 33팔 pose 파일 **해시** | **33종 전부 고유** — 두 팔이 같은 산출물을 공유한 경우 0 ✅ |
| 후퇴 프레임 = **자기** 초기값인가 | 11팔 전부 ✅ (A4←`fp_s2` · H1←`fp_hyb` · I1←`fp_ism` · T1←`fp_txt` 로 **각자 다른 출처**를 정확히 물었다). 비후퇴 프레임이 초기값과 «같아 버린» 경우 **0** |
| `metrics_long.csv` ↔ 원본 JSON | 600행(30×20)의 `ddx`·`moved_mm`·`gated`·`tz` **전부 일치** ✅ |
| `lr` 태그 ↔ pose 디렉토리 | 27 직결 + **3 별칭**(A3←`fp_ns2` · I3←`fp_ism` · T3←`fp_txt`) = 30 ✅ |
| `overlay_sheet` 열 수 | 폭 11,400 / 타일 380 = **정확히 30열** ✅ · `overlay_combo` 는 의도대로 **9팔만** |
| `segcmp` 마스크↔pose 짝 | A/I/T **경로별로 올바르게 짝지어짐** ✅ (`진단용_full` 만 pose 없음 — 설계대로) |
| `traffic` 열 | 33 = 촬영 3 + 변형 30 ✅ |
| 디스크 팔 ↔ CSV | `Ccas_s1`·`Ccas_s2` 만 빠짐 — **팔이 아니라 캐스케이드 중간 단**이라 의도된 제외 |

- 🔴 **여기서 실제로 결함 하나가 나왔다** — 위 §35-2p-1 의 «경로 섞임». 다른 8개 검사는 통과.
- ⚠️ `Ccas_s1/s2` 는 디렉토리가 **팔처럼 생겨서** 실제로 내가 GT 채점에 잘못 포함했다 →
  리포트가 *"팔이 아니라 중간 단"* 을 한 줄로 밝히게 고쳤다. **산출물이 팔처럼 생기면 그렇게 읽힌다.**
- ★ **감사기 자체를 «고장 주입» 으로 검증했다**(교훈 #8 — 자기순환 검증 금지). `A2b` 의 pose 를
  `A1` 것으로 덮어쓰자 **①③이 독립적으로 잡고 ②까지 걸려 종료코드 1** 이 났다
  (*"같은 산출물을 공유: [['A1','A2b']]"* · *"CSV 불일치 10건"*). **검사기가 통과만 하는지도 확인해야 한다.**
- ★ **검사기는 상수를 안 박는다** — 초기값 출처를 `meta_contour.json` 의 `init` 에서 **읽는다**.
  박아 두면 러너가 바뀔 때 검사기가 **조용히 틀린다**(교훈 #22 «틀린 값을 조용히 돌려주지 않는다»).

### ★★★ 35-2p-6. 재실행 재현성 — `runs/ALL20` · `ALL20B` · `ALL20C` 3회 (2026-08-23)

같은 명령을 **처음부터 세 번** 돌려(`ALL20` 815.6s · `ALL20B` 804.2s · `ALL20C` 799.5s)
*"결론이 런마다 흔들리는가"* 를 봤다. GPU 스테이지는 결정론이 아니므로(교훈 #24)
**숫자는 흔들리는 게 정상이고, 흔들리면 안 되는 것은 «결론» 이다.**

| | ALL20 | ALL20B | ALL20C |
|---|---|---|---|
| GT-free 서열, «비교 가능» 팔 상위 3 | T3 0.63 · **A3** 0.70 · I3 0.77 | T3 0.70 · **I3** 0.77 · A3 0.84 | **A3** 0.64 · T3 0.67 · I3 0.72 |
| 같은 서열 하위 3 | Cg3 2.19 · Ea 2.21 · Cg0 2.92 | Cg3 2.19 · Ea 2.22 · Cg0 2.92 | Cg3 2.07 · Ea 2.21 · Cg0 2.93 |
| GT 상위 (KPI) | Cz·A3 20/20 · T3 17/17 | Cz·A3·I3 20/20 · T3 17/17 | Cz·A3 20/20 · T3 17/17 |
| 리포트 판정 | A1·I1·T1 정합 끄기 → **A3·I3·T3** | **동일** | **동일** |
| §32 절차 | coarse (`--no-stage2`) | **동일** | **동일** |
| 참조 스윕 경보 | `n25black` 만 🔴 | **동일** | **동일** |
| 배선 감사 | 7항목 통과 | **통과** | **통과** |

- ✅ **결론이 세 번 다 같다.** «비교 가능» 팔 집합도 **{T3, A3, I3, Cg3, Ea, Cg0} 로 동일**하고,
  상위 3(T3·A3·I3)과 하위 3(Cg3·Ea·Cg0)의 **구성원이 안 바뀐다.** 흔들리는 것은 **상위 3 안의 순서**뿐인데
  셋 다 GT KPI 19~20/20 이라 «구분이 안 되는 팔들의 순서» 다.
- ⚠️ **GT KPI 는 30팔 중 12팔만 세 런에서 완전히 같고, 최대 3장(15%p) 흔들린다**
  (`R_n70black` 11/10/13 · `R_n40black` 14/12/13 · `H1` 11/11/13).
  🔴🔴 **런 두 개의 KPI 가 1~3장 다른 것은 «설정 효과» 의 증거가 아니다** — 교훈 #24 의 정량판이다.
- ★ **결론에 쓰는 팔들은 오히려 안 흔들린다**: `A3` 20/20/20 · `T3` 17/17/17 · `Cz` 20/20/20 ·
  `Ccas` 0/0/0 · `Cg0` 0/0/0. **흔들리는 것은 중간 순위 팔**(참조 스윕·`H1`·`Cs32`)이고,
  그것들은 애초에 «구분이 안 되는» 구간에 있다. → **KPI 1~3장 차로 중간 팔의 우열을 말하지 않는다.**
- ⚠️ 이 재현성은 **같은 입력·같은 설정**에 대한 것이다. 실물에서 «새로 찍은 20~40장» 이 필요하다는
  요구(§35-2o-4)는 그대로다 — 그건 표본 편향 문제이지 재실행 잡음 문제가 아니다.

★★ **부수 발견 — 검정 몸체에서 «정합을 끈다» 의 대안은 «Z 를 묶는다» 다.** 두 런 모두에서
`Cz`(`--fix-z`)가 **A3(정합 off)와 사실상 동률**이다:

| | 좌우 \|Δdx\| | GT KPI | R 중앙 | t 중앙 | 후퇴 |
|---|---|---|---|---|---|
| `A3` 정합 off | 0.70 / 0.84 | **20/20 · 20/20** | 0.976 / 0.906 | 1.55 / 1.50 | — |
| `Cz` 정합 + `--fix-z` | 0.70 / 0.70 | **20/20 · 20/20** | 0.933 / **0.901** | 1.60 / 1.59 | 15/20 (양쪽 동일) |
| `A1` 정합 (Z 자유) | 1.72 / 1.74 | 11/20 · 11/20 | 1.116 / 1.013 | 2.02 / 2.14 | 11/20 |

- **검정 몸체 정합 실패는 «Z 로 샌다»** — Z 를 묶으면 나머지 자유도는 멀쩡히 수렴한다.
  §35-2m-6 이 *"t 만 틀린다(최대 30.8mm)"* 라 한 것과 같은 지문이다.
- 🔴 **그래도 배포 권고는 `A3`(정합 off)다.** `Cz` 의 이득이 R 0.03~0.07° 로 미미한데
  **`--fix-z` 는 «Z 가 이미 맞다» 를 가정**하고(교훈 #26·§35-2o-5의 `⚠️Z고정` 표시), 그 가정이
  깨지면 조용히 틀린다. 이득 대비 전제가 비싸다.
- ⚠️ GT 없이 이 둘을 가릴 수 없다 — \|Δdx\| 가 0.70 으로 **같다**. **런 단위 서열조차 못 내는
  구간이 있다**는 실례다(그래서 «동률» 이라고 적는다).

### 35-2p-7. 검증

- `runs/SWEEP20`·`runs/ALL20`(30팔·20프레임) — 3장 전부 생성, 2초. 축 라벨·범례가 30팔에서도
  안 겹친다 (팔 이름은 **아래 «열 효과» 축에만** 찍고, 범례는 **그래프 밖**으로 뺐다).
- **퇴화 경로**: 빈 디렉토리에 돌리면 3장 모두 «왜 못 그렸는지»를 각각 찍고 종료코드 1
  (`report.json` 없음 / `metrics_long.csv` 없음). 🔴 **조용히 빠지지 않는다**(교훈 #21).
- 러너 안에서는 **실패해도 본 파이프라인을 안 죽인다**(교훈 #79) — 대신 리포트에 이유를 남긴다.

## 35-2b. 오버레이 시트 — **GT-free 지표가 못 보는 축을 보는 유일한 수단** (2026-08-13)

러너가 마지막에 `viz.overlay_pose` 를 돌려 `overlay_sheet.png` 와 `overlay/overlay_frame_*.png` 를 낸다.

- **행 = 프레임 · 열 = 변형**(경로별 FP coarse `fp_ns2`·`fp_ism`·`fp_txt` + A1·A2a·A2b·A4 + I1 + T1
  = **최대 9**, §35-2n-1),
  **행 안에서 크롭 박스를 공유**한다 —
  변형마다 따로 크롭하면 어긋남을 눈으로 못 비교한다.
- 그리는 것: **초록 = 예측 실루엣 윤곽** · 파랑 반투명 = 정합에 쓴 마스크(기본 α 0.22, `--mask-alpha 0` 으로 끔)
  · **축 삼각대**(물체 원점 X/Y/Z 60mm, 글자 라벨) · 주석 `z` · **`moved`**(초기값 대비 이동량) · **`[GATED]`**.
  GT 가 있으면(sim) 빨강으로 GT 를 덧그리고 주석이 R/t 오차로 바뀐다.
- 🔴 **왜 필요한가 — GT-free 지표는 전부 «자기 일관성» 이다.** 후퇴율·좌우 일관성·rms 는 *"결과가
  자기들끼리 맞는가" 만* 말하고 **«다 같이 같은 방향으로 틀린»** 경우(= §29 의 계통 편향 축, 게이트가
  못 막는 그 축)를 **원리적으로 못 잡는다.** 사진 위에 겹쳐 보는 것만이 그 축을 본다.
  이 프로젝트에서 기하 오류를 실제로 잡아낸 것도 지표가 아니라 눈이었다(횡단 정리 #39·#46).
- 읽는 법: 어긋남이 **프레임마다 한 방향으로 일관** → 계통 편향(외곽 융기·윤곽 불일치) ·
  **제각각** → 초기값 폭주(게이트가 잡는 쪽).
- ⚠️ **`stages.refine_contour --debug` 와 색 규약이 다르다**(거기선 초록=GT · 노랑=모델 샘플).
  두 도구 모두 **범례를 이미지에 찍는다** — 시트를 인용할 때 색을 말로 옮기지 말 것.

## 35-2c. 진단 시트 — **«어디서 깨졌는가»** (2026-08-13)

`viz.diag_sheet` — 프레임 하나를 **6패널**로 펼친다. 러너가 `diag/diag_sheet.png` + `diag/diag_frame_*.png`
를 낸다. `overlay_pose` 가 *«맞는가»* 를 본다면 이쪽은 *«어디서 깨졌는가»* 를 본다.

| 패널 | 내용 | 캡션 수치 |
|---|---|---|
| 1 원본 | `left.png` | 밝기 중앙값 · **포화율 · 암부율** ← 분할이 0 이면 여기부터 |
| 2 `mask_full` | FOUP 전체 (초록) | 면적비 · 등가지름 · 조각 수 |
| 3 `mask_flange` | top flange (주황) | 면적비 · **등가지름**(목표 419px, §34-9) |
| 4 depth | TURBO, 무효=검정, flange 윤곽 흰색 | `scale[obj]` 구간 · **`flange plane rms`** |
| 5 `valid` | 흰=유효 / **마젠타=무효** | 전체 · flange · **링** |
| 6 pose | 초록 윤곽 + 축 삼각대 | `z` · `moved` · `[GATED]` |

- 🔴 **정규화 구간을 «물체» 로 잡는다.** 전체 유효 픽셀의 p2~p98 로 잡으면 배경이 구간을 다 먹어
  물체가 통째로 단색이 된다(실측 307~2695mm 구간에서 400mm 물체가 단색). 마스크 안에서 잡고
  배경은 양끝으로 포화시킨다. ⚠️ **구간이 프레임마다 다르므로 색을 프레임 간에 비교하면 안 된다** —
  그래서 구간을 캡션에 찍는다.
- ★★ **flange depth 는 «산포» 가 아니라 «평면 적합 잔차» 로 잰다.** flange 는 평면이지만 비스듬히
  보면 depth 범위가 수십 mm 로 벌어진다(실측 p10~p90 **70.0mm**) — 산포로 재면 **기울기와 노이즈가
  안 갈린다**. 평면을 맞추고(3회 재가중) 남은 잔차만이 *"이 depth 로 pose 를 낼 수 있는가"* 를 말한다.
  sim 기준선: `plane rms 0.65mm · p90 1.05mm`.
- 🔴 **`valid` 100% 를 «뚫렸다» 로 읽으면 안 된다.** `valid` 는 `유한 && z_near ≤ d ≤ z_far` 범위 검사일
  뿐이고(`contracts.py`) FoundationStereo 는 조밀 모델이라 **반투명 표면에서 틀린 값을 내도 100%** 다.
  **열린 항목 #1 판정은 4번 패널**(물체 depth 가 실제 거리인가 · plane rms)로 한다.
- 근접에서 `full` 마스크는 **ISM(CAD 템플릿)** 으로 뽑는다 — `sam3_refs_full_*` 은 원거리용밖에 없고
  ISM 은 사진 참조가 필요 없다. 타깃 지정은 `--select exemplar --exemplar-dir <flange seg>` 로 한다
  (`--select center` 는 배경을 집는다, 교훈 #15).
- ⚠️ 진단 스테이지(`seg_full`·`ov`·`diag`)는 **`optional`** 이라 실패해도 본 파이프라인을 안 죽인다
  — 진단 도구가 진단 대상과 같이 죽으면 안 된다(횡단 정리 #79 의 재적용).
- ⚠️ **경로 폴백에 프레임 디렉토리를 넘기면 안 된다** — `find()` 가 `frame_0007/frame_0007/…` 을 보고
  «산출물 없음» 이라고 **거짓말**했다. 폴백은 «프레임 디렉토리를 담은 루트» 여야 한다.

### 35-2c-2. 프레임 추이 — **40장을 눈으로 훑지 않는다**

`diag_metrics.json`(전 프레임 수치 + `median` 요약) 과 `diag_trends.png`(5단: 등가지름 · flange depth ·
평면 잔차 · 유효율 · 이동량, **붉은 세로 띠 = 게이트 후퇴**) 를 같이 낸다. 120프레임 **10.7초**.

★ **실제로 작동했다** — sim 근접 120프레임에서 추이가 **한 점만** 튀었다(`frame_0098`:
등가지름 261 → **68px** · flange depth 401 → **1452mm** · 평면 잔차 0.287 → **28.7mm**).
그 프레임만 열어 보니 **SAM3 가 flange 대신 배경 방해물을 집었다**(조각 `n=4`, 목표의 0.16배).
- 🔴 **그런데 그 프레임의 pose 는 정상이다**(z 358mm, 윤곽 정확) — 그 pose 런이 이 마스크를 안 썼다.
  **«분할이 깨졌다» 와 «pose 가 깨졌다» 는 별개**이고, 6패널을 나란히 놔야 갈린다.
  지표만 봤으면 정상 통과했을 프레임이다.
- sim 중앙값 기준선: `flange dia 261px · depth 401.5mm · plane rms 0.287mm · valid 100% · moved 0.354°`.
- ⚠️ 그래프 라벨은 **영문**이다 — matplotlib 에 한글 폰트가 없다(`viz.dim_sheet` 과 같은 제약).

예시: `runs/overlay_demo/diag/` (sim 근접 120프레임, GT 제거 조건, 시트는 4프레임).

## 35-2d. 통계 한 벌 — **직접 분석할 수 있게** (2026-08-13)

`spatial_vision.eval.group_stats --root <A그룹 out>` — 흩어진 JSON(`meta_contour` · `lr_consistency` ·
`diag_metrics` · `pose_refined`)을 **한 표**로 합친다. 러너의 마지막 스텝(`stats`)이다.

| 산출 | 무엇 |
|---|---|
| `stats/metrics_long.csv` | **(프레임 × 변형) 긴 형식** — `n_corr·rms_px·moved_deg·gated·ddx_px·dz_mm·t·q`. pandas 로 바로 |
| `stats/frames.csv` | 프레임 × 촬영지표 (노출·마스크·depth·유효율) |
| `stats/summary.md/.json` | 변형별 **중앙 / p90 / 최대** |
| `stats/variants.png` | 후퇴율 · 이동량 분포 · 좌우 일관성 · 대응점 (**상자 + 점**) |
| `stats/repeatability.png` | 정지 구간 반복도 |

- ⚠️ **분포를 «상자 + 점» 으로 그린다** — 40장에서 꼬리는 한두 점이라 상자만으로는 안 보인다(교훈 #16·#58).
  표에도 중앙값과 함께 **p90·최대**를 넣는다.
- ★ **회전 평균은 쿼터니언 외적행렬의 최대 고유벡터**로 낸다. 성분별 평균은 회전이 아니다.
  CSV 의 쿼터니언은 **`w ≥ 0` 으로 부호를 고정**했다 — 안 하면 프레임 간 비교가 무의미하다.
- 🔴 **반복도는 «물체·카메라가 안 움직인 구간» 에서만 랜덤 오차 바닥이다.** 움직이며 찍었으면 자세
  변화다 → **거리 산포로 자동 판정**해 `summary.md` 에 경고를 낸다(sim 120프레임 데모에서 산포 98mm →
  «정지 구간이 아니다» 를 옳게 말했다). 로봇 없이 되는 real 전용 측정이라 우선순위가 높다(`§9.1★c`).
- ✅ **검증 — sim 120프레임에서 §31 을 그대로 재현**: 게이트 후퇴 A2a **83.3%** / A2b 56.7% / A1 **29.2%**,
  대응점 중앙 A2a 14,595 vs A1 1,747. 알려진 결론이 이 도구를 통해 그대로 나온다.

## 35-2e. SAM3 참조 세트를 눈으로 본다 — `viz.ref_sheet` (2026-08-13)

exemplar 경로에서 **분할의 성패는 참조가 거의 다 정하는데**(원거리 참조로 근접 질의 → IoU 0.044)
참조는 자산 디렉토리 안의 PNG 라 아무도 안 본다. 박스를 그려 시트로 낸다.

    envs/pose/bin/python -m spatial_vision.viz.ref_sheet \
        --refs assets/obj/foup_300_semi_r2/sam3_refs_flange_n25 --n-refs 3 --out /tmp/refs.png

**현행 자산 실사(`foup_300_semi_r2`)**:

| 세트 | n | 출처 | 거리 |
|---|---|---|---|
| `sam3_refs_flange_n20` | 3 | `runs/zx_ref_n20` | 194 / 182 / 238mm |
| **`sam3_refs_flange_n25`** ← 배포 | **3** | `runs/zx_ref_n25` | **238 / 223 / 298mm** |
| `sam3_refs_flange_n30` | 3 | `runs/zx_ref_n30` | 296 / 282 / 348mm |
| `sam3_refs_full_far_cand` | 24 | `runs/zx_ref_far` | 후보 풀 |
| `sam3_refs_full_far_top5` | 5 | 위에서 **면적 상위 5장**(§19) | — |

- **랜덤이 아니다.** `refs.json` 의 목록을 **앞에서 `--n-refs` 장** 자른다(`refs[:n]`) — 파일 순서가 곧 우선순위다.
- 🔴 **`--refs-mode chain`(러너 기본값)에서 박스는 `ref_0` 에만 걸린다** — `add_prompt(frame_idx=0,
  boxes_xywh=[refs[0][...]])` 이고 나머지는 추적으로 이어질 뿐이다. **ref_0 이 사실상 지배한다.**
  `independent` 는 참조마다 독립 질의라 N장이 대등하다(§ SAM3 참조 사슬 한계).
- 🔴 **근접 flange 세트에는 §19 의 «면적 상위» 선정이 적용돼 있지 않다** — 후보 풀 없이 3장이 그대로
  배포 세트다. 면적 선정이 실제로 이긴 것은 **`full_far` 에서만** 확인됐다(IoU 0.888 / 오선택 0).
  근접 flange 는 오선택이 원래 0 이라 급하지 않았지만, **real 참조로 다시 만들 때는 후보를 넉넉히
  찍고 `cad.select_sam3_refs` 를 태우는 것이 맞다.**
- ⚠️ 셋 다 **sim 렌더**다(배경 randomization 이 눈에 보인다: 초록 시트 / 흰 바닥 / 보라). 밝기 중앙값
  199 / 239 / 128 로 편차가 크다. **실사진과의 차이가 exemplar 경로에 남은 마지막 도메인 갭 축**이다.

예시 시트: `runs/overlay_demo/refs/refs_n{20,25,30}.png` · `refs_full_far_top5.png`.

## 35-2f. **몸체 외관 3종** 참조 세트 — 실물 변이를 sim 에 넣었다 (2026-08-13)

사용자 확정: 실물 FOUP 몸체는 **① flange 와 같은 검정 불투명 ② 반투명 주황 ③ 투명** 셋이 대부분이다.
`capture_sim --body-appearance {black,orange,clear}` 를 신설해 셋을 렌더하고 참조 세트를 새로 만들었다.
**`top_flange` 는 어느 경우에도 검정 고정**이다 — 이건 몸체만의 축이다.

| 모드 | diffuse | roughness | opacity |
|---|---|---|---|
| `black` | 0.030 / 0.030 / 0.030 | 0.45 | **1.00** |
| `orange` | 0.720 / 0.230 / 0.020 | 0.22 | **0.45** |
| `clear` | 0.780 / 0.820 / 0.800 | 0.07 | **0.25** |

⚠️ `clear` 는 초판 0.14 로 냈다가 **0.25 로 올렸다**(사용자 지정, 2026-08-13). 자산은 재생성했다 —
**상수만 바꾸고 자산을 그대로 두면 코드와 자산이 조용히 어긋난다.**

- 고정 외관은 **`--body-material` 없이도** 바인딩되고 **프레임마다 흔들지 않는다**(flange 와 같은 취급).
  타깃·distractor 를 **같은 외관**으로 둔다 — 몸체 색이 타깃 식별 단서가 되면 분할 점수가 부풀려진다.
- 🔴🔴 **반투명·투명이면 `mask_full` 과 `depth_gt` 가 무효가 된다** (실측): 같은 seed·같은 프레임에서
  `black` 은 `full 730,310 / flange 113,273` 인데 **`orange`·`clear` 는 `full == flange == 113,273`** —
  **몸체 픽셀이 0** 이다. depth 중앙값도 581 → 668mm 로 **몸체를 통과해 배경을 본다.**
  OmniPBR cutout opacity 가 semantic·depth 패스에서도 프래그먼트를 버리기 때문이다.
  → **flange 참조·flange 마스크는 정상**이라(113,273 로 `black` 과 소수점까지 동일) exemplar 생성에는
  지장이 없지만, **이 런들의 `mask_full`/`depth_gt` 를 GT 로 쓰면 안 된다.**
- ⚠️ cutout opacity 는 **굴절·집광이 없다**. 색·대비는 재현하지만 유리처럼 배경이 휘지 않는다 →
  **열린 항목 #1(반투명 본체에서 수동 스테레오가 뚫리는가)의 대역물로 쓸 수 없다.** 그건 실물 측정이다.
- ★ **`black` 이 최난이도라는 것이 수치로 나왔다.** §19 선정 과정의 후보 16장 면적 분포:
  `black` 은 **123,078 ~ 23,077px** 로 크게 갈리는데(하위 2장이 명백한 실패),
  `orange`·`clear` 는 **전 후보가 ~109,000px** 로 균일하다. 몸체와 flange 가 같은 색이면
  **경계가 사라져** 참조 자체가 실패한다.

**만든 자산** (전부 §19 규칙 = 후보 16 → 마스크 면적 중앙값 **상위 5장**, GT 불필요).
🔴 **거리대를 열어 두고 6대역을 다 만들었다** (2026-08-14, `n30` 추가 2026-08-17) — 실물에서
**0.5m 가 sim 최적점(0.22~0.30m)보다 좋았기 때문**이다. sim 최적점이 실물로 전이되지 않았으므로
거리를 고정하지 않는다.

| 거리대 | 범위 | 세트 |
|---|---|---|
| `n25` | 0.22~0.30m | `_black` `_orange` `_clear` `_mixed` |
| **`n30`** | **0.28~0.35m** | 〃 |
| **`n40`** | **0.35~0.45m** | 〃 |
| **`n50`** | **0.45~0.55m** ← 실물 양호 구간 | 〃 |
| **`n60`** | **0.55~0.65m** | 〃 |
| **`n70`** | **0.65~0.75m** | 〃 |

⚠️ **구 `sam3_refs_flange_n30`(접미사 없음)과 헷갈리지 말 것** — 그건 외관 축이 생기기 전에
**몸체를 randomize 해서** 만든 **후보** 세트(n=3, §19 선정 없음)다. 남겨는 뒀지만 거리 스윕에는
`n30_black` 등 **새 세트**를 쓴다. 안 그러면 30cm 만 다른 조건에서 만든 참조로 재게 되어
**«거리 탓인가 참조 탓인가» 를 못 가른다.**
✅ 통제 확인: `n30` 참조 박스 면적 중앙 0.0592 vs `n40` 0.0365 = **1.64배**, 거리비 제곱
(0.40/0.30)²=1.78 과 같은 자릿수다. 거리 중앙도 0.296~0.320m 로 밴드 안에 든다.

각 대역마다 `_black`/`_orange`/`_clear` 는 **5장**(후보 16 → 상위 5), `_mixed` 는 **6장**
(외관별 상위 2장, `cad.mix_sam3_refs`). seed 를 101/202 로 고정해 **거리대·외관이 달라도
카메라 방위·고도가 같다** → A/B 가 통제된다.

- 러너 프리셋: `--preset n{25,40,50,60,70}{black,orange,clear,mixed}` — 목록은 **`--list-presets`**
  (참조 디렉토리 존재 여부까지 ✅/❌ 로 찍는다).
- 🔴 **참조 세트가 없으면 러너가 non-zero 로 죽는다.** 없으면 SAM3 가 **검출 0 으로 조용히** 끝나서
  «분할이 안 된다» 로 오진하게 된다 — 실제로 밟은 적이 있다.
- 🔴 **`mixed` 는 `--refs-mode` 를 `independent` 로 자동 전환**한다(전환 사실을 출력한다).
  `chain` 은 `add_prompt(frame_idx=0)` 라 박스가 **`ref_0` 에만** 걸려 «혼합» 이 아니라
  «ref_0 의 외관» 세트가 된다. 혼합 순서는 **난이도 순(black 먼저)** 이라 `--n-refs` 로 잘라도
  가장 어려운 조건이 남는다.
- ⚠️ **`mixed` 는 `--refs-mode independent` 전제다** — `chain` 은 박스가 `ref_0` 에만 걸려 혼합의 의미가 없다.
- ⚠️ 색·투과율은 **육안 근사**다. 실물 사진이 생기면 맞춰야 한다.

시트: `runs/overlay_demo/refs/refs_n25_{black,orange,clear,mixed}.png`

### 재현 (§35-2f) — 참조 자산 3종

🔴 **자산은 git 에 없다**(`.gitignore: assets/obj/**`) — 릴리스 tarball 로 나간다. 그래서 **이 명령이
자산을 되살리는 유일한 근거**다. 각 `refs.json` 에도 `body_appearance`·`capture_args` 를 박아 뒀다.

```bash
cd vision && source envs/env.sh
OBJ=assets/obj/foup_300_semi_r2
CAM="--width 1920 --height 1200 --fx 727.5751343 --fy 727.5751343 \
     --cx 960.99988 --cy 604.824219 --baseline-mm 120.201996"     # ← cx/cy 는 코너 원점(+0.5)
# 거리대: n25 0.22~0.30 · n30 0.28~0.35 · n40 0.35~0.45 · n50 0.45~0.55 · n60 0.55~0.65 · n70 0.65~0.75
LO=0.45; HI=0.55; CM=50                                            # ← 예: n50
SCENE="--distance-m $LO $HI --elevation-deg 35 70 --flange-color 0.03 0.03 0.03 \
       --ground-material --hdri assets/env/hdri --dome-intensity 110 210 --light-fixtures-active 1 2"

for app in black orange clear; do
  # ① 후보 풀(16) + 프로브(8). seed 를 고정해야 A/B 가 통제된다
  /isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
      --out runs/zx_ref_n${CM}_${app}_cand  --frames 16 --seed 101 $CAM $SCENE --body-appearance $app
  /isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
      --out runs/zx_ref_n${CM}_${app}_probe --frames  8 --seed 202 $CAM $SCENE --body-appearance $app
  # ② 후보 세트 (박스는 mask_flange 에서 뽑는다 — 반투명이어도 flange 마스크는 정상이다)
  envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs \
      --from runs/zx_ref_n${CM}_${app}_cand --obj $OBJ --n 16 --target flange \
      --out-name sam3_refs_flange_n${CM}_${app}_cand
  # ③ 후보 전부로 프로브를 독립 질의 → 참조별 마스크 (§19 선정의 입력)
  envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 \
      --in runs/zx_ref_n${CM}_${app}_probe --out runs/zx_refsel_n${CM}_${app} --target flange \
      --refs $OBJ/sam3_refs_flange_n${CM}_${app}_cand --n-refs 16 --refs-mode independent --save-per-ref
  # ④ 면적 중앙값 상위 5장
  envs/seg_sam3/bin/python -m spatial_vision.cad.select_sam3_refs \
      --refs $OBJ/sam3_refs_flange_n${CM}_${app}_cand --probe runs/zx_refsel_n${CM}_${app} --obj $OBJ --k 5 \
      --out-name sam3_refs_flange_n${CM}_${app}
done
  # ⑤ 🔴 출처 메타 — **선정 세트와 후보 세트 «둘 다»** 에 붙인다. 빠뜨리기 쉬운 단계다(아래 ⚠️)
  for s in "" "_cand"; do
    envs/pose/bin/python - "$OBJ/sam3_refs_flange_n${CM}_${app}${s}/refs.json" "$app" "$CM" "$LO" "$HI" <<'PY'
import json, sys
p, app, cm, lo, hi = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
d = json.load(open(p, encoding="utf-8"))
# 외관 dict 는 하드코딩하지 않고 **이미 있는 세트에서 복사**한다 (값이 갈라지지 않게)
donor = "assets/obj/foup_300_semi_r2/sam3_refs_flange_n40_%s/refs.json" % app
d["body_appearance"] = json.load(open(donor, encoding="utf-8"))["body_appearance"]
d["band"], d["distance_band_m"] = "n%s" % cm, [lo, hi]
d["capture_args"] = ("--body-appearance %s --distance-m %s %s --elevation-deg 35 70 "
    "--flange-color 0.03 0.03 0.03 --ground-material --hdri assets/env/hdri "
    "--dome-intensity 110 210 --light-fixtures-active 1 2") % (app, lo, hi)
d["regen"] = "RESULTS.md §35-2f 「재현」"
open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
PY
  done
done
# ⑥ 혼합 세트 (외관별 상위 2장, 난이도 순 black 먼저) — 계산 0, 파일 복사뿐이다
envs/seg_sam3/bin/python -m spatial_vision.cad.mix_sam3_refs --obj $OBJ --band n${CM} --per-set 2
# ⑦ 육안 확인 시트
envs/pose/bin/python -m spatial_vision.viz.ref_sheet \
    --refs $OBJ/sam3_refs_flange_n${CM}_black --n-refs 3 --cols 5 --out /tmp/refs_black.png
```

⚠️ **자산(`mesh.usda`)이 바뀌면 이 셋을 전부 다시 만들어야 한다**(교훈 #40).

🔴 **⑤는 초판 재현 절차에 없었다** (2026-08-17 에 `n30` 을 만들다 드러났다). `build_sam3_refs` 도
`select_sam3_refs` 도 **거리·외관을 기록하지 않는다** — n40~n70 의 메타는 손으로 붙인 것이었고,
절차만 따라 만든 `n30` 은 `band`/`body_appearance`/`capture_args`/`regen` 없이 나왔다.
**자산 tarball 은 git 밖이라 이 메타가 없으면 «어떤 조건에서 만든 참조인가» 를 되살릴 수 없다.**
→ 횡단 정리: **재현 절차에서 «산출물을 만드는 단계» 와 «산출물을 설명하는 단계» 를 같이 적는다.**
검증은 키 집합 대조로 한다 — `n30_*` 과 `n40_*` 의 `refs.json` 최상위 키가 같아야 한다.
⚠️ `_mixed` 는 예외다: `mix_sam3_refs` 가 메타를 스스로 쓰지만 `distance_band_m` 은 `null` 로 남는다
(원본 세트에서 읽는데 ⑤보다 먼저 도는 순서다). **n25~n70 전부 그러니 그대로 두는 게 일관된다.**

## 35-3. 한계

- ⚠️ **이건 sim 데이터로 한 스모크다.** 실물에서 처음 돌 때 무엇이 깨질지는 모른다.
- ⚠️ `lr_consistency` 는 `--outer-only` 만 지원한다(`--keep-hole-mm` 등은 정합기 내부 전용).
  **모든 변형을 같은 잣대로 채점**하는 게 목적이라 의도된 제약이다.
- ⚠️ 러너는 **A5(거리 스윕)를 자동화하지 않는다** — 거리마다 참조 세트가 달라 `--preset` 을 바꿔
  따로 돌려야 한다(`n25`~`n70` × 외관). 거리와 참조가 어긋나면 IoU 가 조용히 무너진다(§34-6).
  ✅ 존재 여부는 `tools/run_group_a.py --list-presets` 로 확인한다(현재 **27종**).
- ⚠️ **B그룹(원거리)은 아직 러너가 없다.** 분할 백엔드 3종 비교라 구조가 달라 별도다.

## 재현 (§35)

```bash
# 부호·감도 검증 — 정합기가 아니라 «지표» 를 검증하는 절차다 (횡단 정리 #8)
for Z in 0 5 -5; do envs/pose/bin/python -m spatial_vision.eval.lr_consistency \
    --in runs/zx_near/frame_0000 --pose-dir runs/zx_near --pose-name pose_gt.json \
    --obj assets/obj/foup_300_semi_r2 --outer-only --z-shift-mm $Z --out /tmp/lr$Z; done

# A그룹 전체 (실물)
python3 tools/make_frame_from_zed.py --left L.png --right R.png \
    --cam assets/cam/zedx_s48560070_hd1200.json --out runs/real01/frame_0000
envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out runs/real01_A \
    --preset n30black --ism --sam3-text --text-prompt "black plastic box"
#   → runs/real01_A/report.md · overlay_sheet.png · overlay/overlay_frame_*.png
#   🔴 접미사 없는 `n25`·`n30` 은 외관 축 이전의 **구 세트**다 — 새 실험에 쓰지 않는다(§35-2f).

# 오버레이만 다시 (마스크 끄고 실물 테두리를 그대로 보고 싶을 때)
envs/pose/bin/python -m spatial_vision.viz.overlay_pose \
    --capture runs/real01 --obj assets/obj/foup_300_semi_r2 \
    --pred runs/real01_A/fp_ns2:pose_coarse.json --pred runs/real01_A/A1 \
    --frames 4 --tile 560 --mask-alpha 0 --out runs/real01_A/overlay_a1.png
```

**§35-2m — `--primary full` 경로 (실물에서 통과한 그 경로)**

```bash
OBJ=assets/obj/foup_300_semi_r2
ONNX=weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx

# ── (A) 근접 · ISM. 러너의 부분집합이라 러너로 부르는 편이 낫다 ─────────────────
envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out runs/R28_ism \
    --preset n30black --ism --only st,seg_ism,fp_ism,I1,ov,diag \
    --note "28cm · ISM 단독 · --primary full"
#   ⚠️ --preset 은 SAM3 를 안 돌려도 **참조 존재 검사** 때문에 필요하다(결과에는 무영향).
#   ✅ ov·diag 가 A1 이 비면 자동으로 I1·seg_ism 을 가리킨다(§35-2m-4). 이유는 로그에 찍힌다.

# ── (A′) 세 경로 동시 — A(exemplar) / I(ISM) / T(텍스트). 촬영 1회 ────────────
envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out runs/R28_all \
    --preset n30black --ism --sam3-text --text-prompt "black plastic box" \
    --note "28cm · 3경로 동시"
#   🔴 --preset 과 --text-prompt 를 **개체 몸체 색에 함께** 맞춘다:
#      검정 n30black/"black plastic box" · 주황 n30orange/"orange plastic box"
#      투명 n30clear/"clear plastic box" · 모르면 n30mixed/"plastic box"
#   ⚠️ 원거리(≳0.45m)에서는 **정합을 쓰지 않는다**(§35-2m-6) — A3/I3/T3 행을 본다.

# ── (B) 원거리 · SAM3 «텍스트» 프롬프트를 손으로 (러너 밖에서 돌리고 싶을 때) ───
for cm in 40 50; do
  envs/stereo_onnx/bin/python -m spatial_vision.stages.stereo_onnx \
      --in runs/fr$cm --out runs/R${cm}_st --scale 0.5 --model $ONNX
  envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 \
      --in runs/fr$cm --out runs/R${cm}_seg --target full \
      --prompt "black plastic box" --confidence 0.05 --select center
  envs/pose/bin/python -m spatial_vision.stages.pose_fp \
      --in runs/fr$cm --out runs/R${cm}_pose --obj $OBJ \
      --masks runs/R${cm}_seg --depth stereo --depth-dir runs/R${cm}_st \
      --primary full --input-scale 0.5 --no-stage2
  envs/pose/bin/python -m spatial_vision.viz.overlay_pose --capture runs/fr$cm \
      --obj $OBJ --mesh top_flange.ply --pred runs/R${cm}_pose:pose_coarse.json \
      --frames 4 --per-frame-dir runs/R${cm}_viz --out runs/R${cm}_viz/overlay_sheet.png
done
#   🔴 --prompt 는 **실물 몸체 색에 맞춘다** — sim 이 검정이라 "black plastic box" 가 맞았을 뿐이다.
#   🔴 --select center 는 «카메라가 타깃을 겨눈다» 는 씬 규약에 기댄다(교훈 #15) — 실물에서는
#      배경을 집을 수 있다. 오버레이로 반드시 확인한다.
```

**§35-2o — `--mode` 로 후보를 넓혀 한 번에 돌린다**

```bash
envs/pose/bin/python tools/run_group_a.py --list-modes        # 모드·비용·무엇을 여는가

# 실물 초반 권장 — 18팔 (+3~4분)
envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out runs/real01_A \
    --preset n30black --ism --sam3-text --text-prompt "black plastic box" \
    --mode wide --true-distance-mm 280 --note "1차, 형광등 2등"

# 전부 — 30팔 (+4~6분). `--ism`·`--sam3-text` 는 자동으로 켜진다
envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out runs/real01_all \
    --preset n30black --text-prompt "black plastic box" \
    --mode all --true-distance-mm 280
#   참조 스윕 목록을 직접 주려면: --refs-sweep n30black,n40black,n50black,n70black
#   처음 시험이면:              --limit-frames 4     (전 체인 4장 ≈ 3분)
```

⚠️ 읽는 순서 — **⓪ `report.md` 「배선 감사」(❌ 면 아래를 전부 읽지 말 것)** ① 「판정」
② **`stats/ranking.png`**(좌우 \|Δdx\| 정렬 — 꼬리표 붙은 팔은 나란히 놓지 않는다, §35-2o-6b)
③ `stats/distance.png` 거리 4다리 · `stats/heatmap.png` ④ 신호등 ⑤ `segcmp`
⑥ 참조 스윕 표의 «쪼그라든 장»·«이탈 최대». 🔴 팔이 많으면 **선택 편향**(§35-2o-4).

**§35-2p — 판단용 그림 3종 + 배선 감사 (러너가 자동으로 낸다. 손으로 부를 때만)**

```bash
R=runs/real01_all

# 배선 감사 — «어느 팔의 숫자가 다른 팔 것은 아닌가» 7항목. 실패면 종료코드 1
envs/pose/bin/python tools/audit_run.py --root $R

# 판단용 그림 3종 (거리 4다리 · 팔 서열 · 프레임 × 팔). 기존 산출물만 읽는다 — 2초
envs/pose/bin/python -m spatial_vision.viz.result_charts --root $R
#   → $R/stats/{distance,ranking,heatmap}.png
#   ⚠️ 런 전체가 `--fix-z` 였다면 --fix-z 를 같이 준다 (모든 팔에 «Z고정» 표시)

# 리포트만 다시 (그림·감사까지 새로 돈다). 줄자는 run_meta.json 에서 물려받는다
envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out $R \
    --preset n30black --mode all --text-prompt "black plastic box" --report-only
```

**§35-2n — 결과 산출물 6종 (전부 추가 촬영 0)**

```bash
OBJ=assets/obj/foup_300_semi_r2
R=runs/real01_A          # 이미 러너를 한 번 돌린 출력 디렉토리

# ── 러너에 전부 들어 있다. 시각 산출물만 다시 그리려면 (수 초) ──────────────
envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out $R \
    --preset n30black --ism --sam3-text --only ov,ovc,segcmp,diag --force
# ── 실루엣 거리 + 신호등만 (재계산 없음, 디스크에 있는 값만 읽는다) ─────────
envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out $R \
    --preset n30black --ism --sam3-text --only scale,stats --force

# ── 손으로 부르고 싶을 때 ────────────────────────────────────────────────
envs/pose/bin/python -m spatial_vision.viz.overlay_pose --capture runs/real01 --obj $OBJ \
    --combine --pred $R/fp_ism:pose_coarse.json --pred $R/I1 --pred $R/T1 \
    --frames 4 --tile 460 --out $R/overlay_combo.png          # mm 눈금자는 기본 켬
envs/pose/bin/python -m spatial_vision.viz.seg_compare --capture runs/real01 \
    --seg $R/seg:mask_flange.png:A_flange --seg $R/seg_ism:mask_full.png:I_ISM \
    --seg $R/seg_txt:mask_full.png:T_text \
    --obj $OBJ --mesh full.ply \
    --pose $R/fp_ism:pose_coarse.json:I_pose --pose $R/fp_txt:pose_coarse.json:T_pose \
    --out $R/segcmp/seg_compare.png
#   🔴 --mesh 는 --seg 의 마스크와 **같은 대상**이어야 한다 (mask_full ↔ full.ply)
envs/pose/bin/python -m spatial_vision.eval.scale_check --in runs/real01 \
    --seg-dir $R/seg_ism --mask mask_full.png \
    --pose-dir $R/fp_ism --pose-name pose_coarse.json \
    --obj $OBJ --mesh full.ply --out $R/scale_check.json
envs/pose/bin/python -m spatial_vision.eval.group_stats --root $R \
    --variants A1,A2a,A2b,A4,I1,T1                            # → stats/traffic.png

# 부호·응답 검증 — «지표» 자체를 검증하는 절차다 (교훈 #8). pose t 에 ×1.2 를 주입하면
# 601mm → 507mm (참 502) 로 되돌린다. 자기순환이 아님을 이렇게 확인한다.
```

**sim 캡처 — 40/50cm 대조군을 새로 만들 때** (§35-2h 「가짜 실물」)

```bash
OBJ=assets/obj/foup_300_semi_r2
CAM="--width 1920 --height 1200 --fx 727.5751343 --fy 727.5751343 \
     --cx 960.99988 --cy 604.824219 --baseline-mm 120.201996"
SCENE="--elevation-deg 35 70 --flange-color 0.03 0.03 0.03 --ground-material \
       --hdri assets/env/hdri --dome-intensity 110 210 --light-fixtures-active 1 2 \
       --body-appearance black"
/isaac-sim/python.sh -m spatial_vision.stages.capture_sim --obj-usd $OBJ/mesh.usda \
    --out runs/fr_d40 --frames 20 --seed 303 $CAM $SCENE --distance-m 0.35 0.45
#   그다음 left/right/cam.json 만 복사해 runs/fr40 을 만든다(«가짜 실물»).
```

# ★★★★★ 36. 실물 형상 실측 — **§29 의 두 축이 닫혔고 배포 자산이 확정됐다** (사용자 실측, 2026-08-12)

`§29` 가 *"후보를 고르기 전에 맞춰야 할 형상 축이 둘"* 이라고 남겨 둔 항목을 **실물에서 직접 쟀다.**
sim 은 이 축을 원천적으로 못 본다(렌더와 CAD 가 같은 메쉬라 불일치가 0) — **real 에서만 나오는 값**이다.

| 축 | 확인 방법 | **실측** | 현행 CAD `foup_300_semi_r2` | 판정 |
|---|---|---|---|---|
| ① **최외곽 테두리 융기** | 육안 | **있다 (전 둘레)** | 있다 (+2mm) | ✅ **일치** |
| ② **최상면 중심 홀 개구** | 캘리퍼 (융기·챔퍼 제외) | **ø49.0** | **ø49.00** | ✅ **일치** |

⚠️ **«홀 개구» 를 말할 때는 «어느 높이인가» 를 반드시 붙인다.** 홀이 45° 원뿔이라 높이마다 다르다:
`상판 밑면 ø35.02`(= SEMI `d63`, 공차가 걸리는 유일한 값) · `주 상면 ø45.00` · **`최상면 ø49.00`**(융기 꼭대기).
**카메라가 보는 것은 최상면**이고 `§28`·`§29`·여기의 «최상면 개구» 는 전부 이것이다 — **규격이 안 잡는 값**이다.
🔴 실제로 혼동이 있었다 — `verify_semi` 가 `주 상면` 값을 *"홀 상면 개구"* 라는 라벨로 내고 있었고
(융기가 있으면 카메라가 보는 값과 4mm 차이), 초판 §36 은 keypoint 의 ø48.92 를 인용했다.
검사기를 **세 높이를 구분해 내도록** 고쳤다(2026-08-13) — `hole_opening_at_plate_top_mm` /
`hole_opening_topmost_mm` + 그 z. ⚠️ 최상면은 **메쉬 최고점에서 재면 안 된다** — 그건 «최외곽» 융기일 수 있어
홀 융기가 없는 자산에서 `nan` 이 난다(`spec15`·`fv_h0r2` 에서 실제로 났다). 홀 둘레에 재료가 있는
**가장 높은 z** 를 찾아야 한다. 대조군 검증: `fv_h2r0` ø49.00(융기 +4.00) vs `fv_h0r2` ø45.00(융기 없음).
| ③ 홀 주변 융기 | 육안 | **이 개체는 있다. 🔴 그런데 «대부분 있고 가끔 없다»** | 있다 (+2mm) | ⚠️ **개체 변이** |

🔴🔴 **③은 «맞췄다» 가 아니라 «맞출 수 없다» 로 읽어야 한다** (사용자 확정, 2026-08-12).
홀 융기는 **제조사·개체마다 있기도 없기도** 하다. 그리고 **처방이 정확히 그 축에서 뒤집힌다**:

| 실물 | 근거 | 홀을 쓰는 게 나은가 |
|---|---|---|
| 최외곽 융기 ○ + **홀 융기 ○** (대부분) | §31 (`r2`) | ❌ **재앙** — 대응점 88%가 어두운 깔때기 속 신호 없는 실루엣, 게이트 후퇴 88~93/120 |
| 최외곽 융기 ○ + **홀 융기 ✕** (가끔) | §25 (`r40`) | ✅ 홀이 **정칙화**로 작동 (홀 빼면 R 최대 3.23 → 7.40 악화) |

→ ★★★ **`--outer-only` 단독(P9)이 «가장 정확해서» 가 아니라 «유일하게 개체 불변이라서» 배포본이다.**
홀 샘플을 하나도 안 쓰므로 **변이하는 축에 구조적으로 노출되지 않는다** — §29 가 이미 측정했다
(모델 홀 지름을 6mm 틀려도 `--outer-only` 는 **소수점까지 같은 값**, 후퇴율 20 → 20).
대가는 홀 융기 없는 개체에서 R 0.224 vs 0.192 · t 0.419 vs 0.351 인데 **둘 다 KPI(3°/5mm) 한참 안쪽**이다.
**개체마다 파라미터를 바꿔야 하는 구성은 배포할 수 없다** — 이 맞바꿈은 자명하게 남는 장사다.
⚠️ 다만 **런타임 자동 판별은 가능하다** — 같은 데이터에 P7h/P9 를 돌려 **후퇴율만** 비교하면
그 개체에 홀 융기가 있는지가 갈린다(§31: 88 vs 24). GT 불필요·추가 촬영 0·플래그만 다르다.
**실물 A그룹(A2)이 정확히 이 비교다** → `tools/run_group_a.py` 가 자동으로 낸다.

## 36-1. 결론 — `r2` 가 맞는 자산이고, 배포는 **P9** 다

- ★★ **①이 «있다» 는 것이 가장 큰 소득이다.** §29 에서 ①은 **최악 축**이었다 — 틀리면 정합 이득이
  **×0.45(해롭다)** 이고 오차가 폭주가 아니라 **일관된 편향**이라 **게이트가 못 막는다**.
  맞았으므로 매트릭스 최고 이득 구간(**×1.92~2.01 · 후퇴 4/120**)에 들어간다.
- ★★ **②가 맞았는데도 «홀을 쓰라» 는 결론은 안 나온다.** §28-5 의 *"개구를 알면 홀 윤곽이 최고"* 는
  **홀 융기가 없을 때**의 이야기고, ③이 «있다» 이므로 지배하는 것은 **§31** 이다 —
  융기로 개구가 깊고 어두워져 대응점의 88%가 **신호 없는 실루엣**이 되고 게이트 후퇴가 88~93/120 이 된다.
  → **`--outer-only` 단독(P9) 유지.** 홀 지름을 맞힌 값어치(R 0.032°/t 0.068mm)는 **실현되지 않는다.**
- ✅ **§35-2 러너의 판정 문구가 이 경우를 정확히 말한다** — *"원인이 둘이고 처방은 같다,
  융기가 있으면 개구를 재도 안 돌아온다"*. 초판의 *"개구가 CAD 와 다르다"* 였다면 여기서 오진했다.
- ⚠️ **②의 0.08mm 일치는 우연이 아니다** — `r2` 자산 자체가 사용자 육안 관측(융기 2mm)을 반영해
  만든 것이다. **독립 검증이 아니라 «설계대로 나왔다» 는 확인**으로 읽어야 한다.
- ⬜ 남은 형상 미확인: **최외곽 윤곽이 서브밀리미터로 맞는가**(§27-4b — `x46 71±1` 은 준수품끼리
  2mm 차를 허용한다. 규격 띠가 1.6mm 어긋나면 `--outer-only` 가 오히려 나빠진다: KPI 90 → 74).
  융기 폭·라운드·노치(`x69`)도 미실측. **①②③이 맞았다고 «윤곽이 맞다» 로 읽으면 안 된다.**

## 36-2. 카메라 — 편광 SKU 로 보인다

후면 **"P" 각인**(사용자 확인). `ZED-311120`(편광) / `-311110`(무편광) 부품번호로 확정할 것.
운용 함의는 광량 감소다 — **노출을 늘리지 말고 조명을 늘린다.** §33 의 내성이 비대칭이기 때문이다:
테두리 정합은 블러 4px·게인 20×에 무감각한데 **FP 는 꼬리가 터진다**(R 최대 2.1° → 111.6°).
손 촬영이라 노출 증가가 곧 블러다(근접 1px = 0.324mm). 반사 억제 자체는 이득이다 —
광택 하이라이트가 테두리를 가로지르면 **rms 가 정상 범위인 채로 틀린 대응점**을 잡는다(§26).
