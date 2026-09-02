#!/usr/bin/env python3
"""**거리 사다리**를 한 표·한 그림으로 — «KPI 가 거리에 따라 어떻게 변하나».

왜 따로 있나
    `tools/arm_rank_sim.py` 는 **한 캡처 안의 팔들**을 서열화한다. 이건 **캡처가 거리별로 여럿**일 때
    같은 팔을 **거리축에 늘어놓는다**. 배포 거리대를 정하는 것이 목적이다.

    🔴 **두 힘이 반대로 당긴다**(§44-21): 멀수록 **분할 오선택**이 줄고, 가까울수록 **pose 가 정확**하다.
    그래서 KPI 는 «전체 프레임» 과 «오선택 뺀 프레임» 을 **둘 다** 봐야 최적점의 이유가 보인다.

    🔴 **FP 는 비결정이다**(교훈 #24·#107) — 거리마다 반복 런을 받아 **프레임별 중앙값**으로 누른다.
    ⚠️ KPI 는 이항비율이라 n=80 이면 95% 폭이 **±10%p 안팎**이다(0.5 근처에서 최대).
    **곡선의 «모양» 은 읽되 1~2%p 차이를 «순위» 로 읽으면 안 된다**(표에 95% 폭을 함께 낸다).

거리 표기
    디렉토리 이름이 아니라 **GT 의 실측 중앙값**(‖t_gt‖)을 쓴다 — 캡처 인자와 실제가 어긋나도 잡힌다.

사용
    envs/pose/bin/python tools/dist_curve.py --obj assets/obj/foup_300_semi_r2 \\
        --cap "runs/S44L_030" --cap "runs/S44L_040" ... \\
        --seg-suffix _seg --pose-suffix "_p*" --mode hybrid
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def wilson_half(k: int, n: int, z: float = 1.96) -> float:
    """KPI 오차막대 (95% Wilson 반폭, %p).

    🔴 정규근사 `sqrt(p(1-p)/n)` 를 쓰면 **무결점(p=1)에서 0 이 나와** «최적점 확정» 착시가 난다
    (n=80 의 무결점도 실패율 상한이 3.7% 다 — 교훈 #58). Wilson 은 끝에서 무너지지 않는다.
    """
    if n == 0:
        return float("nan")
    p = k / n
    den = 1 + z * z / n
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return 100 * float(half)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cap", action="append", required=True, help="캡처 디렉토리 (여러 번). 글롭 가능")
    ap.add_argument("--obj", required=True)
    ap.add_argument("--seg-suffix", default="_seg", help="캡처명 + 이것 = 분할 디렉토리")
    ap.add_argument("--pose-suffix", default="_p*", help="캡처명 + 이것 = pose **반복 런들** 글롭")
    ap.add_argument("--mode", default="hybrid", choices=("hybrid", "refined", "coarse"),
                    help="hybrid = R 은 coarse · t 는 refined (§27-7, 배포 팔 RH*)")
    ap.add_argument("--miss-iou", type=float, default=0.3)
    ap.add_argument("--add-samples", type=int, default=2000)
    ap.add_argument("--kpi-t", type=float, default=5.0)
    ap.add_argument("--kpi-r", type=float, default=3.0)
    ap.add_argument("--md-out", default=None)
    ap.add_argument("--png-out", default=None)
    a = ap.parse_args(argv)

    import cv2
    import trimesh
    from spatial_vision.contracts import rotation_angle_deg

    caps: list[Path] = []
    for c in a.cap:
        caps += [Path(x) for x in sorted(glob.glob(c))]
    caps = [c for c in caps if (c / "frame_0000" / "pose_gt.json").exists()]
    if not caps:
        print("❌ GT 가 있는 캡처가 없다 — sim 캡처여야 한다", file=sys.stderr)
        return 2

    mesh = trimesh.load(str(Path(a.obj) / "full.ply"), process=False)
    V = np.asarray(mesh.vertices, float)
    if len(V) > a.add_samples:
        V = V[np.linspace(0, len(V) - 1, a.add_samples).astype(int)]

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

    rows = []
    for cap in caps:
        frames = sorted(x.name for x in cap.glob("frame_*") if (x / "pose_gt.json").exists())
        GT = {f: pose(cap / f / "pose_gt.json") for f in frames}
        dist_m = float(np.median([np.linalg.norm(GT[f][1]) for f in frames])) / 1000.0

        seg = Path(str(cap) + a.seg_suffix)
        miou = []
        for f in frames:
            p, q = seg / f / "mask_full.png", cap / f / "mask_full.png"
            if not (p.exists() and q.exists()):
                miou.append(np.nan); continue
            x = cv2.imread(str(p), 0) > 127
            y = cv2.imread(str(q), 0) > 127
            miou.append(float((x & y).sum() / max((x | y).sum(), 1)))
        miou = np.array(miou)

        runs = [Path(x) for x in sorted(glob.glob(str(cap) + a.pose_suffix))]
        runs = [r for r in runs if (r / "meta_pose.json").exists()]
        if not runs:
            out(f"⚠️ `{cap.name}`: pose 반복 런이 없다 — 건너뛴다")
            continue
        R_, T_, A_ = [], [], []
        for rd in runs:
            rr, tt, aa = [], [], []
            for f in frames:
                pr, pc, gt = (pose(rd / f / "pose_refined.json"),
                              pose(rd / f / "pose_coarse.json"), GT[f])
                if gt is None or pr is None or pc is None:
                    rr.append(np.nan); tt.append(np.nan); aa.append(np.nan); continue
                Rp, tp = ((pc[0], pr[1]) if a.mode == "hybrid"
                          else (pc if a.mode == "coarse" else pr))
                rr.append(rotation_angle_deg(Rp.T @ gt[0]))
                tt.append(float(np.linalg.norm(tp - gt[1])))
                aa.append(float(np.linalg.norm((V @ Rp.T + tp) - (V @ gt[0].T + gt[1]),
                                               axis=1).mean()))
            R_.append(rr); T_.append(tt); A_.append(aa)
        R = np.nanmedian(np.array(R_), axis=0)
        T = np.nanmedian(np.array(T_), axis=0)
        A = np.nanmedian(np.array(A_), axis=0)

        # 🔴 pose 가 아예 안 나온 프레임(분할 미검출 등)도 KPI 분모에 넣는다 — 빼면 생존 편향(#110)
        n = len(frames)
        ok = np.isfinite(R) & np.isfinite(T)
        kpi = int(((T <= a.kpi_t) & (R <= a.kpi_r) & ok).sum())
        cl = ok & (miou >= a.miss_iou)
        kpi_c = int(((T <= a.kpi_t) & (R <= a.kpi_r) & cl).sum())
        miss = int((miou < a.miss_iou).sum())
        rows.append(dict(name=cap.name, d=dist_m, n=n, miss=miss, nopose=int((~ok).sum()),
                         kpi=kpi, se=wilson_half(kpi, n),
                         kpi_c=kpi_c, n_c=int(cl.sum()),
                         add=float(np.nanmedian(A[cl])) if cl.any() else np.nan,
                         R=float(np.nanmedian(R[cl])) if cl.any() else np.nan,
                         t=float(np.nanmedian(T[cl])) if cl.any() else np.nan,
                         nrep=len(runs)))

    rows.sort(key=lambda r: r["d"])
    out(f"# 거리 사다리 — 팔 `{a.mode}` · 캡처 {len(rows)}개")
    out()
    out("🔴 **KPI 는 «전체 프레임» 분모**다(미검출·오선택 포함) — 빼면 생존 편향이 난다(교훈 #110). "
        "«깨끗» 열은 오선택을 뺀 것이고, 두 열의 **간격이 곧 분할이 먹는 몫**이다.")
    out()
    out("| 캡처 | **거리(m)** | n | 반복 | 오선택 | pose 없음 | **KPI(전체)** | 95%CI | KPI(깨끗) | "
        "ADD 중앙 | R 중앙 | t 중앙 |")
    out("|---|---|:-:|:-:|:-:|:-:|---|---|---|---|---|---|")
    for r in rows:
        out(f"| `{r['name']}` | **{r['d']:.3f}** | {r['n']} | {r['nrep']} | "
            f"{r['miss']} | {r['nopose']} | **{r['kpi']}/{r['n']} "
            f"({100*r['kpi']/r['n']:.1f}%)** | ±{r['se']:.1f}%p | "
            f"{r['kpi_c']}/{r['n_c']} | {r['add']:.3f} | {r['R']:.3f} | {r['t']:.3f} |")
    out()
    if rows:
        b = max(rows, key=lambda r: r["kpi"] / r["n"])
        near = [r for r in rows if 100 * (b["kpi"] / b["n"] - r["kpi"] / r["n"]) <= b["se"]]
        out(f"**최댓값은 {b['d']:.2f}m ({100*b['kpi']/b['n']:.1f}%)** 인데 🔴 **95% Wilson 폭(±{b['se']:.1f}%p) "
            f"안에 {len(near)}개 거리가 들어온다** — "
            + " · ".join(f"{r['d']:.2f}m" for r in near))
        out()
        out("→ ★ **읽는 법: «최댓값이 어디냐» 가 아니라 «어느 구간이 평평하냐» 다.** "
            "n=80 이면 95% 폭이 최대 ±10%p 라 1~2%p 차이는 순위가 아니다(교훈 #12). 무결점(100%)도 폭이 0 이 아니다 — 실패율 상한 3.7%(교훈 #58).")

    if a.png_out:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        d = [r["d"] for r in rows]
        fig, ax = plt.subplots(figsize=(8.2, 4.6), dpi=140)
        k = [100 * r["kpi"] / r["n"] for r in rows]
        se = [r["se"] for r in rows]
        ax.errorbar(d, k, yerr=se, marker="o", lw=2, color="#1f77b4", capsize=3,
                    label="KPI % (all frames)")
        ax.plot(d, [100 * r["kpi_c"] / max(r["n_c"], 1) for r in rows], marker="s", ls="--",
                color="#2ca02c", label="KPI % (clean only)")
        ax.plot(d, [100 * r["miss"] / r["n"] for r in rows], marker="^", ls=":",
                color="#d62728", label="misselection %")
        ax.set_xlabel("distance (m, GT median)"); ax.set_ylabel("%")
        ax.set_ylim(-3, 103); ax.grid(alpha=.3); ax.legend(fontsize=8)
        ax2 = ax.twinx()
        ax2.plot(d, [r["add"] for r in rows], marker="d", color="#7f7f7f", alpha=.7,
                 label="ADD median (clean)")
        ax2.set_ylabel("ADD median (mm)")
        ax2.legend(fontsize=8, loc="lower right")
        ax.set_title(f"KPI vs distance  (arm={a.mode}, n={rows[0]['n']}/dist)")
        fig.tight_layout(); fig.savefig(a.png_out)
        out(); out(f"→ 그림 `{Path(a.png_out).resolve()}`")

    if a.md_out:
        Path(a.md_out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n→ {Path(a.md_out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
