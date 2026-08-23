"""분할 백엔드 여러 개 **+ 그 pose 결과**를 한 이미지에 겹쳐 비교한다.

    envs/pose/bin/python -m spatial_vision.viz.seg_compare \
        --capture runs/real_50cm --out runs/RB50/segcmp/seg_compare.png \
        --seg runs/RB50/seg:mask_flange.png:A_exemplar \
        --seg runs/RB50/seg_ism:mask_full.png:I_ISM \
        --seg runs/RB50/seg_txt:mask_full.png:T_text \
        --obj assets/obj/foup_300_semi_r2 \
        --pose runs/RB50/fp_ism:pose_coarse.json:I_pose \
        --pose runs/RB50/fp_txt:pose_coarse.json:T_pose

왜 필요한가
    러너는 분할이 **3~4종 동시에** 돈다. 각각을 따로 보면 *"어느 것이 엉뚱한 물체를 집었나"* 를
    비교할 수 없다 — 같은 화소 위에 놓아야 «중앙의 FOUP» 과 «가장자리의 다른 물체» 가 갈린다.
    실제로 실물 50cm 에서 ISM 이 화면 가장자리의 작은 물체를 집었고(면적 0.64% · 중심 이탈 0.56),
    텍스트 경로만 물체를 맞게 집었다. 그 판정을 눈으로 하는 도구다.

★★ **마스크와 pose 를 같은 타일에 놓는 이유** (2026-08-22)
    `overlay_pose` 는 pose 만, 이 도구는 마스크만 보던 때에는 실패를 두 가지로 못 갈랐다:
      **①「마스크부터 엉뚱한 걸 잡았다」** vs **②「마스크는 FOUP 을 맞게 잡았는데 pose 가 틀렸다」**
    ①이면 분할(참조 세트·프롬프트·거리대)을 고쳐야 하고, ②면 depth·초기값·CAD 를 봐야 한다 —
    **처방이 정반대**다. 둘을 겹쳐 놓으면 *"윤곽이 마스크 안에 들어 있나"* 하나로 갈린다.
    ⚠️ `overlay_pose` 와 달리 **크롭하지 않으므로** ① 쪽 실패도 화면에 남는다.

무엇을 그리나 — 프레임당 한 타일 (**크롭하지 않는다**)
    🔴 **전체 화면을 그대로 쓴다** — 이 도구의 질문이 *"화면 «어디» 를 집었나"* 라서,
    물체 주위로 크롭하면 (`overlay_pose` 와 달리) 답이 통째로 사라진다.
    · 각 분할: 자기 색으로 **윤곽 2px + 채움 반투명**, 주석 `[M]`
    · 각 pose: 같은 팔레트의 **뒤이은 색**으로 **점선 윤곽 + 원점 표식**, 주석 `[P]`
      (채우지 않는다 — 마스크 채움 위에 얹혀야 하므로)
    · 화면 중심에 **십자**와 «중심 이탈 0.25» 원 — 씬 규약(카메라가 타깃을 겨눈다)의 기준선
    · 주석: 팔마다 `면적% · 중심(x,y) · 이탈` 을 **그 팔의 색으로** (pose 는 `z` 도)

⚠️ 색 규약은 이미지 안에 찍는다. 시트를 인용할 때 색을 말로 옮기지 말 것.
⚠️ `--pose` 를 쓰려면 `--obj` 가 있어야 한다. 없으면 pose 는 조용히 건너뛰지 않고 **거부**한다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

# ⚠️ `--pose` 를 쓸 때만 필요하다(trimesh 의존). 분할만 비교하는 용도로는 trimesh 없는 venv 에서도
#    그대로 돌아야 하므로 실패를 삼킨다 — 단, `--pose` 를 주면 main 이 **명시적으로 거부**한다.
#    🔴 투영 코드를 여기 복제하지 않는다. 같은 가정이 두 곳에 있으면 한쪽만 고치게 된다(교훈 #20).
try:
    from spatial_vision.viz.overlay_pose import load_pose, silhouette
except Exception:                                                # pragma: no cover
    load_pose = silhouette = None

_K_CACHE: dict = {}

# 🔴 `overlay_pose.COMBO_COLORS` 와 **같은 순서**로 둔다 — 두 시트를 나란히 볼 때 팔마다
#    색이 달라지면 눈이 헷갈린다. 빨강은 거기서 GT 전용이라 여기서도 안 쓴다.
COLORS = [(0, 255, 0), (255, 255, 0), (0, 255, 255), (255, 0, 255),
          (0, 165, 255), (255, 128, 0), (128, 255, 128), (200, 200, 255)]
# ★ pose 는 **마스크와 겹치지 않는 팔레트**를 쓴다. `COLORS` 를 이어서 쓰면 5번째가
#   연두(128,255,128)라 1번째 초록과 헷갈린다 — 실제로 시트에서 구분이 안 됐다.
POSE_COLORS = [(0, 165, 255), (255, 128, 0), (180, 180, 255), (0, 255, 128)]
EDGE_THR = 0.25          # 중심 이탈 임계 — §34-10 의 «사전 위치 가드» 를 화면 좌표로 옮긴 것


def parse_seg(spec: str, default_name: str = "mask_full.png") -> tuple[Path, str, str]:
    """`디렉토리[:파일[:라벨]]` — `--seg` 와 `--pose` 가 같은 문법을 쓴다."""
    parts = spec.split(":")
    d = Path(parts[0])
    name = parts[1] if len(parts) > 1 and parts[1] else default_name
    lab = parts[2] if len(parts) > 2 and parts[2] else d.name
    return d, name, lab


def dashed(img, contours, col, thick: int, on: int = 12, off: int = 9) -> None:
    """점선 윤곽. **마스크의 실선 윤곽과 구분**하려고 pose 는 점선으로 그린다 —
    같은 화소 위에 실선이 둘이면 어느 것이 마스크였는지 알 수 없다."""
    for c in contours:
        p = c.reshape(-1, 2)
        if len(p) < 2:
            continue
        d = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
        keep = (d % (on + off)) < on
        for i in range(len(p) - 1):
            if keep[i]:
                cv2.line(img, tuple(p[i]), tuple(p[i + 1]), col, thick)


def K_of(frame: Path) -> np.ndarray:
    """프레임의 `cam.json` → K. 프레임마다 읽으므로 캐시한다."""
    if frame not in _K_CACHE:
        import json
        c = json.loads((frame / "cam.json").read_text())
        _K_CACHE[frame] = np.array([[c["fx"], 0, c["cx"]], [0, c["fy"], c["cy"]], [0, 0, 1]], float)
    return _K_CACHE[frame]


def origin_uv(T: np.ndarray, K: np.ndarray) -> tuple[int, int] | None:
    """pose 원점(= flange 상면 중심)의 화소 좌표. 마스크 중심과 **다른 양**이라 따로 찍는다."""
    p = T[:3, 3]
    if p[2] <= 1e-6:
        return None
    uv = K @ p
    return int(round(uv[0] / uv[2])), int(round(uv[1] / uv[2]))


def stats(mask: np.ndarray) -> dict | None:
    b = mask > 127
    if b.sum() < 50:
        return None
    H, W = b.shape
    ys, xs = np.nonzero(b)
    cx, cy = xs.mean() / W, ys.mean() / H
    return {"area_pct": 100.0 * b.sum() / (H * W), "cx": cx, "cy": cy,
            "off": float(np.hypot(cx - 0.5, cy - 0.5))}


def label_bar(text: str, w: int, h: int = 26, col=(255, 255, 255)) -> np.ndarray:
    bar = np.full((h, w, 3), 30, np.uint8)
    fs = 0.55
    while fs > 0.24 and cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)[0][0] > w - 14:
        fs -= 0.03
    cv2.putText(bar, text, (8, h - 8), cv2.FONT_HERSHEY_SIMPLEX, fs, col, 1)
    return bar


def make_tile(frame: Path, segs: list, width: int, alpha: float,
              poses: list | None = None, mesh=None):
    img = cv2.imread(str(frame / "left.png"))
    if img is None:
        return None, []
    H, W = img.shape[:2]
    rows = []
    for i, (d, name, lab) in enumerate(segs):
        col = COLORS[i % len(COLORS)]
        m = cv2.imread(str(d / frame.name / name), cv2.IMREAD_GRAYSCALE)
        if m is None or m.shape != (H, W):
            rows.append((f"[M] {lab}", col, None, None))
            continue
        st = stats(m)
        rows.append((f"[M] {lab}", col, st, None))
        if st is None:
            continue
        b = m > 127
        img[b] = ((1 - alpha) * img[b] + alpha * np.array(col)).astype(np.uint8)
        cs, _ = cv2.findContours(b.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, cs, -1, col, max(2, W // 700))

    # ★ pose 투영 실루엣 — **채우지 않고 점선으로** 얹는다. 마스크 채움 위에 놓이므로
    #   채우면 아래가 안 보이고, 실선이면 마스크 윤곽과 구분이 안 된다.
    for j, (d, name, lab) in enumerate(poses or []):
        col = POSE_COLORS[j % len(POSE_COLORS)]
        T = load_pose(d / frame.name / name)
        if T is None:
            rows.append((f"[P] {lab}", col, None, None))
            continue
        s = silhouette(mesh, T, K_of(frame), (H, W))
        st = stats(s)
        rows.append((f"[P] {lab}", col, st, float(T[2, 3])))
        cs, _ = cv2.findContours(s, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        dashed(img, cs, col, max(2, W // 700))
        o = origin_uv(T, K_of(frame))
        if o is not None:
            cv2.drawMarker(img, o, col, cv2.MARKER_TILTED_CROSS, max(14, W // 90), 2)

    # 화면 중심 기준선 — «가장자리를 집었나» 를 눈으로 재는 잣대
    cx, cy = W // 2, H // 2
    cv2.drawMarker(img, (cx, cy), (255, 255, 255), cv2.MARKER_CROSS, max(20, W // 60), 2)
    cv2.ellipse(img, (cx, cy), (int(EDGE_THR * W), int(EDGE_THR * H)), 0, 0, 360, (160, 160, 160), 1)

    s = width / W
    img = cv2.resize(img, (width, int(H * s)))
    h = 18 * max(len(rows), 1) + 8
    cv2.rectangle(img, (0, 0), (width - 1, h), (0, 0, 0), -1)
    y = 15
    for lab, col, st, z in rows:
        txt = (f"{lab}: 없음" if st is None else
               f"{lab}  면적 {st['area_pct']:5.2f}%  중심 {st['cx']:.2f},{st['cy']:.2f}  "
               f"이탈 {st['off']:.2f}" + (f"  z {z:.0f}mm" if z else "")
               + ("  <-- 가장자리" if st["off"] > EDGE_THR else ""))
        cv2.putText(img, txt, (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.46, col, 1)
        y += 18
    return img, rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="분할 백엔드 겹쳐 비교 (GT 불필요)")
    ap.add_argument("--capture", required=True)
    ap.add_argument("--seg", action="append", required=True,
                    help="`디렉토리[:마스크파일[:라벨]]`. 여러 번 준다")
    ap.add_argument("--pose", action="append", default=[],
                    help="★ `디렉토리[:pose파일[:라벨]]`. 같은 타일에 **점선**으로 얹는다. "
                         "«마스크는 맞는데 pose 가 틀렸나» 를 가르는 수단이다. 여러 번 준다")
    ap.add_argument("--obj", default=None, help="--pose 를 쓸 때 필수 (투영할 메쉬의 obj 디렉토리)")
    ap.add_argument("--mesh", default="full.ply",
                    help="🔴 겹쳐 볼 마스크가 `mask_full` 이면 여기도 `full.ply` 여야 «pose 가 마스크 "
                         "안에 드는가» 를 잴 수 있다. 두 메쉬는 원점이 같아 pose 는 그대로 쓴다")
    ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--pick", default=None, help="프레임 직접 지정(쉼표)")
    ap.add_argument("--width", type=int, default=760, help="타일 폭(가로). 세로는 화면비 유지")
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--alpha", type=float, default=0.30)
    ap.add_argument("--per-frame-dir", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    cap = Path(a.capture)
    segs = [parse_seg(s) for s in a.seg]
    poses, mesh = [parse_seg(s, "pose_refined.json") for s in a.pose], None
    if poses:
        # 🔴 «조용히 건너뛰기» 금지(교훈 #22) — pose 를 달라고 했는데 안 그리면 시트를 오독한다.
        if a.obj is None or load_pose is None:
            print("❌ --pose 를 쓰려면 --obj 가 있어야 하고 trimesh 가 깔린 venv 여야 한다 (envs/pose)")
            return 2
        import trimesh
        mesh = trimesh.load(Path(a.obj) / a.mesh, process=False)
    frames = sorted([p for p in cap.glob("frame_*") if (p / "left.png").exists()])
    if not frames:
        print(f"❌ {cap}/frame_*/left.png 가 없다")
        return 2
    if a.pick:
        by = {f.name: f for f in frames}
        sel = [by[w.strip()] for w in a.pick.split(",") if w.strip() in by]
    else:
        sel = [frames[i] for i in
               np.linspace(0, len(frames) - 1, min(a.frames, len(frames))).round().astype(int)]

    tiles, names = [], []
    for f in sel:
        t, _ = make_tile(f, segs, a.width, a.alpha, poses, mesh)
        if t is None:
            continue
        cv2.putText(t, f.name, (a.width - 130, t.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        tiles.append(t)
        names.append(f.name)
    if not tiles:
        print("❌ 읽을 수 있는 프레임이 없다")
        return 2

    ncol = min(a.cols, len(tiles))
    rows = []
    for i in range(0, len(tiles), ncol):
        chunk = tiles[i:i + ncol]
        chunk += [np.zeros_like(chunk[0])] * (ncol - len(chunk))
        rows.append(np.concatenate(chunk, 1))
    W = rows[0].shape[1]
    # ⚠️ 라벨은 주석 줄에 **그 항목 색으로** 이미 찍혀 있다 — 여기 다시 나열하면 글씨만 작아진다.
    legend = ("주석 줄 색 = 그 항목 색  |  [M] 채움+실선 = 마스크" +
              ("  ·  [P] 점선+기울인십자 = pose 투영" if poses else "") +
              f"  |  흰 십자 = 화면 중심 · 회색 타원 = 이탈 {EDGE_THR}")
    sheet = np.concatenate([label_bar(legend, W, 30)] + rows, 0)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet)
    print(f"→ {out}  ({len(tiles)} 프레임 × 분할 {len(segs)} + pose {len(poses)})")

    if a.per_frame_dir:
        pfd = Path(a.per_frame_dir)
        pfd.mkdir(parents=True, exist_ok=True)
        for n, t in zip(names, tiles):
            cv2.imwrite(str(pfd / f"segcmp_{n}.png"),
                        np.concatenate([label_bar(legend, t.shape[1], 30), t], 0))
        print(f"→ {pfd}/segcmp_frame_*.png  ({len(tiles)}장)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
