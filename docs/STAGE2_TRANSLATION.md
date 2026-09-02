# stage2 가 `top_flange` 로 평행이동을 다시 내는 근거 — 논문·코드 위치

> **범위**: *"왜 stage2 에서 메쉬를 `full` → `top_flange` 로 갈아타면 평행이동이 좋아지는가"* 의 근거만 다룬다.
> 배포 구성 전체의 근거는 **`RH_RATIONALE.md`**, 측정치 정본은 **`RESULTS.md`** 다. **수치를 여기서 새로 만들지 않는다.**
> 코드 인용은 전부 **원문 확인**(2026-09-02)이고 줄 번호는 `third_party/FoundationPose` 및 우리 `spatial_vision/` 기준이다.

## 0. 한 줄 요약 — **근거가 두 갈래이고, 강도가 다르다**

| 기전 | 논문 | 코드 | 강도 |
|---|---|---|---|
| **① crop 이 «물체 지름» 으로 정해진다 → 작은 메쉬일수록 유효 해상도가 높다** | ✅ **§3.3 에 명시** | ✅ `Utils.py:605` | **A — 논문 + 코드** |
| **② 평행이동 갱신 보폭만 «물체 지름» 에 비례한다(회전은 상수)** | 🟡 **절반** — 회전 상수 **20° 는 논문 p14**(학습 교란 크기), 평행이동의 **지름 정규화는 논문에 없다** | ✅ `predict_pose_refine.py:228-229` vs `:221` | **B — 코드만** |
| **③ 그래서 R 과 t 를 갈라 쓸 수 있다(하이브리드)** | ✅ **§5.3 (supplementary)** | ✅ `Utils.py:850-857` | **A — 논문 + 코드** |

🔴 **②를 논문 근거로 인용하면 안 된다** — 확인 결과 논문은 `Δt ∈ ℝ³` 를 *"object's translation shift in the
camera frame"* 이라고만 쓰고 **지름 정규화를 언급하지 않는다.** 구현(릴리스 가중치 설정)에만 있다.

---

## 1. 우리 stage2 가 정확히 무엇인가

`spatial_vision/stages/pose_fp.py`

```python
286:    est1 = FoundationPose(model_pts=mesh_primary.vertices, ..., mesh=mesh_primary, ...)
291:        est2 = FoundationPose(model_pts=mesh_flange.vertices,  ..., mesh=mesh_flange,  ...)
...
374:            coarse  = est1.register(K=K, rgb=rgb, depth=depth_m, ob_mask=(mask_full > 127), ...)
416:                refined = est2.track_one(rgb=rgb, depth=depth_crop, K=K, iteration=args.refine_iter)
```

★ **stage2 는 «한 번 더 refine» 이 아니라 «다른 메쉬로 만든 별도의 `FoundationPose` 인스턴스»** 다.
`est1` 은 `full.ply`, `est2` 는 `top_flange.ply` 를 갖고 있고, 두 메쉬는 **원점이 같다**
(`assets/obj/<id>/meta.json` 의 `origin` = flange 주 상면 중심) — 이것이 접합의 전제다.

⚠️ 두 인스턴스는 **같은 `scorer`·`refiner` 네트워크 객체를 공유**한다(`pose_fp.py:284`). 즉 **가중치는
동일**하고 **바뀌는 것은 오직 `mesh` 와 그로부터 나오는 `mesh_diameter`** 다. 이것이 아래 두 기전의 유일한 입력이다.

### 1.1 ★ 그 `.ply` 는 무엇인가 — **점군이 아니라 «면이 있는» 메시다**

`assets/obj/foup_300_semi_r2/*.ply` 헤더 (원문):

```
format binary_little_endian 1.0
comment https://github.com/mikedh/trimesh
element vertex 88179            ← full.ply  (top_flange.ply 는 73131)
property float x / y / z
element face 140970             ← ★ 면이 있다 (top_flange.ply 는 110882)
property list uchar int vertex_indices
end_header
```

| | `full.ply` | `top_flange.ply` |
|---|--:|--:|
| 정점 | 88,179 | 73,131 |
| **면** | **140,970** | **110,882** |
| 파일 크기 | 2.8 MB | 2.3 MB |

🔴 **면이 없으면 이 파이프라인은 성립하지 않는다** — 면이 쓰이는 곳이 셋이다:

1. **정점 법선** — `pose_fp.py:286·291` 이 `model_normals=mesh.vertex_normals` 를 넘기는데,
   trimesh 는 그것을 **면에서 계산**한다. 점군이면 값 자체가 없다.
2. **render-and-compare** — refiner/scorer 는 nvdiffrast 로 메시를 **래스터화**한다
   (`Utils.py:135 nvdiffrast_render`, `mesh_tensors['faces']` 필수).
3. **`mesh_diameter`** 는 예외다 — 정점만 쓴다(`Utils.py:569-575`). 즉 §2 의 crop 기전만 놓고 보면
   점군으로도 계산은 되지만, 위 ①②가 막혀 **파이프라인이 돌지 않는다.**

⚠️ **색·UV·법선은 파일에 없다**(`property` 가 `x,y,z` 뿐). 그래서 trimesh 가 기본 회색
`[102,102,102,255]` 를 **전 정점에 균일하게** 채워 넣고(`ColorVisuals`), `Utils.py:121-125` 의
`else` 분기가 그것을 `vertex_color` 로 쓴다. → ★ **네트워크의 RGB 입력에 들어가는 렌더는
«무늬 없는 균일 회색 물체»** 다. 형상·음영만 있고 텍스처는 **원리적으로 없다.**
🔴 이것이 «CAD 만으로 실물 pose 를 낸다» 가 성립하는 이유이자 한계다 — RGB 가담분이 **실루엣·음영뿐**이라
기하(XYZ 채널)가 정보를 지고, 검정 몸체처럼 **경계 대비가 사라지는 조건에서 취약**해진다(§35-2i).
⚠️ `is_watertight = False` 인데 **FP 는 요구하지 않는다**(래스터화·법선 모두 무관).

---

## 2. 근거 ① — crop 이 «물체 지름» 으로 정해진다 (**논문 + 코드**)

### 2.1 논문 §3.3 «Pose Hypothesis Generation → Pose Refinement»

> *"We then project the object origin to the image space to determine the crop center.
> We then project the **slightly enlarged object diameter (the maximum distance between any pair of
> points on the object surface)** to determine the crop size that encloses the object and the nearby
> context around the pose hypothesis."*
> — Wen, Yang, Kautz, Birchfield, **FoundationPose: Unified 6D Pose Estimation and Tracking of Novel
> Objects**, CVPR 2024 (Highlight). arXiv:2312.08344, §3.3.

★ *"slightly enlarged"* = 코드의 `crop_ratio`, *"maximum distance between any pair of points"* =
코드의 `compute_mesh_diameter` 다. **논문 문장과 구현이 1:1로 대응한다.**

### 2.2 코드 — `third_party/FoundationPose/Utils.py:579-621`

```python
579: def compute_crop_window_tf_batch(pts, H, W, poses, K, crop_ratio=1.2, out_size=None,
                                     method='min_box', mesh_diameter=None):
603:   if method=='box_3d':
605:     radius = mesh_diameter*crop_ratio/2          # ← crop 을 «3D 에서» 정의한다
606:     offsets = torch.tensor([0,0,0,  radius,0,0,  -radius,0,0,  0,radius,0,  0,-radius,0])…
609:     pts = poses[:,:3,3].reshape(-1,1,3)+offsets…  # 물체 원점 ± radius 를
611:     projected = (K@pts.reshape(-1,3).T).T         # K 로 투영해서
612:     uvs = projected[:,:2]/projected[:,2:3]        # 화면 좌표의 crop 창을 얻는다
```

그 창을 `out_size` 로 리사이즈한다 (`Utils.py:594-600`):

```python
597:    new_tf[:,0,0] = out_size[0]/(right-left)
598:    new_tf[:,1,1] = out_size[1]/(bottom-top)
```

호출부는 `learning/training/predict_pose_refine.py:31` 이고 `method='box_3d'`(`:30`),
`out_size = render_size = cfg['input_resize']` 다.

### 2.3 배포 가중치의 상수 (`weights/*/config.yml` — 원문)

🟢 **`input_resize = 160` 은 논문에도 있다** — supplementary(p14):
> *"Both the rendering and input observation are **cropped based on the perturbed pose and resized into
> 160 × 160** before sending to the network."*

🔴 반면 **`crop_ratio` 의 값 1.2 / 1.1 은 논문에 없다** — 설정 파일에만 있다(논문은 *"slightly enlarged"* 라고만 한다).


| 네트워크 | 디렉토리 | `crop_ratio` | `input_resize` | 근거 |
|---|---|---|---|---|
| **refiner** | `2023-10-28-18-33-37` | **1.2** | **160 × 160** | `predict_pose_refine.py:97` 이 이 이름을 하드코딩 |
| scorer | `2024-01-11-20-02-45` | 1.1 | 160 × 160 | `predict_score.py:120` |

### 2.4 ★ 그래서 나오는 결론

```
네트워크 1px 이 담는 물리 크기 = mesh_diameter × crop_ratio / input_resize
```

🔴 **거리에도 `fx` 에도 의존하지 않는다** — crop 이 3D 에서 정의되기 때문이다.
**메쉬를 작게 바꾸는 것이 유효 해상도를 올리는 유일한 수단**이고, 그것이 stage2 다.

배포 자산 `assets/obj/foup_300_semi_r2` 실측:

| 메쉬 | 정점 | `mesh_diameter` | **refiner 1px** |
|---|--:|--:|--:|
| `full.ply` | 88,179 | 578.6~579.0mm | **4.341mm** |
| `top_flange.ply` | 73,131 | 183.4~183.5mm | **1.376mm** |

→ **stage2 에서 유효 해상도가 3.16배 좋아진다**(정본 `RESULTS.md §22`).

🟢 **depth 전처리의 «존재» 도 논문에 있다** — §5 Implementation(p13):
> *"We perform **denoising to the depth images** implemented in Warp, which includes
> **erosion and bilateral filtering**. The pose-conditioned cropping is implemented in batch using Kornia."*

🔴 **다만 `radius=2` 가 «픽셀 단위» 라는 것은 코드에만 있다**(`estimater.py:173-174`) —
§38-10 의 *"`--input-scale` 이 전처리 반경의 물리 크기를 바꾼다"* 는 **코드 근거뿐**이다.

⚠️ **`mesh_diameter` 는 결정론이 아니다** — `estimater.py:54` 가
`compute_mesh_diameter(model_pts=mesh.vertices, n_sample=10000)` 로 부르는데, 그 분기
(`Utils.py:569-575`)는 **`np.random.choice` 로 10,000점을 뽑아** 쌍거리 최댓값을 낸다.
실측 재실행 폭: `full` **0.355mm** · `top_flange` **0.095mm**(각 6회). 크기는 작지만 **교훈 #24·#107
(FP 비결정성)의 원인 중 하나로 확인된 항목**이다. ⚠️ 정점 88k 중 10k 만 보므로 **참 지름의 하한**이다.

---

## 3. 근거 ② — 갱신 보폭이 비대칭이다 (🔴 **코드만. 논문에 없다**)

### 3.1 우리 릴리스가 실제로 타는 분기

`weights/2023-10-28-18-33-37/config.yml` 원문: `trans_rep: tracknet` · `normalize_xyz: true` ·
`rot_rep: axis_angle` · `rot_normalizer: 0.3490658503988659` (= **20.0°** in rad).

그 설정에서 `learning/training/predict_pose_refine.py` 가 타는 경로:

```python
194:        if self.cfg['trans_rep']=='tracknet':
195:          if not self.cfg['normalize_xyz']:
196:            trans_delta = torch.tanh(output["trans"])*trans_normalizer
197:          else:
199:            trans_delta = output["trans"]        # ← 무차원 원출력 그대로
...
220:        if self.cfg['rot_rep']=='axis_angle':
221:          rot_mat_delta = torch.tanh(output["rot"])*self.cfg['rot_normalizer']   # ← 상수 20°
222:          rot_mat_delta = so3_exp_map(rot_mat_delta).permute(0,2,1)
...
228:        if self.cfg['normalize_xyz']:
229:          trans_delta *= (mesh_diameter/2)       # ← 평행이동만 메쉬 크기에 비례
231:        B_in_cam = egocentric_delta_pose_to_pose(pose_data.poseA[b:b+bs],
                                                    trans_delta=trans_delta, rot_mat_delta=rot_mat_delta)
```

### 3.2 ★ 비대칭의 내용

| | 네트워크 출력 | 곱해지는 것 | 메쉬 크기 의존 |
|---|---|---|---|
| **평행이동** | 무차원 `output["trans"]` | **`mesh_diameter / 2`** | ✅ **비례** |
| **회전** | 무차원 `output["rot"]` | `rot_normalizer` = **20° 상수** | ❌ **없음** |

배포 자산: `full` 289.4mm ↔ `top_flange` **91.7mm** → **평행이동 보폭만 3.16배 세밀해진다.**

🟢 **`rot_normalizer = 20°` 는 논문에 근거가 있다** (2026-09-02 확인) — supplementary p14:
> *"the pose is randomly perturbed by adding **translation noise under the magnitude of 0.02m, 0.02m,
> 0.05m** for XYZ axis respectively and **rotation under the magnitude of 20°**"*

★ **네트워크의 회전 출력 범위(±20°)가 학습 교란 크기와 정확히 일치한다** — `tanh(out) × 0.3490658 rad = ±20.0°`.
🔴 **반면 평행이동 쪽은 논문이 «절대 미터»(0.02/0.02/0.05 m)로 적고 `mesh_diameter` 정규화를 언급하지 않는다.**
출시된 설정은 `normalize_xyz: true` 로 **지름에 비례**시킨다 → **그 정규화는 여전히 코드 근거뿐**이다.

회전 보폭은 두 단계에서 **완전히 같다.**

### 3.3 🔴 논문 대조 결과 — 이 항목은 논문 근거가 없다

논문 §3.3 은 `Δt ∈ ℝ³` 를 *"the object's translation shift in the camera frame"* 이라고만 쓰고,
**지름 정규화(`normalize_xyz`)를 언급하지 않는다**(2026-09-02 원문 확인).
→ ★ **인용할 때 «논문에 따르면» 이라고 쓰면 안 되고 «공개 구현의 학습 설정에서» 라고 써야 한다.**
학습 시 스케일 불변성을 얻기 위한 정규화로 보이지만 **그 의도는 문서화돼 있지 않다** — 추정이다.

---

## 4. 왜 stage1 의 R 과 stage2 의 t 를 접합해도 되나 (**논문 + 코드**)

### 4.1 논문 §5.3 (supplementary) «Details on Disentangled Representation for Pose Updates»

> *"this **disentangled representation removes the dependency on the updated orientation when applying
> the translation update**. This unifies both the updates and input observation in the camera
> coordinate frame."*

### 4.2 코드 — `Utils.py:850-857`

```python
850: def egocentric_delta_pose_to_pose(A_in_cam, trans_delta, rot_mat_delta):
855:   B_in_cam[:,:3,3]  = A_in_cam[:,:3,3] + trans_delta        # t ← t + Δt   (R 이 안 낀다)
856:   B_in_cam[:,:3,:3] = rot_mat_delta @ A_in_cam[:,:3,:3]     # R ← ΔR · R   (t 가 안 낀다)
```

★ **평행이동은 카메라 좌표에서 덧셈, 회전은 좌곱**이라 두 성분이 서로를 오염시키지 않는다.
그래서 **한 단계의 `R` 과 다른 단계의 `t` 를 접합해도 각각이 그 단계에서 최적화된 값 그대로 유지된다.**
🔴 물체 좌표계 갱신(`t ← R·Δt + t`)이었다면 접합이 의미를 잃는다 — **이 파라미터화가 하이브리드의 전제**다.

---

## 5. 측정 증거 (정본 = `RESULTS.md`)

**§2.2 의 기전이 예측하는 것**: stage1(큰 메쉬)은 **회전 증거가 많고 평행이동이 거칠다**,
stage2(작은 메쉬)는 **평행이동이 세밀하고 회전 증거가 적다**. 세 파이프라인에서 **부호가 한 번도 안 뒤집힌다**:

| 출처 | coarse R / t | refined R / t |
|---|---|---|
| 원거리 `full` (§27-7, n=120) | **0.549°** / 1.713mm | 0.737° / **1.280mm** |
| 근접 `flange` (§27-7, n=120) | **0.510°** / **0.928mm** | 0.656° / 1.104mm |
| 실물 검증 체인 3종 (§38-7, n=10) | **0.37~0.50°** / 2.0~2.3mm | 1.36~1.42° / **1.04~1.26mm** |

그리고 `--primary flange`(= 두 단계가 **같은 메쉬**) t 이득은 **1.100 → 1.042mm (0.058mm)** 인데
**FP 재실행 잡음 바닥이 0.512mm** 라 **측정되지 않는다**(교훈 #95).

★★★ **이것이 반증 가능한 예측의 검증이다** — *"stage2 가 좋은 이유가 «단계를 하나 더 두어서» 라면
`--primary flange` 에서도 이득이 나야 하고, «메쉬를 갈아타서» 라면 사라져야 한다."* → **사라졌다.**

---

## 6. 🔴 한계 — 같이 쓸 것

1. **②는 코드 근거뿐이다**(§3.3). 논문에 없는 구현 세부이므로 *"공개 구현에서"* 로 한정해 쓴다.
2. **`mesh_diameter` 가 확률적이다**(§2.4) — 재실행마다 `full` 0.36mm 폭. 작지만 0 이 아니다.
3. **stage2 의 대가**: `top_flange` 는 근사 4회 대칭이고 방향 정보가 **표면의 3.5%·전부 경계**에 있다
   (`RESULTS.md § flange 의 회전 구속`). 그래서 stage2 는 **회전 증거를 버린다** — 하이브리드로
   회전을 stage1 에서 받는 이유가 이것이다.
4. **접합의 전제**: `full.ply` 와 `top_flange.ply` 의 **원점이 같아야** 한다(우리 규약, `meta.json`).
   다른 객체로 옮길 때 가장 먼저 깨질 가정이다.
5. **측정은 대부분 sim GT** 다. 실물 근거는 §38 의 육안 확인 하나이며 절대 정확도는 **상대 GT**
   (`PIPELINE_CATALOG §7.5c`)로만 잴 수 있고 아직 안 쟀다.

---

## 7. 인용 목록 (원문 확인 완료, 2026-09-02)

| 주장 | 위치 |
|---|---|
| crop 중심 = 물체 원점 투영 · crop 크기 = **물체 지름**(쌍거리 최댓값)을 조금 키워 투영 | **논문 §3.3** (arXiv:2312.08344, CVPR 2024) |
| 갱신이 **disentangled** — 평행이동에 회전 의존이 없다 | **논문 §5.3** (supplementary) |
| 회전은 **axis-angle** 로 파라미터화 | 논문 §3.3 |
| **crop 을 160×160 으로 리사이즈** | 🟢 **논문 supplementary p14** |
| **depth 를 erosion + bilateral 로 denoise** | 🟢 **논문 §5 Implementation p13** |
| **테스트 시 refinement iteration = 5** | 🟢 **논문 supplementary p14** (*"5 for pose estimation, 1 for tracking"*) |
| crop 을 3D 에서 `mesh_diameter × crop_ratio` 로 잡는다 | `Utils.py:605` (+ 호출 `predict_pose_refine.py:31`, `method='box_3d'` at `:30`) |
| crop 창 → `input_resize` 로 리사이즈 | `Utils.py:597-598` |
| `crop_ratio` 1.2(refiner) / 1.1(scorer) · `input_resize` 160 | `weights/2023-10-28-18-33-37/config.yml` · `weights/2024-01-11-20-02-45/config.yml` |
| 어느 가중치가 refiner/scorer 인가 | `predict_pose_refine.py:97` · `predict_score.py:120` |
| **평행이동 보폭만 `mesh_diameter/2` 배** | `predict_pose_refine.py:228-229` (`normalize_xyz: true`) |
| **회전 보폭은 상수 20°** | `predict_pose_refine.py:221` + `config.yml` `rot_normalizer: 0.3490658503988659` |
| 우리 릴리스가 타는 분기 | `predict_pose_refine.py:194-199` (`trans_rep: tracknet`) |
| R·t 갱신이 분리된다 | `Utils.py:850-857` |
| `mesh_diameter` 계산(무작위 10,000점 쌍거리 최댓값) | `estimater.py:54` → `Utils.py:569-575` |
| stage2 가 메쉬를 갈아탄다 | `spatial_vision/stages/pose_fp.py:286` · `:291` (`est1.register` `:374` · `est2.track_one` `:416`) |
| 두 메쉬의 원점이 같다 | `assets/obj/<id>/meta.json` 의 `origin` · `spatial_vision.cad.verify_obj` |

```bibtex
@InProceedings{foundationposewen2024,
  author    = {Bowen Wen and Wei Yang and Jan Kautz and Stan Birchfield},
  title     = {{FoundationPose}: Unified 6D Pose Estimation and Tracking of Novel Objects},
  booktitle = {CVPR},
  year      = {2024},
}
```
