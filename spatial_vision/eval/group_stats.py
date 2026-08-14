"""A그룹 산출물을 **통계 분석용 한 벌**로 모은다 — 표·그래프·CSV.

    envs/pose/bin/python -m spatial_vision.eval.group_stats --root runs/real01_A

왜 필요한가
    러너가 내는 것은 스테이지마다 흩어진 JSON 이고, `report.md` 는 **중앙값 한 줄씩**만 보여준다.
    분포·꼬리·프레임 간 상관을 직접 보려면 **한 표로 합쳐져** 있어야 한다. 실환경에는 GT 가 없으니
    *"어느 변형이 맞나"* 는 못 묻고, **«분포가 어떻게 다른가»** 만 물을 수 있다 — 그 질문의 도구다.

입력 (전부 있으면 쓰고, 없으면 그 열만 빈다)
    <root>/diag/diag_metrics.json           촬영·depth·마스크 (프레임별)
    <root>/<variant>/meta_contour.json      n_corr·rms_px·moved_deg·gated (프레임별)
    <root>/lr/lr_consistency_<variant>.json 좌우 투영 일관성 (프레임별)
    <root>/<variant>/frame_*/pose_refined.json   최종 pose

산출
    stats/frames.csv          프레임 × 촬영지표          ← 노출·거리·depth 품질
    stats/metrics_long.csv    (프레임 × 변형) 긴 형식     ← pandas/엑셀로 바로 분석
    stats/summary.json/.md    변형별 집계 (중앙·p90·최대)
    stats/variants.png        변형 비교 4패널 (후퇴율·이동량 분포·좌우 일관성·대응점)
    stats/repeatability.png   ★ **정지 구간 반복도** — 랜덤 오차 바닥
    stats/repeatability.json

🔴 **반복도는 «물체·카메라가 안 움직인 구간» 에서만 뜻이 있다.**
    로봇이 없어 손으로 움직이는 지금 환경에서 *연속 촬영 20~40장* 은 **sim 에 대응물이 없는**
    real 전용 측정이다(`PIPELINE_CATALOG §9.1★c`). 움직이면서 찍었으면 이 숫자는 **자세 변화**이지
    오차가 아니다 — 그래서 **z 산포를 함께 찍어** 판별할 수 있게 한다.

⚠️ **중앙값만 보고 우열을 정하지 않는다**(교훈 #16). 그래서 표에 **p90·최대**를 같이 넣고
   그래프는 **분포(상자 + 점)** 로 그린다 — 40장에서 꼬리는 한두 점이라 상자만으로는 안 보인다.
⚠️ 그래프 라벨은 **영문**이다 — matplotlib 에 한글 폰트가 없다(`viz.dim_sheet` 과 같은 제약).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

DEFAULT_VARIANTS = ["A1", "A2a", "A2b", "A4"]
LABELS = {"A1": "A1 hole-excl (deploy)", "A2a": "A2a hole-contour", "A2b": "A2b hole-center",
          "A3": "A3 no-refine (FP)", "A4": "A4 refined-init"}


def _load(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def _stat(v, keys=("median", "p90", "max")):
    v = np.asarray([x for x in v if x is not None and np.isfinite(x)], float)
    if not len(v):
        return {k: None for k in keys} | {"n": 0}
    out = {"n": int(len(v))}
    for k in keys:
        out[k] = round(float({"median": np.median(v), "p90": np.percentile(v, 90),
                              "max": v.max(), "mean": v.mean(), "std": v.std(ddof=1) if len(v) > 1
                              else 0.0}[k]), 4)
    return out


def quat_from_R(R):
    """부호를 고정한 쿼터니언 (w≥0) — CSV 에서 프레임 간 비교가 되게 하려면 부호가 일정해야 한다."""
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        q = np.array([0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s,
                      (R[1, 0] - R[0, 1]) / s])
    else:
        i = int(np.argmax(np.diag(R)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = np.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2
        q = np.zeros(4)
        q[0] = (R[k, j] - R[j, k]) / s
        q[1 + i] = 0.25 * s
        q[1 + j] = (R[j, i] + R[i, j]) / s
        q[1 + k] = (R[k, i] + R[i, k]) / s
    q = q / np.linalg.norm(q)
    return q if q[0] >= 0 else -q          # w≥0 으로 고정


def mean_rotation(Rs):
    """회전 평균 — 쿼터니언 외적행렬의 최대 고유벡터. ⚠️ 성분별 평균은 회전이 아니다."""
    Q = np.stack([quat_from_R(R) for R in Rs])
    w, V = np.linalg.eigh(Q.T @ Q)
    q = V[:, -1]
    w0, x, y, z = q if q[0] >= 0 else -q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w0), 2 * (x * z + y * w0)],
        [2 * (x * y + z * w0), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w0)],
        [2 * (x * z - y * w0), 2 * (y * z + x * w0), 1 - 2 * (x * x + y * y)]])


def ang_deg(A, B):
    c = (np.trace(A.T @ B) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


# ─────────────────────────────────────────────────────────── 수집

def collect(root: Path, variants: list[str], pose_name: str) -> tuple[dict, list[dict], list[dict]]:
    diag = _load(root / "diag" / "diag_metrics.json") or {}
    cap_rows = diag.get("frames", [])
    frames = [r["frame"] for r in cap_rows]

    long_rows: list[dict] = []
    present: dict[str, dict] = {}
    for vid in variants:
        mc = _load(root / vid / "meta_contour.json")
        lr = _load(root / "lr" / f"lr_consistency_{vid}.json")
        if mc is None and lr is None and not (root / vid).exists():
            continue
        present[vid] = {"meta": mc, "lr": lr}
        by_c = {r["frame"]: r for r in (mc or {}).get("frames", [])}
        by_l = {r["frame"]: r for r in (lr or {}).get("frames", [])}
        names = frames or sorted(set(by_c) | set(by_l))
        for fn in names:
            c, l = by_c.get(fn, {}), by_l.get(fn, {})
            row = {"frame": fn, "variant": vid,
                   "n_corr": c.get("n_corr"), "rms_px": c.get("rms_px"),
                   "moved_deg": c.get("moved_deg"), "moved_mm": c.get("moved_mm"),
                   "gated": c.get("gated"),
                   "ddx_px": l.get("ddx_px"), "ddy_px": l.get("ddy_px"), "dz_mm": l.get("dz_mm"),
                   "lr_rms_L": l.get("rms_L"), "lr_rms_R": l.get("rms_R")}
            T = _load(root / vid / fn / pose_name)
            if T:
                R = np.asarray(T["R"], float).reshape(3, 3)
                t = np.asarray(T["t_mm"], float)
                q = quat_from_R(R)
                row |= {"tx_mm": round(float(t[0]), 4), "ty_mm": round(float(t[1]), 4),
                        "tz_mm": round(float(t[2]), 4),
                        "qw": round(float(q[0]), 6), "qx": round(float(q[1]), 6),
                        "qy": round(float(q[2]), 6), "qz": round(float(q[3]), 6)}
            long_rows.append(row)
    return present, cap_rows, long_rows


def flatten_capture(r: dict) -> dict:
    i, mf, ml = r.get("image") or {}, r.get("mask_full") or {}, r.get("mask_flange") or {}
    d, v = r.get("depth") or {}, r.get("valid") or {}
    pl = d.get("plane") or {}
    p = r.get("pose") or {}
    return {"frame": r["frame"], "img_med": i.get("med"), "sat_pct": i.get("sat_pct"),
            "dark_pct": i.get("dark_pct"),
            "full_dia_px": mf.get("dia_px"), "full_blobs": mf.get("n_blobs"),
            "flange_dia_px": ml.get("dia_px"), "flange_blobs": ml.get("n_blobs"),
            "depth_med_flange": d.get("med_flange"), "depth_med_all": d.get("med_all"),
            "plane_rms_mm": pl.get("rms_mm"), "plane_p90_mm": pl.get("p90_mm"),
            "valid_all": v.get("all"), "valid_flange": v.get("flange"), "valid_ring": v.get("ring"),
            "pose_z_mm": p.get("z_mm"), "pose_gated": p.get("gated")}


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    cols: list[str] = []
    for r in rows:                          # 열 순서를 등장 순으로 안정화한다
        for k in r:
            if k not in cols:
                cols.append(k)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


# ─────────────────────────────────────────────────────────── 집계·그래프

def summarize(present: dict, long_rows: list[dict]) -> dict:
    out = {}
    for vid in present:
        rs = [r for r in long_rows if r["variant"] == vid]
        n = len(rs)
        gated = sum(1 for r in rs if r.get("gated"))
        out[vid] = {
            "n": n, "n_gated": gated,
            "gated_pct": round(100 * gated / n, 1) if n else None,
            "moved_deg": _stat([r.get("moved_deg") for r in rs]),
            "moved_mm": _stat([r.get("moved_mm") for r in rs]),
            "rms_px": _stat([r.get("rms_px") for r in rs]),
            "n_corr": _stat([r.get("n_corr") for r in rs]),
            "abs_ddx_px": _stat([abs(r["ddx_px"]) for r in rs if r.get("ddx_px") is not None]),
            "abs_dz_mm": _stat([abs(r["dz_mm"]) for r in rs if r.get("dz_mm") is not None]),
            "sec": (present[vid]["meta"] or {}).get("sec"),
        }
    return out


def repeatability(long_rows: list[dict], variants: list[str]) -> dict:
    """정지 구간 반복도 — 프레임 간 pose 산포.

    🔴 **물체·카메라가 안 움직였을 때만 «랜덤 오차 바닥» 이다.** 움직이며 찍었으면 이건 자세 변화다.
       그래서 `tz_spread_mm`(거리 산포)를 같이 낸다 — 수십 mm 면 움직인 것이다.
    """
    out = {}
    for vid in variants:
        rs = [r for r in long_rows if r["variant"] == vid and "qw" in r]
        if len(rs) < 3:
            continue
        Rs, ts = [], []
        for r in rs:
            w, x, y, z = r["qw"], r["qx"], r["qy"], r["qz"]
            Rs.append(np.array([
                [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]))
            ts.append([r["tx_mm"], r["ty_mm"], r["tz_mm"]])
        Rm, ts = mean_rotation(Rs), np.asarray(ts, float)
        dev = np.array([ang_deg(Rm, R) for R in Rs])
        dt = ts - ts.mean(0)
        out[vid] = {
            "n": len(rs),
            "rot_dev_deg": _stat(dev, ("median", "p90", "max", "std")),
            "t_std_mm": {ax: round(float(ts[:, i].std(ddof=1)), 4) for i, ax in enumerate("xyz")},
            "t_dev_norm_mm": _stat(np.linalg.norm(dt, axis=1), ("median", "p90", "max")),
            "tz_spread_mm": round(float(ts[:, 2].max() - ts[:, 2].min()), 2),
        }
    return out


def figures(out: Path, present: dict, long_rows: list[dict], cap_rows: list[dict],
            rep: dict, gate_deg: float) -> list[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    made = []
    vids = list(present)

    def series(vid, key, absolute=False):
        v = [r.get(key) for r in long_rows if r["variant"] == vid]
        v = [abs(x) if absolute else x for x in v if isinstance(x, (int, float))]
        return np.asarray(v, float)

    def box_strip(ax, data, title, ref=None, reflab=None, logy=False):
        keep = [(v, d) for v, d in zip(vids, data) if len(d)]
        if not keep:
            ax.set_visible(False)
            return
        labs, ds = [v for v, _ in keep], [d for _, d in keep]
        ax.boxplot(ds, tick_labels=[LABELS.get(v, v) for v in labs], showfliers=False,
                   widths=0.5, medianprops={"color": "crimson"})
        for i, d in enumerate(ds, 1):      # ★ 점을 겹쳐 찍는다 — 40장에서 꼬리는 상자에 안 보인다
            ax.plot(np.full(len(d), i) + (np.linspace(-0.16, 0.16, len(d))), d,
                    "o", ms=2.4, alpha=0.5)
        if ref is not None:
            ax.axhline(ref, color="crimson", ls="--", lw=0.9, label=reflab)
            ax.legend(fontsize=7)
        if logy:
            ax.set_yscale("log")
        ax.set_title(title, fontsize=9)
        ax.grid(alpha=0.25, lw=0.5)
        ax.tick_params(labelsize=7, axis="x", rotation=12)

    fig, ax = plt.subplots(2, 2, figsize=(11, 7.2))
    g = [100 * sum(1 for r in long_rows if r["variant"] == v and r.get("gated"))
         / max(sum(1 for r in long_rows if r["variant"] == v), 1) for v in vids]
    ax[0, 0].bar([LABELS.get(v, v) for v in vids], g, color="#4C78A8")
    for i, y in enumerate(g):
        ax[0, 0].text(i, y, f"{y:.0f}%", ha="center", va="bottom", fontsize=8)
    ax[0, 0].set_title("gate fallback rate (%)  — lower is better", fontsize=9)
    ax[0, 0].grid(alpha=0.25, lw=0.5, axis="y")
    ax[0, 0].tick_params(labelsize=7, axis="x", rotation=12)

    box_strip(ax[0, 1], [series(v, "moved_deg") for v in vids],
              "contour moved (deg)", gate_deg, f"gate {gate_deg}")
    box_strip(ax[1, 0], [series(v, "ddx_px", absolute=True) for v in vids],
              "|L-R projection mismatch| (px)  — lower is better")
    box_strip(ax[1, 1], [series(v, "n_corr") for v in vids],
              "correspondences per frame", logy=True)
    fig.suptitle("A-group variant comparison (GT-free)", fontsize=11)
    fig.tight_layout()
    fig.savefig(out / "variants.png", dpi=140)
    plt.close(fig)
    made.append("variants.png")

    if rep:
        rv = list(rep)
        fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
        for v in rv:
            rs = [r for r in long_rows if r["variant"] == v and "tz_mm" in r]
            ax[0].plot(np.arange(len(rs)), [r["tz_mm"] for r in rs], marker="o", ms=2.4,
                       lw=1.0, label=LABELS.get(v, v))
        ax[0].set_title("pose distance z (mm) per frame\n"
                        "large spread = the rig moved -> NOT a noise floor", fontsize=9)
        ax[0].set_xlabel("frame index", fontsize=8)
        ax[0].grid(alpha=0.25, lw=0.5)
        ax[0].legend(fontsize=7)
        ax[0].tick_params(labelsize=7)
        w = 0.8 / max(len(rv), 1)
        for i, v in enumerate(rv):
            s = rep[v]
            vals = [s["rot_dev_deg"]["median"] or 0, s["t_dev_norm_mm"]["median"] or 0,
                    s["t_std_mm"]["x"], s["t_std_mm"]["y"], s["t_std_mm"]["z"]]
            ax[1].bar(np.arange(5) + i * w, vals, width=w, label=LABELS.get(v, v))
        ax[1].set_xticks(np.arange(5) + 0.4 - w / 2)
        ax[1].set_xticklabels(["rot dev\n(deg, med)", "|t dev|\n(mm, med)",
                               "std tx", "std ty", "std tz"], fontsize=7)
        ax[1].set_title("static-scene repeatability (only valid if nothing moved)", fontsize=9)
        ax[1].grid(alpha=0.25, lw=0.5, axis="y")
        ax[1].legend(fontsize=7)
        ax[1].tick_params(labelsize=7)
        fig.tight_layout()
        fig.savefig(out / "repeatability.png", dpi=140)
        plt.close(fig)
        made.append("repeatability.png")
    return made


def summary_md(root: Path, summ: dict, rep: dict, cap_rows: list[dict], figs: list[str]) -> str:
    L = [f"# A그룹 통계 — `{root}`\n",
         "🔴 **실환경에는 GT 가 없다** — 아래는 전부 GT-free 지표다. "
         "절대 오차(mm·도)는 원리적으로 못 낸다.\n",
         "⚠️ **중앙값만 보고 우열을 정하지 않는다**(교훈 #16) — p90·최대를 같이 본다. "
         "n=40 무결점이 n=120 에서 110/120 이었던 전례가 있다(교훈 #58).\n",
         "## 변형별 집계\n",
         "| 변형 | n | 게이트 후퇴 | 이동 ° 중앙/p90/최대 | rms px 중앙 | 대응점 중앙 | "
         "\\|Δdx\\| 중앙/p90 | \\|dz\\| 중앙 |",
         "|---|---|---|---|---|---|---|---|"]
    for vid, s in summ.items():
        m, d = s["moved_deg"], s["abs_ddx_px"]
        L.append(f"| {LABELS.get(vid, vid)} | {s['n']} | {s['n_gated']} ({s['gated_pct']}%) | "
                 f"{m['median']} / {m['p90']} / {m['max']} | {s['rms_px']['median']} | "
                 f"{s['n_corr']['median']} | {d['median']} / {d['p90']} | "
                 f"{s['abs_dz_mm']['median']} |")
    L.append("")
    if rep:
        L.append("## 정지 구간 반복도\n")
        # ★ **판정을 사람에게 미루지 않는다.** z 산포가 크면 이 표는 반복도가 아니라 자세 변화이고,
        #   그걸 모르고 «회전 오차 72°» 로 읽으면 정반대의 결론이 난다.
        zs = max((s["tz_spread_mm"] for s in rep.values()), default=0.0)
        if zs > 10.0:
            L.append(f"🔴🔴 **정지 구간이 아니다 — 이 표를 «반복도» 로 읽으면 안 된다.** "
                     f"거리 산포가 **{zs:.1f}mm** 다(정지면 수 mm 이내). 아래 «회전 산포» 는 "
                     f"**오차가 아니라 자세 변화**다. 반복도를 재려면 **물체·카메라를 고정하고 "
                     f"연속 20~40장**을 찍어야 한다 — 손으로도 싸고 sim 에 대응물이 없는 측정이다.\n")
        else:
            L.append(f"✅ 거리 산포 **{zs:.1f}mm** — 정지 구간으로 볼 수 있다. "
                     f"아래 값이 **랜덤 오차 바닥**이다(계통 편향은 여기서 안 잡힌다 — §7.5c 상대 GT 가 그 몫).\n")
        L.append("🔴 **물체·카메라가 안 움직인 구간에서만 «랜덤 오차 바닥» 이다.** "
                 "움직이며 찍었으면 이 값은 자세 변화이지 오차가 아니다 — `z 산포` 로 판별한다.\n")
        L.append("| 변형 | n | 회전 산포 ° 중앙/p90/최대 | \\|t 산포\\| mm 중앙 | std x/y/z mm | z 산포 mm |")
        L.append("|---|---|---|---|---|---|")
        for vid, s in rep.items():
            r, t = s["rot_dev_deg"], s["t_std_mm"]
            L.append(f"| {LABELS.get(vid, vid)} | {s['n']} | "
                     f"{r['median']} / {r['p90']} / {r['max']} | {s['t_dev_norm_mm']['median']} | "
                     f"{t['x']} / {t['y']} / {t['z']} | **{s['tz_spread_mm']}** |")
        L.append("")
    if cap_rows:
        L.append(f"## 촬영 — 프레임 {len(cap_rows)}장\n")
        L.append("`frames.csv` 에 전부 있다. 노출·거리·depth 품질은 `diag/diag_trends.png` 에서 추이로 본다.\n")
    L.append("## 파일\n")
    L.append("| 파일 | 무엇 |")
    L.append("|---|---|")
    L.append("| `frames.csv` | 프레임 × 촬영지표 (노출·마스크·depth·유효율) |")
    L.append("| `metrics_long.csv` | **(프레임 × 변형) 긴 형식** — pandas/엑셀로 바로 분석 |")
    L.append("| `summary.json` | 위 표의 기계 판독본 |")
    for f in figs:
        L.append(f"| `{f}` | 그래프 |")
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A그룹 산출물 → 통계 표·그래프·CSV")
    ap.add_argument("--root", required=True, help="run_group_a.py 의 --out 디렉토리")
    ap.add_argument("--out", default=None, help="기본 <root>/stats")
    ap.add_argument("--variants", default=",".join(DEFAULT_VARIANTS))
    ap.add_argument("--pose-name", default="pose_refined.json")
    ap.add_argument("--gate-deg", type=float, default=1.5)
    args = ap.parse_args(argv)

    root = Path(args.root)
    out = Path(args.out) if args.out else root / "stats"
    variants = [s.strip() for s in args.variants.split(",") if s.strip()]
    present, cap_rows, long_rows = collect(root, variants, args.pose_name)
    if not long_rows:
        print(f"❌ {root} 에서 읽을 게 없다 — 러너를 먼저 돌릴 것")
        return 2
    out.mkdir(parents=True, exist_ok=True)

    write_csv(out / "frames.csv", [flatten_capture(r) for r in cap_rows])
    write_csv(out / "metrics_long.csv", long_rows)
    summ = summarize(present, long_rows)
    rep = repeatability(long_rows, list(present))
    figs = figures(out, present, long_rows, cap_rows, rep, args.gate_deg)
    (out / "summary.json").write_text(json.dumps(
        {"root": str(root), "variants": list(present), "n_frames": len(cap_rows),
         "summary": summ, "repeatability": rep}, indent=2, ensure_ascii=False))
    md = summary_md(root, summ, rep, cap_rows, figs)
    (out / "summary.md").write_text(md)
    print(md)
    print(f"→ {out}/  ({', '.join(['frames.csv', 'metrics_long.csv', 'summary.json', 'summary.md'] + figs)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
