#!/usr/bin/env python3
"""«좌우 `Δdx` 의 이산 모드가 «지표 인공물» 인가 «pose 결함» 인가» — **sim GT 로 가른다**.

왜 필요한가 (`RESULTS.md §44-6`)
    실물 66cm 에서 `Δdx > +2.5px` 인 프레임이 **하이브리드 5팔에만** 나타나고
    비하이브리드 5팔은 전부 깨끗했다. `RH1.t` 는 `RP1.t` 와 **정의상 소수점까지 같으므로**
    (하이브리드는 `t` 를 `refined` 에서 그대로 가져온다) **원인은 회전뿐**이다.
    그런데 값이 **+3.0~3.7px 로 좁게 뭉친 이산 모드**라, 회전 오차가 매끄럽게 커진 결과가 아니라
    **에지 대응이 옆 특징으로 점프한 것**의 모습이다(§35-2k 의 «예측에 가장 가까운 국소최대» 규칙).

    🔴 이게 **인공물이면 `|Δdx|` 로 낸 팔 서열이 무효**이고, **결함이면 하이브리드가 실제로 나쁘다.**
    실물에는 GT 가 없어 못 가른다. **sim 에는 있다.**

무엇을 하나
    같은 프레임에서 **① `Δdx`(GT-free 지표)** 와 **② GT 대비 실제 회전·평행이동 오차** 를 나란히 놓고,
    «모드에 걸린 프레임» 과 «정상 프레임» 의 **실제 오차가 다른가** 를 검정한다.

        모드 프레임의 GT 오차가 유의하게 크다  → **pose 결함** (지표가 옳다)
        차이가 없다                              → **지표 인공물** (지표를 서열에 쓰면 안 된다)

    ⚠️ 이건 «지표를 검증하는» 절차다 — 횡단 정리 #8(자기순환 금지)에 따라 **판정 기준은 GT** 이고
    지표 자신이 아니다.

사용
    envs/pose/bin/python tools/ddx_mode_check.py --run runs/S44_n70 --in runs/zx_ref_n70_black_cand \\
        --obj assets/obj/foup_300_semi_r2
"""
from __future__ import annotations

import argparse
import json
import sys
from math import comb
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# (라벨, pose 디렉토리, pose 파일, 하이브리드인가)
ARMS = [
    ("RH1", "hyb_combo", "pose_coarse.json", True),
    ("RH2", "hyb_combo2", "pose_coarse.json", True),
    ("RP1", "fp_c075", "pose_refined.json", False),
    ("RP2", "fp_c050", "pose_refined.json", False),
    ("RP3", "fp_chull", "pose_refined.json", False),
]


def mannwhitney_u(a: np.ndarray, b: np.ndarray) -> float:
    """정규근사 Mann-Whitney U 양측 p. 표본이 작아 순위합으로 직접 낸다."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return float("nan")
    allv = np.concatenate([a, b])
    order = allv.argsort()
    ranks = np.empty(len(allv), float)
    ranks[order] = np.arange(1, len(allv) + 1)
    # 동점 평균 순위
    for v in np.unique(allv):
        m = allv == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    u1 = ranks[:n1].sum() - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    # 동점 보정
    _, cnt = np.unique(allv, return_counts=True)
    tie = (cnt ** 3 - cnt).sum()
    n = n1 + n2
    sd = np.sqrt(n1 * n2 / 12 * ((n + 1) - tie / (n * (n - 1)))) if n > 1 else 0.0
    if sd == 0:
        return float("nan")
    z = max(0.0, (abs(u1 - mu) - 0.5) / sd)      # 연속성 보정
    from math import erfc, sqrt
    return float(erfc(z / sqrt(2)))              # 양측 정규 꼬리


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="러너 출력 디렉토리 (lr/ 를 가진 곳)")
    ap.add_argument("--in", dest="in_dir", required=True, help="캡처 디렉토리 (pose_gt.json)")
    ap.add_argument("--obj", default="assets/obj/foup_300_semi_r2")
    ap.add_argument("--thr-px", type=float, default=2.5, help="«모드» 판정 문턱")
    ap.add_argument("--md-out", default=None)
    a = ap.parse_args(argv)

    from spatial_vision.contracts import rotation_angle_deg

    root, cap = Path(a.run), Path(a.in_dir)

    def load_pose(p: Path):
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        # ⚠️ 규약은 `t_mm` 이다(`contracts`). 옛 파일 호환으로 `t` 도 받는다.
        tk = "t_mm" if "t_mm" in d else "t"
        R = np.asarray(d["R"], float).reshape(3, 3)
        t = np.asarray(d[tk], float).reshape(3)
        return R, t

    frames = sorted(x.name for x in cap.glob("frame_*") if (x / "pose_gt.json").exists())
    if not frames:
        print(f"❌ `{cap}` 에 pose_gt.json 이 없다 — sim 캡처여야 한다", file=sys.stderr)
        return 2

    lines: list[str] = []

    def out(s: str = "") -> None:
        print(s)
        lines.append(s)

    out(f"# `Δdx` 이산 모드 판정 — {root.name}  (n={len(frames)}, 문턱 {a.thr_px:+.1f}px)")
    out()
    out("🔴 **판정 기준은 GT 다** — 지표 자신이 아니다(횡단 정리 #8).")
    out()

    rows = []
    for label, pdir, pname, is_hyb in ARMS:
        lr = root / "lr" / f"lr_consistency_{label}.json"
        if not lr.exists():
            out(f"⚠️ `{label}`: `{lr.name}` 없음 — 건너뛴다")
            continue
        per = {r["frame"]: r for r in json.loads(lr.read_text()).get("frames", [])}
        ddx, rerr, terr, tz, fr = [], [], [], [], []
        for f in frames:
            r = per.get(f)
            if not r or "ddx_px" not in r:
                continue
            pr = load_pose(root / pdir / f / pname)
            gt = load_pose(cap / f / "pose_gt.json")
            if pr is None or gt is None:
                continue
            ddx.append(r["ddx_px"])
            rerr.append(rotation_angle_deg(pr[0].T @ gt[0]))
            terr.append(float(np.linalg.norm(pr[1] - gt[1])))
            tz.append(float(pr[1][2] - gt[1][2]))
            fr.append(f)
        if not ddx:
            out(f"⚠️ `{label}`: 짝지을 프레임이 0")
            continue
        ddx = np.array(ddx); rerr = np.array(rerr); terr = np.array(terr); tz = np.array(tz)
        m = ddx > a.thr_px
        rows.append((label, is_hyb, ddx, rerr, terr, tz, m, fr))

    if not rows:
        out("❌ 비교할 팔이 없다")
        return 2

    out("## 1. 팔별 — 모드 발생과 실제 오차")
    out()
    out("| 팔 | 하이브리드 | 모드 프레임 | `Δdx` 중앙 | **GT R 중앙 (모드 / 정상)** | **GT t 중앙 (모드 / 정상)** | R 검정 p |")
    out("|---|:-:|---|---|---|---|---|")
    for label, is_hyb, ddx, rerr, terr, tz, m, fr in rows:
        p = mannwhitney_u(rerr[m], rerr[~m]) if m.any() and (~m).any() else float("nan")
        rm = f"{np.median(rerr[m]):.3f}" if m.any() else "—"
        rn = f"{np.median(rerr[~m]):.3f}" if (~m).any() else "—"
        tm = f"{np.median(terr[m]):.2f}" if m.any() else "—"
        tn = f"{np.median(terr[~m]):.2f}" if (~m).any() else "—"
        out(f"| **{label}** | {'✅' if is_hyb else '❌'} | {int(m.sum())}/{len(ddx)} "
            f"| {np.median(ddx):+.2f} | {rm} / {rn} | {tm} / {tn} "
            f"| {'—' if np.isnan(p) else f'{p:.3f}'} |")
    out()

    # 하이브리드 vs 비하이브리드 모드 발생률
    hy = [r for r in rows if r[1]]
    nh = [r for r in rows if not r[1]]
    if hy and nh:
        kh = sum(int(r[6].sum()) for r in hy); nhh = sum(len(r[2]) for r in hy)
        kn = sum(int(r[6].sum()) for r in nh); nnn = sum(len(r[2]) for r in nh)
        out(f"**모드 발생률** — 하이브리드 **{kh}/{nhh} ({kh/max(nhh,1):.1%})** "
            f"vs 비하이브리드 **{kn}/{nnn} ({kn/max(nnn,1):.1%})**")
        out()

    out("## 2. 🔴 판정")
    out()
    verdicts = []
    for label, is_hyb, ddx, rerr, terr, tz, m, fr in rows:
        if not m.any() or not (~m).any():
            continue
        p = mannwhitney_u(rerr[m], rerr[~m])
        d = np.median(rerr[m]) - np.median(rerr[~m])
        verdicts.append((label, p, d, int(m.sum()), len(ddx)))
    if not verdicts:
        out("⚠️ **어느 팔에서도 모드가 안 나타났다** — 이 sim 조건은 실물 66cm 를 재현하지 못한다.")
        out("→ 조건을 맞춰야 한다: **검정 몸체 · 거리 0.66m · 융기 있는 자산(`_r2`)**. 셋 다 맞는지 확인할 것.")
    else:
        sig = [v for v in verdicts if v[1] < 0.05 and v[2] > 0]
        if sig:
            out(f"✅ **pose 결함 쪽** — {len(sig)}/{len(verdicts)} 팔에서 모드 프레임의 GT 회전 오차가 "
                f"유의하게 크다: " + ", ".join(f"`{l}` p={p:.3f} (Δ{d:+.3f}°)" for l, p, d, _, _ in sig))
            out()
            out("→ `|Δdx|` 는 **실제 오차를 보고 있다.** 서열 지표로 유효하고, 하이브리드가 그 축에서 진다.")
        else:
            out(f"🔴 **지표 인공물 쪽** — {len(verdicts)} 팔 어디서도 모드 프레임의 GT 회전 오차가 "
                f"유의하게 크지 않다: " + ", ".join(f"`{l}` p={p:.3f} (Δ{d:+.3f}°)" for l, p, d, _, _ in verdicts))
            out()
            out("→ 🔴 **`|Δdx|` 의 이산 모드를 팔 서열에 쓰면 안 된다.** 그 축에서의 «CHULL 우위» 는 근거를 잃는다.")
    out()
    out("⚠️ **한계** — sim 이라 실텍스처·실조명이 없다. «모드가 안 나타났다» 는 «인공물이 아니다» 가 "
        "아니라 «이 조건에서는 재현 안 됨» 이다(교훈 #33).")

    if a.md_out:
        Path(a.md_out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n→ {Path(a.md_out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
