"""프레임 하나를 **6패널로 펼쳐** 눈으로 원인을 찾는다 — 실환경 진단의 주력 도구.

    envs/pose/bin/python -m spatial_vision.viz.diag_sheet \
        --in runs/real01 --out runs/real01_A/diag \
        --seg-full runs/real01_A/seg_full --seg-flange runs/real01_A/seg \
        --depth-dir runs/real01_A/st \
        --pose-dir runs/real01_A/A1 --obj assets/obj/foup_300_semi_r2

왜 필요한가
    실환경에는 GT 가 없다. 지표(후퇴율·좌우 일관성·rms)는 *"결과들이 자기들끼리 맞는가"* 만 말하고
    **왜 틀렸는지**는 하나도 말하지 않는다. 분할이 0 인지, depth 가 안 뚫린 것인지, 노출이 나간 것인지는
    **단계별 산출물을 나란히 펼쳐 봐야** 갈린다. `viz.overlay_pose` 가 «맞는가» 를 본다면
    이 도구는 «어디서 깨졌는가» 를 본다.

패널 (왼쪽부터)
    1. 원본 `left.png`         — 밝기 중앙값·포화율·암부율. 🔴 분할이 0 이면 **여기부터** 본다
    2. `mask_full`            — FOUP 전체. 면적비·등가지름·조각 수
    3. `mask_flange`          — top flange. 면적비·등가지름 (목표 419px, §34-9)
    4. depth 컬러맵            — **물체 마스크 안에서** 구간을 잡는다. 무효(0)는 검정.
                                 ★ `flange plane rms` = 평면 적합 잔차 → **이 depth 로 pose 가 되는가**
    5. `valid` 또는 **`stage2` 입력** — `--panel5` 로 고른다.
       🔴 `valid` 는 **범위 검사일 뿐이라 거의 항상 100%** 다. `stage2` 는 **refiner 가 실제로 보는**
       «flange 로 가린 depth» 를 그린다(flange 안 무효는 마젠타로 남겨 «뚫림» 을 계속 볼 수 있다)
    6. pose 오버레이           — 초록 윤곽 + 축 삼각대 (`--pose-dir` 를 준 경우)

산출
    diag_<frame>.png   프레임마다 6패널 (기본은 시트에 든 것만, `--all` 이면 전부)
    diag_sheet.png     고른 프레임을 세로로 이어 붙인 시트
    diag_metrics.json  ★ **전 프레임**의 수치. 이미지 캡션과 같은 값이고 프레임 40장을
                       눈으로 훑는 대신 여기서 추세를 본다
    diag_trends.png    ★ 프레임 축 추이 5단 (등가지름·depth·평면잔차·유효율·이동량)

⚠️ **패널마다 «없음» 을 명시한다.** 산출물이 없는 것과 값이 0 인 것은 원인이 완전히 다른데
   빈 검은 패널로 그리면 구분이 안 된다.
⚠️ **depth 정규화 구간을 캡션에 찍는다.** 컬러맵은 상대값이라 구간을 모르면 아무 의미가 없고,
   프레임마다 구간이 달라 **색을 프레임 간에 비교하면 안 된다**.
🔴 **`valid` 100% 는 «뚫렸다» 가 아니다** — `valid` 는 `유한 && z_near ≤ d ≤ z_far` 범위 검사일 뿐이고
   (`contracts.py`) FoundationStereo 는 조밀 모델이라 반투명 표면에서 **틀린 값을 내도 100%** 다.
   판정은 **4번 패널의 «물체 depth 가 실제 거리인가» + 평면 잔차**로 한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from spatial_vision.viz.overlay_pose import draw_axes, load_pose, rot_deg, silhouette

# ⚠️ 패널을 가로로 이어 붙이므로 캡션 막대 높이는 **전 패널 공통**이어야 한다.
#    줄 수에 맞춰 늘리면 높이가 어긋나 concatenate 가 터진다 → 최대 3줄로 고정한다.
BAR_H = 50
TARGET_FLANGE_PX = 419.0        # §34-9 — 이 근처여야 정합 이득이 난다


# ─────────────────────────────────────────────────────────── 그리기 도구

def _bar(w: int, lines: list[tuple[str, tuple]], h: int = BAR_H) -> np.ndarray:
    bar = np.full((h, w, 3), 22, np.uint8)
    y = 14
    for txt, col in lines:
        fs = 0.44
        while fs > 0.24 and cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)[0][0] > w - 12:
            fs -= 0.03
        cv2.putText(bar, txt, (6, y), cv2.FONT_HERSHEY_SIMPLEX, fs, col, 1)
        y += 15
    return bar


def _panel(img, w, h, title, lines):
    return np.concatenate([_bar(w, [(title, (0, 255, 255))] + lines),
                           cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)], 0)


def _blank(w, h, title, why):
    """산출물이 없을 때. **회색 + 사유**를 찍는다 — 검은 패널은 «0» 과 구분이 안 된다."""
    p = np.full((h, w, 3), 52, np.uint8)
    cv2.putText(p, why, (12, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 150, 150), 1)
    return np.concatenate([_bar(w, [(title, (120, 120, 120)), ("— 없음 —", (120, 120, 120))]), p], 0)


def _imread(p: Path, flag=cv2.IMREAD_GRAYSCALE):
    return cv2.imread(str(p), flag) if p.exists() else None


# ─────────────────────────────────────────────────────────── 수치

def mask_stats(mask) -> dict | None:
    if mask is None:
        return None
    m = mask > 127
    area = int(m.sum())
    n, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return {"area_px": area, "area_pct": round(100 * area / m.size, 3),
            "dia_px": round(2 * float(np.sqrt(area / np.pi)), 1), "n_blobs": len(n)}


def plane_rms(depth_mm, mask, K):
    """flange 안 점들에 평면을 맞추고 잔차(rms, p90)를 mm 로 낸다.

    ★ **산포가 아니라 «평면 잔차» 로 재는 이유** — flange 는 평면이지만 비스듬히 보면 depth 범위가
      수십 mm 로 벌어진다(실측 p10~p90 70mm). 산포로 재면 **기울기와 노이즈가 안 갈린다.**
      평면을 맞추고 남은 잔차만이 *"이 depth 로 pose 를 낼 수 있는가"* 를 말한다.
    """
    if K is None or mask is None:
        return None
    ys, xs = np.nonzero(mask)
    if len(xs) < 200:
        return None
    if len(xs) > 40000:                        # 전수는 필요 없다 — **결정적으로** 솎는다
        k = np.linspace(0, len(xs) - 1, 40000).round().astype(int)
        ys, xs = ys[k], xs[k]
    z = depth_mm[ys, xs].astype(np.float64)
    P = np.stack([(xs - K[0, 2]) * z / K[0, 0], (ys - K[1, 2]) * z / K[1, 1], z], 1)
    r = None
    for _ in range(3):                         # 이상치가 평면을 끌지 않게 두 번 다시 맞춘다
        c = P.mean(0)
        n = np.linalg.svd(P - c, full_matrices=False)[2][-1]
        r = np.abs((P - c) @ n)
        keep = r <= max(3 * np.median(r), 1e-3)
        if keep.sum() < 100:
            break
        P, r = P[keep], r[keep]
    return {"rms_mm": round(float(np.sqrt((r**2).mean())), 3),
            "p90_mm": round(float(np.percentile(r, 90)), 3), "n_px": int(len(r))}


def frame_metrics(f: Path, a, mesh, K, hw) -> tuple[dict, dict]:
    """수치와 원자료를 같이 낸다 — 패널은 이 결과로만 그린다(계산을 두 번 하지 않는다)."""
    img = cv2.imread(str(f / "left.png"))

    def find(name, *dirs):
        """⚠️ 인자는 **프레임 디렉토리를 담은 루트**다. 프레임 디렉토리 자체를 넘기면
        `frame_0007/frame_0007/…` 을 보고 «없음» 이라 거짓말한다(실제로 한 번 그랬다)."""
        for d in dirs:
            if d is None:
                continue
            m = _imread(Path(d) / f.name / name)
            if m is not None and m.shape == hw:
                return m
        return None

    # 폴백 = 캡처 루트. sim 이면 GT 마스크가 거기 있고, 실환경이면 아무것도 없다
    m_full = find("mask_full.png", a.seg_full, f.parent)
    # 🔴 `RH1` 처럼 «분할이 아니라 CAD 투영» 으로 flange 마스크를 만드는 경로는 파일명이
    #    `mask_flange_proj.png` 다(`pose_fp.py` 가 pose 디렉토리에 쓴다). 실환경에는 GT 가 없으므로
    #    그 투영본이 **stage2 가 실제로 소비한 유일한 flange 마스크**다 → 이름을 받는다.
    m_fl = find(a.flange_name, a.seg_flange, f.parent)
    valid = find("valid.png", a.depth_dir)
    depth = None
    for cand in ([Path(a.depth_dir) / f.name / "depth.png"] if a.depth_dir else []) + [f / "depth_gt.png"]:
        if cand.exists():
            d = cv2.imread(str(cand), cv2.IMREAD_UNCHANGED)
            if d is not None and d.shape[:2] == hw:
                depth = d
                break

    fl = (m_fl > 127) if m_fl is not None else None
    ring = None
    if fl is not None and fl.any():
        ring = (cv2.dilate(fl.astype(np.uint8), np.ones((31, 31), np.uint8), iterations=3) > 0) & ~fl

    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    met: dict = {"frame": f.name,
                 "image": {"w": hw[1], "h": hw[0], "med": round(float(np.median(g)), 1),
                           "sat_pct": round(100 * float((g > 250).mean()), 3),
                           "dark_pct": round(100 * float((g < 5).mean()), 3)},
                 "mask_full": mask_stats(m_full), "mask_flange": mask_stats(m_fl)}

    v = (valid > 127) if valid is not None else (depth > 0 if depth is not None else None)
    if v is not None:
        met["valid"] = {
            "all": round(float(v.mean()), 4),
            "flange": round(float(v[fl].mean()), 4) if fl is not None and fl.any() else None,
            "ring": round(float(v[ring].mean()), 4) if ring is not None and ring.any() else None}

    dep: dict = {}
    if depth is not None and v is not None and v.any():
        d = depth.astype(np.float32)
        basis = (m_full > 127) if m_full is not None else (
            cv2.dilate(fl.astype(np.uint8), np.ones((25, 25), np.uint8), iterations=2) > 0
            if fl is not None and fl.any() else None)
        b = (basis & v) if basis is not None else None
        if b is not None and b.sum() > 200:
            lo, hi, src = *np.percentile(d[b], a.depth_pct), f"obj {a.depth_pct[0]:g}-{a.depth_pct[1]:g}%"
            if hi - lo < 40:                   # 정면 평면이면 구간이 붕괴한다 — 최소 폭을 준다
                c = 0.5 * (lo + hi); lo, hi = c - 20, c + 20
        else:
            lo, hi, src = *np.percentile(d[v], a.depth_pct), f"all {a.depth_pct[0]:g}-{a.depth_pct[1]:g}%"
        dep = {"scale_src": src, "scale_lo": round(float(lo), 1), "scale_hi": round(float(hi), 1),
               "med_all": round(float(np.median(d[v])), 1)}
        if fl is not None and (v & fl).any():
            dep["med_flange"] = round(float(np.median(d[v & fl])), 1)
            dep["plane"] = plane_rms(d, v & fl, K)
        met["depth"] = dep

    if a.pose_dir:
        T = load_pose(Path(a.pose_dir) / f.name / a.pose_name)
        if T is not None:
            p = {"z_mm": round(float(T[2, 3]), 1),
                 "gated": (Path(a.pose_dir) / f.name / "pose_contour_raw.json").exists()}
            T0 = load_pose(Path(a.pose_dir) / f.name / "pose_coarse.json")
            if T0 is not None and a.pose_name != "pose_coarse.json":
                p["moved_deg"] = round(rot_deg(T0, T), 3)
                p["moved_mm"] = round(float(np.linalg.norm(T0[:3, 3] - T[:3, 3])), 3)
            met["pose"] = p

    return met, {"img": img, "m_full": m_full, "m_fl": m_fl, "fl": fl,
                 "valid": v, "depth": depth, "mesh": mesh, "K": K}


# ─────────────────────────────────────────────────────────── 패널

def render_frame(f: Path, a, met: dict, raw: dict, w: int, h: int) -> np.ndarray:
    img, fl, v = raw["img"], raw["fl"], raw["valid"]
    i = met["image"]
    # ★ 패널을 «역할» 로 담고 마지막에 순서대로 꺼낸다 — `--order` 로 배치를 바꾸기 위해서다.
    #   🔴 `pipeline` 순서가 인과와 맞다: depth·mask_full 은 **서로 독립**이고 stage1 로 합쳐지며,
    #      **`mask_flange` 는 분할 산출물이 아니라 stage1 pose 를 CAD 로 투영한 것**이다(§3.6).
    #      기본(`default`)은 마스크 둘을 나란히 두는 옛 배치로, 러너 리포트 호환을 위해 남긴다.
    SEQ = (["img", "full", "flange", "depth", "valid", "pose"] if a.order == "default"
           else ["img", "depth", "full", "flange", "valid", "pose"])
    NO = {r: k + 1 for k, r in enumerate(SEQ)}
    P: dict = {}
    P["img"] = _panel(img, w, h, f"{NO['img']} {f.name}",
                      [(f"{i['w']}x{i['h']}  med {i['med']:.0f}  sat {i['sat_pct']:.1f}%  "
                        f"dark {i['dark_pct']:.1f}%", (200, 200, 200))])

    _msuf = {"full": " (SAM3) -> stage1", "flange": " (stage1 pose -> CAD proj) -> stage2"} \
        if a.order == "pipeline" else {"full": "", "flange": ""}
    for key, role, mask, col in (("mask_full", "full", raw["m_full"], (0, 220, 0)),
                                 ("mask_flange", "flange", raw["m_fl"], (0, 165, 255))):
        title = f"{NO[role]} {key}{_msuf[role]}"
        s = met.get(key)
        if s is None:
            P[role] = _blank(w, h, title, "분할 산출물 없음")
            continue
        m = mask > 127
        over = img.copy()
        over[m] = (0.45 * over[m] + 0.55 * np.array(col)).astype(np.uint8)
        cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(over, cs, -1, col, 3)
        extra = ""
        if key == "mask_flange" and s["dia_px"]:
            extra = f"  ({s['dia_px']/TARGET_FLANGE_PX:.2f}x target)"
        P[role] = _panel(over, w, h, title,
                         [(f"area {s['area_pct']:5.2f}%  dia {s['dia_px']:.0f}px  "
                           f"n={s['n_blobs']}{extra}",
                           (200, 200, 200) if s["area_px"] else (0, 140, 255))])

    dep = met.get("depth")
    if raw["depth"] is None or not dep:
        P["depth"] = _blank(w, h, f"{NO['depth']} depth", "stereo 산출물 없음")
    else:
        d = raw["depth"].astype(np.float32)
        lo, hi = dep["scale_lo"], dep["scale_hi"]
        n = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
        cm = cv2.applyColorMap((255 * (1 - n)).astype(np.uint8), cv2.COLORMAP_TURBO)
        cm[~v] = (18, 18, 18)                  # 무효 = 검정. 컬러맵 안의 어느 색과도 안 겹친다
        if fl is not None and fl.any():        # 물체 위치를 알아야 색을 해석할 수 있다
            cs, _ = cv2.findContours(fl.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(cm, cs, -1, (255, 255, 255), 2)
        # 🔴 이 패널은 **전 화면 raw depth** 다 — 데이터를 마스크로 자르지 않는다.
        #    다만 **색 구간을 물체 마스크 안에서** 잡으므로 배경이 한쪽 끝으로 포화돼 «잘린» 것처럼 보인다
        #    (배경 기준으로 잡으면 물체가 통째로 단색이 된다 — 그래서 이렇게 한다).
        lines = [(f"FULL frame · colour range from {dep['scale_src']} mask "
                  f"{lo:.0f}~{hi:.0f}mm (outside saturates)  all med {dep['med_all']:.0f}",
                  (200, 200, 200))]
        if "med_flange" in dep:
            s = f"flange med {dep['med_flange']:.0f}"
            if dep.get("plane"):
                s += f"  plane rms {dep['plane']['rms_mm']:.2f}mm  p90 {dep['plane']['p90_mm']:.2f}"
            lines.append((s, (0, 255, 255)))
        P["depth"] = _panel(cm, w, h, f"{NO['depth']} depth (mm) — raw, full frame"
                            + (" (stereo)" if a.order == "pipeline" else ""), lines)

    mv = met.get("valid", {})
    vstat = "  ".join(f"{k} {100*mv[k]:.1f}%" for k in ("all", "flange", "ring")
                      if mv.get(k) is not None)
    if v is None:
        P["valid"] = _blank(w, h, f"{NO['valid']} valid", "stereo 산출물 없음")
    elif a.panel5 == "valid":
        vi = np.zeros((*v.shape, 3), np.uint8)
        vi[v] = (235, 235, 235)
        vi[~v] = (200, 0, 200)                 # 마젠타 = 무효. 사진 어디에도 없는 색이라 눈에 띈다
        P["valid"] = _panel(vi, w, h, f"{NO['valid']} valid (magenta=invalid)", [(vstat, (200, 200, 200))])
    elif fl is None or not fl.any() or raw["depth"] is None or not met.get("depth"):
        P["valid"] = _blank(w, h, f"{NO['valid']} stage2 input", "flange 마스크 또는 depth 없음")
    else:
        # ★★ stage2 가 «실제로 먹는» 것 — `pose_fp.py:411` 의 `np.where(mf>127, depth, 0)` 그대로.
        #    🔴 `valid` 패널을 대체하되 **정보를 버리지 않는다**: flange 안의 무효 픽셀은 마젠타로 남긴다
        #    (반투명 몸체에서 stereo 가 뚫리는지 = 열린 항목 #1 을 보는 유일한 단서라서).
        dep = met["depth"]
        d = raw["depth"].astype(np.float32)
        din = fl & v                                       # flange ∧ 유효 = 네트워크에 들어가는 픽셀
        if din.any():                                      # 색 구간은 **flange 안에서만** 잡는다
            lo, hi = (float(x) for x in np.percentile(d[din], a.depth_pct))
        else:
            lo, hi = dep["scale_lo"], dep["scale_hi"]
        n = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
        cm = cv2.applyColorMap((255 * (1 - n)).astype(np.uint8), cv2.COLORMAP_TURBO)
        out = np.full((*fl.shape, 3), 24, np.uint8)        # flange 밖 = stage2 가 0 으로 지운 곳
        out[din] = cm[din]
        out[fl & ~v] = (200, 0, 200)                       # flange 안인데 무효 = 마젠타
        cs, _ = cv2.findContours(fl.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, cs, -1, (255, 255, 255), 2)
        lines = [(f"MASKED by flange · colour range from flange {lo:.0f}~{hi:.0f}mm  "
                  f"n={int(din.sum()):,}px  (outside = zeroed by stage2)", (200, 200, 200))]
        s2 = f"valid[flange] {100*mv.get('flange', float('nan')):.1f}%"
        if dep.get("plane"):
            s2 += f"   plane rms {dep['plane']['rms_mm']:.2f}mm  p90 {dep['plane']['p90_mm']:.2f}"
        lines.append((s2, (0, 255, 255)))
        P["valid"] = _panel(out, w, h, f"{NO['valid']} stage2 input depth (magenta=invalid)", lines)

    if a.pose_dir:
        T = load_pose(Path(a.pose_dir) / f.name / a.pose_name)
        if T is None or raw["mesh"] is None:
            P["pose"] = _blank(w, h, f"{NO['pose']} pose", "pose 없음")
        else:
            ov = img.copy()
            cs, _ = cv2.findContours(silhouette(raw["mesh"], T, raw["K"], img.shape[:2]),
                                     cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(ov, cs, -1, (0, 255, 0), 3)
            draw_axes(ov, T, raw["K"], 60.0)
            p = met["pose"]
            s = f"z {p['z_mm']:.0f}mm"
            if "moved_deg" in p:
                s += f"  moved {p['moved_deg']:.2f}deg"
            if p["gated"]:
                s += "  [GATED]"
            P["pose"] = _panel(ov, w, h, f"{NO['pose']} pose · {Path(a.pose_dir).name}", [(s, (200, 200, 200))])

    return np.concatenate([P[r] for r in SEQ if r in P], 1)


# ─────────────────────────────────────────────────────────── 추이

def trends_png(rows: list[dict], out: Path, gate_deg: float) -> bool:
    """프레임 축 추이. **40장을 눈으로 훑는 대신 여기서 이상 프레임을 찾아** 그 장만 연다."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False
    x = np.arange(len(rows))

    def col(*path, scale=1.0):
        out_ = []
        for r in rows:
            v = r
            for k in path:
                v = (v or {}).get(k) if isinstance(v, dict) else None
            out_.append(v * scale if isinstance(v, (int, float)) else np.nan)
        return np.array(out_, float)

    # ⚠️ 라벨은 **영문**이다 — matplotlib 에 한글 폰트가 없어 한글은 두부(□)로 나온다(`viz.dim_sheet` 와 같은 제약).
    specs = [
        ("flange dia (px)", [("dia", col("mask_flange", "dia_px"))], TARGET_FLANGE_PX, "target 419"),
        ("depth (mm)", [("flange med", col("depth", "med_flange"))], None, None),
        ("plane resid (mm)", [("rms", col("depth", "plane", "rms_mm")),
                              ("p90", col("depth", "plane", "p90_mm"))], None, None),
        ("valid (%)", [("all", col("valid", "all", scale=100)),
                       ("flange", col("valid", "flange", scale=100)),
                       ("ring", col("valid", "ring", scale=100))], None, None),
        ("contour moved (deg)", [("moved", col("pose", "moved_deg"))], gate_deg, f"gate {gate_deg}"),
    ]
    specs = [s for s in specs if any(np.isfinite(y).any() for _, y in s[1])]
    if not specs:
        return False
    fig, axes = plt.subplots(len(specs), 1, figsize=(max(7, len(rows) * 0.16), 2.0 * len(specs)),
                             sharex=True)
    axes = np.atleast_1d(axes)
    for ax, (title, series, ref, reflab) in zip(axes, specs):
        for lab, y in series:
            ax.plot(x, y, marker="o", ms=2.6, lw=1.1, label=lab)
        if ref is not None:
            ax.axhline(ref, color="crimson", lw=0.9, ls="--", label=reflab)
        ax.set_ylabel(title, fontsize=8)
        ax.grid(alpha=0.25, lw=0.5)
        ax.legend(fontsize=7, loc="best", framealpha=0.85)
        ax.tick_params(labelsize=7)
    # 게이트에 걸린 프레임을 전 단에 세로선으로 — «어느 프레임이 문제인가» 가 한눈에 나온다
    gated = [i for i, r in enumerate(rows) if (r.get("pose") or {}).get("gated")]
    for ax in axes:
        for i in gated:
            ax.axvline(i, color="crimson", alpha=0.12, lw=2.0)
    axes[-1].set_xlabel(f"frame index (0-{len(rows)-1})   red band = gate fallback", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return True


def _median_block(rows: list[dict]) -> dict:
    """중앙값 요약. ⚠️ 평균이 아니라 **중앙값**이다 — 대실패 한 장이 평균을 지배한다(교훈 #14)."""
    def med(*path, scale=1.0):
        v = []
        for r in rows:
            x = r
            for k in path:
                x = (x or {}).get(k) if isinstance(x, dict) else None
            if isinstance(x, (int, float)):
                v.append(x * scale)
        return round(float(np.median(v)), 3) if v else None

    return {k: v for k, v in {
        "img_med": med("image", "med"), "img_sat_pct": med("image", "sat_pct"),
        "full_dia_px": med("mask_full", "dia_px"), "flange_dia_px": med("mask_flange", "dia_px"),
        "depth_med_flange": med("depth", "med_flange"),
        "plane_rms_mm": med("depth", "plane", "rms_mm"),
        "valid_all_pct": med("valid", "all", scale=100),
        "valid_ring_pct": med("valid", "ring", scale=100),
        "moved_deg": med("pose", "moved_deg"),
        "n_gated": sum(1 for r in rows if (r.get("pose") or {}).get("gated")),
    }.items() if v is not None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="단계별 산출물 6패널 진단 시트 (GT 불필요)")
    ap.add_argument("--in", dest="in_dir", required=True, help="<dir>/frame_XXXX/left.png")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seg-full", default=None, help="mask_full.png 이 있는 디렉토리")
    ap.add_argument("--seg-flange", default=None, help="flange 마스크가 있는 디렉토리")
    ap.add_argument("--flange-name", default="mask_flange.png",
                    help="flange 마스크 파일명. **`RH1` 은 `mask_flange_proj.png`** 다 — "
                         "그 경로는 분할이 아니라 CAD 투영으로 마스크를 만들고 "
                         "`pose_fp` 가 pose 디렉토리에 그 이름으로 쓴다(`--seg-flange <fp 디렉토리>` 와 함께)")
    ap.add_argument("--depth-dir", default=None, help="depth.png·valid.png 이 있는 디렉토리")
    ap.add_argument("--pose-dir", default=None)
    ap.add_argument("--pose-name", default="pose_refined.json")
    ap.add_argument("--obj", default=None, help="--pose-dir 를 쓸 때 필요")
    ap.add_argument("--mesh", default="top_flange.ply")
    ap.add_argument("--depth-pct", type=float, nargs=2, default=[2.0, 98.0],
                    metavar=("LO", "HI"),
                    help="depth 컬러맵 구간을 잡을 백분위. **기본 `2 98`**. "
                         "🔴 컬러맵은 256색뿐이라 «어느 범위를 색에 대응시킬지» 를 반드시 골라야 하고, "
                         "범위 밖은 끝 색으로 포화된다 — 그것이 «잘려 보이는» 것의 정체다. "
                         "기본값은 이상치 몇 픽셀이 구간을 늘려 **물체가 통째로 단색이 되는 것**을 막는다"
                         "(실측: 센서 전 범위로 잡으면 물체 중간50%%가 256단계 중 **2단계**, 현행은 103단계). "
                         "★ 포화 없이 물체 끝까지 색을 내려면 **`--depth-pct 0 100`**"
                         " — 대비는 줄어든다(103 → 81단계). ⚠️ **표시 전용이고 어떤 계산에도 안 들어간다.**")
    ap.add_argument("--order", default="default", choices=["default", "pipeline"],
                    help="패널 배치. `default`(기존) = 원본·마스크2·depth2·pose · "
                         "**`pipeline`** = **인과 순서**(원본 → depth → mask_full → mask_flange → stage2 입력 → pose). "
                         "🔴 `mask_flange` 는 분할 산출물이 아니라 **stage1 pose 의 CAD 투영**이라 "
                         "`mask_full` 옆에 두면 «둘 다 분할» 로 오해된다 — 보고서용은 `pipeline` 을 권한다")
    ap.add_argument("--panel5", default="valid", choices=["valid", "stage2"],
                    help="5번 패널. `valid`(기본) = 범위 검사 마스크 · "
                         "**`stage2`** = **stage2 가 실제로 먹는 «flange 로 가린 depth»**"
                         "(`pose_fp.py:411` 과 같은 연산). 🔴 `valid` 는 범위 검사라 거의 항상 100% 여서 "
                         "정보가 없다 — 보고서용은 `stage2` 를 권한다(flange 안 무효는 마젠타로 남긴다)")
    ap.add_argument("--gate-deg", type=float, default=1.5, help="추이 그래프의 기준선")
    ap.add_argument("--frames", type=int, default=6, help="시트에 넣을 프레임 수")
    ap.add_argument("--pick", default=None, help="프레임 직접 지정 (쉼표 구분)")
    ap.add_argument("--width", type=int, default=380, help="패널 한 장의 가로 픽셀")
    ap.add_argument("--all", action="store_true", help="개별 장을 **모든** 프레임에 대해 쓴다")
    args = ap.parse_args(argv)

    in_dir = Path(args.in_dir)
    frames = sorted([p for p in in_dir.glob("frame_*") if (p / "left.png").exists()])
    if not frames:
        print(f"❌ {in_dir}/frame_XXXX/left.png 가 없다")
        return 2
    mesh = None
    if args.pose_dir:
        if not args.obj:
            print("❌ --pose-dir 를 쓰면 --obj 도 필요하다")
            return 2
        import trimesh
        mesh = trimesh.load(Path(args.obj) / args.mesh, process=False)

    if args.pick:
        by = {f.name: f for f in frames}
        sel = [by[s.strip()] for s in args.pick.split(",") if s.strip() in by]
    else:
        sel = [frames[i] for i in
               np.linspace(0, len(frames) - 1, min(args.frames, len(frames))).round().astype(int)]

    hw = cv2.imread(str(frames[0] / "left.png")).shape[:2]
    w = args.width
    h = int(round(w * hw[0] / hw[1]))          # 원본 화면비 유지 — 찌그러뜨리면 육안 진단이 안 된다
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows, tiles, n_img = [], {}, 0
    for f in frames:                           # ★ 수치는 **전 프레임**에서 낸다 (시트는 일부만)
        cam = json.loads((f / "cam.json").read_text())
        K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], float)
        met, raw = frame_metrics(f, args, mesh, K, hw)
        rows.append(met)
        if args.all or f in sel:
            img = render_frame(f, args, met, raw, w, h)
            cv2.imwrite(str(out / f"diag_{f.name}.png"), img)
            n_img += 1
            if f in sel:
                tiles[f.name] = img

    cv2.imwrite(str(out / "diag_sheet.png"),
                np.concatenate([tiles[f.name] for f in sel if f.name in tiles], 0))
    (out / "diag_metrics.json").write_text(json.dumps(
        {"in": str(in_dir), "n_frames": len(rows), "pose_dir": args.pose_dir,
         "pose_name": args.pose_name, "target_flange_px": TARGET_FLANGE_PX,
         "median": _median_block(rows), "frames": rows}, indent=2, ensure_ascii=False))
    print(f"→ {out}/diag_sheet.png  ({len(sel)} 프레임)")
    print(f"→ {out}/diag_<frame>.png  ({n_img}장)")
    print(f"→ {out}/diag_metrics.json  (전 {len(rows)}프레임)")
    if len(rows) >= 3 and trends_png(rows, out / "diag_trends.png", args.gate_deg):
        print(f"→ {out}/diag_trends.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
