"""러너 출력에서 **어느 팔이 무엇을 집었는지** 한 표로 본다.

🔴 러너는 분할 3종 × pose 3종이 동시에 돈다 — «오선택했다» 를 하나로 뭉뚱그리면
   고칠 곳을 못 찾는다. 마스크의 **면적·중심·화면 대비 위치**와 pose 의 **t** 를 나란히 놓아
   *"중앙의 FOUP 인가, 화면 가장자리의 다른 물체인가"* 를 즉시 가른다.

사용: envs/pose/bin/python tools/which_arm.py --run runs/RB50 [--frame frame_0000]
"""
import argparse, json
from pathlib import Path

import cv2
import numpy as np

SEGS = [("seg", "mask_flange.png", "A  SAM3 exemplar flange"),
        ("seg_full", "mask_full.png", "   SAM3 full (진단용)"),
        ("seg_ism", "mask_full.png", "I  ISM full (CAD 템플릿)"),
        ("seg_txt", "mask_full.png", "T  SAM3 텍스트 full")]
POSES = [("fp_ns2", "A3"), ("fp_ism", "I3"), ("fp_txt", "T3"),
         ("A1", "A1"), ("I1", "I1"), ("T1", "T1")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--frame", default=None, help="기본: 전 프레임 중앙값")
    a = ap.parse_args()
    root = Path(a.run)
    names = ([a.frame] if a.frame else
             sorted(p.name for p in (root / "st").glob("frame_*")))
    if not names:
        print(f"❌ {root}/st/frame_* 가 없다"); return 2

    print(f"\n== 분할 — 무엇을 집었나 ==  ({len(names)}프레임 중앙값)")
    print(f"{'팔':26s} {'검출':>6s} {'면적%':>7s} {'중심 x,y (화면 대비)':>22s} {'가장자리?':>9s}")
    for sub, mname, lab in SEGS:
        rows = []
        for n in names:
            m = cv2.imread(str(root / sub / n / mname), 0)
            if m is None or (m > 127).sum() < 50:
                continue
            b = m > 127
            H, W = b.shape
            ys, xs = np.nonzero(b)
            rows.append((100 * b.sum() / (H * W), xs.mean() / W, ys.mean() / H))
        if not rows:
            print(f"{lab:26s} {'0/' + str(len(names)):>6s}   — 검출 없음 —")
            continue
        r = np.array(rows)
        ar, cx, cy = np.median(r, 0)
        # 🔴 «가장자리» 판정 — 중심이 화면 중앙에서 멀면 다른 물체일 가능성이 크다.
        #    씬 규약상 카메라가 타깃을 겨눈다(교훈 #15 의 전제) → 0.5 근처여야 한다.
        d = float(np.hypot(cx - 0.5, cy - 0.5))
        print(f"{lab:26s} {str(len(rows)) + '/' + str(len(names)):>6s} {ar:7.2f} "
              f"{cx:10.2f},{cy:5.2f}{'':6s} {'🔴 ' + f'{d:.2f}' if d > 0.25 else '✅ ' + f'{d:.2f}':>9s}")

    print(f"\n== pose — 어디에 있다고 하나 ==  (t 중앙값, mm)")
    print(f"{'팔':8s} {'n':>5s} {'tx':>9s} {'ty':>9s} {'tz':>9s} {'횡거리':>9s}")
    for sub, lab in POSES:
        ts = []
        for n in names:
            for pn in ("pose_refined.json", "pose_coarse.json"):
                p = root / sub / n / pn
                if p.exists():
                    ts.append(json.loads(p.read_text())["t_mm"]); break
        if not ts:
            print(f"{lab:8s} {'0':>5s}   — pose 없음 —"); continue
        t = np.median(np.array(ts), 0)
        print(f"{lab:8s} {len(ts):5d} {t[0]:9.1f} {t[1]:9.1f} {t[2]:9.1f} "
              f"{np.hypot(t[0], t[1]):9.1f}")
    print("\n🔴 «횡거리» 가 100mm 를 넘으면 §34-10 의 사전위치 가드에 걸릴 값이다 "
          "(성공군 최대 4.4mm vs 실패군 최소 447mm — 102배 간격).")
    print("🔴 분할의 «가장자리» 가 🔴 인 팔이 범인이다. 그 팔의 마스크를 직접 열어 볼 것:")
    print(f"   {root}/<팔>/frame_0000/mask_*.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
