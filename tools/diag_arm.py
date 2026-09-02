#!/usr/bin/env python3
"""**러너 출력에서 팔 하나만 골라 diag 시트를 낸다** — 이미 있는 산출물만 쓴다(재계산 0).

왜 이 도구가 따로 있나
    `viz.diag_sheet` 는 디렉토리를 **네 개**(캡처·분할·depth·pose) 손으로 받는다. 그런데 그 이름이
    **러너 `--mode` 에 따라 달라서** 손으로 적으면 틀리기 쉽다(`hyb_combo` 는 `--mode combo` 일 때만 생긴다).
    이 도구는 **`run_meta.json` 에서 캡처·CAD 를 읽고 팔 이름으로 나머지를 찾아** 준다.

    🔴 **못 찾으면 «왜 없는지» 를 말한다** — 조용히 빈 패널을 그리지 않는다.

특별 취급 — 하이브리드
    `RH1`/`RH2` 는 **파일 병합 산출물**이라 `--mode combo` 를 안 돌렸으면 없다.
    그 경우 **기반 FP 디렉토리(`fp_c075`/`fp_c050`)가 있으면 즉석에서 만든다**(`--make-hybrid`, 추론 0).

flange 패널
    🔴 **`RH*`·`RP*` 는 flange 마스크를 «분할이 아니라 CAD 투영» 으로 만든다** — 파일명이
    `mask_flange_proj.png` 이고 **pose 디렉토리**에 있다. 실환경엔 GT 가 없으므로 그것이
    **stage2 가 실제로 소비한 유일한 flange 마스크**다. 이 도구가 알아서 그쪽을 가리킨다.

사용
    envs/pose/bin/python tools/diag_arm.py --run runs/real01_A --arm RH1 --frames 6
    envs/pose/bin/python tools/diag_arm.py --run runs/real01_A --list      # 무엇이 있나만 보기
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY_POSE = str(ROOT / "envs/pose/bin/python")

# 팔 → (pose 디렉토리, pose 파일, 분할 디렉토리, 하이브리드 기반)  — `run_group_a.py:770-778` 과 같아야 한다
ARMS: dict[str, tuple[str, str, str, str | None]] = {
    "RH1": ("hyb_combo",  "pose_coarse.json",  "seg_txt", "fp_c075"),
    "RH2": ("hyb_combo2", "pose_coarse.json",  "seg_txt", "fp_c050"),
    "RP1": ("fp_c075",    "pose_refined.json", "seg_txt", None),
    "RP2": ("fp_c050",    "pose_refined.json", "seg_txt", None),
    "RP3": ("fp_chull",   "pose_refined.json", "seg_txt", None),
    "T1":  ("fp_txt",     "pose_refined.json", "seg_txt", None),
    "T3":  ("fp_txt",     "pose_coarse.json",  "seg_txt", None),
    "TF3": ("fp_txtf",    "pose_coarse.json",  "seg_txtf", None),
    "I3":  ("fp_ism",     "pose_coarse.json",  "seg_ism", None),
    "A3":  ("fp_ns2",     "pose_coarse.json",  "seg",     None),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="러너 출력 디렉토리 (`run_group_a.py --out` 로 준 것)")
    ap.add_argument("--arm", default="RH1", choices=sorted(ARMS))
    ap.add_argument("--in", dest="in_dir", default=None, help="캡처 디렉토리 (기본: run_meta.json 의 `in`)")
    ap.add_argument("--obj", default=None, help="기본: run_meta.json 의 `obj`")
    ap.add_argument("--out", default=None, help="기본: <run>/diag_<arm>")
    ap.add_argument("--frames", type=int, default=6)
    ap.add_argument("--pick", default=None, help="프레임 직접 지정 (쉼표)")
    ap.add_argument("--all", action="store_true", help="개별 장을 전 프레임에")
    ap.add_argument("--mesh", default="top_flange.ply",
                    help="6번 pose 패널에 투영할 메쉬. **기본 `top_flange.ply`**(= pose 좌표계의 부품). "
                         "FOUP 전체 윤곽을 보고 싶으면 `full.ply`")
    ap.add_argument("--panel5", default="stage2", choices=["valid", "stage2"],
                    help="5번 패널. **기본 `stage2`** = stage2 가 실제로 먹는 «flange 로 가린 depth». "
                         "`valid` 는 범위 검사라 거의 항상 100%% 여서 정보가 없다")
    ap.add_argument("--order", default="pipeline", choices=["default", "pipeline"],
                    help="패널 배치. **기본 `pipeline`** = 인과 순서(원본 → depth → mask_full → "
                         "mask_flange → stage2 입력 → pose). `mask_flange` 는 분할이 아니라 "
                         "**stage1 pose 의 CAD 투영**이라 `mask_full` 옆에 두면 오해된다")
    ap.add_argument("--make-hybrid", action="store_true",
                    help="하이브리드 디렉토리가 없으면 기반 FP 에서 즉석 생성(추론 0)")
    ap.add_argument("--list", action="store_true", help="무엇이 있는지만 출력하고 끝낸다")
    a = ap.parse_args(argv)

    run = Path(a.run)
    if not run.is_dir():
        print(f"❌ `{run}` 이 없다", file=sys.stderr)
        return 2

    meta = {}
    mp = run / "run_meta.json"
    if mp.exists():
        try:
            meta = json.loads(mp.read_text())
        except Exception as e:                                   # noqa: BLE001
            print(f"⚠️ run_meta.json 을 못 읽었다: {e}")

    cap = Path(a.in_dir or meta.get("in", ""))
    obj = Path(a.obj or meta.get("obj", ""))

    # ── 무엇이 있나 ────────────────────────────────────────────────────
    have = sorted(p.name for p in run.iterdir() if p.is_dir())
    if a.list:
        print(f"# `{run}` 안의 디렉토리 {len(have)}개\n")
        print("  " + " · ".join(have))
        print("\n# 이 런에서 그릴 수 있는 팔")
        for k, (pd, pn, sd, base) in ARMS.items():
            ok = (run / pd / "frame_0000" / pn).exists()
            alt = base and (run / base / "meta_pose.json").exists()
            mark = "✅" if ok else ("🟡 기반만 있음 → `--make-hybrid`" if alt else "❌")
            print(f"  {k:5s} {mark:28s} pose={pd}/{pn}  seg={sd}")
        return 0

    pdir_n, pname, sdir_n, base_n = ARMS[a.arm]
    pdir, sdir = run / pdir_n, run / sdir_n
    st = run / "st"

    # ── 하이브리드가 없으면 만들어 준다 ────────────────────────────────
    if not (pdir / "frame_0000" / pname).exists() and base_n:
        base = run / base_n
        if not (base / "meta_pose.json").exists():
            print(f"❌ `{pdir}` 도 `{base}` 도 없다 — 이 런에는 `{a.arm}` 이 없다.\n"
                  f"   `--list` 로 무엇이 있는지 보고 다른 팔을 고르거나, "
                  f"러너를 `--mode combo --sam3-text` 로 다시 돌린다.", file=sys.stderr)
            return 2
        if not a.make_hybrid:
            print(f"🟡 `{pdir}` 이 없는데 기반 `{base}` 는 있다 — `--make-hybrid` 를 주면 "
                  f"즉석에서 만든다(파일 병합, 추론 0).", file=sys.stderr)
            return 2
        print(f"⚙️ 하이브리드 생성: R={base_n}/pose_coarse.json · t={base_n}/pose_refined.json", flush=True)
        r = subprocess.run([PY_POSE, "-m", "spatial_vision.eval.hybrid_pose",
                            "--r-dir", str(base), "--r-name", "pose_coarse.json",
                            "--t-dir", str(base), "--t-name", "pose_refined.json",
                            "--out", str(pdir)], cwd=ROOT)
        if r.returncode:
            return r.returncode

    # ── 점검 — 없으면 «왜» 를 말한다 ───────────────────────────────────
    checks = [
        ("캡처", cap, "frame_0000/left.png", "`--in` 으로 촬영 디렉토리를 직접 준다"),
        ("CAD", obj, "full.ply", "`--obj assets/obj/foup_300_semi_r2`"),
        ("stereo depth", st, "frame_0000/depth.png", "러너가 `st` 를 만들었는지 확인"),
        ("분할(full)", sdir, "frame_0000/mask_full.png", f"`{sdir_n}` 은 그 경로를 돌려야 생긴다"),
        ("pose", pdir, f"frame_0000/{pname}", "위 참조"),
    ]
    print(f"# `{a.arm}` diag — 입력 점검\n")
    bad = False
    for lab, d, probe, hint in checks:
        ok = bool(d) and (Path(d) / probe).exists()
        print(f"  {'✅' if ok else '❌'} {lab:14s} {str(d) or '(비어 있음)'}")
        if not ok:
            print(f"       ↳ `{probe}` 이 없다 — {hint}")
            bad = True
    if bad:
        print("\n❌ 위 항목을 채우고 다시 실행한다.", file=sys.stderr)
        return 2

    # flange 패널 — RH*/RP* 는 CAD 투영본이 pose 쪽(또는 기반 FP)에 있다
    fl_dir, fl_name = None, "mask_flange.png"
    for cand in ([run / base_n] if base_n else []) + [pdir, run / "fp_c075", run / "fp_txt"]:
        if (Path(cand) / "frame_0000" / "mask_flange_proj.png").exists():
            fl_dir, fl_name = cand, "mask_flange_proj.png"
            break
    if fl_dir is None and (sdir / "frame_0000" / "mask_flange.png").exists():
        fl_dir = sdir
    print(f"  ℹ️ 패널 배치       {a.order}" + ("  (인과 순서 — depth 가 mask 보다 앞)" if a.order=="pipeline" else "  (기존 배치)"))
    print(f"  ℹ️ stage2 패널       {a.panel5}" + ("  (stage2 가 실제로 먹는 flange-가린 depth)" if a.panel5=="stage2" else "  (범위 검사 — 거의 항상 100%)"))
    print(f"  ℹ️ pose 패널 메쉬  {a.mesh}  (기본은 top_flange.ply — FOUP 전체는 `--mesh full.ply`)")
    print(f"  {'✅' if fl_dir else '⚠️'} flange 마스크   "
          f"{fl_dir or '없음 → 3번 패널이 빈다 (RH1 은 정상: 분할로 flange 를 안 만든다)'}"
          + (f"  ({fl_name})" if fl_dir else ""))

    out = Path(a.out or run / f"diag_{a.arm}")
    cmd = [PY_POSE, "-m", "spatial_vision.viz.diag_sheet",
           "--in", str(cap), "--out", str(out),
           "--seg-full", str(sdir), "--depth-dir", str(st),
           "--pose-dir", str(pdir), "--pose-name", pname, "--obj", str(obj), "--mesh", a.mesh, "--panel5", a.panel5, "--order", a.order]
    if fl_dir:
        cmd += ["--seg-flange", str(fl_dir), "--flange-name", fl_name]
    if a.pick:
        cmd += ["--pick", a.pick]
    else:
        cmd += ["--frames", str(a.frames)]
    if a.all:
        cmd += ["--all"]
    print("\n$ " + " ".join(cmd) + "\n", flush=True)   # 🔴 flush — 안 하면 자식 출력이 먼저 나온다
    return subprocess.run(cmd, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
