"""오선택 위험 점검 — **GT 없이** «엉뚱한 걸 집었나» 를 잰다 (§42-8).

왜 필요한가
    오선택은 **pose 팔의 문제가 아니라 그 앞 «분할 한 단계»** 문제다 — COMBO 팔
    (RH1·RH2·RP1·RP2·RP3)이 **전부 같은 `seg_txt` 마스크를 공유**하므로 팔을 바꿔도 안 고쳐진다.
    그런데 러너 리포트는 «이탈» 을 프롬프트 스윕 표에만 내므로, **이미 돌린 런에서 바로**
    확인할 수단이 필요하다.

읽는 법
    · **이탈 최대 > 0.25** → 🔴 화면 가장자리의 다른 물체를 집은 프레임이 있다(§34-10 가드 값)
    · **쪼그라든 장**(면적 < 중앙의 0.5배) → 🔴 부분 실패. 중앙값이 이걸 가린다(교훈 #6·#13)
    · **후보 수**가 1 이면 고를 것이 없으니 이 축은 애초에 안 열린다

    🔴 걸리면 처방은 pose 가 아니다 — **`--text-score-frac 0`**(§42-7) · **사전 위치 가드**(§34-10) ·
       프롬프트다.

사용
    envs/pose/bin/python tools/check_misselect.py runs/R28_combo runs/R40_combo runs/R50_combo
"""
import json, sys, glob, numpy as np, cv2
for run in sys.argv[1:]:
    for seg in sorted(glob.glob(f"{run}/seg_txt*")):
        n_i, offs, small = [], [], 0
        areas = []
        for p in sorted(glob.glob(f"{seg}/frame_*/det_full.json")):
            d = json.load(open(p))
            if not d.get("found"): continue
            n_i.append(d.get("n_instances") or 0); areas.append(d.get("area_px", 0))
            m = cv2.imread(p.replace("det_full.json", "mask_full.png"), 0) > 127
            if m.any():
                ys, xs = np.nonzero(m); H, W = m.shape
                offs.append(float(np.hypot(xs.mean()/W-.5, ys.mean()/H-.5)))
        if not n_i: continue
        a = np.array(areas); o = np.array(offs)
        small = int((a < 0.5*np.median(a)).sum())
        print(f"{seg.split('/')[-2]}/{seg.split('/')[-1]:<14} n={len(n_i):>3} "
              f"후보수 중앙 {np.median(n_i):>4.1f} 최대 {max(n_i):>3}  "
              f"이탈 중앙 {np.median(o):.3f} 최대 {o.max():.3f}{'  🔴이탈>0.25' if o.max()>0.25 else '  ✅'}"
              f"  쪼그라든장 {small}{'  🔴' if small else ''}")
