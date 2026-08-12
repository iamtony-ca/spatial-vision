# LICENSES.md — 이 파이프라인 구성요소의 라이선스

> ⚠️ **핵심 결론 먼저**: GitHub 배포 기준으로 **FoundationStereo·FoundationPose·nvdiffrast 세 개가
> "research/evaluation 목적만" 으로 상업적 사용이 금지**돼 있다. 즉 지금 구성 그대로는 **연구는 가능, 제품화는 불가**.
> 상업화 경로는 §3 참조.
>
> (법률 자문이 아니라 각 repo 의 LICENSE 파일을 직접 읽어 정리한 사실 관계다. 실제 상업화 판단은 법무 검토 필요.)

확인 시점: 2026-08-07. 고정된 커밋은 `third_party/repos.lock`.

---

## 1. 상업적 사용이 제한되는 것 ❌

| 구성요소 | 라이선스 | 근거 조항 |
|---|---|---|
| **FoundationStereo** (코드 + GitHub 배포 가중치) | NVIDIA Source Code License | §3.3 Use Limitation — *"only may be used or intended for use non-commercially … **means for research purposes only**"* (`LICENSE:54-57`) |
| **FoundationPose** (코드 + 가중치) | NVIDIA Source Code License | §3.3 — *"… **means for research or evaluation purposes only**"* (`LICENSE:54-57`) |
| **nvdiffrast** (FoundationPose 필수 의존) | Nvidia Source Code License **(1-Way Commercial)** | §3.3 — 사용자에게는 non-commercial 만 허용, NVIDIA 자신은 상업적 사용 가능 |

- 세 라이선스 모두 **특허 소송 시 권리 종료**(patent retaliation) 조항이 있다.
- FoundationStereo 쪽이 FoundationPose 보다 **더 좁다** — "evaluation" 문구조차 없이 *research purposes only*.
- nvdiffrast 는 FoundationPose 의 렌더링 백엔드라 **FoundationPose 를 쓰는 한 따라온다**. 반대로 FoundationPose 를
  대체하면 같이 해소된다.

## 2. 조건부 / 자유 ✅

| 구성요소 | 라이선스 | 메모 |
|---|---|---|
| **FoundationStereo @ NGC (TAO)** | **NVIDIA Open Model License** | 모델카드 명시: *"This model is ready for **commercial use**."* → **GitHub 배포와 라이선스가 다르다**(§3) |
| **SAM 3** (Meta) | SAM License (2025-11-19) | 상업적 사용 **금지 조항 없음**(LICENSE 전문에 "commercial" 단어가 등장하지 않음). 단 재배포 조건, **Trade Controls/ITAR — 군사·무기·핵 용도 금지**, 소송 시 라이선스 종료 |
| **SAM-6D ISM** | MIT (`Instance_Segmentation_Model/LICENSE`, CNOS 유래) | 자유 — 우리가 쓰는 건 이것뿐 |
| ~~SAM-6D PEM~~ | **라이선스 없음** ⚠️ | 리포 **루트에 LICENSE 가 없고** PEM 하위에도 없다 → 기본값은 *all rights reserved*. research-only 명시보다 오히려 더 모호하다. **상업 대안 후보로 쓸 수 없다**. 현재 설치하지 않으므로 영향 없음 |
| **Stereolabs ZED SDK / `pyzed`** | **독점(proprietary), 무상 배포** | **캡처·정류 전용**으로만 쓴다(`stages/capture_real.py`). 산출물은 `left.png`·`right.png`·`cam.json` 뿐이고 **파이프라인 어디에도 ZED SDK 를 import 하지 않는다** — 카메라를 바꾸면 이 스테이지만 갈아 끼우면 된다. ⚠️ SDK depth·포지셔널트래킹 등 알고리즘 기능은 **쓰지 않는다**(FoundationStereo 로 직접 만든다) |
| segment-anything (SAM), DINOv2 | Apache 2.0 | 자유 |
| pytorch3d | BSD-3-Clause | 자유 |
| open3d, trimesh, pyrender | MIT | 자유 |
| warp-lang, kornia | Apache 2.0 | 자유 |
| **ultralytics / FastSAM** | **AGPL-3.0** | 강한 카피레프트(네트워크 사용까지 소스공개 의무). ISM 을 SAM 경로로 쓰기로 한 결정(M0-5)이 라이선스 관점에서도 유리하게 작용. ⚠️ **정정(2026-08-07)**: `bootstrap.sh` 는 설치하지 않지만, 결정 이전에 만들어진 `seg_sam6d` venv 에 `ultralytics 8.4.115` 가 **실제로 남아 있었다**. 캐시 삭제 후 재빌드로 제거했고, 없는 상태에서 ISM 이 정상 동작함을 확인했다(`RESULTS.md § M0 재현성 재검증`). **결정을 내린 것과 트리에서 사라진 것은 별개다 — 재빌드해야 실제로 없어진다.** |

## 3. 상업화가 필요해지면 — 경로

| 막히는 것 | 대체 경로 | 상태 |
|---|---|---|
| FoundationStereo | **NGC/TAO 배포판**(NVIDIA Open Model License, commercial OK). `trainable_v2.0` = `.pth` 537MB, ONNX deployable 도 제공 | ⚠️ **small 변형만** 있음. GitHub 의 최고성능 `23-51-11`(ViT-large)에 해당하는 .pth 는 NGC 에 없음 → 정확도 손실 감수 여부 확인 필요 |
| FoundationPose | 상업 라이선스 대안을 별도 조사해야 함(자체 학습 / 다른 6D pose 모델). nvdiffrast 의존도 함께 해소됨 | ❌ 미조사. ⚠️ **Any6D 는 대안이 아니다** — pose 백엔드가 FoundationPose 그대로라 같은 라이선스를 물려받는다 |
| 분할(ISM) | 이미 MIT 라 막히지 않는다 | ✅ |
| **카메라 SDK** | ZED SDK 는 **캡처 경계에 격리**돼 있다 — 대체 시 `capture_real.py` 만 다시 쓰면 된다(RealSense 는 `librealsense` Apache 2.0) | ✅ 구조적으로 열려 있음 |

### ⚠️ NOCTIS 를 도입한다면 (현재 **보류**, `PIPELINE_CATALOG.md §2.2b`)

NOCTIS 코드 자체는 **MIT** 지만 **논문의 SOTA 설정이 AGPL-3.0 을 끌고 온다**:

- `src/model/grounded_sam.py:259` — SAM 2.1-L 경로가 `from ultralytics.models.sam import SAM2Predictor`
- `requirements.txt` 가 `ultralytics>=8.3.100,<=8.3.186` 을 **무조건** 건다

**위 §2 표에서 이미 지목하고 우리 트리에서 제거한 바로 그 의존성이다.** 도입 시
**Meta 공식 `sam2`(Apache 2.0)로 교체**해야 상업 경로가 유지된다.
저장소 **기본 설정**(`use_yolo_sam: False`, `sam_vit_model: vit_t`)은 MobileSAM(Apache 2.0)이라
라이선스는 깨끗하지만 **그 조합의 성능은 논문에 없다** — 깨끗한 설정과 벤치마크된 설정이 다르다.
| nvdiffrast | FoundationPose 대체 시 동반 해소. 단독 대체는 pytorch3d(BSD) 렌더러 | — |

**현 과제 맥락**: `CONSUMER_6DPOSE.md` 는 연구과제(Vision AI 기반 Teaching-Free 기술 개발) 문서다.
연구·평가 범위에서는 세 라이선스 모두 **문제없다**. 제품/양산 라인에 넣는 순간 §3 이 필요해진다.

## 4. 앞으로 추가로 받아야 할 것

가중치는 **13/13 확보 완료**(2026-08-07). 그 외에 남은 다운로드는 두 건뿐이다.

| 시점 | 항목 | 이유 / 라이선스 |
|---|---|---|
| **M4** | **BlenderProc (+ Blender ~1GB 자동 다운로드)** | SAM-6D ISM 은 CAD 를 여러 시점에서 렌더한 **템플릿**이 있어야 zero-shot 매칭을 한다. `Render/render_custom_templates.py` 가 `import blenderproc as bproc` 로 시작한다. 현재 `seg_sam6d` venv 에 없음. BlenderProc=BSD-3, Blender=GPL — **렌더 산출물에 GPL 이 전이되지 않는다**는 게 통상 해석이나 상업화 시 법무 확인 권장 |
| ~~M3~~ ✅ **576×960 은 이미 받아 뒀다** (`weights/ngc_foundationstereo/deployable_foundationstereo_small_576x960_v2.0.onnx`, 868MiB). ⚠️ **`check_weights.sh` 의 13종에 없고 `fetch_weights.sh` 도 받지 않는다** — 새 머신으로 옮기지 않으면 조용히 사라진다(`docs/SETUP.md §0`). 320×736 은 아직 없다 | NGC `deployable_v2.0` **고정 해상도** ONNX (320×736 576MB / 576×960 909MB) | 우리가 받은 **dynamic 판은 모델카드상 TRT FP16 변환 불가, ONNX Runtime 전용**이다. TensorRT 경로로 가려면 고정 해상도 판이 필요. 라이선스는 동일(NVIDIA Open Model License) |

## 5. 데이터셋 (참고)

FoundationStereo 학습셋 FSD 는 NVIDIA Omniverse 로 생성된 합성 데이터다 — 우리가 SDG 로 만드는 데이터와
같은 계열이라, 자체 데이터로 재학습하는 경로를 택할 경우 참고가 된다.
