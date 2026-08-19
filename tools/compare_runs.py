#!/usr/bin/env python3
"""여러 A그룹 런을 **한 표로** 비교한다 — 실물 시행착오의 실험 노트.

    envs/pose/bin/python tools/compare_runs.py runs/real01_A runs/real02_A runs/real03_A
    envs/pose/bin/python tools/compare_runs.py runs/*_A --out runs/compare.md

왜 이 도구인가
    실물은 «한 번에» 안 된다. 거리·조명·참조 세트·플래그를 바꿔 가며 여러 번 돌리는데,
    런마다 `report.md` 가 따로 나면 **비교가 손으로만** 된다. 20번째 런에서는
    *"그 좋았던 게 어느 조합이었지"* 가 된다.

무엇을 내는가 — **순서가 중요하다**
    ① **설정 diff 를 먼저** 낸다. 무엇이 달랐는지 모르면 지표 표를 읽을 수 없다.
    ② 그 다음 지표를 나란히 놓는다.
    🔴 ③ **비교 가능성 판정** — 초기값 자체가 달라지는 비교(거리대·분할 백엔드·자산·카메라)에서는
       **게이트 후퇴율이 원리적으로 무효**다(교훈 #82: n25→n30 에서 후퇴율 45→65% 인데 GT KPI 는
       12/20 → 17/20 으로 좋아졌다). 그런 열은 **회색 처리하고 경고를 단다.**

⚠️ 실환경에는 GT 가 없다 — 여기 나오는 것은 전부 GT-free 지표다. **«어느 런이 정확한가» 를
   이 표만으로 단정할 수 없다.** 서열화의 최종 근거는 좌우 투영 일관성 + **오버레이 육안**이다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VISION = Path(__file__).resolve().parents[1]

# 이 키들이 다르면 «초기값이 달라지는 비교» 다 → 후퇴율 비교가 무효 (교훈 #82)
INIT_CHANGING = ("obj", "preset", "refs", "n_refs", "refs_mode", "input_scale",
                 "stereo_scale", "ism", "use_prompts_file")
# 사람이 볼 필요 없는 인자 (경로·실행 제어)
SKIP_ARGS = {"in_dir", "out", "only", "force", "dry_run", "report_only", "allow_cpu",
             "list_presets", "overlay_frames", "overlay_mask_alpha", "diag_all", "note"}


def load(run: Path) -> dict | None:
    rm, rj = run / "run_meta.json", run / "report.json"
    if not rj.exists():
        print(f"⚠️ {run}: report.json 없음 — 건너뜀", file=sys.stderr)
        return None
    d = {"path": run, "report": json.loads(rj.read_text(encoding="utf-8"))}
    # run_meta 는 이 도구가 생기기 전 런에는 없다 — 없어도 report.json 만으로 굴러가야 한다
    d["meta"] = json.loads(rm.read_text(encoding="utf-8")) if rm.exists() else None
    return d


def fmt(x, spec="", dash="—"):
    if x is None:
        return dash
    try:
        return format(x, spec) if spec else str(x)
    except (TypeError, ValueError):
        return str(x)


def config_rows(runs: list[dict]) -> tuple[list[str], set[str]]:
    """설정 표 + **달라진 키 집합**. 달라진 것만 보여 준다 — 같은 건 잡음이다."""
    keys, vals = set(), {}
    for r in runs:
        args = (r["meta"] or {}).get("args", {})
        rep = r["report"]
        merged = dict(args)
        # run_meta 가 없는 옛 런도 최소한은 비교되게 report.json 에서 메운다
        for k, v in (("obj", rep.get("obj")), ("preset", rep.get("preset")),
                     ("refs", rep.get("refs")), ("gate_deg", rep.get("gate_deg")),
                     ("true_distance_mm", rep.get("true_distance_mm"))):
            merged.setdefault(k, v)
        for k, v in merged.items():
            if k in SKIP_ARGS:
                continue
            keys.add(k)
            vals.setdefault(k, []).append(v)
    diff = {k for k in keys if len({json.dumps(x, default=str) for x in vals.get(k, [])}) > 1
            or len(vals.get(k, [])) != len(runs)}
    return sorted(diff), diff


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A그룹 런 비교 (GT-free)")
    ap.add_argument("runs", nargs="+", help="런 디렉토리들 (run_group_a.py 의 --out)")
    ap.add_argument("--out", default=None, help="마크다운 저장 경로 (기본: 표준출력만)")
    ap.add_argument("--index", default=None,
                    help="여기에 지정한 파일에 한 줄씩 **누적** 기록한다 (실험 노트). "
                         "예: runs/runs_index.md")
    a = ap.parse_args(argv)

    runs = [x for x in (load(Path(p) if Path(p).is_absolute() else VISION / p)
                        for p in a.runs) if x]
    if not runs:
        print("❌ 읽을 런이 없다", file=sys.stderr)
        return 2
    names = [r["path"].name for r in runs]
    L = [f"# 런 비교 — {len(runs)}개\n"]

    # ── ① 설정 diff ───────────────────────────────────────────────────────────
    diff_keys, diffset = config_rows(runs)
    L.append("## ① 무엇이 달랐나\n")
    L.append("| 항목 | " + " | ".join(f"`{n}`" for n in names) + " |")
    L.append("|---|" + "---|" * len(runs))
    L.append("| **시각** | " + " | ".join(
        fmt((r["meta"] or {}).get("datetime_local") or r["report"].get("datetime_local"))
        for r in runs) + " |")
    L.append("| **메모** | " + " | ".join(
        fmt((r["meta"] or {}).get("note") or r["report"].get("note")) for r in runs) + " |")
    L.append("| 입력 | " + " | ".join(fmt((r["meta"] or {}).get("in") or r["report"].get("in"))
                                      for r in runs) + " |")
    L.append("| 프레임 | " + " | ".join(fmt(r["report"]["capture"].get("n_frames"))
                                      for r in runs) + " |")
    # 사진이 같은가 — 이름이 아니라 **내용**으로 (같은 촬영 재분석 vs 새 촬영)
    fh = [tuple(sorted(((r["meta"] or {}).get("frame_hashes") or {}).items())) for r in runs]
    if all(fh) and len(set(fh)) == 1:
        L.append("| 사진 | " + " | ".join(["**동일** (내용 해시 일치)"] * len(runs)) + " |")
    elif all(fh):
        L.append("| 사진 | " + " | ".join(
            (list(dict(h).values())[0][:8] if h else "—") for h in fh) + " |")
    if not diff_keys:
        L.append("| — | " + " | ".join(["설정 차이 없음"] * len(runs)) + " |")
    for k in diff_keys:
        row = []
        for r in runs:
            args = (r["meta"] or {}).get("args", {})
            val = args.get(k, r["report"].get(k))
            row.append(fmt(val))
        mark = " 🔴" if k in INIT_CHANGING else ""
        L.append(f"| `{k}`{mark} | " + " | ".join(row) + " |")
    L.append("")

    init_changed = sorted(set(diff_keys) & set(INIT_CHANGING))
    if init_changed:
        L.append(f"🔴 **초기값이 달라지는 비교다** (`{'`, `'.join(init_changed)}`). "
                 f"**게이트 후퇴율로 우열을 가리면 안 된다** — 교훈 #82: 후퇴율은 "
                 f"*\"초기값에서 얼마나 움직였나\"* 이지 *\"맞나\"* 가 아니다. "
                 f"아래 표에서 후퇴율 행은 **참고용**이고, 근거는 **좌우 일관성 + 오버레이 육안**이다.\n")
    else:
        L.append("✅ **같은 초기값 위에서 플래그만 다른 비교다** — 게이트 후퇴율이 유효한 지표다"
                 "(§29·§31 에서 실제로 작동했다).\n")

    # ── ② 촬영 진단 ───────────────────────────────────────────────────────────
    L.append("## ② 촬영 진단\n")
    L.append("| 항목 | " + " | ".join(f"`{n}`" for n in names) + " |")
    L.append("|---|" + "---|" * len(runs))
    for key, lab, spec in (("flange_dia_px", "flange 등가지름 px", ".0f"),
                           ("z_mm", "FP 추정 z mm", ".0f"),
                           ("depth_plane_mm", "stereo depth 평면 mm", ".0f"),
                           ("z_minus_depth_mm", "FP − depth mm", "+.1f"),
                           ("plane_rms_mm", "flange 평면 rms mm", ".2f"),
                           ("lat_mm", "광축 이탈 횡 mm", ".0f"),
                           ("valid_ring", "주변 depth 유효율", ".1%"),
                           ("valid_flange", "flange depth 유효율", ".1%")):
        vals = [r["report"]["capture"].get("median", {}).get(key) for r in runs]
        if any(v is not None for v in vals):
            L.append(f"| {lab} | " + " | ".join(fmt(v, spec) for v in vals) + " |")
    sc = [r["report"]["capture"].get("scale", {}).get("mm_per_px") for r in runs]
    if any(sc):
        L.append("| 눈금 mm/px | " + " | ".join(fmt(v, ".3f") for v in sc) + " |")
    L.append("")

    # ── ③ 변형별 지표 ─────────────────────────────────────────────────────────
    ids = []
    for r in runs:
        for k in r["report"].get("variants", {}):
            if k not in ids:
                ids.append(k)
    order = [x for x in ("A3", "A1", "A2a", "A2b", "A4", "I3", "I1") if x in ids]
    L.append("## ③ 변형별 GT-free 지표\n")
    for metric, lab, spec, better in (
            ("lr_ddx", "좌우 |Δdx| px", ".2f", "작을수록 좋다"),
            ("lr_ddx_signed", "좌우 Δdx 부호 px", "+.2f", "🔴 부호가 쏠리면 계통 편향"),
            ("gated_pct", "게이트 후퇴 %", ".0f", "폭주 지표 — 위 ① 경고 확인"),
            ("n_corr", "대응점", ".0f", "신호가 있었나"),
            ("rms_px", "rms px", ".2f", "적합도"),
            ("moved_deg_med", "이동 ° 중앙", ".2f", "정합이 얼마나 움직였나")):
        L.append(f"**{lab}** — {better}\n")
        L.append("| 변형 | " + " | ".join(f"`{n}`" for n in names) + " |")
        L.append("|---|" + "---|" * len(runs))
        for sid in order:
            vals = [r["report"].get("variants", {}).get(sid, {}).get(metric) for r in runs]
            if all(v is None for v in vals):
                continue
            L.append(f"| {sid} | " + " | ".join(fmt(v, spec) for v in vals) + " |")
        L.append("")

    L.append("## 읽는 법\n")
    L.append("- **①을 먼저 본다.** 설정이 뭐가 달랐는지 모르고 ③을 보면 아무 결론도 못 낸다.")
    L.append("- 🔴 **`lr_ddx` 는 절대값이 아니라 «같은 런 안에서 변형 간 차이» 로 읽는다.** "
             "런 사이 절대 비교는 거리·조명이 다르면 성립하지 않는다.")
    L.append("- 🔴 **부호 행이 한쪽으로 쏠려 있으면 계통 편향**이다 — 게이트도 refine 도 못 고친다"
             "(§29·§35-2i). 캘리브레이션·CAD 형상·원점 규약을 의심한다.")
    L.append("- **GT-free 지표는 전부 «자기 일관성» 이라 «다 같이 틀린» 경우를 못 잡는다.** "
             "각 런의 `overlay_sheet.png` 를 나란히 놓고 눈으로 보는 단계를 건너뛰지 않는다.")
    L.append("- 🔴🔴 **재실행 잡음 바닥을 먼저 뺀다** (`RESULTS.md §35-2l-6`). GPU 단계는 "
             "**같은 입력에도 결과가 달라진다** — `pose_fp` 는 **ΔR 중앙 0.146° · 최대 0.662°**, "
             "`stereo_onnx` 는 매 실행 다르다(`refine_contour` 만 완전 결정론). "
             "**FP 를 다시 돌린 두 런의 R 차이가 0.15° 미만이면 설정 효과의 증거가 아니다.** "
             "⚠️ `cam.json` 이 8번째 자리만 달라도 FP 출력이 0.4° 갈린다(가설 argmax 의 불연속 점프) "
             "— 위 ①의 «사진» 행과 `cam` 해시를 반드시 확인할 것.\n")

    txt = "\n".join(L)
    print(txt)
    if a.out:
        p = Path(a.out) if Path(a.out).is_absolute() else VISION / a.out
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")
        print(f"→ {p}")
    if a.index:
        # ★ 누적 실험 노트 — 한 줄씩 append. 표가 아니라 **시간순 기록**이 목적이다.
        p = Path(a.index) if Path(a.index).is_absolute() else VISION / a.index
        p.parent.mkdir(parents=True, exist_ok=True)
        new = p.exists()
        with open(p, "a", encoding="utf-8") as fh:
            if not new:
                # ⚠️ 표 안의 `|` 는 **이스케이프**해야 한다 — 안 하면 열이 깨진다(전례 있음)
                fh.write("# 런 기록\n\n"
                         "| 시각 | 런 | 프레임 | preset | A1 좌우 \\|Δdx\\| | A1 후퇴% | 메모 |\n"
                         "|---|---|---|---|---|---|---|\n")
            for r, n in zip(runs, names):
                a1 = r["report"].get("variants", {}).get("A1", {})
                m = r["meta"] or {}
                fh.write(f"| {fmt(m.get('datetime_local') or r['report'].get('datetime_local'))} "
                         f"| `{n}` | {fmt(r['report']['capture'].get('n_frames'))} "
                         f"| {fmt(m.get('args', {}).get('preset') or r['report'].get('preset'))} "
                         f"| {fmt(a1.get('lr_ddx'), '.2f')} | {fmt(a1.get('gated_pct'), '.0f')} "
                         f"| {fmt(m.get('note') or r['report'].get('note'), dash='')} |\n")
        print(f"→ {p} (누적)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
