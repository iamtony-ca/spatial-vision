#!/usr/bin/env python3
"""프롬프트 스윕 결과에서 **«서로 다른 것만»** 뽑아 사람이 눈으로 판정하고, 그 판정으로 서열을 낸다.

왜 필요한가 (`sam3_prompt_sweep.py` 의 시트로는 안 되는 이유)
    스윕은 `report.md` 와 `sheets/by_image__*`(한 이미지 × 전 프롬프트)를 이미 낸다. 그런데
    프롬프트가 100개를 넘으면 **대부분이 소수점까지 같은 마스크**를 낸다 — 웹 237장 실측으로
    **158장(67%)에서 68개가 전부 동일**이었다. 그 칸들은 눈으로 볼 값이 0 인데 시트의 대부분을
    차지하고, 폭이 5만 픽셀을 넘어 열리지도 않는다(§39-8).
    → **군집으로 접고 갈린 것만** 보여 주면 16,116칸이 234칸이 된다.

    ★ 그리고 이건 «편의» 가 아니라 **더 나은 측정**이다 — 쉬운(=전원 동일) 표본에서 낸 순위는
      천장에 눌려 **오히려 틀린다**(§39-12b: 상위5 중 1개만 겹쳤다). 교훈 #103.

세 단계 — 전부 추론 0 (기존 `<run>/masks`·`ov` 만 읽는다)
    ① sheets : 이미지마다 마스크를 군집화 → 갈린 것만 `diff_p*.png` + `LEGEND.md` + `clusters.json`
    ② check  : 페이지별 육안 판정을 기록 → 고른 칸만 모은 `CHECK_selected_p*.png` + `human_labels.json`
    ③ rank   : 사람 라벨로 서열 → `ranking.json` + `RANKING.md`
               라벨이 없는 이미지는 «자기를 뺀 나머지의 과반과 합의하는가» 로 대리 채점한다.

🔴 산출물은 `<run>/diff/` 에 쌓이는데 **`runs/` 는 `.gitignore`** 다 — 다른 PC 로 넘길 것은
   `--md-out docs/…` 으로 따로 빼거나 `tools/prompt_ranking_md.py` 로 낸다.
"""
import argparse
import collections
import json
from pathlib import Path

import cv2
import numpy as np

IOU, SZ = 0.90, 128
CELL, LAB, HDR = 300, 46, 46
GRN, RED, BLU = (90, 210, 90), (60, 60, 230), (210, 160, 70)


# ── 공통 ────────────────────────────────────────────────────────────────────────
def load_mask(run: Path, stem: str, target: str, slug: str):
    p = run / "masks" / stem / target / f"{slug}.png"
    if not p.exists():
        return None
    m = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
    if m is None or m.max() == 0:
        return None
    return (cv2.resize(m, (SZ, SZ), interpolation=cv2.INTER_AREA) > 127).ravel()


def iou_matrix(A: np.ndarray) -> np.ndarray:
    """A = (n, SZ*SZ) bool. 🔴 `uint8` 로 행렬곱하면 **조용히 넘친다**(칸 합이 255 초과) — int32."""
    B = A.astype(np.int32)
    inter = B @ B.T
    area = B.sum(1)
    union = area[:, None] + area[None, :] - inter
    return inter / np.maximum(union, 1)


def cluster(masks: dict[str, np.ndarray], thr: float) -> list[list[str]]:
    """전이적(union-find) 군집. 큰 것부터."""
    ks = [k for k, v in masks.items() if v is not None]
    if not ks:
        return []
    M = iou_matrix(np.array([masks[k] for k in ks])) >= thr
    par = list(range(len(ks)))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for i in range(len(ks)):
        for j in np.where(M[i, i + 1:])[0] + i + 1:
            a, b = find(i), find(int(j))
            if a != b:
                par[a] = b
    g = collections.defaultdict(list)
    for i, k in enumerate(ks):
        g[find(i)].append(k)
    return [sorted(v) for v in sorted(g.values(), key=len, reverse=True)]


def ov_img(run: Path, stem: str, target: str, slug: str):
    p = run / "ov" / stem / target / f"{slug}.png"
    return cv2.imread(str(p)) if p.exists() else None


def orig_img(imgdir: Path, stem: str):
    g = [p for p in imgdir.iterdir() if p.stem == stem]
    return cv2.imread(str(g[0])) if g else None


def put(cv_, x0, y0, img, lines, col, cell=CELL):
    if img is not None:
        h, w = img.shape[:2]
        s = (cell - 6) / max(h, w)
        im = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))))
        yo, xo = (cell - im.shape[0]) // 2, (cell - im.shape[1]) // 2
        cv_[y0 + yo:y0 + yo + im.shape[0], x0 + xo:x0 + xo + im.shape[1]] = im
    cv2.rectangle(cv_, (x0 + 1, y0 + 1), (x0 + cell - 2, y0 + cell - 2), col, 3)
    for i, t in enumerate(lines[:3]):
        cv2.putText(cv_, t[:46], (x0 + 5, y0 + cell + 14 + i * 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.39, (236,) * 3, 1, cv2.LINE_AA)


def load_run(run: Path, target: str):
    d = json.load(open(run / "results.json"))
    rows = [r for r in d["rows"] if r["target"] == target]
    slugs = sorted({r["slug"] for r in rows})
    stems = sorted({r["image"] for r in rows})
    return d, rows, slugs, stems


def prompt_map(rows) -> dict:
    return {r["slug"]: r["prompt"] for r in rows}


# ── ① sheets ────────────────────────────────────────────────────────────────────
def cmd_sheets(a) -> int:
    run, sd = Path(a.run), Path(a.run) / "diff"
    sd.mkdir(exist_ok=True)
    d, rows, slugs, stems = load_run(run, a.target)
    res = {(r["slug"], r["image"]): r for r in rows}
    prm = prompt_map(rows)
    print(f"프롬프트 {len(slugs)}개 × 이미지 {len(stems)}장 — 군집화(IoU ≥{a.iou})")

    cl = []
    for n, stem in enumerate(stems, 1):
        ms = {s: load_mask(run, stem, a.target, s) for s in slugs}
        g = cluster(ms, a.iou)
        cl.append({"image": stem, "n": sum(v is not None for v in ms.values()), "groups": g})
        if n % 40 == 0:
            print(f"   {n}/{len(stems)}", flush=True)
    (sd / "clusters.json").write_text(json.dumps(cl, ensure_ascii=False))
    c = collections.Counter(len(o["groups"]) for o in cl)
    print("\n이미지당 «서로 다른 마스크» 군집 수:")
    for k in sorted(c):
        print(f"   {k:3d}군집 : {c[k]:4d}장")
    diff = sorted([o for o in cl if len(o["groups"]) > 1], key=lambda o: -len(o["groups"]))
    print(f"\n★ 전부 같은 이미지 {c.get(1,0)}장 — **볼 값이 없다.** "
          f"판정은 갈린 {len(diff)}장에서만 한다 "
          f"({len(slugs)*len(stems):,}칸 → {sum(len(o['groups']) for o in diff):,}칸)")
    if not diff:
        print("   (갈린 이미지가 없다 — 프롬프트들이 구분되지 않는다)")
        return 0

    imgdir = Path(a.imgs) if a.imgs else None
    pages = [diff[i:i + a.rows] for i in range(0, len(diff), a.rows)]
    for pi, page in enumerate(pages, 1):
        cols = 1 + min(a.max_groups, max(len(o["groups"]) for o in page))
        cv_ = np.full((HDR + len(page) * (CELL + LAB), cols * CELL, 3), 24, np.uint8)
        cv2.rectangle(cv_, (0, 0), (cols * CELL, HDR - 6), (70, 70, 70), -1)
        cv2.putText(cv_, f"{len(slugs)}개 프롬프트의 결과가 «갈린» 이미지  p{pi}/{len(pages)}  "
                         "— 맨 왼쪽=원본, 오른쪽=서로 다른 마스크 (n=몇 개가 그 마스크를 냈나)",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255,) * 3, 2, cv2.LINE_AA)
        for r, o in enumerate(page):
            y0 = HDR + r * (CELL + LAB)
            put(cv_, 0, y0, orig_img(imgdir, o["image"]) if imgdir else None,
                [f"{(pi-1)*a.rows+r+1}번 {o['image'][:32]}",
                 f"군집 {len(o['groups'])}개 / 마스크 {o['n']}"], BLU)
            for k, g in enumerate(o["groups"][:a.max_groups]):
                rr = res[(g[0], o["image"])]
                tail = (f" +{len(o['groups'])-a.max_groups}군집"
                        if k == a.max_groups - 1 and len(o["groups"]) > a.max_groups else "")
                put(cv_, (k + 1) * CELL, y0, ov_img(run, o["image"], a.target, g[0]),
                    [f"n={len(g)}  {' '.join(g[:3])}{'…' if len(g) > 3 else ''}{tail}",
                     f"a{rr.get('area_frac',0):.2f} {'OK' if rr.get('ok') else str(rr.get('why'))[:16]}",
                     prm[g[0]][:46]], GRN if rr.get("ok") else RED)
        q = sd / f"diff_p{pi:02d}.png"
        cv2.imwrite(str(q), cv_)
        print(f"  {q}  {cv_.shape[1]}x{cv_.shape[0]}  ({len(page)}장)")

    L = [f"# 프롬프트가 갈린 이미지 — 시트 읽는 법", "",
         f"{len(stems)}장 중 **{c.get(1,0)}장은 {len(slugs)}개가 같은 마스크**를 냈다(IoU ≥{a.iou}). "
         f"판단 근거가 있는 것은 **갈린 {len(diff)}장**뿐이라 그것만 시트로 냈다.", "",
         "- 행 하나 = 이미지. 맨 왼쪽 파란 테두리가 원본, 오른쪽이 서로 다른 마스크 군집.",
         "- `n=44` = 그 마스크를 낸 프롬프트가 44개라는 뜻.",
         "- 🔴 **다수결이 정답이 아니다.** 소수 군집이 맞는 경우를 보라고 만든 시트다"
         " (실측: 접전 ≤47/68 에서 다수가 틀린 사례 5건, 압도 ≥50/68 에서는 60/60 다수가 옳았다).",
         "- 초록 = 형상 휴리스틱 통과 / 빨강 = 탈락. ⚠️ 통과가 «맞다» 는 뜻은 아니다.", "",
         "판정하려면:", "",
         "```bash",
         f"envs/pose/bin/python tools/prompt_sweep_diff.py check --run {a.run} \\",
         '    --page 1 --picks "3;2;2,3,4;2;…"      # 칸1=원본이므로 «2번째»=군집1',
         "```", "", "## slug ↔ 프롬프트", "", "| slug | 프롬프트 |", "|---|---|"]
    used = sorted({s for o in diff for g in o["groups"] for s in g})
    L += [f"| `{s}` | `{prm[s]}` |" for s in used]
    L += ["", "## 이미지별 군집 구성", ""]
    for o in diff:
        L.append(f"**{o['image']}** — 군집 {len(o['groups'])}개")
        L += [f"  {k}. n={len(g)} : {' '.join(g)}" for k, g in enumerate(o["groups"], 1)]
        L.append("")
    (sd / "LEGEND.md").write_text("\n".join(L))
    print(f"\n→ {sd}/LEGEND.md · {sd}/clusters.json")
    return 0


# ── ② check ─────────────────────────────────────────────────────────────────────
def cmd_check(a) -> int:
    run, sd = Path(a.run), Path(a.run) / "diff"
    d, rows, slugs, stems = load_run(run, a.target)
    res = {(r["slug"], r["image"]): r for r in rows}
    prm = prompt_map(rows)
    cl = json.load(open(sd / "clusters.json"))
    diff = sorted([o for o in cl if len(o["groups"]) > 1], key=lambda o: -len(o["groups"]))
    page = diff[(a.page - 1) * a.rows: a.page * a.rows]
    picks = [[int(x) for x in tok.split(",")] for tok in a.picks.split(";") if tok.strip()]
    if len(picks) != len(page):
        print(f"🔴 판정 {len(picks)}개 ≠ 그 페이지의 행 {len(page)}개 — 시트를 다시 확인할 것")
        return 2

    imgdir = Path(a.imgs) if a.imgs else None
    cols = 1 + max(len(p) for p in picks)
    cv_ = np.full((HDR + len(page) * (CELL + LAB), cols * CELL, 3), 24, np.uint8)
    cv2.rectangle(cv_, (0, 0), (cols * CELL, HDR - 6), (50, 140, 50), -1)
    cv2.putText(cv_, f"확인용 — diff_p{a.page:02d} 에서 «정답» 이라 하신 칸만 모았다 "
                     "(칸1=원본이므로 «2번째»=군집1)",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255,) * 3, 2, cv2.LINE_AA)
    lab = {}
    for r, (o, pk) in enumerate(zip(page, picks)):
        stem = o["image"]
        y0 = HDR + r * (CELL + LAB)
        put(cv_, 0, y0, orig_img(imgdir, stem) if imgdir else None,
            [f"{(a.page-1)*a.rows+r+1}번 {stem[:30]}",
             f"군집 {len(o['groups'])}개 · 선택 {pk}"], BLU)
        sel = []
        for k, cell in enumerate(pk):
            gi = cell - 2
            if not 0 <= gi < len(o["groups"]):
                print(f"🔴 {stem}: 칸 {cell} 은 군집 {len(o['groups'])}개 범위 밖")
                return 2
            g = o["groups"][gi]
            sel += g
            rr = res[(g[0], stem)]
            put(cv_, (k + 1) * CELL, y0, ov_img(run, stem, a.target, g[0]),
                [f"선택 {cell}번째 = 군집{gi+1}  n={len(g)}",
                 f"a{rr.get('area_frac',0):.2f}  {' '.join(g[:3])}{'…' if len(g)>3 else ''}",
                 prm[g[0]][:46]], GRN)
        lab[stem] = {"page": a.page, "row": r + 1, "picked_cells": pk,
                     "correct_slugs": sorted(set(sel)), "n_masks": o["n"],
                     "n_groups": len(o["groups"]),
                     "cluster_sizes": [len(g) for g in o["groups"]]}
    q = sd / f"CHECK_selected_p{a.page:02d}.png"
    cv2.imwrite(str(q), cv_)

    ap = sd / "human_labels.json"
    acc = json.loads(ap.read_text()) if ap.exists() else {
        "_note": ("육안 판정. 칸1=원본이므로 «2번째»=군집1. 🔴 이 데이터에 붙은 유일한 사람 라벨 — "
                  "프롬프트 서열화의 GT 대용이다. `correct_slugs` = 그 이미지에서 «맞는» 마스크를 낸 프롬프트."),
        "_source": str(run), "labels": {}}
    acc["labels"].update(lab)
    acc["_pages_done"] = sorted({v["page"] for v in acc["labels"].values()})
    acc["_n_images"] = len(acc["labels"])
    ap.write_text(json.dumps(acc, ensure_ascii=False, indent=1))
    print(f"→ {q}\n→ {ap}  (누적 {acc['_n_images']}장 · 페이지 {acc['_pages_done']})")
    for s, v in lab.items():
        print(f"   {v['row']:2d}. {s:40s} 칸{v['picked_cells']} → 군집크기{v['cluster_sizes']}"
              f" → 정답 {len(v['correct_slugs'])}개")
    return 0


# ── ③ rank ──────────────────────────────────────────────────────────────────────
def cmd_rank(a) -> int:
    from scipy.stats import rankdata
    run, sd = Path(a.run), Path(a.run) / "diff"
    d, rows, slugs, stems = load_run(run, a.target)
    prm = prompt_map(rows)
    lab = json.loads((sd / "human_labels.json").read_text())["labels"]
    labeled = [s for s in stems if s in lab]
    rest = [s for s in stems if s not in lab]
    print(f"사람 라벨 {len(labeled)}장 · 라벨 없음 {len(rest)}장")

    # ⓐ 라벨 있는 이미지 — 사람이 승인한 마스크와 IoU ≥ thr
    ok_h = {s: 0 for s in slugs}
    for stem in labeled:
        ref = [m for g in lab[stem]["correct_slugs"]
               if (m := load_mask(run, stem, a.target, g)) is not None]
        if not ref:
            continue
        for s in slugs:
            m = load_mask(run, stem, a.target, s)
            if m is None:
                continue
            if max(float(np.count_nonzero(m & r)) / max(np.count_nonzero(m | r), 1)
                   for r in ref) >= a.iou:
                ok_h[s] += 1

    # ⓑ 라벨 없는 이미지 — «자기를 뺀 나머지의 과반과 합의하는가» (leave-one-out 내장)
    ok_c = {s: 0 for s in slugs}
    for stem in rest:
        ms = [load_mask(run, stem, a.target, s) for s in slugs]
        idx = [i for i, m in enumerate(ms) if m is not None]
        if len(idx) < 2:
            continue
        M = iou_matrix(np.array([ms[i] for i in idx])) >= a.iou
        np.fill_diagonal(M, False)
        need = (len(slugs) - 1) / 2          # 🔴 미검출도 «동의 안 함» 으로 센다
        for k, i in enumerate(idx):
            if M[k].sum() > need:
                ok_c[slugs[i]] += 1

    out = [{"slug": s, "prompt": prm[s], "ok_human": ok_h[s], "n_human": len(labeled),
            "ok_consensus": ok_c[s], "n_consensus": len(rest),
            "ok_total": ok_h[s] + ok_c[s]} for s in slugs]
    key = (lambda r: -r["ok_total"]) if a.combine == "sum" else (lambda r: -r["ok_human"])
    out.sort(key=lambda r: (key(r), -r["ok_human"], r["slug"]))
    rk = rankdata([key(r) for r in out], method="average")
    for r, k in zip(out, rk):
        r["rank"] = float(k)

    print(f"\n서열 ({'237식 합산' if a.combine=='sum' else '사람 라벨만'}) — 상위 12")
    for r in out[:12]:
        print(f"  {r['rank']:5.1f}. 사람 {r['ok_human']:3d}/{r['n_human']:<3d} · "
              f"합의 {r['ok_consensus']:3d}/{r['n_consensus']:<3d}  `{r['prompt']}`")
    (sd / "ranking.json").write_text(json.dumps(
        {"_note": "`ok_human` = 사람 라벨(정본) · `ok_consensus` = 라벨 없는 이미지에서 "
                  "«나머지의 과반과 합의»(대리). 🔴 자가 다른 두 수다 — 어긋나면 `ok_human` 을 믿는다.",
         "_combine": a.combine, "_iou": a.iou, "rows": out}, ensure_ascii=False, indent=1))
    md = [f"# 프롬프트 서열 — `{run.name}`", "",
          f"- `사람` = 갈린 {len(labeled)}장에서 **직접 판정**한 통과 수 (**가장 믿을 수 있는 수**)",
          f"- `합의` = 나머지 {len(rest)}장에서 «자기를 뺀 나머지의 과반과 합의하는가» (사람 라벨 없음)",
          "- 🔴 **자가 다른 두 수다.** 어긋나면 `사람` 을 믿는다 — 라벨 없는 쪽은 «전원 동일» 이라",
          "  천장에 눌려 변별력이 낮다(교훈 #103).", "",
          "| 순위 | 사람 | 합의 | 합 | slug | 프롬프트 |", "|---:|---:|---:|---:|---|---|"]
    md += [f"| {r['rank']:.0f} | {r['ok_human']}/{r['n_human']} | "
           f"{r['ok_consensus']}/{r['n_consensus']} | **{r['ok_total']}** | `{r['slug']}` | "
           f"`{r['prompt']}` |" for r in out]
    dst = Path(a.md_out) if a.md_out else sd / "RANKING.md"
    dst.write_text("\n".join(md) + "\n")
    print(f"\n→ {sd}/ranking.json\n→ {dst}")
    return 0


# ── ④ slugs — 「통과한 프롬프트의 slug 만」 뽑는다 ────────────────────────────────
def cmd_slugs(a) -> int:
    """`report.md` 에는 프롬프트 전문만 있고 slug 이 없다. 다음 라운드에 그대로 먹일 수 있게
    **slug 목록 txt** 와 (선택) **`--prompts-json` 으로 바로 쓸 부분집합 json** 을 낸다."""
    run = Path(a.run)
    d, rows, slugs, stems = load_run(run, a.target)
    prm = prompt_map(rows)
    ok = collections.Counter(r["slug"] for r in rows if r.get("ok"))
    seen = collections.Counter(r["slug"] for r in rows)
    need = len(stems) if a.min_pass is None else a.min_pass
    keep = [s for s in slugs if ok[s] >= need]
    # 정렬 = 통과 수 → score 최소값(= 미검출까지의 여유) 내림차순.
    # 🔴 `score` 는 품질이 아니라 «필요한 문턱» 이다(교훈 #90·#100) — 이 순서를 서열로 읽지 말 것.
    smin = {s: min((r.get("score", 0.0) for r in rows if r["slug"] == s), default=0.0)
            for s in keep}
    keep.sort(key=lambda s: (-ok[s], -smin[s], s))
    print(f"이미지 {len(stems)}장 · 프롬프트 {len(slugs)}개 → **{need}장 이상 통과 {len(keep)}개**")
    for s in keep[:10]:
        print(f"   {s}  {ok[s]}/{seen[s]}  score최소 {smin[s]:.3f}  `{prm[s]}`")
    if len(keep) > 10:
        print(f"   … 그 외 {len(keep)-10}개")

    out = Path(a.out) if a.out else run / f"pass_slugs_{a.target}.txt"
    body = "\n".join(f"{s}\t{ok[s]}/{seen[s]}\t{smin[s]:.3f}\t{prm[s]}" for s in keep) \
        if a.with_prompt else "\n".join(keep)
    out.write_text(body + "\n")
    print(f"\n→ {out}  ({len(keep)}줄"
          + (", `slug<TAB>통과<TAB>score최소<TAB>프롬프트`)" if a.with_prompt else ")"))
    if a.json_out:
        src = json.load(open(a.src_json)) if a.src_json else None
        if src:
            cat = {x[0]: x[1] for x in src[a.target]}
            meta = {x[0]: (x[3] if len(x) > 3 else {}) for x in src[a.target]}
        else:
            cat, meta = {}, {}
        items = [[s, cat.get(s, "?"), prm[s],
                  dict(meta.get(s, {}), pass_real=f"{ok[s]}/{seen[s]}")] for s in keep]
        Path(a.json_out).write_text(json.dumps(
            {"_note": f"`{run}` 에서 {need}장 이상 통과한 {len(keep)}개. "
                      "🔴 **형상 휴리스틱 통과이지 «맞다» 가 아니다** — 서열은 육안 판정으로 낸다"
                      "(교훈 #90·#100·§39-11d).",
             "_from": str(run), a.target: items}, ensure_ascii=False, indent=1))
        print(f"→ {a.json_out}  (다음 라운드에 `--prompts-json` 으로 그대로)")
    if not a.min_pass and len(keep) > 8:
        print(f"\n⚠️ **{len(keep)}개는 pose 팔로 걸기엔 많다** — 팔 ≥8 이면 선택 편향 경고(§35-2o-4).")
    print("🔴 «전 이미지 통과» 는 1등의 근거가 못 된다 — 웹 실측에서 그런 프롬프트가 사람 기준 92위였다.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("sheets", cmd_sheets), ("check", cmd_check), ("rank", cmd_rank),
                     ("slugs", cmd_slugs)):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True, help="스윕 산출 디렉토리 (`--out` 으로 준 것)")
        p.add_argument("--target", default="full", choices=["full", "flange"])
        p.add_argument("--iou", type=float, default=IOU, help="«같은 마스크» 판정 문턱")
        p.add_argument("--imgs", default=None, help="원본 이미지 디렉토리 (시트 맨 왼쪽 칸)")
        p.add_argument("--rows", type=int, default=12, help="시트 한 장당 이미지 수")
        p.set_defaults(fn=fn)
        if name == "sheets":
            p.add_argument("--max-groups", type=int, default=8, help="한 행에 그릴 군집 상한")
        if name == "check":
            p.add_argument("--page", type=int, required=True)
            p.add_argument("--picks", required=True,
                           help='행별 «정답» 칸. 예 "3;2;2,3,4;2" — 칸1=원본이므로 2번째=군집1')
        if name == "rank":
            p.add_argument("--combine", default="sum", choices=["sum", "human"],
                           help="sum = 사람+합의 (전체 표본) · human = 사람 라벨만")
            p.add_argument("--md-out", default=None, help="표를 `runs/` 밖으로 뺄 경로")
        if name == "slugs":
            p.add_argument("--min-pass", type=int, default=None,
                           help="이 장수 이상 통과한 것만. 기본은 **전 이미지 통과**")
            p.add_argument("--out", default=None, help="txt 경로 (기본 `<run>/pass_slugs_<target>.txt`)")
            p.add_argument("--with-prompt", action="store_true",
                           help="`slug<TAB>통과<TAB>score최소<TAB>프롬프트` 로 (기본은 slug 만)")
            p.add_argument("--json-out", default=None,
                           help="다음 라운드에 `--prompts-json` 으로 먹일 부분집합 json")
            p.add_argument("--src-json", default="assets/prompts/real_testset.json",
                           help="--json-out 에 범주·메타를 물려줄 원본")
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
