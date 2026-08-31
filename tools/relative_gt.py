#!/usr/bin/env python3
"""★★★ **상대 GT** — 물체를 «자로 잰 만큼» 움직여 **팔의 절대 정확도를 서열화**한다 (§7.5c).

왜 이것뿐인가
    실환경에는 GT 가 없다. 그래서 지금 있는 지표는 **전부 «자기 일관성»** 이다 —
    오버레이·좌우 `|Δdx|`·게이트·`arm_diff` 모두 *"팔끼리 합의하는가"* 만 말하고
    **«다 같이 틀린» 경우를 원리적으로 못 본다.** 육안으로 여섯이 겹쳐 보이는 것도 같은 한계다.

    ★ **차분은 잴 수 있다.** 카메라를 고정하고 물체를 **자로 잰 만큼(≥100mm)** 밀면
    참값 `Δt` 를 안다. 팔마다 추정한 `Δt` 와의 차이가 곧 **scale·offset 계통 편향**이고,
    그건 `refine` 으로 못 고치는 바로 그 축이다(§20). **로봇이 필요 없다**(카메라를 안 움직인다).

촬영 절차 (2회)
    ① 카메라를 삼각대에 **고정**한다. FOUP 을 놓고 20~40장 연속 촬영 → `runs/relA`
    ② FOUP 을 **자로 잰 만큼** 민다(≥100mm, 한 축으로). 카메라는 **건드리지 않는다**.
       다시 20~40장 → `runs/relB`
    ③ 두 런에 러너를 돌린 뒤 이 도구를 태운다.

    🔴 **회전과 평행이동을 섞지 않는다** — pose 원점이 flange 상면 중심이라 물체를 돌리면
       `Δt` 가 오염된다(§7.5c). 이동 시험과 회전 시험을 **따로** 한다.
    🔴 **이동량을 크게** 잡는다(≥100mm) — 조작 오차가 바닥이라 작게 움직이면 신호가 묻힌다.
    ⚠️ **CAD 불일치는 안 잡힌다** — 같은 CAD 로 두 번 재서 상쇄된다(§20 은 여전히 열려 있다).

사용
    envs/pose/bin/python tools/relative_gt.py --a runs/relA --b runs/relB --move-mm 100
    envs/pose/bin/python tools/relative_gt.py --a ... --b ... --move-vec 100,0,0    # 방향까지 알 때
    envs/pose/bin/python tools/relative_gt.py --a ... --b ... --rot-deg 90          # 회전 시험
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spatial_vision.contracts import rotation_angle_deg          # noqa: E402
from tools.arm_diff import load                                  # noqa: E402


def rep(poses: dict[str, tuple]) -> tuple[np.ndarray, np.ndarray, float, float]:
    """런 하나의 **대표 pose** + 반복도.

    ⚠️ **중앙값**을 쓴다 — 정지 촬영이라도 한두 프레임이 크게 틀릴 수 있고(§35-2l-8b),
       평균은 그걸 통째로 끌고 간다(교훈 #6·#14).
    반환: (t 중앙, 대표 R, t 산포 p90, R 산포 p90) — **산포가 이 측정의 잡음 바닥**이다.
    """
    ts = np.array([t for _, t in poses.values()])
    Rs = [R for R, _ in poses.values()]
    t_med = np.median(ts, axis=0)
    # 대표 R = t 가 중앙에 가장 가까운 프레임의 R (회전 중앙값은 정의가 성가시다)
    R_med = Rs[int(np.argmin(np.linalg.norm(ts - t_med, axis=1)))]
    t_sp = float(np.percentile(np.linalg.norm(ts - t_med, axis=1), 90))
    r_sp = float(np.percentile([rotation_angle_deg(R, R_med) for R in Rs], 90))
    return t_med, R_med, t_sp, r_sp


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True, help="이동 «전» 런 디렉토리")
    ap.add_argument("--b", required=True, help="이동 «후» 런 디렉토리")
    ap.add_argument("--move-mm", type=float, default=None,
                    help="자로 잰 이동 **거리**(mm). 방향을 모를 때")
    ap.add_argument("--move-vec", default=None,
                    help="자로 잰 이동 **벡터** `x,y,z`(mm, 카메라 좌표). 방향까지 알 때 — "
                         "★ 성분별로 갈리므로 **어느 축이 틀렸나** 까지 나온다")
    ap.add_argument("--rot-deg", type=float, default=None,
                    help="직각자에 대고 돌린 **각도**(도). 🔴 이동 시험과 **따로** 한다")
    ap.add_argument("--arms", default=None, help="쉼표로 골라 쓴다. 안 주면 공통 팔 전부")
    ap.add_argument("--md-out", default=None)
    a = ap.parse_args(argv)

    if a.move_mm is None and a.move_vec is None and a.rot_deg is None:
        print("❌ `--move-mm` · `--move-vec` · `--rot-deg` 중 하나는 있어야 한다 — "
              "참값이 없으면 이 도구는 뜻이 없다", file=sys.stderr)
        return 2
    if (a.move_mm or a.move_vec) and a.rot_deg:
        print("🔴 이동과 회전을 **같이 주지 말 것** — pose 원점이 flange 상면 중심이라 "
              "물체를 돌리면 `Δt` 가 오염된다(§7.5c). 시험을 나눠서 한다.", file=sys.stderr)
        return 2

    mv = np.array([float(x) for x in a.move_vec.split(",")]) if a.move_vec else None
    want_t = float(np.linalg.norm(mv)) if mv is not None else a.move_mm

    A, B = load(Path(a.a)), load(Path(a.b))
    if not A or not B:
        return 2
    arms = [x.strip() for x in a.arms.split(",")] if a.arms else sorted(set(A) & set(B))
    arms = [x for x in arms if x in A and x in B]
    if not arms:
        print("❌ 두 런에 공통인 팔이 없다", file=sys.stderr); return 2

    L: list[str] = []

    def say(s: str = "") -> None:
        print(s); L.append(s)

    say(f"# 상대 GT — `{Path(a.a).name}` → `{Path(a.b).name}`")
    say("")
    if want_t:
        say(f"참값: **이동 {want_t:.1f}mm**" + (f"  벡터 `{mv.tolist()}`" if mv is not None else
                                             "  (방향 미지 — 크기만 비교한다)"))
    else:
        say(f"참값: **회전 {a.rot_deg:.1f}°**")
    say("")
    if want_t:
        say("| 팔 | nA/nB | 추정 \\|Δt\\| | 노름 오차 | 오차 % | 성분 오차 x/y/z |"
            + (" **3D 오차** |" if mv is not None else "") + " 반복도 t p90 (A/B) |")
        say("|---|---:|---:|---:|---:|---|" + ("---:|" if mv is not None else "") + "---|")
    else:
        say("| 팔 | nA/nB | 추정 ΔR | **오차** | Δt 오염 | 반복도 R p90 (A/B) |")
        say("|---|---:|---:|---:|---:|---|")

    rows = []
    for k in arms:
        ta, Ra, tspA, rspA = rep(A[k])
        tb, Rb, tspB, rspB = rep(B[k])
        if want_t:
            d = tb - ta
            got = float(np.linalg.norm(d))
            err = got - want_t
            # 🔴🔴 **서열은 노름 오차로 매기면 안 된다** (교훈 #83) — 이동 방향과 «직교» 하는
            #    편향은 노름에 거의 안 잡힌다. 합성 검증에서 z 편향 **+3mm** 를 심었더니
            #    노름 오차가 **+0.10mm** 로 나와 서열 2위가 됐다. `--move-vec` 를 주면
            #    **3D 벡터 오차 ‖d − mv‖** 로 매긴다.
            comp = (" / ".join(f"{v:+.1f}" for v in (d - mv)) if mv is not None else "—")
            key = float(np.linalg.norm(d - mv)) if mv is not None else abs(err)
            rows.append((key, k))
            say(f"| `{k}` | {len(A[k])}/{len(B[k])} | {got:.2f} | **{err:+.2f}mm** | "
                f"{100 * err / want_t:+.2f}% | {comp} | "
                + (f"**{key:.2f}** | " if mv is not None else "")
                + f"{tspA:.2f} / {tspB:.2f} |")
        else:
            got = rotation_angle_deg(Ra, Rb)
            err = got - a.rot_deg
            rows.append((abs(err), k))
            say(f"| `{k}` | {len(A[k])}/{len(B[k])} | {got:.3f}° | **{err:+.3f}°** | "
                f"{float(np.linalg.norm(tb - ta)):.1f}mm | {rspA:.3f} / {rspB:.3f} |")
    say("")
    rows.sort()
    say(f"★ **오차 작은 순: {' · '.join('`' + k + '`' for _, k in rows)}**"
        + ("  (기준 = **3D 벡터 오차** ‖Δt−참값‖)" if mv is not None else
           "  (기준 = 노름 오차. 🔴 `--move-vec` 가 없어 **직교 편향을 못 본다**)"))
    say("")
    say("## 읽는 법")
    say("")
    say("- ★★★ **이것이 «누가 더 정확한가» 를 답하는 유일한 표다.** 다른 지표는 전부 «자기 "
        "일관성» 이라 팔끼리 합의만 볼 수 있고, 여기서는 **외부 기준(자)** 과 견준다.")
    say("- 🔴 **«반복도» 열보다 오차가 작으면 서열은 무의미하다** — 그건 이 측정 자체의 "
        "잡음 바닥이다. 두 런의 `t p90` 합보다 오차 차이가 커야 «갈렸다» 고 말할 수 있다.")
    if mv is not None:
        say("- 🔴🔴 **«노름 오차» 가 아니라 «3D 오차» 로 서열을 매긴다**(교훈 #83) — 이동 방향과 "
            "**직교하는 편향은 노름에 거의 안 잡힌다.** 합성 검증에서 z 편향 3mm 를 심었더니 "
            "노름 오차가 **0.10mm** 로 나왔다.")
        say("- ★ **성분 오차**가 축을 짚어 준다 — `z` 만 크면 `fx·B`(스케일), `x`/`y` 가 "
            "크면 `cx`/`cy`·정류를 의심한다(§35-2k-5).")
    else:
        say("- ⚠️ 크기만 비교하면 **방향이 상쇄될 수 있다** — 가능하면 `--move-vec` 로 "
            "성분까지 준다(자로 한 축만 밀면 그대로 쓸 수 있다).")
    say("- 🔴 **CAD 불일치는 여기서 안 잡힌다** — 같은 CAD 로 두 번 재서 상쇄된다. "
        "그 축(§20)은 여전히 실물 스캔이 필요하다.")
    say("- 🔴 **카메라가 움직였으면 이 표는 통째로 무효다.** 삼각대 고정을 확인할 것 — "
        "배경이 두 런에서 같은 화소에 있는지 오버레이로 본다.")
    say("- ⚠️ 이동량이 작으면(<100mm) 조작 오차가 신호를 삼킨다. **크게 민다.**")

    if a.md_out:
        Path(a.md_out).write_text("\n".join(L) + "\n", encoding="utf-8")
        print(f"\n→ {a.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
