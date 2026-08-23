"""**하이브리드 초기값** — 회전은 `coarse`, 평행이동은 `refined` 에서 받는다 (`RESULTS.md §27-7`).

    envs/pose/bin/python -m spatial_vision.eval.hybrid_pose \
        --r-dir runs/real01_A/fp_ns2 --r-name pose_coarse.json \
        --t-dir runs/real01_A/fp_s2  --t-name pose_refined.json \
        --out runs/real01_A/fp_hyb

왜 필요한가
    `refine` 은 «켜냐 끄냐» 가 아니라 **«어느 자유도를 어디서 받느냐»** 다(§27-7, n=120):

        산출 단계            원거리 full R / t      근접 flange R / t
        pose_coarse.json     **0.549** / 1.713      **0.510 / 0.928**
        pose_refined.json    0.737 / **1.280**      0.656 / 1.104

    원거리는 고전적 맞바꿈(R↑ t↓)이고 근접 flange 는 refine 이 **둘 다** 악화시킨다.
    **회전은 coarse, 평행이동은 refined** 로 받으면 원거리·근접·융합 세 곳 모두에서 이긴다.
    단일 시점 경로가 **R 0.367 → 0.245 (1.5배)** 로 좋아진다 — hand-eye 도 다중 시점도 필요 없다.

    다중 시점용 `eval.fuse_pose --pred-name/--pred-name-t` 가 같은 일을 하지만 그쪽은
    `--near` 에 **`pose_gt.json` 을 요구**해서 **실환경에서 못 쓴다.** 이 도구는 GT 를 안 쓴다.

무엇을 내나
    `<out>/frame_*/pose_coarse.json` — 하류(`refine_contour --pose-name pose_coarse.json`)가
    그대로 먹을 수 있는 이름으로 쓴다. `source` 에 두 출처를 남긴다.

⚠️ **clean 한정이다** (§26-4). depth 가 오염되면 `refined` 가 붕괴하므로 `coarse` 단독으로
   자동 축퇴해야 한다 — 러너는 후퇴율이 낮은 쪽을 고르는 §32 판정 절차로 그걸 대신한다.
🔴 두 디렉토리의 pose 는 **같은 프레임·같은 물체**여야 한다. 섞이면 회전과 평행이동이 서로
   다른 관측에서 와서 조용히 틀린다 — 그래서 프레임이 한쪽에만 있으면 **건너뛰고 개수를 보고**한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="회전=coarse · 평행이동=refined 하이브리드 초기값")
    ap.add_argument("--r-dir", required=True, help="회전을 가져올 디렉토리")
    ap.add_argument("--r-name", default="pose_coarse.json")
    ap.add_argument("--t-dir", required=True, help="평행이동을 가져올 디렉토리")
    ap.add_argument("--t-name", default="pose_refined.json")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    rd, td, out = Path(a.r_dir), Path(a.t_dir), Path(a.out)
    frames = sorted(p.name for p in rd.glob("frame_*") if (p / a.r_name).exists())
    if not frames:
        print(f"❌ {rd}/frame_*/{a.r_name} 이 없다")
        return 2

    n, skip = 0, []
    for fn in frames:
        R, T = load(rd / fn / a.r_name), load(td / fn / a.t_name)
        if R is None or T is None:
            skip.append(fn)
            continue
        od = out / fn
        od.mkdir(parents=True, exist_ok=True)
        (od / "pose_coarse.json").write_text(json.dumps(
            {"R": R["R"], "t_mm": T["t_mm"],
             "source": f"hybrid(R={rd.name}/{a.r_name}, t={td.name}/{a.t_name})"}, indent=2))
        n += 1

    meta = {"stage": "hybrid_pose", "r": f"{rd}/{a.r_name}", "t": f"{td}/{a.t_name}",
            "n_written": n, "n_skipped": len(skip), "skipped": skip[:20]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "meta_hybrid.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    # ⚠️ 개수를 반드시 찍는다 — 한쪽 디렉토리가 비면 조용히 0장을 쓰고 하류가 «pose 없음» 이 된다.
    print(f"하이브리드 {n}장" + (f" · 건너뜀 {len(skip)}장 ({skip[:3]}…)" if skip else "")
          + f"  → {out}")
    return 0 if n else 2


if __name__ == "__main__":
    raise SystemExit(main())
