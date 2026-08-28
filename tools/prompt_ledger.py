#!/usr/bin/env python3
"""**이미 돌린 SAM3 텍스트 프롬프트 장부** — 흩어진 스윕 결과를 한 파일로 모은다.

    envs/pose/bin/python tools/prompt_ledger.py                       # 갱신 + 요약 출력
    envs/pose/bin/python tools/prompt_ledger.py --check new.json      # 중복만 걸러서 보여준다

왜 필요한가
    프롬프트 스윕을 돌릴 때마다 `runs/<이름>/results.json` 에 결과가 남는데, **어떤 문장을 이미
    시험했는지** 알려면 그 파일들을 매번 다시 훑어야 했다. 새 후보를 짤 때 이미 죽은 문장을
    다시 넣는 낭비가 생기고, 더 나쁘게는 **«안 해봤다» 와 «해봤는데 0/9» 를 헷갈린다.**
    → 장부(`assets/prompts/tested_prompts.json`)를 **정본**으로 두고 여기서 생성한다.

무엇을 기록하나 (프롬프트 × target 마다)
    n_img      몇 장에서 시험했나 (런이 여럿이면 합집합)
    n_pass     그중 형상 판정을 통과한 장 수
    score_med / score_min   ⚠️ **최소값이 중요한 지표**다 — score 는 마스크 품질이 아니라
               `--text-conf` 문턱까지의 «여유» 이고 상관은 r=+0.06 이다(교훈 #90).
    runs       어느 스윕에서 나왔나
    verdict    dead(0장 통과) / partial / perfect(전 장 통과)

🔴 **장부는 «시험했다» 만 말하고 «쓸 만하다» 는 말하지 않는다.** 이 스윕들은 전부
   **단일 물체 사진**이라 «주변 사물 중에서 FOUP 을 고르는가»(오선택)를 **원리적으로 못 쟀다.**
   그 축은 distractor 씬(`capture_sim --distractors`)이나 실물 배치 사진에서만 나온다.
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

VISION = Path(__file__).resolve().parent.parent
LEDGER = VISION / "assets/prompts/tested_prompts.json"
DEFAULT_GLOBS = ("runs/*sweep*/results.json", "runs/psweep*/results.json")


def _rows(f: Path):
    d = json.loads(f.read_text())
    return d["rows"] if isinstance(d, dict) and "rows" in d else d


def _domain(images) -> str:
    """이미지 이름으로 «어느 데이터에서 쟀나» 를 가른다.

    🔴 **도메인을 섞어 합계를 내면 안 된다.** 같은 문장이 웹사진 9/9 인데 sim 검정에서 3/20 인
    일이 실제로 있었고(교훈 #92), 합집합으로 세면 «partial» 한 칸이 되어 **두 사실이 모두 사라진다.**
    """
    return "sim" if all(str(i).startswith(("f0", "frame_")) for i in images) else "web"


def build(patterns) -> dict:
    acc: dict = defaultdict(lambda: {"imgs": set(), "ok": set(), "score": [],
                                     "runs": set(), "slug": None, "cat": None})
    files = sorted({p for g in patterns for p in glob.glob(str(VISION / g))})
    for f in map(Path, files):
        run = f.parent.name
        rows = _rows(f)
        dom = _domain({x.get("image") or x.get("img") for x in rows})
        for x in rows:
            t, p = x.get("target"), x.get("prompt")
            if not t or not p:
                continue
            img = x.get("image") or x.get("img") or "?"
            a = acc[(t, p, dom)]                        # ★ 도메인을 키에 넣는다
            a["imgs"].add(img)
            a["runs"].add(run)
            a["slug"] = a["slug"] or x.get("slug")
            a["cat"] = a["cat"] or x.get("category") or x.get("cat")
            # 🔴 «통과» 판정 키가 스윕 판마다 달랐다 — 둘 다 본다(없으면 미판정으로 둔다).
            if x.get("plausible") or x.get("ok"):
                a["ok"].add(img)
            if x.get("score") is not None:
                a["score"].append(float(x["score"]))

    out = {"_note": "이미 돌린 SAM3 텍스트 프롬프트 장부. `tools/prompt_ledger.py` 가 생성한다 — "
                    "손으로 고치지 말 것. 🔴 «시험했다» 만 말하고 «오선택에 강한가» 는 말하지 않는다 "
                    "(스윕 이미지가 전부 단일 물체다).",
           "_sources": [Path(f).parent.name for f in files],
           "targets": {}}
    for t in sorted({k[0] for k in acc}):
        merged: dict = {}
        for (tt, p, dom), a in acc.items():
            if tt != t:
                continue
            n, k = len(a["imgs"]), len(a["ok"])
            s = a["score"]
            r = merged.setdefault(p, {"prompt": p, "slug": a["slug"], "category": a["cat"],
                                      "by_domain": {}, "runs": set()})
            r["by_domain"][dom] = {
                "n_img": n, "n_pass": k,
                "score_med": round(float(np.median(s)), 3) if s else None,
                "score_min": round(float(min(s)), 3) if s else None,
                "verdict": "perfect" if k == n and n else ("dead" if k == 0 else "partial")}
            r["runs"] |= a["runs"]
        rows = []
        for r in merged.values():
            r["runs"] = sorted(r["runs"])
            # ★ 대표 판정은 **web**(실사진 9장)을 쓴다 — 후보 선정을 그 위에서 하기 때문이다.
            #   sim 성적은 `by_domain.sim` 에 그대로 남는다(교훈 #92: 서열이 도메인을 안 넘는다).
            w = r["by_domain"].get("web") or next(iter(r["by_domain"].values()))
            r |= {k: w[k] for k in ("n_img", "n_pass", "score_med", "score_min", "verdict")}
            rows.append(r)
        rows.sort(key=lambda r: (-(r["n_pass"] / max(r["n_img"], 1)), -(r["score_min"] or 0)))
        out["targets"][t] = rows
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="이미 돌린 SAM3 프롬프트 장부")
    ap.add_argument("--glob", action="append", default=None,
                    help=f"결과 파일 패턴 (기본 {' · '.join(DEFAULT_GLOBS)})")
    ap.add_argument("--out", default=str(LEDGER))
    ap.add_argument("--check", default=None,
                    help="후보 프롬프트 JSON — 장부와 대조해 **이미 돌린 것만** 걸러 보여준다")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)

    led = build(a.glob or DEFAULT_GLOBS)
    if not a.no_write:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(led, indent=2, ensure_ascii=False))

    for t, rows in led["targets"].items():
        v = {k: sum(1 for r in rows if r["verdict"] == k) for k in ("perfect", "partial", "dead")}
        print(f"target={t:<7} 총 {len(rows):3d}개  ·  perfect {v['perfect']:3d} · "
              f"partial {v['partial']:3d} · dead {v['dead']:3d}")
    print(f"{'→' if not a.no_write else '(안 씀)'} {a.out}   "
          f"(스윕 {len(led['_sources'])}건에서 모았다)")

    if a.check:
        raw = json.loads(Path(a.check).read_text())
        # ★ 네 번째 원소(메타)는 버린다 — `sam3_prompt_sweep.py` 와 같은 규약이다.
        cand = {k: [tuple(x[:3]) for x in v] for k, v in raw.items() if not k.startswith("_")}
        for t, items in cand.items():
            done = {r["prompt"]: r for r in led["targets"].get(t, [])}
            dup = [(s, c, p) for s, c, p in items if p in done]
            new = [(s, c, p) for s, c, p in items if p not in done]
            print(f"\n═══ target={t} — 후보 {len(items)}개 · 신규 {len(new)} · **중복 {len(dup)}**")
            for s, c, p in dup:
                r = done[p]
                print(f"  🔴 중복  {p!r}  ← 이미 {r['n_pass']}/{r['n_img']} ({r['verdict']}) "
                      f"in {', '.join(r['runs'])}")
            if dup:
                print("  → 중복은 빼거나, **일부러 재현하려는 것이면 이유를 적어 둔다.**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
