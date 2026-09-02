#!/usr/bin/env python3
"""팔(arm) 여럿을 **sim GT 로 서열화**한다 — 반복 런을 받아 FP 비결정성을 누른다.

왜 이 도구가 따로 있나
    `tools/rank_sim.py` 는 **러너 출력 하나** 안의 팔들을 채점한다. 이건 **디렉토리를 직접 지정**해
    «다른 프롬프트 · 다른 배율 · 다른 투영» 처럼 **런이 갈라진 팔들**을 한 표에 놓는다.

    🔴 **FP 는 비결정이다**(교훈 #24·#107). 같은 설정 두 런이 **서로소 실패집합**을 낸 적이 있다.
    그래서 팔마다 **반복 런 여러 개**를 받아 ① 프레임별 **반복 중앙값**으로 RNG 를 누르고
    ② 그 위에서 **짝지은 부호검정**을 한다. ③ **반복 산포(잡음 바닥)** 를 같이 내서
    «설정 차이가 잡음보다 큰가» 를 먼저 보게 한다.

지표
    R(도) · t(mm) · **ADD**(mm, 모델 정점 평균 거리 — R·t 를 합쳐 본다).
    ⚠️ R 은 `contracts.rotation_angle_deg` 로만 잰다(교훈 #85).

pose 조합 (`--arm` 의 세 번째 칸)
    `refined` = `pose_refined.json` · `coarse` = `pose_coarse.json`
    **`hybrid`** = **R 은 coarse · t 는 refined** (§27-7). 배포 팔 `RH*` 가 이것이다.

사용
    envs/pose/bin/python tools/arm_rank_sim.py --in runs/S44_cap60 \\
        --obj assets/obj/foup_300_semi_r2 \\
        --arm "RH1:runs/S44c_p05_r*:hybrid" --arm "RP1:runs/S44c_p05_r*:refined" ...
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from math import comb
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def sign_p(k: int, n: int) -> float:
    if n == 0:
        return float("nan")
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(k, n - k) + 1)) / 2 ** n)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="in_dir", required=True, help="캡처 (pose_gt.json)")
    ap.add_argument("--obj", required=True)
    ap.add_argument("--arm", action="append", required=True,
                    help="'라벨:글롭:refined|coarse|hybrid[:분할디렉토리]' — 글롭은 **반복 런들**. "
                         "분할디렉토리를 주면 **오선택을 먼저 갈라낸다**(§42-1: 오선택이 전부를 덮는다)")
    ap.add_argument("--miss-iou", type=float, default=0.3,
                    help="마스크 IoU 가 이 값 미만이면 «오선택» 으로 본다")
    ap.add_argument("--add-samples", type=int, default=2000, help="ADD 용 정점 표본")
    ap.add_argument("--kpi-t", type=float, default=5.0)
    ap.add_argument("--kpi-r", type=float, default=3.0)
    ap.add_argument("--md-out", default=None)
    a = ap.parse_args(argv)

    import trimesh
    from spatial_vision.contracts import rotation_angle_deg

    cap = Path(a.in_dir)
    frames = sorted(x.name for x in cap.glob("frame_*") if (x / "pose_gt.json").exists())
    if not frames:
        print(f"❌ `{cap}` 에 GT 가 없다 — sim 캡처여야 한다", file=sys.stderr)
        return 2

    mesh = trimesh.load(str(Path(a.obj) / "full.ply"), process=False)
    V = np.asarray(mesh.vertices, float)
    if len(V) > a.add_samples:                       # 결정적 균등 솎기 (난수 금지)
        V = V[np.linspace(0, len(V) - 1, a.add_samples).astype(int)]

    def pose(p: Path):
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        k = "t_mm" if "t_mm" in d else "t"
        return np.asarray(d["R"], float).reshape(3, 3), np.asarray(d[k], float).reshape(3)

    GT = {f: pose(cap / f / "pose_gt.json") for f in frames}

    lines: list[str] = []

    def out(s: str = "") -> None:
        print(s)
        lines.append(s)

    arms: dict[str, dict[str, np.ndarray]] = {}
    order: list[str] = []
    import cv2

    def mask_iou(seg: Path) -> np.ndarray:
        """그 분할의 프레임별 GT 대비 IoU. 없으면 NaN."""
        v = []
        for f in frames:
            p, q = seg / f / "mask_full.png", cap / f / "mask_full.png"
            if not (p.exists() and q.exists()):
                v.append(np.nan); continue
            x = cv2.imread(str(p), 0) > 127
            y = cv2.imread(str(q), 0) > 127
            v.append(float((x & y).sum() / max((x | y).sum(), 1)))
        return np.array(v)

    for spec in a.arm:
        parts = spec.split(":")
        lab, g, mode = parts[0], parts[1], parts[2]
        seg = Path(parts[3]) if len(parts) > 3 and parts[3] else None
        runs = sorted(Path(x) for x in glob.glob(g))
        runs = [r for r in runs if (r / "meta_pose.json").exists()]
        if not runs:
            out(f"⚠️ `{lab}`: `{g}` 에 완료된 런이 없다 — 건너뛴다")
            continue
        R_, T_, A_ = [], [], []
        for rd in runs:
            rr, tt, aa = [], [], []
            for f in frames:
                pr = pose(rd / f / "pose_refined.json")
                pc = pose(rd / f / "pose_coarse.json")
                gt = GT[f]
                if gt is None or pr is None or pc is None:
                    rr.append(np.nan); tt.append(np.nan); aa.append(np.nan); continue
                Rp, tp = (pc[0], pr[1]) if mode == "hybrid" else (pc if mode == "coarse" else pr)
                rr.append(rotation_angle_deg(Rp.T @ gt[0]))
                tt.append(float(np.linalg.norm(tp - gt[1])))
                aa.append(float(np.linalg.norm((V @ Rp.T + tp) - (V @ gt[0].T + gt[1]), axis=1).mean()))
            R_.append(rr); T_.append(tt); A_.append(aa)
        arms[lab] = {"R": np.array(R_), "t": np.array(T_), "ADD": np.array(A_),
                     "n_rep": len(runs), "mode": mode,
                     "miou": mask_iou(seg) if seg else None}
        order.append(lab)

    if not arms:
        out("❌ 채점할 팔이 없다")
        return 2

    out(f"# 팔 서열 (sim GT) — `{cap.name}` · n={len(frames)}프레임 · 팔 {len(arms)}개")
    out()
    out("🔴 **FP 는 비결정이다** — 팔마다 반복 런의 **프레임별 중앙값**으로 RNG 를 눌렀다. "
        "**설정 차이가 «반복 산포» 보다 작으면 «구분 안 됨»** 이고, p 값보다 그걸 먼저 본다.")
    out()
    has_seg = any(arms[l]["miou"] is not None for l in order)
    out("| 팔 | 조합 | 반복 | " + ("**오선택** | " if has_seg else "")
        + "**ADD 중앙**" + ("(깨끗)" if has_seg else "")
        + " | ADD p90 | ADD 최대 | R 중앙 | t 중앙 | KPI(전체) | 반복산포 |")
    out("|---|:-:|:-:|" + ("---|" if has_seg else "") + "---|---|---|---|---|---|---|")
    med: dict[str, dict[str, np.ndarray]] = {}
    clean: dict[str, np.ndarray] = {}
    for lab in order:
        d = arms[lab]
        m = {k: np.nanmedian(d[k], axis=0) for k in ("R", "t", "ADD")}
        med[lab] = m
        ok = np.isfinite(m["R"]) & np.isfinite(m["t"])
        kpi = int(((m["t"][ok] <= a.kpi_t) & (m["R"][ok] <= a.kpi_r)).sum())
        # 🔴 오선택 프레임을 빼고 통계를 낸다 — 안 빼면 오선택이 전부를 덮는다(§42-1)
        cm = ok & ((d["miou"] >= a.miss_iou) if d["miou"] is not None else True)
        clean[lab] = cm
        sp = (float(np.nanmedian(np.nanmax(d["ADD"], 0) - np.nanmin(d["ADD"], 0)))
              if d["n_rep"] > 1 else float("nan"))
        miss = (f"**{int((d['miou'] < a.miss_iou).sum())}/{int(np.isfinite(d['miou']).sum())}** | "
                if d["miou"] is not None else ("— | " if has_seg else ""))
        out(f"| **{lab}** | {d['mode']} | {d['n_rep']} | {miss}**{np.nanmedian(m['ADD'][cm]):.3f}** "
            f"| {np.nanpercentile(m['ADD'][cm],90):.3f} | {np.nanmax(m['ADD'][cm]):.3f} "
            f"| {np.nanmedian(m['R'][cm]):.3f} | {np.nanmedian(m['t'][cm]):.3f} "
            f"| {kpi}/{int(ok.sum())} | {sp:.3f} |")
    out()
    if has_seg:
        out("🔴 **ADD·R·t 는 «오선택을 뺀» 프레임에서만** 냈다 — 안 빼면 오선택이 전부를 덮는다(§42-1). "
            "`KPI` 열만 **전체 프레임** 기준이다.")
        out()

    best = min(order, key=lambda l: np.nanmedian(med[l]["ADD"][clean[l]]))
    out(f"**짝지은 부호검정** — ADD 중앙 1위 **`{best}`** 대비 (프레임별 반복중앙값끼리, 동률 제외)")
    out()
    out("| 상대 | ADD 더 나은 프레임 | 중앙차 | p | 판정 |")
    out("|---|---|---|---|---|")
    for lab in order:
        if lab == best:
            continue
        x, y = med[best]["ADD"], med[lab]["ADD"]
        # 🔴 둘 다 깨끗한 프레임에서만 짝짓는다
        m = np.isfinite(x) & np.isfinite(y) & (x != y) & clean[best] & clean[lab]
        n = int(m.sum()); k = int((x[m] < y[m]).sum())
        d = float(np.median(x[m] - y[m])) if n else float("nan")
        p = sign_p(k, n)
        sp = np.nanmedian([np.nanmedian(np.nanmax(arms[l]["ADD"], 0) - np.nanmin(arms[l]["ADD"], 0))
                           for l in (best, lab)])
        v = ("🔴 **구분 안 됨** (차이 < 잡음 바닥)" if abs(d) < sp else
             ("✅ 유의" if p < 0.05 else "⚠️ 방향만"))
        out(f"| `{lab}` | {k}/{n} | {d:+.3f} mm | {p:.4f} | {v} |")
    out()
    out("🔴 **읽는 법** — «차이 < 잡음 바닥» 이면 p 가 작아도 **구분 안 된 것**이다. "
        "그리고 이건 **sim** 이다 — 실텍스처·실조명·CAD 불일치 축이 없다(교훈 #33).")

    if a.md_out:
        Path(a.md_out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n→ {Path(a.md_out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
