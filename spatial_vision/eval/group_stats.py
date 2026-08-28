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
    stats/traffic.png         ★ **신호등 (프레임 × [촬영3 + 변형])** — 🔴 칸을 한눈에
                              🔴 **순위표가 아니라 «고장 표시» 다** (아래 `traffic()` 주석)
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

from spatial_vision.contracts import rotation_angle_deg

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


# 🔴 `arccos((tr−1)/2)` 는 항등 근처에서 오차를 **제곱근으로 증폭**한다 — 저장된 R 이
#    정확히 직교가 아니라(9자리 반올림) **자기 자신과 비교해도 0.03° 가 나왔다**
#    (실측 p90 0.028° · 최대 0.049°, 2026-08-19). 정본은 `contracts.rotation_angle_deg`.
def ang_deg(A, B):
    return rotation_angle_deg(A, B)


# ─────────────────────────────────────────────────────────── 수집

def collect(root: Path, variants: list[str], pose_name: str,
            alias: dict | None = None) -> tuple[dict, list[dict], list[dict]]:
    """`alias` : `{변형id: (pose 디렉토리, pose 파일명)}`.

    🔴 **«정합 off» 팔(A3·I3·T3)이 여기 필요하다.** 그 팔들은 `<root>/A3/` 같은 자기 디렉토리가
       없고 pose 가 `fp_ns2/pose_coarse.json` 에 있다. 그래서 그냥 `--variants` 에 넣으면
       «pose 없음» 으로 잡혀 **신호등이 ⬛ 로, CSV 가 빈 줄로** 나온다 — 실제로는 정상 동작하는,
       심지어 sim GT 채점에서 **1~3위였던** 팔들이다(§35-2o-6). 별칭으로 실제 위치를 알려 준다.
    """
    diag = _load(root / "diag" / "diag_metrics.json") or {}
    cap_rows = diag.get("frames", [])
    frames = [r["frame"] for r in cap_rows]

    long_rows: list[dict] = []
    present: dict[str, dict] = {}
    alias = alias or {}
    for vid in variants:
        pdir, pname = alias.get(vid, (root / vid, pose_name))
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
            T = _load(Path(pdir) / fn / pname)
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


# ─────────────────────────────────────────────────────────── 신호등 (프레임 × 변형)

# 🔴🔴 **이건 «순위표» 가 아니라 «고장 표시» 다.**
#    GT 가 없으면 살아남은 것들 중 «어느 쪽이 더 정확한가» 는 프레임 단위로 원리적으로 못 정한다:
#    적합도 rms 는 실패와 성공의 분포가 **완전히 겹치고**(교훈 #56), 좌우 일관성은 프레임당
#    분해능이 ±1~2mm 이며(§35), 게이트는 계통 편향을 못 본다(교훈 #64).
#    여기서 하는 일은 **«이 칸은 깨졌다» 를 40×9 격자에서 한눈에 찾는 것**까지다.
LEVELS = ["🟢", "🟡", "🔴", "⬛"]              # 0 정상 · 1 주의 · 2 고장 · 3 없음/미측정
LEVEL_RGB = ["#A5D6A7", "#FFE082", "#EF9A9A", "#BDBDBD"]

# 임계값. ⚠️ **절대 기준이 아니다** — 촬영 조건별 지표(노출·마스크·depth)는 런 자기 자신을
#    기준으로 하는 강건 z-score 를 쓴다(§35-2l-8b: 기준선이 없어 도메인 갭에 면역인 쪽).
#    변형별 지표만 절대값을 쓰는데, 그 눈금은 §35-2m-6(이동량 10mm)·§35(좌우 dz) 에서 왔다.
THR = {"moved_mm_warn": 10.0, "moved_mm_bad": 20.0, "moved_deg_bad": 10.0,
       "ddx_warn": 2.0, "ddx_bad": 5.0, "corr_frac_warn": 0.3, "rz_warn": 3.5, "rz_bad": 6.0}


def _rz(vals: list) -> np.ndarray:
    """강건 z-score (중앙값·MAD). **런 자기 자신이 기준**이라 sim↔real 갭에 면역이다.

    🔴 **MAD 가 0 이면 눈이 먼다** (2026-08-27 수정). 값의 **과반이 똑같으면** MAD=0 이 되어
    나머지가 아무리 튀어도 전부 `z=0` 을 돌려줬다 — `n_corr`·`valid_frac` 처럼 값이 뭉치는
    열에서 실제로 생긴다(«이상치가 없다» 가 아니라 «이상치를 못 본다» 다).
    → MAD=0 이면 **IQR** 로 물러난다(값의 과반만 뭉친 흔한 경우가 여기서 회복된다).

    🔴 **표준편차로는 물러나지 않는다.** 표본 std 기반 z 는 구조적으로 `(n−1)/√n` 을 못 넘어서
    **n < 14 면 3.5 문턱에 원리적으로 도달할 수 없다**(n=7 이면 최대 2.27). 이상치가 스스로
    std 를 부풀리는 masking 이다 — 우리 런은 5~40프레임이라 정확히 그 구간에 있다.

    ★ MAD·IQR 이 **둘 다 0** = 핵심이 완전히 뭉쳤다 → «몇 σ» 가 정의되지 않는다. 이때는
      **중앙값의 1% 를 1σ 로** 본다(상대 편차 규칙). 그러면 `[10]*6+[30]` 은 z=200 으로 잡히고
      `[1.0]*4+[0.999]`(유효율 0.1% 차)는 z=0.1 로 안 잡힌다 — 3.5σ ≈ **중앙값의 3.5% 차이**다.
      ⚠️ 중앙값이 0 인 열에서는 이 규칙이 무뎌진다(절대 하한 1.0 을 쓴다). 우리 지표엔 그런 열이 없다.
    """
    v = np.array([np.nan if x is None else float(x) for x in vals], float)
    ok = np.isfinite(v)
    if ok.sum() < 3:
        return np.zeros_like(v)
    med = np.median(v[ok])
    mad = np.median(np.abs(v[ok] - med))
    scale = mad / 0.6745 if mad > 1e-9 else 0.0
    if scale <= 0.0:                                    # ← MAD 축퇴. IQR 로 물러난다
        q1, q3 = np.percentile(v[ok], [25, 75])
        scale = (q3 - q1) / 1.349 if (q3 - q1) > 1e-9 else 0.0
    if scale <= 0.0:                                    # ← 둘 다 축퇴. 상대 편차 규칙
        if not np.any(np.abs(v[ok] - med) > 1e-12):
            return np.zeros_like(v)                     # 진짜로 전부 같다 = 이상치 없음
        scale = 0.01 * max(abs(med), 1.0)
    return np.where(ok, (v - med) / scale, 0.0)


def traffic(long_rows: list[dict], cap_rows: list[dict], variants: list[str]) -> dict:
    """(프레임 × [촬영 3열 + 변형들]) 격자. 칸마다 `(레벨, 표시값, 이유)`."""
    frames = [r["frame"] for r in cap_rows] or sorted({r["frame"] for r in long_rows})
    by = {(r["frame"], r["variant"]): r for r in long_rows}

    cap = {r["frame"]: flatten_capture(r) for r in cap_rows}
    rz = {k: dict(zip(frames, _rz([cap.get(f, {}).get(k) for f in frames])))
          for k in ("img_med", "full_dia_px", "plane_rms_mm")}

    cols = ["노출", "마스크", "depth"] + variants
    grid: dict[str, list] = {}
    for f in frames:
        c, row = cap.get(f, {}), []

        # ① 노출 — 포화·암부는 절대 기준(센서 물리), 밝기 자체는 런 상대
        sat, dark, med = c.get("sat_pct"), c.get("dark_pct"), c.get("img_med")
        lv, why = 0, "ok"
        if med is None:
            lv, why = 3, "미측정"
        elif (sat or 0) > 2.0:
            lv, why = 2, f"포화 {sat:.1f}%"
        elif abs(rz["img_med"].get(f, 0)) > THR["rz_bad"]:
            lv, why = 1, f"밝기 이상치 z{rz['img_med'][f]:+.1f}"
        elif (dark or 0) > 60:
            lv, why = 1, f"암부 {dark:.0f}%"
        row.append((lv, f"{med:.0f}" if med is not None else "-", why))

        # ② 마스크 — 등가지름이 런 안에서 튀면 «다른 걸 집었거나 잘렸다»
        d, z = c.get("full_dia_px"), abs(rz["full_dia_px"].get(f, 0))
        lv, why = (3, "미측정") if d is None else \
            (2, f"지름 이상치 z{z:.1f}") if z > THR["rz_bad"] else \
            (1, f"지름 z{z:.1f}") if z > THR["rz_warn"] else (0, "ok")
        row.append((lv, f"{d:.0f}" if d else "-", why))

        # ③ depth — 평면 잔차(스테레오 관통 품질) + 주변 링 유효율
        pr, vr = c.get("plane_rms_mm"), c.get("valid_ring")
        z = abs(rz["plane_rms_mm"].get(f, 0))
        lv, why = (3, "미측정") if pr is None else \
            (2, f"링 유효 {100 * vr:.0f}%") if (vr is not None and vr < 0.5) else \
            (2, f"평면잔차 z{z:.1f}") if z > THR["rz_bad"] else \
            (1, f"평면잔차 z{z:.1f}") if z > THR["rz_warn"] else (0, "ok")
        row.append((lv, f"{pr:.2f}" if pr is not None else "-", why))

        # ④ 변형들
        corr_med = {v: np.median([x["n_corr"] for x in long_rows
                                  if x["variant"] == v and x.get("n_corr")] or [0]) for v in variants}
        for v in variants:
            r = by.get((f, v))
            if r is None or r.get("tz_mm") is None:
                row.append((3, "없음", "pose 없음"))
                continue
            mm, dg = r.get("moved_mm"), r.get("moved_deg")
            ddx = abs(r["ddx_px"]) if r.get("ddx_px") is not None else None
            nc = r.get("n_corr")
            lv, why = 0, "ok"
            if dg is not None and dg >= THR["moved_deg_bad"]:
                lv, why = 2, f"이동 {dg:.1f}°"
            elif mm is not None and mm >= THR["moved_mm_bad"]:
                lv, why = 2, f"이동 {mm:.1f}mm"
            elif ddx is not None and ddx >= THR["ddx_bad"]:
                lv, why = 2, f"좌우 {ddx:.1f}px"
            elif mm is not None and mm >= THR["moved_mm_warn"]:
                lv, why = 1, f"이동 {mm:.1f}mm"
            elif ddx is not None and ddx >= THR["ddx_warn"]:
                lv, why = 1, f"좌우 {ddx:.1f}px"
            elif nc and corr_med[v] and nc < THR["corr_frac_warn"] * corr_med[v]:
                lv, why = 1, f"대응점 {nc:.0f}"
            elif r.get("gated"):
                lv, why = 1, "게이트 후퇴"
            # ⚠️ 칸의 숫자는 **판정을 내린 그 값**이어야 한다. 늘 `moved_mm` 을 찍었더니
            #    회전으로 🔴 가 된 칸에 «5.6» 이 찍혀 표와 이유가 어긋났다.
            txt = (f"{mm:.1f}" if mm is not None else "·") if lv == 0 else \
                why.replace("이동 ", "").replace("좌우 ", "LR ") \
                   .replace("대응점 ", "n").replace("게이트 후퇴", "GATE")
            row.append((lv, txt, why))
        grid[f] = row
    return {"frames": frames, "cols": cols, "grid": grid, "thresholds": THR}


def traffic_md(tr: dict) -> list[str]:
    L = ["## 신호등 — 프레임 × 변형 (고장 표시)\n",
         "🔴🔴 **«순위표» 가 아니라 «고장 표시» 다.** GT 가 없으면 *살아남은 것들 중* 어느 쪽이 더 "
         "정확한지는 **프레임 단위로 원리적으로 못 정한다** — rms 는 실패·성공 분포가 겹치고"
         "(교훈 #56), 좌우 일관성은 프레임당 ±1~2mm 이며(§35), 게이트는 계통 편향을 못 본다"
         "(교훈 #64). 여기서 찾는 것은 **«깨진 칸이 어디인가»** 까지다.\n",
         "🟢 정상 · 🟡 주의 · 🔴 고장 · ⬛ pose 없음/미측정 &nbsp;|&nbsp; "
         "촬영 3열(노출·마스크·depth)은 **런 자기 자신 기준 강건 z-score** — 도메인 갭에 면역이다.\n",
         "| 프레임 | " + " | ".join(tr["cols"]) + " |",
         "|---" * (len(tr["cols"]) + 1) + "|"]
    for f in tr["frames"]:
        cells = [f"{LEVELS[lv]} {txt}" for lv, txt, _ in tr["grid"][f]]
        L.append(f"| {f.replace('frame_', '')} | " + " | ".join(cells) + " |")
    bad = [(f, tr["cols"][i], why) for f in tr["frames"]
           for i, (lv, _, why) in enumerate(tr["grid"][f]) if lv == 2]
    L.append("")
    if bad:
        L.append("### 🔴 칸 목록 — **여기부터 연다**\n")
        for f, c, why in bad[:40]:
            L.append(f"- `{f}` · **{c}** — {why}")
        if len(bad) > 40:
            L.append(f"- … 외 {len(bad) - 40}칸")
    else:
        L.append("✅ 🔴 칸 없음. ⚠️ **«전부 맞다» 가 아니라 «이 지표들로는 안 걸린다» 다** — "
                 "«다 같이 같은 방향으로 틀린» 경우는 이 표가 원리적으로 못 잡는다(오버레이 육안이 그 몫).")
    L.append("")
    return L


def figures(out: Path, present: dict, long_rows: list[dict], cap_rows: list[dict],
            rep: dict, gate_deg: float, tr: dict | None = None) -> list[str]:
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

    # ★★ 신호등 격자 — 40×12 를 한 장에. **칸의 숫자는 «주된 값», 색은 «판정»** 이다.
    if tr and tr["frames"]:
        fr, cols = tr["frames"], tr["cols"]
        nr, nc = len(fr), len(cols)
        fig, ax = plt.subplots(figsize=(1.05 * nc + 1.6, 0.30 * nr + 1.6))
        for i, f in enumerate(fr):
            for j, (lv, txt, _) in enumerate(tr["grid"][f]):
                ax.add_patch(plt.Rectangle((j, nr - 1 - i), 1, 1, facecolor=LEVEL_RGB[lv],
                                           edgecolor="white", lw=1.2))
                # ⚠️ matplotlib 에 한글 폰트가 없다 — 한글이 들어간 표시값은 두부가 된다.
                ax.text(j + 0.5, nr - 0.5 - i, txt.replace("없음", "none"),
                        ha="center", va="center", fontsize=6.5)
        ax.set_xlim(0, nc)
        ax.set_ylim(0, nr)
        ax.set_xticks(np.arange(nc) + 0.5)
        # ⚠️ 라벨은 영문 — matplotlib 에 한글 폰트가 없다. 한글판은 `summary.md` 표를 본다.
        ax.set_xticklabels(["expo", "mask", "depth"] + cols[3:], fontsize=7.5, rotation=20)
        ax.xaxis.set_ticks_position("top")
        ax.set_yticks(np.arange(nr) + 0.5)
        ax.set_yticklabels([f.replace("frame_", "") for f in reversed(fr)], fontsize=6.5)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(length=0)
        ax.set_title("FAILURE FLAGS, not a ranking  —  green ok / yellow watch / red broken / "
                     "gray missing\ncapture cols use robust z within this run (domain-gap immune)",
                     fontsize=8.5, pad=26)
        fig.tight_layout()
        fig.savefig(out / "traffic.png", dpi=150)
        plt.close(fig)
        made.append("traffic.png")
    return made


def summary_md(root: Path, summ: dict, rep: dict, cap_rows: list[dict], figs: list[str],
               tr: dict | None = None) -> str:
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
    if tr:
        L += traffic_md(tr)
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
    ap.add_argument("--alias", action="append", default=[],
                    help="`변형id=디렉토리:파일명`. 자기 디렉토리가 없는 팔(A3·I3·T3 = 정합 off)의 "
                         "pose 위치를 알려 준다. 예 `--alias A3=fp_ns2:pose_coarse.json`. "
                         "🔴 없으면 그 팔이 «pose 없음» 으로 잡혀 신호등이 ⬛ 가 된다")
    ap.add_argument("--gate-deg", type=float, default=1.5)
    args = ap.parse_args(argv)

    root = Path(args.root)
    out = Path(args.out) if args.out else root / "stats"
    variants = [s.strip() for s in args.variants.split(",") if s.strip()]
    alias = {}
    for spec in args.alias:
        vid, _, rest = spec.partition("=")
        d, _, nm = rest.partition(":")
        alias[vid.strip()] = (root / d.strip(), nm.strip() or args.pose_name)
    present, cap_rows, long_rows = collect(root, variants, args.pose_name, alias)
    if not long_rows:
        print(f"❌ {root} 에서 읽을 게 없다 — 러너를 먼저 돌릴 것")
        return 2
    out.mkdir(parents=True, exist_ok=True)

    write_csv(out / "frames.csv", [flatten_capture(r) for r in cap_rows])
    write_csv(out / "metrics_long.csv", long_rows)
    summ = summarize(present, long_rows)
    rep = repeatability(long_rows, list(present))
    tr = traffic(long_rows, cap_rows, list(present))
    figs = figures(out, present, long_rows, cap_rows, rep, args.gate_deg, tr)
    (out / "summary.json").write_text(json.dumps(
        {"root": str(root), "variants": list(present), "n_frames": len(cap_rows),
         "summary": summ, "repeatability": rep,
         "traffic": {"cols": tr["cols"], "thresholds": tr["thresholds"],
                     "grid": {f: [{"level": lv, "value": v, "why": w}
                                  for lv, v, w in tr["grid"][f]] for f in tr["frames"]}}},
        indent=2, ensure_ascii=False))
    md = summary_md(root, summ, rep, cap_rows, figs, tr)
    (out / "summary.md").write_text(md)
    print(md)
    print(f"→ {out}/  ({', '.join(['frames.csv', 'metrics_long.csv', 'summary.json', 'summary.md'] + figs)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
