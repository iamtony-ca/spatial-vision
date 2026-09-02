"""pose 결과를 **눈으로 검사**할 컨택트 시트를 만든다.

    # sim (GT 있음)
    envs/pose/bin/python -m spatial_vision.viz.overlay_pose \
        --capture runs/dr2_near --pred runs/rim_g9_w3 --obj assets/obj/foup_300_semi_rim3 \
        --frames 6 --out runs/rim_g9_w3/overlay_sheet.png

    # 실환경 (GT 없음) — 변형을 나란히 놓고 비교한다
    envs/pose/bin/python -m spatial_vision.viz.overlay_pose \
        --capture runs/real01 --obj assets/obj/foup_300_semi_r2 \
        --pred runs/real01_A/fp_ns2:pose_coarse.json --pred runs/real01_A/A1 \
        --pred runs/real01_A/A2a --frames 4 --out runs/real01_A/overlay_sheet.png

왜 필요한가
    `metrics_pose.json` 의 숫자만으로는 **무엇이 잘못됐는지** 안 보인다. 90° 뒤집힘인지, 마스크가
    엉뚱한 곳을 잡았는지, 밴드가 물체를 안 덮는지는 **겹쳐 그려야** 안다. 이 프로젝트에서
    기하 오류를 실제로 잡아낸 건 지표가 아니라 눈이었다(RESULTS.md 횡단 정리 #39·#46).

🔴 **실환경에는 GT 가 없다 — 그래서 이 도구가 «유일한» 육안 판정 수단이다**
    절대 오차(mm·도)는 원리적으로 못 낸다(`PIPELINE_CATALOG §7.5`). 남는 것은
    ① 투영 실루엣이 사진의 물체 테두리에 **붙는가** ② 축 삼각대가 상식적인 방향인가
    ③ 변형끼리 **서로 어긋나는가** 다. 셋 다 이 시트에서만 보인다.

무엇을 그리나 — (프레임 × 예측) 한 타일
    · 배경: `left.png`
    · **빨강** = GT pose 로 투영한 모델 윤곽    (`pose_gt.json` — 없으면 안 그린다)
    · **초록** = 예측 pose 로 투영한 모델 윤곽
    · **파랑 반투명** = 정합에 실제로 쓴 마스크 (mask_band > mask_flange_proj > mask_flange)
    · **축 삼각대** = 물체 원점(flange 주 상면 중심)의 X/Y/Z. 글자로 라벨을 찍는다
    · 좌상단: GT 가 있으면 R/t 오차, 없으면 **초기값 대비 이동량**과 **게이트 후퇴 여부**
    · **좌하단 mm 눈금자** — 크롭 배율이 프레임마다 달라서 밖에서 환산할 수 없다. 이미지 안에
      박아야 *"이 어긋남이 몇 mm 인가"* 를 읽을 수 있다 (`--no-scalebar` 로 끈다)

⚠️ **`stages.refine_contour --debug` 와 색 규약이 다르다** — 거기서는 초록=GT · 노랑=모델 샘플이다.
   그래서 두 도구 모두 **이미지에 범례를 찍는다.** 시트를 인용할 때 색을 말로 옮기지 말 것.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from spatial_vision.contracts import rotation_angle_deg
import trimesh

MASK_CANDIDATES = ("mask_band.png", "mask_flange_proj.png", "mask_flange.png")


def load_pose(p: Path) -> np.ndarray | None:
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    T = np.eye(4)
    T[:3, :3] = np.asarray(d["R"], float).reshape(3, 3)
    T[:3, 3] = np.asarray(d["t_mm"], float)
    return T


def silhouette(mesh: trimesh.Trimesh, T: np.ndarray, K: np.ndarray, hw) -> np.ndarray:
    """투영 삼각형의 **합집합**. ⚠️ fillPoly 한 번으로 그리면 짝홀 규칙으로 상쇄된다(교훈 #41)."""
    V, F = np.asarray(mesh.vertices), np.asarray(mesh.faces)
    Xc = (T[:3, :3] @ V.T + T[:3, 3:4]).T
    uv = (K @ Xc.T).T
    good = uv[:, 2] > 1e-6
    uv = np.divide(uv[:, :2], np.where(uv[:, 2:3] > 1e-6, uv[:, 2:3], 1.0))
    m = np.zeros(hw, np.uint8)
    for t in np.rint(uv[F[good[F].all(axis=1)]]).astype(np.int32):
        cv2.fillConvexPoly(m, t, 255)
    return m


# 🔴 `arccos((tr−1)/2)` 는 항등 근처에서 오차를 **제곱근으로 증폭**한다 — 저장된 R 이
#    정확히 직교가 아니라(9자리 반올림) **자기 자신과 비교해도 0.03° 가 나왔다**
#    (실측 p90 0.028° · 최대 0.049°, 2026-08-19). 정본은 `contracts.rotation_angle_deg`.
def rot_deg(A: np.ndarray, B: np.ndarray) -> float:
    return rotation_angle_deg(A[:3, :3], B[:3, :3])


def draw_axes(img, T, K, mm: float, col=None) -> None:
    """물체 원점의 X/Y/Z. **글자로 라벨을 찍는다** — 색만으로는 다른 도구와 헷갈린다.

    ★ `col` 을 주면 **세 축을 그 색으로** 그린다(`--axes-all`). 팔을 여럿 겹칠 때는
      «어느 축인가»(X/Y/Z 라벨)와 «어느 팔인가»(색)를 **둘 다** 알아야 해서, 축 색을
      팔 색으로 넘기고 축 구분은 라벨에 맡긴다. 🔴 `col=None` 이면 기존 R/G/B 규약 그대로다.
    """
    P = np.array([[0, 0, 0], [mm, 0, 0], [0, mm, 0], [0, 0, mm]], float)
    Xc = (T[:3, :3] @ P.T + T[:3, 3:4]).T
    if (Xc[:, 2] <= 1e-6).any():
        return
    uv = (K @ Xc.T).T
    uv = np.rint(uv[:, :2] / uv[:, 2:3]).astype(int)
    o = tuple(uv[0])
    for i, (lab, c) in enumerate(((("X"), (0, 0, 255)), ("Y", (0, 255, 0)), ("Z", (255, 0, 0))), 1):
        c = col if col is not None else c
        cv2.arrowedLine(img, o, tuple(uv[i]), c, 2, tipLength=0.18)
        cv2.putText(img, lab, tuple(uv[i]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
    cv2.circle(img, o, 4, (255, 255, 255), -1)


def draw_scalebar(img, px_per_mm_disp: float, mm_per_px_src: float,
                  max_span_mm: float | None = None) -> None:
    """★ **mm 눈금자** — *"10mm 쯤 어긋난 것 같다"* 를 눈대중이 아니라 **읽어서** 판정한다.

    실환경에는 GT 가 없어 오차를 숫자로 못 낸다. 남는 건 오버레이인데, 거기서 «윤곽이 얼마나
    떨어져 있나» 를 재려면 화면에 길이 기준이 있어야 한다. 크롭 배율이 프레임마다 달라서
    *"이 시트는 1px 이 몇 mm"* 를 밖에서 계산할 수도 없다 → 이미지 안에 박는다.

    ⚠️ **물체 평면(= pose 의 z)에서만 맞다.** 원근이 있으므로 더 앞/뒤의 화소에는 안 맞는다.
    ⚠️ `px_per_mm_disp` 는 **크롭·리사이즈를 반영한 표시 이미지 기준**이고,
       `mm_per_px_src` 는 **원본 픽셀** 기준이다(= Z/fx, 진짜 측정 분해능).
    """
    if not (np.isfinite(px_per_mm_disp) and px_per_mm_disp > 0):
        return
    H, W = img.shape[:2]
    # 🔴 **«가장 긴 것» 이 아니라 «읽을 수 있는 것» 을 고른다.** 크롭이 없는 시트(seg_compare)에서는
    #    500mm 가 들어가 버리는데 그러면 **눈금 한 칸이 50mm** 라 우리가 실제로 판정하려는
    #    «1~5mm 어긋났나»(KPI t ≤5mm)·«10mm 넘었나»(§35-2m-6)를 못 읽는다.
    #    → 부르는 쪽이 `max_span_mm` 으로 상한을 건다.
    fits = [s for s in (5, 10, 20, 50, 100, 200, 500)
            if s * px_per_mm_disp <= 0.45 * W and (max_span_mm is None or s <= max_span_mm)]
    span = fits[-1] if fits else 5
    L = int(round(span * px_per_mm_disp))
    if L < 12:
        return
    x0, y = 10, H - 26
    # ⚠️ **10 칸**으로 쪼갠다 — 5 칸이면 100mm 자의 한 칸이 20mm 라 우리가 실제로 판정하려는
    #    «10mm 어긋났나» 를 못 읽는다. 5칸마다 눈금을 길게 해서 절반 지점을 표시한다.
    txt = f"{span}mm · 눈금 {span / 10:g}mm   (원본 1px = {mm_per_px_src:.2f}mm)"
    tw = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)[0][0]
    cv2.rectangle(img, (x0 - 6, y - 14), (x0 + max(L, tw) + 8, H - 4), (0, 0, 0), -1)
    cv2.line(img, (x0, y), (x0 + L, y), (255, 255, 255), 2)
    for k in range(11):
        xk, big = x0 + int(round(L * k / 10)), k % 5 == 0
        cv2.line(img, (xk, y - (6 if big else 3)), (xk, y + (6 if big else 3)),
                 (255, 255, 255), 2 if big else 1)
    cv2.putText(img, txt, (x0, H - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1)


def scale_terms(K, T, box, hw, tile: int) -> tuple[float, float]:
    """(표시 px/mm, 원본 mm/px). `T` 가 없으면 (0, 0) — 깊이를 모르면 눈금이 뜻이 없다."""
    if T is None:
        return 0.0, 0.0
    z = float(T[2, 3])
    if z <= 1e-6:
        return 0.0, 0.0
    src_w = (box[2] - box[0]) if box else hw[1]
    return float(K[0, 0]) / z * (tile / max(src_w, 1)), z / float(K[0, 0])


def parse_pred(spec: str, default_name: str) -> tuple[Path, str, str]:
    """`경로[:pose_이름[:라벨]]` → (디렉토리, pose 파일명, 라벨).

    ★ **라벨을 직접 줄 수 있다** — 안 주면 디렉토리 이름에서 만든다. 팔을 여럿 겹칠 때
      `hyb_combo/coarse` 같은 **디렉토리 이름은 «어느 팔인가» 를 말해 주지 않는다**(`RH1` 이어야 한다).
      부르는 쪽이 이름을 아는데 그림이 모르면 시트를 읽을 수 없다(교훈 #88).
    ⚠️ 절대경로의 `C:\\` 를 구분자로 오해하면 안 되므로, 조각이 «파일명처럼» 생겼을 때만 자른다.
    """
    parts = spec.split(":")
    # 앞에서부터: 경로 · (pose 파일) · (라벨). pose 파일은 `.json` 으로 끝나는 조각으로 판별한다.
    d, name, lab = Path(parts[0]), default_name, None
    rest = parts[1:]
    if rest and rest[0].endswith(".json"):
        name, rest = rest[0], rest[1:]
    if rest:
        lab = ":".join(rest)
    if lab is None:
        lab = (d.name if name == default_name
               else f"{d.name}/{name.replace('pose_', '').replace('.json', '')}")
    return d, name, lab


def square_box(mask: np.ndarray, hw, pad_frac: float = 0.35) -> tuple[int, int, int, int] | None:
    """실루엣 주위 **정사각** 크롭 — 직사각으로 자른 뒤 정사각 타일로 리사이즈하면 찌그러진다."""
    if mask is None or not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    cx, cy = (xs.min() + xs.max()) / 2.0, (ys.min() + ys.max()) / 2.0
    r = 0.5 * max(np.ptp(xs), np.ptp(ys)) * (1 + 2 * pad_frac) + 20   # numpy 2: ndarray.ptp 제거됨
    r = min(r, min(hw) / 2.0)
    x0 = int(np.clip(cx - r, 0, hw[1] - 2 * r))
    y0 = int(np.clip(cy - r, 0, hw[0] - 2 * r))
    return x0, y0, int(x0 + 2 * r), int(y0 + 2 * r)


def make_tile(frame: Path, pred_dir: Path, pose_name: str, mesh, K, box, tile: int,
              mask_alpha: float = 0.22, scalebar: bool = True):
    """타일 하나. `box` 가 None 이면 이 타일의 예측으로 잡는다(그 박스를 반환해 행에서 공유).

    ⚠️ 마스크는 **연하게** 깐다 — 실환경 판정은 *"초록 윤곽이 사진의 진짜 테두리에 붙는가"* 인데
       진하게 칠하면 그 테두리가 가려진다. `--mask-alpha 0` 으로 아예 끌 수 있다.
    """
    img = cv2.imread(str(frame / "left.png"))
    hw = img.shape[:2]

    for name, src in ((n, s) for n in MASK_CANDIDATES for s in (pred_dir / frame.name, frame)):
        mp = src / name
        if mask_alpha <= 0:
            break
        if mp.exists():
            mk = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
            if mk is not None and mk.shape == hw:
                img[mk > 127] = ((1 - mask_alpha) * img[mk > 127]
                                 + mask_alpha * np.array([255, 120, 0])).astype(np.uint8)
            break

    T_gt = load_pose(frame / "pose_gt.json")
    T_pr = load_pose(pred_dir / frame.name / pose_name)
    s_pr = silhouette(mesh, T_pr, K, hw) if T_pr is not None else None
    if box is None:
        box = square_box(silhouette(mesh, T_gt, K, hw) if T_gt is not None else s_pr, hw)

    for T, col in ((T_gt, (0, 0, 255)), (T_pr, (0, 255, 0))):
        if T is None:
            continue
        s = s_pr if T is T_pr else silhouette(mesh, T, K, hw)
        cs, _ = cv2.findContours(s, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, cs, -1, col, 2)
    if T_pr is not None:
        draw_axes(img, T_pr, K, 60.0)

    # 좌상단 주석 — GT 가 있으면 오차, 없으면 GT-free 단서(이동량·게이트)
    if T_pr is None:
        note = "pose 없음"
    elif T_gt is not None:
        note = f"R {rot_deg(T_gt, T_pr):5.2f}deg  t {np.linalg.norm(T_gt[:3, 3] - T_pr[:3, 3]):5.2f}mm"
    else:
        note = f"z {T_pr[2, 3]:.0f}mm"
        T0 = load_pose(pred_dir / frame.name / "pose_coarse.json")
        if T0 is not None and pose_name != "pose_coarse.json":
            note += f"  moved {rot_deg(T0, T_pr):.2f}deg {np.linalg.norm(T0[:3, 3] - T_pr[:3, 3]):.2f}mm"
        if (pred_dir / frame.name / "pose_contour_raw.json").exists():
            note += "  [GATED]"          # 정합 결과를 버리고 초기값을 낸 프레임

    if box:
        x0, y0, x1, y1 = box
        img = img[y0:y1, x0:x1]
    if img.size == 0:
        img = np.zeros((tile, tile, 3), np.uint8)
    img = cv2.resize(img, (tile, tile))
    if scalebar:
        draw_scalebar(img, *scale_terms(K, T_pr if T_pr is not None else T_gt, box, hw, tile))
    cv2.rectangle(img, (0, 0), (tile - 1, 22), (0, 0, 0), -1)
    cv2.putText(img, note, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 255, 255), 1)
    return img, box


# ★ 겹쳐 그리기 전용 팔레트 (BGR) — **16색**. 🔴 **빨강은 GT 전용이라 뺀다** · 흰색은 중심 십자다.
#   🔴🔴 **8색이던 것을 16색으로 늘렸다 (2026-08-31)** — 팔이 8개를 넘으면 색이 순환해
#   **다른 팔이 같은 색으로 그려졌다.** «구분이 안 된다» 가 아니라 **오독**이다.
#   ⚠️ 눈대중으로 고르지 않았다: 황금각 색상 sweep 을 **CIE Lab 최소 쌍거리**로 골랐고
#   예약색(GT 빨강·흰색·검정)을 **씨앗으로 넣은 최원점 샘플링**(farthest-point)으로 골랐고
#   **최소 쌍거리 44.3 · 인접 순서쌍 58.1** 이다(JND ≈ 2.3).
#   ⚠️ 초판은 «황금각 색상 sweep» 이었는데 OpenCV 의 H 범위가 0~179 라 137.5 를 그대로
#   쓰면 색이 안 퍼진다 — 최소 19.9 로 **파랑끼리·초록끼리 닮아 실제로 못 갈랐다.**
#   런마다 색이 바뀌면 안 되므로 **순서를 고정**한다.
COMBO_COLORS = [
    (255, 0, 128), (0, 205, 0), (205, 143, 0), (0, 179, 255),
    (175, 55, 255), (185, 205, 0), (55, 255, 215), (205, 82, 0),
    (155, 255, 55), (44, 125, 205), (82, 0, 205), (255, 55, 215),
    (255, 195, 55), (255, 255, 0), (0, 255, 76), (44, 205, 173),
]


def make_combo_tile(frame: Path, preds: list, mesh, K, box, tile: int, axes_for: int = 0,
                    scalebar: bool = True, axes_all: bool = False):
    """★ **예측 여러 개를 «한 장» 에 겹쳐** 그린다 (`--combine`).

    타일을 나눠 그리면 *"coarse 와 refined 가 얼마나 어긋나는가"* 를 눈으로 못 잰다 —
    같은 화소 위에 놓아야 보인다. 분할 백엔드별 FP 결과를 겹치는 것도 같은 이유다.

    ⚠️ 마스크는 안 깐다(윤곽이 여럿이라 가려진다) · 축 삼각대는 기본이 **하나**다(`axes_for`).
    ★ `axes_all=True` 면 **팔마다** 그리고 **축 색을 팔 색으로** 맞춘다(`--axes-all`).
      회전 오차는 윤곽보다 축에서 훨씬 잘 보인다 — 60mm 지렛대가 각도를 화면 거리로 늘린다.
      🔴 대신 원점이 겹쳐 있어 팔이 많으면 화살표가 뭉친다. 4~6팔까지가 읽을 만하다.
    """
    img = cv2.imread(str(frame / "left.png"))
    hw = img.shape[:2]
    T_gt = load_pose(frame / "pose_gt.json")

    drawn = []                                    # (라벨, 색, T) — 범례·주석에 그대로 쓴다
    for i, (d, name, lab) in enumerate(preds):
        T = load_pose(d / frame.name / name)
        if i >= len(COMBO_COLORS):
            lab += " ⚠️색순환"          # 🔴 같은 색이 두 번 나오면 시트를 오독한다
        drawn.append((lab, COMBO_COLORS[i % len(COMBO_COLORS)], T, d, name))
    first = next((T for _, _, T, _, _ in drawn if T is not None), None)

    if box is None:
        ref = T_gt if T_gt is not None else first
        box = square_box(silhouette(mesh, ref, K, hw), hw) if ref is not None else None

    if T_gt is not None:                          # GT 는 늘 빨강 (단독 모드와 같은 규약)
        cs, _ = cv2.findContours(silhouette(mesh, T_gt, K, hw),
                                 cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, cs, -1, (0, 0, 255), 2)
    for i, (lab, col, T, d, name) in enumerate(drawn):
        if T is None:
            continue
        cs, _ = cv2.findContours(silhouette(mesh, T, K, hw),
                                 cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, cs, -1, col, 2)
        if axes_all:
            draw_axes(img, T, K, 60.0, col=col)
        elif i == axes_for:
            draw_axes(img, T, K, 60.0)

    if box:
        x0, y0, x1, y1 = box
        img = img[y0:y1, x0:x1]
    if img.size == 0:
        img = np.zeros((tile, tile, 3), np.uint8)
    img = cv2.resize(img, (tile, tile))
    if scalebar:
        draw_scalebar(img, *scale_terms(K, T_gt if T_gt is not None else first, box, hw, tile))

    # 주석 — **줄마다 그 예측의 색으로** 찍는다. 색 규약을 밖에서 설명할 필요가 없어진다.
    n = sum(1 for *_, T, _, _ in drawn if T is not None) + (1 if T_gt is not None else 0)
    h = 16 * max(n, 1) + 6
    cv2.rectangle(img, (0, 0), (tile - 1, h), (0, 0, 0), -1)
    y = 14
    if T_gt is not None:
        cv2.putText(img, "GT", (5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 255), 1); y += 16
    ref_T = T_gt if T_gt is not None else None
    for lab, col, T, d, name in drawn:
        if T is None:
            cv2.putText(img, f"{lab}: 없음", (5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, col, 1)
            y += 16
            continue
        if ref_T is not None:                     # sim — GT 대비 오차
            s = f"{lab}  R{rot_deg(ref_T, T):5.2f} t{np.linalg.norm(ref_T[:3, 3] - T[:3, 3]):5.1f}"
        else:                                     # 실물 — z 와 «초기값 대비 이동량»
            s = f"{lab}  z{T[2, 3]:.0f}"
            T0 = load_pose(d / frame.name / "pose_coarse.json")
            if T0 is not None and name != "pose_coarse.json":
                s += f" mv{rot_deg(T0, T):.2f}d/{np.linalg.norm(T0[:3, 3] - T[:3, 3]):.1f}mm"
            if (d / frame.name / "pose_contour_raw.json").exists():
                s += " [G]"
        cv2.putText(img, s, (5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, col, 1)
        y += 16
    return img, box


def label_bar(text: str, w: int, h: int = 26, col=(255, 255, 255)) -> np.ndarray:
    """⚠️ 폰트를 폭에 맞춰 줄인다 — 범례가 잘리면 색 규약을 알 수 없고, 그게 이 도구의 존재 이유다."""
    bar = np.full((h, w, 3), 30, np.uint8)
    fs = 0.55
    while fs > 0.24 and cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)[0][0] > w - 14:
        fs -= 0.03
    cv2.putText(bar, text, (8, h - 8), cv2.FONT_HERSHEY_SIMPLEX, fs, col, 1)
    return bar


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="pose overlay 컨택트 시트 (GT 없어도 된다)")
    ap.add_argument("--capture", required=True, help="left.png·cam.json (+sim 이면 pose_gt.json) 디렉토리")
    ap.add_argument("--pred", action="append", required=True,
                    help="pose 산출 디렉토리. **`경로:pose_이름:라벨`** — 뒤 둘은 선택. "
                         "★ 라벨을 주면 주석·범례에 그대로 쓴다. 팔을 여럿 겹칠 때 "
                         "`hyb_combo/coarse` 같은 디렉토리 이름은 «어느 팔인가» 를 말해 주지 않는다. "
                         "여러 번 주면 열로 나란히 놓는다(`--combine` 이면 한 장에 겹친다)")
    ap.add_argument("--obj", required=True, help="투영에 쓸 obj (밴드 런이면 밴드 obj)")
    ap.add_argument("--mesh", default="top_flange.ply")
    ap.add_argument("--pose-name", default="pose_refined.json", help="--pred 에 `:이름` 이 없을 때의 기본값")
    ap.add_argument("--frames", type=int, default=6, help="균등 간격으로 고를 프레임 수")
    ap.add_argument("--pick", default=None,
                    help="프레임을 직접 지정한다(쉼표 구분, 예 frame_0010,frame_0026). --frames 를 무시한다")
    ap.add_argument("--worst", type=int, default=0,
                    help="`--pred/metrics_pose.json` 에서 오차 상위 N 프레임 (sim 전용, --pick 다음 우선)")
    ap.add_argument("--worst-key", default="rot_deg", choices=["rot_deg", "trans_mm"])
    ap.add_argument("--tile", type=int, default=420, help="타일 한 변 픽셀")
    ap.add_argument("--cols", type=int, default=3, help="예측이 하나일 때의 열 수")
    ap.add_argument("--mask-alpha", type=float, default=0.22,
                    help="마스크 반투명도. 0 이면 안 그린다 — 실물 테두리를 가리지 않고 보고 싶을 때")
    ap.add_argument("--max-combine", type=int, default=16,
                    help="`--combine` 에서 그릴 예측 수 상한. 🔴 팔레트가 8색이라 넘으면 색이 "
                         "순환해 구분이 안 되고, 주석 줄이 타일을 통째로 덮는다(30팔에서 실제로 "
                         "그랬다). 넘치면 **앞에서 자르고 범례에 밝힌다**")
    ap.add_argument("--axes-all", action="store_true",
                    help="★ `--combine` 에서 **팔마다** X/Y/Z 축을 그린다(축 색 = 그 팔 색). "
                         "회전 오차는 윤곽보다 축에서 잘 보인다 — 60mm 지렛대가 각도를 화면 "
                         "거리로 늘린다. 🔴 원점이 겹쳐 있어 **4~6팔까지가 읽을 만하다**")
    ap.add_argument("--combine", action="store_true",
                    help="★ 예측 전부를 **한 이미지에 겹쳐** 그린다(예측마다 다른 색 + 색 맞춘 주석). "
                         "coarse↔refined 어긋남, 분할 백엔드별 FP 차이를 눈으로 재려면 이것이다")
    ap.add_argument("--no-scalebar", action="store_true",
                    help="mm 눈금자를 안 그린다. 기본은 그린다 — GT 가 없는 실환경에서 «몇 mm 어긋났나» 를 "
                         "읽을 수 있는 유일한 수단이다(물체 평면 기준)")
    ap.add_argument("--per-frame-dir", default=None,
                    help="프레임마다 한 장씩 따로 쓴다(전체 시트와 별개). 육안 확대 검사용")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    cap = Path(args.capture)
    preds = [parse_pred(s, args.pose_name) for s in args.pred]
    n_dropped = 0
    if args.combine and args.max_combine and len(preds) > args.max_combine:
        # 🔴 조용히 자르지 않는다(교훈 #22) — 몇 개를 왜 뺐는지 로그와 **범례 양쪽**에 남긴다.
        n_dropped = len(preds) - args.max_combine
        print(f"🔴 --combine 은 {args.max_combine}개까지만 그린다 (팔레트 {len(COMBO_COLORS)}색 — "
              f"넘으면 색이 순환해 **다른 팔이 같은 색**이 된다). "
              f"뒤 {n_dropped}개를 뺀다: {[l for _, _, l in preds[args.max_combine:]]}")
        preds = preds[:args.max_combine]
    mesh = trimesh.load(Path(args.obj) / args.mesh, process=False)
    frames = sorted([p for p in cap.glob("frame_*") if p.is_dir()])
    if not frames:
        print("❌ 프레임이 없다")
        return 2
    if args.pick:
        want = [s.strip() for s in args.pick.split(",") if s.strip()]
        by_name = {f.name: f for f in frames}
        missing = [w for w in want if w not in by_name]
        if missing:
            print(f"❌ 없는 프레임: {missing}")
            return 2
        sel = [by_name[w] for w in want]
    elif args.worst:
        # ⚠️ 균등 간격은 **꼬리를 못 잡는다** — 대실패는 몇 프레임에 몰리므로 지표에서 직접 고른다(교훈 #14).
        mp = json.loads((preds[0][0] / "metrics_pose.json").read_text())["results"]
        key = next((k for k in mp if k.endswith("refined")), sorted(mp)[0])
        by_name = {f.name: f for f in frames}
        ranked = sorted(mp[key]["frames"], key=lambda r: -r[args.worst_key])
        sel = [by_name[r["frame"]] for r in ranked[:args.worst] if r["frame"] in by_name]
    else:
        sel = [frames[i] for i in
               np.linspace(0, len(frames) - 1, min(args.frames, len(frames))).round().astype(int)]

    has_gt = (sel[0] / "pose_gt.json").exists()
    rows, per_frame = [], {}
    for f in sel:
        cam = json.loads((f / "cam.json").read_text())
        K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], float)
        box, tiles = None, []
        if args.combine:                       # ★ 전부 한 장에 겹친다
            t, box = make_combo_tile(f, preds, mesh, K, box, args.tile,
                                     scalebar=not args.no_scalebar, axes_all=args.axes_all)
            tiles.append(t)
        else:
            for d, name, _ in preds:           # ★ 행 안에서 크롭 박스를 공유해야 나란히 비교된다
                t, box = make_tile(f, d, name, mesh, K, box, args.tile, args.mask_alpha,
                                   scalebar=not args.no_scalebar)
                tiles.append(t)
        rows.append((f.name, tiles))
        per_frame[f.name] = tiles

    # ⚠️ combine 모드는 타일이 프레임당 **하나**다 — 열 수를 예측 개수로 잡으면 폭이 안 맞는다.
    ntile = 1 if args.combine else len(preds)
    ncol = ntile if ntile > 1 else min(args.cols, len(sel))
    W = ncol * args.tile

    if ntile > 1:           # 행 = 프레임, 열 = 변형
        blocks = [label_bar("  |  ".join(f"{lab:^18}" for _, _, lab in preds), W, 28, (0, 255, 255))]
        for fname, tiles in rows:
            blocks.append(label_bar(fname, W, 22))
            blocks.append(np.concatenate(tiles, 1))
    else:                   # 예측 하나 — 프레임을 격자로
        flat = [t for _, ts in rows for t in ts]
        blocks = []
        for i in range(0, len(flat), ncol):
            chunk = flat[i:i + ncol]
            chunk += [np.zeros_like(chunk[0])] * (ncol - len(chunk))
            blocks.append(np.concatenate(chunk, 1))

    if args.combine:
        # 🔴 색 규약을 **이미지 안에** 박는다 — 이 시트는 색으로만 구분되므로 밖에서 설명하면 안 된다.
        legend = ("red=GT  | " if has_gt else "GT 없음  | ") + "  ".join(
            f"[{i + 1}]{lab}" for i, (_, _, lab) in enumerate(preds)) + \
            f"  (색은 아래 주석 줄과 같다)  / {Path(args.obj).name}" + \
            (f"  ⚠️ 뒤 {n_dropped}개 생략 — 전부 보려면 overlay_sheet.png" if n_dropped else "")
    else:
        legend = ("red=GT  green=pred  " if has_gt else "green=pred (GT 없음)  ") + \
                 ("blue=mask  " if args.mask_alpha > 0 else "") + "axes=obj XYZ 60mm  | " + \
                 " · ".join(f"{lab}" for _, _, lab in preds) + f"  / {Path(args.obj).name}"
    if not args.no_scalebar:
        legend += "  | 좌하단 = mm 눈금자(물체 평면)"
    sheet = np.concatenate([label_bar(legend, W, 30)] + blocks, 0)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet)
    print(f"→ {out}  ({len(sel)} 프레임 × {len(preds)} 예측)")

    if args.per_frame_dir:
        pfd = Path(args.per_frame_dir)
        pfd.mkdir(parents=True, exist_ok=True)
        # ⚠️ **프레임별 이미지의 폭은 `W` 가 아니다** — `W` 는 시트 격자용(`ncol × tile`)이고
        #    여기 한 줄은 **예측 개수 × tile** 이다. 예측이 하나면 둘이 어긋나 concat 이 터진다.
        Wf = ntile * args.tile
        head = label_bar("겹쳐 그림 — 주석 줄 색 = 그 예측의 윤곽 색" if args.combine else
                         "  |  ".join(f"{lab:^18}" for _, _, lab in preds), Wf, 28, (0, 255, 255))
        for fname, tiles in rows:
            cv2.imwrite(str(pfd / f"overlay_{fname}.png"),
                        np.concatenate([label_bar(legend, Wf, 30), head,
                                        np.concatenate(tiles, 1)], 0))
        print(f"→ {pfd}/overlay_frame_*.png  ({len(rows)}장)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
