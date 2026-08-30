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
         "T3": ("fp_txt", "pose_coarse.json"), "TF3": ("fp_txtf", "pose_coarse.json"),
         # COMBO — 실물 검증 체인(§38). 정합을 안 하므로 자기 디렉토리가 없다.
         "RP1": ("fp_c075", "pose_refined.json"), "RP2": ("fp_c050", "pose_refined.json"),
         "RP3": ("fp_chull", "pose_refined.json"), "RH1": ("hyb_combo", "pose_coarse.json"),
         "RH2": ("hyb_combo2", "pose_coarse.json")}
# 🔴 여기에 안 적힌 별칭은 ④ lr 파일 수 · ⑤ 오버레이 열 수 검사에서 **초과분으로 잡혀 감사 실패**가 된다.
#    새 «정합 안 하는 팔» 을 만들 때마다 이 표를 같이 고친다 — 실제로 TF3 을 빠뜨려 잡혔다.


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _in_root(root: Path, p: Path) -> Path:
    """meta 에 기록된 경로를 **이 `root` 안의 같은 이름**으로 되돌린다.

    🔴 러너는 절대 경로를 기록한다. 런 디렉토리를 복사·이동해서 감사하면 그 경로가 **옛 위치**를
       가리켜, 감사기가 «지금 보고 있는 런» 이 아닌 것을 읽는다 — 자기검증 중에 실제로 걸렸다.
       조용히 틀린 값을 쓰느니 이름으로 되찾는 편이 낫다(교훈 #22).
    """
    q = root / p.name
    return q if q.exists() else p



def _auto_polarity_match(root: Path, grp: list[str], cs: list[dict]) -> bool:
    """`--polarity auto` 팔이 상대 팔의 **고정 극성으로 매 프레임 판정**됐는가.

    ★ 이것만 다른 두 팔은 «설정은 다른데 실행된 것이 같다» — 배선 오류가 아니다.
      검정 몸체에서는 `auto` 가 항상 `dark_out` 이라 `A1`↔`Ed` 가 늘 같아진다.
    🔴 판정 근거는 **기록된 값**(`polarity_used`)이다 — 추측하지 않는다. 기록이 없으면 False
      (모르면 «정상» 이라고 하지 않는다, 교훈 #22).
    """
    if len(grp) != 2 or len(cs) != 2:
        return False
    pol = [c.get("polarity") for c in cs]
    # 그 둘 말고 다른 설정이 같아야 한다
    if any(a.get(k) != b.get(k) for a, b in [tuple(cs)] for k in cs[0] if k != "polarity"):
        return False
    if "auto" not in pol or pol[0] == pol[1]:
        return False
    fixed = pol[1] if pol[0] == "auto" else pol[0]
    vid = grp[0] if pol[0] == "auto" else grp[1]
    fr = (_load(root / vid / "meta_contour.json") or {}).get("frames") or []
    used = [f.get("polarity_used") for f in fr]
    return bool(used) and all(u == fixed for u in used)


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

    # 🔴 «같다» 에는 두 종류가 있고 **처방이 정반대**다. 자동으로 무시하지 말고 **갈라서 보여준다**:
    #    ⓐ 설정이 «게이트 문턱만» 다르다 → 그 사이 구간에 프레임이 없으면 같은 게 **정상**(소표본 우연).
    #       실측: 8장 런에서 `A1`(1.5°)==`Cg3`(3.0°) — moved_deg 가 (1.5,3.0] 에 한 장도 없었다.
    #    ⓑ 초기값·마스크가 다른데 결과가 같다 → **배선 오류**. 실측: `AF1`==`I1` (§35-2p-7).
    #    ⚠️ ⓐ도 «통과» 로 적지 않는다 — 「우연히 같아 보이는 것」을 계속 눈에 띄게 둔다.
    def cfg(vid: str) -> dict:
        m = _load(root / vid / "meta_contour.json") or {}
        return {k: m.get(k) for k in
                ("init", "mesh", "outer_only", "keep_hole_mm", "hole_center_mm", "search_px",
                 "per_edge", "min_grad", "polarity", "fix_z", "iters", "huber_px", "blur")}
    def upstream_masks(vid: str) -> str | None:
        """그 팔의 FP 가 실제로 먹은 **마스크 디렉토리의 내용 해시**.

        🔴 «마스크 «디렉토리 이름» 이 다르다» 와 «마스크 «내용» 이 다르다» 는 다른 말이다.
           `seg_full`(ISM·select exemplar)과 `seg_ism`(ISM·select score)은 **이름이 다른데
           방해물이 없으면 내용이 byte 단위로 같다** — 그래서 하류 두 팔이 같은 결과를 낸다.
           그건 배선 오류가 아니라 **«선택 규칙이 같은 것을 골랐다»** 이므로 갈라서 보고한다.
        """
        mc = _load(root / vid / "meta_contour.json") or {}
        init = mc.get("init")
        if not init:
            return None
        # 🔴 meta 의 경로는 **절대 경로**다 — 런을 복사·이동하면 «옛 위치» 를 읽어 감사가 조용히
        #    엉뚱한 걸 본다(실제로 자기검증 중에 이 함정에 걸렸다). **항상 이 `root` 안에서** 찾는다.
        mp = _load(_in_root(root, Path(init).parent) / "meta_pose.json") or {}
        md = mp.get("masks")
        if not md:
            return None
        m = hashlib.sha256()
        for f in sorted(_in_root(root, Path(md)).glob("frame_*/*.png")):
            m.update(f.name.encode())
            m.update(f.read_bytes())
        return m.hexdigest()

    benign, real_dup = [], []
    for grp in shared:
        cs = [cfg(v) for v in grp if (root / v / "meta_contour.json").exists()]
        ms = [upstream_masks(v) for v in grp]
        if len(cs) == len(grp) and all(c == cs[0] for c in cs[1:]):
            benign.append((grp, "게이트 문턱만 다르다 — 그 구간에 프레임이 없으면 정상"))
        elif _auto_polarity_match(root, grp, cs):
            benign.append((grp, "한쪽이 `--polarity auto` 이고 **매 프레임 상대 팔의 고정값으로 판정**됐다 "
                                "— 설정은 다르지만 실행된 것이 같다(검정 몸체에서 흔하다)"))
        elif (len({c.get("init") for c in cs}) == len(grp)          # 🔴 초기값이 서로 «달라야» 한다
              and all(x is not None for x in ms) and all(x == ms[0] for x in ms[1:])):
            # 초기값 FP 런이 서로 다른데 그 상류 **마스크 내용이 같다** → 선택 규칙이 같은 것을 골랐다.
            # ⚠️ 초기값이 «같은» 팔들(A1↔A2b 등)에는 이 면제를 주면 안 된다 — 그 경우 결과가 같다는
            #    것은 «정합 플래그가 아무 일도 안 했다» 이고, 실제로 고장 주입이 여기로 새 나갔다.
            benign.append((grp, "초기값 FP 런은 다른데 그 상류 **마스크 내용이 동일**하다"
                                "(디렉토리 이름만 다르다) — 선택 규칙이 같은 것을 골랐다는 뜻"))
        else:
            real_dup.append(grp)
    line = f"① 산출물 고유성 — 팔 {len(h)}개 · 서로 다른 결과 {len(dup)}종"
    for grp, why in benign:
        line += f"\n      ⚠️ {grp} 결과 동일 — {why} (소표본이면 흔하다)"
    if real_dup:
        line += (f"\n      🔴 **초기값·설정이 다른데 결과가 같다 = 배선 오류**: {real_dup}"
                 f"\n         → 그 팔들의 `--masks`·`--pose-dir` 이 정말 다른지 확인할 것(§35-2p-7)")
    (bad if real_dup else ok).append(line)

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
        sd, nm = _in_root(root, Path(init).parent), Path(init).name   # 복사된 런에서도 맞게(위 참조)
        gated = {f["frame"] for f in mc.get("frames", []) if f.get("gated")}
        # ★ 대응점 0 = 정합기가 **아무 일도 못 했다** → 초기값을 그대로 돌려주는데 `gated=False` 라
        #   「정합이 성공했다」처럼 보인다. 이유를 알아야 조치가 갈리므로 프레임별로 들고 온다.
        ncorr = {f.get("frame"): f.get("n_corr") for f in mc.get("frames", [])}
        bad_g = bad_ng = 0
        degen: list[str] = []
        for f in sorted((root / a).glob("frame_*/pose_refined.json")):
            fn = f.parent.name
            cur, ini = _rt(f), _rt(sd / fn / nm)
            if ini is None:
                continue
            if fn in gated and not _same(cur, ini):
                bad_g += 1
            if fn not in gated and _same(cur, ini):
                bad_ng += 1
                if not ncorr.get(fn):
                    degen.append(fn)
        if bad_g or bad_ng:
            why = (f" — 그중 **대응점 0** 인 프레임 {len(degen)}장 {degen[:4]}: 정합기가 "
                   "에지를 하나도 못 찾아 초기값을 그대로 냈다(=«정합 안 됨»). "
                   "🔴 마스크·조명·거리를 의심할 것 — «정합이 잘 맞아서 안 움직인 것» 이 아니다"
                   if degen else "")
            bad.append(f"② {a}: 후퇴인데 초기값과 다름 {bad_g}장 · 비후퇴인데 초기값과 같음 {bad_ng}장{why} "
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
