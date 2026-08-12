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

    전부 `--gate-deg 1.5`. 그리고 다섯 결과에 **좌우 투영 일관성**(`eval.lr_consistency`)을 건다.

🔴 실환경에는 GT 가 없다 — 리포트는 **GT-free 지표만** 낸다
    ① **게이트 후퇴율**  — 폭주 여부. 홀 전략 셋을 비교하면 *"CAD 홀이 실물과 맞는가"* 가 나온다(§28-5)
    ② **좌우 투영 일관성** — 왼쪽만 보고 정합한 pose 를 오른쪽에 투영해 채점. A3 판정의 유일한 근거
    ③ **대응점 수·rms·이동량** — 신호가 실제로 있었는지
    절대 오차(mm·도)는 실물에서 **잴 수 없다.** 리포트에 R/t 오차가 없는 것은 버그가 아니다.

⚠️ 프레임 레이아웃은 `<in>/frame_XXXX/` 여야 한다
    `tools/make_frame_from_zed.py --out runs/real01/frame_0000` 이 그렇게 만든다.
    단일 프레임 디렉토리를 바로 주면 `pose_fp --depth-dir` 의 경로 규약과 어긋나
    **조용히 틀린 depth 를 읽는다** — 그래서 여기서 막는다.

⚠️ 인터프리터는 `envs/pose/bin/python` 이다 (numpy·cv2 를 쓴다).
   스테이지 자체는 각자의 venv 를 subprocess 로 부르므로 venv 를 활성화하면 안 된다.
"""
from __future__ import annotations

import argparse
import json
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
    "pose": VISION / "envs/pose/bin/python",
}
STEREO_MODEL = "weights/ngc_foundationstereo/deployable_foundation_stereo_s_dynamic_v2.0.onnx"

# 거리대 → SAM3 참조. 🔴 참조는 **거리 종속**이라 틀리면 IoU 가 조용히 무너진다(§34-6).
REFS_BY_PRESET = {
    "n20": ("sam3_refs_flange_n20", "0.18~0.24m"),
    "n25": ("sam3_refs_flange_n25", "0.22~0.30m  ← 배포 권장"),
    "n30": ("sam3_refs_flange_n30", "0.28~0.35m"),
}
# §34-9 — 이 거리대에서 flange 등가지름이 이 근처여야 정합 이득이 난다(0.82× ↔ 1.66× 를 가른 값)
TARGET_FLANGE_PX = 419.0


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
                 per_frame: bool = False):
        self.sid, self.desc, self.cmd, self.out = sid, desc, cmd, out
        self.sentinel, self.per_frame = sentinel, per_frame

    def done(self, frames: list[Path]) -> bool:
        if self.per_frame:
            return bool(frames) and all((self.out / f.name / self.sentinel).exists()
                                        for f in frames)
        return (self.out / self.sentinel).exists()


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
        Step("fp_ns2", "FoundationPose --no-stage2 (배포본 초기값)",
             [PY["pose"], "-m", "spatial_vision.stages.pose_fp",
              "--in", a.in_dir, "--out", ns2, "--no-stage2"] + fp_common,
             ns2, "meta_pose.json"),
        Step("fp_s2", "FoundationPose stage2 on (A4 대조군)",
             [PY["pose"], "-m", "spatial_vision.stages.pose_fp",
              "--in", a.in_dir, "--out", s2] + fp_common,
             s2, "meta_pose.json"),
    ]

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
    for sid, desc, pdir, pname, extra in arms:
        d = Path(a.out) / sid
        steps.append(Step(sid, desc,
                          [PY["pose"], "-m", "spatial_vision.stages.refine_contour",
                           "--in", a.in_dir, "--pose-dir", pdir, "--pose-name", pname,
                           "--out", d] + rc_common + extra,
                          d, "meta_contour.json"))

    # 좌우 투영 일관성 — 전부 **같은 잣대**(외곽 실루엣)로 채점한다
    lr = [("A3", ns2, "pose_coarse.json")] + [(sid, Path(a.out) / sid, "pose_refined.json")
                                              for sid, *_ in arms]
    for sid, pdir, pname in lr:
        steps.append(Step(f"lr_{sid}", f"좌우 투영 일관성 · {sid}",
                          [PY["pose"], "-m", "spatial_vision.eval.lr_consistency",
                           "--in", a.in_dir, "--pose-dir", pdir, "--pose-name", pname,
                           "--obj", obj, "--outer-only",
                           "--out", Path(a.out) / "lr", "--tag", sid],
                          Path(a.out) / "lr", f"lr_consistency_{sid}.json"))
    return steps


# ─────────────────────────────────────────────────────────────── 리포트

def _med(v):
    return float(np.median(v)) if len(v) else float("nan")


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
        pj = ns2 / f.name / "pose_coarse.json"
        if pj.exists():
            r["z_mm"] = round(float(json.loads(pj.read_text())["t_mm"][2]), 1)
        rows.append(r)

    def col(k):
        return [r[k] for r in rows if r.get(k) is not None]

    return {"n_frames": len(rows),
            "median": {k: round(_med(col(k)), 4) for k in
                       ("valid_all", "valid_flange", "valid_ring",
                        "flange_dia_px", "z_mm") if col(k)},
            "frames": rows}


def read_variant(root: Path, sid: str) -> dict:
    """정합 변형 하나의 GT-free 요약."""
    out = {"id": sid}
    mc = root / sid / "meta_contour.json"
    if mc.exists():
        m = json.loads(mc.read_text())
        fr = m["frames"]
        n = len(fr)
        out |= {
            "n": n,
            "gated": m["n_gated"],
            "gated_pct": round(100.0 * m["n_gated"] / max(n, 1), 1),
            "n_corr": int(_med([r["n_corr"] for r in fr])),
            "rms_px": round(_med([r["rms_px"] for r in fr if r["rms_px"] is not None]), 3),
            "moved_deg_med": round(_med([r["moved_deg"] for r in fr]), 3),
            "moved_deg_max": round(max((r["moved_deg"] for r in fr), default=float("nan")), 3),
            "moved_mm_med": round(_med([r["moved_mm"] for r in fr]), 3),
            "sec": m["sec"],
        }
    lr = root / "lr" / f"lr_consistency_{sid}.json"
    if lr.exists():
        a = json.loads(lr.read_text())["abs_median"]
        out |= {"lr_dxR": a["dx_R"], "lr_ddx": a["ddx_px"], "lr_dz": a["dz_mm"]}
    return out


def verdicts(v: dict[str, dict], diag: dict) -> list[str]:
    """측정값 → **처방**. 규칙은 전부 문서에 근거가 있고 GT 를 쓰지 않는다."""
    out = []
    med = diag.get("median", {})

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

    if diag.get("n_frames", 0) < 20:
        out.append(f"⚠️ **표본 {diag.get('n_frames')}장** — 꼬리로 우열을 가리기엔 부족하다"
                   f"(교훈 #58: n=40 무결점이 n=120 에서 110/120 이었다). "
                   f"연속 촬영은 손으로도 싸다 — **20~40장** 찍어 두면 반복도까지 같이 나온다.")
    return out


def report(a) -> int:
    root = Path(a.out)
    in_dir = Path(a.in_dir)
    diag = capture_diag(in_dir, root / "st", root / "seg", root / "fp_ns2")
    ids = ["A1", "A2a", "A2b", "A4"]
    v = {sid: read_variant(root, sid) for sid in ids}
    v["A3"] = read_variant(root, "A3")                       # 정합 없음 — lr 만 있다
    labels = {"A1": "A1 홀 제외 (배포본)", "A2a": "A2a 홀 윤곽 (규격부)",
              "A2b": "A2b 홀 중심", "A3": "A3 정합 off (FP 단독)", "A4": "A4 refine 초기값"}

    L = []
    L.append(f"# A그룹 결과 — `{in_dir}`\n")
    L.append(f"프레임 {diag['n_frames']}장 · obj `{a.obj}` · 참조 "
             f"`{a.refs or REFS_BY_PRESET[a.preset][0]}` · 게이트 {a.gate_deg}°\n")
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
        L.append(f"| FP 추정 거리 | **{m['z_mm']:.0f}mm** | 최적 220~300mm (§34-9) |")
    for k, lab, ref in (("valid_all", "depth 유효율 (전체)", "—"),
                        ("valid_flange", "depth 유효율 (flange)", "검정 불투명 — 높아야 정상"),
                        ("valid_ring", "depth 유효율 (주변 링)", "🔴 **반투명 본체 판정**")):
        if k in m:
            L.append(f"| {lab} | **{m[k]*100:.1f}%** | {ref} |")
    L.append("")

    L.append("## 변형 비교 (GT-free)\n")
    L.append("| 변형 | 게이트 후퇴 | 대응점 | rms px | 이동 ° 중앙/최대 | 좌우 \\|Δdx\\| px | 좌우 dz mm |")
    L.append("|---|---|---|---|---|---|---|")
    for sid in ["A3", "A1", "A2a", "A2b", "A4"]:
        r = v.get(sid, {})
        gp = f"{r['gated']}/{r['n']} ({r['gated_pct']}%)" if "gated" in r else "—"
        mv = f"{r['moved_deg_med']:.2f} / {r['moved_deg_max']:.2f}" if "moved_deg_med" in r else "—"
        L.append(f"| {labels[sid]} | {gp} | {r.get('n_corr', '—')} | "
                 f"{r.get('rms_px', '—')} | {mv} | "
                 f"**{r.get('lr_ddx', '—')}** | {r.get('lr_dz', '—')} |")
    L.append("")
    L.append("- **게이트 후퇴** = 정합이 초기값에서 1.5° 넘게 움직여 결과를 버린 프레임 수. "
             "높으면 «정합이 폭주했거나 CAD 가 실물과 다르다».")
    L.append("- **좌우 |Δdx|** = 왼쪽만 보고 정합한 pose 를 오른쪽에 투영했을 때 남는 어긋남. "
             "**작을수록 좋다.** 절대값이 아니라 변형 간 차이로만 읽는다.")
    L.append("- 좌우 **dz** 는 그 어긋남을 깊이로 환산한 값 — 기준선 편향이 있어 "
             "0 이 아닌 게 정상이다.\n")

    L.append("## 판정\n")
    for s in verdicts(v, diag):
        L.append(f"- {s}")
    L.append("")

    L.append("## 눈으로 볼 것\n")
    L.append(f"- depth 유효 마스크 — `{root/'st'}/frame_*/valid.png`  🔴 열린 항목 #1")
    L.append(f"- flange 마스크 — `{root/'seg'}/frame_*/mask_flange.png`")
    L.append(f"- FP 오버레이 — `{root/'fp_ns2'}/frame_*/`")
    L.append(f"- 정합 디버그 — `--debug` 로 다시 돌리면 `{root}/A1/frame_*/contour_debug.png`")
    L.append(f"- 최종 pose — `{root}/A1/frame_*/pose_refined.json`\n")

    txt = "\n".join(L)
    (root / "report.md").write_text(txt)
    (root / "report.json").write_text(json.dumps(
        {"in": str(in_dir), "obj": a.obj, "gate_deg": a.gate_deg,
         "refs": a.refs or REFS_BY_PRESET[a.preset][0],
         "capture": diag, "variants": v}, indent=2, ensure_ascii=False))
    print("\n" + txt)
    print(f"→ {root/'report.md'} · {root/'report.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A그룹 원샷 러너 (근접 촬영 1벌 → A1~A4)")
    ap.add_argument("--in", dest="in_dir", required=True, help="<dir>/frame_XXXX/{left,right,cam}")
    ap.add_argument("--out", required=True)
    ap.add_argument("--obj", default="assets/obj/foup_300_semi_r2")
    ap.add_argument("--preset", default="n25", choices=list(REFS_BY_PRESET),
                    help="촬영 거리대 → SAM3 참조 (" +
                         " · ".join(f"{k} {d}" for k, (_, d) in REFS_BY_PRESET.items()) + ")")
    ap.add_argument("--refs", default=None, help="참조 디렉토리 이름을 직접 지정 (--preset 무시)")
    ap.add_argument("--n-refs", type=int, default=3)
    ap.add_argument("--refs-mode", default="chain", choices=["chain", "independent"])
    ap.add_argument("--use-prompts-file", action="store_true",
                    help="객체의 sam3_prompts.json 을 쓴다. ⚠️ 기본값(끔)이 §34 sim 재현과 같다")
    ap.add_argument("--stereo-scale", type=float, default=0.5)
    ap.add_argument("--input-scale", type=float, default=0.5, help="🔴 1.0 은 OOM (§34-12)")
    ap.add_argument("--gate-deg", type=float, default=1.5)
    ap.add_argument("--fix-z", action="store_true",
                    help="§23 — depth 가 깨끗하면 켠다. 실물 depth 품질을 모르므로 기본은 끔")
    ap.add_argument("--only", default=None, help="쉼표로 구분한 스텝 id 만 실행 (예: A1,A2a,lr_A1)")
    ap.add_argument("--force", action="store_true", help="산출물이 있어도 다시 돌린다")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args(argv)

    # cwd 가 어디든 같게 동작해야 한다 — 스테이지는 cwd=VISION 으로 부르므로 여기서 절대화한다
    in_dir = Path(a.in_dir)
    if not in_dir.is_absolute():
        in_dir = VISION / in_dir
    a.in_dir = str(in_dir)
    out_dir = Path(a.out)
    a.out = str(out_dir if out_dir.is_absolute() else VISION / out_dir)

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

    if a.report_only:
        return report(a)

    steps = build_steps(a)
    if a.only:
        want = {s.strip() for s in a.only.split(",")}
        steps = [s for s in steps if s.sid in want]
        if not steps:
            print(f"❌ --only 에 맞는 스텝이 없다: {a.only}", file=sys.stderr)
            return 2

    print(f"== A그룹 | 프레임 {len(frames)}장 | obj {a.obj} | "
          f"참조 {a.refs or REFS_BY_PRESET[a.preset][0]} | 게이트 {a.gate_deg}°")
    t0 = time.time()
    for s in steps:
        if s.done(frames) and not a.force:
            print(f"\n[{s.sid}] {s.desc}  — 산출물 있음, 건너뜀 (--force 로 재실행)")
            continue
        print(f"\n[{s.sid}] {s.desc}")
        rc = sh(s.cmd, a.dry_run)
        if rc != 0:
            print(f"❌ [{s.sid}] 실패 (rc={rc}) — 여기서 멈춘다", file=sys.stderr)
            return rc
    print(f"\n== 전체 {time.time()-t0:.1f}s")
    return 0 if a.dry_run else report(a)


if __name__ == "__main__":
    raise SystemExit(main())
