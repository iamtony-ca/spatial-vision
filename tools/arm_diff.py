#!/usr/bin/env python3
"""팔끼리 **실제로 몇 도 / 몇 mm 다른가** 를 잰다 — 육안으로 «분간이 안 될» 때 쓴다.

왜 필요한가
    `inspect/flange` 에서 팔 여섯이 겹쳐 보이면 그건 **결과**다 — 다만 «눈에 안 보인다» 와
    «같다» 는 다른 말이다(교훈 #86). 여기서 **프레임마다 짝지어** ΔR·Δt 를 직접 계산해
    **이미 측정해 둔 잡음 바닥**과 견준다:

      · `pose_fp` 재실행 잡음  ΔR 중앙 **0.146°** / 최대 0.662°            (교훈 #24)
      · 하이브리드 ADD 재실행 폭 중앙 **0.071~0.095mm** / 최대 0.147mm     (§38-9)

    차이가 그 바닥 안이면 **«구분되지 않는다» 가 증명된 것**이고, 넘으면 «눈이 못 본 것» 이다.

🔴 이건 «누가 맞나» 가 아니라 «얼마나 다른가» 다. GT 가 없으므로 정확도는 여전히 못 잰다 —
   **여섯이 합의한다 ≠ 여섯이 맞다.** 계통 편향은 전부 같이 틀려도 여기서 0 으로 나온다
   (그 축을 보는 유일한 수단은 `PIPELINE_CATALOG §7.5c` 상대 GT 다).

입력은 러너가 이미 낸 **`<run>/stats/metrics_long.csv`** 뿐이다 — 추가 계산·촬영 0.

사용
    envs/pose/bin/python tools/arm_diff.py --run runs/R28_combo
    envs/pose/bin/python tools/arm_diff.py --run runs/R28_combo runs/R56_combo runs/R66_combo
    envs/pose/bin/python tools/arm_diff.py --run ... --arms RH1,RH2,RP3_hull --ref RH1
"""
from __future__ import annotations

import argparse
import csv
import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spatial_vision.contracts import rotation_angle_deg          # noqa: E402

# 이미 측정해 둔 잡음 바닥 — 🔴 «정상 범위» 가 아니라 «같은 설정을 다시 돌렸을 때의 폭» 이다.
NOISE_R_MED, NOISE_R_MAX = 0.146, 0.662      # 교훈 #24 (pose_fp 재실행)
NOISE_T_MED, NOISE_T_MAX = 0.095, 0.147      # §38-9 (하이브리드 ADD 재실행 4회)


def R_of(row: dict) -> np.ndarray | None:
    """쿼터니언(qw,qx,qy,qz) → 회전행렬. 값이 없으면 None."""
    try:
        q = np.array([float(row[k]) for k in ("qw", "qx", "qy", "qz")])
    except (KeyError, TypeError, ValueError):
        return None
    n = np.linalg.norm(q)
    if not np.isfinite(n) or n < 1e-9:
        return None
    w, x, y, z = q / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def t_of(row: dict) -> np.ndarray | None:
    try:
        t = np.array([float(row[k]) for k in ("tx_mm", "ty_mm", "tz_mm")])
    except (KeyError, TypeError, ValueError):
        return None
    return t if np.isfinite(t).all() else None


def load(run: Path) -> dict[str, dict[str, tuple]]:
    """`stats/metrics_long.csv` → {팔: {프레임: (R, t)}}."""
    p = run / "stats" / "metrics_long.csv"
    if not p.exists():
        print(f"❌ `{p}` 가 없다 — 러너를 끝까지 돌렸는지 확인할 것", file=sys.stderr)
        return {}
    out: dict[str, dict[str, tuple]] = {}
    with p.open(newline="") as fh:
        for row in csv.DictReader(fh):
            R, t = R_of(row), t_of(row)
            if R is None or t is None:
                continue
            out.setdefault(row["variant"], {})[row["frame"]] = (R, t)
    return out


def q(v: list[float]) -> tuple[float, float, float]:
    a = np.asarray(v, float)
    return float(np.median(a)), float(np.percentile(a, 90)), float(a.max())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", nargs="+", required=True, help="러너 출력 디렉토리 (여러 개 가능)")
    ap.add_argument("--arms", default=None, help="쉼표로 골라 쓴다. 안 주면 CSV 에 있는 전부")
    ap.add_argument("--ref", default=None,
                    help="기준 팔. 주면 «기준 대비» 만 낸다(짝이 많으면 표가 길어진다)")
    ap.add_argument("--md-out", default=None, help="표를 마크다운으로도 쓴다")
    a = ap.parse_args(argv)

    L: list[str] = []

    def say(s: str = "") -> None:
        print(s)
        L.append(s)

    for run in [Path(r) for r in a.run]:
        d = load(run)
        if not d:
            continue
        arms = [x.strip() for x in a.arms.split(",")] if a.arms else sorted(d)
        arms = [x for x in arms if x in d]
        if len(arms) < 2:
            print(f"⚠️ {run.name}: 비교할 팔이 {len(arms)}개다 — 건너뛴다", file=sys.stderr)
            continue
        pairs = ([(a.ref, x) for x in arms if x != a.ref] if a.ref and a.ref in arms
                 else list(itertools.combinations(arms, 2)))

        say(f"\n## {run.name} — 팔 {len(arms)}개 · 짝 {len(pairs)}개")
        say("")
        say("| 짝 | n | ΔR 중앙 | ΔR p90 | **ΔR 최대** | Δt 중앙 | Δt p90 | **Δt 최대** | 판정 |")
        say("|---|---:|---:|---:|---:|---:|---:|---:|:--|")
        n_same = 0
        for u, v in pairs:
            common = sorted(set(d[u]) & set(d[v]))
            if not common:
                say(f"| `{u}` ↔ `{v}` | 0 | — | — | — | — | — | — | 🔴 공통 프레임 0 |")
                continue
            dr = [rotation_angle_deg(d[u][f][0], d[v][f][0]) for f in common]
            dt = [float(np.linalg.norm(d[u][f][1] - d[v][f][1])) for f in common]
            rm, r9, rx = q(dr)
            tm, t9, tx = q(dt)
            # ★ **구조상 같은 값을 공유하는 짝**을 먼저 가른다 — 하이브리드(R=coarse·t=refined)는
            #   자기 기반 FP 와 t 를 **정확히** 공유한다. 0.000 이 나오는 게 정상이고, 안 나오면
            #   하이브리드가 깨진 것이다. 이걸 «다르다» 로 세면 표가 통째로 오독된다.
            share = ("t 공유" if tx == 0 else "R 공유" if rx == 0 else "")
            # 🔴 판정은 **중앙값**으로 한다. 꼬리는 따로 표시한다 — n 이 작으면 max 가 곧 잡음이다.
            med_ok = rm <= NOISE_R_MED and tm <= NOISE_T_MED
            n_same += med_ok
            mark = ("★ " + share + " (구조상 정상)" if share and med_ok else
                    "🔴 " + share + " 인데 중앙 초과" if share else
                    "구분 안 됨" if med_ok and rx <= NOISE_R_MAX else
                    "⚠️ 중앙은 바닥 안 · **꼬리 초과**" if med_ok else
                    "🔴 **다르다**")
            say(f"| `{u}` ↔ `{v}` | {len(common)} | {rm:.3f}° | {r9:.3f}° | **{rx:.3f}°** "
                f"| {tm:.3f} | {t9:.3f} | **{tx:.3f}** | {mark} |")
        say("")
        n_com = max((len(set(d[u]) & set(d[v])) for u, v in pairs), default=0)
        say(f"- **{n_same}/{len(pairs)} 짝이 «중앙값» 기준 잡음 바닥 안**이다 "
            f"(ΔR ≤{NOISE_R_MED}° · Δt ≤{NOISE_T_MED}mm).")
        if n_com < 10:
            say(f"- 🔴🔴 **n={n_com} 이라 `p90`·`최대` 열은 읽지 말 것** — 표본이 10 미만이면 "
                f"꼬리 통계가 곧 잡음이다(교훈 #58: n=40 무결점도 실패율 상한이 7.5% 였다). "
                f"**중앙값 열만** 본다.")
        say(f"- ★ **`t 공유`·`R 공유` 는 «같은 값을 쓰도록 만든» 짝**이다 — 하이브리드는 자기 기반 "
            f"FP 와 **t 를 정확히 공유**한다(R=coarse·t=refined, §27-7). `0.000` 이 정상이고 "
            f"**0 이 아니면 하이브리드가 깨진 것**이다. 성능 비교로 읽지 말 것.")
        say(f"- 🔴 **«하이브리드 ↔ refined» 의 ΔR ~2° 는 잡음이 아니라 구조**다 — 하이브리드는 R 을 "
            f"`coarse` 에서 받고 refined 는 `refine` 을 거친다. §27-7 이 «refine 이 R 을 악화시킨다» "
            f"고 잰 바로 그 간격이다. **같은 축의 팔끼리만** 나란히 놓는다.")
        say(f"- 잡음 바닥은 **같은 설정을 다시 돌렸을 때의 폭**이다 — `pose_fp` 재실행 "
            f"ΔR 중앙 {NOISE_R_MED}°/최대 {NOISE_R_MAX}°(교훈 #24) · 하이브리드 ADD "
            f"{NOISE_T_MED}mm(§38-9). **그 안이면 «설정 효과의 증거가 아니다».**")

    say("")
    say("🔴 **이 표는 «얼마나 다른가» 이지 «누가 맞나» 가 아니다.** GT 가 없으므로 정확도는 못 잰다 —")
    say("   **여섯이 합의한다 ≠ 여섯이 맞다.** 전부 같이 틀린 계통 편향은 여기서 **0 으로 나온다.**")
    say("   그 축을 보는 유일한 수단은 **상대 GT**(`PIPELINE_CATALOG §7.5c`)다 — 물체를 자로 잰 만큼")
    say("   밀거나 직각자에 대고 돌려 두 번 추정하면 `Δt·ΔR` 오차가 곧 scale·offset 편향이다.")
    say("   🔴 로봇이 필요 없다(카메라를 안 움직인다).")

    if a.md_out:
        Path(a.md_out).write_text("\n".join(L) + "\n", encoding="utf-8")
        print(f"\n→ {a.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
