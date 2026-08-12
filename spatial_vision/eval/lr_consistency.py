"""좌우 투영 일관성 — **GT 없이** pose 의 절대 품질을 재는 지표.

    envs/pose/bin/python -m spatial_vision.eval.lr_consistency \
        --in runs/real01 --pose-dir runs/real01_A1 --pose-name pose_refined.json \
        --obj assets/obj/foup_300_semi_r2 --outer-only --out runs/real01_A1

왜 필요한가
    실환경에는 GT 가 없다(사용자 확정). `RESULTS.md` 의 R·t·IoU 는 전부 sim GT 대비라
    **실물에서는 잴 수 없다.** 그래서 후보 서열화는 GT-free 지표로만 해야 하는데
    (`PIPELINE_CATALOG §7.5`), 그중 **게이트 후퇴율**은 «폭주했는가» 만 말하고
    «맞는가» 는 말하지 않는다. 계통 편향은 후퇴율에 안 걸린다(횡단 정리 #64).

    좌우 투영 일관성은 그 빈틈을 메운다. **정합은 왼쪽 이미지만 보고 하므로**,
    같은 pose 를 오른쪽 이미지에 투영했을 때 실루엣이 맞는지는 **독립 관측**이다.
    왼쪽에 과적합된 pose(특히 Z 가 틀린 pose)는 오른쪽에서 어긋난다.

무엇을 재는가
    `refine_contour.residuals_at` 로 좌·우 각각에서 **부호 있는 실루엣 잔차**(px)를 얻고,
    그 잔차를 가장 잘 설명하는 **2D 평행이동 (dx, dy)** 을 Huber 로 푼다.
    법선 방향 성분만 관측되므로 `d ≈ dx·n_x + dy·n_y` 를 풀면 된다.

        dx_L, dy_L  왼쪽에서 남은 어긋남 — 정합이 수렴했으면 ≈0 이어야 한다
        dx_R, dy_R  오른쪽에서 남은 어긋남 — **이게 진짜 지표다**
        Δdx = dx_R − dx_L                    좌우가 갈라진 정도 = 시차 방향 오차
        dz_mm = Z² · Δdx / (fx · B)          그 시차 오차를 깊이로 환산한 값

    rectified stereo 라 오른쪽 카메라는 왼쪽에서 +X 로 `baseline_mm` 만큼 떨어져 있다
    → 물체의 오른쪽 카메라 좌표는 `P − [B,0,0]` 이므로 `T_R = T` 의 `t_x` 에서 B 를 뺀다.

부호 검증 (`--z-shift-mm`) — **검증 완료**
    ⚠️ 자기순환 검증 금지(횡단 정리 #8). 이 도구가 실제로 Z 오차에 반응하는지는
    **일부러 Z 를 밀어서** 확인한다 — sim 런에 `--pose-name pose_gt.json --z-shift-mm 5`.
    `dz_mm > 0` = *"모델이 실물보다 멀리 있다고 추정하고 있다"*. 부호는 실측으로 맞췄다.

🔴 **절대값을 믿지 말고 변형 간 차이만 본다** (`RESULTS.md §35`)
    ① 주입 0 에서도 `dz` 가 0 이 아니다 — 융기 라운드는 계단이 아니라 밝기 기울기를 만들어
       관측 edge 가 참 실루엣에서 밀려 있다(`residuals_at` 문서 참조). 이 **기준선 편향은
       모든 변형에 똑같이 실린다** → 빼고 비교하면 상쇄된다.
    ② 프레임 하나의 분해능은 대략 ±1~2mm 다. **≥20 프레임의 중앙값**으로만 서열화한다.
    ③ 그래서 이 지표의 용도는 *"A1 과 A3 중 어느 쪽이 오른쪽 이미지와 더 맞는가"* 이지
       *"오차가 몇 mm 인가"* 가 아니다. 후자는 실환경에서 여전히 잴 수 없다.

한계
    - `--outer-only` 만 지원한다. `--keep-hole-mm`·`--hole-center-mm` 는 정합기 내부
      전용이라 여기엔 없다 — **어느 정합 변형이든 «같은 잣대(외곽 실루엣)»로 채점**한다.
      변형끼리 비교하는 게 목적이므로 이게 오히려 맞다.
    - 오른쪽 이미지가 왼쪽과 **같은 노출·같은 정류**여야 한다(ZED X 는 그렇다).
    - 물체가 오른쪽 화면에서 잘리면 대응점이 줄어든다 → `n_R` 을 항상 같이 본다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import trimesh

from spatial_vision.stages.refine_contour import load_pose_mm, residuals_at


def solve_shift(d: np.ndarray, n2: np.ndarray, huber_px: float = 2.0,
                iters: int = 6) -> tuple[float, float, float]:
    """법선 방향 잔차 `d` 를 가장 잘 설명하는 2D 평행이동 (dx, dy) 과 잔여 rms.

    `d ≈ dx·n_x + dy·n_y` 의 Huber IRLS. 실루엣 법선이 한 방향으로 쏠려 있으면
    (예: 물체가 잘려 한쪽 변만 보이면) 해가 축퇴하므로 **조건수도 함께 확인**한다.
    """
    x = np.zeros(2)
    for _ in range(iters):
        r = d - n2 @ x
        s = float(np.median(np.abs(r))) * 1.4826 + 1e-6
        w = np.clip(huber_px * s / np.maximum(np.abs(r), 1e-9), 0.0, 1.0)
        x = np.linalg.lstsq(n2 * w[:, None], d * w, rcond=None)[0]
    rms = float(np.sqrt(np.mean((d - n2 @ x) ** 2)))
    return float(x[0]), float(x[1]), rms


def cond_of(n2: np.ndarray) -> float:
    """법선 분포의 조건수 — 크면 (dx, dy) 분리가 안 된다는 뜻이다."""
    s = np.linalg.svd(n2, compute_uv=False)
    return float(s[0] / max(s[-1], 1e-9))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="좌우 투영 일관성 (GT-free pose 품질)")
    ap.add_argument("--in", dest="in_dir", required=True, help="캡처 디렉토리 (left/right/cam)")
    ap.add_argument("--pose-dir", required=True)
    ap.add_argument("--pose-name", default="pose_refined.json")
    ap.add_argument("--obj", required=True)
    ap.add_argument("--mesh", default="top_flange.ply")
    ap.add_argument("--outer-only", action="store_true",
                    help="최외곽 실루엣만 (중심 홀·내부 능선 제외). 정합 변형 비교 시 켠다")
    ap.add_argument("--search-px", type=int, default=8)
    ap.add_argument("--per-edge", type=int, default=3)
    ap.add_argument("--min-grad", type=float, default=1.5)
    ap.add_argument("--huber-px", type=float, default=2.0)
    ap.add_argument("--blur", type=float, default=1.0)
    ap.add_argument("--polarity", default="auto", choices=["auto", "bright_out", "dark_out", "any"])
    ap.add_argument("--z-shift-mm", type=float, default=0.0,
                    help="진단용 — 초기 pose 의 Z 를 일부러 민다. 부호·감도 검증에 쓴다")
    ap.add_argument("--out", dest="out_dir", default=None,
                    help="lr_consistency.json 을 쓸 곳 (기본: --pose-dir)")
    ap.add_argument("--tag", default=None, help="리포트에 쓸 이름 (기본: pose-dir 이름)")
    args = ap.parse_args(argv)

    in_dir, pdir = Path(args.in_dir), Path(args.pose_dir)
    out_dir = Path(args.out_dir) if args.out_dir else pdir
    mesh = trimesh.load(Path(args.obj) / args.mesh, process=False)
    adj = np.asarray(mesh.face_adjacency)
    adj_edges = np.asarray(mesh.face_adjacency_edges)

    frames = sorted([p for p in in_dir.glob("frame_*") if p.is_dir()]) or [in_dir]
    rows = []
    for f in frames:
        cam = json.loads((f / "cam.json").read_text())
        K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], float)
        B = float(cam["baseline_mm"])
        T = load_pose_mm(pdir / f.name / args.pose_name)
        if T is None:
            T = load_pose_mm(pdir / args.pose_name)          # 단일 프레임 배치
        if T is None:
            print(f"  {f.name}: pose 없음 — 건너뜀", file=sys.stderr)
            continue
        if args.z_shift_mm:
            T = T.copy()
            T[2, 3] += args.z_shift_mm

        gl = cv2.imread(str(f / "left.png"), cv2.IMREAD_GRAYSCALE)
        gr = cv2.imread(str(f / "right.png"), cv2.IMREAD_GRAYSCALE)
        if gl is None or gr is None:
            print(f"  {f.name}: left/right 를 못 읽었다 — 건너뜀", file=sys.stderr)
            continue
        gl, gr = gl.astype(np.float32), gr.astype(np.float32)
        if args.blur > 0:
            gl = cv2.GaussianBlur(gl, (0, 0), args.blur)
            gr = cv2.GaussianBlur(gr, (0, 0), args.blur)

        T_R = T.copy()
        T_R[0, 3] -= B                                        # 오른쪽 카메라 좌표계로

        row = {"frame": f.name, "z_mm": round(float(T[2, 3]), 3)}
        ok = True
        for side, gray, Tx in (("L", gl, T), ("R", gr, T_R)):
            d, p, n2, pol = residuals_at(gray, mesh, adj, adj_edges, Tx, K, args.search_px,
                                         args.min_grad, args.per_edge, args.polarity,
                                         None, args.outer_only)
            row[f"n_{side}"] = int(len(d))
            if len(d) < 20:
                ok = False
                continue
            dx, dy, rms = solve_shift(d, n2, args.huber_px)
            row[f"dx_{side}"] = round(dx, 4)
            row[f"dy_{side}"] = round(dy, 4)
            row[f"rms_{side}"] = round(rms, 4)
            row[f"cond_{side}"] = round(cond_of(n2), 2)
            row[f"pol_{side}"] = pol
        if ok:
            ddx = row["dx_R"] - row["dx_L"]
            row["ddx_px"] = round(ddx, 4)
            row["ddy_px"] = round(row["dy_R"] - row["dy_L"], 4)
            # 시차 오차 → 깊이 오차. depth = fx·B/disp 를 disp 로 미분한 것.
            row["dz_mm"] = round(-(row["z_mm"] ** 2) * ddx / (cam["fx"] * B), 4)
        rows.append(row)
        print(f"  {f.name}: n {row.get('n_L', 0):5d}/{row.get('n_R', 0):5d}  "
              f"L({row.get('dx_L', float('nan')):+.2f},{row.get('dy_L', float('nan')):+.2f})px  "
              f"R({row.get('dx_R', float('nan')):+.2f},{row.get('dy_R', float('nan')):+.2f})px  "
              f"Δdx {row.get('ddx_px', float('nan')):+.2f}px → dz {row.get('dz_mm', float('nan')):+.2f}mm")

    def med(key: str) -> float | None:
        v = [r[key] for r in rows if key in r]
        return round(float(np.median(v)), 4) if v else None

    def absmed(key: str) -> float | None:
        v = [abs(r[key]) for r in rows if key in r]
        return round(float(np.median(v)), 4) if v else None

    summary = {
        "stage": "lr_consistency",
        "pose": str(pdir / args.pose_name), "mesh": args.mesh,
        "outer_only": args.outer_only, "z_shift_mm": args.z_shift_mm,
        "n_frames": len(rows),
        "median": {k: med(k) for k in ("dx_L", "dy_L", "dx_R", "dy_R", "ddx_px", "ddy_px", "dz_mm")},
        # ★ 서열화에 쓸 값 — 부호가 섞여 상쇄되면 안 되므로 **절댓값의 중앙값**이다
        "abs_median": {k: absmed(k) for k in ("dx_R", "dy_R", "ddx_px", "dz_mm")},
        "n_corr_median": {"L": med("n_L"), "R": med("n_R")},
        "frames": rows,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"lr_consistency{'_' + args.tag if args.tag else ''}.json"
    (out_dir / name).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    a = summary["abs_median"]
    print(f"  → {out_dir / name}  |R 어긋남| {a['dx_R']}px  |Δdx| {a['ddx_px']}px  |dz| {a['dz_mm']}mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
