"""M4 자산 — SAM3 참조 후보 중 **쓸 것만 골라** 배포용 세트를 만든다.

    # ① 후보를 넉넉히 만든다 (기존 스크립트 그대로)
    envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs \
        --from runs/ref42 --obj assets/obj/foup_300_semi --n 42 --out-name sam3_refs42

    # ② 후보 전부로 프로브 프레임을 분할하고 **참조별 마스크를 남긴다**
    envs/seg_sam3/bin/python -m spatial_vision.stages.segment_sam3 \
        --in runs/probe --out runs/probe_perref --target full \
        --refs assets/obj/foup_300_semi/sam3_refs42 \
        --refs-mode independent --save-per-ref

    # ③ 면적 기준으로 상위 k 장을 골라 새 자산으로 굳힌다  ← 이 스크립트
    envs/seg_sam3/bin/python -m spatial_vision.cad.select_sam3_refs \
        --refs assets/obj/foup_300_semi/sam3_refs42 --probe runs/probe_perref \
        --obj assets/obj/foup_300_semi --k 5 --out-name sam3_refs_top5

왜 `build_sam3_refs.py` 를 안 고치고 새로 만들었나
    ①은 "후보를 만드는" 일이고 ③은 "고르는" 일이라 **단계가 다르다**. 후보 세트는 그대로 남겨 두어야
    기준을 바꿔가며 다시 고를 수 있고, 실패했을 때 되돌아갈 곳이 된다.

왜 SAM3 를 여기서 안 돌리나
    ②가 이미 참조별 마스크를 디스크에 남긴다. 이 스크립트는 **numpy + cv2 만** 쓴다 —
    GPU 도 모델 로딩도 필요 없고, 기준을 바꿔 몇 번을 다시 돌려도 공짜다.
    (스테이지 경계를 디스크로 두는 이 워크스페이스의 규약과 같은 이유다.)

무엇을 기준으로 고르나 (실측 근거는 RESULTS.md §19)
    **참조를 단독으로 썼을 때 나오는 마스크 면적의 중앙값**이 큰 순.
    - GT 가 **필요 없다** — 자기 출력의 픽셀을 세는 것뿐이다. 실환경에서 그대로 쓴다.
      (정답 대비 IoU 로 고르는 방법은 sim 에서만 가능하고, 게다가 표본이 적으면 면적보다 **못하다**.)
    - IoU 0.770(균등 간격) → **0.888**, 오선택 2 → **0**. 전체 42장(0.798)도, GT 를 쓰는
      oracle(0.846)도 이긴다.
    - **k=5 가 최적이다.** 8·12·42장은 더 나쁘다 — 나쁜 참조가 과반 투표를 오염시킨다.
    - 추론도 같이 빨라진다: 42장 10.9s/frame → 5장 **1.3s/frame**.

⚠️ 성립 조건 — 신규 객체에 쓰기 전에 확인할 것
    이 기준은 실패가 **과소분할**(덜 잡음)일 때 성립한다. 면적↔recall 상관 +0.75 이고,
    오선택조차 "파편을 집는" 형태라 면적이 4분의 1(46k vs 188k)이어서 같이 걸러졌다.
    **반사·투명체처럼 배경을 삼키는(과대분할) 객체에서는 정반대로 작동한다.**
    `--guard` 가 그 방어선이다 — 후보 전체의 과반 융합 마스크보다 지나치게 큰 참조를 버린다.
    가드가 여러 장을 쳐내면 그 객체는 이 기준을 쓰면 안 된다는 신호다.

⚠️ 프로브 프레임 수 (RESULTS.md §19)
    20장이면 전체와 사실상 같다(IoU 0.887 vs 0.888). 10장도 쓸 만하다(0.882).
    **5장 이하는 권하지 않는다** — 평균은 비슷해도 운이 나쁘면 0.66 까지 떨어진다.

출력  assets/obj/<id>/<out-name>/  ref_0.png …  refs.json
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


def load_per_ref(probe: Path, n_refs: int) -> tuple[np.ndarray, list[Path], np.ndarray]:
    """프로브 런에서 참조별 마스크를 읽는다.

    반환 (면적 (F, n_refs), 프레임 목록, 프레임별 과반 융합 면적 (F,)).
    실패한 질의는 스테이지가 1×1 을 쓰므로 **면적 0** 으로 잡힌다 — 그것이 곧 나쁜 참조의 신호다.
    """
    frames = sorted([p for p in probe.glob("frame_*") if (p / "per_ref").is_dir()])
    if not frames:
        raise SystemExit(f"❌ {probe} 에 frame_*/per_ref/ 가 없다. "
                         f"segment_sam3 을 --refs-mode independent --save-per-ref 로 돌렸나?")

    # 마스크 해상도는 최빈값을 정본으로 본다(실패 마스크 1×1 을 배제하기 위해)
    shapes = Counter()
    for f in frames:
        for p in (f / "per_ref").glob("ref*.png"):
            m = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if m is not None and m.size > 1:
                shapes[m.shape] += 1
    if not shapes:
        raise SystemExit(f"❌ {probe} 의 참조 마스크가 전부 비어 있다.")
    shape = shapes.most_common(1)[0][0]

    area = np.zeros((len(frames), n_refs), dtype=np.int64)
    consensus = np.zeros(len(frames), dtype=np.int64)
    for fi, f in enumerate(frames):
        votes = np.zeros(shape, dtype=np.int16)   # 픽셀별 득표 → 과반이 합의 마스크
        for i in range(n_refs):
            m = cv2.imread(str(f / "per_ref" / f"ref{i:03d}.png"), cv2.IMREAD_GRAYSCALE)
            if m is None or m.shape != shape:
                continue                      # 실패 질의 → 면적 0
            b = m > 127
            area[fi, i] = int(b.sum())
            votes += b
        consensus[fi] = int((votes * 2 > n_refs).sum())
    return area, frames, consensus


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="SAM3 참조 후보 중 마스크 면적 상위 k 장을 골라 배포 세트를 만든다 (GT 불필요)")
    ap.add_argument("--refs", required=True, help="후보 참조 디렉토리 (refs.json 포함)")
    ap.add_argument("--probe", required=True,
                    help="후보 전부로 돌린 분할 런. frame_*/per_ref/refNNN.png 가 있어야 한다")
    ap.add_argument("--obj", required=True, help="assets/obj/<obj_id>")
    ap.add_argument("--k", type=int, default=5, help="고를 장수 (실측 최적 5)")
    ap.add_argument("--guard", type=float, default=1.2,
                    help="과대분할 방어 — 면적이 '후보 과반 융합'의 이 배수를 넘으면 버린다")
    ap.add_argument("--out-name", default=None, help="기본값: <후보디렉토리명>_top<k>")
    ap.add_argument("--dry-run", action="store_true", help="순위만 출력하고 쓰지 않는다")
    args = ap.parse_args(argv)

    refs_dir = Path(args.refs)
    meta = json.loads((refs_dir / "refs.json").read_text())
    cand = meta["refs"]
    n = len(cand)

    area, frames, consensus = load_per_ref(Path(args.probe), n)
    if len(frames) < 10:
        print(f"⚠️ 프로브 프레임 {len(frames)}장 — 10장 이상을 권한다(RESULTS.md §19). "
              f"적으면 운에 따라 나쁜 조합이 뽑힌다.")

    med = np.median(area, axis=0)
    con_med = float(np.median(consensus))
    limit = con_med * args.guard

    order = np.argsort(-med)
    print(f"후보 {n}장 · 프로브 {len(frames)}프레임 · 과반 융합 면적 중앙값 {con_med:,.0f}px "
          f"→ 가드 상한 {limit:,.0f}px ({args.guard}×)\n")
    print(f"{'순위':>4s} {'후보':>5s} {'이미지':>14s} {'면적중앙':>10s} {'가드':>5s}  출처")
    kept: list[int] = []
    for rank, i in enumerate(order, 1):
        over = med[i] > limit
        if not over and len(kept) < args.k:
            kept.append(int(i))
            mark = "★"
        else:
            mark = "✗" if over else " "
        print(f"{mark}{rank:3d} {i:5d} {cand[i]['image']:>14s} {med[i]:10,.0f} "
              f"{'초과' if over else '  -':>5s}  {cand[i].get('source', '')}")

    n_over = int((med > limit).sum())
    if n_over:
        print(f"\n⚠️ 가드에 걸린 후보 {n_over}장 — **과대분할**이 있다는 뜻이다. "
              f"여러 장이면 이 객체에는 면적 기준을 쓰면 안 된다(RESULTS.md §19 성립 조건).")
    if len(kept) < args.k:
        print(f"\n❌ 가드를 통과한 후보가 {len(kept)}장뿐이라 k={args.k} 를 못 채운다.")
        return 2
    if args.dry_run:
        print("\n(--dry-run: 쓰지 않았다)")
        return 0

    out_name = args.out_name or f"{refs_dir.name}_top{args.k}"
    out = Path(args.obj) / out_name
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("ref_*.png"):
        f.unlink()

    picked = []
    for k, i in enumerate(kept):
        shutil.copy(refs_dir / cand[i]["image"], out / f"ref_{k}.png")
        r = dict(cand[i])
        r["image"] = f"ref_{k}.png"
        # 어느 후보였는지·왜 뽑혔는지를 남긴다 — 자산만 보고 재현할 수 있어야 한다
        r["selected_from"] = {"dir": str(refs_dir), "index": int(i),
                              "image": cand[i]["image"], "median_area_px": int(med[i])}
        picked.append(r)
        print(f"  ref_{k}.png ← {cand[i]['image']}  면적중앙 {med[i]:,.0f}px")

    (out / "refs.json").write_text(json.dumps({
        "target": meta.get("target", "full"),
        "note": "면적 기준으로 선별한 SAM3 exemplar 세트. 박스는 정규화 [x,y,w,h]. "
                "선별 기준은 '참조 단독 마스크 면적 중앙값 상위' — GT 불필요(RESULTS.md §19).",
        "selection": {"method": "median_mask_area", "k": args.k, "guard_ratio": args.guard,
                      "candidates": n, "probe": str(Path(args.probe)),
                      "probe_frames": len(frames), "consensus_area_px": con_med},
        "n": len(picked), "refs": picked}, indent=2, ensure_ascii=False))
    print(f"\n참조 {len(picked)}장 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
