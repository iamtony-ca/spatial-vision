"""M2 확장 — 씬 randomization + distractor / occluder.

`capture_sim.py` 가 쓰는 헬퍼. 최소 씬(dome light + ground + 객체 하나)에 다음을 얹는다:

  1. **조명**  dome 세기·색온도 + 상반구의 rect/distant 조명 N개 (그림자 방향이 프레임마다 바뀐다)
  2. **distractor**  바닥에 흩뿌리는 방해물. ★ **같은 FOUP 인스턴스**를 포함한다 —
     "유사 인스턴스 오선택률"(PIPELINE_PLAN §M4 판정 기준)은 이것 없이는 측정할 수 없다.
  3. **occluder**  카메라→타깃 시선 위에 놓아 **부분 가림을 보장**한다. 무작위로 뿌리면
     대부분의 프레임에서 아무것도 가리지 않아 표본이 낭비된다.
  4. **가림 정량화**  clutter 를 숨긴 채 한 번 더 렌더해 `visib_fract` 를 실측한다
     (BOP 의 visib_fract 와 같은 정의). 가림 정도와 오차의 상관을 보려면 이 값이 필요하다.
  5. **배경(HDRI)**  dome light 의 latlong 텍스처를 프레임마다 갈아끼우고 회전시킨다.
  6. **재질(MDL/OmniPBR)**  바닥과 **FOUP 몸체**의 색·거칠기·금속성을 흔든다.

★★ **`top_flange` 는 프레임마다 바뀌지 않는다** (5·6 의 설계 제약)
    flange 는 pose 원점이자 SEMI 표준부이고, exemplar 참조·ISM 템플릿이 기대하는 외관이다.
    재질은 **`<foup>/body` 프림에만** 바인딩한다 — `top_flange` 는 형제 프림이라 상속되지 않는다.
    (USD 바인딩은 프림 하위로만 전파된다. 루트에 걸면 flange 까지 물든다 — 그래서 루트에 걸지 않는다.)
    `--flange-color` 를 주면 flange 에 **고정색**(실물 FOUP 처럼 검정) 재질을 한 번만 칠한다 —
    randomize 가 아니라 상수다. `eval.verify_randomization` 이 이 불변식을 렌더 픽셀로 검사한다.

⚠️ **distractor 의 semantic class 에 `obj_id` 가 들어가면 안 된다.** `masks_from_semantic` 이
   라벨을 매칭해 GT 마스크를 만들기 때문에, `foup_300_semi_distractor` 같은 이름을 쓰면
   distractor 가 GT 에 섞여 들어가 **모든 지표가 조용히 오염된다.** 그래서 `distractor` 를 쓴다.

★ 6.0.1 API (설치본에서 확인한 것만 사용 — sdg_ws randomizers 와 동일 계열)
    rep.functional.create.{xform,reference,cube,sphere,cylinder,cone,rect_light,distant_light}
    rep.functional.create.material(mdl="OmniPBR.mdl", bind_prims=[...])
    rep.functional.modify.{visibility,semantics}
    조명 세기·색온도·dome 텍스처·shader 입력은 USD 속성을 **직접** 세팅한다
    (replicator 그래프 상태보다 결정적이고, 프레임마다 되돌릴 필요가 없다).

자산은 `bash envs/fetch_env_assets.sh` 로 받는다 (`assets/env/{hdri,ground}/`).

미구현(sdg_ws 에 있으니 필요해지면 이식): 환경 USD(창고·사무실) 배경 교체, 물리 낙하 배치.
"""

from __future__ import annotations

import colorsys
import math
from pathlib import Path

import numpy as np

_HDRI_EXTS = (".hdr", ".exr", ".png", ".jpg", ".jpeg")
_TEX_EXTS = (".png", ".jpg", ".jpeg")


class SceneRandomizer:
    def __init__(self, args, rng, world_path: str, target_prim, obj_usd: str):
        self.a = args
        self.rng = rng
        # ★ 외관(HDRI·재질)은 **별도 난수 스트림**에서 뽑는다.
        #   같은 스트림에서 뽑으면 외관 옵션을 켜는 것만으로 뒤따르는 **기하 추첨(카메라 거리·고도·
        #   방위·객체 yaw)이 통째로 밀린다.** 그러면 randomization 켠 런과 끈 런이 다른 씬이 되어
        #   "배경·재질 때문에 나빠졌다" 를 **기하 차이와 분리할 수 없다.**
        #   스트림을 나누면 두 런이 프레임 단위로 짝지어져 n=40 짝지은 비교가 된다(실측 확인).
        self.rng_app = np.random.default_rng(int(getattr(args, "seed", 0)) * 7919 + 104729)
        self.world = world_path
        self.target = target_prim
        self.obj_usd = obj_usd
        self.distractors: list = []       # (prim, kind)
        self.occluders: list = []
        self.lights: list = []
        self.dome = None
        self._state: dict = {}
        self._hdris: list[str] = []
        self._hdri_gain: dict[str, float] = {}
        self._ground_tex: list[str] = []
        self._body_tex: list[str] = []
        self._ground_shader = None
        self._body_shaders: list = []      # 타깃 + distractor FOUP 의 body shader
        self._flange_shaders: list = []    # flange 고정색 shader (프레임마다 흔들지 않는다)

    # ── setup ────────────────────────────────────────────────────────────────
    def setup(self, dome_prim=None, ground_prims=None):
        """풀을 미리 만들어 두고 프레임마다 보이기/숨기기만 한다(생성·삭제는 비싸다)."""
        import omni.replicator.core as rep

        self.dome = dome_prim
        rep.functional.create.xform(name="Clutter", parent=self.world)
        root = f"{self.world}/Clutter"

        # distractor: 같은 FOUP n_foup 개 + 원시 도형 나머지
        n_foup = min(self.a.distractor_foups, self.a.distractors)
        for i in range(self.a.distractors):
            if i < n_foup:
                p = rep.functional.create.reference(
                    usd_path=self.obj_usd, parent=root, name=f"dist_foup_{i}",
                    semantics={"class": "distractor"})   # ⚠️ obj_id 를 포함시키지 말 것
                kind = "foup"
            else:
                fn = [rep.functional.create.cube, rep.functional.create.sphere,
                      rep.functional.create.cylinder, rep.functional.create.cone][i % 4]
                p = fn(parent=root, name=f"dist_prim_{i}", semantics={"class": "distractor"})
                kind = "prim"
            rep.functional.modify.visibility(p, False)
            self.distractors.append((p, kind))

        for i in range(self.a.occluders):
            fn = [rep.functional.create.cube, rep.functional.create.cylinder][i % 2]
            p = fn(parent=root, name=f"occ_{i}", semantics={"class": "occluder"})
            rep.functional.modify.visibility(p, False)
            self.occluders.append(p)

        for i in range(self.a.light_fixtures):
            fn = rep.functional.create.rect_light if i % 2 == 0 else rep.functional.create.distant_light
            p = fn(parent=root, name=f"light_{i}", intensity=0.0)
            rep.functional.modify.visibility(p, False)
            self.lights.append(p)

        self._setup_background()
        self._setup_materials(ground_prims)

    # ── 배경(HDRI) ────────────────────────────────────────────────────────────
    def _setup_background(self):
        """HDRI 풀을 모으고, 맵마다 평균 복사휘도를 재서 **세기 보정 게인**을 미리 계산한다.

        ⚠️ dome intensity 는 HDRI 를 **곱한다.** 맵마다 평균 밝기가 12.9배 차이나므로(실측)
           보정 없이 섞으면 어떤 프레임은 새까맣고 어떤 프레임은 날아간다 — randomization 이
           아니라 **노출 사고**가 된다.

        게인은 `1/평균휘도` 로 잡는다. 그러면 실효 밝기 = 뽑은 intensity 그대로가 되어
        **`--dome-intensity` 가 HDRI 유무와 무관하게 같은 뜻**을 갖는다. 중앙값 기준으로 맞추면
        (sdg_ws 방식) 맵 간 편차는 없어지지만 절대 밝기가 텍스처 없는 dome 과 달라져,
        기존에 튜닝한 intensity 밴드를 다시 잡아야 한다.
        """
        self._hdris = _collect(getattr(self.a, "hdri", None), _HDRI_EXTS)
        if not self._hdris or not getattr(self.a, "hdri_normalize", True):
            return
        means = {p: _mean_radiance(p) for p in self._hdris}
        bad = [Path(p).name for p, v in means.items() if not v or v <= 0]
        if bad:                      # 읽기 실패를 조용히 게인 1.0 으로 넘기지 않는다
            raise RuntimeError(f"HDRI 평균휘도를 못 쟀다: {bad} — --no-hdri-normalize 로 끄거나 파일을 확인할 것")
        self._hdri_gain = {p: 1.0 / v for p, v in means.items()}

    # ── 재질(OmniPBR) ─────────────────────────────────────────────────────────
    def _setup_materials(self, ground_prims):
        """바닥과 **FOUP 몸체**에 각각 OmniPBR 재질을 하나씩 만들어 바인딩한다.

        재질은 프레임마다 **만들지 않는다** — 프림당 하나를 만들고 shader 입력만 흔든다.
        (생성은 비싸고, 스테이지에 재질이 프레임 수만큼 쌓인다.)

        ★★ body 프림에만 바인딩한다. `top_flange` 는 형제라 영향을 받지 않는다.
        """
        import omni.usd
        from pxr import UsdShade

        self._ground_tex = _collect(getattr(self.a, "ground_textures", None), _TEX_EXTS)
        self._body_tex = _collect(getattr(self.a, "body_textures", None), _TEX_EXTS)
        stage = omni.usd.get_context().get_stage()

        if getattr(self.a, "ground_material", False) and ground_prims:
            self._ground_shader = _make_material("mat_ground", list(ground_prims))

        flange_rgb = getattr(self.a, "flange_color", None)
        if getattr(self.a, "body_material", False) or flange_rgb:
            # 타깃 + distractor FOUP 전부. 타깃만 흔들면 **몸체 색이 타깃 식별 단서**가 되어
            # segmentation 점수가 부풀려진다 — distractor 도 같은 분포에서 흔들어야 한다.
            targets = [self.target] + [p for p, kind in self.distractors if kind == "foup"]
            for i, root_prim in enumerate(targets):
                if getattr(self.a, "body_material", False):
                    body = stage.GetPrimAtPath(f"{root_prim.GetPath()}/body")
                    if not body or not body.IsValid():
                        raise RuntimeError(f"body 서브프림을 찾을 수 없다: {root_prim.GetPath()}/body")
                    self._body_shaders.append(_make_material(f"mat_body_{i:02d}", [body]))
                fl = stage.GetPrimAtPath(f"{root_prim.GetPath()}/top_flange")
                if flange_rgb:
                    # ★ flange 는 **고정 색**이다. 프레임마다 흔들지 않는다 —
                    #   pose 앵커이자 exemplar 참조가 기대하는 외관이므로 한 번만 칠하고 둔다.
                    if not fl or not fl.IsValid():
                        raise RuntimeError(f"top_flange 서브프림을 찾을 수 없다: {root_prim.GetPath()}")
                    sh = _make_material(f"mat_flange_{i:02d}", [fl])
                    _set_pbr(sh, color=tuple(flange_rgb),
                             roughness=float(getattr(self.a, "flange_roughness", 0.45)),
                             metallic=float(getattr(self.a, "flange_metallic", 0.0)))
                    self._flange_shaders.append(sh)
                elif fl and fl.IsValid() and UsdShade.MaterialBindingAPI(fl).ComputeBoundMaterial()[0]:
                    raise RuntimeError(
                        f"top_flange 에 재질이 걸렸다: {fl.GetPath()} — 몸체 전용 계약 위반")

    # ── per-frame ────────────────────────────────────────────────────────────
    def randomize(self, eye: np.ndarray, target_center: np.ndarray, target_radius_m: float,
                  occluder_shrink: float = 1.0):
        """프레임 하나에 대한 배치. 반환값은 meta 에 기록할 상태 dict.

        `occluder_shrink` < 1 이면 occluder 를 줄이고 시선에서 더 비껴 놓는다 —
        프리체크에서 너무 많이 가려졌을 때 재시도용이다(캡처 프레임을 버리지 않기 위해).
        """
        import omni.replicator.core as rep
        from pxr import Gf, UsdGeom, UsdLux

        rng = self.rng
        st: dict = {}

        # 1) 조명 + 배경(HDRI) --------------------------------------------------
        dome_i = float(rng.uniform(*self.a.dome_intensity))
        kelvin = float(rng.uniform(*self.a.color_temperature_k))
        hdri = None
        if self.dome is not None:
            if self._hdris:
                ar = self.rng_app                            # ★ 외관 전용 스트림
                hdri = self._hdris[int(ar.integers(len(self._hdris)))]
                _set_dome_texture(self.dome, hdri)
                dome_i *= self._hdri_gain.get(hdri, 1.0)     # 맵별 평균 밝기 보정
                lo, hi = getattr(self.a, "hdri_rotate_deg", (0.0, 0.0))
                if hi > lo:
                    _set_dome_rotation(self.dome, float(ar.uniform(lo, hi)))
            _set_light(self.dome, dome_i, kelvin)
        st["background"] = {"hdri": Path(hdri).name if hdri else None,
                            "dome_intensity_after_gain": dome_i}
        n_fix = int(rng.integers(self.a.light_fixtures_active[0], self.a.light_fixtures_active[1] + 1)) \
            if self.lights else 0
        active = rng.permutation(len(self.lights))[:n_fix] if self.lights else []
        for i, p in enumerate(self.lights):
            on = i in active
            rep.functional.modify.visibility(p, bool(on))
            if not on:
                continue
            el = math.radians(float(rng.uniform(30.0, 85.0)))
            az = math.radians(float(rng.uniform(-180.0, 180.0)))
            d = float(rng.uniform(*self.a.light_distance_m))
            pos = target_center + np.array([d * math.cos(el) * math.cos(az),
                                            d * math.cos(el) * math.sin(az),
                                            d * math.sin(el)])
            _place_look_at(p, pos, target_center)
            _set_light(p, float(rng.uniform(*self.a.fixture_intensity)), kelvin)
        st["lighting"] = {"dome_intensity": dome_i, "color_temperature_k": kelvin,
                          "n_fixtures": int(n_fix)}

        # 2) distractor — 바닥에 흩뿌리되 타깃/서로 겹치지 않게 -------------------
        placed: list[tuple[float, float, float]] = [(0.0, 0.0, target_radius_m)]
        n_d = int(rng.integers(self.a.distractors_active[0], self.a.distractors_active[1] + 1)) \
            if self.distractors else 0
        chosen = rng.permutation(len(self.distractors))[:n_d]
        n_foup_shown = 0
        for i, (p, kind) in enumerate(self.distractors):
            on = i in chosen
            rep.functional.modify.visibility(p, bool(on))
            if not on:
                continue
            r = target_radius_m if kind == "foup" else float(rng.uniform(*self.a.distractor_size_m)) / 2
            xy = _reject_sample(rng, placed, r, self.a.scatter_radius_m)
            if xy is None:                      # 자리를 못 찾으면 그냥 숨긴다(억지로 겹치지 않는다)
                rep.functional.modify.visibility(p, False)
                continue
            placed.append((xy[0], xy[1], r))
            if kind == "foup":
                n_foup_shown += 1
                _place(p, (xy[0], xy[1], self.a._z_lift), rot_z_deg=float(rng.uniform(-180, 180)))
            else:
                s = float(rng.uniform(*self.a.distractor_size_m))
                _place(p, (xy[0], xy[1], s / 2), scale=s,
                       rot=(float(rng.uniform(0, 360)), float(rng.uniform(0, 360)),
                            float(rng.uniform(0, 360))))
        st["distractors"] = {"n_shown": len(placed) - 1, "n_foup": n_foup_shown}

        # 3) occluder — 카메라→타깃 시선 위에 놓아 가림을 보장 -------------------
        n_o = int(rng.integers(self.a.occluders_active[0], self.a.occluders_active[1] + 1)) \
            if self.occluders else 0
        chosen_o = rng.permutation(len(self.occluders))[:n_o]
        for i, p in enumerate(self.occluders):
            on = i in chosen_o
            rep.functional.modify.visibility(p, bool(on))
            if not on:
                continue
            t = float(rng.uniform(*self.a.occluder_ray_frac))     # 시선 위 위치 (0=타깃, 1=카메라)
            # ★ 조준점을 **몸체 중간**으로 내린다. 원점(=flange 주 상면)을 겨누면 occluder 가
            #   flange 를 덮는다 — "top flange 는 온전히 보인다" 는 전제와 어긋난다.
            aim = np.array(target_center, float)
            aim[2] -= self.a.occluder_aim_drop_m
            base = aim + (eye - aim) * t
            # 시선에서 살짝 비껴 놓아야 '부분' 가림이 된다 (정확히 올리면 전체를 가린다)
            sigma = self.a.occluder_offset_sigma / max(occluder_shrink, 1e-3)
            off = rng.normal(0.0, target_radius_m * sigma, 3)
            off[2] = abs(off[2]) * 0.3
            s = float(rng.uniform(*self.a.occluder_size_m)) * occluder_shrink
            _place(p, tuple(base + off), scale=s,
                   rot=(float(rng.uniform(0, 360)),) * 3)
        st["occluders"] = {"n_shown": int(n_o), "shrink": float(occluder_shrink)}

        # 4) 재질 — 바닥, 그리고 FOUP **몸체만** ---------------------------------
        ar = self.rng_app                          # ★ 외관 전용 스트림 (기하 추첨을 밀지 않는다)
        mat_st: dict = {}
        if self._ground_shader is not None:
            tex = self._ground_tex[int(ar.integers(len(self._ground_tex)))] if self._ground_tex else None
            _set_pbr(self._ground_shader,
                     color=_hsv(ar, (0.0, 1.0), self.a.ground_saturation, self.a.ground_value),
                     roughness=float(ar.uniform(*self.a.ground_roughness)),
                     metallic=0.0, texture=tex,
                     texture_scale=float(ar.uniform(*self.a.ground_texture_scale)))
            mat_st["ground"] = {"texture": Path(tex).name if tex else None}
        if self._body_shaders:
            bodies = []
            for sh in self._body_shaders:          # 타깃·distractor 를 **독립적으로** 흔든다
                tex = self._body_tex[int(ar.integers(len(self._body_tex)))] if self._body_tex else None
                c = _hsv(ar, (0.0, 1.0), self.a.body_saturation, self.a.body_value)
                r = float(ar.uniform(*self.a.body_roughness))
                m = float(ar.uniform(*self.a.body_metallic))
                _set_pbr(sh, color=c, roughness=r, metallic=m, texture=tex,
                         texture_scale=float(ar.uniform(*self.a.body_texture_scale)))
                bodies.append({"rgb": [round(v, 4) for v in c], "roughness": round(r, 4),
                               "metallic": round(m, 4),
                               "texture": Path(tex).name if tex else None})
            mat_st["bodies"] = bodies             # [0] = 타깃, 이후 distractor FOUP
        if mat_st or self._flange_shaders:
            fc = getattr(self.a, "flange_color", None)
            # ★ 불변식: flange 는 프레임마다 바뀌지 않는다. verify_randomization 이 픽셀로 검사한다.
            mat_st["flange"] = {"fixed_rgb": list(fc)} if fc else "unchanged"
            st["materials"] = mat_st

        self._state = st
        return st

    # ── 불변식 검사 ───────────────────────────────────────────────────────────
    def body_material_summary(self) -> dict | None:
        """meta 기록용 — 현재 프레임의 타깃 몸체 재질."""
        b = self._state.get("materials", {}).get("bodies")
        return b[0] if b else None

    # ── 가림 정량화 ───────────────────────────────────────────────────────────
    def hide_all_clutter(self):
        import omni.replicator.core as rep

        self._prev = ([bool(_visible(p)) for p, _ in self.distractors],
                      [bool(_visible(p)) for p in self.occluders])
        for p, _ in self.distractors:
            rep.functional.modify.visibility(p, False)
        for p in self.occluders:
            rep.functional.modify.visibility(p, False)

    def restore_clutter(self):
        import omni.replicator.core as rep

        d, o = getattr(self, "_prev", ([], []))
        for (p, _), v in zip(self.distractors, d):
            rep.functional.modify.visibility(p, v)
        for p, v in zip(self.occluders, o):
            rep.functional.modify.visibility(p, v)


# ── 자산 풀 ──────────────────────────────────────────────────────────────────
def _collect(spec, exts: tuple[str, ...]) -> list[str]:
    """디렉토리 / 개별 파일 / 그 둘의 목록 → 정렬된 절대경로 리스트.

    정렬은 seed 재현성을 위해서다 — glob 순서는 파일시스템에 따라 달라진다.
    """
    if not spec:
        return []
    if isinstance(spec, (str, Path)):
        spec = [spec]
    out: list[str] = []
    for s in spec:
        p = Path(s).expanduser()
        if p.is_dir():
            out += [str(f.resolve()) for f in p.rglob("*") if f.suffix.lower() in exts]
        elif p.is_file():
            out.append(str(p.resolve()))
        else:
            raise FileNotFoundError(f"자산 경로가 없다: {p}  (bash envs/fetch_env_assets.sh)")
    if not out:
        raise FileNotFoundError(f"자산을 하나도 못 찾았다: {spec} (확장자 {exts})")
    return sorted(set(out))


def _mean_radiance(path: str) -> float | None:
    """HDRI 의 평균 휘도. 실패하면 None(게인 1.0 으로 둔다).

    ⚠️ `IMREAD_UNCHANGED` 로 읽는다. `IMREAD_ANYDEPTH|IMREAD_COLOR` 는 .hdr 을 float 로 주지만
       범위가 0~수천이라, 이걸 8/16-bit 로 오인해 65535 로 나누면 **평균이 0 이 된다**
       (실측: 14개 맵 중 11개가 0.0000 으로 나와 정규화가 통째로 무효화됐다).
       dtype 으로 판단한다 — 값 범위로 추측하지 않는다.
    """
    import cv2

    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None or img.ndim != 3:
        return None
    if img.dtype == np.uint8:
        img = img.astype(np.float32) / 255.0
    elif img.dtype == np.uint16:
        img = img.astype(np.float32) / 65535.0
    else:
        img = img.astype(np.float32)          # float HDR — 이미 선형 복사휘도다
    # BGR → 상대휘도. HDRI 는 위/아래 왜곡이 크지만 게인 목적에는 단순 평균으로 충분하다.
    return float((img[..., 2] * 0.2126 + img[..., 1] * 0.7152 + img[..., 0] * 0.0722).mean())


def _hsv(rng, hue, sat, val) -> tuple[float, float, float]:
    h = float(rng.uniform(*hue))
    s = float(rng.uniform(*sat))
    v = float(rng.uniform(*val))
    return colorsys.hsv_to_rgb(h, s, v)


# ── 저수준 헬퍼 ──────────────────────────────────────────────────────────────
def _set_dome_texture(prim, path: str):
    from pxr import Sdf

    a = prim.GetAttribute("inputs:texture:file")
    if not a:
        a = prim.CreateAttribute("inputs:texture:file", Sdf.ValueTypeNames.Asset)
    a.Set(Sdf.AssetPath(str(path)))
    f = prim.GetAttribute("inputs:texture:format")
    if not f:
        f = prim.CreateAttribute("inputs:texture:format", Sdf.ValueTypeNames.Token)
    f.Set("latlong")


def _set_dome_rotation(prim, deg: float):
    """dome 을 z 축(up) 기준으로 돌린다 = 배경이 흐른다. UsdLux dome 의 up 은 stage up(+Z)."""
    from pxr import UsdGeom

    UsdGeom.XformCommonAPI(prim).SetRotate((0.0, 0.0, float(deg)))


def _make_material(name: str, bind_prims: list):
    """OmniPBR 재질을 만들어 주어진 프림들에 바인딩하고 shader 를 돌려준다.

    ⚠️ **`rep.functional.create.material(bind_prims=...)` 를 쓰면 안 된다.**
       참조(reference) 안에서만 정의된 프림 — 우리의 `<foup>/body` 가 정확히 그렇다 — 에 대해
       **조용히 실패한다**: `material:binding` 관계는 생기지만 타깃이 비어 있고 예외도 없다.
       (실측: 루트 레이어에 스펙이 있는 Sphere 는 되고, `PrimStack=[mesh.usda]` 인 body 는 안 된다.
        참조 **루트**에 걸면 되지만 그러면 `top_flange` 까지 물든다 — 우리 계약 위반.)
       그래서 재질만 만들고 바인딩은 `UsdShade` 로 직접 한다. `Bind()` 의 반환값도 확인한다.
    """
    import omni.replicator.core as rep
    from pxr import UsdShade

    mat = rep.functional.create.material(mdl="OmniPBR.mdl", name=name)
    material = UsdShade.Material(mat)
    for p in bind_prims:
        if not UsdShade.MaterialBindingAPI.Apply(p).Bind(material):
            raise RuntimeError(f"재질 바인딩 실패: {p.GetPath()} ← {mat.GetPath()}")
        if not UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial()[0]:
            raise RuntimeError(f"바인딩이 반영되지 않았다: {p.GetPath()}")
    return _shader_of(mat, UsdShade)


def _shader_of(mat_prim, UsdShade):
    for child in mat_prim.GetChildren():
        if UsdShade.Shader(child):
            return UsdShade.Shader(child)
    src = UsdShade.Material(mat_prim).ComputeSurfaceSource("mdl")
    if src and src[0]:
        return src[0]
    raise RuntimeError(f"OmniPBR shader 를 못 찾았다: {mat_prim.GetPath()}")


def _set_pbr(shader, color, roughness: float, metallic: float,
             texture: str | None = None, texture_scale: float = 1.0):
    """OmniPBR.mdl 입력. 이름은 /isaac-sim/kit/mdl/core/Base/OmniPBR.mdl 에서 확인한 것."""
    from pxr import Gf, Sdf

    shader.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(
        Gf.Vec3f(*[float(c) for c in color]))
    shader.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(float(roughness))
    shader.CreateInput("metallic_constant", Sdf.ValueTypeNames.Float).Set(float(metallic))
    # ⚠️ 텍스처를 끌 때는 입력을 **지우지 말고 빈 경로**를 넣는다. 지우면 이전 프레임 값이 남는다.
    shader.CreateInput("diffuse_texture", Sdf.ValueTypeNames.Asset).Set(
        Sdf.AssetPath(str(texture) if texture else ""))
    if texture:
        # CAD 유래 메쉬는 UV 가 없다 → 월드 평면 투영으로 강제한다(없으면 텍스처가 안 보인다).
        shader.CreateInput("project_uvw", Sdf.ValueTypeNames.Bool).Set(True)
        shader.CreateInput("world_or_object", Sdf.ValueTypeNames.Bool).Set(True)
        shader.CreateInput("texture_scale", Sdf.ValueTypeNames.Float2).Set(
            Gf.Vec2f(float(texture_scale), float(texture_scale)))


def _visible(prim) -> bool:
    a = prim.GetAttribute("visibility")
    return not (a and a.Get() == "invisible")


def _set_light(prim, intensity: float, kelvin: float):
    from pxr import Sdf

    for name, val, typ in (("inputs:intensity", float(intensity), Sdf.ValueTypeNames.Float),
                           ("inputs:enableColorTemperature", True, Sdf.ValueTypeNames.Bool),
                           ("inputs:colorTemperature", float(kelvin), Sdf.ValueTypeNames.Float)):
        a = prim.GetAttribute(name)
        if not a:
            a = prim.CreateAttribute(name, typ)
        a.Set(val)


def _place(prim, position, scale=None, rot=None, rot_z_deg=None):
    import omni.replicator.core as rep

    kw = {"position_value": tuple(float(v) for v in position)}
    if rot is not None:
        kw["rotation_value"] = tuple(float(v) for v in rot)
    elif rot_z_deg is not None:
        kw["rotation_value"] = (0.0, 0.0, float(rot_z_deg))
    if scale is not None:
        kw["scale_value"] = (float(scale),) * 3
    rep.functional.modify.pose(prim, **kw)


def _place_look_at(prim, position, target):
    import omni.replicator.core as rep

    rep.functional.modify.pose(prim,
                               position_value=tuple(float(v) for v in position),
                               look_at_value=tuple(float(v) for v in target))


def _reject_sample(rng, placed, r, scatter_r, tries: int = 40):
    """이미 놓인 것들과 겹치지 않는 (x,y). 못 찾으면 None."""
    for _ in range(tries):
        a = float(rng.uniform(0, 2 * math.pi))
        d = float(rng.uniform(0, scatter_r))
        x, y = d * math.cos(a), d * math.sin(a)
        if all(math.hypot(x - px, y - py) > (r + pr) * 1.15 for px, py, pr in placed):
            return (x, y)
    return None
