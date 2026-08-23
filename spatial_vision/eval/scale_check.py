"""**실루엣이 말하는 거리** — stereo baseline 오차를 잡는 네 번째 관측 (GT 불필요).

    envs/pose/bin/python -m spatial_vision.eval.scale_check \
        --in runs/real01 --seg-dir runs/real01_A/seg_ism --mask mask_full.png \
        --pose-dir runs/real01_A/fp_ism --pose-name pose_coarse.json \
        --obj assets/obj/foup_300_semi_r2 --mesh full.ply \
        --out runs/real01_A/scale_check.json

왜 필요한가 — 기존 «거리 삼각 대조» 의 세 다리가 **다 같은 뿌리**다
    `FP 추정 z` 와 `stereo depth` 는 둘 다 `Z = fx·B/disparity` 에서 나온다. 그래서 둘이 아무리
    잘 맞아도 **`fx·B` 가 틀렸으면 사이좋게 틀린다.** 줄자가 세 번째 다리인데, 없을 때가 많고
    기준점(= flange 상면 중심) 을 잘못 재기 쉽다.

    실루엣 크기는 **`B` 를 안 쓴다** — 물체의 화면상 크기는 `d_px = D_mm · fx / Z` 이므로
    `Z` 를 다시 풀면 스테레오와 **독립인 거리 관측**이 된다.

무엇을 재나
        Z_실루엣 = Z_pose × (모델을 pose 에 놓고 투영한 등가지름) / (관측 마스크 등가지름)

    pose 가 맞으면 두 지름이 같아 비 = 1.0 이다. 스테레오가 `s` 배로 틀리면 FP 는 물체를
    `s·Z` 에 놓고, 그 위치에서 투영한 실루엣은 관측보다 `1/s` 배 작아진다 → 비가 `1/s` 로
    나오고 `Z_실루엣` 이 **참값을 되돌린다.**

🔴🔴 **`fx` 오차는 이 검사로 못 잡는다 — 원리적으로 불가능하다.**
    `fx` 가 틀리면 `Z` 와 투영 크기가 **같은 비율로** 틀려 정확히 상쇄된다(순수 스케일).
    오버레이에서 윤곽이 완벽히 붙은 채로 거리만 틀릴 수 있다는 뜻이다.
    → **`fx` 를 검증하는 관측은 줄자(또는 §7.5c 상대 GT)뿐이다.**
    이 도구가 잡는 것은 **`baseline`·시차 스케일** 쪽 오차다.

부호·응답 검증 (⚠️ 자기순환 검증 금지 — 교훈 #8)
    «맞는 데이터에서 1.0 이 나온다» 는 아무것도 증명하지 않는다. **일부러 틀려서** 확인한다:
    sim 50cm(참 z 502.2mm) 런의 pose `t` 에 **×1.2** 를 곱해 넣으면
        pose z 601mm → **실루엣 거리 507mm** (비 0.848, 예상 0.833)
    로 참값을 되돌린다. 20% 주입을 −15.2% 로 보고하므로 **방향·크기 모두 맞고**, 남는 1%는
    실루엣이 순수 스케일이 아니어서 생기는 잔차다 → **정밀 측정기가 아니라 «수 % 급 스케일
    오차를 잡는 경보기»** 로 쓴다.

⚠️ 읽을 때의 함정
    · **잘린 프레임은 무효** — 마스크가 화면 밖으로 나가면 관측 지름이 작아져 비가 부푼다.
      경계 화소 비율로 걸러낸다(`--max-edge-frac`).
    · **마스크가 틀린 프레임도 무효** — 오선택·부품 결손이 그대로 비에 들어온다. 산포를 같이 본다.
    · FP 는 depth 뿐 아니라 **마스크도 함께 맞추므로** 이미 일부 타협했을 수 있다
      → 비의 어긋남은 **하한**으로 읽는다(실제 스케일 오차가 더 클 수 있다).
    · 마스크와 메쉬가 **같은 대상**이어야 한다 — `mask_full` 이면 `full.ply`,
      `mask_flange` 면 `top_flange.ply`. 섞으면 비가 통째로 무의미하다(교훈 #26).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from spatial_vision.viz.overlay_pose import load_pose, silhouette


def equiv_dia(mask: np.ndarray) -> float:
    n = int((mask > 127).sum())
    return float(2.0 * np.sqrt(n / np.pi)) if n else 0.0


def edge_frac(mask: np.ndarray) -> float:
    """마스크 중 **화면 경계에 닿은** 화소 비율 — 잘림 판정."""
    b = mask > 127
    if not b.any():
        return 1.0
    e = b[0, :].sum() + b[-1, :].sum() + b[:, 0].sum() + b[:, -1].sum()
    return float(e) / float(b.sum())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="실루엣 기반 독립 거리 관측 (stereo 비의존)")
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--seg-dir", required=True, help="관측 마스크가 있는 디렉토리")
    ap.add_argument("--mask", default="mask_full.png")
    ap.add_argument("--pose-dir", required=True)
    ap.add_argument("--pose-name", default="pose_coarse.json")
    ap.add_argument("--obj", required=True)
    ap.add_argument("--mesh", default="full.ply",
                    help="🔴 `--mask` 와 **같은 대상**이어야 한다 (mask_full↔full.ply)")
    ap.add_argument("--frames", type=int, default=12, help="균등 간격 표본 수 (0=전부)")
    ap.add_argument("--max-edge-frac", type=float, default=0.02,
                    help="이보다 많이 화면 경계에 닿으면 «잘림» 으로 보고 제외")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    import trimesh
    mesh = trimesh.load(Path(a.obj) / a.mesh, process=False)
    frames = sorted([p for p in Path(a.in_dir).glob("frame_*") if (p / "left.png").exists()])
    if not frames:
        print(f"❌ {a.in_dir}/frame_*/left.png 가 없다")
        return 2
    if a.frames and a.frames < len(frames):
        frames = [frames[i] for i in
                  np.linspace(0, len(frames) - 1, a.frames).round().astype(int)]

    rows, skipped = [], {"pose 없음": 0, "마스크 없음": 0, "잘림": 0}
    for f in frames:
        T = load_pose(Path(a.pose_dir) / f.name / a.pose_name)
        if T is None:
            skipped["pose 없음"] += 1
            continue
        m = cv2.imread(str(Path(a.seg_dir) / f.name / a.mask), cv2.IMREAD_GRAYSCALE)
        if m is None or (m > 127).sum() < 500:
            skipped["마스크 없음"] += 1
            continue
        ef = edge_frac(m)
        if ef > a.max_edge_frac:
            skipped["잘림"] += 1
            continue
        cam = json.loads((f / "cam.json").read_text())
        K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], float)
        d_obs, d_prj = equiv_dia(m), equiv_dia(silhouette(mesh, T, K, m.shape))
        if d_obs <= 0 or d_prj <= 0:
            skipped["마스크 없음"] += 1
            continue
        z = float(T[2, 3])
        rows.append({"frame": f.name, "dia_obs_px": round(d_obs, 1), "dia_proj_px": round(d_prj, 1),
                     "ratio": round(d_prj / d_obs, 4), "edge_frac": round(ef, 4),
                     "z_pose_mm": round(z, 1), "z_silhouette_mm": round(z * d_prj / d_obs, 1)})

    out = {"in": str(Path(a.in_dir).resolve()), "seg_dir": str(a.seg_dir), "mask": a.mask,
           "pose_dir": str(a.pose_dir), "pose_name": a.pose_name, "mesh": a.mesh,
           "n_used": len(rows), "skipped": skipped, "frames": rows}
    if rows:
        r = np.array([x["ratio"] for x in rows])
        zp = np.array([x["z_pose_mm"] for x in rows])
        # 🔴 **요약 거리는 `median(z_pose) × median(비)` 로 낸다** — 프레임별 `z_sil` 의 중앙값을
        #    쓰면 안 된다. 곱의 중앙값 ≠ 중앙값의 곱이라 **보고한 비와 보고한 거리가 서로 안 맞는다.**
        #    실측 사례: 비 1.004 인데 `median(z_sil)` 이 483mm(= pose 499mm 보다 16mm 작음) 로 나왔다
        #    — 한 프레임의 비 0.769 와 프레임 간 z 산포 62mm 가 엇갈린 결과다.
        zmed, rmed = float(np.median(zp)), float(np.median(r))
        n_out = int((np.abs(r - 1.0) > 0.15).sum())      # 마스크가 틀린 프레임의 지문
        out["median"] = {
            "ratio": round(rmed, 4),
            "ratio_iqr": round(float(np.percentile(r, 75) - np.percentile(r, 25)), 4),
            "n_ratio_outlier": n_out,
            "z_pose_mm": round(zmed, 1),
            "z_silhouette_mm": round(zmed * rmed, 1),
            "delta_mm": round(zmed * (rmed - 1.0), 1),
            "delta_pct": round(100.0 * (rmed - 1.0), 2)}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))

    if rows:
        m = out["median"]
        print(f"실루엣 거리 {m['z_silhouette_mm']:.0f}mm  vs  pose z {m['z_pose_mm']:.0f}mm  "
              f"(비 {m['ratio']:.3f}, IQR {m['ratio_iqr']:.3f}, n={len(rows)})")
    else:
        print(f"⚠️ 쓸 프레임이 없다 — 제외 사유 {skipped}")
    print(f"→ {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
