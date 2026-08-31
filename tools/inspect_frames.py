#!/usr/bin/env python3
"""러너 산출물에서 **프레임마다 한 장씩** «마스크 + 최종 pose» 를 색 달리해 겹친 이미지를 낸다.

왜 도구로 두나
    `viz.seg_compare` 가 이미 이 일을 하는데, **팔마다 디렉토리와 pose 파일 이름이 다르다**
    (`hyb_combo/pose_coarse.json` · `fp_chull/pose_refined.json` · `hyb_f005/pose_coarse.json` …).
    손으로 조립하면 하나만 틀려도 **조용히 «없음» 으로 그려지고** 시트를 오독한다(교훈 #88).
    여기서 배선을 한 번만 정하고, **없는 팔은 이유를 찍고 뺀다.**

무엇을 내나 (`<run>/inspect/` 아래, 프레임마다 한 장)
    `arms/`    — 마스크 1개(기준 프롬프트) + **pose 팔 3개**(RH1·RH2·RP3).
                 마스크가 같으므로 **«pose 알고리즘 차이» 만** 남는다.
    `prompts/` — **프롬프트마다 마스크 + 그 pose**. 마스크가 다르므로 «분할 차이» 가 보인다.
    `all/`     — 위를 전부 겹친 것. 한 장에서 다 보고 싶을 때.

🔴 **읽는 법** — 실선 채움 `[M]` = 마스크 · **점선 + 십자** `[P]` = pose 투영 실루엣.
   ① 점선이 실선 안에 잘 들어가면 그 팔은 «마스크와 합의» 다.
   ② 점선끼리 어긋나면 그게 **팔 사이 오차**다(GT 가 없으니 «누가 맞나» 는 이걸로 못 정한다 —
      **어느 쪽이 사진의 진짜 테두리에 붙었나** 를 본다).
   ③ 흰 십자·회색 타원은 화면 중심과 «가장자리» 기준선이다(§34-10 의 사전 위치 가드).

⚠️ pose 투영은 **`full.ply`** 다 — 마스크가 `mask_full` 이라서. 두 메쉬는 원점이 같다.
⚠️ 인터프리터는 **`envs/pose`**(trimesh 필요).

사용
    envs/pose/bin/python tools/inspect_frames.py --in runs/real_zedx_28cm --run runs/R28_combo
    envs/pose/bin/python tools/inspect_frames.py --in ... --run ... --only prompts --prompts f002,f005,f007
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PY = HERE / "envs" / "pose" / "bin" / "python"

# (라벨, 마스크 디렉토리, pose 디렉토리, pose 파일)  — 🔴 팔마다 pose 파일 이름이 다르다
POSE_ARMS = [
    ("RH1", "seg_txt", "hyb_combo", "pose_coarse.json"),
    ("RH2", "seg_txt", "hyb_combo2", "pose_coarse.json"),
    ("RP3_hull", "seg_txt", "fp_chull", "pose_refined.json"),
]


def prompt_arms(run: Path) -> list[tuple[str, str, str, str]]:
    """프롬프트 팔을 **디스크에서** 찾는다 — tag 를 미리 못 안다(`--mode prompts`, §41-10)."""
    out = []
    if (run / "seg_txt").exists():          # 기준 프롬프트(`--text-prompt`)는 접미사가 없다
        out.append(("f002_base", "seg_txt", "fp_c075", "pose_refined.json"))
    for d in sorted(run.glob("seg_txt_*")):
        tag = d.name[len("seg_txt_"):]
        out.append((tag, d.name, f"hyb_{tag}", "pose_coarse.json"))
    return out


def label_of(run: Path, seg_dir: str) -> str:
    """마스크 라벨에 **프롬프트 문장**을 넣는다 — `f005` 만 보고는 무엇인지 알 수 없다(교훈 #88)."""
    for q in sorted((run / seg_dir).glob("frame_*/det_full.json"))[:1]:
        p = json.loads(q.read_text()).get("prompt")
        if p:
            return p[:46]
    return seg_dir


def build(run: Path, arms: list, view: str) -> tuple[list[str], list[str]]:
    """살아 있는 팔만 `--seg`/`--pose` 인자로. 🔴 없는 것은 **이유를 찍고 뺀다**(교훈 #22)."""
    seg, pose, seen = [], [], set()
    for lab, sd, pd, pn in arms:
        n = len(list((run / pd).glob(f"frame_*/{pn}")))
        if n == 0:
            print(f"    ⚠️ [{view}] {lab:10s} 건너뜀 — `{pd}/frame_*/{pn}` 이 0개다")
            continue
        if sd not in seen and (run / sd).exists():
            seen.add(sd)
            seg.append(f"{run / sd}:mask_full.png:{label_of(run, sd)}")
        pose.append(f"{run / pd}:{pn}:{lab}  ({n}장)")
    return seg, pose


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="in_dir", required=True, help="촬영 디렉토리 (frame_*/left.png)")
    ap.add_argument("--run", required=True, help="러너 출력 디렉토리 (seg_txt·hyb_combo… 가 있는 곳)")
    ap.add_argument("--out", default=None, help="기본 `<run>/inspect`")
    ap.add_argument("--obj", default="assets/obj/foup_300_semi_r2")
    ap.add_argument("--only", default="arms,prompts,all",
                    help="낼 시점. 쉼표로. `arms` · `prompts` · `all`")
    ap.add_argument("--prompts", default=None,
                    help="프롬프트 tag 를 골라 쓴다(쉼표, 예 `f002_base,f005,f007`). "
                         "안 주면 **디스크에 있는 전부**")
    ap.add_argument("--width", type=int, default=1600, help="프레임당 이미지 가로 픽셀")
    ap.add_argument("--frames", type=int, default=0, help="0 = 전부")
    a = ap.parse_args(argv)

    run, cap = Path(a.run), Path(a.in_dir)
    if not run.exists():
        print(f"❌ `{run}` 이 없다", file=sys.stderr); return 2
    n_frames = len(list(cap.glob("frame_*/left.png")))
    if n_frames == 0:
        print(f"❌ `{cap}` 에 frame_*/left.png 가 없다", file=sys.stderr); return 2
    out = Path(a.out) if a.out else run / "inspect"

    pa = prompt_arms(run)
    if a.prompts:
        want = [x.strip() for x in a.prompts.split(",") if x.strip()]
        miss = [w for w in want if w not in {x[0] for x in pa}]
        if miss:
            print(f"❌ `--prompts` 에 없는 tag: {miss}. 있는 것: {[x[0] for x in pa]}",
                  file=sys.stderr)
            return 2
        pa = [x for x in pa if x[0] in want]

    VIEWS = {"arms": POSE_ARMS, "prompts": pa, "all": POSE_ARMS + pa}
    print(f"★ 프레임 {n_frames}장 · 프롬프트 팔 {len(pa)}개 {[x[0] for x in pa]}")
    rc = 0
    for v in [x.strip() for x in a.only.split(",") if x.strip()]:
        if v not in VIEWS:
            print(f"❌ 모르는 시점: {v}. 가능: {', '.join(VIEWS)}", file=sys.stderr); return 2
        seg, pose = build(run, VIEWS[v], v)
        if not pose:
            print(f"    🔴 [{v}] 그릴 pose 가 하나도 없다 — 건너뛴다"); continue
        if len(pose) > 7:      # `seg_compare.POSE_COLORS` 가 7색이다
            print(f"    ⚠️ [{v}] pose {len(pose)}개 — 색이 순환한다. `--prompts` 로 줄이는 편이 낫다")
        d = out / v
        cmd = [str(PY), "-m", "spatial_vision.viz.seg_compare",
               "--capture", str(cap), "--obj", a.obj, "--mesh", "full.ply",
               "--frames", str(a.frames or n_frames), "--width", str(a.width),
               "--per-frame-dir", str(d), "--out", str(d / "_sheet.png")]
        for s in seg:
            cmd += ["--seg", s]
        for s in pose:
            cmd += ["--pose", s]
        print(f"\n── [{v}] 마스크 {len(seg)} + pose {len(pose)} → {d}/segcmp_frame_*.png")
        rc |= subprocess.run(cmd, cwd=HERE).returncode
    print(f"\n{'✅' if rc == 0 else '🔴'} → {out}")
    print("   실선 채움 [M] = 마스크 · 점선+십자 [P] = pose 투영. "
          "🔴 GT 가 없으므로 «누가 맞나» 가 아니라 **어느 점선이 사진의 진짜 테두리에 붙었나** 를 본다.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
