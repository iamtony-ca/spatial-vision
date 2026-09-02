#!/usr/bin/env python3
"""노브 스윕을 **GT 로** 채점한다 — `--refine-iter`·`--stereo-scale` 처럼 «값의 근거» 가 없던 것들.

왜 이 도구가 따로 있나
    🔴 **FP 는 비결정이다**(교훈 #24·#107). 설정 하나당 런 하나로 비교하면 **설정 효과가 아니라
    RNG 를 재게 된다** — §44-2a 에서 «같은 설정 두 런이 서로소 실패집합» 이 실제로 나왔다.
    그래서 이 도구는 **설정당 반복 런 여러 개를 받아**
      ① 프레임별로 **반복 중앙값**을 취해 RNG 를 누르고
      ② 그 위에서 **짝지은 부호검정**(프레임 1:1)으로 설정끼리 비교한다.
    ★ 그리고 **반복 사이의 산포(= 잡음 바닥)를 같이 낸다** — 설정 차이가 그보다 작으면 «구분 안 됨» 이다.

무엇을 채점하나
    `pose_refined.json` (그 노브가 직접 건드리는 것) 과
    **하이브리드**(R=`pose_coarse` · t=`pose_refined`, §27-7) — 배포 팔 `RH1` 이 이것이다.

사용
    envs/pose/bin/python tools/knob_sweep_eval.py --in runs/zx_ref_n70_black_cand \\
        --group "refine-iter=2:runs/S44_ri2_r1,runs/S44_ri2_r2,runs/S44_ri2_r3" \\
        --group "refine-iter=5:runs/S44_ri5_r1,runs/S44_ri5_r2,runs/S44_ri5_r3" \\
        --group "refine-iter=10:runs/S44_ri10_r1,runs/S44_ri10_r2,runs/S44_ri10_r3" \\
        --md-out docs/_knob_refine_iter.md
"""
from __future__ import annotations

import argparse
import json
import sys
from math import comb
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def sign_p(k: int, n: int) -> float:
    """짝지은 부호검정 양측 p. 동률은 호출부에서 제외하고 넘긴다."""
    if n == 0:
        return float("nan")
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(k, n - k) + 1)) / 2 ** n)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="in_dir", required=True, help="캡처 (pose_gt.json)")
    ap.add_argument("--group", action="append", required=True,
                    help="'라벨:런1,런2,…' — 같은 설정의 반복 런들")
    ap.add_argument("--kpi-t", type=float, default=5.0)
    ap.add_argument("--kpi-r", type=float, default=3.0)
    ap.add_argument("--md-out", default=None)
    a = ap.parse_args(argv)

    from spatial_vision.contracts import rotation_angle_deg

    cap = Path(a.in_dir)
    frames = sorted(x.name for x in cap.glob("frame_*") if (x / "pose_gt.json").exists())
    if not frames:
        print(f"❌ `{cap}` 에 GT 가 없다", file=sys.stderr)
        return 2

    def pose(p: Path):
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        k = "t_mm" if "t_mm" in d else "t"
        return np.asarray(d["R"], float).reshape(3, 3), np.asarray(d[k], float).reshape(3)

    lines: list[str] = []

    def out(s: str = "") -> None:
        print(s)
        lines.append(s)

    groups: dict[str, list[Path]] = {}
    for g in a.group:
        lab, _, runs = g.partition(":")
        groups[lab] = [Path(x) for x in runs.split(",") if x]

    # errs[label][variant] = (n_rep, n_frame) 배열
    errs: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = {}
    for lab, runs in groups.items():
        R_ref, T_ref, R_hyb, T_hyb = [], [], [], []
        for rd in runs:
            rr, tt, rh, th = [], [], [], []
            for f in frames:
                gt = pose(cap / f / "pose_gt.json")
                pr = pose(rd / f / "pose_refined.json")
                pc = pose(rd / f / "pose_coarse.json")
                if gt is None or pr is None or pc is None:
                    rr.append(np.nan); tt.append(np.nan); rh.append(np.nan); th.append(np.nan)
                    continue
                rr.append(rotation_angle_deg(pr[0].T @ gt[0]))
                tt.append(float(np.linalg.norm(pr[1] - gt[1])))
                rh.append(rotation_angle_deg(pc[0].T @ gt[0]))   # 하이브리드 R = coarse
                th.append(float(np.linalg.norm(pr[1] - gt[1])))  # 하이브리드 t = refined
            R_ref.append(rr); T_ref.append(tt); R_hyb.append(rh); T_hyb.append(th)
        errs[lab] = {"refined": (np.array(R_ref), np.array(T_ref)),
                     "hybrid": (np.array(R_hyb), np.array(T_hyb))}

    out(f"# 노브 스윕 GT 채점 — n={len(frames)} 프레임 · 설정 {len(groups)}개")
    out()
    out("🔴 **FP 는 비결정이다** — 설정당 반복 런의 **프레임별 중앙값**으로 RNG 를 누르고, "
        "**반복 사이 산포**를 잡음 바닥으로 같이 낸다(교훈 #24·#107).")
    out()

    for variant in ("refined", "hybrid"):
        out(f"## `{variant}` " + ("(= 그 노브가 직접 건드리는 산출물)" if variant == "refined"
                                  else "(= 배포 팔 `RH1`: R=coarse · t=refined)"))
        out()
        out("| 설정 | 반복 | R 중앙 | R p90 | R 최대 | t 중앙 | t 최대 | KPI | **반복 산포** R / t |")
        out("|---|:-:|---|---|---|---|---|---|---|")
        med: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for lab in groups:
            R, T = errs[lab][variant]
            rm, tm = np.nanmedian(R, axis=0), np.nanmedian(T, axis=0)
            med[lab] = (rm, tm)
            ok = np.isfinite(rm) & np.isfinite(tm)
            kpi = int(((tm[ok] <= a.kpi_t) & (rm[ok] <= a.kpi_r)).sum())
            # 반복 산포 = 같은 프레임에 대한 반복 간 (최대−최소) 의 중앙값
            sr = float(np.nanmedian(np.nanmax(R, 0) - np.nanmin(R, 0))) if R.shape[0] > 1 else float("nan")
            st = float(np.nanmedian(np.nanmax(T, 0) - np.nanmin(T, 0))) if T.shape[0] > 1 else float("nan")
            out(f"| **{lab}** | {R.shape[0]} | {np.nanmedian(rm):.3f} | {np.nanpercentile(rm,90):.3f} "
                f"| {np.nanmax(rm):.3f} | {np.nanmedian(tm):.3f} | {np.nanmax(tm):.3f} "
                f"| {kpi}/{int(ok.sum())} | {sr:.3f}° / {st:.3f}mm |")
        out()
        labs = list(groups)
        out("**짝지은 부호검정** (프레임별 반복 중앙값끼리, 동률 제외)")
        out()
        out("```")
        for i in range(len(labs)):
            for j in range(i + 1, len(labs)):
                A, B = labs[i], labs[j]
                for key, unit, idx in (("R", "°", 0), ("t", "mm", 1)):
                    x, y = med[A][idx], med[B][idx]
                    m = np.isfinite(x) & np.isfinite(y) & (x != y)
                    n = int(m.sum()); k = int((x[m] < y[m]).sum())
                    d = float(np.median(x[m] - y[m])) if n else float("nan")
                    tie = int((np.isfinite(x) & np.isfinite(y) & (x == y)).sum())
                    p = sign_p(k, n)
                    mark = " ✅" if p < 0.05 else ""
                    out(f"  {key:1s}  {A} < {B}: {k}/{n}  중앙차 {d:+.3f}{unit}  "
                        f"p={p:.4f}{mark}" + (f"  (동률 {tie})" if tie else ""))
        out("```")
        out()

    out("## 🔴 읽는 법")
    out()
    out("- **설정 간 중앙차가 «반복 산포» 보다 작으면 «구분 안 됨»** 이다 — p 값보다 이걸 먼저 본다.")
    out("- `refined` 에서 차이가 나는데 `hybrid` 에서 안 나면, 그 노브는 **회전에만** 영향을 준 것이다"
        "(하이브리드는 회전을 `coarse` 에서 받으므로).")
    out("- 🔴 **«차이 없음» 을 천장에서 관찰하면 안 된다**(교훈 #103) — KPI 가 전부 만점이면 "
        "KPI 로는 못 가르고 R·t 분포를 봐야 한다.")

    if a.md_out:
        Path(a.md_out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n→ {Path(a.md_out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
