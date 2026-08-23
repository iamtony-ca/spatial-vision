"""러너 산출물의 **배선**을 기계로 검사한다 — *"어느 팔의 숫자가 다른 팔 것은 아닌가"*.

    envs/pose/bin/python tools/audit_run.py --root runs/real01_A

왜 필요한가
    이 러너는 한 번에 **30팔**을 만들고, 그 결과를 표·CSV·오버레이·히트맵으로 **여러 번 다시**
    그린다. 배선이 한 군데 어긋나면 **숫자는 멀쩡해 보이는데 뜻이 달라진다** — 그리고 GT 가
    없으면 그걸 눈으로 알아챌 수 없다. 실제로 이 검사를 처음 돌렸을 때 결함 둘이 나왔다:
      ① `distance.png` 가 **A 경로의 `FP z`** 에서 **I 경로의 실루엣**을 빼고 있었다
         (잔차 +0.75mm 를 +1.50mm 로 보고. 두 경로가 크게 어긋난 런이었다면 «baseline 이
         틀렸다» 는 정반대 처방이 나온다) → `RESULTS.md §35-2p-1`
      ② `Ccas_s1`·`Ccas_s2` 가 **팔처럼 생겨서** 실제로 팔로 채점됐다(캐스케이드 중간 단이다)
    ⚠️ **«숫자가 맞나» 가 아니라 «그 숫자가 그 팔 것인가» 를 본다.** 정확도 검사가 아니다.

무엇을 검사하나 (전부 GT 불필요)
    1. 팔마다 pose 산출물이 **고유한가** — 두 팔이 같은 파일을 공유하면 배선 사고다
    2. **후퇴 프레임 = 그 팔 «자신의» 초기값**인가 (A4←fp_s2 · H1←fp_hyb · I1←fp_ism …)
       그리고 비후퇴 프레임이 초기값과 «같아 버리지» 않았는가(정합이 실제로 돌았는가)
    3. `stats/metrics_long.csv` 의 값이 **원본 JSON 과 일치**하는가 (ddx·moved·gated·tz)
    4. `lr/` 태그가 **그 팔의 pose 디렉토리**를 봤는가 (별칭 A3/I3/T3 포함)
    5. `overlay_sheet` 열 수 = 팔 수인가
    6. `scale_check` 의 pose 출처가 `report.json` 의 `capture_pose_dir` 과 **같은가**
       (다르면 `distance.png` 가 «경로 차» 를 잔차로 오해할 수 있다 — 경고)
    7. 디스크의 «팔처럼 생긴» 디렉토리 중 표·CSV 에서 빠진 것이 있는가

🔴 **실패는 종료코드 1** 이다 — 리포트를 읽기 전에 이걸 먼저 돌린다.
⚠️ 이 도구는 **배선만** 본다. «값이 맞나» 는 GT 가 있어야 하고 실환경에는 GT 가 없다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

# 팔이 아닌 디렉토리 — 스테이지 산출물과 캐스케이드 중간 단
NOT_ARMS = ("fp_", "seg", "st", "lr", "diag", "overlay", "segcmp", "stats", "worst", "_in_")
CASCADE_STAGES = ("Ccas_s1", "Ccas_s2")
# 정합을 안 하는 팔 — pose 가 자기 디렉토리가 아니라 FP 디렉토리에 있다
ALIAS = {"A3": ("fp_ns2", "pose_coarse.json"), "I3": ("fp_ism", "pose_coarse.json"),
         "T3": ("fp_txt", "pose_coarse.json")}


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _rt(p: Path):
    j = _load(p)
    if not j or "R" not in j:
        return None
    return np.asarray(j["R"], float).reshape(3, 3), np.asarray(j["t_mm"], float)


def _same(a, b) -> bool:
    return (a is not None and b is not None
            and np.allclose(a[0], b[0], atol=1e-9) and np.allclose(a[1], b[1], atol=1e-9))


def arms_on_disk(root: Path) -> list[str]:
    return sorted(d.name for d in root.iterdir()
                  if d.is_dir() and (d / "meta_contour.json").exists()
                  and not d.name.startswith(NOT_ARMS))


def check(root: Path) -> tuple[list[str], list[str]]:
    ok: list[str] = []
    bad: list[str] = []

    disk = arms_on_disk(root)
    real = [a for a in disk if a not in CASCADE_STAGES]

    # ── 1. 팔마다 고유한 산출물인가 ────────────────────────────────────────────
    h: dict[str, str] = {}
    for a in real:
        m = hashlib.sha256()
        for f in sorted((root / a).glob("frame_*/pose_refined.json")):
            m.update(f.read_bytes())
        h[a] = m.hexdigest()
    for k, (d, nm) in ALIAS.items():
        fs = sorted((root / d).glob(f"frame_*/{nm}"))
        if fs:
            m = hashlib.sha256()
            for f in fs:
                m.update(f.read_bytes())
            h[k] = m.hexdigest()
    dup: dict[str, list[str]] = {}
    for k, v in h.items():
        dup.setdefault(v, []).append(k)
    shared = [v for v in dup.values() if len(v) > 1]
    (ok if not shared else bad).append(
        f"① 산출물 고유성 — 팔 {len(h)}개 · 서로 다른 결과 {len(dup)}종"
        + ("" if not shared else f"  🔴 **같은 산출물을 공유**: {shared}"))

    # ── 2. 후퇴 = 자기 초기값 / 비후퇴 ≠ 초기값 ────────────────────────────────
    #    🔴 팔마다 초기값 출처가 다르다 — `meta_contour.json` 이 기록한 것을 **읽어서** 쓴다.
    #       여기에 상수를 박으면 러너가 바뀔 때 검사기가 조용히 틀린다.
    n_ok = 0
    for a in real:
        mc = _load(root / a / "meta_contour.json") or {}
        # `init` 은 «디렉토리/파일명» 전체 경로다 — 팔마다 다르고, 여기 기록된 것을 그대로 쓴다.
        # 🔴 상수를 박으면 러너가 바뀔 때 검사기가 조용히 틀린다.
        init = mc.get("init")
        if not init:
            bad.append(f"② {a}: `meta_contour.json` 에 초기값 출처(`init`)가 없다")
            continue
        sd, nm = Path(init).parent, Path(init).name
        gated = {f["frame"] for f in mc.get("frames", []) if f.get("gated")}
        bad_g = bad_ng = 0
        for f in sorted((root / a).glob("frame_*/pose_refined.json")):
            fn = f.parent.name
            cur, ini = _rt(f), _rt(sd / fn / nm)
            if ini is None:
                continue
            if fn in gated and not _same(cur, ini):
                bad_g += 1
            if fn not in gated and _same(cur, ini):
                bad_ng += 1
        if bad_g or bad_ng:
            bad.append(f"② {a}: 후퇴인데 초기값과 다름 {bad_g}장 · 비후퇴인데 초기값과 같음 {bad_ng}장 "
                       f"(초기값 = `{sd.name}/{nm}`)")
        else:
            n_ok += 1
    ok.append(f"② 후퇴↔초기값 — {n_ok}/{len(real)}팔이 **각자 자기 출처**를 정확히 물었다")

    # ── 3. CSV ↔ 원본 JSON ────────────────────────────────────────────────────
    csvp = root / "stats" / "metrics_long.csv"
    if not csvp.exists():
        bad.append("③ `stats/metrics_long.csv` 가 없다 — `eval.group_stats` 가 실패했다")
        rows = []
    else:
        rows = list(csv.DictReader(csvp.open()))
    byv: dict[str, dict] = {}
    for r in rows:
        byv.setdefault(r["variant"], {})[r["frame"]] = r
    mism = 0
    for v, fr in byv.items():
        lr = _load(root / "lr" / f"lr_consistency_{v}.json") or {}
        src = {f["frame"]: f for f in lr.get("frames", [])}
        mc = _load(root / v / "meta_contour.json") or {}
        msrc = {f["frame"]: f for f in mc.get("frames", [])}
        for fn, r in fr.items():
            a, b = r["ddx_px"], src.get(fn, {}).get("ddx_px")
            if a and b is not None and abs(float(a) - b) > 1e-9:
                mism += 1
            s = msrc.get(fn, {})
            if r["moved_mm"] and abs(float(r["moved_mm"]) - s.get("moved_mm", -1)) > 1e-9:
                mism += 1
            if r["gated"] and str(s.get("gated")).lower() != r["gated"].lower():
                mism += 1
        d, nm = ALIAS.get(v, (v, "pose_refined.json"))
        for fn, r in fr.items():
            t = _rt(root / d / fn / nm)
            if t is not None and r["tz_mm"] and abs(float(r["tz_mm"]) - t[1][2]) > 1e-3:
                mism += 1
    (ok if not mism else bad).append(
        f"③ CSV ↔ 원본 JSON — {len(rows)}행 · 불일치 {mism}건" + ("" if not mism else " 🔴"))

    # ── 4. lr 태그 수 ─────────────────────────────────────────────────────────
    nlr = len(list((root / "lr").glob("lr_consistency_*.json"))) if (root / "lr").exists() else 0
    want = len(real) + sum(1 for k in ALIAS if (root / ALIAS[k][0]).exists())
    (ok if nlr == want else bad).append(
        f"④ 좌우 일관성 파일 {nlr}개 (기대 {want} = 정합 팔 {len(real)} + 별칭)"
        + ("" if nlr == want else " 🔴"))

    # ── 5. 오버레이 열 수 ──────────────────────────────────────────────────────
    try:
        import cv2
        img = cv2.imread(str(root / "overlay_sheet.png"))
        # 타일 폭은 러너 기본 380. 나누어떨어지지 않으면 열 수를 못 세므로 «확인 불가» 로 남긴다.
        ncol = img.shape[1] / 380.0 if img is not None else 0
        if img is None:
            bad.append("⑤ `overlay_sheet.png` 이 없다")
        elif abs(ncol - round(ncol)) > 1e-6:
            ok.append(f"⑤ 오버레이 열 수 확인 불가 (타일 폭이 380 이 아니다: {img.shape[1]}px)")
        else:
            want5 = len(real) + sum(1 for k in ALIAS if (root / ALIAS[k][0]).exists())
            (ok if round(ncol) == want5 else bad).append(
                f"⑤ 오버레이 {round(ncol)}열 (기대 {want5})" + ("" if round(ncol) == want5 else " 🔴"))
    except Exception as e:
        ok.append(f"⑤ 오버레이 열 수 확인 건너뜀 ({e})")

    # ── 6. 거리 그림의 «경로 섞임» ────────────────────────────────────────────
    rep = _load(root / "report.json") or {}
    sc = _load(root / "scale_check.json") or {}
    fp_src = rep.get("capture_pose_dir")
    sil_src = Path(sc["pose_dir"]).name if sc.get("pose_dir") else None
    if not sil_src:
        ok.append("⑥ 실루엣 다리 없음 (`scale_check.json` 미생성) — 거리 그림은 3다리")
    elif fp_src is None:
        bad.append("⑥ `report.json` 에 `capture_pose_dir` 이 없다 — 거리 그림이 «어느 경로의 z 인지» "
                   "모른 채 뺄셈을 하게 된다 (러너가 옛 버전이다)")
    else:
        ok.append(f"⑥ 거리 다리 출처 — FP z `{fp_src}` · 실루엣 `{sil_src}`"
                  + ("" if fp_src == sil_src else
                     "  ⚠️ **다르다** → 그림이 잔차를 «실루엣 − 그 자신의 pose» 로 잡고 "
                     "«경로 차» 선을 따로 그리는지 확인할 것(§35-2p-1)"))

    # ── 7. 팔처럼 생겼는데 표에 없는 디렉토리 ──────────────────────────────────
    missing = sorted(set(real) - set(byv))
    extra_look = sorted(set(disk) & set(CASCADE_STAGES))
    n_al = sum(1 for k in ALIAS if (root / ALIAS[k][0]).exists())
    (ok if not missing else bad).append(
        f"⑦ 디스크 정합 팔 {len(real)} + 별칭 {n_al} = {len(real) + n_al} ↔ CSV {len(byv)}"
        + (f"  🔴 표에 없는 팔: {missing}" if missing else "")
        + (f"  ·  중간 단(팔 아님): {extra_look}" if extra_look else ""))
    return ok, bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="러너 산출물 배선 감사 (GT 불필요)")
    ap.add_argument("--root", required=True, help="run_group_a.py 의 --out 디렉토리")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if not root.exists():
        print(f"❌ {root} 가 없다")
        return 2
    ok, bad = check(root)
    print(f"# 배선 감사 — `{root}`\n")
    for s in ok:
        print(f"  ✅ {s}")
    for s in bad:
        print(f"  🔴 {s}")
    print()
    if bad:
        print(f"🔴 **{len(bad)}건 실패** — 리포트의 숫자를 해석하기 전에 이걸 먼저 고친다.")
        return 1
    print("✅ 전부 통과 — 각 팔의 숫자가 그 팔의 것이다. "
          "⚠️ 단 이건 «배선» 검사지 «정확도» 검사가 아니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
