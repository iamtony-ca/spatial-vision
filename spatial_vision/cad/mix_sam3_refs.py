"""여러 SAM3 참조 세트를 **섞어** 하나로 만든다 — 몸체 외관을 모를 때용.

    envs/seg_sam3/bin/python -m spatial_vision.cad.mix_sam3_refs \
        --obj assets/obj/foup_300_semi_r2 --band n50 --per-set 2

왜 필요한가
    실물 FOUP 몸체는 **검정 불투명 / 반투명 주황 / 투명** 셋이 대부분이고(사용자 확정 2026-08-13)
    참조는 그 외관에서 만들어야 한다. 종류를 **알면** 종류별 세트가 낫지만, 모르는 채로 한 번에
    가야 하는 상황이 있다. 그때 쓰는 세트다.

🔴 **`--refs-mode independent` 전제다.** `chain` 은 `add_prompt(frame_idx=0)` 라 박스가 **`ref_0` 에만**
   걸리고 나머지는 추적으로 이어질 뿐이다 → 섞는 의미가 없고 사실상 «ref_0 의 외관» 세트가 된다.
   `tools/run_group_a.py` 는 mixed 프리셋에서 이 모드로 **자동 전환**한다.

⚠️ 순서는 **어려운 것부터**다. `black`(몸체와 flange 가 같은 색 → 경계 소실)이 최난이도이므로
   먼저 놓는다 — `--n-refs` 로 앞에서 자를 때 가장 어려운 조건이 남는다.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ORDER = ["black", "orange", "clear"]        # 난이도 순 (앞이 어렵다)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SAM3 참조 세트 혼합 (몸체 외관 미상용)")
    ap.add_argument("--obj", required=True, help="assets/obj/<obj_id>")
    ap.add_argument("--band", required=True, help="거리대 태그 (예: n25, n50)")
    ap.add_argument("--apps", nargs="+", default=ORDER, help=f"섞을 외관, 순서대로 (기본 {ORDER})")
    ap.add_argument("--per-set", type=int, default=2, help="세트당 상위 몇 장")
    ap.add_argument("--prefix", default="sam3_refs_flange", help="세트 이름 접두")
    ap.add_argument("--out-name", default=None, help="기본 <prefix>_<band>_mixed")
    a = ap.parse_args(argv)

    obj = Path(a.obj)
    out = obj / (a.out_name or f"{a.prefix}_{a.band}_mixed")
    srcs = [(app, obj / f"{a.prefix}_{a.band}_{app}") for app in a.apps]
    missing = [str(p) for _, p in srcs if not (p / "refs.json").exists()]
    if missing:
        print("❌ 없는 세트: " + ", ".join(missing))
        return 2

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    refs, band_m, k = [], None, 0
    for app, src in srcs:
        j = json.loads((src / "refs.json").read_text())
        band_m = band_m or j.get("distance_band_m")
        for r in j["refs"][:a.per_set]:
            shutil.copy(src / r["image"], out / f"ref_{k}.png")
            refs.append({**r, "image": f"ref_{k}.png", "body_appearance_mode": app,
                         "mixed_from": src.name})
            k += 1

    (out / "refs.json").write_text(json.dumps({
        "target": "flange",
        "n": len(refs),
        "band": a.band,
        "distance_band_m": band_m,
        "body_appearance": "mixed(" + ",".join(a.apps) + ")",
        "per_set": a.per_set,
        "note": "몸체 외관 미상용 혼합 세트. 🔴 --refs-mode independent 로 쓸 것 — chain 은 박스가 "
                "ref_0 에만 걸려 섞는 의미가 없다. 종류를 알면 종류별 세트가 낫다. "
                "순서는 난이도 순(black 먼저)이라 --n-refs 로 잘라도 어려운 조건이 남는다.",
        "regen": "RESULTS.md §35-2f 「재현」",
        "refs": refs,
    }, indent=2, ensure_ascii=False))
    print(f"참조 {len(refs)}장 → {out}  ({' + '.join(f'{app}×{a.per_set}' for app, _ in srcs)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
