#!/usr/bin/env python3
"""중간 보고서용 그림 3종 — 「왜 하이브리드(RH1/RH2)가 이기는가」의 이론적 근거.

    envs/pose/bin/python tools/report_figs_hybrid.py \
        --gt runs/fr_d50 --obj assets/obj/foup_300_semi_r2 \
        --arms runs/NECKRP_A1 runs/NECKRP_A2 … --out docs/figs

① complementarity.png — 프레임별 (R 오차, t 오차) 산점 + **등-ADD 선**.
   coarse 는 왼쪽 위(회전 강·이동 약), refined 는 오른쪽 아래, 하이브리드는 **왼쪽 아래**.
② lever_arm.png     — 원점 규약이 «R 오차 → ADD» 지렛대를 정한다. 하이브리드 이득의 **성립 조건**.
③ add_model.png     — 예측 상한 ADD(R)+ADD(t) 대 실측 ADD. 모델이 맞는지 눈으로 본다.

🔴 라벨은 **영문**이다 — 이 워크스페이스에 한글 폰트가 없다(`viz.dim_sheet` 와 같은 이유).
🔴 회전각은 `contracts.rotation_angle_deg` 로만 잰다 (교훈 #85: `arccos` 식은 잡음 바닥 0.03°).
⚠️ 그림은 «현재 데이터» 의 렌더링일 뿐이다 — 최종 프롬프트·파이프라인이 정해지면 그 산출물로 다시 돌린다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # tools/ 에서 spatial_vision 을 본다
import matplotlib.pyplot as plt
import numpy as np
import trimesh

from spatial_vision.contracts import rotation_angle_deg

STAGES = {"coarse": ("pose_coarse.json", "#1f77b4", "o"),
          "refined": ("pose_refined.json", "#ff7f0e", "s"),
          "hybrid": ("pose_coarse.json", "#2ca02c", "^")}   # hybrid 는 <arm>H 디렉토리


def load(p: Path):
    d = json.loads(p.read_text())
    return np.asarray(d["R"], float).reshape(3, 3), np.asarray(d["t_mm"], float)


def lever_mm_per_deg(pts: np.ndarray, origin: np.ndarray, rng, n: int = 300) -> float:
    """원점을 `origin` 으로 잡았을 때 **회전 1° 당 ADD 기여**(mm). 무작위 축 평균."""
    Q = pts - origin
    out = []
    for _ in range(n):
        a = rng.normal(size=3); a /= np.linalg.norm(a)
        K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
        th = np.radians(1.0)
        R = np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K
        out.append(np.linalg.norm((R @ Q.T).T - Q, axis=1).mean())
    return float(np.mean(out))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="하이브리드 근거 그림 3종")
    ap.add_argument("--gt", required=True, help="GT 캡처 디렉토리 (pose_gt.json)")
    ap.add_argument("--obj", required=True)
    ap.add_argument("--arms", nargs="+", required=True,
                    help="FP 산출 디렉토리들. 같은 이름 + 'H' 가 하이브리드로 간주된다")
    ap.add_argument("--out", default="docs/figs")
    ap.add_argument("--n-points", type=int, default=4096)
    a = ap.parse_args(argv)

    gt, out = Path(a.gt), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    V = np.asarray(trimesh.load(str(Path(a.obj) / "full.ply"), process=False).vertices)
    pts = V[rng.choice(len(V), min(a.n_points, len(V)), replace=False)]
    lev0 = lever_mm_per_deg(pts, np.zeros(3), rng)

    rows = []
    for arm in a.arms:
        A = Path(arm)
        for stage, (name, _, _) in STAGES.items():
            d = Path(str(A) + "H") if stage == "hybrid" else A
            for f in sorted(p.name for p in gt.glob("frame_*")):
                p = d / f / name
                if not p.exists():
                    continue
                Rg, tg = load(gt / f / "pose_gt.json")
                Rp, tp = load(p)
                rows.append({"arm": A.name, "stage": stage, "frame": f,
                             "R": rotation_angle_deg(Rg, Rp),
                             "t": float(np.linalg.norm(tg - tp)),
                             "ADD": float(np.linalg.norm(((Rg @ pts.T).T + tg)
                                                         - ((Rp @ pts.T).T + tp), axis=1).mean())})
    if not rows:
        print("❌ pose 를 하나도 못 읽었다 — --arms 경로를 확인할 것")
        return 2
    sel = lambda s, k: np.array([r[k] for r in rows if r["stage"] == s], float)
    print(f"프레임×팔 {len(rows)}행 · 지렛대 {lev0:.3f} mm/deg")

    # ── ① 상보성 ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    Rmax = max(sel(s, "R").max() for s in STAGES) * 1.12
    tmax = max(sel(s, "t").max() for s in STAGES) * 1.12
    for lv in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0):        # 등-ADD 선: lever·R + t = lv
        x = np.linspace(0, Rmax, 50)
        ax.plot(x, lv - lev0 * x, color="0.82", lw=0.9, zorder=0)
        # 라벨은 «선이 그림 안에 있는» x 를 찾아 붙인다 — 고정 위치는 대부분 잘려 나간다
        xs = x[(lv - lev0 * x > 0.03 * tmax) & (lv - lev0 * x < 0.95 * tmax)]
        if len(xs):
            xl = xs[len(xs) // 2]
            ax.text(xl, lv - lev0 * xl, f"ADD {lv:g}", color="0.5", fontsize=7,
                    ha="center", va="bottom", rotation=np.degrees(np.arctan2(
                        -lev0 / tmax * 5.2, 1.0 / Rmax * 6.4)), zorder=0)
    for s, (_, c, m) in STAGES.items():
        R, t = sel(s, "R"), sel(s, "t")
        ax.scatter(R, t, s=17, c=c, marker=m, alpha=0.42, edgecolors="none", label=None)
        ax.scatter([np.median(R)], [np.median(t)], s=190, c=c, marker=m,
                   edgecolors="k", linewidths=1.4, zorder=5,
                   label=f"{s}  (median {np.median(R):.2f}°, {np.median(t):.2f} mm)")
    ax.set_xlim(0, Rmax); ax.set_ylim(0, tmax)
    ax.set_xlabel("rotation error  [deg]")
    ax.set_ylabel("translation error  ‖Δt‖  [mm]")
    ax.set_title("(1) Stage complementarity — and why grafting wins\n"
                 f"grey lines: iso-ADD  (ADD ≈ {lev0:.2f}·R + t)", fontsize=10.5)
    ax.legend(fontsize=8, loc="upper right", framealpha=0.95)
    ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout(); fig.savefig(out / "fig1_complementarity.png", dpi=190); plt.close(fig)

    # ── ② 원점 규약 → 지렛대 → 하이브리드 이득 ────────────────────────────────────
    offs = np.linspace(0, 380, 26)
    lv = np.array([lever_mm_per_deg(pts, np.array([0, 0, -z]), rng, n=120) for z in offs])
    Rc, tc = np.median(sel("coarse", "R")), np.median(sel("coarse", "t"))
    Rr, tr = np.median(sel("refined", "R")), np.median(sel("refined", "t"))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 4.5))
    ax1.plot(offs, lv, "-", color="#333", lw=2)
    for z, lab in ((0, "flange top centre\n(current)"), (41.4, "mesh centroid"),
                   (171.0, "bbox centre"), (344.0, "body bottom")):
        y = lever_mm_per_deg(pts, np.array([0, 0, -z]), rng, n=200)
        ax1.plot([z], [y], "o", ms=8, color="#d62728" if z == 0 else "#666")
        off = {0: (14, 30), 41.4: (22, -6), 171.0: (-88, 14), 344.0: (-100, 8)}[z]
        ax1.annotate(f"{lab}\n{y:.2f} mm/deg", (z, y), textcoords="offset points",
                     xytext=off, fontsize=7.6,
                     color="#d62728" if z == 0 else "#444")
    ax1.set_xlabel("pose-origin offset below flange top plane  [mm]")
    ax1.set_ylabel("lever arm  [mm per deg]")
    ax1.set_title("(2a) The origin convention sets the R→ADD lever", fontsize=10.5)
    ax1.grid(alpha=0.25, lw=0.5)
    # 🔴 «이득» 을 직접 그린다. 절대 ADD 3선을 그리면 «하이브리드가 계속 아래» 로 보여
    #    정작 말하려는 «이득이 줄어든다» 가 안 보인다 (초판이 그래서 제목을 과장했다).
    pc, pr = lv * Rc + tc, lv * Rr + tr
    gain = np.minimum(pc, pr) / (lv * Rc + tr)          # 단일 최선 대비 하이브리드 이득 배수
    ax2.plot(offs, gain, lw=2.4, color="#2ca02c")
    ax2.axvline(0, color="#d62728", ls=":", lw=1.3)
    ax2.axhline(1.0, color="0.6", ls="--", lw=1.0)
    ax2.set_ylim(0.97, gain.max() * 1.10)          # 주석이 위로 새지 않게 여유
    ax2.annotate(f"current convention\n×{gain[0]:.2f}", (0, gain[0]),
                 textcoords="offset points", xytext=(16, -26), fontsize=8.4, color="#d62728")
    i = int(np.argmin(np.abs(offs - 344)))
    ax2.annotate(f"body bottom\n×{gain[i]:.2f}", (offs[i], gain[i]),
                 textcoords="offset points", xytext=(-70, 22), fontsize=8.4, color="#444",
                 arrowprops=dict(arrowstyle="-", lw=0.7, color="#888"))
    ax2.text(0.03, 0.06, "×1.00 = grafting buys nothing", transform=ax2.transAxes,
             fontsize=8, color="0.45")
    ax2.set_xlabel("pose-origin offset below flange top plane  [mm]")
    ax2.set_ylabel("hybrid gain   best-single ADD / hybrid ADD   [×]")
    ax2.set_title("(2b) Falsifiable prediction: the grafting gain\n"
                  "shrinks as the origin leaves the observed surface", fontsize=10.5)
    ax2.grid(alpha=0.25, lw=0.5)
    fig.tight_layout(); fig.savefig(out / "fig2_lever_arm.png", dpi=190); plt.close(fig)

    # ── ③ 예측 상한 vs 실측 ───────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(6.0, 5.4))
    allmax = 0.0
    for s, (_, c, m) in STAGES.items():
        R, t, D = sel(s, "R"), sel(s, "t"), sel(s, "ADD")
        pred = lev0 * R + t
        ax.scatter(pred, D, s=16, c=c, marker=m, alpha=0.40, edgecolors="none")
        ax.scatter([np.median(pred)], [np.median(D)], s=185, c=c, marker=m,
                   edgecolors="k", linewidths=1.4, zorder=5,
                   label=f"{s}: {np.median(D)/np.median(pred)*100:.0f}% of bound")
        allmax = max(allmax, pred.max(), D.max())
    lim = allmax * 1.06
    ax.plot([0, lim], [0, lim], "k--", lw=1.2, label="y = x  (triangle-ineq. bound)")
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel(f"predicted upper bound   {lev0:.2f}·R + ‖Δt‖   [mm]")
    ax.set_ylabel("measured ADD  [mm]")
    ax.set_title("(3) The additive error model is quantitatively validated\n"
                 "all stages sit consistently just below the bound", fontsize=10.5)
    ax.legend(fontsize=8.4, loc="upper left"); ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout(); fig.savefig(out / "fig3_add_model.png", dpi=190); plt.close(fig)

    (out / "figs_data.json").write_text(json.dumps(
        {"_note": "중간 보고서용. 최종 파이프라인이 정해지면 --arms 만 바꿔 다시 돌린다.",
         "lever_mm_per_deg": lev0, "n_rows": len(rows), "arms": [Path(x).name for x in a.arms],
         "rows": rows}, ensure_ascii=False, indent=1))
    for f in ("fig1_complementarity.png", "fig2_lever_arm.png", "fig3_add_model.png"):
        print(f"→ {out / f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
