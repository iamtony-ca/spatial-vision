"""**다른 제조사 body + 우리 표준 flange** 하이브리드 객체를 만든다.

    envs/cad/bin/python -m spatial_vision.cad.build_hybrid_obj \
        --obj assets/obj/foup_300_semi \
        --body-cad "assets/cad/foup-300mm_check_only_body/FOUP 300.stl" \
        --body-scale 10 --out assets/obj/foup_300_hybrid

왜
    `RESULTS.md §20` 은 body 를 **합성 저주파 장**으로 교란해 민감도를 쟀다. 실제 제조사 차이는
    그보다 구조적일 수 있다(문 형상은 다른데 외곽은 같다든지). 사용자가 두 번째 FOUP CAD 를 제공했으므로
    **실제 형상**으로 다시 잰다. 그 CAD 의 top flange 는 사용자가 *"이상하다"* 고 확인해 주었으므로
    **body 만 가져오고 flange 는 우리 것을 그대로 쓴다.**

원점을 지키는 것이 핵심이다
    pose frame 원점 = **우리 flange 주 상면 중심**이다. 우리 `top_flange.ply` 를 **손대지 않고** 그대로
    합치므로 원점·GT 규약이 그대로 성립한다. body 는 그 아래에 붙는다.

정렬
    두 CAD 의 축 대응은 **24가지 축정렬 회전 전수 탐색 + 병진 최적화**로 구했다(§20).
    기본값은 그 결과(Z-up 공통, Z 축 90° 회전)이며 `--rot-z-deg` 로 바꿀 수 있다.
    수직 배치는 **body 상단을 우리 flange 하면에 맞춘다** — 그래야 flange 가 공중에 뜨거나 파묻히지 않는다.

⚠️ 결과 메쉬는 watertight 가 아니다(잘라 붙였다). FoundationPose 는 삼각형을 래스터화하므로 문제없지만,
   부피·질량 계산에는 쓰면 안 된다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="다른 제조사 body + 우리 flange 하이브리드 생성")
    ap.add_argument("--obj", required=True, help="기준 객체 assets/obj/<id> (flange 를 여기서 가져온다)")
    ap.add_argument("--body-cad", required=True, help="body 를 가져올 CAD 파일")
    ap.add_argument("--body-scale", type=float, default=1.0, help="body CAD → mm 배율 (cm 소스면 10)")
    ap.add_argument("--rot-z-deg", type=float, default=270.0,
                    help="body 를 Z 축으로 회전. ⚠️ 270° 다 — 24회전 탐색이 고른 값을 옮기며 "
                         "부호 규약이 뒤집혀 180° 틀렸었다(사용자가 XY 뷰에서 발견). "
                         "표면거리로는 90°(중앙 8.15mm)와 270°(5.32mm)가 잘 안 갈린다 — "
                         "외곽이 대략 대칭이라 **방향 특징을 눈으로 확인**해야 한다")
    ap.add_argument("--dxyz", type=float, nargs=3, default=(3.58, 0.06, 0.13),
                    help="bbox 중심 일치 후 추가 병진. 기본값은 §20 의 표면거리 최적화 결과")
    ap.add_argument("--cut-z", type=float, default=None,
                    help="이 z 위의 body 기하를 버린다. 기본은 **우리 상판 상면**"
                         "(= flange 바깥 기하의 최대 z). 그 CAD 의 flange 잔재를 제거한다")
    ap.add_argument("--out", required=True, help="출력 assets/obj/<id>")
    args = ap.parse_args(argv)

    obj = Path(args.obj)
    flange = trimesh.load(obj / "top_flange.ply", process=False)
    ours = trimesh.load(obj / "full.ply", process=False)

    # 우리 **상판 상면** = flange 바깥(반경 > flange 최대반경) 기하의 최대 z.
    # flange 는 여기서 위로 돌출하며, 그 돌출량이 회전 신호(테두리 비대칭)를 담는다 → 반드시 보존한다.
    W = np.asarray(ours.vertices)
    r_flange = float(np.linalg.norm(np.asarray(flange.vertices)[:, :2], axis=1).max())
    plate_z = float(W[np.linalg.norm(W[:, :2], axis=1) > r_flange * 1.03][:, 2].max())
    cut_z = args.cut_z if args.cut_z is not None else plate_z

    body = trimesh.load(args.body_cad, process=True)
    if isinstance(body, trimesh.Scene):
        body = body.dump(concatenate=True)
    body.apply_scale(args.body_scale)

    th = np.deg2rad(args.rot_z_deg)
    Rz = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1]])
    body = trimesh.Trimesh(vertices=np.asarray(body.vertices) @ Rz.T,
                           faces=np.asarray(body.faces), process=False)

    # §20 의 정렬을 그대로 쓴다: bbox 중심 일치 + 표면거리 최적화 병진.
    # 이 정렬이 두 CAD 의 **상판 상면을 자동으로 일치**시킨다(둘 다 z=-6) — 등록이 맞다는 방증이다.
    body.apply_translation(ours.bounds.mean(0) - body.bounds.mean(0) + np.asarray(args.dxyz))
    print(f"정렬 후 body 상단 z {body.bounds[1][2]:.1f} / 우리 상판 상면 z {plate_z:.1f} "
          f"(차이 {body.bounds[1][2] - plate_z:+.1f}mm)")

    # 상판보다 위(= 그 CAD 의 flange 잔재)를 잘라낸다 — 그 flange 는 신뢰할 수 없다(사용자 확인)
    keep = np.asarray(body.triangles).reshape(-1, 3, 3)[:, :, 2].max(axis=1) <= cut_z + 1e-6
    body = trimesh.Trimesh(vertices=body.vertices,
                           faces=np.asarray(body.faces)[keep], process=False)
    body.remove_unreferenced_vertices()

    hybrid = trimesh.util.concatenate([body, flange])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    hybrid.export(out / "full.ply")
    # `build_usd` 는 part 단위 시맨틱을 위해 body/top_flange 를 따로 요구한다
    body.export(out / "body.ply")
    # flange 는 **바이트 그대로** — 원점 규약과 2단계 경로가 성립하려면 동일해야 한다
    (out / "top_flange.ply").write_bytes((obj / "top_flange.ply").read_bytes())
    for name in ("keypoints.json",):
        if (obj / name).exists():
            (out / name).write_bytes((obj / name).read_bytes())

    meta = json.loads((obj / "meta.json").read_text())
    meta["obj_id"] = out.name
    meta["hybrid"] = {"body_from": args.body_cad, "body_scale": args.body_scale,
                      "rot_z_deg": args.rot_z_deg, "cut_z_mm": cut_z,
                      "flange_from": str(obj / "top_flange.ply"),
                      "note": "body 는 다른 제조사 CAD, flange 는 기준 객체 그대로(원점 불변). "
                              "watertight 아님 — 부피·질량에 쓰지 말 것"}
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    print(f"body   {len(body.vertices):,}v / {len(body.faces):,}f   bbox {np.round(body.bounds, 1).tolist()}")
    print(f"flange {len(flange.vertices):,}v (원본 그대로)")
    print(f"하이브리드 {len(hybrid.vertices):,}v / {len(hybrid.faces):,}f  "
          f"bbox {np.round(hybrid.bounds, 1).tolist()}")
    print(f"참고: 기준 full bbox {np.round(ours.bounds, 1).tolist()}")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
