#!/usr/bin/env python3
"""sim GT 로 팔을 **서열화**하고, **GT-free 지표가 그 서열을 맞혔는지** 대조한다.

왜 필요한가
    실환경에는 GT 가 없다 — 그래서 «누가 더 정확한가» 를 못 정한다(§41-12a).
    sim 에는 GT 가 있으니 **진짜 서열**을 낼 수 있는데, 🔴 **sim 서열 자체는 실물로 안 넘어갈 수
    있다**(교훈 #92 · §38-1: sim 참조가 실물에서 전멸했다). 그러면 이 표의 쓸모는 무엇인가?

    ★★ **«GT-free 지표가 진짜 승자를 맞혔는가» 를 재는 것**이다. 그 상관은 실물로 넘어간다 —
    실물에서는 GT-free 지표밖에 못 쓰므로, **그 지표를 얼마나 믿을지**를 여기서 정한다.
    §35-2o-6b 가 좌우 `|Δdx|` 를 r = −0.94 로 잰 것이 그 방식이고, 이 도구는 그것을
    **지금 데이터에서 다시** 낸다.

무엇을 내나
    ① **진짜 서열** — KPI 통과율 → t 중앙 → R 중앙 (GT 대비)
    ② **GT-free 서열** — 좌우 `|Δdx|` 중앙 (`stats/metrics_long.csv`)
    ③ **둘의 Spearman 상관** + 「GT-free 로 1위를 골랐다면 진짜 몇 위였나」

사용
    envs/pose/bin/python tools/rank_sim.py --gt runs/zx_n30 --run runs/SIMRANK
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
PY = HERE / "envs" / "pose" / "bin" / "python"

# (팔, 디렉토리, eval_pose 가 붙이는 단계 이름) — 🔴 팔마다 «자기 결과» 인 단계가 다르다.
#   하이브리드는 `pose_coarse.json` 에 결과를 쓰므로 `coarse` 로 읽어야 한다.
ARMS = [
    ("RH1", "hyb_combo", "coarse"),
    ("RH2", "hyb_combo2", "coarse"),
    ("RP1", "fp_c075", "refined"),
    ("RP2", "fp_c050", "refined"),
    ("RP3", "fp_chull", "refined"),
    ("T3", "fp_txt", "coarse"),
]


def prompt_arms(run: Path) -> list[tuple[str, str, str]]:
    """프롬프트 팔(`--mode prompts`)은 tag 를 미리 못 아니까 디스크에서 찾는다."""
    return [(f"RH1@{d.name[4:]}", d.name, "coarse") for d in sorted(run.glob("hyb_*"))
            if d.name not in ("hyb_combo", "hyb_combo2")]


def gtfree(run: Path) -> dict[str, float]:
    """`stats/metrics_long.csv` 에서 팔별 좌우 `|Δdx|` 중앙값."""
    p = run / "stats" / "metrics_long.csv"
    if not p.exists():
        return {}
    by: dict[str, list[float]] = {}
    with p.open(newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                by.setdefault(r["variant"], []).append(abs(float(r["ddx_px"])))
            except (KeyError, TypeError, ValueError):
                pass
    return {k: float(np.median(v)) for k, v in by.items() if v}


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = (np.argsort(np.argsort(x)).astype(float) for x in (np.array(a), np.array(b)))
    ra, rb = ra - ra.mean(), rb - rb.mean()
    d = float(np.linalg.norm(ra) * np.linalg.norm(rb))
    return float(ra @ rb / d) if d > 1e-12 else float("nan")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt", required=True, help="캡처 디렉토리 (pose_gt.json 보유)")
    ap.add_argument("--run", required=True, help="러너 출력 디렉토리")
    ap.add_argument("--obj", default="assets/obj/foup_300_semi_r2")
    ap.add_argument("--kpi-mm", type=float, default=5.0)
    ap.add_argument("--kpi-deg", type=float, default=3.0)
    ap.add_argument("--misselect-mm", type=float, default=50.0,
                    help="이 값을 넘는 t 오차는 **«오선택»**(다른 물체를 집었다)으로 보고 **따로 센다**. "
                         "🔴 안 걸러내면 오선택이 표를 통째로 덮어 «pose 정확도» 를 못 본다(§42-1) — "
                         "실제로 초판이 그랬다. 0 이면 안 거른다")
    ap.add_argument("--md-out", default=None)
    a = ap.parse_args(argv)

    run = Path(a.run)
    arms = [x for x in ARMS + prompt_arms(run) if (run / x[1]).exists()]
    if not arms:
        print(f"❌ `{run}` 에 채점할 팔이 없다", file=sys.stderr); return 2

    ev = run / "metrics_pose_rank.json"
    cmd = [str(PY), "-m", "spatial_vision.eval.eval_pose", "--gt", a.gt, "--obj", a.obj,
           "--kpi-mm", str(a.kpi_mm), "--kpi-deg", str(a.kpi_deg), "--out", str(ev),
           "--pred"] + [str(run / d) for _, d, _ in arms]
    print(f"★ 채점 — 팔 {len(arms)}개 · GT {a.gt}", flush=True)
    if subprocess.run(cmd, cwd=HERE).returncode:
        return 1
    res = json.loads(ev.read_text())["results"]

    gf = gtfree(run)
    rows = []
    for name, d, stage in arms:
        s = res.get(f"{d}/{stage}")
        if not s:
            print(f"    ⚠️ {name}: `{d}/{stage}` 채점 결과가 없다 — 뺀다")
            continue
        # 🔴 **오선택을 먼저 분리한다.** 다른 물체를 집으면 t 가 수백 mm 라 중앙값·꼬리·KPI 를
        #    통째로 덮는다 — 그러면 «pose 알고리즘 차이» 가 보이지 않는다(§42-1).
        fr = s["frames"]
        mis = [f for f in fr if f["trans_mm"] > a.misselect_mm] if a.misselect_mm else []
        ok = [f for f in fr if f not in mis]
        if not ok:
            print(f"    🔴 {name}: 전 프레임이 오선택이다 — 뺀다"); continue
        rr = np.array([f["rot_deg"] for f in ok]); tt = np.array([f["trans_mm"] for f in ok])
        rows.append({"arm": name, "n": s["n"], "mis": len(mis),
                     "mis_pct": 100.0 * len(mis) / len(fr),
                     "kpi": 100.0 * float(((rr <= a.kpi_deg) & (tt <= a.kpi_mm)).sum()) / len(ok),
                     "r_med": float(np.median(rr)), "r_max": float(rr.max()),
                     "t_med": float(np.median(tt)), "t_max": float(tt.max()),
                     "add": s["stat"]["add_mm"]["median"], "ddx": gf.get(name)})
    if not rows:
        print("❌ 채점된 팔이 없다", file=sys.stderr); return 2

    # 🔴 서열 기준: **오선택률 먼저** → KPI → t 중앙. 오선택은 KPI 를 20%p 씩 깎으므로
    #    «어느 pose 팔이 나은가» 보다 훨씬 크게 작용한다(§42-3).
    rows.sort(key=lambda r: (r["mis_pct"], -r["kpi"], r["t_med"]))
    ns = {r["n"] for r in rows}

    L: list[str] = []

    def say(s: str = "") -> None:
        print(s); L.append(s)

    say(f"\n# sim GT 서열 — `{Path(a.gt).name}` / `{run.name}`  (KPI R ≤{a.kpi_deg}° & t ≤{a.kpi_mm}mm)")
    say("")
    say("🔴 **`오선택`(t 오차 > "
        f"{a.misselect_mm:.0f}mm = 다른 물체를 집었다)을 먼저 분리했다** — 나머지 열은 "
        "**오선택을 뺀 프레임**의 값이다. 안 그러면 오선택이 표를 통째로 덮는다(§42-1).")
    say("")
    say("| # | 팔 | n | **오선택** | **KPI\\*** | R 중앙 | R 최대 | **t 중앙** | t 최대 "
        "| GT-free \\|Δdx\\| |")
    say("|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    for i, r in enumerate(rows, 1):
        say(f"| {i} | `{r['arm']}` | {r['n']} | **{r['mis']} ({r['mis_pct']:.1f}%)** "
            f"| **{r['kpi']:.1f}%** | {r['r_med']:.3f}° | {r['r_max']:.2f}° "
            f"| **{r['t_med']:.3f}** | {r['t_max']:.2f} "
            f"| {'—' if r['ddx'] is None else f'{r ['ddx']:.2f}'} |")
    say("")
    if len(ns) > 1:
        say(f"🔴 **행마다 프레임 수가 다르다** {sorted(ns)} — 나란히 놓을 수 없다(꼬리는 특히).")
    elif min(ns) < 60:
        say(f"⚠️ n={min(ns)} — 무결점이어도 실패율 95% 상한이 {100 * (1 - 0.05 ** (1 / min(ns))):.1f}% 다"
            f"(교훈 #58). **꼬리로 우열을 가르지 말 것.**")

    # ── ★★ 이 도구의 본론: GT-free 지표가 진짜 서열을 맞혔는가 ──────────────────────
    ok = [r for r in rows if r["ddx"] is not None]
    say("")
    say("## ★★ GT-free 지표(`|Δdx|`)가 진짜 서열을 맞혔는가")
    say("")
    if len(ok) < 3:
        say("⚠️ `|Δdx|` 가 있는 팔이 3개 미만이라 상관을 못 낸다.")
    else:
        rho_k = spearman([-r["kpi"] for r in ok], [r["ddx"] for r in ok])
        rho_t = spearman([r["t_med"] for r in ok], [r["ddx"] for r in ok])
        pick = min(ok, key=lambda r: r["ddx"])
        true_rank = [r["arm"] for r in rows].index(pick["arm"]) + 1
        say(f"- **Spearman(|Δdx| ↔ KPI) = {rho_k:+.3f}** · (|Δdx| ↔ t 중앙) = {rho_t:+.3f}  "
            f"(n={len(ok)}팔)")
        say(f"- **GT-free 로 1위를 골랐다면 `{pick['arm']}`** → 진짜 서열 **{true_rank}위** "
            f"(KPI {pick['kpi']:.1f}% · t 중앙 {pick['t_med']:.3f}mm). "
            f"진짜 1위는 `{rows[0]['arm']}`(KPI {rows[0]['kpi']:.1f}% · t {rows[0]['t_med']:.3f}mm).")
        say(f"- 손실 = **t 중앙 {pick['t_med'] - rows[0]['t_med']:+.3f}mm · "
            f"KPI {pick['kpi'] - rows[0]['kpi']:+.1f}%p**")
    say("")
    say("## 🔴 읽는 법")
    say("")
    say("- 🔴🔴 **이 서열 자체를 실물로 가져가지 말 것.** sim 은 텍스처·조명·CAD 불일치 축이 "
        "닫혀 있고, sim 최적이 실물에서 뒤집힌 전례가 있다(§38-1: sim 참조가 실물에서 전멸).")
    say("- ★★ **가져갈 것은 «GT-free 지표를 얼마나 믿을지» 다.** 위 Spearman 이 실물에서 쓸 "
        "유일한 정보다 — 실물에는 GT 가 없으므로 `|Δdx|` 로 고를 수밖에 없고, 그 선택이 "
        "**얼마나 손해인지**를 여기서 미리 안다.")
    say("- ⚠️ **팔들이 애초에 안 갈리면 상관도 무의미하다** — 위 표의 `t 중앙` 이 서로 "
        "FP 재실행 잡음(0.252mm, §37-6) 안이면 «서열» 자체가 잡음이다. 그때는 "
        "**어느 지표로 골라도 손해가 없다**는 뜻이기도 하다.")
    say("- 🔴🔴 **서열 1순위는 «오선택률» 이다** — pose 팔 사이 차이는 0.01mm 급인데 "
        "**오선택은 KPI 를 20%p 씩 깎는다**(§42-3). 처방도 다르다: 오선택은 pose 가 아니라 "
        "**사전 위치 가드(§34-10) · 프롬프트 · `--text-select`** 로 잡는다.")
    say("- 🔴 **`|Δdx|` 는 오선택된 pose 에도 좋은 값을 낼 수 있다** — 엉뚱한 물체를 좌우 모두에 "
        "일관되게 투영하면 된다. §35-2o-6b 의 r = −0.94 는 **방해물 없는 씬**에서 잰 값이다. "
        "**가드 없이 `|Δdx|` 로 서열을 매기지 말 것**(§42-4).")

    if a.md_out:
        mp = Path(a.md_out)
        if str(mp.parent) != ".":
            mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text("\n".join(L) + "\n", encoding="utf-8")
        print(f"\n→ {mp.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
