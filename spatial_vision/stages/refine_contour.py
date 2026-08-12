"""M5b — **원본 해상도 테두리 정합**. FoundationPose 밖에서 pose 를 다듬는다.

    envs/cad/bin/python -m spatial_vision.stages.refine_contour \
        --in runs/dr2_near --pose-dir runs/dr2_near_flonly --obj assets/obj/foup_300_semi \
        --out runs/dr2_near_ctr

왜 필요한가 — **160×160 이 정밀도의 천장이다** (`RESULTS.md §22`)
    FoundationPose 의 refiner 는 `diameter × 1.2` 정사각 crop 을 **160×160** 으로 줄여 넣는다.
    → 네트워크 1px = `diameter·1.2/160` mm 이고 **거리·fx 와 무관**하다:
      `full.ply` **4.34mm/px** · `top_flange.ply` **1.38mm/px**. 원본 이미지는 **0.36mm/px** 다.
    즉 관측에 있는 정보의 4~12배를 정합기가 버린다. 이 스테이지는 그 버려진 해상도를 쓴다.

방법 — occluding contour(실루엣 모서리) 정합, RAPID/SRT3D 계열
    1. 현재 pose 에서 메쉬의 **실루엣 모서리**를 찾는다: 인접 두 면의 앞/뒤향이 갈리는 edge.
       (래스터화가 필요 없다. 바깥 테두리뿐 아니라 **중심 홀 테두리**도 자동으로 잡힌다 —
        둘 다 SEMI 표준부다.)
    2. 그 3D 모서리를 투영해 등간격 샘플하고, 각 점에서 **윤곽 법선 방향으로** 원본 이미지의
       방향 미분이 최대인 곳을 찾는다(포물선 보간으로 **서브픽셀**).
    3. 잔차 = (투영점 − 관측 edge점)·법선. 6-DoF(회전벡터+평행이동)로 **Huber 강건 최소제곱**.
    4. 재투영하며 `--iters` 회 반복.

★ **GT 를 쓰지 않는다.** 입력은 `left.png` · `cam.json` · 초기 pose 뿐이다 → 실환경에 그대로 간다.
★ **표준부만 쓴다.** `--mesh top_flange.ply` 면 테두리와 중심 홀만 정합에 들어간다
  (body 는 제조사마다 다르다 — `RESULTS.md §20`).
★ **research-only 코드에 의존하지 않는다** — numpy/opencv/scipy/trimesh 뿐이라 상업 경로가 깨지지 않는다.

⚠️ 한계
    - **초기값이 필요하다.** 실루엣 정합은 국소 수렴이라 90° 오추정은 못 고친다.
    - 평면형 테두리라 **Z(거리)는 약하게 구속**된다 — `--fix-z` 로 초기 pose 의 Z 를 묶을 수 있다.
    - 배경 대비가 없으면(검정 flange + 검정 배경) edge 가 안 잡힌다. 유효 대응점 수를 항상 기록한다.

★ **이동량 게이트 `--gate-deg`** (`RESULTS.md §26`)
    남은 실패는 **면외 tilt 폭주**뿐이고, 그 프레임들은 초기값에서 **크게 회전한다**(실패 3.3~8.5°,
    성공 ≤2.9°). 그래서 *"초기값 대비 회전 이동량이 τ 를 넘으면 정합 결과를 버린다"* 로 걸러진다.
    비교 대상이 GT 가 아니라 **초기값**이라 실환경에 그대로 간다. τ=1.5° 에서 전 초기값 구성이
    **40/40 을 회복**한다. 버린 결과는 `pose_contour_raw.json` 에 남는다.

출력  <out>/frame_XXXX/  pose_coarse.json(=입력 pose, 대조용) pose_refined.json(정합 결과)
      + pose_contour_raw.json(게이트에 걸린 경우) + contour_debug.png (--debug)  + meta_contour.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import trimesh
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def load_pose_mm(p: Path) -> np.ndarray | None:
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    T = np.eye(4)
    T[:3, :3] = np.asarray(d["R"], float).reshape(3, 3)
    T[:3, 3] = np.asarray(d["t_mm"], float)
    return T


def rot_deg(R1: np.ndarray, R2: np.ndarray) -> float:
    return float(np.degrees(np.arccos(np.clip((np.trace(R1.T @ R2) - 1.0) / 2.0, -1.0, 1.0))))


def pose_json(T: np.ndarray, stage: str, extra: dict | None = None) -> dict:
    return {"frame": "cam_T_obj", "convention": "BOP (R 3x3 row-major, t mm)",
            "R": np.asarray(T[:3, :3], float).round(9).tolist(),
            "t_mm": np.asarray(T[:3, 3], float).round(6).tolist(),
            "stage": stage, **(extra or {})}


def silhouette_points(mesh: trimesh.Trimesh, adj, adj_edges, T: np.ndarray,
                      per_edge: int = 3) -> np.ndarray:
    """현재 pose 에서 **실루엣 모서리** 위의 3D 점들 (물체 좌표계).

    인접한 두 면의 **앞/뒤 향함이 갈리는** edge 가 occluding contour 다. 카메라 좌표계에서
    `n · (c - 0) < 0` 이면 앞면(카메라를 향함)이다 — 원근이므로 면 중심 벡터를 써야 한다.
    """
    V = np.asarray(mesh.vertices)
    N = np.asarray(mesh.face_normals)
    C = np.asarray(mesh.triangles_center)
    R, t = T[:3, :3], T[:3, 3]
    Nc = (R @ N.T).T
    Cc = (R @ C.T).T + t
    front = np.einsum("ij,ij->i", Nc, Cc) < 0
    sil = front[adj[:, 0]] != front[adj[:, 1]]
    if not sil.any():
        return np.zeros((0, 3))
    E = V[adj_edges[sil]]                                  # (M,2,3)
    w = np.linspace(0.0, 1.0, per_edge + 2)[1:-1]          # 끝점은 제외(모서리 교차점이라 불안정)
    return (E[:, None, 0, :] * (1 - w)[None, :, None] + E[:, None, 1, :] * w[None, :, None]
            ).reshape(-1, 3)


def project(P: np.ndarray, T: np.ndarray, K: np.ndarray) -> np.ndarray:
    X = (T[:3, :3] @ P.T).T + T[:3, 3]
    uv = (K @ X.T).T
    return uv[:, :2] / np.maximum(uv[:, 2:3], 1e-9)


def build_samples(mesh, adj, adj_edges, T, K, per_edge=3):
    """실루엣 모서리 위 샘플점 + 그 점에서의 **2D 윤곽 법선**을 함께 만든다."""
    V = np.asarray(mesh.vertices)
    N = np.asarray(mesh.face_normals)
    C = np.asarray(mesh.triangles_center)
    R, t = T[:3, :3], T[:3, 3]
    front = np.einsum("ij,ij->i", (R @ N.T).T, (R @ C.T).T + t) < 0
    sil = front[adj[:, 0]] != front[adj[:, 1]]
    if not sil.any():
        return np.zeros((0, 3)), np.zeros((0, 2)), np.zeros((0, 2))
    E = V[adj_edges[sil]]                                   # (M,2,3)
    a2, b2 = project(E[:, 0], T, K), project(E[:, 1], T, K)
    d = b2 - a2
    L = np.linalg.norm(d, axis=1)
    ok = L > 1e-6
    E, a2, d, L = E[ok], a2[ok], d[ok], L[ok]
    d = d / L[:, None]
    n2 = np.stack([-d[:, 1], d[:, 0]], 1)                   # 2D 법선
    w = np.linspace(0.0, 1.0, per_edge + 2)[1:-1]
    P3 = (E[:, None, 0, :] * (1 - w)[None, :, None] + E[:, None, 1, :] * w[None, :, None]).reshape(-1, 3)
    NN = np.repeat(n2, per_edge, axis=0)
    return P3, NN, np.repeat(L, per_edge)


def sample_bilinear(img: np.ndarray, xy: np.ndarray) -> np.ndarray:
    return cv2.remap(img, xy[None, :, 0].astype(np.float32), xy[None, :, 1].astype(np.float32),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)[0]


def find_edges(gray_f: np.ndarray, p: np.ndarray, n: np.ndarray, search: int,
               min_grad: float, polarity: str = "bright_out") -> tuple[np.ndarray, np.ndarray]:
    """법선 방향 ±search px 에서 관측 edge 를 찾는다 (서브픽셀).

    ⚠️ **전역 최대를 쓰면 안 된다** — 검정 flange 옆의 **그림자 경계**가 물체 경계보다 강해서
    거기로 끌려간다(GT 에서 출발시켜도 R 1.1° / t 1.35mm 이동하는 것으로 확인). 그래서:
      ① 법선을 **바깥쪽으로 정렬**하고
      ② **극성**을 요구한다 — `bright_out` 이면 안쪽(물체)이 어둡고 바깥이 밝아 `∂I/∂n > 0`
      ③ 그중 **예측에 가장 가까운 국소최대**를 고른다(전역 최대가 아니라).
    """
    ks = np.arange(-search, search + 1, dtype=np.float32)
    prof = np.stack([sample_bilinear(gray_f, p + k * n) for k in ks], 1)   # (P, 2S+1)
    g = np.gradient(prof, axis=1)
    if polarity == "dark_out":
        g = -g
    elif polarity == "any":
        g = np.abs(g)
    # 국소최대 + 임계 통과
    cand = np.zeros_like(g, dtype=bool)
    cand[:, 1:-1] = (g[:, 1:-1] >= g[:, :-2]) & (g[:, 1:-1] >= g[:, 2:]) & (g[:, 1:-1] > min_grad)
    # 예측(k=0)에 가장 가까운 후보
    dist = np.where(cand, np.abs(ks)[None, :], np.inf)
    j = dist.argmin(1)
    valid = np.isfinite(dist[np.arange(len(j)), j])
    jm = np.clip(j - 1, 0, g.shape[1] - 1); jp = np.clip(j + 1, 0, g.shape[1] - 1)
    y0, y1, y2 = g[np.arange(len(j)), jm], g[np.arange(len(j)), j], g[np.arange(len(j)), jp]
    den = (y0 - 2 * y1 + y2)
    sub = np.clip(np.where(np.abs(den) > 1e-9, 0.5 * (y0 - y2) / np.where(np.abs(den) > 1e-9, den, 1.0), 0.0), -1, 1)
    return ks[j] + sub, valid


def silhouette_segments(mesh, adj, adj_edges, T, K) -> np.ndarray:
    """실루엣 모서리를 투영한 **선분** (M,2,2). 실루엣은 닫힌 고리라 선분으로 그리면 새지 않는다."""
    V = np.asarray(mesh.vertices)
    R, t = T[:3, :3], T[:3, 3]
    front = np.einsum("ij,ij->i", (R @ np.asarray(mesh.face_normals).T).T,
                      (R @ np.asarray(mesh.triangles_center).T).T + t) < 0
    sil = front[adj[:, 0]] != front[adj[:, 1]]
    if not sil.any():
        return np.zeros((0, 2, 2))
    E = V[adj_edges[sil]]
    return np.stack([project(E[:, 0], T, K), project(E[:, 1], T, K)], 1)


def outer_only(p: np.ndarray, seg: np.ndarray, hw, thick: int = 2) -> np.ndarray:
    """투영 샘플 중 **가장 바깥 윤곽**에 속한 것만 남기는 불리언 마스크.

    왜 필요한가 — 융기 테두리가 있는 flange 는 실루엣이 하나가 아니다. 외곽선 말고도
    **융기 능선을 따라 물체 안쪽에 고리**가 생긴다. 검정 flange 위의 검정 능선이라
    이미지 대비가 거의 없는데 샘플 수는 크게 늘어(121→9,087) 가장 약한 자유도
    (면외 tilt)에 잡음을 얹을 수 있다. → `RESULTS.md §23-2`.

    구현: **실루엣 선분**을 그려 닫힌 고리를 만들고 이미지 바깥에서 flood fill 해,
    바깥 영역과 맞닿은 획 위의 샘플만 남긴다. 볼록성을 가정하지 않으므로 노치가 있어도
    맞다(횡단 정리 #46).
    ⚠️ 점만 찍어 고리를 만들면 **획에 틈이 생겨 flood 가 새고**, 전부 outer 로 분류된다
       (첫 구현이 그랬다 — 9,087개 전부 통과해 필터가 무효였다).
    """
    if len(p) < 30 or len(seg) == 0:
        return np.ones(len(p), bool)
    h, w = hw
    pad = thick + 4
    m = np.zeros((h + 2 * pad, w + 2 * pad), np.uint8)
    S = np.rint(seg).astype(np.int32) + pad
    for a, b in S:
        cv2.line(m, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), 255, thick)
    free = (m == 0).astype(np.uint8)
    ff = np.zeros((free.shape[0] + 2, free.shape[1] + 2), np.uint8)
    cv2.floodFill(free, ff, (0, 0), 2)                    # 바깥 = 2
    outside = (free == 2).astype(np.uint8)
    touch = cv2.dilate(outside, np.ones((2 * thick + 3,) * 2, np.uint8)) > 0
    q = np.rint(p).astype(np.int32) + pad
    q[:, 0] = np.clip(q[:, 0], 0, m.shape[1] - 1)
    q[:, 1] = np.clip(q[:, 1], 0, m.shape[0] - 1)
    keep = touch[q[:, 1], q[:, 0]]
    return keep if keep.sum() >= 30 else np.ones(len(p), bool)


def residuals_at(gray_f, mesh, adj, adj_edges, T, K, search, min_grad, per_edge,
                 polarity="auto", rim_mask=None, outer=False):
    """pose `T` 에서의 **부호 있는 잔차**(px)와 대응점을 낸다 — 정합하지 않고 재기만 한다.

    `T` 에 GT 를 넣으면 *"관측 edge 가 참 실루엣에서 얼마나 밀려 있는가"* 가 나온다.
    라운드 처리된 융기 테두리는 계단이 아니라 밝기 기울기를 만들어 이 값이 0 이 아니게 된다.
    부호는 **바깥이 +**.
    """
    P3, n2, _ = build_samples(mesh, adj, adj_edges, T, K, per_edge)
    if rim_mask is not None and len(P3):
        keep = rim_mask(P3)
        P3, n2 = P3[keep], n2[keep]
    if len(P3) < 10:
        return np.zeros(0), np.zeros((0, 2)), np.zeros((0, 2)), "?"
    p = project(P3, T, K)
    h, w = gray_f.shape
    inb = (p[:, 0] > search + 1) & (p[:, 0] < w - search - 2) & \
          (p[:, 1] > search + 1) & (p[:, 1] < h - search - 2)
    P3, n2, p = P3[inb], n2[inb], p[inb]
    if outer and len(P3):
        k = outer_only(p, silhouette_segments(mesh, adj, adj_edges, T, K), gray_f.shape)
        P3, n2, p = P3[k], n2[k], p[k]
    if len(P3) < 10:
        return np.zeros(0), np.zeros((0, 2)), np.zeros((0, 2)), "?"
    ctr = p.mean(0)
    flip = np.einsum("ij,ij->i", p - ctr, n2) < 0
    n2 = np.where(flip[:, None], -n2, n2)
    pol = polarity
    if pol == "auto":
        din = sample_bilinear(gray_f, p - 4.0 * n2)
        dout = sample_bilinear(gray_f, p + 4.0 * n2)
        pol = "bright_out" if np.median(dout - din) > 0 else "dark_out"
    d, valid = find_edges(gray_f, p, n2, search, min_grad, pol)
    return d[valid], p[valid], n2[valid], pol


def draw_debug(gray_f, mesh, adj, adj_edges, T_ref, T_init, T_gt, K, search, min_grad,
               per_edge, polarity, rim_mask, outer=False, tile=520):
    """정합 결과를 **눈으로** 검사할 한 장. 위=전체, 아래=테두리 확대 2곳.

    · 노랑 = 모델 실루엣 샘플(최종 pose)  · 빨강/파랑 선 = 그 점에서 찾은 관측 edge 까지(밖/안)
    · 초록 = GT 실루엣  (sim 전용)

    ⚠️ **`viz.overlay_pose` 와 색 규약이 다르다** — 거기서는 **빨강=GT · 초록=예측**이다.
       그래서 두 도구 모두 **이미지에 범례를 찍는다.** 시트를 인용할 때 색을 말로 옮기지 말고
       범례를 함께 보게 할 것.
    """
    bgr = cv2.cvtColor(np.clip(gray_f, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    if T_gt is not None:
        g3, _, _ = build_samples(mesh, adj, adj_edges, T_gt, K, per_edge)
        for u, v in np.rint(project(g3, T_gt, K)).astype(int):
            cv2.circle(bgr, (u, v), 1, (0, 255, 0), -1)
    d, p, n2, pol = residuals_at(gray_f, mesh, adj, adj_edges, T_ref, K, search,
                                 min_grad, per_edge, polarity, rim_mask, outer)
    for di, pi, ni in zip(d, p, n2):
        a = tuple(np.rint(pi).astype(int))
        b = tuple(np.rint(pi + di * ni).astype(int))
        cv2.line(bgr, a, b, (0, 0, 255) if di > 0 else (255, 0, 0), 1)
        cv2.circle(bgr, a, 1, (0, 255, 255), -1)
    if len(p) == 0:
        return bgr
    h, w = gray_f.shape
    x0, y0 = np.clip(p.min(0).astype(int) - 20, [0, 0], [w - 2, h - 2])
    x1, y1 = np.clip(p.max(0).astype(int) + 20, [x0 + 1, y0 + 1], [w, h])
    crop = bgr[y0:y1, x0:x1]
    if crop.size == 0:                                   # 방어: 크롭이 비면 전체를 쓴다
        crop = bgr
    full = cv2.resize(crop, (2 * tile, 2 * tile))
    # 확대: 잔차가 가장 큰 점과 가장 작은 점 주변
    zooms = []
    for idx, lab in ((int(np.argmax(d)), "max"), (int(np.argmin(d)), "min")):
        cx, cy = np.rint(p[idx]).astype(int)
        r = 26
        a, b = max(0, min(cy - r, h - 2)), min(h, max(cy + r, 2))
        c, e = max(0, min(cx - r, w - 2)), min(w, max(cx + r, 2))
        sub = bgr[a:b, c:e]
        z = cv2.resize(sub if sub.size else bgr, (tile, tile), interpolation=cv2.INTER_NEAREST)
        cv2.putText(z, f"{lab} d={d[idx]:+.2f}px", (8, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 255, 255), 1)
        zooms.append(z)
    bar = np.full((30, 2 * tile, 3), 35, np.uint8)
    cv2.putText(bar, f"pol={pol}  n={len(d)}  d median {np.median(d):+.2f}px  "
                     f"mean {d.mean():+.2f}  rms {np.sqrt((d**2).mean()):.2f}",
                (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    # ⚠️ 범례를 **이미지에 찍는다.** `viz.overlay_pose` 는 GT 를 **빨강**으로 그리는데 여기서는
    #    **초록**이다 — 두 도구를 나란히 보면 반드시 헷갈린다(실제로 헷갈렸다).
    key = np.full((26, 2 * tile, 3), 20, np.uint8)
    for txt, col, x in (("yellow=model samples", (0, 255, 255), 8),
                        ("green=GT silhouette", (0, 255, 0), 250),
                        ("red/blue=residual out/in", (0, 0, 255), 480)):
        cv2.putText(key, txt, (x, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
    return np.concatenate([bar, key, full, np.concatenate(zooms, 1)], 0)


def refine_one(gray_f, mesh, adj, adj_edges, T0, K, iters, search, min_grad,
               per_edge, fix_z, huber_px, polarity="bright_out", rim_mask=None, outer=False,
               max_samples=0, no_hole_mm=0.0, keep_hole_mm=0.0, hole_center_mm=0.0):
    T = T0.copy()
    hist = []
    for it in range(iters):
        P3, n2, _ = build_samples(mesh, adj, adj_edges, T, K, per_edge)
        if rim_mask is not None and len(P3):
            P3, n2 = P3[rim_mask(P3)], n2[rim_mask(P3)]
        if len(P3) < 30:
            break
        p = project(P3, T, K)
        h, w = gray_f.shape
        inb = (p[:, 0] > search + 1) & (p[:, 0] < w - search - 2) & \
              (p[:, 1] > search + 1) & (p[:, 1] < h - search - 2)
        P3, n2, p = P3[inb], n2[inb], p[inb]
        if no_hole_mm > 0 and len(P3):
            k = np.hypot(P3[:, 0], P3[:, 1]) > no_hole_mm
            P3, n2, p = P3[k], n2[k], p[k]
        if outer and len(P3):
            k = outer_only(p, silhouette_segments(mesh, adj, adj_edges, T, K), gray_f.shape)
            if keep_hole_mm > 0:
                # ★ **중심 홀은 규격부다**(`d63 ø35±0.1`) — outer-only 로 한꺼번에 버리면 안 된다.
                #   회전은 테두리가, 평행이동은 홀이 준다(홀은 완전한 원이라 yaw 정보 0, §21).
                #   비규격인 **중간부만** 빼는 것이 "표준부만 쓴다" 의 정확한 구현이다.
                k = k | (np.hypot(P3[:, 0], P3[:, 1]) <= keep_hole_mm)
            P3, n2, p = P3[k], n2[k], p[k]
        if max_samples and len(P3) > max_samples:
            sel = np.linspace(0, len(P3) - 1, max_samples).round().astype(int)
            P3, n2, p = P3[sel], n2[sel], p[sel]
        if len(P3) < 30:
            break
        # 법선을 **바깥쪽**으로 정렬한다 — 극성 판정의 전제다
        ctr = p.mean(0)
        flip = np.einsum("ij,ij->i", p - ctr, n2) < 0
        n2 = np.where(flip[:, None], -n2, n2)
        pol = polarity
        if pol == "auto":
            # ⚠️ 조명에 따라 flange 가 배경보다 **밝을 수도** 있다(실측: 램프 근처 프레임에서 R 2.67° 실패).
            #    현재 투영을 기준으로 안/밖 밝기를 재서 프레임마다 극성을 정한다.
            din = sample_bilinear(gray_f, p - 4.0 * n2)
            dout = sample_bilinear(gray_f, p + 4.0 * n2)
            pol = "bright_out" if np.median(dout - din) > 0 else "dark_out"
        d, valid = find_edges(gray_f, p, n2, search, min_grad, pol)
        if hole_center_mm > 0:
            # ★ **중심 홀은 지름을 믿지 않고 중심만 쓴다** (사용자 제안, `RESULTS.md §28`).
            #   제조사마다 최상면 융기 유무로 홀 개구가 달라진다 → CAD 와 지름이 어긋나면 홀 샘플의
            #   잔차에 **일정한 방사 성분**이 실린다. 법선이 전부 방사 방향이므로 그 성분은 곧
            #   `mean(d)` 이고, **빼 버리면 지름 오차가 1차로 상쇄된다.**
            #   중심 어긋남은 `cos(θ−φ)` 로, tilt 는 `cos 2θ` 로 나타나 평균이 0 이라 그대로 남는다.
            h = (np.hypot(P3[:, 0], P3[:, 1]) <= hole_center_mm) & valid
            if h.sum() >= 8:
                d = d.copy()
                d[h] -= float(np.median(d[h]))       # 평균 대신 중앙값 — 어두운 깔때기의 이상치에 강하다
        P3, n2, q = P3[valid], n2[valid], (p + d[:, None] * n2)[valid]
        if len(P3) < 30:
            break

        R0, t0 = T[:3, :3], T[:3, 3]

        def apply(x):
            """x = (rvec, t) 를 왼쪽에서 곱한다: T' = [dR|dt]·T. fix_z 면 Z 를 초기값으로 되돌린다."""
            dR = Rotation.from_rotvec(x[:3]).as_matrix()
            Tn = np.eye(4)
            Tn[:3, :3] = dR @ R0
            Tn[:3, 3] = dR @ t0 + np.r_[x[3:5], 0.0 if fix_z else x[5]]
            if fix_z:
                Tn[2, 3] = t0[2]                            # 이름대로 Z 를 진짜로 묶는다
            return Tn

        def resid(x):
            return np.einsum("ij,ij->i", project(P3, apply(x), K) - q, n2)   # 점-직선 거리

        nvar = 5 if fix_z else 6
        sol = least_squares(lambda z: resid(np.r_[z, 0.0] if fix_z else z),
                            np.zeros(nvar), loss="huber", f_scale=huber_px,
                            method="trf", max_nfev=60, xtol=1e-8, ftol=1e-8)
        Tn = apply(np.r_[sol.x, 0.0] if fix_z else sol.x)
        step = float(np.linalg.norm(Tn[:3, 3] - T[:3, 3]))
        T = Tn
        rms = float(np.sqrt(np.mean(np.einsum("ij,ij->i", project(P3, T, K) - q, n2) ** 2)))
        hist.append({"iter": it, "n_corr": int(len(P3)), "rms_px": round(rms, 4),
                     "step_mm": round(step, 4)})
        if step < 0.01:
            break
    return T, hist


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="원본 해상도 테두리(실루엣) pose refinement")
    ap.add_argument("--in", dest="in_dir", required=True, help="캡처 디렉토리 (left.png·cam.json)")
    ap.add_argument("--pose-dir", required=True, help="초기 pose 디렉토리 (FoundationPose 산출)")
    ap.add_argument("--pose-name", default="pose_refined.json")
    ap.add_argument("--obj", required=True)
    ap.add_argument("--mesh", default="top_flange.ply",
                    help="정합에 쓸 메쉬. **표준부만** 쓰려면 top_flange.ply (기본)")
    ap.add_argument("--iters", type=int, default=8)
    ap.add_argument("--search-px", type=int, default=8, help="법선 방향 탐색 반경")
    ap.add_argument("--per-edge", type=int, default=3, help="실루엣 모서리당 샘플 수")
    ap.add_argument("--min-grad", type=float, default=1.5, help="유효 edge 로 볼 최소 |∂I/∂n| (0~255 스케일)")
    ap.add_argument("--huber-px", type=float, default=2.0)
    ap.add_argument("--polarity", default="auto", choices=["auto", "bright_out", "dark_out", "any"],
                    help="auto=프레임마다 안/밖 밝기로 판정(기본) / bright_out=물체가 어둡다 / "
                         "any=극성 무시(**그림자에 끌린다** — 권장 안 함)")
    ap.add_argument("--blur", type=float, default=1.0, help="기울기 계산 전 가우시안 σ (0=끄기)")
    ap.add_argument("--rim-only-mm", type=float, default=0.0,
                    help="샘플을 **XY 외곽선에서 W mm 이내**(=규격 테두리)로 제한한다. 0=제한 없음. "
                         "중심 홀 테두리와 중간부 융기가 실루엣에 섞이는 것을 막는다 — "
                         "flange 중간부가 제조사마다 달라도 견디게 하는 장치")
    ap.add_argument("--no-hole-mm", type=float, default=0.0,
                    help="중심에서 이 반경(mm) 안의 샘플을 뺀다. **중심 홀만** 제외하고 나머지 안쪽 "
                         "실루엣은 남긴다 — `--outer-only` 는 둘을 한꺼번에 뺀다. "
                         "홀은 원뿔이 가팔라 어두운 깔때기 안에서 신호 없는 대응을 대량 만든다(§25-4c)")
    ap.add_argument("--max-samples", type=int, default=0,
                    help="샘플을 이 개수로 **균등 솎아낸다**(0=전부). 세분화 밀도의 효과만 분리해 재려고 둔다 — "
                         "형상은 그대로 두고 대응점 수만 바꾼다")
    ap.add_argument("--outer-only", action="store_true",
                    help="**가장 바깥 윤곽의 샘플만** 쓴다. 융기 테두리가 만드는 안쪽 능선 고리는 "
                         "검정 위 검정이라 정보가 없는데 수만 늘린다(121→4,522) — 그 잡음이 "
                         "가장 약한 자유도(면외 tilt)로 들어간다")
    ap.add_argument("--keep-hole-mm", type=float, default=0.0,
                    help="`--outer-only` 를 쓰더라도 **중심에서 반경 R 안의 샘플은 남긴다**. "
                         "중심 홀도 SEMI 규격부(`d63 ø35±0.1`)이므로 비규격인 **중간부만** 빼는 것이 "
                         "'표준부만 쓴다' 의 정확한 구현이다. 회전은 테두리가·평행이동은 홀이 준다(§27-6). "
                         "권장 25 (홀 상단 개구 ø45 + 여유)")
    ap.add_argument("--hole-center-mm", type=float, default=0.0,
                    help="중심에서 반경 R 안(=중심 홀) 샘플의 잔차에서 **중앙값을 뺀다**. "
                         "→ 홀의 **지름은 안 믿고 중심만** 쓴다. 제조사마다 최상면 융기 유무로 홀 개구가 "
                         "달라지는데(사용자 확정), 동심 반경 변화는 중심을 안 움직이므로 1차로 상쇄된다. "
                         "`--keep-hole-mm` 과 같은 값을 주면 된다 (§28)")
    ap.add_argument("--fix-z", action="store_true", help="Z 를 초기 pose 값으로 묶는다(평면 테두리는 Z 구속이 약하다)")
    ap.add_argument("--gate-deg", type=float, default=0.0,
                    help="정합이 초기값에서 **이만큼 넘게 회전하면 결과를 버리고 초기값을 그대로 낸다**. "
                         "0=끄기. 남은 실패는 전부 면외 tilt 폭주이고 그 프레임들은 크게 움직인다 — "
                         "GT 없이 판정된다(§26). 권장 1.5° (원거리 5시점 융합 초기값 기준)")
    ap.add_argument("--gate-mm", type=float, default=0.0, help="같은 게이트를 평행이동 이동량에도 적용 (0=끄기)")
    ap.add_argument("--debug", action="store_true", help="프레임마다 contour_debug.png 저장")
    ap.add_argument("--out", dest="out_dir", required=True)
    args = ap.parse_args(argv)

    in_dir, out_dir, pdir = Path(args.in_dir), Path(args.out_dir), Path(args.pose_dir)
    if in_dir.resolve() == out_dir.resolve():
        print("❌ --out 이 --in 과 같다 (GT 를 덮어쓴다).", file=sys.stderr)
        return 2
    mesh = trimesh.load(Path(args.obj) / args.mesh, process=False)
    adj, adj_edges = np.asarray(mesh.face_adjacency), np.asarray(mesh.face_adjacency_edges)

    rim_mask = None
    if args.rim_only_mm > 0:
        # ⚠️ 윤곽은 **볼록껍질이 아니라 진짜 투영 윤곽**이어야 한다 (횡단 정리 #46)
        from spatial_vision.cad.build_rim_obj import outline_polygon
        from shapely.geometry import Point
        poly = outline_polygon(mesh)
        bnd = poly.exterior
        w = args.rim_only_mm

        def rim_mask(P):                                     # noqa: F811
            return np.array([bnd.distance(Point(q[0], q[1])) <= w for q in P])

    frames = sorted([p for p in in_dir.glob("frame_*") if p.is_dir()]) or [in_dir]
    print(f"== 테두리 정합 | {len(frames)} 프레임 | mesh={args.mesh} ({len(mesh.faces)}f)"
          f" | init={pdir.name}/{args.pose_name} | search ±{args.search_px}px")
    rows, t0 = [], time.time()
    for f in frames:
        cam = json.loads((f / "cam.json").read_text())
        K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]], float)
        T_init = load_pose_mm(pdir / f.name / args.pose_name)
        if T_init is None:
            print(f"  {f.name}: 초기 pose 없음 — 건너뜀", file=sys.stderr)
            continue
        gray = cv2.imread(str(f / "left.png"), cv2.IMREAD_GRAYSCALE).astype(np.float32)
        if args.blur > 0:
            gray = cv2.GaussianBlur(gray, (0, 0), args.blur)

        T, hist = refine_one(gray, mesh, adj, adj_edges, T_init, K, args.iters,
                             args.search_px, args.min_grad, args.per_edge, args.fix_z,
                             args.huber_px, args.polarity, rim_mask, args.outer_only,
                             args.max_samples, args.no_hole_mm, args.keep_hole_mm,
                             args.hole_center_mm)

        moved = float(np.linalg.norm(T[:3, 3] - T_init[:3, 3]))
        moved_deg = rot_deg(T_init[:3, :3], T[:3, :3])
        # ★ **이동량 게이트** — 정합이 초기값에서 크게 회전하면 그건 개선이 아니라 폭주다.
        #   남은 실패는 전부 면외 tilt 축퇴(§25-2a)이고 그 프레임만 크게 움직인다.
        #   비교 대상이 GT 가 아니라 **초기값**이라 실환경에서 그대로 쓸 수 있다.
        gated = bool((args.gate_deg > 0 and moved_deg > args.gate_deg)
                     or (args.gate_mm > 0 and moved > args.gate_mm))
        T_out = T_init if gated else T

        od = out_dir / f.name
        od.mkdir(parents=True, exist_ok=True)
        (od / "pose_coarse.json").write_text(json.dumps(pose_json(T_init, "input(FP)"), indent=2))
        (od / "pose_refined.json").write_text(json.dumps(
            pose_json(T_out, "contour_fullres", {"iters": hist, "gated": gated,
                                                 "moved_deg": round(moved_deg, 4),
                                                 "moved_mm": round(moved, 4)}), indent=2))
        if gated:
            # 버린 결과도 남긴다 — 게이트 τ 를 나중에 다시 잡으려면 원본이 있어야 한다
            (od / "pose_contour_raw.json").write_text(json.dumps(
                pose_json(T, "contour_fullres(rejected)", {"iters": hist}), indent=2))
        rows.append({"frame": f.name, "n_corr": hist[-1]["n_corr"] if hist else 0,
                     "rms_px": hist[-1]["rms_px"] if hist else None, "moved_mm": moved,
                     "moved_deg": round(moved_deg, 4), "gated": gated})
        # GT 가 있으면 **참 실루엣에서 잰 부호 있는 잔차**를 남긴다 — 정합기가 아니라
        # *관측 edge 자체*가 얼마나 밀려 있는지의 척도다 (sim 전용).
        T_gt = load_pose_mm(f / "pose_gt.json")
        if T_gt is not None:
            dg, _, _, _ = residuals_at(gray, mesh, adj, adj_edges, T_gt, K, args.search_px,
                                       args.min_grad, args.per_edge, args.polarity, rim_mask,
                                       args.outer_only)
            if len(dg):
                rows[-1]["gt_bias_px"] = round(float(np.median(dg)), 3)
                rows[-1]["gt_spread_px"] = round(float(np.percentile(dg, 84) - np.percentile(dg, 16)), 3)
        if args.debug:
            cv2.imwrite(str(od / "contour_debug.png"),
                        draw_debug(gray, mesh, adj, adj_edges, T, T_init, T_gt, K,
                                   args.search_px, args.min_grad, args.per_edge,
                                   args.polarity, rim_mask, args.outer_only))
        print(f"  {f.name}: 대응 {rows[-1]['n_corr']:4d}점  rms {rows[-1]['rms_px'] or -1:5.2f}px  "
              f"이동 {moved:6.2f}mm/{moved_deg:5.2f}°  ({len(hist)} iter)"
              + ("  ⛔게이트 → 초기값 유지" if gated else ""))

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta_contour.json").write_text(json.dumps({
        "stage": "refine_contour", "backend": "silhouette-edge LSQ (자체 구현)",
        "license": "이 저장소 코드 — research-only 의존 없음",
        "obj": args.obj, "mesh": args.mesh, "init": str(pdir / args.pose_name),
        "outer_only": args.outer_only, "keep_hole_mm": args.keep_hole_mm,
        "hole_center_mm": args.hole_center_mm,
        "max_samples": args.max_samples,
        "no_hole_mm": args.no_hole_mm,
        "iters": args.iters, "search_px": args.search_px, "per_edge": args.per_edge,
        "min_grad": args.min_grad, "huber_px": args.huber_px, "blur": args.blur,
        "polarity": args.polarity, "rim_only_mm": args.rim_only_mm,
        "fix_z": args.fix_z, "gate_deg": args.gate_deg, "gate_mm": args.gate_mm,
        "n_gated": sum(1 for r in rows if r.get("gated")),
        "sec": round(time.time() - t0, 1), "frames": rows,
    }, indent=2, ensure_ascii=False))
    ng = sum(1 for r in rows if r.get("gated"))
    print(f"  {time.time()-t0:.1f}s → {out_dir}"
          + (f" | 게이트 후퇴 {ng}/{len(rows)}" if args.gate_deg or args.gate_mm else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
