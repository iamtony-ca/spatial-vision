#!/usr/bin/env python3
"""A그룹 원샷 러너 — **근접 촬영 한 벌**에서 A1~A4 를 전부 낸다 (추가 촬영 0).

    envs/pose/bin/python tools/run_group_a.py --in runs/real01 --out runs/real01_A

왜 이 도구인가
    지금 실험 환경에는 **로봇이 없다**(사용자 확정 2026-08-12) — 카메라 + FOUP 뿐이고
    손으로 움직인다. 그래서 **1 사이클 촬영 1회** 파이프라인만 돌릴 수 있고, 실행 목록은
    `docs/PIPELINE_CATALOG.md §9.1★c` 의 A그룹이다. A2~A4 는 **A1 과 같은 사진**에
    플래그만 바꿔 붙는다 — 손으로 이으면 4개 venv 를 오가며 명령 8개를 치게 되고,
    그 사이 `--input-scale 0.5`(없으면 OOM) 나 **거리별 SAM3 참조** 같은 걸 빠뜨린다.

무엇을 돌리는가 (`docs/RESULTS.md §34-11` 배포 구성 [A] 기준)

    st        stereo_onnx --scale 0.5
    seg       segment_sam3 --target flange --refs sam3_refs_flange_n25 --n-refs 3
    fp_ns2    pose_fp --primary flange --no-stage2   ← 배포본
    fp_s2     pose_fp --primary flange               ← A4 대조군 (pose_refined.json 용)

    A1  홀 제외   refine_contour --outer-only                                  = 배포본 [A] / P9
    A2a 홀 윤곽   refine_contour --outer-only --keep-hole-mm 25                = 규격부 / P7h
    A2b 홀 중심   refine_contour --outer-only --keep-hole-mm 25 --hole-center-mm 25 = P8
    A3  정합 off  (돌릴 게 없다 — `fp_ns2/pose_coarse.json` 이 곧 결과다)
    A4  refine on refine_contour --outer-only  (초기값 = `fp_s2/pose_refined.json`)

    전부 `--gate-deg 1.5`. 그리고 다섯 결과에 **좌우 투영 일관성**(`eval.lr_consistency`)과
    **오버레이 시트**(`viz.overlay_pose`)를 건다.

    ov        overlay_sheet.png + overlay/overlay_frame_*.png   ← 육안 판정

★ `--ism` — ISM 경로(I그룹, SAM-6D ISM)를 함께 돌린다. **추가 촬영 0, 플래그 하나.**

    seg_ism   segment_sam6d --target full --select score   ← CAD 템플릿. SAM3 비의존
    fp_ism    pose_fp --primary full --no-stage2 --masks seg_ism
    I1        refine_contour --outer-only                  ← A1 과 정합 조건 동일
    I3        정합 off (= fp_ism/pose_coarse.json)         ← I1 의 이득 분모

    🔴 목적은 «어느 쪽이 정확한가» 가 아니라 **«도메인 갭이 어디에 오는가»** 다.
       SAM3 참조는 **sim 렌더**라 실사진과 갭이 있고, ISM 템플릿은 **CAD 형상**이라 그 축이 없다.
       그래서 두 경로가 «독립» 이어야 뜻이 있다 — `--select score` 를 쓰고 진단용 `seg_full` 처럼
       SAM3 마스크를 exemplar 로 받지 않는다.
    ⚠️ **I1 은 `--primary full` 이다** — ISM 은 `full` 만 쓸 수 있다(flange 전용 ISM 템플릿은
       오선택 23/40 으로 금지). 즉 A1↔I1 은 **분할뿐 아니라 pose 메쉬도 다르다.**
       차이를 «분할 백엔드» 하나로 돌리면 안 된다 — 리포트도 방향만 말한다.
    ⚠️ ISM 템플릿(`ism_full/`)은 CAD 렌더라 **거리 무관**이다. SAM3 참조와 정반대로
       거리대마다 다시 만들 필요가 없다.

★ `--sam3-text` — SAM3 를 **참조 없이 낱말로** 돌리는 경로(T그룹). **추가 촬영 0.**

    seg_txt   segment_sam3 --target full --prompt "…" --confidence 0.05 --select center
    fp_txt    pose_fp --primary full --no-stage2 --masks seg_txt
    T1        refine_contour --outer-only                  ← A1·I1 과 정합 조건 동일
    T3        정합 off (= fp_txt/pose_coarse.json)         ← T1 의 이득 분모

    🔴 **실물에서 실제로 통과한 원거리 경로가 이쪽이었다**(§35-2m). exemplar 는 «참조 사진과
       닮았는가» 를 묻고 텍스트는 «낱말에 맞는가» 를 묻는다 — **참조 자산의 도메인 갭이 없다.**
    🔴 **프롬프트를 실물 몸체에 맞춘다.** 기본 `"black plastic box"` 는 sim 검정 몸체 기준이다.
       반투명 주황이면 `--text-prompt "orange plastic box"`, 투명이면 `"clear plastic box"`.
    ⚠️ **미검출은 마스크 품질이 아니라 임계값 문제**다(§35-2m-2): 50cm 에서 conf 0.15 → 17/20,
       0.05 → **20/20** 인데 IoU 중앙은 0.986 으로 불변이었다.
    🔴🔴 **그렇다고 0.05 를 기본으로 쓰면 안 된다 (2026-08-20 정정).** 그 sim 씬은
       **`distractors: 0 · occluders: 0`** 이라 «오선택 0» 이 **공허한 측정**이었다 —
       고를 다른 물체가 없었을 뿐이다. 실물에서 **배경 물체를 집었다.** 기본값은 사용자가
       실물에서 검증한 **0.15** 다. 내리는 것은 **오버레이로 무엇을 집었는지 확인한 뒤**에만.
    ⚠️ `--select center` 는 «카메라가 타깃을 겨눈다» 는 씬 규약에 기댄다(교훈 #15) — sim 은 그렇게
       생성돼 **자기순환**이다. 실물에서는 배경을 집을 수 있으니 **오버레이로 확인**하고,
       필요하면 `--text-select score` 로 바꾼다.
    ⚠️ T1 도 `--primary full` 이다 — 텍스트로 `flange` 를 따로 뽑으면 안 된다(§M4: SAM3 의 결손이
       flange 에 몰린다, recall 0.844 vs body 0.968). **A1↔I1↔T1 은 pose 메쉬가 A 만 다르다.**

🔴 실환경에는 GT 가 없다 — 리포트는 **GT-free 지표만** 낸다
    ① **게이트 후퇴율**  — 폭주 여부. 홀 전략 셋을 비교하면 *"CAD 홀이 실물과 맞는가"* 가 나온다(§28-5)
    ② **좌우 투영 일관성** — 왼쪽만 보고 정합한 pose 를 오른쪽에 투영해 채점. A3 판정의 유일한 근거
    ③ **대응점 수·rms·이동량** — 신호가 실제로 있었는지
    ④ **오버레이 시트** — ①~③ 은 전부 «자기 일관성» 이라 *«다 같이 틀린»* 경우를 못 잡는다.
       사진 위에 투영해 눈으로 보는 것만이 그 축을 본다(교훈 #39·#46 이 그렇게 잡혔다).
    절대 오차(mm·도)는 실물에서 **잴 수 없다.** 리포트에 R/t 오차가 없는 것은 버그가 아니다.

★ **거리 삼각 대조** (`RESULTS.md §35-2l`) — GT 가 없어도 **z 편향은 잡을 수 있다**
    `FP 추정 z` ↔ `stereo depth(flange **평면적합**)` ↔ (선택) `--true-distance-mm 줄자값`.
    앞의 둘만으로도 *"둘 중 하나가 틀렸다"* 는 갈리고, 줄자를 주면 **어느 쪽인지**까지 나온다.
    🔴 depth 쪽은 **평면 적합**이어야 한다 — 마스크 안 depth 중앙값은 원근·융기 때문에 pose
    원점 z 보다 구조적으로 ~7mm 작아 **거짓 경보를 낸다**(교훈 #84, 실제로 밟았다).
    덤으로 나오는 **flange 평면 잔차 rms** 가 «depth 가 맞는가» 의 정량 지표다 —
    `valid.png` 100% 는 범위 검사일 뿐이라 «뚫렸다» 를 뜻하지 않는다. sim 기준선 **0.37mm**.

★ **실험 노트** — 실물은 한 번에 안 된다. 시행착오가 복구 가능해야 한다
    `<out>/run_meta.json`   날짜·시각 · `--note` 메모 · 전체 인자 · 참조 출처 · **내용 해시**
    `tools/compare_runs.py <런들…> --index runs/runs_index.md`  설정 diff 먼저 → 지표 나란히

⚠️ 프레임 레이아웃은 `<in>/frame_XXXX/` 여야 한다
    `tools/make_frame_from_zed.py --out runs/real01/frame_0000` 이 그렇게 만든다.
    단일 프레임 디렉토리를 바로 주면 `pose_fp --depth-dir` 의 경로 규약과 어긋나
    **조용히 틀린 depth 를 읽는다** — 그래서 여기서 막는다.

⚠️ 인터프리터는 `envs/pose/bin/python` 이다 (numpy·cv2 를 쓴다).
   스테이지 자체는 각자의 venv 를 subprocess 로 부르므로 venv 를 활성화하면 안 된다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

VISION = Path(__file__).resolve().parents[1]
PY = {
    "stereo_onnx": VISION / "envs/stereo_onnx/bin/python",
    "sam3": VISION / "envs/seg_sam3/bin/python",
    "sam6d": VISION / "envs/seg_sam6d/bin/python",
    "pose": VISION / "envs/pose/bin/python",
}
STEREO_MODEL = "weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx"

# ★★ **모드 = 후보 파이프라인을 얼마나 넓게 펼치는가** (`--mode`, 쉼표로 겹친다)
#    실물 초반에는 sim 최적이 안 맞을 수 있으니 **축을 넓혀 봐야 한다**(사용자 방침, 2026-08-22).
#    🔴 다만 넓히기는 «탐색» 이지 «성능 향상» 이 아니다 — 팔 수가 늘수록 **선택 편향**이 커진다.
#    비용은 10프레임 실측(콜드스타트 포함)에서 낸 것: 정합 팔 **5초** · 분할 13초 · FP 18초.
#    → 정합·게이트 축은 사실상 공짜라 여기부터 넓히는 게 맞다.
MODES = {
    "quick":   {"arms": "0", "cost": "−40초 (더 싸다)",
                "what": "정합 팔 전부 뺀다. A3·I3·T3 만 — 「끝까지 도는가」 + 분할 3종 비교"},
    "default": {"arms": "4~6", "cost": "기준",
                "what": "현행 배포 후보 — A1(배포본)·A2a·A2b·A4 (+I1 +T1)"},
    "contour": {"arms": "+5~6", "cost": "+50~60초",
                "what": "정합·게이트 축: 탐색폭 16/32px · 게이트 0/0.75/3.0° · `--fix-z` 반대쪽. "
                        "🔴 실물 «t 가 10mm 밀린다» 가 갈리는 축이고 FP 재계산이 없다"},
    "init":    {"arms": "+1", "cost": "+15초",
                "what": "하이브리드 초기값(R=coarse · t=refined, §27-7) — 단일 시점 R 1.5배. GT 불필요"},
    "cascade": {"arms": "+1", "cost": "+35초",
                "what": "coarse-to-fine 정합 32→12→8 (§35-2k-3) — 횡 포획 4mm → 24mm. "
                        "게이트 기준을 최초 FP 로 맞춰(`--gate-ref-dir`) 다른 팔과 나란히 읽힌다"},
    # 🔴 이 모드는 «A 경로» 가 아니다 (2026-08-23 정정, 배선 감사가 잡았다 — §35-2p-7).
    #    근접에는 **SAM3 `full` 참조가 없어** `seg_full` 을 ISM 으로 뽑는다. 그래서 이 팔은
    #    「SAM3 full」이 아니라 **「ISM full + `--select exemplar`」** 이고, `I1`(ISM full +
    #    `--select score`)과 **선택 규칙만** 다르다. 방해물이 없으면 둘이 같은 마스크가 된다.
    "select": {"arms": "+1", "cost": "+40초",
               "what": "ISM `full` 마스크의 **타깃 지정 규칙** 대조 — `--select exemplar`"
                       "(flange 로 지목) vs `I1` 의 `--select score`. 방해물이 없으면 **`I1` 과 "
                       "같은 결과가 정상**이다(교훈 #15). 옛 이름 `primary` 도 받는다"},
    "edge":    {"arms": "+5", "cost": "+25초",
                "what": "정합기가 **어느 밝기 경계를 잡는가**: `--polarity` 3종 × `--min-grad` 2종. "
                        "🔴 검정 몸체에서 융기 능선을 잡는 §35-2i 편향을 직접 겨냥한다 — "
                        "한 번도 안 흔들어 본 노브다"},
    "refs":    {"arms": "+N", "cost": "+36초/개",
                "what": "SAM3 **참조 거리대 스윕** (`--refs-sweep n30black,n40black,…`) + `--n-refs` 1/5. "
                        "🔴 참조는 거리 종속이라 틀리면 조용히 무너진다 — «실제 거리가 몇인가» 를 "
                        "데이터가 답하게 한다"},
    "wide":    {"arms": "+13~14", "cost": "+3~4분",
                "what": "= default + contour + init + cascade + select + edge. **실물 초반 권장**. "
                        "⚠️ `refs` 는 뺀다(비용 자릿수가 다르고 초기값이 달라지는 비교라 성격이 다르다) "
                        "— 필요하면 `--mode wide,refs`"},
    "all":     {"arms": "전부", "cost": "+4~6분",
                "what": "quick 을 뺀 전부 (refs 스윕 포함). ★ **`--ism`·`--sam3-text` 도 자동으로 켠다** "
                        "— «all» 은 경로도 전부라는 뜻이다"},
}

# 거리대 → SAM3 참조. 🔴 참조는 **거리 종속**이라 틀리면 IoU 가 조용히 무너진다(§34-6).
REFS_BY_PRESET = {
    # 구 세트 — 몸체를 randomize 해서 만든 것 (외관 축이 없다)
    "n20": ("sam3_refs_flange_n20", "0.18~0.24m"),
    "n25": ("sam3_refs_flange_n25", "0.22~0.30m"),
    "n30": ("sam3_refs_flange_n30", "0.28~0.35m"),
}
# ★ 실물 FOUP **몸체 외관 3종**(사용자 확정 2026-08-13) × 거리대. `--preset n50orange` 처럼 쓴다.
#   ⚠️ 손으로 나열하면 오타가 난다 — **표에서 생성**한다. 없는 디렉토리는 실행 시점에 걸린다.
#   🔴 거리는 **열어 두고 접근한다** — 실물에서 0.5m 가 sim 최적점(0.22~0.30m)보다 좋았다.
#   ⚠️ 밴드 문자열은 **구 세트 표(위)와 같은 값**이어야 한다 — `n30` 은 두 곳에 나온다.
_BANDS = {"25": "0.22~0.30m", "30": "0.28~0.35m", "40": "0.35~0.45m",
          "50": "0.45~0.55m", "60": "0.55~0.65m", "70": "0.65~0.75m"}
_APPS = {"black": "몸체 검정 불투명 (최난이도)", "orange": "몸체 반투명 주황",
         "clear": "몸체 투명", "mixed": "3종 혼합 ⚠️ refs-mode independent 로 자동 전환"}
for _cm, _band in _BANDS.items():
    for _app, _d in _APPS.items():
        REFS_BY_PRESET[f"n{_cm}{_app}"] = (f"sam3_refs_flange_n{_cm}_{_app}", f"{_band} · {_d}")
# §34-9 — 이 거리대에서 flange 등가지름이 이 근처여야 정합 이득이 난다(0.82× ↔ 1.66× 를 가른 값)
TARGET_FLANGE_PX = 419.0

# ────────────────────────────────────────────────────────── sim 기준선
# 🔴 **이건 «정상 범위» 가 아니라 «sim 에서 잰 값» 이다.** 실물이 여기서 벗어나는 것은
#    «고장» 일 수도 «도메인 갭» 일 수도 있다 — 표는 판정을 대신하지 않고 **비교 대상을 준다.**
#    출처: `runs/e2e_A`·`runs/fakereal_oA`(n25 orange) · `runs/fakereal30oA`(n30 orange), 각 n=20,
#    2026-08-19. **조건 2개에서만 잰 값**이라 대역이 좁다 — 첫 실물 런 이후 real 값으로 갱신할 것.
#    (키, 라벨, lo, hi, 단위, 주석)
SIM_BASELINE_CAPTURE = [
    ("plane_rms_mm", "flange 평면 잔차", 0.30, 0.45, "mm",
     "🔴 실물에서 가장 벌어질 값 — 스테레오 관통 품질. 3mm 초과면 열린 항목 #1"),
    ("z_minus_depth_mm", "FP z − depth 평면", 0.3, 1.6, "mm",
     "두 독립 추정의 일치도. 부호까지 본다"),
    ("valid_ring", "주변 depth 유효율", 0.99, 1.0, "",
     "⚠️ sim 은 항상 1.0 이다 — 실물이 낮은 건 당연하고, **얼마나** 낮은지가 정보다"),
]
SIM_BASELINE_A1 = [
    ("gated_pct", "게이트 후퇴", 0.0, 15.0, "%", "초기값이 나쁘거나 CAD 가 다르면 오른다"),
    ("n_corr", "대응점", 1500, 2100, "개", "`--outer-only` 기준. 홀을 쓰면 14,000 급이 정상"),
    ("rms_px", "정합 잔차", 0.30, 1.00, "px", "적합도 — 🔴 «맞는가» 는 못 말한다(교훈 #56)"),
    ("moved_deg_med", "정합 이동량", 0.40, 0.90, "°", "게이트 τ=1.5° 와 같은 축"),
    ("lr_ddx", "좌우 |Δdx|", 0.15, 0.60, "px", "변형 간 차이로 읽는 게 원칙이지만 대역은 참고된다"),
]


def sh(cmd: list[str], dry: bool) -> int:
    print("  $ " + " ".join(str(c) for c in cmd))
    if dry:
        return 0
    return subprocess.call([str(c) for c in cmd], cwd=VISION)


class Step:
    """⚠️ 완료 판정은 스테이지마다 다르다 — stereo 만 메타를 **프레임마다** 쓰고
    나머지(segment·pose·contour·lr)는 출력 루트에 하나 쓴다. 이걸 틀리면 조용히
    «항상 처음부터» 가 되거나(느림) «절반만 돌고 완료» 가 된다(틀림)."""

    def __init__(self, sid: str, desc: str, cmd: list, out: Path, sentinel: str,
                 per_frame: bool = False, optional: bool = False):
        self.sid, self.desc, self.cmd, self.out = sid, desc, cmd, out
        self.sentinel, self.per_frame = sentinel, per_frame
        # ⚠️ **진단용 스테이지가 진단 대상을 죽이면 안 된다**(교훈 #79 — Blender 프리페치가
        #    set -e 로 뒤의 venv 를 통째로 날렸다). optional 은 실패해도 다음으로 간다.
        self.optional = optional

    def resolve(self) -> list:
        """★ `cmd` 가 함수면 **실행 직전에** 부른다.

        진단 스테이지(`ov`·`diag`)는 «어느 팔이 실제로 pose 를 냈는가» 에 따라 가리킬 곳이
        달라진다. 스텝 목록은 런 시작 시점에 만들어지므로 그때는 아직 아무것도 없다.
        → 앞 스텝이 끝난 뒤에 결정하도록 미룬다."""
        self.cmd = self.cmd() if callable(self.cmd) else self.cmd
        return self.cmd

    def done(self, frames: list[Path]) -> bool:
        if self.per_frame:
            return bool(frames) and all((self.out / f.name / self.sentinel).exists()
                                        for f in frames)
        return (self.out / self.sentinel).exists()


def _n_pose(d: Path) -> int:
    """그 디렉토리가 실제로 낸 pose 개수. 정합 팔은 `pose_refined.json`,
    FP 팔은 `pose_coarse.json` 이라 **둘 다** 센다."""
    d = Path(d)
    return len(list(d.glob("frame_*/pose_refined.json"))) or \
        len(list(d.glob("frame_*/pose_coarse.json")))


def _live_preds(cands: list[str]) -> list[str]:
    """`dir` 또는 `dir:name` 목록에서 **pose 가 실제로 있는 것만** 남긴다.
    전부 비면 원본을 그대로 돌려준다 — 그래야 «왜 비었나» 가 오류 메시지로 드러난다."""
    live = [c for c in cands if _n_pose(c.split(":")[0])]
    if live and len(live) != len(cands):
        drop = [Path(c.split(":")[0]).name for c in cands if c not in live]
        print(f"    ⚠️ pose 가 없는 팔은 뺀다: {', '.join(drop)}", flush=True)
    return live or cands


def _live_pose_dir(cands: list[Path]) -> Path:
    """진단 시트의 6번 패널이 가리킬 곳 — **pose 를 낸 첫 팔**."""
    for d in cands:
        if _n_pose(d):
            if d != cands[0]:
                print(f"    ⚠️ `{cands[0].name}` 에 pose 가 없다 → 진단 시트는 "
                      f"**`{d.name}`** 을 가리킨다", flush=True)
            return d
    return cands[0]


def _live_seg(cands: list[Path], mask_name: str, fallback: Path) -> Path:
    """마스크 패널이 가리킬 분할 산출물 — **마스크가 실제로 있는 첫 것**."""
    for d in cands:
        if list(Path(d).glob(f"frame_*/{mask_name}")):
            if d != cands[0]:
                print(f"    ⚠️ `{Path(cands[0]).name}` 에 {mask_name} 이 없다 → "
                      f"**`{Path(d).name}`** 을 쓴다", flush=True)
            return d
    return fallback


def build_steps(a) -> list[Step]:
    obj = Path(a.obj)
    refs_name = a.refs or REFS_BY_PRESET[a.preset][0]
    refs = obj / refs_name
    o = Path(a.out)
    st, seg = o / "st", o / "seg"
    ns2, s2 = o / "fp_ns2", o / "fp_s2"

    fp_common = ["--obj", obj, "--masks", seg, "--depth", "stereo", "--depth-dir", st,
                 "--primary", "flange", "--flange-mask-from", "pose",
                 "--input-scale", a.input_scale]          # 🔴 없으면 1920×1200 에서 OOM (§34-12)
    rc_common = ["--obj", obj, "--mesh", "top_flange.ply", "--gate-deg", a.gate_deg]
    if a.fix_z:
        rc_common += ["--fix-z"]

    steps = [
        Step("st", "stereo (ONNX)",
             [PY["stereo_onnx"], "-m", "spatial_vision.stages.stereo_onnx",
              "--in", a.in_dir, "--out", st, "--scale", a.stereo_scale,
              "--model", STEREO_MODEL],
             st, "meta_stereo.json", per_frame=True),
        Step("seg", f"segment flange (SAM3 exemplar, {refs_name})",
             [PY["sam3"], "-m", "spatial_vision.stages.segment_sam3",
              "--in", a.in_dir, "--out", seg, "--target", "flange",
              "--refs", refs, "--n-refs", a.n_refs, "--refs-mode", a.refs_mode]
             + (["--prompts-file", obj / "sam3_prompts.json"] if a.use_prompts_file else []),
             seg, "meta_segment_flange.json"),
        # 🔵 **진단 전용** — pose 에는 안 쓴다. 근접에서 `full` 을 뽑을 SAM3 참조가 없으므로
        #    사진 참조가 필요 없는 **ISM(CAD 템플릿)** 을 쓴다. 타깃 지정은 flange 마스크로 한다
        #    («동일 인스턴스가 여럿이면 시스템이 정해줘야 한다» — `--select center` 는 교훈 #15).
        Step("seg_full", "segment full (ISM · 진단용)",
             [PY["sam6d"], "-m", "spatial_vision.stages.segment_sam6d",
              "--in", a.in_dir, "--out", o / "seg_full", "--target", "full",
              "--templates", obj / "ism_full", "--cad", obj / "full.ply",
              "--depth", "stereo", "--depth-dir", st,
              "--select", "exemplar", "--exemplar-dir", seg],
             o / "seg_full", "meta_segment_full.json", optional=True),
        Step("fp_ns2", "FoundationPose --no-stage2 (배포본 초기값)",
             [PY["pose"], "-m", "spatial_vision.stages.pose_fp",
              "--in", a.in_dir, "--out", ns2, "--no-stage2"] + fp_common,
             ns2, "meta_pose.json"),
        Step("fp_s2", "FoundationPose stage2 on (A4 대조군)",
             [PY["pose"], "-m", "spatial_vision.stages.pose_fp",
              "--in", a.in_dir, "--out", s2] + fp_common,
             s2, "meta_pose.json"),
    ]

    # ── ISM 경로 (I그룹) — CAD 템플릿 단독, SAM3 비의존 ────────────────────────────────────────
    # 🔴 A그룹과 **한 군데도 공유하지 않는다**(stereo depth 만 공유). 분할도 pose 도 따로 간다.
    #    그래야 «SAM3 참조의 도메인 갭» 이 결과 차이로 드러난다.
    if a.ism:
        seg_i, ism_fp = o / "seg_ism", o / "fp_ism"
        steps += [
            # ⚠️ `--select score` 다 — 진단용 `seg_full` 은 SAM3 마스크를 exemplar 로 받지만
            #    여기서 그러면 SAM3 에 의존하게 돼 비교가 성립하지 않는다.
            #    ⚠️ `--select center` 는 쓰지 않는다(교훈 #15: 파편·배경을 집는다).
            Step("seg_ism", "segment full (ISM · CAD 템플릿, SAM3 비의존)",
                 [PY["sam6d"], "-m", "spatial_vision.stages.segment_sam6d",
                  "--in", a.in_dir, "--out", seg_i, "--target", "full",
                  "--templates", obj / "ism_full", "--cad", obj / "full.ply",
                  "--depth", "stereo", "--depth-dir", st, "--select", "score"],
                 seg_i, "meta_segment_full.json"),
            # 🔴 `--primary full` 이다 — ISM 은 `full` 만 쓸 수 있다. **flange 전용 ISM 템플릿은
            #    금지**다(오선택 23/40): flange 만 떼면 CAD 형상의 변별력이 사라진다.
            Step("fp_ism", "FoundationPose (ISM 마스크 · --primary full)",
                 [PY["pose"], "-m", "spatial_vision.stages.pose_fp",
                  "--in", a.in_dir, "--out", ism_fp, "--no-stage2",
                  "--obj", obj, "--masks", seg_i, "--depth", "stereo", "--depth-dir", st,
                  "--primary", "full", "--flange-mask-from", "pose",
                  "--input-scale", a.input_scale],
                 ism_fp, "meta_pose.json"),
        ]

    # ── SAM3 «텍스트» 경로 (T그룹) — 참조 자산 비의존 ──────────────────────────────────────────
    # 🔴 A그룹(exemplar)과 **같은 모델·다른 조건부**다. A 는 참조 이미지에, T 는 낱말에 건다.
    #    실물에서 실제로 통과한 원거리 경로가 이쪽이었다(§35-2m) — 참조의 도메인 갭을 우회한다.
    # ⚠️ `--select center` 는 «카메라가 타깃을 겨눈다» 는 씬 규약에 기댄다(교훈 #15).
    #    실물에서 배경·파편을 집을 수 있으므로 **오버레이로 반드시 확인**한다. `--text-select` 로 바꾼다.
    if a.sam3_text:
        seg_t, txt_fp = o / "seg_txt", o / "fp_txt"
        steps += [
            Step("seg_txt", f"segment full (SAM3 텍스트 “{a.text_prompt}” · 참조 비의존)",
                 [PY["sam3"], "-m", "spatial_vision.stages.segment_sam3",
                  "--in", a.in_dir, "--out", seg_t, "--target", "full",
                  "--prompt", a.text_prompt, "--confidence", a.text_conf,
                  "--select", a.text_select],
                 seg_t, "meta_segment_full.json"),
            # 🔴 `--primary full` 이다 — 텍스트로는 `flange` 를 따로 못 뽑는다(§ M4: SAM3 의 결손이
            #    flange 에 몰린다, recall 0.844 vs body 0.968). I그룹과 같은 이유로 `full` 만 쓴다.
            Step("fp_txt", "FoundationPose (텍스트 마스크 · --primary full)",
                 [PY["pose"], "-m", "spatial_vision.stages.pose_fp",
                  "--in", a.in_dir, "--out", txt_fp, "--no-stage2",
                  "--obj", obj, "--masks", seg_t, "--depth", "stereo", "--depth-dir", st,
                  "--primary", "full", "--flange-mask-from", "pose",
                  "--input-scale", a.input_scale],
                 txt_fp, "meta_pose.json"),
        ]

    # ══════════════════════════════════════════════════════════════════════════════════
    #  변형(팔) 구성 — `--mode` 로 넓힌다
    # ══════════════════════════════════════════════════════════════════════════════════
    # 🔴🔴 **팔을 늘리는 것은 «후보 탐색» 이지 «성능 향상» 이 아니다.** 실물 초반에는 sim 최적이
    #    안 맞을 수 있으니 축을 넓혀 보는 게 맞지만(사용자 방침), 팔이 늘수록 **선택 편향**이 커진다:
    #    n=20 프레임에서 팔 20개를 돌리고 «가장 좋아 보이는 것» 을 고르면 그건 대개 잡음이다.
    #    → 리포트가 팔 수 × 표본 수로 경고를 낸다. **사전 정의 규칙**(이동량 ≥10mm 등)이
    #      사후 선택보다 항상 낫다.
    # 비용 실측(10프레임·콜드스타트 포함): **정합 팔 5초** · 분할 팔 13초 · FP 팔 18초.
    #    → 정합·게이트 축은 사실상 공짜다. 여기부터 넓힌다.
    #
    # (id, 설명, 초기 pose 디렉토리, 초기 pose 파일명, 추가 플래그)
    arms = [
        ("A1", "홀 제외  --outer-only            ← 배포본 [A]/P9", ns2, "pose_coarse.json",
         ["--outer-only"]),
        ("A2a", "홀 윤곽  +--keep-hole-mm 25      (규격부/P7h)", ns2, "pose_coarse.json",
         ["--outer-only", "--keep-hole-mm", "25"]),
        ("A2b", "홀 중심  +--hole-center-mm 25    (P8)", ns2, "pose_coarse.json",
         ["--outer-only", "--keep-hole-mm", "25", "--hole-center-mm", "25"]),
        ("A4", "refine on 초기값 (§32 판정)", s2, "pose_refined.json", ["--outer-only"]),
    ]
    # I1 = ISM 초기값 + 같은 정합·같은 게이트. **A1 과 정합 조건이 동일**해야 앞단(분할·pose)의
    # 차이만 남는다 — 그래서 `--outer-only` 를 똑같이 준다.
    if a.ism:
        arms.append(("I1", "ISM 초기값 + 정합       ← A1 의 CAD-only 대조군",
                     o / "fp_ism", "pose_coarse.json", ["--outer-only"]))
    if a.sam3_text:
        arms.append(("T1", "텍스트 초기값 + 정합    ← 참조 비의존 대조군",
                     o / "fp_txt", "pose_coarse.json", ["--outer-only"]))

    modes = set(a.mode)
    if "quick" in modes:                     # 「끝까지 도는가」 + 분할 3종만. 정합 팔 0
        arms = []

    # ── contour : 정합·게이트 축 (FP 재계산 0 · 팔당 5초) ───────────────────────────
    #    실물 초반에 **가장 값어치 있는 축**이다 — «t 가 10mm 밀린다» 는 여기서 갈린다.
    if "contour" in modes:
        arms += [
            # 포획 반경. §35-2k: `--search-px` 를 키우면 좋은 초기값에서는 손해지만
            # **횡 포획 반경이 4mm → 16~24mm** 로 넓어진다. 초기값이 밀려 있으면 이쪽이 산다.
            ("Cs16", "탐색폭 16px (포획 반경 ↑)", ns2, "pose_coarse.json",
             ["--outer-only", "--search-px", "16"]),
            ("Cs32", "탐색폭 32px (포화 지점)", ns2, "pose_coarse.json",
             ["--outer-only", "--search-px", "32"]),
            # 게이트 τ. §27-5 의 GT-free 규칙은 «융합 쌍거리 중앙» 인데 단일 시점엔 융합이 없다
            # → **여기서 직접 스윕한다.** 0 = 게이트 끔(정합 결과를 그대로 낸다).
            ("Cg0", "게이트 off (정합 원본)", ns2, "pose_coarse.json",
             ["--outer-only", "--gate-deg", "0"]),
            ("Cg3", "게이트 3.0° (느슨)", ns2, "pose_coarse.json",
             ["--outer-only", "--gate-deg", "3.0"]),
            ("Cg07", "게이트 0.75° (엄격)", ns2, "pose_coarse.json",
             ["--outer-only", "--gate-deg", "0.75"]),
        ]
        # `--fix-z` 는 store_true 라 끌 수 없다 → **반대쪽만** 붙인다.
        if not a.fix_z:
            arms.append(("Cz", "--fix-z on (Z 고정)", ns2, "pose_coarse.json",
                         ["--outer-only", "--fix-z"]))
        else:
            print("    ⚠️ `--fix-z` 가 이미 켜져 있어 contour 모드의 `Cz` 팔은 뺀다", flush=True)

    # ── init : 초기값 축 (§27-7 — 회전은 coarse, 평행이동은 refined) ────────────────
    #    ★ **단일 시점 경로가 R 1.5배 좋아진다**(0.367 → 0.245). hand-eye·다중시점 불필요.
    #    ⚠️ clean 한정 — 오염이면 refined 가 붕괴한다(§26-4). §32 판정 절차가 그걸 걸러 준다.
    if "init" in modes:
        hyb = o / "fp_hyb"
        steps.append(Step("fp_hyb", "하이브리드 초기값 (R=coarse · t=refined, §27-7)",
                          [PY["pose"], "-m", "spatial_vision.eval.hybrid_pose",
                           "--r-dir", ns2, "--r-name", "pose_coarse.json",
                           "--t-dir", s2, "--t-name", "pose_refined.json", "--out", hyb],
                          hyb, "meta_hybrid.json"))
        arms.append(("H1", "하이브리드 초기값 + 정합 (§27-7)", hyb, "pose_coarse.json",
                     ["--outer-only"]))

    # ── cascade : coarse-to-fine 정합 (§35-2k-3) ───────────────────────────────────
    #    `32@4 → 12@4 → 8@8`. 정밀도는 `s8` 급이면서 **횡 포획을 4 → 24mm** 로 넓힌다.
    #    🔴 마지막 단의 게이트 기준을 **최초 FP 초기값**으로 맞춘다(`--gate-ref-dir`) —
    #       안 그러면 이동량이 «직전 단 대비» 라 다른 팔과 **다른 양**이 된다(교훈 #26).
    if "cascade" in modes:
        c1, c2 = o / "Ccas_s1", o / "Ccas_s2"
        for sid, pdir, pname, extra, outd in (
                ("Ccas_s1", ns2, "pose_coarse.json", ["--search-px", "32", "--per-edge", "4"], c1),
                ("Ccas_s2", c1, "pose_refined.json", ["--search-px", "12", "--per-edge", "4"], c2)):
            steps.append(Step(sid, f"캐스케이드 {sid[-2:]} (게이트 off)",
                              [PY["pose"], "-m", "spatial_vision.stages.refine_contour",
                               "--in", a.in_dir, "--pose-dir", pdir, "--pose-name", pname,
                               "--out", outd, "--obj", obj, "--mesh", "top_flange.ply",
                               "--outer-only", "--gate-deg", "0"] + extra,
                              outd, "meta_contour.json"))
        arms.append(("Ccas", "캐스케이드 32→12→8 (§35-2k-3)", c2, "pose_refined.json",
                     ["--outer-only", "--search-px", "8", "--per-edge", "8",
                      "--gate-ref-dir", str(ns2), "--gate-ref-name", "pose_coarse.json"]))

    # ── edge : 정합기가 **어느 밝기 경계를 잡는가** (FP 재계산 0 · 팔당 5초) ───────────
    #    🔴 **검정 몸체의 핵심 문제를 직접 겨냥한다.** §35-2i 에서 GT 초기값 검증으로 갈랐듯이,
    #    검정 위 검정이면 바깥 경계에 밝기 차가 없어 `find_edges` 가 **융기 능선**(안쪽 4~6px)을
    #    잡고 정합기가 그리로 성실히 수렴한다(`gt_bias_px` −2.04). 편향이 프레임마다 같은 방향이라
    #    **게이트가 못 막는다.** 그런데 그 «어느 경계를 고르나» 노브(`--polarity`·`--min-grad`)를
    #    지금까지 **한 번도 흔들어 보지 않았다.** 여기서 연다.
    #    ⚠️ 기본 `auto` 는 프레임마다 극성을 스스로 고른다 — 아래는 그걸 **고정**한 대조군이다.
    if "edge" in modes:
        arms += [
            ("Ed", "극성 고정 dark_out (물체가 어둡다)", ns2, "pose_coarse.json",
             ["--outer-only", "--polarity", "dark_out"]),
            ("Eb", "극성 고정 bright_out (물체가 밝다)", ns2, "pose_coarse.json",
             ["--outer-only", "--polarity", "bright_out"]),
            ("Ea", "극성 무관 any (부호 안 봄)", ns2, "pose_coarse.json",
             ["--outer-only", "--polarity", "any"]),
            # 기울기 문턱. 높이면 «약한 경계» 를 버린다 → 융기 능선처럼 **약한** 에지를 배제할 수
            # 있지만 검정 위 검정에서는 진짜 외곽도 약하다. 양쪽으로 흔들어 어느 쪽인지 본다.
            ("Eg3", "최소 기울기 3.0 (약한 에지 배제)", ns2, "pose_coarse.json",
             ["--outer-only", "--min-grad", "3.0"]),
            ("Eg05", "최소 기울기 0.5 (약한 에지 허용)", ns2, "pose_coarse.json",
             ["--outer-only", "--min-grad", "0.5"]),
        ]

    # ── refs : SAM3 참조 **거리대 스윕** (분할 + FP 를 새로 돈다 · 팔당 36초) ────────────
    #    🔴 참조는 **거리 종속**이라 틀리면 조용히 무너진다(원거리 참조로 근접 질의 시 IoU 0.044).
    #    실물에서 «몇 cm 인지» 를 우리가 모를 수 있다 — 그러면 **데이터가 답하게 하는 게 맞다.**
    #    ⚠️ 이 팔들은 **초기값이 서로 다르다** → 게이트 후퇴율로 비교하면 안 된다(교훈 #82).
    #       판정은 «분할 IoU 대리지표»(마스크 면적·중심 이탈, `segcmp`)와 좌우 일관성으로 한다.
    for ps in getattr(a, "refs_sweep_list", []):
        rn = REFS_BY_PRESET[ps][0]
        sg, fp = o / f"seg_{ps}", o / f"fp_{ps}"
        # 🔴 mixed 세트는 chain 이면 박스가 ref_0 에만 걸린다 — 여기서도 자동 전환한다.
        rmode = "independent" if ps.endswith("mixed") else a.refs_mode
        steps += [
            Step(f"seg_{ps}", f"segment flange (참조 {rn})",
                 [PY["sam3"], "-m", "spatial_vision.stages.segment_sam3",
                  "--in", a.in_dir, "--out", sg, "--target", "flange",
                  "--refs", obj / rn, "--n-refs", a.n_refs, "--refs-mode", rmode],
                 sg, "meta_segment_flange.json"),
            Step(f"fp_{ps}", f"FoundationPose (참조 {ps} · --no-stage2)",
                 [PY["pose"], "-m", "spatial_vision.stages.pose_fp",
                  "--in", a.in_dir, "--out", fp, "--no-stage2",
                  "--obj", obj, "--masks", sg, "--depth", "stereo", "--depth-dir", st,
                  "--primary", "flange", "--flange-mask-from", "pose",
                  "--input-scale", a.input_scale],
                 fp, "meta_pose.json"),
        ]
        arms.append((f"R_{ps}", f"참조 {ps} + 정합", fp, "pose_coarse.json", ["--outer-only"]))
    # `--n-refs` 축 — 참조 세트는 그대로 두고 **몇 장 쓰는가**만 바꾼다
    for nr in getattr(a, "refs_sweep_n", []):
        sg, fp = o / f"seg_nr{nr}", o / f"fp_nr{nr}"
        steps += [
            Step(f"seg_nr{nr}", f"segment flange ({refs_name} · n-refs {nr})",
                 [PY["sam3"], "-m", "spatial_vision.stages.segment_sam3",
                  "--in", a.in_dir, "--out", sg, "--target", "flange",
                  "--refs", refs, "--n-refs", nr, "--refs-mode", a.refs_mode],
                 sg, "meta_segment_flange.json"),
            Step(f"fp_nr{nr}", f"FoundationPose (n-refs {nr} · --no-stage2)",
                 [PY["pose"], "-m", "spatial_vision.stages.pose_fp",
                  "--in", a.in_dir, "--out", fp, "--no-stage2",
                  "--obj", obj, "--masks", sg, "--depth", "stereo", "--depth-dir", st,
                  "--primary", "flange", "--flange-mask-from", "pose",
                  "--input-scale", a.input_scale],
                 fp, "meta_pose.json"),
        ]
        arms.append((f"Rn{nr}", f"n-refs {nr} + 정합", fp, "pose_coarse.json", ["--outer-only"]))

    # ── select : ISM `full` 마스크의 **타깃 지정 규칙** 대조 ──────────────────────────
    #    🔴 옛 이름은 `primary` 였고 «A 경로를 --primary full 로» 라고 적혀 있었다. **틀렸다** —
    #       `seg_full` 은 근접에 SAM3 `full` 참조가 없어 **ISM 으로** 뽑는다(`--select exemplar`).
    #       따라서 이 팔은 `I1`(ISM full + `--select score`)과 **선택 규칙만** 다르고,
    #       방해물이 없으면 마스크가 **byte 단위로 같아진다**(sim 8·20프레임에서 실측).
    #       → 배선 감사 ①이 8프레임 런에서 `AF1 == I1` 로 잡아 냈다(§35-2p-7).
    #    ⚠️ 그래도 버리지 않는다 — 방해물이 있으면 갈리는 축이고, 그게 교훈 #15 의 «선택» 문제다.
    if "select" in modes:
        af = o / "fp_isel"
        steps.append(Step("fp_isel", "FoundationPose (ISM full 마스크 · --select exemplar)",
                          [PY["pose"], "-m", "spatial_vision.stages.pose_fp",
                           "--in", a.in_dir, "--out", af, "--no-stage2",
                           "--obj", obj, "--masks", o / "seg_full", "--depth", "stereo",
                           "--depth-dir", st, "--primary", "full",
                           "--flange-mask-from", "pose", "--input-scale", a.input_scale],
                          af, "meta_pose.json"))
        arms.append(("IX1", "ISM full · select exemplar + 정합 (I1 은 select score)",
                     af, "pose_coarse.json", ["--outer-only"]))
    for sid, desc, pdir, pname, extra in arms:
        d = Path(a.out) / sid
        steps.append(Step(sid, desc,
                          [PY["pose"], "-m", "spatial_vision.stages.refine_contour",
                           "--in", a.in_dir, "--pose-dir", pdir, "--pose-name", pname,
                           "--out", d] + rc_common + extra,
                          d, "meta_contour.json"))

    # 좌우 투영 일관성 — 전부 **같은 잣대**(외곽 실루엣)로 채점한다
    # ⚠️ 정합 «전» 도 채점한다 — 이득 배수(정합 후/전)를 내려면 분모가 있어야 한다.
    #    A3 = SAM3 경로의 정합 전, I3 = ISM 경로의 정합 전. **경로마다 자기 분모를 쓴다.**
    lr = [("A3", ns2, "pose_coarse.json")]
    if a.ism:
        lr.append(("I3", o / "fp_ism", "pose_coarse.json"))
    if a.sam3_text:
        lr.append(("T3", o / "fp_txt", "pose_coarse.json"))
    lr += [(sid, Path(a.out) / sid, "pose_refined.json") for sid, *_ in arms]
    for sid, pdir, pname in lr:
        steps.append(Step(f"lr_{sid}", f"좌우 투영 일관성 · {sid}",
                          [PY["pose"], "-m", "spatial_vision.eval.lr_consistency",
                           "--in", a.in_dir, "--pose-dir", pdir, "--pose-name", pname,
                           "--obj", obj, "--outer-only",
                           "--out", Path(a.out) / "lr", "--tag", sid],
                          Path(a.out) / "lr", f"lr_consistency_{sid}.json"))

    # 🔴 **육안 검사 시트 — 실환경에서 이게 유일한 «맞는가» 판정 수단이다.**
    #    GT 가 없으니 R/t 오차를 못 낸다. 남는 것은 *"투영 실루엣이 사진의 진짜 테두리에 붙는가"* 이고
    #    그건 겹쳐 그려야만 보인다. 변형 다섯을 **같은 크롭**으로 나란히 놓아 서로 어긋나는지도 본다.
    #    🔴 **없는 팔을 넘기면 시트 전체가 「없음」으로 나온다** — SAM3 flange 가 비면 A1~A4 가
    #    아예 안 만들어지는데, 같은 런의 `I1` 에는 멀쩡한 pose 가 있다. 그걸 못 보고 «pose 실패»
    #    로 오진한 전례가 있다 → **실행 직전에 실제로 pose 를 낸 팔만** 넘긴다.
    #    ★ **FP 원본(coarse)도 경로마다 넣는다** — 정합 전/후를 한 시트에서 봐야 «정합이 무엇을
    #      했는가» 가 보인다. 예전에는 A 경로의 coarse 하나만 있었다.
    ov_cands = [f"{ns2}:pose_coarse.json"] \
        + ([f"{o / 'fp_ism'}:pose_coarse.json"] if a.ism else []) \
        + ([f"{o / 'fp_txt'}:pose_coarse.json"] if a.sam3_text else []) \
        + [str(Path(a.out) / sid) for sid, *_ in arms]
    steps.append(Step("ov", "오버레이 시트 (육안 검사)",
                      lambda: [PY["pose"], "-m", "spatial_vision.viz.overlay_pose",
                               "--capture", a.in_dir, "--obj", obj, "--mesh", "top_flange.ply",
                               "--frames", a.overlay_frames, "--tile", 380,
                               "--mask-alpha", a.overlay_mask_alpha,
                               "--per-frame-dir", o / "overlay",
                               "--out", o / "overlay_sheet.png"]
                              + sum((["--pred", p] for p in _live_preds(ov_cands)), []),
                      o, "overlay_sheet.png", optional=True))

    # ★★ **겹쳐 그린 시트** — 타일을 나눠 그리면 «coarse 와 refined 가 얼마나 어긋나는가» 를
    #    눈으로 못 잰다. 같은 화소 위에 놓아야 보인다. 분할 백엔드별 FP 차이도 마찬가지다.
    # 🔴 **겹쳐 그리기는 «전부» 를 담으면 안 된다.** 팔레트가 8색이라 그 이상이면 색이 순환하고,
    #    주석 줄이 타일을 통째로 덮는다 — `--mode all`(30팔)에서 실제로 그렇게 됐다.
    #    → **항상 `default` 팔만** 겹친다(경로별 FP coarse + A1·A2a·A2b·A4 + I1 + T1).
    #      늘어난 팔은 «열로 나란히» 놓는 `overlay_sheet.png` 에서 본다. 역할을 나눈다.
    ovc_cands = [c for c in ov_cands
                 if ":" in c or Path(c).name in ("A1", "A2a", "A2b", "A4", "I1", "T1")]
    steps.append(Step("ovc", "겹쳐 그린 오버레이 (coarse↔refined · 경로별 FP · default 팔만)",
                      lambda: [PY["pose"], "-m", "spatial_vision.viz.overlay_pose",
                               "--capture", a.in_dir, "--obj", obj, "--mesh", "top_flange.ply",
                               "--combine", "--frames", a.overlay_frames, "--tile", 460,
                               "--max-combine", 9,
                               "--per-frame-dir", o / "overlay_combo",
                               "--out", o / "overlay_combo.png"]
                              + sum((["--pred", p] for p in _live_preds(ovc_cands)), []),
                      o, "overlay_combo.png", optional=True))

    # ★★ **분할 겹쳐 비교** — 러너는 분할이 3~4종 동시에 돈다. 따로 보면 «어느 것이 엉뚱한 물체를
    #    집었나» 를 비교할 수 없다. 🔴 실물 50cm 에서 ISM 이 화면 가장자리의 작은 물체를 집었고
    #    (면적 0.64% · 이탈 0.56) 텍스트만 맞게 집은 사례가 있다 — 그 판정을 눈으로 하는 도구다.
    seg_cands = [f"{seg}:mask_flange.png:A_exemplar_flange"] \
        + ([f"{o / 'seg_ism'}:mask_full.png:I_ISM_full"] if a.ism else []) \
        + ([f"{o / 'seg_txt'}:mask_full.png:T_text_full"] if a.sam3_text else []) \
        + [f"{o / 'seg_full'}:mask_full.png:진단용_full"]
    # ★★ **같은 타일에 그 경로의 FP pose 도 얹는다** — 마스크만 보면
    #    «마스크부터 엉뚱한 걸 잡았다» 와 «마스크는 맞는데 pose 가 틀렸다» 가 안 갈린다.
    #    처방이 정반대(분할 재설정 vs depth·초기값·CAD)라 이 구분이 실물에서 제일 비싸다.
    #    🔴 크롭을 안 하는 시트라 **가장자리 오선택도 화면에 남는다** — 그게 이 도구의 존재 이유다.
    segp_cands = [f"{ns2}:pose_coarse.json:A_pose"] \
        + ([f"{o / 'fp_ism'}:pose_coarse.json:I_pose"] if a.ism else []) \
        + ([f"{o / 'fp_txt'}:pose_coarse.json:T_pose"] if a.sam3_text else [])
    steps.append(Step("segcmp", "분할 + pose 겹쳐 비교 (무엇을 집었나 · pose 가 거기 붙었나)",
                      lambda: [PY["pose"], "-m", "spatial_vision.viz.seg_compare",
                               "--capture", a.in_dir, "--frames", a.overlay_frames,
                               # 🔴 여기서는 **`full.ply`** 다 — 겹쳐 볼 마스크가 `mask_full` 이라
                               #    `top_flange` 로 투영하면 «pose 가 마스크 안에 드는가» 를 못 잰다.
                               #    두 메쉬는 원점이 같으므로(규약) 같은 pose 를 그대로 쓴다.
                               "--obj", obj, "--mesh", "full.ply",
                               "--per-frame-dir", o / "segcmp",
                               "--out", o / "segcmp" / "seg_compare.png"]
                              + sum((["--seg", s] for s in seg_cands), [])
                              + sum((["--pose", p] for p in _live_preds(segp_cands)), []),
                      o / "segcmp", "seg_compare.png", optional=True))

    # 🔵 단계별 산출물 6패널 — «맞는가»(ov) 가 아니라 **«어디서 깨졌는가»** 를 본다.
    #    분할 0 · depth 미관통 · 노출 이상은 여기서만 갈린다.
    #    🔴 `--pose-dir` 를 `A1` 로 박아 두면 SAM3 flange 가 빈 런에서 6번 패널이 「없음」이 된다
    #    — `I1` 에 pose 가 있어도 그렇다. 마스크 패널도 마찬가지로 살아 있는 분할을 가리킨다.
    arm_ids = [sid for sid, *_ in arms]
    steps.append(Step("diag", "진단 시트 (원본·마스크 2종·depth·valid·pose)",
                      lambda: [PY["pose"], "-m", "spatial_vision.viz.diag_sheet",
                               "--in", a.in_dir, "--out", o / "diag",
                               "--seg-full", _live_seg([o / "seg_full", o / "seg_ism",
                                                        o / "seg_txt"],
                                                       "mask_full.png", o / "seg_full"),
                               "--seg-flange", seg,
                               "--depth-dir", st,
                               "--pose-dir", _live_pose_dir([Path(a.out) / s for s in arm_ids]),
                               "--obj", obj, "--frames", a.overlay_frames, "--width", 380,
                               "--gate-deg", a.gate_deg]
                              + (["--all"] if a.diag_all else []),
                      o / "diag", "diag_sheet.png", optional=True))

    # ★★ **실루엣 기반 거리** — 거리 대조의 네 번째 다리 (`baseline` 비의존, «독립» 은 아니다).
    #    🔴 `FP z` 와 `stereo depth` 는 **둘 다 `fx·B/disparity`** 에서 나온다. 아무리 잘 맞아도
    #    `fx·B` 가 틀렸으면 사이좋게 틀린다. 실루엣 크기는 `B` 를 안 쓰므로 **baseline 오차를 가른다.**
    #    (⚠️ `fx` 오차는 순수 스케일이라 이걸로도 못 잡는다 — 줄자뿐이다.)
    #    마스크와 메쉬가 **같은 대상**이어야 하므로 `mask_full` ↔ `full.ply` 로 짝짓는다.
    def _scale_pair():
        for sd, pd in ([(o / "seg_ism", o / "fp_ism")] if a.ism else []) \
                + ([(o / "seg_txt", o / "fp_txt")] if a.sam3_text else []) \
                + [(o / "seg_full", ns2)]:
            if _n_pose(pd) and any(Path(sd).glob("frame_*/mask_full.png")):
                return sd, pd
        return o / "seg_full", ns2
    steps.append(Step("scale", "실루엣 기반 거리 (baseline 비의존)",
                      lambda: (lambda sd, pd: [
                          PY["pose"], "-m", "spatial_vision.eval.scale_check",
                          "--in", a.in_dir, "--seg-dir", sd, "--mask", "mask_full.png",
                          "--pose-dir", pd, "--pose-name", "pose_coarse.json",
                          "--obj", obj, "--mesh", "full.ply",
                          "--out", o / "scale_check.json"])(*_scale_pair()),
                      o, "scale_check.json", optional=True))

    # 🔵 통계 — 흩어진 JSON 을 **한 표**로 합치고 분포 그래프·CSV 를 낸다.
    #    ⚠️ 반드시 마지막이다(위 산출물을 전부 읽는다).
    # 🔴 **«정합 off» 팔(A3·I3·T3)도 넣는다.** sim GT 채점에서 **이 셋이 1~3위**였는데(§35-2o-6)
    #    자기 디렉토리가 없어 통계 한 벌에서 통째로 빠져 있었다 — 「분석용 CSV 에 승자가 없는」
    #    상태였다. `--alias` 로 실제 pose 위치를 알려 준다.
    stat_ids = [sid for sid, *_ in arms] + ["A3"] \
        + (["I3"] if a.ism else []) + (["T3"] if a.sam3_text else [])
    stat_alias = ["A3=fp_ns2:pose_coarse.json"] \
        + (["I3=fp_ism:pose_coarse.json"] if a.ism else []) \
        + (["T3=fp_txt:pose_coarse.json"] if a.sam3_text else [])
    steps.append(Step("stats", "통계 표·그래프·CSV",
                      [PY["pose"], "-m", "spatial_vision.eval.group_stats",
                       "--root", o, "--variants", ",".join(stat_ids),
                       "--gate-deg", a.gate_deg]
                      + sum((["--alias", x] for x in stat_alias), []),
                      o / "stats", "summary.md", optional=True))
    return steps


# ─────────────────────────────────────────────────────────────── 리포트

def _med(v):
    return float(np.median(v)) if len(v) else float("nan")


def flange_plane_depth(depth: np.ndarray, core: np.ndarray, K: np.ndarray,
                       uv: np.ndarray) -> tuple[float, float, int] | None:
    """flange 중앙부 depth 에 **평면을 적합**하고 그 평면이 `uv` 시선과 만나는 z 를 낸다.

    🔴 **왜 중앙값이 아니라 평면인가** — 처음엔 «flange 마스크 안 depth 중앙값» 을 FP 의 z 와
    비교했는데 **거짓 경보가 났다**. sim GT 로 확인하니 그 중앙값은 pose 원점 z 보다 구조적으로
    **~7mm 작다**(GT depth 로 재도 똑같다). 원근 때문에 **가까운 쪽이 픽셀을 더 차지**하고,
    융기(+2mm)와 홀 깔때기가 섞이기 때문이다. **두 양이 애초에 같은 것이 아니었다.**
    평면을 적합해 **원점이 투영되는 시선 위에서** 평가하면 같은 양이 되고, 실측 오차가
    `-0.81mm`(GT 대비)로 떨어졌다.

    덤으로 **평면 잔차 rms** 가 나온다 — *"스테레오가 이 표면을 제대로 뚫었는가"* 의 정량 지표다
    (`valid.png` 100% 는 범위 검사일 뿐이라 틀린 값도 유효로 센다).
    """
    ys, xs = np.nonzero(core)
    if len(ys) < 200:
        return None
    z = depth[ys, xs].astype(np.float64)
    ok = z > 0
    ys, xs, z = ys[ok], xs[ok], z[ok]
    if len(z) < 200:
        return None
    X = (xs - K[0, 2]) / K[0, 0] * z
    Y = (ys - K[1, 2]) / K[1, 1] * z
    A = np.stack([X, Y, np.ones_like(z)], 1)             # z = aX + bY + c
    c = np.linalg.lstsq(A, z, rcond=None)[0]
    keep = np.ones(len(z), bool)
    for _ in range(3):                                   # 강건화 — 3σ 절단 반복
        r = z - A @ c
        s = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-6
        keep = np.abs(r - np.median(r)) < 3 * s
        if keep.sum() < 100:
            break
        c = np.linalg.lstsq(A[keep], z[keep], rcond=None)[0]
    rms = float(np.sqrt(np.mean((z[keep] - A[keep] @ c) ** 2))) if keep.sum() else float("nan")
    x, y = (uv[0] - K[0, 2]) / K[0, 0], (uv[1] - K[1, 2]) / K[1, 1]
    den = 1.0 - c[0] * x - c[1] * y
    if abs(den) < 1e-6:                                  # 평면이 시선과 거의 평행 — 못 쓴다
        return None
    return float(c[2] / den), rms, int(keep.sum())


def _sha8(p: Path) -> str | None:
    """파일 내용 해시 앞 8자리. **«같은 입력인가» 를 이름이 아니라 내용으로 확인**하기 위한 것."""
    if not Path(p).is_file():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()[:8]


def write_run_meta(a, frames: list[Path], elapsed: float | None = None) -> dict:
    """`<out>/run_meta.json` — **이 런이 무엇이었는가**. 실험 노트의 기계 판독본이다.

    왜 필요한가 — 실물은 시행착오다. 거리·조명·참조 세트·플래그를 바꿔 가며 여러 번 돌리는데,
    지금까지는 **무엇을 바꿨는지가 어디에도 안 남았다.** 지표를 아무리 늘려도 런 간 비교가
    안 되면 방향을 못 정한다. `tools/compare_runs.py` 가 이 파일을 읽어 **설정 diff 를 먼저** 낸다.

    ⚠️ **git 정보는 넣지 않는다**(사용자 방침). 대신 «어떤 상태였나» 는 **입력 파일 내용 해시**로
       남긴다 — 커밋 여부와 무관하게 «같은 사진·같은 CAD·같은 참조였나» 를 확정할 수 있다.
    ⚠️ 참조 세트의 출처 메타(`band`·`body_appearance`·`capture_args`)는 `build_sam3_refs`·
       `select_sam3_refs` 가 **기록하지 않는다**(RESULTS §35-2f 재현 ⑤). 있으면 싣고 없으면
       `null` 로 두되 **없다는 사실 자체를 남긴다** — 조용히 빠뜨리면 나중에 못 되짚는다.
    """
    root = Path(a.out)
    root.mkdir(parents=True, exist_ok=True)
    refs_name = a.refs or REFS_BY_PRESET[a.preset][0]
    refs_dir = VISION / a.obj / refs_name
    refs_meta = None
    for cand in ("meta_refs.json", "refs.json"):
        if (refs_dir / cand).exists():
            try:
                d = json.loads((refs_dir / cand).read_text(encoding="utf-8"))
                refs_meta = {k: d.get(k) for k in
                             ("band", "body_appearance", "capture_args", "source_run",
                              "n_candidates", "selected", "criterion")}
            except Exception:                                  # 메타가 깨져도 런을 죽이지 않는다
                refs_meta = {"error": f"{cand} 파싱 실패"}
            break
    n_refs_files = len(list(refs_dir.glob("*.png"))) + len(list(refs_dir.glob("*.jpg")))

    cam = {}
    if frames:
        cj = frames[0] / "cam.json"
        if cj.exists():
            try:
                cam = json.loads(cj.read_text(encoding="utf-8"))
            except Exception:
                cam = {}
    now = time.localtime()
    # 🔴 `--report-only` 로 다시 낼 때 **원래 런의 인자를 덮어쓰면 안 된다** — 산출물은 이전
    #    호출이 만든 것인데 메타는 지금 호출을 기록하게 되어 «어떤 설정으로 나온 결과인가» 가
    #    조용히 틀어진다. 원본을 보존하고 재생성 사실만 덧붙인다.
    prev = None
    if getattr(a, "report_only", False) and (root / "run_meta.json").exists():
        try:
            prev = json.loads((root / "run_meta.json").read_text(encoding="utf-8"))
        except Exception:
            prev = None
    if prev and prev.get("args"):
        prev["report_regenerated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", now)
        prev["report_args_note"] = ("이 파일의 `args` 는 **원래 런**의 것이다. "
                                    "`--report-only` 재생성은 산출물을 다시 만들지 않는다.")
        if a.note:
            prev.setdefault("notes_added", []).append(
                {"at": prev["report_regenerated_at"], "note": a.note})
        if a.true_distance_mm is not None:
            prev["true_distance_mm"] = a.true_distance_mm      # 줄자 값은 나중에 알 수 있다
        (root / "run_meta.json").write_text(
            json.dumps(prev, indent=2, ensure_ascii=False), encoding="utf-8")
        return prev
    meta = {
        "tool": "tools/run_group_a.py",
        # ★ 사람이 읽는 시각과 기계가 정렬하는 시각을 **둘 다** 남긴다
        "datetime_local": time.strftime("%Y-%m-%d %H:%M:%S", now),
        "datetime_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", now),
        "note": a.note,
        "in": str(a.in_dir), "out": str(a.out), "n_frames": len(frames),
        "args": {k: (str(val) if isinstance(val, Path) else val)
                 for k, val in sorted(vars(a).items()) if k not in ("list_presets",)},
        "obj": a.obj,
        "obj_hashes": {n: _sha8(VISION / a.obj / n)
                       for n in ("full.ply", "top_flange.ply", "meta.json")},
        "refs": {"name": refs_name, "dir": str(refs_dir), "n_files": n_refs_files,
                 "n_refs_used": a.n_refs, "mode": a.refs_mode,
                 # 🔴 없으면 «없다» 를 명시한다 — null 과 «안 봤다» 를 구분하기 위해서다
                 "provenance": refs_meta,
                 "provenance_note": None if refs_meta else
                 "참조 디렉토리에 출처 메타가 없다 (build_sam3_refs/select_sam3_refs 가 안 남긴다)"},
        "cam": {"width": cam.get("width"), "height": cam.get("height"),
                "fx": cam.get("fx"), "cx": cam.get("cx"), "cy": cam.get("cy"),
                "baseline_mm": cam.get("baseline_mm"),
                "sha8": _sha8(frames[0] / "cam.json") if frames else None},
        # ★ 사진 자체의 해시 — «같은 촬영을 다시 돌린 건가, 새로 찍은 건가» 가 이름으로는 안 갈린다
        "frame_hashes": {f.name: _sha8(f / "left.png") for f in frames[:8]},
        "true_distance_mm": a.true_distance_mm,
        "elapsed_sec": round(elapsed, 1) if elapsed is not None else None,
    }
    (root / "run_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def capture_diag(in_dir: Path, st: Path, seg: Path, ns2: Path) -> dict:
    """촬영 진단 — **이 사진으로 계속 가도 되는가**.

    🔴 열린 항목 #1(«FOUP 반투명 본체에서 수동 스테레오가 뚫리는가»)이 여기서 1차로 갈린다.
    flange 는 검정 불투명이라 잘 나오는 게 당연하고, **판정은 «주변 링»**(= 본체·배경)이다.
    """
    frames = sorted([p for p in in_dir.glob("frame_*") if p.is_dir()])
    rows = []
    for f in frames:
        r = {"frame": f.name}
        valid = cv2.imread(str(st / f.name / "valid.png"), cv2.IMREAD_GRAYSCALE)
        mask = cv2.imread(str(seg / f.name / "mask_flange.png"), cv2.IMREAD_GRAYSCALE)
        if valid is not None:
            v = valid > 127
            r["valid_all"] = round(float(v.mean()), 4)
            if mask is not None:
                m = mask > 127
                ring = cv2.dilate(m.astype(np.uint8), np.ones((31, 31), np.uint8), iterations=3) > 0
                ring &= ~m
                r["valid_flange"] = round(float(v[m].mean()), 4) if m.any() else None
                r["valid_ring"] = round(float(v[ring].mean()), 4) if ring.any() else None
        if mask is not None:
            area = int((mask > 127).sum())
            r["flange_px"] = area
            r["flange_dia_px"] = round(float(2 * np.sqrt(area / np.pi)), 1)
        # 분할이 «무엇을» 봤는지 — 마스크가 비었을 때 원인을 가리키는 유일한 단서다
        dj = seg / f.name / "det_flange.json"
        if dj.exists():
            d = json.loads(dj.read_text())
            r["seg_score"] = d.get("score")
            r["seg_found"] = d.get("found")
            r["seg_instances"] = d.get("n_instances")
        pj = ns2 / f.name / "pose_coarse.json"
        t = None
        if pj.exists():
            t = np.asarray(json.loads(pj.read_text(encoding="utf-8"))["t_mm"], float)
            r["z_mm"] = round(float(t[2]), 1)
            # 🔴 교훈 #83 — 벡터는 «크기» 가 아니라 «축» 으로 본다. 횡(x,y)을 따로 남긴다.
            r["tx_mm"], r["ty_mm"] = round(float(t[0]), 1), round(float(t[1]), 1)
            r["lat_mm"] = round(float(np.hypot(t[0], t[1])), 1)
        # ★ **stereo depth 가 직접 말하는 거리** — FP 추정 z 와 대조할 **다른 경로**의 관측이다.
        #   🔴 «독립» 이 아니다 — 둘 다 `Z = fx·B/disparity` 에서 나온다. `fx·B` 가 틀리면
        #      **정확히 같은 비율로** 같이 틀려 이 대조가 캘리브레이션 축에 무반응이다(교훈 #89).
        #      그 축은 `eval.scale_check`(실루엣, baseline 비의존)와 줄자가 본다.
        #   ⚠️ 경계 픽셀이 지표를 지배하므로(교훈 #5) 마스크를 **침식**해서 중앙부만 본다.
        #   ⚠️ depth.png 는 16-bit mm 이고 **0 = invalid** 다 — 빼고 세지 않으면 거리가 당겨진다.
        dp = cv2.imread(str(st / f.name / "depth.png"), cv2.IMREAD_UNCHANGED)
        if dp is not None and mask is not None and t is not None and (f / "cam.json").exists():
            cam = json.loads((f / "cam.json").read_text(encoding="utf-8"))
            K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], float)
            core = cv2.erode((mask > 127).astype(np.uint8), np.ones((9, 9), np.uint8),
                             iterations=2) > 0
            p = K @ t
            res = flange_plane_depth(dp, core, K, p[:2] / max(p[2], 1e-9))
            if res:
                zp, rms, npx = res
                r["depth_plane_mm"] = round(zp, 1)
                r["plane_rms_mm"] = round(rms, 3)
                r["plane_px"] = npx
                # 부호를 살린다: + 면 FP 가 depth 평면보다 «멀다» 고 본 것
                r["z_minus_depth_mm"] = round(float(t[2]) - zp, 1)
        rows.append(r)

    def col(k):
        return [r[k] for r in rows if r.get(k) is not None]

    out = {"n_frames": len(rows),
           "median": {k: round(_med(col(k)), 4) for k in
                      ("valid_all", "valid_flange", "valid_ring", "flange_dia_px",
                       "z_mm", "depth_plane_mm", "z_minus_depth_mm", "plane_rms_mm",
                       "lat_mm", "tx_mm", "ty_mm") if col(k)},
           "frames": rows}
    # ★ **눈금** — 이 런에서 1px 이 몇 mm 인가. 오버레이를 «정량적으로» 볼 수 있게 한다
    #   (교훈: «10mm 틀렸다» 를 그림에서 확인하려면 그게 몇 px 인지 알아야 한다).
    z = out["median"].get("z_mm")
    if z and frames:
        try:
            cam = json.loads((frames[0] / "cam.json").read_text(encoding="utf-8"))
            out["scale"] = {"mm_per_px": round(z / float(cam["fx"]), 4),
                            "px_per_10mm": round(10.0 * float(cam["fx"]) / z, 1),
                            "at_z_mm": z}
        except Exception:
            pass
    return out


def read_variant(root: Path, sid: str) -> dict:
    """정합 변형 하나의 GT-free 요약."""
    out = {"id": sid}
    mc = root / sid / "meta_contour.json"
    if mc.exists():
        m = json.loads(mc.read_text())
        fr = m["frames"]
        n = len(fr)
        # 🔴 **전단이 실패하면 여기가 빈다.** 진단 도구가 진단 대상과 같이 죽으면 안 된다 —
        #    빈 목록에 int(median([])) 를 하면 NaN 으로 터진다(실측 2026-08-13, 실물 첫 런).
        out["n"] = n
        if n == 0:
            out["failed"] = "정합할 프레임이 0 — 전단(분할·FP)에서 끊겼다"
            return out
        out |= {
            "gated": m["n_gated"],
            "gated_pct": round(100.0 * m["n_gated"] / n, 1),
            "n_corr": int(_med([r["n_corr"] for r in fr])),
            "rms_px": round(_med([r["rms_px"] for r in fr if r["rms_px"] is not None]), 3),
            "moved_deg_med": round(_med([r["moved_deg"] for r in fr]), 3),
            "moved_deg_max": round(max((r["moved_deg"] for r in fr), default=float("nan")), 3),
            "moved_mm_med": round(_med([r["moved_mm"] for r in fr]), 3),
            "sec": m["sec"],
        }
    lr = root / "lr" / f"lr_consistency_{sid}.json"
    if lr.exists():
        d = json.loads(lr.read_text())
        a = d["abs_median"]
        out |= {"lr_dxR": a["dx_R"], "lr_ddx": a["ddx_px"], "lr_dz": a["dz_mm"]}
        # ★ **부호를 살린다** (교훈 #83). `|Δdx|` 는 «얼마나» 만 말하고 «어느 쪽으로» 를 못 말한다.
        #   프레임마다 **부호가 같으면 계통 편향**이고, 그건 게이트가 못 막는 축이다(§29·§35-2i).
        #   ⚠️ `lr_consistency` 는 이미 부호 있는 중앙값을 계산해 두는데 지금까지 안 읽고 있었다.
        s = d.get("median", {})
        out |= {"lr_ddx_signed": s.get("ddx_px"), "lr_ddy_signed": s.get("ddy_px"),
                "lr_dz_signed": s.get("dz_mm")}
    return out


def _n_small(areas: list, frac: float = 0.5) -> int:
    """중앙값의 `frac` 배도 안 되는 마스크가 몇 장인가 — **부분 실패**의 지문.

    🔴 이 열이 없어서 실제로 놓쳤다: `n25black` 참조가 **검출 20/20 · 면적 중앙 35,982 · 이탈
       0.015** 로 완벽해 보였는데, GT 로 채점하니 **3프레임이 90~115° 뒤집혀** KPI 9/20 이었다.
       원인은 한 프레임의 마스크 면적이 **5,234px**(중앙의 0.15배)로 쪼그라든 것 — **중앙값이
       그걸 통째로 가렸다.** 교훈 #6·#13(«평균·중앙값이 고장을 숨긴다»)의 재발이다.
    """
    if not areas:
        return 0
    m = float(np.median(areas))
    return int(sum(1 for x in areas if x < frac * m))


def refs_sweep_rows(root: Path, base_preset: str) -> list[dict]:
    """`--mode refs` 스윕의 **분할 쪽 지표**를 모은다 (검출율 · 면적 · 중심 이탈 · 등가지름).

    🔴 **후퇴율로 이 스윕을 판정하면 안 된다**(교훈 #82) — 참조가 바뀌면 마스크가 바뀌고 FP
       초기값 자체가 달라진다. 후퇴율은 «같은 초기값 위에서 플래그만 바꾼» 비교에서만 유효하다.
       그래서 여기서는 **분할이 무엇을 집었나** 를 직접 본다: 검출율 · 면적 · **중심 이탈**.
    ⚠️ 이것도 IoU 가 아니다(GT 가 없다). «타깃을 집었는가» 의 **대리지표**일 뿐이고, 최종 판정은
       `segcmp` 육안과 좌우 일관성이다.
    """
    out = []
    for d in sorted(root.glob("seg_*")):
        ps = d.name[4:]
        if ps in ("full", "ism", "txt") or not ps.startswith("n"):
            continue
        # `seg_nr5` 는 **다른 프리셋이 아니라** 같은 참조를 몇 장 쓰는가의 변형이다 — 라벨을 구분한다.
        ps = f"{base_preset} · n-refs {ps[2:]}" if ps.startswith("nr") and ps[2:].isdigit() else ps
        dets = sorted(d.glob("frame_*/det_flange.json"))
        if not dets:
            continue
        found, areas, offs = 0, [], []
        for q in dets:
            j = _read_json(q)
            if not j.get("found"):
                continue
            found += 1
            areas.append(j.get("area_px", 0))
            b = j.get("bbox")
            m = cv2.imread(str(q.parent / "mask_flange.png"), cv2.IMREAD_GRAYSCALE)
            if m is not None and (m > 127).any():
                ys, xs = np.nonzero(m > 127)
                H, W = m.shape
                offs.append(float(np.hypot(xs.mean() / W - 0.5, ys.mean() / H - 0.5)))
            elif b:
                offs.append(0.0)
        out.append({"preset": ps, "n": len(dets), "found": found,
                    "area_med": float(np.median(areas)) if areas else None,
                    "area_min": float(np.min(areas)) if areas else None,
                    "n_small": _n_small(areas), "off_max": float(np.max(offs)) if offs else None,
                    "off_med": float(np.median(offs)) if offs else None})
    # 기본 preset(= `seg/`)도 같은 잣대로 넣는다 — 분모가 없으면 스윕을 읽을 수 없다
    dets = sorted((root / "seg").glob("frame_*/det_flange.json"))
    if dets:
        found, areas, offs = 0, [], []
        for q in dets:
            j = _read_json(q)
            if not j.get("found"):
                continue
            found += 1
            areas.append(j.get("area_px", 0))
            m = cv2.imread(str(q.parent / "mask_flange.png"), cv2.IMREAD_GRAYSCALE)
            if m is not None and (m > 127).any():
                ys, xs = np.nonzero(m > 127)
                H, W = m.shape
                offs.append(float(np.hypot(xs.mean() / W - 0.5, ys.mean() / H - 0.5)))
        out.insert(0, {"preset": f"{base_preset} (기본)", "n": len(dets), "found": found,
                       "area_med": float(np.median(areas)) if areas else None,
                       "area_min": float(np.min(areas)) if areas else None,
                       "n_small": _n_small(areas),
                       "off_max": float(np.max(offs)) if offs else None,
                       "off_med": float(np.median(offs)) if offs else None})
    return out


def _read_json(p: Path) -> dict:
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return {}


def cam_verdicts(in_dir: Path) -> list[str]:
    """**`cam.json` 무결성** — 실측 거리가 34% 어긋났던 사건의 세 번째 후보를 한 번에 닫는다.

    🔴🔴 **경고만 낸다. 어떤 경우에도 파이프라인을 멈추지 않는다** (사용자 방침).
       여기서 걸리는 것들은 «틀렸다» 가 아니라 «확인해 볼 것» 이고, 실제로 의도적인 구성일 수도 있다.

    왜 필요한가 — 캘리브레이션 오류는 **모든 내부 지표를 통과한다.** `fx·B` 가 `s` 배 틀리면
    거리도 `s` 배 틀리는데 투영 크기까지 같이 스케일돼서 오버레이 윤곽은 **완벽하게 붙는다**.
    좌우 일관성·게이트·평면 잔차 어느 것도 반응하지 않는다. 그래서 «입력이 애초에 맞는가» 를
    파일 수준에서 한 번 보는 것이 유일하게 싼 방어다.
    """
    out: list[str] = []
    fr = sorted([p for p in Path(in_dir).glob("frame_*") if (p / "cam.json").exists()])
    if not fr:
        return ["⚠️ `cam.json` 을 못 읽어 카메라 점검을 건너뛴다."]
    f = fr[0]
    try:
        c = json.loads((f / "cam.json").read_text())
    except Exception as e:
        return [f"⚠️ `{f.name}/cam.json` 파싱 실패 — {e}. 카메라 점검을 건너뛴다."]

    bad: list[str] = []
    W, H = c.get("width"), c.get("height")
    im = cv2.imread(str(f / "left.png"))
    if im is not None and W and H and (im.shape[1], im.shape[0]) != (W, H):
        bad.append(f"🔴 **해상도 불일치** — `left.png` 는 {im.shape[1]}×{im.shape[0]} 인데 "
                   f"`cam.json` 은 {W}×{H} 다. **`fx` 가 그 비율만큼 틀리고 거리가 통째로 스케일된다.** "
                   f"프로파일을 다른 해상도에서 복사했을 때 나는 증상이다 "
                   f"(`assets/cam/*.json` 은 그 모드 전용이다).")
    r = cv2.imread(str(f / "right.png"))
    if im is not None and r is not None and im.shape != r.shape:
        bad.append(f"🔴 **좌우 크기가 다르다** — {im.shape[1]}×{im.shape[0]} vs {r.shape[1]}×{r.shape[0]}. "
                   f"rectified 쌍이 아니다.")

    dis = c.get("distortion") or c.get("disto") or []
    if any(abs(float(x)) > 1e-9 for x in dis):
        bad.append(f"🔴 **왜곡 계수가 0 이 아니다** (`{[round(float(x), 4) for x in dis][:5]}…`). "
                   f"우리 파이프라인은 **rectified 만** 소비한다 — raw 를 넣으면 ZED X 2.2mm 는 "
                   f"`k1 0.54` 라 전 체인이 무효다(`docs/CAMERAS.md`). "
                   f"`tools/make_frame_from_zed.py` 로 다시 만들 것.")

    fx, fy, cx, cy = c.get("fx"), c.get("fy"), c.get("cx"), c.get("cy")
    B = c.get("baseline_mm")
    if fx and fy and abs(fx - fy) / fx > 0.01:
        bad.append(f"⚠️ `fx {fx:.1f}` 와 `fy {fy:.1f}` 가 1% 넘게 다르다 — rectified 라면 보통 같다.")
    if W and cx is not None and abs(cx - W / 2) > 0.06 * W:
        bad.append(f"⚠️ `cx {cx:.1f}` 가 화면 중심 {W / 2:.0f} 에서 {abs(cx - W / 2):.0f}px 벗어났다 "
                   f"— rectified 면 보통 중심 근처다. 크롭했거나 규약이 다를 수 있다.")
    if not B or B <= 0:
        bad.append("🔴 **`baseline_mm` 이 없거나 0 이다** — stereo depth 가 나올 수 없다.")

    if fx and B:
        hfov = 2 * np.degrees(np.arctan((W or 0) / 2 / fx)) if W else None
        out.append(f"📷 **카메라** — `{W}×{H}` · `fx {fx:.1f}` · `B {B:.1f}mm` · "
                   f"`fx·B {fx * B:,.0f}`"
                   + (f" · HFOV {hfov:.0f}°" if hfov else "")
                   + f" · 왜곡 {'0 (rectified)' if not any(abs(float(x)) > 1e-9 for x in dis) else '≠0'}")
    out += bad
    if bad:
        out.append("  ⚠️ **위 항목은 경고일 뿐이고 실행은 그대로 진행했다.** 다만 캘리브레이션 오류는 "
                   "**모든 GT-free 지표를 통과한다** — `fx·B` 가 틀리면 거리와 투영 크기가 같은 비율로 "
                   "틀려 **오버레이 윤곽이 완벽히 붙은 채로** 거리만 틀린다. 숫자를 쓰기 전에 확인할 것.")
    return out


def scale_verdicts(sc: dict, zf: float | None) -> list[str]:
    """**네 번째 다리 — 실루엣이 말하는 거리** (`eval.scale_check`).

    🔴 `FP z` 와 `stereo depth` 는 **둘 다 `fx·B/disparity`** 다. 서로 맞아도 «맞다» 가 아니라
       «같은 뿌리를 공유한다» 일 뿐이다. 실루엣 크기는 `B` 를 안 쓰므로 **baseline 축을 가른다.**
    ⚠️ 단 `fx` 오차는 이걸로도 못 잡는다(순수 스케일, 상쇄) — 그 축은 줄자뿐이다.
    """
    m = (sc or {}).get("median")
    if not m:
        if sc:
            out = [f"⚠️ 실루엣 거리 검사에 쓸 프레임이 없었다 — 제외 사유 {sc.get('skipped')}."]
            return out
        return []
    n, iqr, dpct = sc.get("n_used", 0), m["ratio_iqr"], m["delta_pct"]
    nout = m.get("n_ratio_outlier", 0)
    # ⚠️ «독립» 이라고 쓰지 않는다 — `baseline` 을 안 쓸 뿐 `fx` 는 공유한다(교훈 #89).
    head = (f"🔭 **실루엣이 말하는 거리 {m['z_silhouette_mm']:.0f}mm** vs pose z "
            f"{m['z_pose_mm']:.0f}mm (비 {m['ratio']:.3f} · IQR {iqr:.3f} · n={n}"
            + (f" · **비 이상 {nout}장**" if nout else "") + ") "
            f"— **`baseline` 을 안 쓰는** 네 번째 관측이다.")
    out = [head]
    if nout:
        out.append(f"  ⚠️ **비가 1 에서 15% 넘게 벗어난 프레임이 {nout}장** 있다 — 거의 항상 "
                   f"**마스크가 틀린 것**이다(오선택·부품 결손·그림자). 중앙값이 가려 주지만 "
                   f"`segcmp/seg_compare.png` 에서 그 프레임을 확인할 것.")
    if n < 6:
        out.append(f"  ⚠️ **표본 {n}장** — 중앙값·IQR 이 불안정하다. 지시적으로만 읽는다(≥10장 권장).")
    if iqr > 0.10:
        return out + [f"  ⚠️ **산포가 커서(IQR {iqr:.3f}) 이 값을 쓰면 안 된다** — 마스크 품질이 "
                      f"프레임마다 널뛰고 있다는 뜻이다. `segcmp` 로 마스크부터 확인할 것."]
    if abs(dpct) < 3.0:
        return out + [f"  ✅ **{dpct:+.1f}% 차 — baseline·시차 스케일은 정상**으로 보인다. "
                      f"🔴 다만 **`fx` 오차는 이 검사로 원리적으로 못 잡는다**(거리와 투영 크기가 "
                      f"같은 비율로 틀려 상쇄된다) — 그 축을 보는 건 **줄자**뿐이다."]
    return out + [
            f"  🔴 **{dpct:+.1f}% 어긋난다 — stereo 스케일(baseline·시차)을 의심하라.** "
            f"실루엣은 `baseline` 을 안 쓰는데 `FP z`·`stereo depth` 는 둘 다 쓴다. "
            f"셋 중 **실루엣만 다르면** 원인이 거기다. `cam.json` 의 `baseline_mm` 과 "
            f"카메라 실제 값을 대조할 것.",
            f"  ⚠️ FP 는 마스크도 함께 맞추므로 이미 일부 타협했을 수 있다 → **하한으로 읽는다**"
            f"(실제 스케일 오차가 이보다 클 수 있다)."]


def distance_verdicts(diag: dict, true_mm: float | None, scale: dict | None = None) -> list[str]:
    """**거리 대조** — FP 추정 z · stereo depth 중앙값 · **실루엣 거리** · (있으면) 줄자 실측.

    왜 이게 필요한가 — 실물에서 *"t 가 10mm 넘게 틀린다"* 가 나왔을 때, GT 가 없어도
    **두 추정이 서로 맞는지는 잴 수 있다.** 둘이 어긋나면 어느 한쪽이 틀린 것이고,
    둘이 맞는데도 물리적으로 틀렸다면 **공통 원인**(캘리브레이션·원점 규약)이다.

    🔴🔴 **«FP z ↔ stereo depth» 는 독립이 아니다** (교훈 #89) — 둘 다 `Z = fx·B/disparity` 다.
       `fx·B` 가 틀리면 **정확히 같은 비율로** 같이 틀려서 이 대조가 캘리브레이션 축에 무반응이다.
       그래서 다리를 둘 더 둔다: **실루엣 거리**(`baseline` 비의존) 와 **줄자**(`fx` 까지 보는 유일한 관측).

    🔴 `--true-distance-mm` 은 **선택**이다. 없으면 «FP ↔ depth ↔ 실루엣» 만 본다 —
       그것만으로도 «둘 중 하나가 틀렸다» 는 갈린다. 실측이 있어야 **어느 쪽이** 틀렸는지 나온다.
    ⚠️ 실측 기준점은 **flange 상면 중심**이다(pose 원점 규약). 몸체 바닥이나 받침대를 재면
       344mm 급으로 어긋나고, 그건 «편향» 이 아니라 «다른 것을 쟀다» 다.
    """
    out = []
    med = diag.get("median", {})
    zf, zd = med.get("z_mm"), med.get("depth_plane_mm")
    sc = diag.get("scale", {})
    if sc:
        out.append(f"📏 **눈금** — 이 런의 1px = **{sc['mm_per_px']:.3f}mm** "
                   f"(Z {sc['at_z_mm']:.0f}mm 기준). **10mm 어긋남 = {sc['px_per_10mm']:.0f}px** — "
                   f"오버레이에서 이만큼 밀렸는지 보면 «2D 문제 vs 3D(깊이) 문제» 가 갈린다.")
    if zf is None or zd is None:
        if zf is not None:
            out.append(f"⚠️ 거리 대조 불가 — FP z {zf:.0f}mm 는 있는데 flange 평면 적합에 실패했다"
                       f"(마스크가 작거나 depth 가 비었다). `diag_sheet.png` 의 depth 패널 확인.")
        return out + scale_verdicts(scale or {}, zf)

    d = med.get("z_minus_depth_mm", zf - zd)
    tol = 3.0                                   # 이 정도면 flange 융기·평면 적합 오차 범위다
    if abs(d) <= tol:
        out.append(f"✅ **거리 일관성** — FP 추정 z **{zf:.0f}mm** vs stereo depth 평면 "
                   f"**{zd:.0f}mm** (차 {d:+.1f}mm). 두 추정이 맞는다. "
                   f"🔴 **«독립» 이 아니다** — 둘 다 `fx·B/disparity` 라 `fx·B` 오차에는 "
                   f"**같이** 틀린다(교훈 #89). 그 축은 아래 «실루엣 거리» 와 줄자가 본다.")
    else:
        px = abs(d) / sc["mm_per_px"] if sc else None
        out.append(f"🔴 **FP 와 depth 가 어긋난다** — FP z **{zf:.0f}mm** vs stereo depth 평면 "
                   f"**{zd:.0f}mm** (차 **{d:+.1f}mm**"
                   + (f", 횡으로 새면 최대 {px:.0f}px" if px else "") + "). "
                   f"**둘 중 하나가 틀렸고 이 지표만으로는 못 가른다.** "
                   f"→ ① `diag_sheet.png` depth 패널에서 물체 depth 가 실제 거리인지 "
                   f"② `--true-distance-mm` 로 줄자 값을 주면 **어느 쪽이** 틀렸는지 나온다.")
        out.append("  ⚠️ Z 오차는 물체가 광축에서 벗어나 있으면 **횡방향으로 샌다** "
                   "(`δx = X_이탈/fx · δZ`). *«t 가 한 방향으로 밀린다»* 의 흔한 원인이고, "
                   "**테두리 정합은 Z 를 못 고친다**(§35-2k-2).")

    out += scale_verdicts(scale or {}, zf)

    rms = med.get("plane_rms_mm")
    if rms is not None:
        # 🔴 `valid.png` 100% 를 «뚫렸다» 로 읽으면 안 된다 — 범위 검사일 뿐이라 틀린 값도 유효로 센다.
        #    평면 잔차는 **값이 맞는가** 를 본다. sim(깨끗) 기준선 0.37mm.
        if rms > 3.0:
            out.append(f"🔴 **flange 평면 잔차 {rms:.2f}mm** — sim 기준선 0.37mm 의 8배 넘는다. "
                       f"스테레오가 표면을 제대로 못 뚫고 있다(**열린 항목 #1**). "
                       f"`valid.png` 100% 는 «뚫렸다» 를 뜻하지 않는다 — 범위 검사일 뿐이다.")
        elif rms > 1.0:
            out.append(f"⚠️ **flange 평면 잔차 {rms:.2f}mm** — sim 기준선(0.37mm)보다 크다. "
                       f"치명적이진 않지만 depth 를 초기값으로 신뢰하기 전에 depth 패널을 볼 것.")
        else:
            out.append(f"✅ **flange 평면 잔차 {rms:.2f}mm** — depth 가 평면을 제대로 잡았다.")

    if true_mm is None:
        out.append("  · `--true-distance-mm <줄자값>` 을 주면 여기에 **실측 대조**가 붙는다"
                   "(촬영 추가 0). 기준점은 **flange 상면 중심**이다.")
        return out

    ef, ed = zf - true_mm, zd - true_mm
    out.append(f"📐 **실측 대조** (줄자 {true_mm:.0f}mm) — FP {ef:+.1f}mm · depth {ed:+.1f}mm")
    bad = [n for n, e in (("FP", ef), ("depth", ed)) if abs(e) > 5.0]
    if not bad:
        out.append("  ✅ 둘 다 실측의 ±5mm 안이다. **거리 계통 편향은 아니다** — "
                   "t 오차가 크다면 원인은 횡방향이거나 원점 규약이다.")
    elif len(bad) == 2 and abs(ef - ed) <= tol:
        out.append(f"  🔴 **둘 다 같은 방향으로 틀렸다** ({ef:+.1f} / {ed:+.1f}mm) → **공통 원인**이다: "
                   f"baseline·fx 캘리브레이션, 또는 **실측 기준점이 pose 원점(flange 상면 중심)과 "
                   f"다르다**. ⚠️ 후자가 훨씬 흔하다 — 먼저 무엇을 쟀는지 확인할 것. "
                   f"`refine`·정합·게이트 어느 것도 이 축을 못 고친다.")
    else:
        out.append(f"  🔴 **{' 와 '.join(bad)} 가 틀렸다.** "
                   + ("depth 가 맞고 FP 가 틀렸다면 마스크·초기화 문제이고, "
                      if "FP" in bad and "depth" not in bad else "")
                   + ("depth 가 틀렸다면 스테레오가 표면을 못 뚫은 것이다 — **열린 항목 #1**, "
                      "`valid.png` 와 depth 패널을 볼 것."
                      if "depth" in bad else ""))
    return out


def verdicts(v: dict[str, dict], diag: dict, ism: bool = False) -> list[str]:
    """측정값 → **처방**. 규칙은 전부 문서에 근거가 있고 GT 를 쓰지 않는다."""
    out = []
    med = diag.get("median", {})

    # 🔴 전단이 끊겼으면 **그것만 말한다.** 뒤의 지표는 전부 무의미하고, 거리·CAD 판정을
    #    같이 내면 엉뚱한 원인을 쫓게 된다.
    fr = diag.get("frames", [])
    n_found = sum(1 for r in fr if r.get("flange_px"))
    if fr and n_found == 0:
        sc = [r["seg_score"] for r in fr if r.get("seg_score") is not None]
        s = f" (SAM3 score 중앙값 {np.median(sc):.3f})" if sc else ""
        out.append(f"🔴🔴 **분할이 {len(fr)}프레임 전부에서 검출 0 이다**{s} — flange 마스크가 비어 "
                   f"뒤 단계가 전부 건너뛰었다. **여기부터 고쳐야 하고 아래 지표는 의미가 없다.**")
        out.append("  ① 먼저 `seg/frame_0000/mask_flange.png` 와 원본 `left.png` 를 **눈으로** 볼 것 — "
                   "물체가 프레임에 제대로 있는지, 노출이 맞는지.")
        out.append("  ② **가장 유력한 원인: SAM3 exemplar 참조가 sim 렌더로 만들어졌다.** 참조는 "
                   "«배포 조건에서» 만들어야 하고(원거리 참조로 근접 질의 시 IoU 0.044 전례), "
                   "**실사진은 마지막 남은 도메인 갭 축**이다.")
        out.append("  ③ **대안은 ISM 이다** — CAD 렌더 템플릿을 쓰므로 사진 참조가 필요 없고, "
                   "randomization 하에서도 유지된 전례가 있다. **`--ism` 을 붙이면 I1 이 바로 그 비교다.**")
        return out

    d = med.get("flange_dia_px")
    if d:
        ratio = d / TARGET_FLANGE_PX
        if ratio < 0.80:
            out.append(f"🔴 거리 — flange 등가지름 {d:.0f}px 로 목표 {TARGET_FLANGE_PX:.0f}px 의 "
                       f"{ratio:.2f}배다. **더 가까이 가야 한다**(§34-9: 광각에서 정합 이득이 "
                       f"0.82× 로 죽는 조건). 참조 세트도 거리에 맞춰 바꿀 것.")
        elif ratio > 1.25:
            out.append(f"⚠️ 거리 — flange {d:.0f}px 로 목표보다 크다({ratio:.2f}배). 0.22m 아래로 "
                       f"내려가면 baseline 120mm 이 커져 FP 가 뒤집힌다(§34-9). 거리 확인.")
        else:
            out.append(f"✅ 거리 — flange 등가지름 {d:.0f}px ({ratio:.2f}× 목표). 최적 구간이다.")

    vr, vf = med.get("valid_ring"), med.get("valid_flange")
    if vr is not None:
        if vr < 0.5:
            out.append(f"🔴 **열린 항목 #1** — flange 주변(본체·배경) depth 유효율 {vr*100:.0f}% 다. "
                       f"수동 스테레오가 반투명 본체를 못 뚫고 있을 수 있다. `st/*/valid.png` 를 "
                       f"**눈으로 확인**할 것 — 카메라 선택을 뒤집을 수 있는 유일한 축이다.")
        else:
            out.append(f"✅ **열린 항목 #1** — 주변 depth 유효율 {vr*100:.0f}% (flange {vf*100:.0f}%). "
                       f"수동 스테레오가 뚫린다. 단 `valid.png` 눈 확인은 그대로 할 것.")

    g = {k: v[k].get("gated_pct") for k in ("A1", "A2a", "A2b") if k in v}
    if len(g) == 3 and all(x is not None for x in g.values()):
        hi = 3.0                                   # 배포본 대비 이 배수 넘게 후퇴하면 «폭증»
        excl, cont, ctr = g["A1"], g["A2a"], g["A2b"]
        if cont > max(excl * hi, excl + 25) and ctr <= max(excl * hi, excl + 25):
            out.append(f"🔴 **CAD 홀 지름이 실물과 다르다** (후퇴율 홀제외 {excl}% / 윤곽 {cont}% / "
                       f"중심 {ctr}%). §28-5 의 «윤곽만 폭증» 패턴 → **`--hole-center-mm 25`(A2b) 채택**.")
        elif cont > max(excl * hi, excl + 25) and ctr > max(excl * hi, excl + 25):
            nc, ne = v["A2a"].get("n_corr"), v["A1"].get("n_corr")
            frac = f" 대응점이 {ne} → {nc} ({100*(1-ne/max(nc,1)):.0f}% 가 홀에서 나온다)." \
                if nc and ne else ""
            out.append(f"🔴 **홀은 못 쓴다** (후퇴율 홀제외 {excl}% / 윤곽 {cont}% / 중심 {ctr}%).{frac} "
                       f"→ **A1 배포본 유지**. ⚠️ 원인이 둘이고 «중심 모드도 같이 무너진 것» 만으로는 "
                       f"안 갈린다: ① 최상면 개구가 CAD 와 크게 다르다(§28-5) ② 홀 주변 **융기**가 "
                       f"깔때기를 만들어 신호 없는 샘플이 대량 생긴다(§31 — CAD 가 정확해도 난다). "
                       f"**처방은 둘 다 «홀 제외» 로 같다.** 개구를 캘리퍼로 재는 값어치는 "
                       f"①일 때만 있고 R 0.032°/t 0.068mm 다 — **융기가 있으면 재도 안 돌아온다**.")
        else:
            out.append(f"✅ **CAD 홀이 실물과 맞는다** (후퇴율 {excl}/{cont}/{ctr}%). "
                       f"§27-6 에 따르면 이 경우 **규격부(A2a) 가 가장 정확**하다 — "
                       f"회전은 테두리가, 평행이동은 홀이 준다.")

    if "A1" in v and "A4" in v and v["A1"].get("gated_pct") is not None \
            and v["A4"].get("gated_pct") is not None:
        c, r = v["A1"]["gated_pct"], v["A4"]["gated_pct"]
        pick = "coarse (=`--no-stage2` 유지)" if c <= r else "refined (**`--no-stage2` 를 뺀다**)"
        out.append(f"{'✅' if c <= r else '🔴'} **§32 판정 절차** — 초기값 후퇴율 coarse {c}% vs "
                   f"refined {r}% → **{pick}**. "
                   + ("깨끗·정확 조건의 기본값 그대로다."
                      if c <= r else "refined 가 이긴다는 것은 **CAD 불일치 신호**다(§32 표)."))

    # ★★★★ **정합 on/off 를 GT 없이 정하는 값** (§35-2m-6). 네 조건(28/50cm × black·orange·clear)에서
    #   6.2 / 17.5 / 1.7 / 1.8mm 로 깨끗하게 갈렸다. «거리» 가 아니라 «정합기가 신호를 찾았나» 를 잰다.
    #   🔴 `--gate-deg` 는 회전만 보므로 **t 로만 새는 계통 편향을 못 잡는다** — 그래서 이 값이 따로 필요하다.
    if "Cz" in v and v["Cz"].get("moved_mm_med") is not None:
        out.append(f"⚠️ **`Cz`(--fix-z) 의 이동량 {v['Cz']['moved_mm_med']:.1f}mm 을 다른 팔과 "
                   f"나란히 읽지 말 것** — Z 가 묶여 있어 구조적으로 작게 나온다. "
                   f"«정합이 잘 맞았다» 가 아니라 **«움직일 수 없었다»** 다. "
                   f"`--fix-z` 의 우열은 **좌우 |Δdx|** 와 오버레이로 본다.")
    for sid in ("A1", "I1", "T1"):
        mm = v.get(sid, {}).get("moved_mm_med")
        if mm is None:
            continue
        if mm >= 10:
            out.append(f"🔴 **{sid} 정합을 쓰지 말 것 — 이동량 t 중앙 {mm:.1f}mm (≥10mm)**. "
                       f"정합기가 외곽 경계를 못 찾고 엉뚱한 에지로 수렴한 것이다. "
                       f"**게이트가 못 막는다**(회전만 보는데 이 실패는 t 로만 샌다). "
                       f"흔한 원인은 **몸체와 flange 가 같은 검정**이라 외곽에 밝기 경계가 없는 것(§35-2i) "
                       f"— 오버레이에서 초록 윤곽이 «융기 능선» 에 붙었는지 확인할 것. "
                       f"→ 이 런의 결론은 **{sid[0]}3**(정합 전)으로 낸다.")
        elif mm >= 5:
            out.append(f"⚠️ **{sid} 이동량 t 중앙 {mm:.1f}mm** — 경계 구간(5~10mm)이다. "
                       f"정합이 중립일 가능성이 높다. **{sid} 와 {sid[0]}3 의 좌우 일관성을 비교**하고 "
                       f"오버레이를 눈으로 볼 것.")
        else:
            out.append(f"✅ **{sid} 이동량 t 중앙 {mm:.1f}mm** — 정합기가 외곽 신호를 찾았다. "
                       f"이 대역에서는 정합이 R 을 1.5~2.0배 개선한다(§35-2m-6).")

    a3, a1 = v.get("A3", {}).get("lr_ddx"), v.get("A1", {}).get("lr_ddx")
    if a3 is not None and a1 is not None:
        if diag.get("n_frames", 0) < 10:
            out.append(f"⚠️ **A3 판정 유보** — 좌우 |Δdx| {a3:.2f} → {a1:.2f}px 이지만 "
                       f"프레임 {diag.get('n_frames')}장으로는 프레임별 산포(±1~2mm 급)에 묻힌다. "
                       f"**≥10장**에서 다시 볼 것.")
        elif a1 < a3 * 0.9:
            out.append(f"✅ **A3 정합 이득 있음** — 좌우 |Δdx| {a3:.2f}px → {a1:.2f}px "
                       f"({a3/max(a1,1e-6):.2f}배 개선). 정합을 켠다.")
        elif a1 > a3 * 1.1:
            out.append(f"🔴 **A3 정합이 해롭다** — 좌우 |Δdx| {a3:.2f}px → {a1:.2f}px 로 나빠졌다. "
                       f"§29 의 «외곽 융기 유무가 CAD 와 다름» 이 정확히 이 증상이고 "
                       f"**게이트가 못 막는 축**이다(계통 편향). 융기를 육안 확인할 것.")
        else:
            out.append(f"⚠️ **A3 판정 보류** — 좌우 |Δdx| {a3:.2f} → {a1:.2f}px 로 구분이 안 된다. "
                       f"프레임 수를 늘리거나(≥20) 융기 유무를 직접 확인할 것.")

    # ── ISM 경로 판정 — «어느 쪽이 정확한가» 가 아니라 «도메인 갭이 어디에 오는가» ──────────
    # ⚠️ `read_variant` 는 **부분 dict** 를 돌려준다(스테이지가 일부만 돌았을 때).
    #    `is not None` 으로는 부족하고 **쓰려는 키의 존재**를 봐야 한다 — lr 은 optional 이 아니지만
    #    실물에서 한 스테이지가 죽으면 리포트가 통째로 KeyError 로 날아간다.
    i1, i3 = v.get("I1") or {}, v.get("I3") or {}
    if i1.get("lr_ddx") is not None and a1 is not None:
        gb, ga = i1.get("gated_pct"), v.get("A1", {}).get("gated_pct")
        out.append(f"── **ISM 경로 (SAM-6D ISM · CAD 템플릿 단독)** — 후퇴율 A1 {ga}% vs I1 {gb}%, "
                   f"좌우 |Δdx| A1 {a1:.2f}px vs I1 {i1['lr_ddx']:.2f}px")
        # 🔴 두 경로는 **분할도 pose 메쉬도 다르다**(SAM3 flange vs ISM full) —
        #    차이를 «분할 백엔드» 하나로 돌리면 안 된다. 그래서 판정을 **방향으로만** 낸다.
        if i1["lr_ddx"] < a1 * 0.8:
            # 🔴 **원인을 단정하지 않는다.** 두 경로는 분할·pose 메쉬가 «둘 다» 다르므로
            #    I1 이 낫다는 것만으로 도메인 갭을 결론지을 수 없다 — sim 데이터(갭 0)에서도
            #    이 부등식이 성립하는 것을 확인했다(§35-2g 스모크). 후보를 나열하고 **가르는
            #    방법**까지 준다. 그러지 않으면 «그럴듯한 오진» 을 리포트가 만들어 낸다.
            out.append("  ⚠️ **ISM 경로가 낫다** — 원인 후보가 셋이고 이 지표만으로는 못 가른다: "
                       "①SAM3 참조의 도메인 갭(참조가 sim 렌더다) "
                       "②pose 메쉬 차이(I1 은 `--primary full`, A1 은 `flange`) "
                       "③거리·조건이 A1 에 불리(등가지름·후퇴율을 위 표에서 확인). "
                       "→ 가르는 법: **`seg/mask_flange.png` 를 눈으로 본다**(갭이면 마스크부터 어긋난다) · "
                       "실사진 참조를 만들어 A1 을 다시 돌린다(박스만 그리면 된다) · "
                       "등가지름이 목표에서 멀면 거리부터 맞춘다.")
        elif i1["lr_ddx"] > a1 * 1.25:
            out.append("  ✅ **SAM3 경로가 낫다** — sim 참조가 실물에 전이됐다는 «방향» 이다. "
                       "배포본 [A] 를 그대로 간다. ⚠️ 이것도 pose 메쉬 차이가 섞인 값이므로 "
                       "«참조에 갭이 없다» 의 증명은 아니다.")
        else:
            out.append("  ⚠️ **구분이 안 된다** — 두 경로가 같은 수준이면 «갭이 없다» 가 아니라 "
                       "«이 표본으로는 못 가른다» 다. 프레임을 늘리거나 두 오버레이를 겹쳐 볼 것.")
    if i3.get("lr_ddx") and i1.get("lr_ddx"):
        out.append(f"  · ISM 경로 정합 이득 {i3['lr_ddx']:.2f} → {i1['lr_ddx']:.2f}px "
                   f"({i3['lr_ddx']/max(i1['lr_ddx'],1e-6):.2f}배) — A3 이득과 나란히 볼 것.")
    if ism and not i1.get("lr_ddx"):
        out.append("🔴 **ISM 경로 결과가 비어 있다** — `seg_ism`/`fp_ism` 이 실패했을 수 있다. "
                   "ISM 은 검출 0 이어도 조용히 끝나므로 `seg_ism/frame_0000/mask_full.png` 를 "
                   "**눈으로** 확인할 것.")

    if diag.get("n_frames", 0) < 20:
        out.append(f"⚠️ **표본 {diag.get('n_frames')}장** — 꼬리로 우열을 가리기엔 부족하다"
                   f"(교훈 #58: n=40 무결점이 n=120 에서 110/120 이었다). "
                   f"연속 촬영은 손으로도 싸다 — **20~40장** 찍어 두면 반복도까지 같이 나온다.")
    return out


def baseline_rows(diag: dict, v: dict) -> list[tuple]:
    """**(a) sim 기준선 대조** — «이 값이 상이한가» 를 한 표로.

    지금까지 임계값이 판정 «문장 안» 에 박혀 있어 한눈에 안 보였다. 여기서는 **대역과 실측을
    나란히** 놓고 벗어남만 표시한다.
    🔴 **판정을 대신하지 않는다** — sim 대역 밖이 곧 고장이 아니다(도메인 갭일 수 있다).
    """
    out = []
    med = diag.get("median", {})
    for key, lab, lo, hi, unit, note in SIM_BASELINE_CAPTURE:
        out.append((lab, lo, hi, unit, med.get(key), note))
    a1 = v.get("A1", {})
    for key, lab, lo, hi, unit, note in SIM_BASELINE_A1:
        out.append((f"A1 {lab}", lo, hi, unit, a1.get(key), note))
    return out


def frame_outliers(root: Path, diag: dict, z_thr: float = 3.5, min_n: int = 8) -> dict:
    """**(b) 프레임 이상치** — 강건 z-score(중앙값·MAD)로 *"이 프레임만 다르다"* 를 찾는다.

    ★ `worst_frames` 와 **다른 도구다**:
      · `worst_frames` 는 **순위** — 정상인 런에서도 «상대적으로 가장 나쁜» 장이 나온다.
      · 여기는 **분포** — 아무것도 안 나오는 게 정상이고, **나오면 그 자체가 신호**다.
    ★ **기준선이 필요 없다** — 런 자기 자신이 기준이라 **도메인 갭에 면역**이다.
      실물 첫 런부터, sim 값과 아무리 달라도 그대로 작동한다.
    ⚠️ 표본이 적으면 강건 통계가 무의미하다 → `min_n` 미만이면 아예 돌리지 않는다.
    ⚠️ 이상치는 «pose 가 틀렸다» 가 아니다 — §35-2c 에서 분할이 깨졌는데 pose 는 정상인 실례가 있었다.
    """
    rows = {r["frame"]: dict(r) for r in diag.get("frames", [])}
    mc = root / "A1" / "meta_contour.json"
    if mc.exists():
        for r in json.loads(mc.read_text(encoding="utf-8"))["frames"]:
            rows.setdefault(r["frame"], {}).update(
                {"A1 대응점": r.get("n_corr"), "A1 정합잔차": r.get("rms_px"),
                 "A1 이동량°": r.get("moved_deg")})
    lr = root / "lr" / "lr_consistency_A1.json"
    if lr.exists():
        for r in json.loads(lr.read_text(encoding="utf-8")).get("frames", []):
            rows.setdefault(r["frame"], {})["A1 좌우Δdx"] = r.get("ddx_px")
    if len(rows) < min_n:
        return {"_note": f"프레임 {len(rows)}장 — 강건 통계에 최소 {min_n}장이 필요하다"}

    LABEL = {"flange_dia_px": "flange 등가지름", "valid_all": "depth 유효율",
             "valid_ring": "주변 유효율", "plane_rms_mm": "평면 잔차",
             "z_mm": "FP 거리 z", "z_minus_depth_mm": "FP−depth", "lat_mm": "광축 이탈",
             "seg_score": "분할 점수"}
    keys = [k for k in (list(LABEL) + ["A1 대응점", "A1 정합잔차", "A1 이동량°", "A1 좌우Δdx"])
            if sum(1 for r in rows.values() if isinstance(r.get(k), (int, float))) >= min_n]
    hits: dict[str, list] = {}
    bimodal = []
    for k in keys:
        vals = {f: float(r[k]) for f, r in rows.items() if isinstance(r.get(k), (int, float))}
        a = np.array(list(vals.values()))
        m = float(np.median(a))
        # ⚠️ **MAD 만 쓰면 안 된다** — 값의 절반 이상이 같으면(예: sim 의 `valid_all` 이 1.0)
        #    MAD 가 0 이 되어 z 가 발산한다(실측 z=209). IQR 과 **상대 바닥**을 함께 깐다.
        mad = 1.4826 * float(np.median(np.abs(a - m)))
        iqr = float(np.percentile(a, 75) - np.percentile(a, 25)) / 1.349
        s = max(mad, iqr, 0.02 * abs(m))                 # 중앙값의 2% 미만 편차는 안 본다
        if s < 1e-9:                                     # 전부 같은 값 → 판정 불가
            continue
        cand = [(f, abs(x - m) / s, x) for f, x in vals.items() if abs(x - m) / s >= z_thr]
        # 🔴 **한 지표에서 25% 넘게 걸리면 그건 «이상치» 가 아니라 «분포가 갈라진 것» 이다.**
        #    (실측: 좌우 Δdx 가 20장 중 6장에서 −1.5~−4.6px 로 뭉쳐 있었다. 그건 소수의 사고가
        #     아니라 «30% 가 다르게 동작한다» 는 뜻이고, 이상치로 보고하면 오독을 만든다.)
        if len(cand) > max(2, int(0.25 * len(vals))):
            bimodal.append((LABEL.get(k, k), len(cand), len(vals), m,
                            float(np.min(a)), float(np.max(a))))
            continue
        for f, z, x in cand:
            hits.setdefault(f, []).append((LABEL.get(k, k), z, x, m))
    out = {f: sorted(v, key=lambda t: -t[1]) for f, v in
           sorted(hits.items(), key=lambda kv: -max(t[1] for t in kv[1]))}
    if bimodal:
        out["_bimodal"] = bimodal
    return out


def worst_frames(root: Path, diag: dict, v: dict, k: int = 2, cap: int = 6) -> dict:
    """**«여기부터 보라»** — GT-free 지표별 최악 프레임을 골라 이유와 함께 돌려준다.

    왜 필요한가 — `diag_trends.png` 가 이상 프레임을 «보여» 주지만, 그 다음에 사람이 어느 장을
    열어야 하는지는 손으로 찾아야 했다. 실물은 20~40장이라 훑을 수는 있지만 **매 시도마다** 훑는
    것은 비싸다. 지표마다 상위 `k` 장을 뽑아 합집합을 만든다.

    ⚠️ **순위 기반이지 임계값 기반이 아니다** — 정상인 런에서도 «상대적으로 가장 나쁜» 장이
    나온다. *"여기 이상이 있다"* 가 아니라 *"본다면 여기부터"* 다. 정상 판정은 리포트 본문이 한다.
    """
    rows = {r["frame"]: dict(r) for r in diag.get("frames", [])}
    # 정합 지표를 배포본(A1) 기준으로 붙인다 — 변형마다 다르면 비교가 안 된다
    mc = root / "A1" / "meta_contour.json"
    if mc.exists():
        for r in json.loads(mc.read_text(encoding="utf-8"))["frames"]:
            rows.setdefault(r["frame"], {}).update(
                {"c_rms": r.get("rms_px"), "c_ncorr": r.get("n_corr"),
                 "c_moved": r.get("moved_deg"), "c_gated": r.get("gated")})
    lr = root / "lr" / "lr_consistency_A1.json"
    if lr.exists():
        for r in json.loads(lr.read_text(encoding="utf-8")).get("frames", []):
            rows.setdefault(r["frame"], {})["lr_ddx"] = r.get("ddx_px")

    dia = [r.get("flange_dia_px") for r in rows.values() if r.get("flange_dia_px")]
    dia_med = float(np.median(dia)) if dia else None

    def rank(key, fn, why, reverse=True):
        got = [(fn(r), f) for f, r in rows.items() if fn(r) is not None]
        if not got:
            return []
        got.sort(reverse=reverse)
        return [(f, why, val) for val, f in got[:k]]

    picks = []
    picks += rank("gated", lambda r: 1.0 if r.get("c_gated") else None,
                  "게이트 후퇴 — 정합이 폭주했다")
    picks += rank("moved", lambda r: r.get("c_moved"), "정합 이동량 최대")
    picks += rank("rms", lambda r: r.get("c_rms"), "정합 잔차 rms 최대")
    picks += rank("ncorr", lambda r: r.get("c_ncorr"), "대응점 최소 — 신호가 없었다", reverse=False)
    picks += rank("lr", lambda r: abs(r["lr_ddx"]) if r.get("lr_ddx") is not None else None,
                  "좌우 투영 불일치 최대")
    picks += rank("plane", lambda r: r.get("plane_rms_mm"), "flange 평면 잔차 최대 — depth 의심")
    picks += rank("zdiff", lambda r: abs(r["z_minus_depth_mm"])
                  if r.get("z_minus_depth_mm") is not None else None, "FP−depth 어긋남 최대")
    if dia_med:
        picks += rank("dia", lambda r: abs(r["flange_dia_px"] - dia_med)
                      if r.get("flange_dia_px") else None, "마스크 크기가 중앙값에서 최대 이탈")

    out: dict[str, list] = {}
    for f, why, val in picks:
        out.setdefault(f, []).append((why, val))
    # 여러 지표에 걸린 프레임을 먼저 — 그게 진짜 볼 값어치가 있는 장이다
    ordered = sorted(out.items(), key=lambda kv: -len(kv[1]))[:cap]
    return {f: reasons for f, reasons in ordered}


def make_worst_dir(a, root: Path, picks: dict) -> Path | None:
    """최악 프레임만 모아 **`contour_debug.png` 를 다시 낸다**.

    `--debug` 를 전 프레임에 켜면 무겁고, 안 켜면 *"Sobel 이 물체 경계를 잡았나 · 융기 능선을
    잡았나 · 그림자를 잡았나"* 를 볼 그림이 아예 없다. 🔴 **그 그림 없이는 §35-2i 의
    «검정 몸체 계통 편향» 을 실물에서 대리 관측할 방법이 없다.**

    구현: 고른 프레임만 **심링크**한 임시 캡처 디렉토리를 만들고 거기에 `refine_contour --debug`
    를 돌린다. → `refine_contour` 를 **한 줄도 안 고친다**(배포 경로 무영향).
    """
    if not picks:
        return None
    wd = root / "worst"
    fdir = wd / "_frames"
    fdir.mkdir(parents=True, exist_ok=True)
    in_dir = Path(a.in_dir)
    for f in picks:
        link = fdir / f
        if not link.exists():
            try:
                link.symlink_to(in_dir / f, target_is_directory=True)
            except OSError:
                return None
    cmd = [PY["pose"], "-m", "spatial_vision.stages.refine_contour",
           "--in", fdir, "--pose-dir", root / "fp_ns2", "--pose-name", "pose_coarse.json",
           "--obj", a.obj, "--mesh", "top_flange.ply", "--outer-only",
           "--gate-deg", a.gate_deg, "--debug", "--out", wd / "A1_debug"]
    if a.fix_z:
        cmd.append("--fix-z")
    rc = subprocess.call([str(c) for c in cmd], cwd=VISION,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return wd if rc == 0 else None


def next_steps(v: dict, diag: dict, a) -> list[str]:
    """**다음에 무엇을 시도할지** — 비용(촬영 횟수) 순으로 정렬해서 낸다.

    `verdicts()` 는 *진단*을 준다. 여기서는 **행동**을 준다. 🔴 이 환경은 **로봇이 없고 손 촬영**이라
    «촬영 0» 과 «촬영 2» 의 차이가 크다 — 그래서 정렬 기준이 «중요도» 가 아니라 **«비용»** 이다.

    ⚠️ 여기 규칙은 **지금까지 sim 에서 본 실패 유형**만 안다. 실물에서 새로운 증상이 나오면
       그건 이 목록에 없다 — **목록이 비었다고 «문제 없음» 이 아니다.**
    """
    med, out = diag.get("median", {}), []
    a1, a3 = v.get("A1", {}), v.get("A3", {})

    if not a.true_distance_mm and med.get("z_mm"):
        out.append(("촬영 0 · 인자만", "`--true-distance-mm <줄자값>` 을 주고 `--report-only` 로 재리포트 — "
                    "**FP 와 depth 중 어느 쪽이 틀렸는지**가 갈린다. 기준점은 flange 상면 중심."))
    g = {k: v[k].get("gated_pct") for k in ("A1", "A2a", "A2b") if k in v}
    if len(g) == 3 and all(x is not None for x in g.values()) and g["A1"] > 40:
        out.append(("촬영 0 · 플래그만", f"A1 후퇴율이 {g['A1']}% 로 높다 — `--fix-z` 를 켜고/끄고 "
                    "각각 돌려 비교한다(§35-2j: Z 를 묶으면 횡 축퇴가 끊긴다)."))
    d = med.get("z_minus_depth_mm")
    if d is not None and abs(d) > 3.0:
        out.append(("촬영 1", "물체를 **화면 반대쪽**에 두고 한 장 더 — 횡 편향의 **부호가 뒤집히면 "
                    "Z 오차**이고 그대로면 진짜 횡방향 문제(캘리브레이션·원점 규약)다."))
    rms = med.get("plane_rms_mm")
    if rms is not None and rms > 1.0:
        out.append(("촬영 0 · 육안", f"flange 평면 잔차 {rms:.2f}mm — `st/frame_*/valid.png` 와 진단 시트 "
                    "depth 패널을 본다. **열린 항목 #1**(반투명 본체 관통) 판정."))
    if a1.get("lr_ddx") is not None and a3.get("lr_ddx") is not None \
            and a1["lr_ddx"] > a3["lr_ddx"] * 1.1:
        out.append(("촬영 0 · 육안", "정합이 좌우 일관성을 **악화**시켰다 — 실물 flange 최외곽에 "
                    "**융기가 있는지 눈으로 확인**한다(§29 최악 축, 게이트가 못 막는다). "
                    "융기가 CAD 와 다르면 **정합을 끄는 편이 안전**하다."))
    sg = a1.get("lr_ddx_signed")
    if sg is not None and a1.get("lr_ddx") and abs(sg) > 0.7 * a1["lr_ddx"]:
        out.append(("촬영 0 · 확인", f"좌우 Δdx 부호가 한쪽으로 쏠렸다({sg:+.2f}px) — **계통 편향**이다. "
                    "`cam.json` 의 `disto` 가 전부 0 인지(= rectified 인지), 해상도가 프로파일과 "
                    "같은지부터 확인한다. **게이트·refine 어느 것도 이 축을 못 고친다.**"))
    if diag.get("n_frames", 0) < 20:
        out.append(("촬영 1 (연속)", f"프레임 {diag.get('n_frames')}장 → **20~40장 연속 촬영**. "
                    "꼬리가 보이고(교훈 #58) **반복도**(sim 에 대응물 없는 지표)까지 공짜로 나온다."))
    out.append(("촬영 2", "**§7.5c 상대 GT** — 물체를 자로 잰 만큼(≥100mm) 밀고 두 번 찍는다. "
                "**계통 편향(scale·offset)을 real 에서 잡는 유일한 수단**이고 hand-eye 가 필요 없다. "
                "⚠️ 회전과 평행이동을 섞지 않는다."))
    return [f"**[{cost}]** {what}" for cost, what in out]


# 리포트에서 이 제목 **바로 뒤**에 그림 3종 줄이 꽂힌다 — 문자열이 곧 삽입 지점이라 같이 둔다.
HDR_ANALYZE = "## 직접 분석할 것\n"


def wiring_audit(root: Path) -> list[str]:
    """`tools/audit_run.py` 를 돌려 **«어느 팔의 숫자가 다른 팔 것은 아닌가»** 를 기계로 확인한다.

    🔴 **리포트의 첫 관문이다.** 배선이 어긋나면 아래 표·그림의 숫자는 «틀린» 게 아니라
       **«다른 뜻»** 이 되고, GT 가 없으면 눈으로 알아챌 수 없다. 실제로 이 검사가
       `distance.png` 의 경로 섞임을 잡았다(§35-2p-1).
    ⚠️ **배선만 본다 — 정확도 검사가 아니다.**
    """
    r = subprocess.run([PY["pose"], str(Path(__file__).with_name("audit_run.py")),
                        "--root", str(root)], capture_output=True, text=True)
    # 항목 줄만 남긴다 — 감사기의 마지막 총평은 아래 `head` 와 겹친다.
    body = [l for l in (r.stdout or "").splitlines()
            if l.strip().startswith(("✅ ①", "✅ ②", "✅ ③", "✅ ④", "✅ ⑤", "✅ ⑥", "✅ ⑦",
                                     "🔴 ①", "🔴 ②", "🔴 ③", "🔴 ④", "🔴 ⑤", "🔴 ⑥", "🔴 ⑦"))]
    if not body:
        return ["", "## 배선 감사\n",
                f"⚠️ 돌리지 못했다 — 직접: `envs/pose/bin/python tools/audit_run.py --root {root}`\n"]
    head = ("🔴🔴 **배선 감사 실패 — 아래 숫자를 해석하기 전에 이걸 먼저 본다.**"
            if r.returncode else
            "✅ **배선 감사 통과** — 각 팔의 숫자가 **그 팔의 것**이다.")
    return ["", "## 배선 감사 (`tools/audit_run.py`)\n", head + "\n"] \
        + [f"- {l.strip()}" for l in body] \
        + ["", "⚠️ 이건 **«배선»** 검사지 **«정확도»** 검사가 아니다 — 값이 맞는지는 GT 가 있어야 하고 "
           "실환경에는 GT 가 없다(그건 오버레이·좌우 일관성의 몫이다).\n"]


def result_charts(root: Path, a) -> list[str]:
    """판단용 그림 3종을 그리고 **리포트에 붙일 줄**을 돌려준다 (`viz.result_charts`).

    ⚠️ **실패해도 본 파이프라인을 안 죽인다**(교훈 #79) — 진단 그림이 없다고 결과가 없어지지는
       않는다. 대신 «왜 없는지» 를 리포트에 남긴다. 조용히 빠지는 것이 제일 나쁘다.
    🔴 `report.json` 을 읽으므로 **그 파일을 쓴 뒤에** 부른다.
    """
    L: list[str] = []
    r = subprocess.run([PY["pose"], "-m", "spatial_vision.viz.result_charts",
                        "--root", str(root)] + (["--fix-z"] if a.fix_z else []),
                       capture_output=True, text=True)
    made = [n for n in ("distance.png", "ranking.png", "heatmap.png")
            if (root / "stats" / n).exists()]
    if r.returncode != 0 and not made:
        L.append(f"⚠️ 그리지 못했다 — `{(r.stderr or r.stdout).strip().splitlines()[-1:] or ['?']}`. "
                 f"직접 돌려 본다: `envs/pose/bin/python -m spatial_vision.viz.result_charts "
                 f"--root {root}`\n")
        return L
    L.append(f"- 🔴🔴 **거리 4다리 — `{root}/stats/distance.png`**")
    L.append("  - `FP z` · `stereo 평면적합` · **실루엣** · **줄자** 를 프레임축에 겹치고, 아래 칸에 "
             "**FP 대비 차**를 낸다. 🔴 **앞의 둘은 «독립 검증» 이 아니다** — 둘 다 "
             "`Z = fx·B/disparity` 라 `fx·B` 가 틀리면 **같은 비율로 같이** 틀린다(교훈 #89).")
    L.append("  - **읽는 법**: 실루엣만 갈라지면 → `baseline` · 셋이 붙었는데 줄자만 다르면 → "
             "**`fx`**(내부 관측 전부를 통과하는 순수 스케일이라 **줄자 외엔 못 잡는다**) · "
             "셋 다 붙고 줄자와도 맞으면 ✅.")
    L.append("  - ⚠️ 프레임마다 거리가 달랐으면 줄자 선은 **오차가 아니라 자세 변화**다 — "
             "그때는 그림 안의 **중앙값 상자**만 비교한다.")
    L.append(f"- 🔴 **팔 서열 — `{root}/stats/ranking.png`**")
    L.append("  - 좌우 **|Δdx| 중앙값으로 정렬**한 가로 막대(위가 1등, 수염 = p90). "
             "★ 이 지표만 서열을 맞힌다(**실제 KPI 와 r = −0.94**, §35-2o-6b).")
    L.append("  - 🔴 **막대에 붙은 표시를 먼저 본다** — `*all-gated`(그 값은 **자기 결과가 아니라 "
             "초기값**) · `Z-fixed`(이동량이 구조적으로 작다) · `init!=`(참조가 달라 초기값 자체가 "
             "다른 비교, 교훈 #82). 표시가 붙은 팔은 **나란히 놓을 수 없다.**")
    L.append("  - ⚠️ 함께 찍힌 `gate %` 는 **품질 지표가 아니다**(r = **+0.82**, 부호가 반대다).")
    L.append(f"- 🔴 **프레임 × 팔 — `{root}/stats/heatmap.png`**")
    L.append("  - |Δdx| 와 이동량을 격자로. **오른쪽 띠 = 프레임 중앙값(행 효과)** · "
             "**아래 띠 = 팔 중앙값(열 효과)**. 가로줄이 뜨면 «그 프레임이 어렵다», "
             "세로줄이 뜨면 «그 팔이 나쁘다» — 상자그림은 이 둘을 뭉갠다.")
    L.append("  - 🔴 **프레임 단위 «순위표» 가 아니다** — GT 없이는 원리적으로 못 정한다"
             "(#56·#64). 패턴을 찾아 **그 프레임을 오버레이로 여는** 용도다.\n")
    if len(made) < 3:
        L.append(f"⚠️ {3 - len(made)}장이 빠졌다(그린 것: {', '.join(made) or '없음'}) — "
                 f"`report.json`·`scale_check.json`·`stats/metrics_long.csv` 중 없는 것이 있다.\n")
    return L


def report(a) -> int:
    root = Path(a.out)
    in_dir = Path(a.in_dir)
    # 🔴 **줄자 값은 그 «촬영» 의 물리량이지 그 «실행» 의 인자가 아니다.** `--report-only` 로 다시
    #    낼 때 플래그를 안 주면 조용히 사라져 **거리 사각 대조의 유일한 외부 다리가 없어진다**
    #    (`fx` 오차는 내부 관측 전부를 통과한다). `run_meta.json` 에 남은 값을 물려받는다.
    if a.true_distance_mm is None:
        prev = _read_json(root / "run_meta.json") or {}
        if prev.get("true_distance_mm") is not None:
            a.true_distance_mm = float(prev["true_distance_mm"])
            print(f"    · 줄자 {a.true_distance_mm:.0f}mm 를 `run_meta.json` 에서 물려받았다 "
                  f"(`--true-distance-mm` 미지정)", flush=True)
    diag = capture_diag(in_dir, root / "st", root / "seg", root / "fp_ns2")
    ids = ["A1", "A2a", "A2b", "A4"] + (["I1"] if a.ism else []) \
        + (["T1"] if a.sam3_text else [])
    # ★ `--mode` 로 늘어난 팔은 **디스크에 실제로 있는 것만** 집는다 — 리포트만 다시 낼 때
    #   (`--report-only`) 모드 인자를 안 줘도 그 런의 팔이 그대로 나온다.
    ids += [k for k in ("Cs16", "Cs32", "Cg0", "Cg07", "Cg3", "Cz", "H1", "Ccas", "IX1",
                        "Ed", "Eb", "Ea", "Eg3", "Eg05")
            if (root / k / "meta_contour.json").exists() and k not in ids]
    # ★ `refs` 스윕 팔은 이름이 런마다 다르다 — **디스크를 훑어** 집는다(정적 목록으로 못 적는다).
    ids += sorted(d.name for d in root.iterdir()
                  if d.is_dir() and (d.name.startswith("R_") or
                                     (d.name.startswith("Rn") and d.name[2:].isdigit()))
                  and (d / "meta_contour.json").exists() and d.name not in ids)
    v = {sid: read_variant(root, sid) for sid in ids}
    v["A3"] = read_variant(root, "A3")                       # 정합 없음 — lr 만 있다
    if a.ism:
        v["I3"] = read_variant(root, "I3")                   # ISM 경로의 정합 전 (I1 의 분모)
    if a.sam3_text:
        v["T3"] = read_variant(root, "T3")                   # 텍스트 경로의 정합 전 (T1 의 분모)
    labels = {"A1": "A1 홀 제외 (배포본)", "A2a": "A2a 홀 윤곽 (규격부)",
              "A2b": "A2b 홀 중심", "A3": "A3 정합 off (FP 단독)", "A4": "A4 refine 초기값",
              "I1": "I1 ISM 초기값 + 정합 (CAD only)", "I3": "I3 ISM 정합 off",
              "T1": "T1 텍스트 초기값 + 정합 (참조 비의존)", "T3": "T3 텍스트 정합 off",
              # ── `--mode` 로 늘어나는 팔 ─────────────────────────────────────────
              "Cs16": "Cs16 탐색폭 16px", "Cs32": "Cs32 탐색폭 32px",
              "Cg0": "Cg0 게이트 off", "Cg3": "Cg3 게이트 3.0°", "Cg07": "Cg07 게이트 0.75°",
              "Cz": "Cz --fix-z on", "H1": "H1 하이브리드 초기값 (§27-7)",
              "Ccas": "Ccas 캐스케이드 32→12→8", "IX1": "IX1 ISM full · select exemplar",
              "Ed": "Ed 극성 dark_out", "Eb": "Eb 극성 bright_out", "Ea": "Ea 극성 any",
              "Eg3": "Eg3 min-grad 3.0", "Eg05": "Eg05 min-grad 0.5"}
    # ★ `refs` 스윕 팔은 **이름이 런마다 다르다**(`R_n40black`·`Rn5`) → 라벨을 만들어 붙인다.
    #   🔴 이 팔들은 **초기값이 서로 다르다** — 라벨에 ⚠️ 를 박아 «후퇴율로 비교 금지»(교훈 #82)를
    #      표 안에서 상기시킨다.
    for sid in ids:
        if sid.startswith("R_"):
            labels[sid] = f"{sid} 참조 {sid[2:]} ⚠️초기값다름"
        elif sid.startswith("Rn"):
            labels[sid] = f"{sid} n-refs {sid[2:]} ⚠️초기값다름"

    L = []
    L.append(f"# A그룹 결과 — `{in_dir}`\n")
    L.append(f"**{time.strftime('%Y-%m-%d %H:%M:%S')}** · 프레임 {diag['n_frames']}장 · "
             f"obj `{a.obj}` · 참조 `{a.refs or REFS_BY_PRESET[a.preset][0]}` "
             f"(preset `{a.preset}`, n-refs {a.n_refs}, {a.refs_mode}) · 게이트 {a.gate_deg}°"
             + (f" · `--fix-z`" if a.fix_z else "")
             + (f" · 실측거리 {a.true_distance_mm:.0f}mm" if a.true_distance_mm else "") + "\n")
    if a.note:
        L.append(f"> **메모** — {a.note}\n")
    L.append(f"설정 전체는 `{root}/run_meta.json` 에 있다. "
             f"런 여러 개를 비교하려면 `envs/pose/bin/python tools/compare_runs.py "
             f"{root} <다른런> ...`\n")
    L.append("🔴 **실환경에는 GT 가 없다** — 아래는 전부 GT-free 지표다. "
             "R/t 절대 오차는 원리적으로 못 낸다(`PIPELINE_CATALOG §7.5`).\n")

    L.append("## 촬영 진단\n")
    m = diag["median"]
    L.append("| 항목 | 중앙값 | 기준 |")
    L.append("|---|---|---|")
    if "flange_dia_px" in m:
        L.append(f"| flange 등가지름 | **{m['flange_dia_px']:.0f}px** | "
                 f"목표 {TARGET_FLANGE_PX:.0f}px (§34-9) |")
    if "z_mm" in m:
        L.append(f"| FP 추정 거리 (z) | **{m['z_mm']:.0f}mm** | 최적 220~300mm (§34-9) |")
    if "depth_plane_mm" in m:
        L.append(f"| stereo depth (flange **평면적합**) | **{m['depth_plane_mm']:.0f}mm** | "
                 f"FP z 와 **다른 경로** (⚠️ `fx·B` 는 공유 — 교훈 #89) |")
    if "plane_rms_mm" in m:
        L.append(f"| flange 평면 잔차 rms | **{m['plane_rms_mm']:.2f}mm** | "
                 f"🔴 스테레오가 표면을 뚫었나 (sim 기준선 0.37mm) |")
    if "z_minus_depth_mm" in m:
        L.append(f"| 그 차 (FP − depth) | **{m['z_minus_depth_mm']:+.1f}mm** | "
                 f"±3mm 안이면 일관 |")
    if a.true_distance_mm and "z_mm" in m:
        L.append(f"| 줄자 실측 | **{a.true_distance_mm:.0f}mm** | 기준점 = flange **상면 중심** |")
    _sc = (_read_json(Path(a.out) / "scale_check.json") or {}).get("median")
    if _sc:
        L.append(f"| 실루엣 거리 | **{_sc['z_silhouette_mm']:.0f}mm** | "
                 f"**`baseline` 비의존** — 앞의 둘과 뿌리가 다르다 |")
    if "lat_mm" in m:
        L.append(f"| 광축 이탈 (횡) | **{m['lat_mm']:.0f}mm** "
                 f"(x {m.get('tx_mm', 0):+.0f} / y {m.get('ty_mm', 0):+.0f}) | "
                 f"클수록 Z 오차가 횡으로 샌다 |")
    for k, lab, ref in (("valid_all", "depth 유효율 (전체)", "—"),
                        ("valid_flange", "depth 유효율 (flange)", "검정 불투명 — 높아야 정상"),
                        ("valid_ring", "depth 유효율 (주변 링)", "🔴 **반투명 본체 판정**")):
        if k in m:
            L.append(f"| {lab} | **{m[k]*100:.1f}%** | {ref} |")
    L.append("")

    L.append("## 변형 비교 (GT-free)\n")
    # ★ `이동 mm 중앙` 이 **정합 on/off 판정값**이다(§35-2m-6): ≥10mm 면 정합기가 신호를 못 찾은 것.
    #   `이동 °` 와 달리 게이트 축이 아니라서 «게이트가 못 잡는 t 편향» 까지 드러난다.
    L.append("| 변형 | 게이트 후퇴 | 대응점 | rms px | 이동 ° 중앙/최대 | **이동 mm 중앙** "
             "| 좌우 \\|Δdx\\| px | 좌우 Δdx **부호** | 좌우 dz mm |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    # ⚠️ ISM 경로도 **같은 표**에 넣는다 — 따로 내면 나란히 비교가 안 된다.
    all_gated: list[str] = []
    order = ["A3", "A1", "A2a", "A2b", "A4"] + (["I3", "I1"] if a.ism else []) \
        + (["T3", "T1"] if a.sam3_text else []) \
        + [k for k in ("Cs16", "Cs32", "Cg0", "Cg07", "Cg3", "Cz", "H1", "Ccas", "IX1",
                       "Ed", "Eb", "Ea", "Eg3", "Eg05") if k in v] \
        + sorted(k for k in v if k.startswith("R_") or (k.startswith("Rn") and k[2:].isdigit()))
    for sid in order:
        r = v.get(sid, {})
        gp = f"{r['gated']}/{r['n']} ({r['gated_pct']}%)" if "gated" in r else "—"
        mv = f"{r['moved_deg_med']:.2f} / {r['moved_deg_max']:.2f}" if "moved_deg_med" in r else "—"
        sg = r.get("lr_ddx_signed")
        mm = r.get("moved_mm_med")
        # 🔴 **`--fix-z` 팔에는 이동량 규칙을 적용하지 않는다.** Z 가 묶여 있어 `moved_mm` 이
        #    구조적으로 작게 나온다 — «정합이 잘 맞았다» 가 아니라 «움직일 수 없었다» 다.
        #    실측: 같은 데이터에서 A1 12.45mm vs Cz 1.32mm. 🔴 를 그대로 안 붙이면 이 팔이
        #    «유일하게 건강한 팔» 로 보인다(교훈 #26 — 두 값이 같은 양인지부터 본다).
        fixz = sid == "Cz" or a.fix_z
        mms = (f"**{mm:.2f}** ⚠️Z고정" if fixz else
               f"**{mm:.2f}**{' 🔴' if mm >= 10 else ''}") if mm is not None else "—"
        # 🔴 **후퇴율 100% 면 그 행의 좌우 지표는 «그 변형» 이 아니라 «초기값» 이다.**
        #    게이트가 전 프레임에서 정합 결과를 버렸으므로 최종 pose = 초기 pose 다. 표시를 안 하면
        #    «홀 중심 모드가 |Δdx| 0.90 을 냈다» 로 읽히는데 실제로는 그 모드가 **한 번도 안 쓰였다.**
        #    교훈 #21(«소수점까지 같으면 차이 없음이 아니라 적용 안 됨»)이 표 층에서 재발하는 자리다.
        allg = r.get("gated_pct") == 100.0
        L.append(f"| {labels[sid]}{' ⬛' if allg else ''} | {gp} | {r.get('n_corr', '—')} | "
                 f"{r.get('rms_px', '—')} | {mv} | {mms} | "
                 f"**{r.get('lr_ddx', '—')}**{'*' if allg else ''} | "
                 f"{f'{sg:+.2f}' if sg is not None else '—'} | {r.get('lr_dz', '—')} |")
        if allg:
            all_gated.append(labels[sid])
    L.append("")
    if all_gated:
        L.append(f"🔴 **⬛ 표시({', '.join(all_gated)})는 «후퇴율 100%» 다 — 그 행의 좌우 지표(`*`)는 "
                 f"«그 변형의 결과» 가 아니라 «초기값» 이다.** 게이트가 전 프레임에서 정합 결과를 버렸으므로 "
                 f"최종 pose = 초기 pose 이고, **그 변형은 한 번도 실제로 쓰이지 않았다.** "
                 f"두 변형의 좌우 값이 소수점까지 같다면 그것도 같은 이유다(교훈 #21). "
                 f"이 행으로 «이 변형이 좋다/나쁘다» 를 말하면 안 된다 — 말할 수 있는 것은 "
                 f"**«이 조건에서는 정합이 전혀 채택되지 않았다»** 까지다.")
    L.append("- **게이트 후퇴** = 정합이 초기값에서 1.5° 넘게 움직여 결과를 버린 프레임 수. "
             "높으면 «정합이 폭주했거나 CAD 가 실물과 다르다».")
    L.append("  - 🔴🔴 **후퇴율이 낮은 팔이 좋은 팔이 아니다.** 후퇴 = «정합을 안 쓰고 초기값을 "
             "냈다» 이므로, **정합이 해로운 조건에서는 많이 버릴수록 정확해진다.** sim 검증에서 "
             "후퇴율과 실제 KPI 의 상관이 **r = +0.82**(높을수록 정확)로 나왔다. "
             "후퇴율은 «정합이 얼마나 개입했나» 의 역지표일 뿐 **품질 지표가 아니다** — "
             "§32 판정 절차(후퇴율 낮은 쪽)는 «같은 정합 설정에서 초기값만 바꾼» 비교에만 쓴다.")
    L.append("  - ⚠️ **정합 rms 로 팔을 고르면 안 된다** — 같은 검증에서 KPI 와의 상관이 "
             "**r = −0.05**(사실상 무관)였다. 축퇴 방향이라 틀린 pose 도 관측에 잘 맞는다(교훈 #56).")
    L.append("  - ★★★ **팔 서열을 가장 잘 예측한 GT-free 지표는 «좌우 |Δdx|» 다 (r = −0.94).** "
             "우열을 가려야 하면 이 열을 본다.")
    L.append("- **좌우 |Δdx|** = 왼쪽만 보고 정합한 pose 를 오른쪽에 투영했을 때 남는 어긋남. "
             "**작을수록 좋다.** 절대값이 아니라 변형 간 차이로만 읽는다.")
    L.append("- 🔴 **좌우 Δdx 부호** = 같은 값의 **부호 있는** 중앙값. `|Δdx|` 는 «얼마나» 만 "
             "말하고 «어느 쪽으로» 를 못 말한다. **부호가 한쪽으로 쏠려 있으면 계통 편향**이고 "
             "그건 게이트로 못 막는 축이다(§29·§35-2i). 0 근처에서 왔다갔다 하면 랜덤 오차다.")
    L.append("- 좌우 **dz** 는 그 어긋남을 깊이로 환산한 값 — 기준선 편향이 있어 "
             "0 이 아닌 게 정상이다.")
    # ⚠️ 디스크에 «팔처럼 생긴» 중간 산출물이 남는다 — 안 적어 두면 그걸 팔로 착각해 채점한다.
    if (root / "Ccas_s2").exists():
        L.append("- ⚠️ `Ccas_s1`·`Ccas_s2` 디렉토리는 **팔이 아니라 캐스케이드의 중간 단**이다"
                 "(게이트 off, 32px → 12px). 표·그래프·CSV 에서 일부러 뺐다 — **최종단은 `Ccas`** 다.")
    # 🔴🔴 **선택 편향** — 팔을 늘리면 «가장 좋아 보이는 팔» 이 잡음일 확률이 같이 커진다.
    #    실물 초반에 축을 넓히는 것은 맞지만(사용자 방침), 그 표에서 승자를 뽑는 순간
    #    표본 하나에 과적합된다. **경고를 표 바로 밑에 둔다** — 아래로 밀면 안 읽힌다.
    n_arm, n_fr = len(order), diag.get("n_frames", 0)
    if n_arm >= 8 and n_fr:
        L.append(f"\n🔴🔴 **선택 편향 경고 — 팔 {n_arm}개 × 프레임 {n_fr}장.** 이 표에서 "
                 f"«가장 좋아 보이는 팔» 을 고르면 **그 표본에 과적합**된다. "
                 f"팔이 많을수록 잡음만으로도 한 팔이 앞서 보인다"
                 + (f" (특히 n={n_fr} 은 꼬리를 못 본다 — 교훈 #58)" if n_fr < 40 else "") + ".")
        L.append("  - ✅ **쓰는 법**: ① **사전 정의 규칙**으로 판정한다(정합 on/off = 이동량 t 중앙 "
                 "≥10mm · refine on/off = §32 후퇴율). ② 축 하나씩, **같은 초기값 위에서만** 비교한다"
                 "(A1↔A2a↔A2b, A1↔A4). ③ 경로 간(A↔I↔T)은 초기값이 달라 **후퇴율로 비교하면 안 된다**"
                 "(교훈 #82).")
        L.append("  - ✅ **좁히는 법**: 넓힌 런에서 **후보를 2~3개로 줄인 뒤**, 그 후보만 "
                 "**새로 찍은 20~40장**에서 확인한다. 같은 데이터에서 고르고 같은 데이터에서 "
                 "검증하면 그건 검증이 아니다.")
    L.append("")

    # ── `--mode refs` 스윕 요약 ────────────────────────────────────────────────────
    rs = refs_sweep_rows(root, a.preset)
    if len(rs) > 1:
        L.append("## 참조 거리대 스윕 (`--mode refs`)\n")
        L.append("🔴 **이 표를 게이트 후퇴율로 읽지 말 것**(교훈 #82) — 참조가 바뀌면 마스크가 "
                 "바뀌고 **FP 초기값 자체가 달라진다.** 후퇴율은 «같은 초기값 위에서 플래그만 바꾼» "
                 "비교(A1↔A2a↔A2b)에만 유효하다. 여기서는 **분할이 무엇을 집었나** 를 직접 본다.\n")
        L.append("| 참조 프리셋 | 검출 | 면적 중앙 (px) | **면적 최소** | **쪼그라든 장** | "
                 "이탈 중앙 | **이탈 최대** |")
        L.append("|---|---|---|---|---|---|---|")
        for r in rs:
            fr = f"{r['found']}/{r['n']}"
            am = f"{r['area_med']:,.0f}" if r["area_med"] else "—"
            an = f"{r['area_min']:,.0f}" if r.get("area_min") else "—"
            ns = r.get("n_small", 0)
            om = f"{r['off_med']:.3f}" if r["off_med"] is not None else "—"
            ox = (f"{r['off_max']:.3f}" + (" 🔴" if r["off_max"] > 0.25 else "")) \
                if r.get("off_max") is not None else "—"
            L.append(f"| `{r['preset']}` | {fr} | {am} | {an} | "
                     f"{'**' + str(ns) + '** 🔴' if ns else '0'} | {om} | {ox} |")
        best = max((r for r in rs if r["found"]), key=lambda r: r["found"], default=None)
        L.append("")
        L.append("- **읽는 법** — ① **검출율**이 먼저다(0 이면 그 거리대 참조가 안 맞는 것) "
                 "② **이탈 >0.25** 면 엉뚱한 물체다(§34-10 사전 위치 가드를 화면 좌표로 옮긴 값) "
                 "③ 면적은 **거리의 대리**다 — 참조 거리대가 맞으면 면적이 그 대역의 기대치에 든다.")
        L.append("- 🔴🔴 **«쪼그라든 장»(면적이 중앙의 0.5배 미만)과 «최소·최대» 를 먼저 본다.** "
                 "중앙값은 **부분 실패를 통째로 가린다** — sim 검증에서 `n25black` 이 "
                 "«검출 20/20 · 면적 중앙 35,982 · 이탈 0.015» 로 완벽해 보였는데 GT 로 채점하니 "
                 "**3프레임이 90~115° 뒤집혀 KPI 9/20** 이었다. 한 프레임의 마스크가 5,234px "
                 "(중앙의 0.15배)로 쪼그라든 것이 원인이다(교훈 #6·#13의 재발).")
        L.append(f"- **`flange 등가지름 목표 {TARGET_FLANGE_PX:.0f}px`**(§34-9)와 대조하면 "
                 f"«실제 거리가 몇인가» 가 나온다. 면적 → 등가지름은 `2·√(면적/π)` 다.")
        if best:
            L.append(f"- 검출율 최고: **`{best['preset']}`** ({best['found']}/{best['n']}). "
                     f"⚠️ 검출율만으로 고르지 말 것 — **중심 이탈**과 `segcmp` 육안을 같이 본다.")
        L.append("- 🔴 **여기서 고른 참조는 «이 데이터에서 골랐다»** — 확정하려면 그 참조로 "
                 "**새로 찍은 20~40장**을 다시 돌린다(§35-2o-4 선택 편향).\n")

    L.append("## 판정\n")
    for s in cam_verdicts(Path(a.in_dir)):          # 🔴 경고 전용 — 실행을 막지 않는다
        L.append(f"- {s}")
    for s in distance_verdicts(diag, a.true_distance_mm,
                               _read_json(Path(a.out) / "scale_check.json")):
        L.append(f"- {s}")
    for s in verdicts(v, diag, ism=a.ism):
        L.append(f"- {s}")
    L.append("")

    # ── (a) sim 기준선 대조 ───────────────────────────────────────────────────
    L.append("## 이 값이 상이한가 — sim 기준선 대조\n")
    L.append("| 항목 | sim 대역 | **이번 런** | | 뜻 |")
    L.append("|---|---|---|---|---|")
    n_out = 0
    for lab, lo, hi, unit, val, note in baseline_rows(diag, v):
        if val is None:
            L.append(f"| {lab} | {lo}~{hi}{unit} | — | ⚪ | {note} |")
            continue
        inside = lo <= val <= hi
        n_out += not inside
        mark = "✅" if inside else ("🔼" if val > hi else "🔽")
        L.append(f"| {lab} | {lo}~{hi}{unit} | **{val:g}{unit}** | {mark} | {note} |")
    L.append("")
    L.append(f"- 🔴 **이 표는 «정상 범위» 가 아니라 «sim 에서 잰 값» 이다.** 벗어남({n_out}건)이 "
             f"곧 고장이 아니다 — **도메인 갭일 수도 있다.** 표는 판정을 대신하지 않고 "
             f"**비교 대상**을 준다.")
    L.append("- 출처: `e2e_A`·`fakereal_oA`(0.22~0.30m) · `fakereal30oA`(0.28~0.35m), 각 n=20, "
             "몸체 orange. **조건 2개에서만 잰 값**이라 대역이 좁다 — "
             "**첫 실물 런 이후 real 값으로 갱신할 것**(`tools/run_group_a.py` 의 `SIM_BASELINE_*`).")
    L.append("- ⚠️ 실물에서 **가장 먼저 벌어질 값은 `flange 평면 잔차`** 다(스테레오 관통 품질). "
             "sim 은 0.37mm 인데 실물은 그보다 클 것이 당연하고, **얼마나** 큰지가 정보다.\n")

    # ── (b) 프레임 이상치 (분포 기준) ──────────────────────────────────────────
    fo = frame_outliers(root, diag)
    bimodal = fo.pop("_bimodal", [])
    L.append("## 이상 프레임 (분포 기준)\n")
    if "_note" in fo:
        L.append(f"⚪ {fo['_note']}\n")
    elif not fo:
        L.append("✅ **이상치 없다** — 어떤 프레임도 나머지와 통계적으로 벗어나지 않는다"
                 "(강건 z ≥ 3.5 없음). 🔴 단 **«다 같이 틀린» 경우는 이 검사가 못 잡는다.**\n")
    else:
        L.append("| 프레임 | 지표 | z | 이 프레임 | 전체 중앙 |")
        L.append("|---|---|---|---|---|")
        for f, items in fo.items():
            for lab, z, x, m in items:
                L.append(f"| `{f}` | {lab} | **{z:.1f}** | {x:g} | {m:g} |")
        L.append("")
    if bimodal:
        L.append("### ⚠️ 이상치가 아니라 **분포가 갈라진** 지표\n")
        L.append("| 지표 | 벗어난 프레임 | 중앙 | 최소~최대 |")
        L.append("|---|---|---|---|")
        for lab, nc, nt, m, lo, hi in bimodal:
            L.append(f"| {lab} | **{nc}/{nt}** | {m:g} | {lo:g} ~ {hi:g} |")
        L.append("")
        L.append("- 🔴 **«소수의 사고» 가 아니라 «상당수가 다르게 동작한다» 는 뜻이다.** "
                 "프레임 몇 장을 열어 보는 것으로는 안 풀린다 — **자세·거리·조명 같은 조건 축**을 "
                 "의심하고 `stats/metrics_long.csv` 에서 그 축과의 상관을 본다.")
        L.append("- ⚠️ 이상치 표에서 **일부러 뺐다** — 25% 넘게 걸리는 지표를 이상치로 보고하면 "
                 "«프레임 몇 장 문제» 로 오독하게 된다.\n")
    L.append("- ★ **위 «여기부터 보라» 와 다른 도구다** — 저기는 **순위**(정상인 런에서도 뭔가 "
             "나온다), 여기는 **분포**(아무것도 안 나오는 게 정상이고 **나오면 그 자체가 신호**다).")
    L.append("- ★ **기준선이 필요 없다** — 런 자기 자신이 기준이라 **도메인 갭에 면역**이다. "
             "sim 값과 아무리 달라도 실물 첫 런부터 그대로 작동한다.")
    L.append("- ⚠️ **이상치 = «pose 가 틀렸다» 가 아니다.** §35-2c 에서 분할이 깨졌는데 "
             "pose 는 정상인 프레임이 실제로 있었다. **어느 지표가 튀었는지**를 보고 상류를 연다.\n")

    L.append("## 다음에 무엇을 할까 (비용 순)\n")
    L.append("🔴 이 환경은 **로봇이 없고 손 촬영**이라 «촬영 0» 과 «촬영 2» 의 차이가 크다. "
             "그래서 중요도가 아니라 **비용 순**이다.\n")
    for i, s in enumerate(next_steps(v, diag, a), 1):
        L.append(f"{i}. {s}")
    L.append("\n⚠️ 이 목록은 **지금까지 sim 에서 본 실패 유형만** 안다. "
             "새로운 증상은 여기 없다 — **목록이 짧다고 «문제 없음» 이 아니다.**\n")

    # ── 「여기부터 보라」 ─────────────────────────────────────────────────────
    picks = worst_frames(root, diag, v)
    if picks:
        L.append("## 여기부터 보라 — 지표별 최악 프레임\n")
        L.append("| 프레임 | 걸린 지표 |")
        L.append("|---|---|")
        for f, reasons in picks.items():
            L.append(f"| `{f}` | " + " · ".join(w for w, _ in reasons) + " |")
        wd = make_worst_dir(a, root, picks)
        if wd:
            L.append(f"\n★ 이 프레임들만 `refine_contour --debug` 로 다시 돌렸다 → "
                     f"**`{wd}/A1_debug/frame_*/contour_debug.png`**")
            L.append("  - 노랑=모델 실루엣 샘플 · 빨강/파랑=찾아낸 관측 edge 까지의 잔차(밖/안) "
                     "· 초록=GT(실물엔 없다). **범례가 이미지에 찍혀 있다** — "
                     "`viz.overlay_pose` 와 색 규약이 달라서다.")
            L.append("  - 🔴 **이 그림이 «Sobel 이 물체 경계를 잡았나, 융기 능선을 잡았나, "
                     "그림자를 잡았나» 를 보는 유일한 수단이다.** 검정 몸체에서 정합기가 "
                     "경계 안쪽 능선으로 끌려가는 계통 편향(§35-2i)을 실물에서 대리 관측하는 통로다.")
        else:
            L.append(f"\n⚠️ `{root}/worst/` 생성 실패 — 수동으로는 "
                     f"`refine_contour ... --debug` 로 다시 돌리면 된다.")
        L.append("\n⚠️ **순위 기반이지 임계값 기반이 아니다** — 정상인 런에서도 «상대적으로 가장 "
                 "나쁜» 장은 나온다. *«이상이 있다»* 가 아니라 *«본다면 여기부터»* 다.\n")

    L.append("## 눈으로 볼 것\n")
    L.append(f"- 🔴 **진단 시트 — `{root}/diag/diag_sheet.png`** (프레임마다: `{root}/diag/diag_frame_*.png`)")
    L.append("  - 한 줄에 6패널: 원본 · `mask_full` · `mask_flange` · depth · valid · pose. "
             "**«어디서 깨졌는가» 를 보는 도구다** — 분할 0, depth 미관통, 노출 이상이 여기서 갈린다.")
    L.append("  - depth 는 **물체 마스크 안에서** 구간을 잡는다(배경으로 잡으면 물체가 단색이 된다). "
             "캡션의 `scale[obj] lo~hi` 를 보지 않고 색을 프레임 간에 비교하면 안 된다.")
    L.append(f"- 🔴 **프레임 추이 — `{root}/diag/diag_trends.png`** · 수치 `{root}/diag/diag_metrics.json`")
    L.append("  - **전 프레임**의 등가지름·depth·평면잔차·유효율·이동량을 한 장에. "
             "40장을 눈으로 훑는 대신 **여기서 이상 프레임을 찾아 그 장만 연다**. "
             "붉은 세로 띠 = 게이트 후퇴 프레임.")
    L.append(f"- 🔴 **pose 오버레이 — `{root}/overlay_sheet.png`** (프레임마다: `{root}/overlay/overlay_frame_*.png`)")
    L.append("  - **GT 가 없으니 이게 «맞는가» 를 보는 유일한 수단이다.** 초록 윤곽이 사진 속 flange "
             "테두리에 붙어 있는지, 축 삼각대(X/Y/Z)가 상식적인 방향인지, 변형 다섯이 서로 어긋나는지를 본다.")
    L.append("  - 어긋남이 **한 방향으로 일관**되면 계통 편향(§29 외곽 융기 축)이고 **게이트가 못 막는다**. "
             "프레임마다 제각각이면 초기값 폭주다.")
    L.append("  - ★ **좌하단 mm 눈금자**로 그 어긋남을 **읽는다**. 크롭 배율이 프레임마다 달라 밖에서 "
             "환산할 수 없어서 이미지 안에 박았다. ⚠️ **물체 평면(pose 의 z)에서만 맞다.**")
    L.append(f"- 🔴 **겹쳐 그린 오버레이 — `{root}/overlay_combo.png`** "
             f"(프레임마다: `{root}/overlay_combo/overlay_frame_*.png`)")
    L.append("  - **위 시트와 같은 데이터를 «한 이미지에» 겹친 것**이다. 타일을 나눠 그리면 "
             "*«coarse 와 refined 가 얼마나 어긋나는가»* 를 눈으로 못 잰다 — 같은 화소 위에 놓아야 보인다.")
    L.append("  - **주석 줄의 색 = 그 예측의 윤곽 색**이다. 어느 팔이 튀는지 한 줄로 갈린다. "
             "경로별 FP 원본(`fp_ns2`·`fp_ism`·`fp_txt` 의 coarse)도 함께 들어간다.")
    L.append(f"- 🔴 **분할 + pose 겹쳐 비교 — `{root}/segcmp/seg_compare.png`** "
             f"(프레임마다: `{root}/segcmp/segcmp_frame_*.png`)")
    L.append("  - 분할 3~4종(`[M]` 채움+실선)과 **그 경로의 FP pose 투영**(`[P]` 점선+기울인 십자)을 "
             "**한 화면에** 겹치고, 팔마다 `면적% · 중심 · 이탈` 을 그 색으로 찍는다.")
    L.append("  - ★★ **이 시트만이 두 실패를 가른다** — **①「마스크부터 엉뚱한 걸 잡았다」**(점선이 "
             "채움과 함께 딴 데 있다) vs **②「마스크는 맞는데 pose 가 틀렸다」**(채움은 물체 위인데 "
             "점선만 어긋났다). ①이면 분할(참조·프롬프트·거리대)을, ②면 depth·초기값·CAD 를 고친다.")
    L.append("  - 🔴 **크롭하지 않는다** — 질문이 *«화면 어디를 집었나»* 라서 크롭하면 답이 사라진다. "
             "흰 십자 = 화면 중심 · 회색 타원 = 이탈 0.25. **타원 밖에 작게 찍힌 팔이 «엉뚱한 물체를 "
             "집은» 팔**이다(실물 50cm 에서 ISM 이 면적 0.64%·이탈 0.56 이었다).")
    L.append("  - ⚠️ pose 투영은 **`full.ply`** 다(마스크가 `mask_full` 이라서). `A_exemplar_flange` "
             "행만 flange 라 면적이 작은 것이 정상이다.")
    L.append(f"- depth 유효 마스크 — `{root/'st'}/frame_*/valid.png`  🔴 열린 항목 #1")
    L.append(f"- flange 마스크 — `{root/'seg'}/frame_*/mask_flange.png`")
    L.append(f"- 정합 디버그 — `--debug` 로 다시 돌리면 `{root}/A1/frame_*/contour_debug.png`")
    L.append(f"- 최종 pose — `{root}/A1/frame_*/pose_refined.json`\n")
    L.append(HDR_ANALYZE)
    L.append(f"- 🔴🔴 **신호등 — `{root}/stats/traffic.png`** (한글판 표: `{root}/stats/summary.md`)")
    L.append("  - **(프레임 × [촬영 3열 + 변형])** 격자. 🟢 정상 · 🟡 주의 · 🔴 고장 · ⬛ pose 없음. "
             "칸의 숫자는 **판정을 내린 그 값**이다. 40×9 에서 «깨진 칸» 을 한눈에 찾는다.")
    L.append("  - 🔴🔴 **«순위표» 가 아니다.** GT 가 없으면 *살아남은 것들 중* 어느 쪽이 더 정확한지는 "
             "**프레임 단위로 원리적으로 못 정한다** — rms 는 실패·성공 분포가 겹치고(교훈 #56), "
             "좌우 일관성은 프레임당 ±1~2mm 이며(§35), 게이트는 계통 편향을 못 본다(교훈 #64). "
             "서열화는 **런 단위**(위 «변형 비교» 표)에서만 한다.")
    L.append("  - 촬영 3열(노출·마스크·depth)은 **런 자기 자신 기준 강건 z-score** 라 "
             "sim 기준선이 필요 없고 **도메인 갭에 면역**이다(§35-2l-8b).")
    L.append(f"- 🔴 **변형 비교 그래프 — `{root}/stats/variants.png`** "
             "(후퇴율 · 이동량 분포 · 좌우 일관성 · 대응점). **상자 + 점**이라 꼬리가 보인다.")
    L.append(f"- 🔴 **`{root}/stats/metrics_long.csv`** — (프레임 × 변형) 긴 형식. "
             "pandas/엑셀로 바로 연다. `frames.csv` 는 촬영지표(노출·마스크·depth·유효율).")
    L.append(f"- `{root}/stats/summary.md` — 변형별 **중앙 / p90 / 최대**. "
             "⚠️ 중앙값만 보고 우열을 정하지 않는다(교훈 #16).")
    L.append(f"- `{root}/stats/repeatability.png` — **정지 구간 반복도**. "
             "⚠️ 거리 산포가 크면 그건 반복도가 아니라 자세 변화다 — `summary.md` 가 자동 판정한다.\n")

    # 🔴 **`report.json` 을 먼저 쓴다** — 아래 그림 3종이 그 파일(프레임별 z·줄자)을 읽는다.
    #    순서를 바꾸면 첫 런에서 `distance.png` 만 조용히 빠진다.
    (root / "report.json").write_text(json.dumps(
        {"in": str(in_dir), "obj": a.obj, "gate_deg": a.gate_deg,
         "datetime_local": time.strftime("%Y-%m-%d %H:%M:%S"), "note": a.note,
         "preset": a.preset, "refs": a.refs or REFS_BY_PRESET[a.preset][0],
         "true_distance_mm": a.true_distance_mm,
         # 🔴 «이 z 가 어느 경로에서 나왔나» 를 반드시 남긴다 — `scale_check` 는 다른 경로(`fp_ism`)의
         #    pose 를 쓸 수 있어서, 출처를 모르면 하류가 **두 경로의 z 를 빼는** 사고를 낸다(교훈 #26).
         "capture_pose_dir": "fp_ns2",
         "capture": diag, "variants": v}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    # 그림 3종은 **「직접 분석할 것」 의 맨 앞**에 꽂는다 — 가장 먼저 볼 것이 가장 먼저 나와야 한다.
    # (생성 자체는 `report.json` 이 있어야 되므로 여기서 하고, 줄만 위로 끼워 넣는다.)
    ch = result_charts(root, a)
    if ch:
        i = L.index(HDR_ANALYZE) + 1 if HDR_ANALYZE in L else len(L)
        L[i:i] = ch
    # 🔴 배선 감사는 «직접 분석할 것» **바로 앞**에 — 그림·표를 해석하기 전에 통과 여부부터 본다.
    au = wiring_audit(root)
    if au:
        i = L.index(HDR_ANALYZE) if HDR_ANALYZE in L else len(L)
        L[i:i] = au

    txt = "\n".join(L)
    (root / "report.md").write_text(txt)
    print("\n" + txt)
    print(f"→ {root/'report.md'} · {root/'report.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A그룹 원샷 러너 (근접 촬영 1벌 → A1~A4)")
    # ⚠️ `--list-presets` 는 «디스크에 뭐가 있나» 만 보는 조회 명령이라 입출력이 필요 없다.
    #    required=True 로 두면 목록을 보려고 더미 경로를 지어내야 한다 — 아래에서 직접 검사한다.
    ap.add_argument("--in", dest="in_dir", help="<dir>/frame_XXXX/{left,right,cam}")
    ap.add_argument("--out")
    ap.add_argument("--obj", default="assets/obj/foup_300_semi_r2")
    ap.add_argument("--preset", default="n25", choices=list(REFS_BY_PRESET),
                    help="촬영 거리대(cm) + 몸체 외관 → SAM3 참조. "
                         "예 `n50orange` = 0.45~0.55m · 반투명 주황. "
                         "거리 " + "/".join(_BANDS) + " × 외관 " + "/".join(_APPS) +
                         ". 목록은 --list-presets")
    ap.add_argument("--list-presets", action="store_true", help="참조 프리셋 목록과 존재 여부만 출력")
    ap.add_argument("--refs", default=None, help="참조 디렉토리 이름을 직접 지정 (--preset 무시)")
    ap.add_argument("--n-refs", type=int, default=3)
    ap.add_argument("--refs-mode", default="chain", choices=["chain", "independent"])
    ap.add_argument("--use-prompts-file", action="store_true",
                    help="객체의 sam3_prompts.json 을 쓴다. ⚠️ 기본값(끔)이 §34 sim 재현과 같다")
    # ★ ISM 경로 — **CAD 템플릿만 쓰는 분할 백엔드**(SAM-6D ISM)로 같은 데이터를 한 번 더 푼다.
    #   🔴 목적은 «어느 쪽이 정확한가» 가 아니라 **«도메인 갭이 어느 쪽에 오는가»** 다:
    #   SAM3 참조는 **sim 렌더**라 실사진과 갭이 있고, ISM 템플릿은 **CAD 형상**이라 그 축이 없다.
    #   그래서 두 경로는 «독립» 이어야 뜻이 있다 — `--select score`(ISM 자체 점수)를 쓰고
    #   진단용 `seg_full` 처럼 SAM3 마스크를 exemplar 로 받지 않는다.
    ap.add_argument("--ism", action="store_true",
                    help="SAM-6D ISM 경로(ISM 경로)를 함께 돌린다 — CAD 템플릿 단독, SAM3 비의존")
    # ★ T그룹 — SAM3 를 **참조 없이 낱말로** 돌리는 팔. 참조 자산의 도메인 갭을 우회한다.
    #   🔴 프롬프트는 **실물 몸체 외관에 맞춰야** 한다. 기본값은 sim 검정 몸체 기준이다.
    ap.add_argument("--sam3-text", action="store_true",
                    help="SAM3 텍스트 프롬프트 경로(T그룹)를 함께 돌린다 — 참조 자산 비의존")
    ap.add_argument("--text-prompt", default="black plastic box",
                    help="T그룹 프롬프트. 🔴 실물 몸체 색에 맞출 것 "
                         "(예: \"orange plastic box\" · \"clear plastic box\")")
    # 🔴🔴 **기본값을 0.05 → 0.15 로 되돌렸다 (2026-08-20).** 0.05 는 §35-2m-2 의 sim 측정
    #   («검출 20/20 · 오선택 0»)에 근거했는데, 그 씬은 **`distractors: 0 · occluders: 0`** 이었다.
    #   **고를 다른 물체가 없는 씬에서 «오선택 0» 은 공허하다** — 실물에서 배경 물체를 집었다.
    #   0.15 는 사용자가 **실물 50cm 에서 검증한 값**이다(미검출 2/10 은 있지만 오선택은 없었다).
    #   ⚠️ 내리려면 **오버레이로 무엇을 집었는지 먼저 확인**할 것 — 미검출과 오선택을 맞바꾸는 것이다.
    ap.add_argument("--text-conf", type=float, default=0.15,
                    help="T그룹 검출 임계값. 실물 검증값 0.15. 🔴 내리면 미검출은 줄지만 "
                         "**배경 물체를 집을 위험**이 는다(sim 측정은 방해물 없는 씬이라 이 축을 못 봤다)")
    ap.add_argument("--text-select", default="center", choices=["center", "score", "largest"],
                    help="⚠️ center 는 «카메라가 타깃을 겨눈다» 는 규약에 기댄다(교훈 #15)")
    ap.add_argument("--stereo-scale", type=float, default=0.5)
    ap.add_argument("--input-scale", type=float, default=0.5, help="🔴 1.0 은 OOM (§34-12)")
    ap.add_argument("--gate-deg", type=float, default=1.5)
    ap.add_argument("--fix-z", action="store_true",
                    help="§23 — depth 가 깨끗하면 켠다. 실물 depth 품질을 모르므로 기본은 끔")
    # ── 실험 노트 ─────────────────────────────────────────────────────────────
    #   🔴 실물은 «한 번에» 안 된다 — 거리·조명·참조·플래그를 바꿔 가며 여러 번 돌린다.
    #      무엇을 바꿨는지가 안 남으면 20번째 런에서 «그 좋았던 게 어느 조합이었지» 가 된다.
    ap.add_argument("--note", default=None,
                    help="이 런의 조건 메모 (조명·노출·물체 배치·몇 번째 시도인지). "
                         "run_meta.json 에 그대로 남고 tools/compare_runs.py 가 함께 보여준다")
    ap.add_argument("--true-distance-mm", type=float, default=None,
                    help="줄자로 잰 **카메라 ↔ flange 상면** 거리(mm). **선택**이다 — "
                         "안 주면 FP 추정 z 와 stereo depth 중앙값끼리만 비교한다. "
                         "주면 그 둘이 실측과 각각 얼마나 벗어나는지까지 나온다 → "
                         "**계통 편향(scale·offset)을 real 에서 잡는 가장 싼 수단**")
    # ★★ **`--mode`** — 후보 파이프라인을 얼마나 넓게 펼칠지. 여러 개를 쉼표로 겹칠 수 있다.
    #    🔴 «넓히기» 는 실물 초반의 **탐색** 수단이지 성능 향상이 아니다 — 팔이 늘수록 선택 편향이
    #       커진다(리포트가 경고한다). 축이 좁혀지면 `default` 나 `quick` 으로 되돌린다.
    ap.add_argument("--mode", default="default",
                    help="쉼표로 겹친다. " + " / ".join(f"`{k}`" for k in MODES) +
                         ". 자세한 설명·비용은 `--list-modes`")
    ap.add_argument("--list-modes", action="store_true", help="모드 목록·비용·무엇을 여는가만 출력")
    ap.add_argument("--refs-sweep", default=None,
                    help="`--mode refs` 가 돌 참조 프리셋 목록(쉼표). 예 `n30black,n40black,n50black`. "
                         "안 주면 **`--preset` 과 같은 외관의 모든 거리대**를 자동으로 잡는다. "
                         "🔴 없는 프리셋은 종료코드 2 로 거부한다 — 조용히 빠지면 «스윕했다고 믿는 "
                         "반쪽 런» 이 된다")
    ap.add_argument("--refs-sweep-nrefs", default="1,5",
                    help="`--mode refs` 에서 `--n-refs` 를 흔들 값(쉼표). 기본 참조 세트 위에서만 돈다. "
                         "빈 문자열이면 끈다")
    ap.add_argument("--limit-frames", type=int, default=0,
                    help="앞 N 장만 돌린다(빠른 시험). `<out>/_in_firstN/` 에 심링크 부분집합을 만들어 "
                         "거기를 입력으로 쓴다. 🔴 10장 미만이면 좌우 일관성 판정이 «유보» 다")
    ap.add_argument("--overlay-frames", type=int, default=4, help="오버레이 시트에 넣을 프레임 수")
    ap.add_argument("--diag-all", action="store_true",
                    help="진단 시트를 **모든 프레임**에 대해 개별 장으로 쓴다 (기본은 시트에 든 것만)")
    ap.add_argument("--overlay-mask-alpha", type=float, default=0.22,
                    help="0 이면 마스크를 안 깐다 — 실물 테두리를 가리지 않고 보고 싶을 때")
    ap.add_argument("--only", default=None, help="쉼표로 구분한 스텝 id 만 실행 (예: A1,A2a,lr_A1)")
    ap.add_argument("--force", action="store_true", help="산출물이 있어도 다시 돌린다")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--allow-cpu", action="store_true",
                    help="env.sh 없이 CPU 폴백으로 돌리는 것을 허용 (수십 배 느리다)")
    a = ap.parse_args(argv)

    if a.list_modes:
        print("모드 (쉼표로 겹칠 수 있다 — 예 `--mode contour,init`)\n")
        print(f"  {'이름':10s} {'추가 팔':>7s} {'20프레임 추가비용':>18s}  무엇을 여는가")
        for k, m in MODES.items():
            print(f"  {k:10s} {m['arms']:>7s} {m['cost']:>18s}  {m['what']}")
        print("\n🔴 팔을 늘리는 것은 «후보 탐색» 이지 «성능 향상» 이 아니다. n=20 에서 팔 20개를 돌리고\n"
              "   «가장 좋아 보이는 것» 을 고르면 대개 잡음이다 — **사전 정의 규칙**(이동량 ≥10mm 등)이\n"
              "   사후 선택보다 항상 낫다. 리포트가 팔 수 × 표본 수로 경고를 낸다.")
        return 0

    a.mode = [m.strip() for m in a.mode.split(",") if m.strip()]
    if "all" in a.mode:
        a.mode = [k for k in MODES if k not in ("all", "quick")]
        # 🔴 **«all» 은 경로도 전부여야 한다.** I그룹(ISM)·T그룹(텍스트)은 `--mode` 가 아니라
        #    별도 플래그라, 안 켜면 `--mode all` 인데 **경로 둘이 통째로 빠진다**(팔 30 → 24).
        #    이름이 약속을 안 지키는 것이므로 여기서 켜고 **반드시 알린다**(조용히 바꾸지 않는다).
        for f, lab in (("ism", "--ism (I그룹)"), ("sam3_text", "--sam3-text (T그룹)")):
            if not getattr(a, f):
                setattr(a, f, True)
                print(f"    · `--mode all` → **{lab} 를 켠다** (all 은 경로도 전부라는 뜻이다)",
                      flush=True)
    elif "wide" in a.mode and not (a.ism and a.sam3_text):
        off = [x for x, on in (("--ism", a.ism), ("--sam3-text", a.sam3_text)) if not on]
        print(f"    ⚠️ `--mode wide` 인데 {', '.join(off)} 가 꺼져 있다 — 경로 대조군이 빠진다. "
              f"의도한 게 아니면 같이 켤 것(추가 촬영 0)", flush=True)
    if "wide" in a.mode:
        # ⚠️ `refs` 는 **뺀다** — 참조 스윕만 분할·FP 를 통째로 다시 돌아 비용이 자릿수로 다르고
        #    («팔당 36초» × 최대 5개), 게다가 **초기값이 달라지는 비교**라 성격이 다르다(교훈 #82).
        #    필요하면 명시적으로 `--mode wide,refs` 라고 쓴다.
        a.mode += ["contour", "init", "cascade", "select", "edge"]
    # 옛 이름 호환 — `primary` → `select`. 🔴 조용히 바꾸지 않고 **알리고** 바꾼다(교훈 #21).
    #    `bad` 계산 **전**에 해야 «모르는 모드» 로 걸려 죽지 않는다.
    if "primary" in a.mode:
        a.mode = ["select" if m == "primary" else m for m in a.mode]
        print("    ⚠️ `--mode primary` 는 **`select` 로 이름이 바뀌었다** — 그 팔은 «A 경로» 가 "
              "아니라 «ISM full + select exemplar» 였다(§35-2p-7). 계속 진행한다", flush=True)
    bad = [m for m in a.mode if m not in MODES]
    if bad:
        # 🔴 조용히 무시하지 않는다 — 오타 하나로 «넓혔다고 믿는 좁은 런» 이 나온다.
        print(f"❌ 모르는 모드: {bad}. 가능한 값: {', '.join(MODES)}  (`--list-modes` 참고)")
        return 2
    if "select" in a.mode:
        print("    ⚠️ `select` 모드(`IX1`)는 `seg_full`(ISM) 마스크를 쓴다 — **`I1` 과 선택 규칙만 "
              "다르다.** 방해물이 없으면 두 팔이 같은 결과인 것이 정상이다", flush=True)

    # ── `--mode refs` 의 스윕 목록을 여기서 확정한다 (build_steps 는 결과만 받는다) ──────────
    a.refs_sweep_list, a.refs_sweep_n = [], []
    if "refs" in a.mode:
        if a.refs_sweep:
            want = [x.strip() for x in a.refs_sweep.split(",") if x.strip()]
        else:
            # ★ 같은 **외관**의 모든 거리대를 자동으로 잡는다 — 거리는 «모르는 것» 이고
            #   외관은 «눈으로 아는 것» 이라, 자동으로 열 축은 거리 쪽이 맞다.
            app = next((k for k in ("black", "orange", "clear", "mixed")
                        if a.preset.endswith(k)), None)
            if app is None:
                print(f"❌ `--preset {a.preset}` 은 외관 접미사가 없어 스윕을 자동으로 못 만든다. "
                      f"`--refs-sweep` 으로 직접 줄 것", file=sys.stderr)
                return 2
            want = [f"n{cm}{app}" for cm in _BANDS]
        unknown = [w for w in want if w not in REFS_BY_PRESET]
        if unknown:
            print(f"❌ 모르는 프리셋: {unknown}  (`--list-presets` 참고)", file=sys.stderr)
            return 2
        # 🔴 **없는 디렉토리는 여기서 거부한다** — 참조가 없으면 SAM3 가 «검출 0» 으로 조용히
        #    끝나서 «그 거리대가 나쁘다» 로 오독된다(교훈 #22 의 스윕판).
        missing = [w for w in want if not (VISION / a.obj / REFS_BY_PRESET[w][0]).is_dir()]
        if missing:
            print(f"❌ 참조 세트가 없는 프리셋: {missing}\n"
                  f"   `--list-presets` 로 확인하거나 `--refs-sweep` 에서 뺄 것", file=sys.stderr)
            return 2
        base = a.preset
        a.refs_sweep_list = [w for w in want if w != base]      # 기본 preset 은 A1 이 이미 담당
        a.refs_sweep_n = [int(x) for x in a.refs_sweep_nrefs.split(",")
                          if x.strip().isdigit() and int(x) != a.n_refs]
        print(f"    · refs 스윕: {len(a.refs_sweep_list)}개 프리셋 "
              f"({', '.join(a.refs_sweep_list) or '없음'})"
              + (f" · n-refs {a.refs_sweep_n}" if a.refs_sweep_n else ""), flush=True)

    if a.list_presets:
        print(f"{'preset':14s}{'참조 디렉토리':44s}{'있음':5s} 설명")
        for k, (name, desc) in REFS_BY_PRESET.items():
            ok = (VISION / a.obj / name).is_dir()
            print(f"{k:14s}{name:44s}{'✅' if ok else '❌':5s} {desc}")
        return 0

    missing = [n for n, val in (("--in", a.in_dir), ("--out", a.out)) if not val]
    if missing:
        ap.error(f"다음 인자가 필요하다: {', '.join(missing)}  (목록만 보려면 --list-presets)")

    # ★ 혼합 세트는 **참조마다 독립 질의**여야 한다 — `chain` 은 박스가 ref_0 에만 걸려
    #   («혼합» 이 아니라 «ref_0 세트») 가 된다. 조용히 틀리느니 여기서 바꾸고 알린다.
    if a.preset.endswith("mixed") and a.refs_mode == "chain":
        a.refs_mode = "independent"
        print("⚠️ mixed 프리셋 → --refs-mode 를 independent 로 자동 전환한다 "
              "(chain 은 박스가 ref_0 에만 걸린다)")

    # cwd 가 어디든 같게 동작해야 한다 — 스테이지는 cwd=VISION 으로 부르므로 여기서 절대화한다
    in_dir = Path(a.in_dir)
    if not in_dir.is_absolute():
        in_dir = VISION / in_dir
    a.in_dir = str(in_dir)
    out_dir = Path(a.out)
    a.out = str(out_dir if out_dir.is_absolute() else VISION / out_dir)

    # 🔴 참조가 없으면 SAM3 가 **검출 0 으로 조용히 끝난다** — 여기서 죽는 게 낫다
    refs_dir = VISION / a.obj / (a.refs or REFS_BY_PRESET[a.preset][0])
    if not refs_dir.is_dir():
        print(f"❌ 참조 세트가 없다: {refs_dir}\n"
              f"   `--list-presets` 로 있는 것을 확인하거나 RESULTS.md §35-2f 「재현」 으로 만들 것",
              file=sys.stderr)
        return 2

    frames = sorted([p for p in in_dir.glob("frame_*") if (p / "left.png").exists()])
    if not frames:
        print(f"❌ `{in_dir}/frame_XXXX/left.png` 가 없다.\n"
              f"   tools/make_frame_from_zed.py --left L.png --right R.png \\\n"
              f"       --cam assets/cam/zedx_s48560070_hd1200.json --out {in_dir}/frame_0000",
              file=sys.stderr)
        return 2
    for f in frames:                       # 조용히 틀리는 것보다 여기서 죽는 게 낫다
        missing = [n for n in ("right.png", "cam.json") if not (f / n).exists()]
        if missing:
            print(f"❌ {f.name}: {', '.join(missing)} 없음", file=sys.stderr)
            return 2

    # ★ `--limit-frames N` — 앞 N 장만 돌린다(빠른 시험용).
    #   🔴 러너의 `frames` 만 자르면 안 된다 — **스테이지는 `--in` 디렉토리를 통째로 돈다.**
    #   그래서 심링크 부분집합 디렉토리를 만들고 `--in` 을 그리로 돌린다(복사가 아니라 디스크 0).
    #   ⚠️ 스테이지는 `--in` 에 쓰지 않고 전부 `--out` 에만 쓴다 — 그래서 심링크가 안전하다.
    if a.limit_frames and a.limit_frames < len(frames):
        sub = Path(a.out) / f"_in_first{a.limit_frames}"
        sub.mkdir(parents=True, exist_ok=True)
        for f in frames[:a.limit_frames]:
            link = sub / f.name
            if not link.exists():
                link.symlink_to(f.resolve(), target_is_directory=True)
        # 남아 있던 잉여 링크는 지운다(N 을 줄여서 재실행한 경우)
        keep = {f.name for f in frames[:a.limit_frames]}
        for old in sub.iterdir():
            if old.name not in keep and old.is_symlink():
                old.unlink()
        print(f"★ --limit-frames {a.limit_frames} — 전체 {len(frames)}장 중 앞 {a.limit_frames}장만 돈다\n"
              f"  입력을 {sub} (심링크) 로 바꾼다. 🔴 이 런의 모든 산출물은 그 부분집합 기준이다.")
        if a.limit_frames < 10:
            print(f"  ⚠️ 10장 미만이면 좌우 일관성 판정이 «유보» 로 나온다(프레임별 산포에 묻힌다).")
        a.in_dir, in_dir = str(sub), sub
        frames = sorted([p for p in sub.glob("frame_*") if (p / "left.png").exists()])

    # 🔴 **`source envs/env.sh` 를 빼먹으면 조용히 CPU 로 떨어진다.**
    #    ONNX Runtime 은 `libcublasLt.so.12`(= `$CUDA_HOME/lib64`)를 못 찾으면 CUDAExecutionProvider
    #    생성에 실패하고 **경고만 찍은 뒤 CPUExecutionProvider 로 계속 간다.** 결과는 맞는데
    #    스테레오가 수십 배 느려져서 «원래 이만큼 걸리나 보다» 로 넘어가게 된다 — 실제로 그랬다.
    #    ⚠️ 진단이 아니라 **차단**이다: 느린 건 «틀린 것» 은 아니지만 20프레임 × 여러 거리대를
    #    돌릴 때 하루가 날아간다. 정말 CPU 로 돌리려면 `--allow-cpu` 를 준다.
    if not a.report_only:
        cuda_lib = VISION / "envs/cuda/lib64/libcublasLt.so.12"
        ld = os.environ.get("LD_LIBRARY_PATH", "")
        if cuda_lib.exists() and str(VISION / "envs/cuda/lib64") not in ld:
            msg = ("🔴 `LD_LIBRARY_PATH` 에 envs/cuda/lib64 가 없다 — ONNX 가 **조용히 CPU 로 폴백**한다.\n"
                   "   먼저 실행할 것:  source envs/env.sh\n"
                   "   (일부러 CPU 로 돌리려면 --allow-cpu)")
            if not a.allow_cpu:
                print(msg, file=sys.stderr)
                return 2
            print(msg.replace("🔴", "⚠️ (--allow-cpu)"), file=sys.stderr)

    if a.report_only:
        write_run_meta(a, frames)              # 리포트만 다시 낼 때도 메타는 갱신한다
        return report(a)

    steps = build_steps(a)
    if a.only:
        want = {s.strip() for s in a.only.split(",")}
        steps = [s for s in steps if s.sid in want]
        if not steps:
            print(f"❌ --only 에 맞는 스텝이 없다: {a.only}", file=sys.stderr)
            return 2

    print(f"== A그룹 | {time.strftime('%Y-%m-%d %H:%M:%S')} | 프레임 {len(frames)}장 | "
          f"obj {a.obj} | 참조 {a.refs or REFS_BY_PRESET[a.preset][0]} | 게이트 {a.gate_deg}°"
          + (f"\n   메모: {a.note}" if a.note else ""))
    t0 = time.time()
    # ★ **런 시작 시점에 먼저 쓴다** — 중간에 죽어도 «무엇을 돌리려 했는지» 는 남아야 한다.
    if not a.dry_run:
        write_run_meta(a, frames)
    for s in steps:
        if s.done(frames) and not a.force:
            print(f"\n[{s.sid}] {s.desc}  — 산출물 있음, 건너뜀 (--force 로 재실행)")
            continue
        print(f"\n[{s.sid}] {s.desc}")
        rc = sh(s.resolve(), a.dry_run)
        if rc != 0:
            if s.optional:
                print(f"⚠️ [{s.sid}] 실패 (rc={rc}) — **넘어간다**(진단용). "
                      f"본 파이프라인은 계속된다", file=sys.stderr)
                continue
            print(f"❌ [{s.sid}] 실패 (rc={rc}) — 여기서 멈춘다", file=sys.stderr)
            return rc
    print(f"\n== 전체 {time.time()-t0:.1f}s")
    if a.dry_run:
        return 0
    write_run_meta(a, frames, elapsed=time.time() - t0)      # 소요 시간까지 채워 다시 쓴다
    return report(a)


if __name__ == "__main__":
    raise SystemExit(main())
