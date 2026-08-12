"""M4 자산 — SAM3 exemplar(참조 이미지 + 박스) 세트를 객체 자산으로 굳힌다.

    envs/seg_sam3/bin/python -m spatial_vision.cad.build_sam3_refs \
        --from runs/semi_clean --obj assets/obj/foup_300_semi --n 3

⚠️ `envs/cad` 가 아니라 **`envs/seg_sam3`** 로 돌린다 — cad venv 는 순수 기하용이라 cv2 가 없고,
이건 SAM3 전용 자산이다.

왜 자산인가
    이 파이프라인의 목표는 **CAD 와 Isaac Sim 만으로 실환경 6D pose 를 자동화**하는 것이다.
    그러면 SAM3 의 참조 이미지도 실환경에서 찍는 것이 아니라 **sim 에서 미리 렌더해 두는 자산**이어야
    한다 — ISM 의 CAD 템플릿(`ism_full/`)과 정확히 같은 위치의 물건이다. 그래서 캡처 산출물(runs/)이
    아니라 `assets/obj/<id>/sam3_refs/` 에 둔다.

⚠️ **이 스크립트는 "후보를 만드는" 단계다. 배포 세트는 여기서 고르지 않는다.**
    아래 "2~3장 최적 / 균등 간격" 은 **사슬 방식(`--refs-mode chain`) 시절의 결론이고 폐기됐다**
    (RESULTS.md §17·§19). 균등 간격은 실측상 **random 보다도 나쁘다**(IoU 0.709 vs 0.739).
    → **후보를 넉넉히(`--n 42`) 만든 뒤 `spatial_vision.cad.select_sam3_refs` 로 고른다.**
      선별 기준은 *참조 단독 마스크 면적 중앙값 상위 5장* 이며 **GT 가 필요 없다**.
    이 파일은 후보 생성 동작을 **일부러 바꾸지 않았다** — 후보 세트가 남아 있어야 기준을 바꿔 다시 고른다.

무엇을 고르나 (이력. 실측 근거는 RESULTS.md § M4-exemplar)
    - ~~**2~3장이 최적.**~~ 1장은 실패 프레임이 생기고(10프레임 중 1건 IoU 0.000), 5장은 오히려 나빠진다.
      SAM3 의 비디오 경로는 박스를 **첫 프레임에만** 걸 수 있고(`add_prompt` 가 매번 `reset_state`),
      나머지 참조는 추적으로 통과한다 → 참조가 길어질수록 사슬이 끊어질 확률이 는다.
      **→ `--refs-mode independent` 로 바꾸면 이 제약이 사라진다(§17).**
    - **순서·시점(방위·고도) 유사도는 무관하다**(임의 0.957 vs 유사시점 0.950~0.957). 배치 시점을 몰라도 된다.
      → ~~균등 간격으로 뽑는다~~ **유관한 것은 참조 개별 품질이었다(§19).**
    - ⚠️ **거리(스케일)는 무관하지 않다.** 참조 1.65~2.17m 로 0.30~0.50m 질의를 하면 IoU **0.044** 로
      전멸하고(투영 면적 34배 차이), 같은 질의를 근접 참조로 바꾸면 **0.905** 다.
      → `--from` 은 **배포 작업거리에서 렌더한 런**을 준다. 작업거리 대역이 여러 개면 세트도 여러 개다.
      (RESULTS.md § M5 확장 §5)

출력  assets/obj/<id>/sam3_refs/  ref_0.png …  refs.json{boxes_xywh(정규화), 출처}
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np


def box_from_mask(mask_path: Path) -> list[float] | None:
    """GT 마스크 → 정규화 [x, y, w, h]. SAM3 비디오 경로가 요구하는 형식."""
    m = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if m is None or not (m > 127).any():
        return None
    ys, xs = np.nonzero(m > 127)
    h, w = m.shape
    return [float(xs.min()) / w, float(ys.min()) / h,
            float(xs.max() - xs.min()) / w, float(ys.max() - ys.min()) / h]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SAM3 exemplar 참조 세트 생성")
    ap.add_argument("--from", dest="src", required=True,
                    help="깨끗한(단일 객체) 캡처 런. distractor 가 섞이면 박스가 모호해진다")
    ap.add_argument("--obj", required=True, help="assets/obj/<obj_id>")
    ap.add_argument("--n", type=int, default=3, help="참조 장수 (실측 최적 2~3)")
    ap.add_argument("--target", default="full", choices=["full", "flange"],
                    help="어느 마스크로 박스를 뽑나. flange 면 top flange 만 가리키는 참조가 된다")
    ap.add_argument("--out-name", default=None, help="기본값: sam3_refs / sam3_refs_flange")
    args = ap.parse_args(argv)

    src = Path(args.src)
    mask_name = "mask_full.png" if args.target == "full" else "mask_flange.png"
    out_name = args.out_name or ("sam3_refs" if args.target == "full" else "sam3_refs_flange")
    frames = sorted([p for p in src.glob("frame_*") if (p / mask_name).exists()])
    if len(frames) < args.n:
        print(f"❌ 프레임 부족: {len(frames)} < {args.n}")
        return 2

    # 균등 간격 — **후보 생성용이다.** 배포 세트는 `select_sam3_refs` 가 면적 기준으로 고른다.
    # (균등 간격을 그대로 배포하면 random 보다 나쁘다 — RESULTS.md §19)
    idx = np.linspace(0, len(frames) - 1, args.n).round().astype(int)
    out = Path(args.obj) / out_name
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("ref_*.png"):
        f.unlink()

    refs = []
    for k, i in enumerate(idx):
        f = frames[int(i)]
        box = box_from_mask(f / mask_name)
        if box is None:
            print(f"  건너뜀(마스크 없음): {f.name}")
            continue
        shutil.copy(f / "left.png", out / f"ref_{k}.png")
        meta_p = f / "meta_capture.json"
        vp = {}
        if meta_p.exists():
            mm = json.loads(meta_p.read_text())
            vp = {"distance_m": mm.get("camera_distance_m"),
                  "elevation_deg": mm.get("elevation_deg"),
                  "azimuth_deg": mm.get("azimuth_deg")}
        refs.append({"image": f"ref_{k}.png", "box_xywh_norm": box, "source": str(f), **vp})
        print(f"  ref_{k}.png ← {f.name}  box {[round(v, 3) for v in box]}")

    (out / "refs.json").write_text(json.dumps(
        {"target": args.target,
         "note": "sim 에서 미리 만든 SAM3 exemplar **후보** 세트. 박스는 정규화 [x,y,w,h]. "
                 "배포 세트는 select_sam3_refs 가 면적 기준으로 고른다(RESULTS.md §19).",
         "n": len(refs), "refs": refs}, indent=2, ensure_ascii=False))
    print(f"\n참조 {len(refs)}장 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
