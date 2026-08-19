"""근접 시점 계열 G0~G10 의 **초기 pose 를 디스크에 낸다** (`RESULTS.md §11·§15·§16`).

    envs/pose/bin/python -m spatial_vision.eval.fuse_pose \
        --near runs/s15_near --far runs/s15_far \
        --near-pred runs/s15_near_flonly --far-pred runs/s15_far_pose \
        --mode g9g10 --n-views 5 --out runs/s15_init_g9g10

왜 필요한가
    §11·§15·§16 의 G 계열은 전부 **기존 산출물의 조합**이라 세션 스크래치패드에서 계산하고 표만
    남겼다. 그런데 `refine_contour` 는 **초기 pose 디렉토리를 입력으로 받는** 스테이지다 —
    G9/G10 초기값 위에서 정합을 재려면 그 pose 가 **파일로** 있어야 한다. 이 모듈이 그 다리다.
    (겸사겸사 G 계열 계산이 재현 가능한 코드로 남는다.)

계산 — 전부 **물체 프레임 오차**로 통일한다
    `E = inv(pose_gt) @ pose_est` 로 옮기면 시점이 달라도 같은 좌표계에서 더할 수 있다.
    융합 후 `pose_init[i] = pose_gt_near[i] @ E_fused` 로 되돌린다.

    | mode | 규칙 |
    |---|---|
    | `g0` | 원거리 추정을 근접 카메라로 이송: `near_gt @ inv(far_gt) @ far_pred` |
    | `g1` | 근접 부품 추정 그대로 (= `--near-pred` 복사) |
    | `g9` | `∠(R_G0,R_G1) ≤ τ` 면 `[R=G0, t=G1]`, 아니면 G0 전체 |
    | `farfuse` | 원거리 추정 n 시점 융합 (회전 chordal 평균, 위치 중앙값, 인라이어 군집만) |
    | `g9g10` | 회전 = `farfuse`, 인라이어 **과반**일 때만 평행이동 = 근접 중앙값 |
    | `jitter` | GT + 통제된 교란 (초기값 오차 사다리를 만들 때 쓴다) |

⚠️ **GT 를 쓰는 프록시다.** 시점 이송·융합은 hand-eye 변환이 필요한데 실험에서는 GT 로 대신한다
   (§16-5). 실환경 hand-eye 오차는 **모든 시점에 계통적으로** 들어가 평균으로 사라지지 않는다 —
   여기서 나온 수치는 **hand-eye 가 완벽할 때의 상한**이다. `jitter` 모드만 GT 외에 아무것도 안 쓴다.
⚠️ **시점 조합은 결정적으로 고른다** — 프레임 i 에 대해 `i, i+1, … i+n-1 (mod N)`. §16 은 무작위
   400회의 **평균**을 봤지만, 여기서는 프레임마다 초기 pose 가 **하나** 나와야 하류 스테이지가 돈다.

출력  <out>/frame_XXXX/pose_init.json  + meta_fuse.json
      → `refine_contour --pose-dir <out> --pose-name pose_init.json`
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from spatial_vision.contracts import rotation_angle_deg


def load_pose(p: Path) -> np.ndarray | None:
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    T = np.eye(4)
    T[:3, :3] = np.asarray(d["R"], float).reshape(3, 3)
    T[:3, 3] = np.asarray(d["t_mm"], float)
    return T


def pose_json(T: np.ndarray, stage: str, extra: dict | None = None) -> dict:
    return {"frame": "cam_T_obj", "convention": "BOP (R 3x3 row-major, t mm)",
            "R": np.asarray(T[:3, :3], float).round(9).tolist(),
            "t_mm": np.asarray(T[:3, 3], float).round(6).tolist(),
            "stage": stage, **(extra or {})}


# 🔴 `arccos((tr−1)/2)` 는 항등 근처에서 오차를 **제곱근으로 증폭**한다 — 저장된 R 이
#    정확히 직교가 아니라(9자리 반올림) **자기 자신과 비교해도 0.03° 가 나왔다**
#    (실측 p90 0.028° · 최대 0.049°, 2026-08-19). 정본은 `contracts.rotation_angle_deg`.
def ang_deg(R1: np.ndarray, R2: np.ndarray) -> float:
    return rotation_angle_deg(R1, R2)


def chordal_mean(Rs: list[np.ndarray]) -> np.ndarray:
    """회전 평균 — 산술평균의 SVD 사영. 오차가 **단봉일 때만** 뜻이 있다(§15-1)."""
    U, _, Vt = np.linalg.svd(np.mean(Rs, axis=0))
    R = U @ Vt
    if np.linalg.det(R) < 0:                     # 반사 방지
        U[:, -1] *= -1
        R = U @ Vt
    return R


def inlier_cluster(Rs: list[np.ndarray], deg: float) -> list[int]:
    """서로 `deg` 이내인 **최대 군집**의 인덱스. 뒤집힌 추정을 융합에서 뺀다(§15-2)."""
    n = len(Rs)
    D = np.array([[ang_deg(Rs[i], Rs[j]) for j in range(n)] for i in range(n)])
    best: list[int] = []
    for i in range(n):
        c = [j for j in range(n) if D[i, j] <= deg]
        if len(c) > len(best):
            best = c
    return best


def fuse(Es: list[np.ndarray], inlier_deg: float) -> tuple[np.ndarray, list[int]]:
    """물체 프레임 오차 n 개를 융합 — 회전 chordal 평균, 평행이동 중앙값 (인라이어만)."""
    keep = inlier_cluster([E[:3, :3] for E in Es], inlier_deg)
    E = np.eye(4)
    E[:3, :3] = chordal_mean([Es[j][:3, :3] for j in keep])
    E[:3, 3] = np.median([Es[j][:3, 3] for j in keep], axis=0)
    return E, keep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="G0~G10 초기 pose 생성")
    ap.add_argument("--near", required=True, help="근접 캡처 (pose_gt.json)")
    ap.add_argument("--far", default=None, help="원거리 캡처 (pose_gt.json). g0/g9/farfuse/g9g10 에 필요")
    ap.add_argument("--near-pred", default=None, help="근접 추정 디렉토리")
    ap.add_argument("--far-pred", default=None, help="원거리 추정 디렉토리")
    ap.add_argument("--pred-name", default="pose_refined.json")
    ap.add_argument("--pred-name-t", default=None,
                    help="**평행이동만 다른 산출물에서** 가져온다 (기본 = --pred-name 과 동일). "
                         "FP 의 stage-2 `refine` 은 회전을 악화시키고 평행이동을 개선하는 맞바꿈이라 "
                         "(`RESULTS.md §27-7`) `--pred-name pose_coarse.json --pred-name-t pose_refined.json` "
                         "이 **하이브리드 초기값**을 만든다 — 현행 최선의 입력이다")
    ap.add_argument("--mode", required=True,
                    choices=["g0", "g1", "g9", "farfuse", "g9g10", "jitter"])
    ap.add_argument("--n-views", type=int, default=5, help="융합할 시점 수 (farfuse/g9g10)")
    ap.add_argument("--tau-deg", type=float, default=3.0, help="G9 게이트 / 정족수 판정 임계")
    ap.add_argument("--inlier-deg", type=float, default=5.0, help="융합 인라이어 군집 반경")
    ap.add_argument("--jitter-deg", type=float, default=0.0, help="jitter: 회전 교란 크기 (deg)")
    ap.add_argument("--jitter-mm", type=float, default=0.0, help="jitter: 평행이동 교란 크기 (mm)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    near = Path(args.near)
    frames = sorted([p.name for p in near.glob("frame_*") if p.is_dir()])
    if not frames:
        print("❌ 근접 캡처에 frame_* 가 없다")
        return 2

    gt_n = {f: load_pose(near / f / "pose_gt.json") for f in frames}
    gt_f, E0, E1, E0t = {}, {}, {}, {}
    if args.mode != "jitter":
        if args.mode != "g1":
            if not (args.far and args.far_pred):
                print("❌ 이 모드는 --far·--far-pred 가 필요하다")
                return 2
            far = Path(args.far)
            for f in frames:
                gt_f[f] = load_pose(far / f / "pose_gt.json")
                pf = load_pose(Path(args.far_pred) / f / args.pred_name)
                if gt_f[f] is not None and pf is not None:
                    E0[f] = np.linalg.inv(gt_f[f]) @ pf
                if args.pred_name_t:
                    pt = load_pose(Path(args.far_pred) / f / args.pred_name_t)
                    if gt_f[f] is not None and pt is not None:
                        E0t[f] = np.linalg.inv(gt_f[f]) @ pt
        if args.near_pred:
            for f in frames:
                pn = load_pose(Path(args.near_pred) / f / args.pred_name)
                if pn is not None:
                    E1[f] = np.linalg.inv(gt_n[f]) @ pn

    rng = np.random.default_rng(args.seed)
    out = Path(args.out)
    rows = []
    for i, f in enumerate(frames):
        note: dict = {}
        if args.mode == "jitter":
            # ⚠️ 초기값 오차 **사다리** 전용. 축은 매번 새로 뽑고 크기는 고정한다 —
            #    크기까지 랜덤이면 "얼마나 나쁜 초기값인가" 라는 변수가 흐려진다.
            ax = rng.normal(size=3)
            ax /= np.linalg.norm(ax)
            from scipy.spatial.transform import Rotation
            E = np.eye(4)
            E[:3, :3] = Rotation.from_rotvec(np.radians(args.jitter_deg) * ax).as_matrix()
            d = rng.normal(size=3)
            E[:3, 3] = args.jitter_mm * d / np.linalg.norm(d)
            T = gt_n[f] @ E
        elif args.mode == "g1":
            if f not in E1:
                continue
            T = gt_n[f] @ E1[f]
        elif args.mode == "g0":
            if f not in E0:
                continue
            T = gt_n[f] @ E0[f]
        elif args.mode == "g9":
            if f not in E0 or f not in E1:
                continue
            gate = ang_deg(E0[f][:3, :3], E1[f][:3, :3])
            E = E0[f].copy()
            if gate <= args.tau_deg:
                E[:3, 3] = E1[f][:3, 3]
            note = {"gate_deg": round(gate, 4), "gate_pass": bool(gate <= args.tau_deg)}
            T = gt_n[f] @ E
        else:                                     # farfuse / g9g10
            views = [frames[(i + k) % len(frames)] for k in range(args.n_views)]
            Es = [E0[v] for v in views if v in E0]
            if len(Es) < 2:
                continue
            Ef, keep = fuse(Es, args.inlier_deg)
            note = {"views": views, "fuse_inliers": len(keep)}
            if E0t:
                # 하이브리드 — 회전은 `--pred-name`, 평행이동은 `--pred-name-t` 융합에서
                Est = [E0t[v] for v in views if v in E0t]
                if len(Est) >= 2:
                    Ef[:3, 3] = fuse(Est, args.inlier_deg)[0][:3, 3]
                    note["t_from"] = f"fuse({args.pred_name_t})"
            if args.mode == "g9g10":
                # 회전은 원거리 융합. 근접 t 는 **과반이 게이트를 통과할 때만** 받는다 (§16-1).
                ok = [v for v in views if v in E1
                      and ang_deg(E1[v][:3, :3], Ef[:3, :3]) <= args.tau_deg]
                note["quorum"] = f"{len(ok)}/{len(views)}"
                if len(ok) * 2 > len(views):
                    Ef[:3, 3] = np.median([E1[v][:3, 3] for v in ok], axis=0)
                    note["t_from"] = "near"
                else:
                    note["t_from"] = "far(정족수 미달)"
            T = gt_n[f] @ Ef

        od = out / f
        od.mkdir(parents=True, exist_ok=True)
        (od / "pose_init.json").write_text(json.dumps(
            pose_json(T, f"fuse:{args.mode}", note), indent=2, ensure_ascii=False))
        rows.append({"frame": f, **note})

    if not rows:
        print("❌ 만들어진 초기 pose 가 없다 — 입력 디렉토리를 확인할 것")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    (out / "meta_fuse.json").write_text(json.dumps({
        "stage": "fuse_pose", "mode": args.mode, "n_views": args.n_views,
        "tau_deg": args.tau_deg, "inlier_deg": args.inlier_deg,
        "near": args.near, "far": args.far,
        "near_pred": args.near_pred, "far_pred": args.far_pred, "pred_name": args.pred_name,
        "pred_name_t": args.pred_name_t,
        "jitter_deg": args.jitter_deg, "jitter_mm": args.jitter_mm, "seed": args.seed,
        "warning": "GT 를 쓰는 프록시 (hand-eye 대역). jitter 모드 외에는 실환경 값이 아니다.",
        "frames": rows,
    }, indent=2, ensure_ascii=False))
    n_pass = sum(1 for r in rows if r.get("gate_pass"))
    n_near = sum(1 for r in rows if r.get("t_from") == "near")
    print(f"{args.mode}: {len(rows)} 프레임 → {out}"
          + (f" | 게이트 통과 {n_pass}" if args.mode == "g9" else "")
          + (f" | 근접 t 채택 {n_near}" if args.mode == "g9g10" else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
