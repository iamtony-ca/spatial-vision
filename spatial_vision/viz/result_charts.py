"""러너 산출물(JSON·CSV)을 **판단용 그림 3종**으로 낸다 — 추가 촬영 0, 계산 수 초.

    envs/pose/bin/python -m spatial_vision.viz.result_charts --root runs/real01_A

왜 필요한가
    러너는 이미 `report.md`(표)·`metrics_long.csv`(원자료)를 낸다. 그런데 **다른 PC 에서 결과만
    보고 판단**하려면 표를 읽기 전에 *«어디가 깨졌나»* 가 한눈에 들어와야 한다. 기존 그림
    (`variants.png`·`traffic.png`·`diag_trends.png`)이 못 보여 주는 축이 셋 있다:

    ① **거리 4다리** — 지금은 리포트의 «한 줄» 이다. 그런데 `FP z` 와 `stereo depth` 는
       **둘 다 `Z = fx·B/disparity`** 라 `fx·B` 가 틀리면 **같이** 틀린다(교훈 #89).
       실루엣 다리는 `baseline` 비의존, 줄자는 완전 외부 — **네 선이 어디서 갈라지는지**가
       곧 진단이다. 선으로 겹쳐 그려야 보인다.
    ② **팔 서열** — 좌우 |Δdx| 는 **실제 KPI 와 상관 r = −0.94 로, 팔 서열을 맞히는 유일한
       GT-free 지표**다(§35-2o-6b). 그런데 `variants.png` 4패널 중 한 칸의 상자그림이라
       30팔이면 x축이 뭉개진다. **정렬된 가로 막대**로 따로 뽑는다.
    ③ **프레임 × 팔 히트맵** — 상자그림은 **행 효과와 열 효과를 뭉갠다.**
       «이 프레임이 어려운가»(가로줄) 와 «이 팔이 나쁜가»(세로줄) 는 히트맵 + 주변 중앙값에서만
       갈린다. `traffic.png` 는 3단계 색이라 연속값 패턴이 안 보인다.

입력 (있는 것만 쓴다 — 없으면 그 그림만 건너뛴다)
    <root>/report.json                프레임별 `z_mm`(FP) · `depth_plane_mm`(stereo 평면적합) · 줄자
    <root>/scale_check.json           프레임별 `z_silhouette_mm` (실루엣 다리)
    <root>/stats/metrics_long.csv     프레임 × 팔 (ddx_px · moved_mm · gated · n_corr …)

산출 → `<root>/stats/`
    distance.png    ★ 거리 4다리 대조 (프레임축 + FP 대비 차)
    ranking.png     ★ 팔 서열 (|Δdx| 중앙, 정렬) — ⬛전량후퇴 · Z고정 · 초기값다름 표시
    heatmap.png     ★ 프레임 × 팔 (|Δdx| · 이동량) + 주변 중앙값

🔴 **서열은 «런 단위» 에서만 낸다.** 프레임 단위 우열은 GT 없이 원리적으로 못 정한다
   (rms 는 성공·실패 분포가 겹치고 #56, 좌우 일관성은 프레임당 ±1~2mm, 게이트는 계통 편향을
   못 본다 #64). 그래서 ③은 «서열» 이 아니라 **«패턴 찾기»** 용이다.
⚠️ 라벨은 **영문**이다 — matplotlib 에 한글 폰트가 없다(`viz.dim_sheet` 과 같은 제약).
   한글 해설은 `report.md` · `stats/summary.md` 가 담당한다.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

# 전량 후퇴(게이트 100%)면 그 팔의 지표는 **자기 결과가 아니라 초기값**이다 — 반드시 표시한다.
GATED_ALL_HATCH = "///"
KPI_T_MM = 5.0          # 배포 KPI (translation) — 거리 그림의 참조 밴드


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _f(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def read_long(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open() as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["gated"] = str(r.get("gated", "")).lower() == "true"
        for k in ("ddx_px", "ddy_px", "dz_mm", "moved_mm", "moved_deg", "rms_px", "n_corr"):
            r[k] = _f(r.get(k))
    return rows


def arm_flags(vid: str, rows: list[dict], fix_z_run: bool) -> tuple[str, str]:
    """(표시 접미사, 색 구분키). 🔴 **경고가 없는 팔과 시각적으로 달라야** 오독을 막는다.

    🔴🔴 **문턱은 100% 가 아니라 «과반» 이다.** 후퇴율 50% 를 넘으면 **중앙값이 후퇴 프레임에서
    나오므로** 그 막대는 «그 팔의 결과» 가 아니라 사실상 **초기값**이다. 실측에서
    A2a(후퇴 19/20)의 \\|Δdx\\| 중앙이 A3(정합 off)와 **소수점까지 같게**(0.695) 나왔다 —
    100% 기준만 걸었더니 정확히 이 오독을 못 막았다.
    """
    g = [r for r in rows if r["variant"] == vid]
    gp = 100.0 * sum(1 for r in g if r["gated"]) / max(len(g), 1)
    tags = []
    if g and all(r["gated"] for r in g):
        tags.append("*all-gated")
    elif gp >= 50.0:
        tags.append(f"*gated {gp:.0f}% (med=init)")
    if vid == "Cz" or fix_z_run:
        tags.append("Z-fixed")
    if vid.startswith("R_") or vid.startswith("Rn"):
        tags.append("init!=")           # 참조가 달라 «초기값이 다른» 비교다(교훈 #82)
    kind = ("gated" if any(t.startswith("*") for t in tags) else
            "zfix" if "Z-fixed" in tags else
            "refs" if "init!=" in tags else "ok")
    return (" " + " ".join(tags) if tags else ""), kind


# ─────────────────────────────────────────────────────────── ① 거리 4다리

def distance_png(root: Path, out: Path) -> str | None:
    """`FP z` · `stereo 평면` · `실루엣` · `줄자` 를 한 축에.

    🔴 **앞의 둘은 독립이 아니다** — 둘 다 `fx·B/disparity` 다(교훈 #89). 그래서 그 둘만
       일치하는 것은 «검증» 이 아니다. 세 번째 다리(실루엣)는 `baseline` 비의존이고,
       **`fx` 오차는 넷 중 줄자만 잡는다**(순수 스케일이라 내부 관측 전부를 통과한다).
    """
    import matplotlib.pyplot as plt

    rep = _load(root / "report.json") or {}
    cap = (rep.get("capture") or {}).get("frames") or []
    if not cap:
        return None
    sc = _load(root / "scale_check.json") or {}
    sil = {r["frame"]: _f(r.get("z_silhouette_mm")) for r in (sc.get("frames") or [])}
    # 🔴🔴 **실루엣 다리는 «자기 pose» 와만 뺄 수 있다.** `scale_check` 는 `fp_ism`(I 경로)를 쓰는데
    #    `FP z` 는 `fp_ns2`(A 경로)에서 온다 — 초판이 이 둘을 빼서 **잔차 +0.75mm 를 +1.50mm 로**
    #    부풀렸다. 두 경로가 20mm 어긋난 런이었다면 *"실루엣이 갈라졌다 → baseline 이 틀렸다"* 는
    #    **완전히 틀린 처방**이 나온다. 교훈 #26(비교 전에 «같은 양인가»부터)의 재발이라 출처를 명시한다.
    sil_pose = {r["frame"]: _f(r.get("z_pose_mm")) for r in (sc.get("frames") or [])}
    fp_src = rep.get("capture_pose_dir") or "FP"
    sil_src = Path(sc["pose_dir"]).name if sc.get("pose_dir") else fp_src
    mixed = bool(sil) and sil_src != fp_src

    fr = [r["frame"] for r in cap]
    x = np.arange(len(fr))
    zfp = np.array([_f(r.get("z_mm")) or np.nan for r in cap], float)
    zst = np.array([_f(r.get("depth_plane_mm")) or np.nan for r in cap], float)
    zsi = np.array([sil.get(f) if sil.get(f) is not None else np.nan for f in fr], float)
    zsp = np.array([sil_pose.get(f) if sil_pose.get(f) is not None else np.nan for f in fr], float)
    ruler = _f(rep.get("true_distance_mm"))

    fig, ax = plt.subplots(2, 1, figsize=(max(7.5, len(fr) * 0.42), 7.0), sharex=True,
                           gridspec_kw={"height_ratios": [1.25, 1.0]})
    ax[0].plot(x, zfp, "o-", ms=3.4, lw=1.3, color="#4C78A8", label=f"FP pose z [{fp_src}]")
    ax[0].plot(x, zst, "s-", ms=3.2, lw=1.2, color="#72B7B2",
               label="stereo depth (flange plane fit)")
    if np.isfinite(zsi).any():
        if mixed:      # 실루엣이 쓴 pose 를 **같이** 그린다 — 안 그리면 두 경로 차가 실루엣 오차로 보인다
            ax[0].plot(x, zsp, "o--", ms=2.6, lw=1.0, color="#9467BD", alpha=0.85,
                       label=f"pose z used by silhouette [{sil_src}]")
        ax[0].plot(x, zsi, "^-", ms=3.4, lw=1.3, color="#E45756",
                   label=f"silhouette, baseline-free [{sil_src}] (n={int(np.isfinite(zsi).sum())})")
    if ruler:
        ax[0].axhline(ruler, color="black", ls="--", lw=1.3, label=f"tape measure {ruler:.0f}mm")
    # 중앙값 요약 — **같은 프레임 부분집합에서** 낸다. 실루엣은 잘림·이상비로 일부 프레임을 버리므로
    # 전 프레임 중앙값과 나란히 놓으면 «부분집합 차이» 가 «편향» 으로 보인다(교훈 #26).
    ok = np.isfinite(zsi) if np.isfinite(zsi).any() else np.isfinite(zfp)
    def _m(v, mask=None):
        w = v[mask] if mask is not None else v
        return f"{np.nanmedian(w):.0f}" if np.isfinite(w).any() else "-"
    med_txt = (f"medians over the {int(ok.sum())} frames the silhouette could use (mm):  "
               f"FP[{fp_src}] {_m(zfp, ok)} · stereo {_m(zst, ok)} · "
               f"silhouette[{sil_src}] {_m(zsi, ok)}"
               + (f" · pose[{sil_src}] {_m(zsp, ok)}" if mixed else "")
               + (f" · tape {ruler:.0f}" if ruler else ""))
    if int(ok.sum()) != len(fr):
        med_txt += f"\nall {len(fr)} frames:  FP {_m(zfp)} · stereo {_m(zst)}"
    if mixed:
        med_txt += ("\n[!] the silhouette leg uses a DIFFERENT path's pose - its residual is "
                    f"taken against pose[{sil_src}], not against FP[{fp_src}]")
    ax[0].set_ylabel("distance to flange top-center (mm)", fontsize=8)
    ax[0].set_title("FOUR LEGS on the same distance  —  they must agree, and two of them "
                    "CANNOT disagree\n"
                    "FP z and stereo depth are both fx*B/disparity: a wrong fx*B moves them "
                    "together (lesson #89)", fontsize=9)
    ax[0].grid(alpha=0.25, lw=0.5)
    ax[0].legend(fontsize=7.5, ncol=2, loc="lower right", framealpha=0.92)
    ax[0].tick_params(labelsize=7)

    # 아래 — FP 기준 차. **절대값보다 «어느 다리가 갈라지나» 가 진단**이다.
    ax[1].axhspan(-KPI_T_MM, KPI_T_MM, color="#4C78A8", alpha=0.08,
                  label=f"KPI +-{KPI_T_MM:g}mm")
    ax[1].axhline(0, color="#4C78A8", lw=1.2)
    ax[1].plot(x, zst - zfp, "s-", ms=3.2, lw=1.2, color="#72B7B2", label="stereo - FP")
    if np.isfinite(zsi).any():
        # 🔴 실루엣 잔차는 **그 자신이 쓴 pose** 와의 차다 — 다른 경로의 z 를 빼면 «경로 차» 가 섞인다.
        ref = zsp if mixed and np.isfinite(zsp).any() else zfp
        ax[1].plot(x, zsi - ref, "^-", ms=3.4, lw=1.3, color="#E45756",
                   label=f"silhouette - pose[{sil_src}]" if mixed else "silhouette - FP")
        if mixed:
            ax[1].plot(x, zsp - zfp, ":", lw=1.1, color="#9467BD",
                       label=f"path gap: pose[{sil_src}] - FP[{fp_src}]")
    # 🔴 줄자는 «한 값» 이다 — 프레임마다 거리가 달랐으면 `tape − FP` 는 **오차가 아니라 자세 변화**이고,
    #    그리면 축만 흔들어 나머지 두 다리의 일치를 가린다. **정지 구간에서만** 그린다(교훈 #26 의 정신:
    #    두 값을 비교하기 전에 «같은 양인가» 를 먼저 묻는다).
    spread = float(np.nanpercentile(zfp, 90) - np.nanpercentile(zfp, 10)) if np.isfinite(zfp).any() else 0.0
    static = spread <= 10.0
    if ruler and static:
        ax[1].plot(x, ruler - zfp, "--", lw=1.2, color="black", label="tape - FP")
    elif ruler:
        ax[1].plot([], [], "--", lw=1.2, color="black",
                   label=f"tape - FP: NOT drawn (rig moved, z spread {spread:.0f}mm)")
    ax[1].set_ylabel("difference from FP z (mm)", fontsize=8)
    ax[1].set_xlabel("frame index" + ("" if ruler else
                     "   (no tape measure given: --true-distance-mm is the ONLY external length)"),
                     fontsize=8)
    ax[1].set_title("silhouette splitting off  ->  baseline is wrong    |    "
                    "all three agree but tape disagrees  ->  fx is wrong (invisible internally)\n"
                    "tape is ONE number: if the rig moved between frames, compare medians only "
                    "(box above)", fontsize=8.5)
    # ⚠️ 이상치 하나가 축을 다 먹으면 «나머지가 일치한다» 는 정보가 사라진다 — 강건 범위로 자르고
    #    잘린 점은 **개수와 최댓값을 글로 남긴다**(조용히 숨기지 않는다).
    _sref = zsp if (mixed and np.isfinite(zsp).any()) else zfp
    dall = np.concatenate([v[np.isfinite(v)] for v in (zst - zfp, zsi - _sref) if np.isfinite(v).any()]
                          or [np.zeros(1)])
    lim = max(2.0 * KPI_T_MM, float(np.percentile(np.abs(dall), 90)) * 1.8)
    n_out = int((np.abs(dall) > lim).sum())
    ax[1].set_ylim(-lim, lim)
    if n_out:
        _d = zsi - _sref
        i_bad = int(np.nanargmax(np.abs(np.where(np.isfinite(_d), _d, 0))))
        ax[1].text(0.005, 0.03, f"{n_out} point(s) outside +-{lim:.0f}mm "
                                f"(worst {_d[i_bad]:+.0f}mm at frame {i_bad}) "
                                f"-> see top panel", transform=ax[1].transAxes, fontsize=7.5,
                   color="#B00020", va="bottom",
                   bbox={"fc": "white", "ec": "#B00020", "alpha": 0.9, "pad": 2.5})
    ax[1].grid(alpha=0.25, lw=0.5)
    ax[1].legend(fontsize=7.5, ncol=2, loc="upper right")
    ax[1].tick_params(labelsize=7)
    ax[1].set_xticks(x[:: max(1, len(fr) // 24)])

    fig.tight_layout()
    # 요약은 **그림 밖 아래**에 둔다 — 축 안에 두면 팔·프레임이 늘 때 범례·선에 덮인다.
    fig.text(0.01, -0.005, med_txt, fontsize=7.5, va="top", ha="left",
             color="#B00020" if mixed else "#333333",
             bbox={"fc": "white", "ec": "#B00020" if mixed else "#cccccc", "alpha": 0.95, "pad": 3})
    fig.savefig(out / "distance.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return "distance.png"


# ─────────────────────────────────────────────────────────── ② 팔 서열

def ranking_png(rows: list[dict], out: Path, fix_z_run: bool) -> tuple[str, list[str]] | None:
    """좌우 |Δdx| 중앙값으로 팔을 **정렬해** 가로 막대로. 반환값의 둘째가 **정렬된 팔 순서**다.

    ★ 이 지표만 서열을 맞힌다(r = −0.94). 같이 재 본 나머지는 rms −0.05(무관) ·
      **게이트 후퇴율 +0.82(부호 반대!)** · 이동량 −0.32 였다(§35-2o-6b).
    """
    import matplotlib.pyplot as plt

    vids = []
    for r in rows:
        if r["variant"] not in vids:
            vids.append(r["variant"])
    stat = []
    for v in vids:
        d = np.array([abs(r["ddx_px"]) for r in rows
                      if r["variant"] == v and r["ddx_px"] is not None], float)
        if not len(d):
            continue
        g = [r for r in rows if r["variant"] == v]
        tag, kind = arm_flags(v, rows, fix_z_run)
        stat.append({"vid": v, "med": float(np.median(d)), "p90": float(np.percentile(d, 90)),
                     "n": len(d), "tag": tag, "kind": kind,
                     "gpct": 100.0 * sum(1 for r in g if r["gated"]) / max(len(g), 1)})
    if not stat:
        return None
    stat.sort(key=lambda s: s["med"])                       # 작을수록 좋다
    order = [s["vid"] for s in stat]

    col = {"ok": "#4C78A8", "gated": "#B0B0B0", "zfix": "#F58518", "refs": "#9D755D"}
    y = np.arange(len(stat))[::-1]                          # 위가 1등
    fig, ax = plt.subplots(figsize=(9.2, max(3.0, 0.34 * len(stat) + 2.0)))
    ax.barh(y, [s["med"] for s in stat], height=0.62,
            color=[col[s["kind"]] for s in stat],
            hatch=[GATED_ALL_HATCH if s["gpct"] >= 99.9 else "" for s in stat],
            edgecolor="white")
    for yy, s in zip(y, stat):
        ax.plot([s["med"], s["p90"]], [yy, yy], color="#333333", lw=1.0)
        ax.plot([s["p90"]], [yy], "|", color="#333333", ms=7)
        ax.text(s["p90"] + 0.05, yy, f"  med {s['med']:.2f} / p90 {s['p90']:.2f} px"
                                     f"   gate {s['gpct']:.0f}%", va="center", fontsize=7)
    ax.set_yticks(y)
    ax.set_yticklabels([s["vid"] + s["tag"] for s in stat], fontsize=8)
    ax.set_xlabel("|L-R projection mismatch dx| (px)   —   lower is better", fontsize=8.5)
    ax.set_xlim(0, max(s["p90"] for s in stat) * 1.45 + 0.1)
    ax.grid(alpha=0.25, lw=0.5, axis="x")
    ax.set_title("ARM RANKING (run level)  —  |dx| is the only GT-free metric that ranks arms\n"
                 "measured r = -0.94 vs true KPI;  rms -0.05 (useless),  "
                 "gate fallback +0.82 (SIGN FLIPPED),  moved -0.32", fontsize=9)
    # 🔴 표시가 붙은 팔은 «같은 조건의 비교» 가 아니다 — 범례에서 그 이유를 밝힌다.
    h = [plt.Rectangle((0, 0), 1, 1, color=col[k]) for k in ("ok", "gated", "zfix", "refs")]
    # 🔴 범례를 그래프 «밖» 에 둔다 — 안에 두면 팔이 많을 때 마지막 막대의 주석을 덮는다.
    ax.legend(h, ["comparable",
                  "*gated >=50%: the MEDIAN comes from fallback frames = the INITIAL pose",
                  "Z-fixed: moved/dz are structurally small",
                  "init!=: different reference set -> different initial pose (lesson #82)"],
              fontsize=7, loc="upper left", bbox_to_anchor=(0.0, -0.055), ncol=2,
              framealpha=0.9, borderaxespad=0.0,
              title="gate % is printed for context only - it is NOT a quality metric "
                    "(r = +0.82, sign flipped)", title_fontsize=7.5)
    fig.savefig(out / "ranking.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return "ranking.png", order


# ─────────────────────────────────────────────────────────── ③ 프레임 × 팔 히트맵

def _grid(rows: list[dict], frames: list[str], order: list[str], key: str,
          absolute: bool) -> np.ndarray:
    g = np.full((len(frames), len(order)), np.nan)
    fi = {f: i for i, f in enumerate(frames)}
    vi = {v: j for j, v in enumerate(order)}
    for r in rows:
        i, j, v = fi.get(r["frame"]), vi.get(r["variant"]), r.get(key)
        if i is not None and j is not None and v is not None:
            g[i, j] = abs(v) if absolute else v
    return g


def _nanmed(G: np.ndarray, axis: int) -> np.ndarray:
    """전부 NaN 인 행·열이 있어도 조용히 0 을 낸다 — 예: 정합을 안 하는 팔(A3·I3·T3)의 이동량."""
    n = np.isfinite(G).sum(axis=axis)
    m = np.zeros(G.shape[1 - axis])
    ok = n > 0
    if ok.any():
        sub = G[:, ok] if axis == 0 else G[ok, :]
        m[ok] = np.nanmedian(sub, axis=axis)
    return m


def heatmap_png(rows: list[dict], out: Path, order: list[str]) -> str | None:
    """프레임 × 팔. **주변 중앙값 띠**가 «행 효과(어려운 프레임)» 와 «열 효과(나쁜 팔)» 를 가른다."""
    import matplotlib.pyplot as plt
    from matplotlib import gridspec

    frames = []
    for r in rows:
        if r["frame"] not in frames:
            frames.append(r["frame"])
    frames.sort()
    if not frames or not order:
        return None
    gated = _grid([{**r, "g": 1.0 if r["gated"] else 0.0} for r in rows],
                  frames, order, "g", False)
    panels = [("|L-R dx| (px)  - lower better", _grid(rows, frames, order, "ddx_px", True), "magma_r"),
              ("contour moved (mm)", _grid(rows, frames, order, "moved_mm", False), "viridis")]

    nr, nc = len(frames), len(order)
    fig = plt.figure(figsize=(max(9.0, 0.46 * nc * len(panels) + 2.2), 0.26 * nr + 3.4))
    gs = gridspec.GridSpec(2, 2 * len(panels), figure=fig,
                           height_ratios=[nr, 1.6], width_ratios=[nc, 1.5] * len(panels),
                           hspace=0.04, wspace=0.16)
    for p, (title, G, cmap) in enumerate(panels):
        if not np.isfinite(G).any():
            continue
        vmax = float(np.nanpercentile(G, 95)) or 1.0     # 꼬리 하나가 색을 다 먹지 않게
        ax = fig.add_subplot(gs[0, 2 * p])
        im = ax.imshow(G, aspect="auto", cmap=cmap, vmin=0, vmax=vmax, interpolation="nearest")
        ys, xs = np.where(gated > 0.5)
        ax.plot(xs, ys, ".", color="white", ms=2.6, alpha=0.85)   # 흰 점 = 게이트 후퇴
        ax.set_xticks(np.arange(nc))
        ax.tick_params(labelbottom=False)      # 🔴 팔 이름은 아래 «열 효과» 축에만 — 겹치면 둘 다 못 읽는다
        ax.set_yticks(np.arange(nr))
        ax.set_yticklabels([f.replace("frame_", "") for f in frames], fontsize=6)
        ax.set_title(f"{title}\nwhite dot = gate fallback · blank cell = no data "
                     f"(e.g. arm runs no contour) · color clipped at p95", fontsize=8.5)
        fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01).ax.tick_params(labelsize=6.5)

        # 행 효과 — 프레임별 중앙값(팔 전체에 걸쳐). 가로로 길게 나오면 «그 프레임이 어렵다».
        axr = fig.add_subplot(gs[0, 2 * p + 1], sharey=ax)
        rmed = _nanmed(G, 1)
        axr.barh(np.arange(nr), rmed, height=0.75, color="#666666")
        axr.set_xlim(0, np.nanmax(rmed) * 1.15 + 1e-9)
        axr.tick_params(labelleft=False, labelsize=6)
        axr.set_title("frame\nmedian", fontsize=7)
        axr.grid(alpha=0.25, lw=0.4, axis="x")

        # 열 효과 — 팔별 중앙값. 세로로 길게 나오면 «그 팔이 나쁘다».
        axb = fig.add_subplot(gs[1, 2 * p], sharex=ax)
        cmed = _nanmed(G, 0)
        axb.bar(np.arange(nc), cmed, width=0.75, color="#333333")
        axb.set_ylim(0, np.nanmax(cmed) * 1.15 + 1e-9)
        axb.set_xticks(np.arange(nc))
        axb.set_xticklabels(order, fontsize=6.5, rotation=90)
        axb.tick_params(labelsize=6, labelbottom=True)
        axb.set_ylabel("arm\nmedian", fontsize=7)
        axb.grid(alpha=0.25, lw=0.4, axis="y")
    fig.suptitle("FRAME x ARM  —  separates 'this frame is hard' (row) from 'this arm is bad' "
                 "(column).  NOT a per-frame ranking: with no GT that is impossible "
                 "(lessons #56/#64)", fontsize=9)
    fig.savefig(out / "heatmap.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return "heatmap.png"


# ─────────────────────────────────────────────────────────── 진입점

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="러너 산출물 → 판단용 그림 3종")
    ap.add_argument("--root", required=True, help="run_group_a.py 의 --out 디렉토리")
    ap.add_argument("--out", default=None, help="기본 <root>/stats")
    ap.add_argument("--fix-z", action="store_true",
                    help="런 전체가 `--fix-z` 면 켠다 — 모든 팔에 «Z고정» 표시를 붙인다")
    a = ap.parse_args(argv)

    root = Path(a.root)
    out = Path(a.out) if a.out else root / "stats"
    out.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
    except Exception:
        print("❌ matplotlib 이 없다 — 그림을 건너뛴다")
        return 1

    made: list[str] = []
    d = distance_png(root, out)
    if d:
        made.append(d)
    else:
        # ⚠️ 조용히 넘어가지 않는다 — «그림이 없다» 와 «데이터가 없다» 는 다른 문제다(교훈 #21).
        print("⚠️ distance.png 건너뜀 — `report.json` 의 `capture.frames` 가 없다")

    rows = read_long(out / "metrics_long.csv")
    if not rows:
        print("⚠️ ranking/heatmap 건너뜀 — `stats/metrics_long.csv` 가 없다 "
              "(`eval.group_stats` 를 먼저 돌린다)")
    else:
        rk = ranking_png(rows, out, a.fix_z)
        if rk:
            made.append(rk[0])
            hm = heatmap_png(rows, out, rk[1])
            if hm:
                made.append(hm)
        else:
            print("⚠️ ranking 건너뜀 — 좌우 일관성(`lr/`)이 비어 있다")

    print(f"그림 {len(made)}장 → {out}/  ({', '.join(made) if made else '없음'})")
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
