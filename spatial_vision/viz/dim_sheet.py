"""top flange 를 **치수 기입 도면**으로 그린다 — 눈으로 규격을 검사하기 위한 것.

    envs/pose/bin/python -m spatial_vision.viz.dim_sheet \
        --obj assets/obj/foup_300_semi_r2 --out docs/semi/dim_r2.png

왜 필요한가
    `verify_semi` 는 숫자로 통과/실패만 낸다. *"어디를 어떻게 쟀는가"* 는 안 보인다.
    이 프로젝트는 **도면 오독으로 거짓 위반을 두 번** 보고했다(횡단 정리 #50·#61) — 그래서
    측정 위치를 **그림 위에 화살표로 그려** 사람이 대조할 수 있게 한다.

★ **표시되는 값은 전부 메쉬에서 실측한 값**이다(공칭값을 적어 두는 도면이 아니다).
  괄호 안이 SEMI 규격값이며, 벗어나면 빨강으로 표시한다.

⚠️ **인터프리터는 `envs/pose/bin/python`** 이다 — `cad` venv 에는 matplotlib 이 없다.
   그래서 shapely 를 쓰지 않고 `trimesh.intersections.mesh_plane` 만으로 단면을 만든다.

패널  ① 상면도(z 슬라이스)  ② 수직 단면 y=20  ③ 최외곽 융기 확대  ④ 중심 홀 확대
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
import trimesh                           # noqa: E402

SPEC = {"x46": (71.0, 1.0), "d63": (35.0, 0.1), "beta": (45.0, 1.0), "theta": (45.0, 0.5)}
ENV = {"z49": ("max", 8.0), "x47": ("min", 58.0)}


def section(mesh, normal, origin):
    """평면 절단 → 선분 (M,2,3). shapely 불필요."""
    seg = trimesh.intersections.mesh_plane(mesh, plane_normal=np.asarray(normal, float),
                                           plane_origin=np.asarray(origin, float))
    return np.asarray(seg).reshape(-1, 2, 3)


def draw_segments(ax, seg, ij, **kw):
    for a, b in seg:
        ax.plot([a[ij[0]], b[ij[0]]], [a[ij[1]], b[ij[1]]], **kw)


def dim_h(ax, x0, x1, y, text, color="tab:blue", off=0.0):
    """수평 치수선."""
    ax.annotate("", xy=(x0, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="<->", color=color, lw=1.0))
    ax.text((x0 + x1) / 2, y + off, text, ha="center", va="bottom", fontsize=7.5,
            color=color, bbox=dict(fc="white", ec="none", alpha=0.75, pad=0.8))


def dim_v(ax, y0, y1, x, text, color="tab:blue"):
    ax.annotate("", xy=(x, y0), xytext=(x, y1),
                arrowprops=dict(arrowstyle="<->", color=color, lw=1.0))
    ax.text(x, (y0 + y1) / 2, text, ha="left", va="center", fontsize=7.5, color=color,
            rotation=90, bbox=dict(fc="white", ec="none", alpha=0.75, pad=0.8))


def ok_color(v, spec):
    if spec is None:
        return "tab:blue"
    if len(spec) == 2 and isinstance(spec[0], (int, float)):
        return "tab:green" if abs(v - spec[0]) <= spec[1] else "tab:red"
    kind, lim = spec
    good = v <= lim if kind == "max" else v >= lim
    return "tab:green" if good else "tab:red"


def column_z(sec2, x, tol=0.15):
    """단면 선분들이 수직선 x 를 지나는 z 값들 (내림차순). 판 두께를 재는 데 쓴다."""
    zs = []
    for (x0, z0), (x1, z1) in sec2:
        if (x0 - x) * (x1 - x) <= 0 and abs(x1 - x0) > 1e-9:
            zs.append(z0 + (z1 - z0) * (x - x0) / (x1 - x0))
        elif abs(x0 - x) < tol:
            zs.append(z0)
    return sorted(zs, reverse=True)


def radius_at_z(sec2, z, r_max=45.0):
    """높이 z 에서 중심 홀 벽의 반경 — **단면 선분과의 교점**으로 정확히 구한다.

    ⚠️ 정점에서 `|z − z0| < tol` 로 고르면 안 된다 — 원뿔 벽이 긴 삼각형으로 테셀레이션돼 있으면
       그 높이에 정점이 아예 없어 엉뚱한 값(예: 상면 링)이 잡힌다. 실제로 d63 가 45.1 로 나왔다.
    """
    xs = []
    for (x0, z0), (x1, z1) in sec2:
        if (z0 - z) * (z1 - z) <= 0 and abs(z1 - z0) > 1e-9:
            x = x0 + (x1 - x0) * (z - z0) / (z1 - z0)
            if abs(x) < r_max:
                xs.append(abs(x))
    return float(min(xs)) if xs else float("nan")


def measure(mesh, y0):
    """도면에 적을 값을 **메쉬에서 직접** 잰다 (공칭값을 적어 두는 게 아니다)."""
    V = np.asarray(mesh.vertices)
    r = np.hypot(V[:, 0], V[:, 1])
    m: dict = {}
    m["half"] = float(max(V[:, 0].max(), V[:, 1].max()))
    m["z_top_max"] = float(V[:, 2].max())

    # ⚠️ 밑면은 **정점 최소 z** 가 아니다 — flange 메쉬에는 아래로 내려가는 벽이 붙어 있다(-29mm).
    #    노치를 피한 방위의 **주 환상부에서 판을 관통하는 수직선**의 두 번째 교점이 판 밑면이다.
    sec2 = section(mesh, [0, 1, 0], [0, y0, 0])[:, :, [0, 2]]
    # 홀은 y=y0(=20) 단면이 밑면에서 **안 지난다**(밑면 홀 반경 17.5 < 20) → 중심을 지나는 y=0 단면
    hsec = section(mesh, [0, 1, 0], [0, 0, 0])[:, :, [0, 2]]
    zs = column_z(sec2, 39.0)
    top = [z for z in zs if z <= 0.05]
    m["z_bot"] = float(top[1]) if len(top) > 1 else float(min(zs))
    m["z49"] = m["z_top_max"] - m["z_bot"]
    m["plate"] = -m["z_bot"]

    m["d63"] = 2 * radius_at_z(hsec, m["z_bot"] + 0.02)          # 규격: 밑면(z47) 기준
    m["open"] = float("nan")                                      # 아래에서 hole_raise 기준으로 잰다
    m["rim_raise"] = float(V[r > m["half"] - 3][:, 2].max())
    m["hole_raise"] = float(V[(r > 20) & (r < 32)][:, 2].max())
    # ⚠️ 최상면 개구는 **홀 쪽 최고점**에서 잰다. 전체 최고점(z_top_max)을 쓰면 최외곽 융기만 있고
    #    홀 융기는 없는 자산에서 그 높이에 홀 재료가 없어 NaN 이 된다(실제로 spec15 에서 터졌다).

    m["open"] = 2 * radius_at_z(hsec, m["hole_raise"] - 0.02)     # 카메라가 보는 최상면 개구
    zz = np.linspace(m["z_bot"] + 0.3, -0.3, 8)
    rr = np.array([radius_at_z(hsec, z) for z in zz])
    g = np.isfinite(rr)
    m["beta"] = float(np.degrees(np.arctan(abs(np.polyfit(zz[g], rr[g], 1)[0])))) if g.sum() > 2 else float("nan")

    # x47 = 직선 변의 끝(챔퍼 시작)까지의 |y|. ⚠️ 상면 z=0 정점으로 고르면 **융기 때문에 비어 있다**
    #      (외곽 최상면이 z=+2 다). 주 상면 **바로 아래** 수평 단면의 윤곽에서 잰다.
    outl = section(mesh, [0, 0, 1], [0, 0, -0.05])[:, :, [0, 1]].reshape(-1, 2)
    e = np.abs(np.abs(outl[:, 0]) - m["half"]) < 0.6
    m["x47"] = float(np.abs(outl[e][:, 1]).max()) if e.any() else float("nan")
    return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="top flange 치수 기입 도면")
    ap.add_argument("--obj", required=True)
    ap.add_argument("--mesh", default="top_flange.ply")
    ap.add_argument("--section-y", type=float, default=20.0,
                    help="수직 단면 위치. ⚠️ **노치를 피해야 한다** — 모든 변의 y=0 에 노치가 있다")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    obj = Path(args.obj)
    mesh = trimesh.load(obj / args.mesh, process=False)
    y0 = args.section_y
    m = measure(mesh, y0)
    half, ztm, zb = m["half"], m["z_top_max"], m["z_bot"]

    sec = section(mesh, [0, 1, 0], [0, y0, 0])
    outl = section(mesh, [0, 0, 1], [0, 0, -0.05])
    hole = section(mesh, [0, 0, 1], [0, 0, ztm - 0.05])

    fig = plt.figure(figsize=(17.5, 15.5), dpi=125)
    gs = fig.add_gridspec(3, 2, hspace=0.30, wspace=0.18, height_ratios=[1.25, 0.85, 0.85])
    fig.suptitle(f"{obj.name} / {args.mesh}    MEASURED from mesh   "
                 f"(parentheses = SEMI E47.1 spec;  green = in spec, red = violation)",
                 fontsize=12.5, y=0.955)

    # ── (1) 상면도 ───────────────────────────────────────────────────────────
    ax = fig.add_subplot(gs[0, 0])
    draw_segments(ax, outl, (0, 1), color="0.25", lw=0.9)
    draw_segments(ax, hole, (0, 1), color="tab:orange", lw=1.1)
    ax.plot([0, 0], [-half - 8, half + 8], ls=(0, (6, 4)), lw=0.6, c="0.6")
    ax.plot([-half - 8, half + 8], [0, 0], ls=(0, (6, 4)), lw=0.6, c="0.6")
    dim_h(ax, 0, half, -half - 13, f"x46 = {m['half']:.2f}  (71 +/-1)", ok_color(m["half"], SPEC["x46"]))
    dim_v(ax, -m["x47"], m["x47"], half + 6, f"x47 = {m['x47']:.2f}  (>=58)", ok_color(m["x47"], ENV["x47"]))
    ax.plot([0], [0], "+", c="tab:red", ms=9)
    ax.axhline(y0, ls=":", lw=0.9, c="tab:purple")
    ax.text(-half, y0 + 2, f"section y={y0:g}", fontsize=7, color="tab:purple")
    ax.set_aspect("equal"); ax.set_xlim(-half - 20, half + 20); ax.set_ylim(-half - 20, half + 16)
    ax.set_title(f"(1) TOP VIEW    grey = outer outline    orange = hole opening "
                 f"{m['open']:.2f} dia (no spec)", fontsize=9)
    ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)"); ax.grid(alpha=0.25, lw=0.4)

    # ── (2) 노치 상세 (+x 변) ────────────────────────────────────────────────
    ax = fig.add_subplot(gs[0, 1])
    draw_segments(ax, outl, (0, 1), color="0.25", lw=1.2)
    for yv in (-50, -30, 0, 30, 50):
        ax.axvline(yv, ls=":", lw=0.7, c="tab:red")
        ax.text(yv, half + 1.2, f"{yv:+d}" if yv else "0", fontsize=7.5, color="tab:red", ha="center")
    ax.set_xlim(-62, 62); ax.set_ylim(half - 9, half + 4)
    ax.set_title("(2) NOTCH DETAIL on +x edge   (spec: 0 / +/-30+/-1 / +/-50+/-1,  depth 5)", fontsize=9)
    ax.set_xlabel("y (mm)"); ax.set_ylabel("x (mm)"); ax.grid(alpha=0.25, lw=0.4)
    ax.text(-60, half - 8.4, "dotted red = allowed notch positions (each edge uses a DIFFERENT subset "
            "— that is the orientation code)", fontsize=7.5, color="tab:red")
    sc = obj / "semi_check.json"
    if sc.exists():
        me = json.loads(sc.read_text()).get("measured", {}).get("notches_per_edge", {})
        txt = "  ".join(f"{k}:{v}" for k, v in me.items())
        ax.text(-60, half - 7.0, f"measured (verify_semi): {txt}", fontsize=7.2, color="tab:green")

    # ── (3) 수직 단면 (등척 아님 — z 를 확대해야 보인다) ──────────────────────
    ax = fig.add_subplot(gs[1, :])
    draw_segments(ax, sec, (0, 2), color="0.2", lw=1.1)
    ax.axhline(0, ls=(0, (6, 4)), lw=0.6, c="0.6")
    ax.axhline(zb, ls=(0, (4, 3)), lw=0.9, c="tab:green")
    dim_v(ax, zb, ztm, half + 3, f"z49 = {m['z49']:.2f} (<=8)", ok_color(m["z49"], ENV["z49"]))
    dim_v(ax, zb, 0.0, -half - 6, f"plate {m['plate']:.2f}", "tab:gray")
    ax.text(0, ztm + 1.6, f"outer rim ridge +{m['rim_raise']:.2f}     hole ridge +{m['hole_raise']:.2f}",
            ha="center", fontsize=9, color="tab:blue")
    ax.text(-half - 4, zb - 1.3, "z47 = flange BOTTOM", fontsize=8, color="tab:green")
    ax.set_xlim(-half - 12, half + 10); ax.set_ylim(zb - 3.5, ztm + 3.5)
    ax.set_title(f"(3) VERTICAL SECTION y={y0:g}   —   z49 spans flange BOTTOM to TOP (ridges included). "
                 f"z exaggerated", fontsize=9)
    ax.set_xlabel("x (mm)"); ax.set_ylabel("z (mm)"); ax.grid(alpha=0.25, lw=0.4)

    # ── (4) 최외곽 융기 확대 ─────────────────────────────────────────────────
    ax = fig.add_subplot(gs[2, 0])
    draw_segments(ax, sec, (0, 2), color="0.2", lw=1.6)
    ax.axhline(0, ls=(0, (6, 4)), lw=0.6, c="0.6")
    dim_v(ax, 0.0, m["rim_raise"], half - 12, f"ridge +{m['rim_raise']:.2f}", "tab:blue")
    dim_v(ax, zb, ztm, half + 2.2, f"z49 {m['z49']:.2f}", ok_color(m["z49"], ENV["z49"]))
    ax.axvline(half, ls=":", lw=0.9, c="tab:red")
    ax.text(half - 0.4, ztm + 1.0, f"x46={m['half']:.2f}", fontsize=8, color="tab:red", ha="right")
    ax.set_aspect("equal"); ax.set_xlim(half - 20, half + 6); ax.set_ylim(zb - 2, ztm + 2.5)
    ax.set_title("(4) OUTER RIM RIDGE (zoom, 1:1)", fontsize=9)
    ax.set_xlabel("x (mm)"); ax.set_ylabel("z (mm)"); ax.grid(alpha=0.25, lw=0.4)

    # ── (5) 중심 홀 확대 ─────────────────────────────────────────────────────
    ax = fig.add_subplot(gs[2, 1])
    hs = section(mesh, [0, 1, 0], [0, 0, 0])
    draw_segments(ax, hs, (0, 2), color="0.2", lw=1.6)
    ax.axhline(0, ls=(0, (6, 4)), lw=0.6, c="0.6")
    ax.axhline(zb, ls=(0, (4, 3)), lw=1.0, c="tab:green")
    dim_h(ax, -m["d63"] / 2, m["d63"] / 2, zb - 1.9,
          f"d63 = {m['d63']:.2f} dia  (35 +/-0.1)  @ z47", ok_color(m["d63"], SPEC["d63"]))
    dim_h(ax, -m["open"] / 2, m["open"] / 2, m["hole_raise"] + 1.4,
          f"top opening {m['open']:.2f} dia  (no spec)", "tab:orange")
    dim_v(ax, 0.0, m["hole_raise"], m["open"] / 2 + 2.0, f"ridge +{m['hole_raise']:.2f}", "tab:blue")
    ax.text(-m["open"] / 2 - 3, zb + 1.6, f"beta = {m['beta']:.2f} deg\n(45 +/-1)",
            fontsize=8, color=ok_color(m["beta"], SPEC["beta"]), ha="right", va="center")
    ax.set_aspect("equal"); ax.set_xlim(-m["open"] / 2 - 18, m["open"] / 2 + 14)
    ax.set_ylim(zb - 4.0, max(m["hole_raise"], 0.0) + 4.0)
    ax.set_title("(5) CENTER HOLE (zoom, 1:1)   —   d63 is at the BOTTOM face (z47), not the top",
                 fontsize=9)
    ax.set_xlabel("x (mm)"); ax.set_ylabel("z (mm)"); ax.grid(alpha=0.25, lw=0.4)

    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"→ {out_p}")
    print("  " + " · ".join(f"{k}={v:.3f}" for k, v in m.items() if isinstance(v, float)))
    out_p.with_suffix(".json").write_text(json.dumps(m, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
