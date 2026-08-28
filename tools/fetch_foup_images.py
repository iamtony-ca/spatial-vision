#!/usr/bin/env python3
"""웹에서 FOUP 사진을 긁어 모은다 — SAM3 텍스트 프롬프트 스윕용 «눈으로 추릴» 표본 확보.

왜 필요한가
    `assets/real_imgs/` 의 9장으로 프롬프트 8차까지 돌렸는데, 9장이 **전부 흰 배경 단일 물체**라
    「오선택」 축을 원리적으로 못 잰다(§37-13 `_limit`). 배경·조명·제조사·시점이 흩어진 표본이
    있어야 *"FOUP 주변에 다른 사물이 있을 때"* 를 프롬프트가 견디는지 볼 수 있다.

무엇을 하나
    DuckDuckGo 이미지 검색을 질의별로 훑어 후보 URL 을 모으고, 내려받아 **디코드 가능 + 최소 크기**
    를 통과한 것만 남긴다. 중복은 세 겹으로 거른다 — URL · 내용 sha256 · **dHash 근사 중복**
    (같은 사진이 사이트마다 크기만 달라 재게시되는 일이 흔하다). 기존 `assets/real_imgs/` 의
    사진과도 대조해 이미 가진 것은 다시 받지 않는다.

    ⚠️ **내려받은 것이 전부 FOUP 이라는 보장은 없다** — 검색엔진이 로드포트·스토커·웨이퍼·
    로고 이미지도 섞어 준다. 그래서 이 도구는 **거르지 않고** 컨택트 시트를 내고, 추리는 것은
    사람의 눈에 맡긴다(`--sheet`). 지우기 쉽도록 manifest 에 파일명 → 출처를 남긴다.

    ⚠️ 저작권 — 받은 사진은 **사내 실험 표본**이고 재배포 대상이 아니다. 출처 URL 을 전부
    `manifest.json` 에 남겨 추적 가능하게 한다. `.gitignore` 대상인지 확인할 것.

인터프리터
    `envs/pose/bin/python` (cv2 + numpy 만 쓴다)

예
    envs/pose/bin/python tools/fetch_foup_images.py --out assets/real_imgs/web
    envs/pose/bin/python tools/fetch_foup_images.py --out assets/real_imgs/web --sheet-only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# ── 질의 목록 ────────────────────────────────────────────────────────────────
# 축을 셋으로 나눠 놓는다: ① 총칭·규격 ② 제조사 ③ 시점·맥락·외관.
# ③이 가장 중요하다 — 기존 9장에 없는 «배경 있는 사진» 이 거기서 나온다.
QUERIES: list[tuple[str, str]] = [
    # ① 총칭 · 규격
    ("generic", "FOUP"),
    ("generic", "FOUP wafer carrier"),
    ("generic", "front opening unified pod"),
    ("generic", "front opening unified pod semiconductor"),
    ("generic", "300mm FOUP"),
    ("generic", "300mm wafer carrier pod"),
    ("generic", "semiconductor wafer pod"),
    ("generic", "wafer cassette pod semiconductor"),
    ("generic", "SEMI E47.1 FOUP"),
    ("generic", "FOUP 웨이퍼 캐리어"),
    ("generic", "FOUP ウェーハキャリア"),
    ("generic", "晶圆盒 FOUP"),

    # ② 제조사
    ("vendor", "Entegris FOUP"),
    ("vendor", "Entegris A300 FOUP"),
    ("vendor", "Shin-Etsu Polymer FOUP"),
    ("vendor", "Miraial FOUP"),
    ("vendor", "Gudeng FOUP"),
    ("vendor", "Brooks FOUP wafer carrier"),
    ("vendor", "3S Korea FOUP"),
    ("vendor", "Chung King Enterprise FOUP"),

    # ③ 시점 · 맥락 · 외관  ← 배경이 있는 사진이 여기서 나온다
    ("context", "FOUP top flange"),
    ("context", "FOUP robotic handling flange"),
    ("context", "FOUP OHT overhead hoist transport"),
    ("context", "FOUP load port"),
    ("context", "FOUP on load port equipment"),
    ("context", "FOUP stocker AMHS"),
    ("context", "FOUP semiconductor fab cleanroom"),
    ("context", "FOUP opener door"),
    ("context", "FOUP cleaning machine"),
    ("context", "FOUP transport robot"),
    ("context", "wafer FOUP inside cleanroom"),
    ("appearance", "transparent FOUP wafer carrier"),
    ("appearance", "orange FOUP wafer carrier"),
    ("appearance", "black FOUP wafer carrier"),
    ("appearance", "clear polycarbonate wafer pod"),
]

MIN_SIDE = 300          # 짧은 변 하한 (px)
MAX_BYTES = 25 << 20    # 25MB — 웹에 있는 사고성 대용량 파일 차단
DHASH_DIST = 5          # 이하면 «같은 사진» 으로 본다


# ── 유틸 ─────────────────────────────────────────────────────────────────────
def _slug(s: str, n: int = 28) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:n].strip("-")


def _get(url: str, timeout: int = 25, referer: str | None = None) -> bytes:
    hdr = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        hdr["Referer"] = referer
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(MAX_BYTES + 1)


def dhash(img: np.ndarray, size: int = 8) -> int:
    """인접 픽셀 밝기 비교로 64bit 해시. 크기·재압축에 둔감해 재게시본을 잡는다."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = cv2.resize(g, (size + 1, size), interpolation=cv2.INTER_AREA)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ── 검색 ─────────────────────────────────────────────────────────────────────
def ddg_images(query: str, want: int, pause: float = 0.6) -> list[dict]:
    """DuckDuckGo 이미지 검색. vqd 토큰을 먼저 받고 i.js 를 페이지네이션한다."""
    q = urllib.parse.quote(query)
    try:
        html = _get(f"https://duckduckgo.com/?q={q}&iax=images&ia=images").decode("utf8", "ignore")
    except Exception as e:                                   # noqa: BLE001
        print(f"   🔴 vqd 실패 [{query}] {type(e).__name__}: {e}")
        return []
    m = re.search(r'vqd=["\']?([\d-]+)', html)
    if not m:
        print(f"   🔴 vqd 토큰 없음 [{query}] — 엔진이 형식을 바꿨을 수 있다")
        return []
    vqd = m.group(1)

    out, seen, nxt = [], set(), f"/i.js?l=us-en&o=json&q={q}&vqd={vqd}&f=,,,&p=1"
    while nxt and len(out) < want:
        try:
            d = json.loads(_get("https://duckduckgo.com" + nxt,
                                referer="https://duckduckgo.com/"))
        except Exception as e:                               # noqa: BLE001
            print(f"   ⚠️ 페이지 실패 [{query}] {type(e).__name__}: {e}")
            break
        for r in d.get("results", []):
            u = r.get("image")
            if not u or u in seen:
                continue
            seen.add(u)
            out.append({"image": u, "page": r.get("url", ""), "title": r.get("title", ""),
                        "w": r.get("width", 0), "h": r.get("height", 0)})
        nxt = d.get("next")
        if nxt and not nxt.startswith("/"):
            nxt = "/" + nxt
        time.sleep(pause)
    return out[:want]


# ── 본체 ─────────────────────────────────────────────────────────────────────
def build_known(dirs: list[Path]) -> tuple[set[str], list[int]]:
    """이미 가진 사진의 sha256 · dHash. 재수집 방지용."""
    shas, hashes = set(), []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                continue
            b = p.read_bytes()
            img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            shas.add(hashlib.sha256(b).hexdigest())
            hashes.append(dhash(img))
    return shas, hashes


def fetch_one(item: dict) -> dict | None:
    try:
        b = _get(item["image"], timeout=20, referer=item.get("page") or None)
    except Exception as e:                                   # noqa: BLE001
        item["error"] = f"{type(e).__name__}"
        return None
    if len(b) > MAX_BYTES:
        item["error"] = "too-large"
        return None
    img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        item["error"] = "decode"
        return None
    h, w = img.shape[:2]
    if min(h, w) < MIN_SIDE:
        item["error"] = f"small-{w}x{h}"
        return None
    item.update(bytes_=b, W=w, H=h,
                sha256=hashlib.sha256(b).hexdigest(), dhash=dhash(img))
    return item


def ext_of(url: str, blob: bytes) -> str:
    if blob[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return ".webp"
    e = Path(urllib.parse.urlparse(url).path).suffix.lower()
    return e if e in {".jpg", ".jpeg", ".png", ".webp", ".bmp"} else ".jpg"


def load_blocklist(out: Path) -> tuple[set[str], list[int]]:
    """육안 검수에서 버린 사진의 해시. **파일을 지웠으므로 이것 없이는 다시 받아 온다.**"""
    p = out / "rejected.json"
    if not p.exists():
        return set(), []
    rows = json.loads(p.read_text()).get("rejected", {})
    return ({v["sha256"] for v in rows.values()},
            [int(v["dhash"], 16) for v in rows.values()])


def rebuild_manifest(out: Path, queries, per_query: int, workers: int) -> int:
    """검색을 다시 돌려 **이미 가진 파일의 출처 URL 을 해시로 역추적**한다.

    🔴 왜 필요한가 — 수집이 중간에 끊기면 대장이 안 쓰인 채 사진만 남는다. 그러면
       «다른 PC 에서 같은 이미지를 받는다» 가 불가능해진다. 내용 해시로 되짚으면 복구된다.
    """
    files = [p for p in sorted(out.iterdir())
             if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}]
    by_sha, by_dh = {}, {}
    for p in files:
        b = p.read_bytes()
        img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        by_sha[hashlib.sha256(b).hexdigest()] = p.name
        by_dh[dhash(img)] = p.name

    mf_path = out / "manifest.json"
    manifest = json.loads(mf_path.read_text()) if mf_path.exists() else {}
    print(f"== 대장 복구 | 대상 {len(files)}장 · 기록된 것 "
          f"{sum(1 for k in manifest if not k.startswith('_'))}장")

    for gi, (group, q) in enumerate(queries, 1):
        cands = ddg_images(q, per_query)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            got = [g for g in ex.map(fetch_one, cands) if g]
        hit = 0
        for it in got:
            name = by_sha.get(it["sha256"])
            if not name:                       # 재압축본이면 sha 가 다르다 → dHash 로
                for h, n in by_dh.items():
                    if hamming(it["dhash"], h) <= DHASH_DIST:
                        name = n
                        break
            if not name or name in manifest:
                continue
            manifest[name] = {"query": q, "group": group, "image_url": it["image"],
                              "source_page": it["page"], "title": it["title"],
                              "w": it["W"], "h": it["H"], "sha256": it["sha256"],
                              "dhash": f"{it['dhash']:016x}", "bytes": len(it["bytes_"]),
                              "sha_exact": it["sha256"] in by_sha}
            hit += 1
        done = sum(1 for k in manifest if not k.startswith("_"))
        print(f"   [{gi:2d}/{len(queries)}] {q:44s} +{hit:3d} → 누적 {done}/{len(files)}",
              flush=True)
        mf_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))

    done = sum(1 for k in manifest if not k.startswith("_"))
    lost = [p.name for p in files if p.name not in manifest]
    manifest["_note"] = ("웹 수집 FOUP 사진의 출처 대장. **사내 실험 표본이고 재배포 대상이 아니다.** "
                         "다른 PC 에서 같은 표본을 만들려면 `--restore` 로 이 대장을 재생한다.")
    if lost:
        manifest["_unresolved"] = lost
    mf_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"\n✅ 출처 확보 {done}/{len(files)}장 → {mf_path}")
    if lost:
        print(f"   🔴 URL 미복구 {len(lost)}장 — 검색 순위가 바뀌어 후보에 안 나온 것들이다. "
              f"`--per-query` 를 키워 다시 돌리면 일부 회수된다. 목록은 `_unresolved`.")
    return 0


def restore(out: Path, workers: int) -> int:
    """`manifest.json` 만 들고 다른 PC 에서 같은 표본을 재생한다. sha256 로 검증한다."""
    mf_path = out / "manifest.json"
    if not mf_path.exists():
        print(f"🔴 대장이 없다: {mf_path}")
        return 2
    manifest = json.loads(mf_path.read_text())
    rows = {k: v for k, v in manifest.items() if not k.startswith("_")}
    out.mkdir(parents=True, exist_ok=True)
    print(f"== 표본 복원 | 대장 {len(rows)}장 → {out}")

    todo = [(k, v) for k, v in rows.items() if not (out / k).exists()]
    print(f"   이미 있는 것 {len(rows) - len(todo)}장 · 받을 것 {len(todo)}장")

    def one(kv):
        name, v = kv
        try:
            b = _get(v["image_url"], timeout=20, referer=v.get("source_page") or None)
        except Exception as e:                               # noqa: BLE001
            return name, f"dead:{type(e).__name__}"
        sha = hashlib.sha256(b).hexdigest()
        if sha != v["sha256"]:
            # 사이트가 재압축했을 수 있다 → dHash 로 «같은 사진인가» 만 본다
            img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
            if img is None or hamming(dhash(img), int(v["dhash"], 16)) > DHASH_DIST:
                return name, "changed"
            (out / name).write_bytes(b)
            return name, "near"
        (out / name).write_bytes(b)
        return name, "ok"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(one, todo))
    tally: dict[str, int] = {}
    for _, st in res:
        tally[st.split(":")[0]] = tally.get(st.split(":")[0], 0) + 1
    print(f"\n✅ 복원 결과: {tally}")
    bad = [n for n, st in res if st.startswith("dead") or st == "changed"]
    if bad:
        (out / "restore_failed.json").write_text(
            json.dumps({n: st for n, st in res if n in set(bad)}, ensure_ascii=False, indent=1))
        print(f"   🔴 실패 {len(bad)}장 → {out / 'restore_failed.json'} "
              f"(링크가 죽었거나 내용이 바뀌었다. 원본 PC 에서 파일로 옮겨야 한다.)")
    return 0


def contact_sheets(out: Path, cols: int = 6, cell: int = 260, rows: int = 6) -> list[Path]:
    """받은 사진 전부를 격자로. **거르지 않고 다 그린다** — 추리는 것은 사람 몫이다."""
    files = sorted(p for p in out.iterdir()
                   if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"})
    if not files:
        return []
    sd = out / "sheets"
    sd.mkdir(exist_ok=True)
    for p in sd.glob("contact_p*.png"):
        p.unlink()
    per, made = cols * rows, []
    for pi in range(0, len(files), per):
        chunk = files[pi:pi + per]
        nr = (len(chunk) + cols - 1) // cols
        lab = 22
        canvas = np.full((nr * (cell + lab), cols * cell, 3), 32, np.uint8)
        for i, f in enumerate(chunk):
            img = cv2.imdecode(np.frombuffer(f.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            h, w = img.shape[:2]
            s = cell / max(h, w)
            img = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))))
            r, c = divmod(i, cols)
            y0, x0 = r * (cell + lab), c * cell
            yo, xo = (cell - img.shape[0]) // 2, (cell - img.shape[1]) // 2
            canvas[y0 + yo:y0 + yo + img.shape[0], x0 + xo:x0 + xo + img.shape[1]] = img
            cv2.putText(canvas, f.stem[:34], (x0 + 3, y0 + cell + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (210, 210, 210), 1, cv2.LINE_AA)
        q = sd / f"contact_p{pi // per + 1}.png"
        cv2.imwrite(str(q), canvas)
        made.append(q)
    return made


def main() -> int:
    global MIN_SIDE
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="assets/real_imgs/web", help="받을 디렉토리")
    ap.add_argument("--per-query", type=int, default=60, help="질의당 후보 수")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--min-side", type=int, default=MIN_SIDE)
    ap.add_argument("--dedupe-against", nargs="*", default=["assets/real_imgs"],
                    help="이미 가진 사진 디렉토리 (재수집 방지)")
    ap.add_argument("--queries-file", help="질의를 JSON 으로 교체 ([[group, query], …])")
    ap.add_argument("--sheet-only", action="store_true", help="받지 않고 컨택트 시트만 다시 그린다")
    ap.add_argument("--sheet-cols", type=int, default=6)
    ap.add_argument("--sheet-rows", type=int, default=6)
    ap.add_argument("--sheet-cell", type=int, default=260)
    ap.add_argument("--rebuild-manifest", action="store_true",
                    help="검색을 다시 돌려 이미 가진 파일의 출처 URL 을 해시로 역추적한다")
    ap.add_argument("--restore", action="store_true",
                    help="manifest.json 만 들고 같은 표본을 재생한다 (다른 PC 용)")
    a = ap.parse_args()

    MIN_SIDE = a.min_side
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    if a.sheet_only:
        made = contact_sheets(out, cols=a.sheet_cols, cell=a.sheet_cell, rows=a.sheet_rows)
        print(f"✅ 컨택트 시트 {len(made)}장 → {out / 'sheets'}")
        return 0

    if a.restore:
        return restore(out, a.workers)

    queries = QUERIES
    if a.queries_file:
        queries = [tuple(x) for x in json.loads(Path(a.queries_file).read_text())]

    if a.rebuild_manifest:
        return rebuild_manifest(out, queries, a.per_query, a.workers)

    mf_path = out / "manifest.json"
    manifest = json.loads(mf_path.read_text()) if mf_path.exists() else {}
    known_urls = {v["image_url"] for v in manifest.values() if isinstance(v, dict)}

    print(f"== FOUP 이미지 수집 | 질의 {len(queries)} × {a.per_query} | → {out}")
    ext_shas, ext_hashes = build_known([Path(p) for p in a.dedupe_against])
    # 이미 이 폴더에 있는 것도 기준에 넣는다 (재실행 멱등)
    my_shas, my_hashes = build_known([out])
    # 🔴 육안으로 버린 것들은 **파일이 지워져** 대조본에 없다 → 해시 목록으로 막는다
    blk_shas, blk_hashes = load_blocklist(out)
    shas = ext_shas | my_shas | blk_shas
    hashes = ext_hashes + my_hashes + blk_hashes
    print(f"   기존 대조본 {len(shas)}장 (외부 {len(ext_shas)} + 현재 폴더 {len(my_shas)} "
          f"+ 🚫차단 {len(blk_shas)})")

    idx = max([int(m.group(1)) for p in out.iterdir()
               if (m := re.match(r"w(\d{3,})_", p.name))] or [0])
    n_new = 0
    stat: dict[str, int] = {}

    for gi, (group, q) in enumerate(queries, 1):
        cands = [c for c in ddg_images(q, a.per_query) if c["image"] not in known_urls]
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            got = list(ex.map(fetch_one, cands))
        kept = 0
        for it in got:
            known_urls.add((it or {}).get("image", ""))
            if it is None:
                continue
            if it["sha256"] in shas:
                stat["dup-sha"] = stat.get("dup-sha", 0) + 1
                continue
            if any(hamming(it["dhash"], h) <= DHASH_DIST for h in hashes):
                stat["dup-near"] = stat.get("dup-near", 0) + 1
                continue
            idx += 1
            name = f"w{idx:03d}_{_slug(q)}{ext_of(it['image'], it['bytes_'])}"
            (out / name).write_bytes(it["bytes_"])
            shas.add(it["sha256"])
            hashes.append(it["dhash"])
            manifest[name] = {"query": q, "group": group, "image_url": it["image"],
                              "source_page": it["page"], "title": it["title"],
                              "w": it["W"], "h": it["H"], "sha256": it["sha256"],
                              "dhash": f"{it['dhash']:016x}", "bytes": len(it["bytes_"])}
            kept += 1
            n_new += 1
        for it in got:
            if it is None:
                pass
        fails = sum(1 for c in cands if "error" in c)
        print(f"   [{gi:2d}/{len(queries)}] {q:44s} 후보 {len(cands):3d} → +{kept:3d} "
              f"(실패 {fails})", flush=True)
        # 🔴 질의마다 즉시 쓴다 — 끝에 한 번만 쓰면 중간에 끊겼을 때 **출처가 통째로 날아간다**
        #    (실제로 한 번 날렸다). 사진은 남고 대장만 없어져 추적이 불가능해진다.
        mf_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))

    manifest["_note"] = ("웹 수집 FOUP 사진. **사내 실험 표본이고 재배포 대상이 아니다** — "
                         "출처는 각 항목의 source_page. 전부 FOUP 이라는 보장은 없으니 "
                         "sheets/contact_p*.png 로 눈으로 추린 뒤 지운다.")
    mf_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))

    made = contact_sheets(out, cols=a.sheet_cols, cell=a.sheet_cell, rows=a.sheet_rows)
    total = len([p for p in out.iterdir() if p.suffix.lower() in
                 {".jpg", ".jpeg", ".png", ".webp", ".bmp"}])
    print(f"\n✅ 새로 {n_new}장 · 폴더 총 {total}장 → {out}")
    print(f"   중복 제외: {stat}")
    print(f"   컨택트 시트 {len(made)}장 → {out / 'sheets'}")
    print(f"   출처 대장 → {mf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
