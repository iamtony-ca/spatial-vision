#!/usr/bin/env python3
"""SAM3 **텍스트 프롬프트 스윕** — 실사진에서 어떤 낱말이 통하는가.

    envs/seg_sam3/bin/python tools/sam3_prompt_sweep.py \
        --imgs assets/real_imgs --out runs/promptsweep --target full,flange

왜 필요한가
    T그룹(`run_group_a.py --sam3-text`)은 **참조 자산의 도메인 갭이 원천적으로 없는** 유일한 경로다
    (`RESULTS.md §35-2m-5`). 그런데 그 경로의 성능은 전적으로 «낱말» 이 정한다. sim 에서 고른
    `"black plastic box"` 류가 **실사진에서도 통하는지**는 sim 으로 알 수 없다 — 텍스처·조명·배경이
    전부 다르기 때문이다. 이 스크립트는 그 축만 따로 떼어 잰다.

🔴 이 스윕에는 **GT 가 없다.** 실사진이므로 IoU 를 못 낸다. 그래서 여기 나오는 숫자는 전부
   **GT-free 형상 지표**(면적비·연결성·볼록성·테두리 접촉·중심 위치)이고, 최종 판정은
   **사람이 오버레이를 보고** 한다. 자동 순위는 «후보를 좁히는 도구» 이지 «정답» 이 아니다.

★ 모델을 한 번만 올린다
    ONNX/SAM3 콜드 스타트가 수십 초다(교훈 #9·#76). 이미지 × 프롬프트를 전부 한 프로세스 안에서 돈다.

출력
    <out>/results.csv                       프레임 × 프롬프트 전 지표 (pandas 로 바로)
    <out>/results.json                      같은 내용 + 실행 메타
    <out>/report.md                         읽는 법 + 프롬프트 서열 + 이미지별 최선
    <out>/masks/<img>/<target>/<slug>.png   마스크 (0/255)
    <out>/ov/<img>/<target>/<slug>.png      오버레이 (선택 인스턴스 초록 + 나머지 청록 윤곽)
    <out>/sheets/by_image__<target>__<img>.png    한 이미지 × 전 프롬프트   ← 눈으로 고를 때
    <out>/sheets/by_prompt__<target>__<slug>.png  한 프롬프트 × 전 이미지   ← 일반화 확인
    <out>/sheets/matrix__<target>.png             프롬프트(행) × 이미지(열) 축소판
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np

VISION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VISION_ROOT))

DEFAULT_CKPT = VISION_ROOT / "weights/sam3/sam3.pt"

# ── 프롬프트 목록 ────────────────────────────────────────────────────────────────
# 범주로 묶어 둔다 — «어느 낱말» 보다 «어느 부류의 낱말» 이 통하는가가 이전 가능한 결론이다.
# sim 에서의 관찰(`segment_sam3.py` 주석): 도메인 용어는 conf 0.1 에서도 검출 0.
# 실사진에서도 그런지가 이 스윕의 1번 질문이다.
PROMPTS = {
    "full": [
        # (slug, 범주, 프롬프트)
        ("g_box",            "generic",   "box"),
        ("g_plasticbox",     "generic",   "plastic box"),
        ("g_container",      "generic",   "container"),
        ("g_plasticcont",    "generic",   "plastic container"),
        ("g_case",           "generic",   "case"),
        ("g_crate",          "generic",   "plastic crate"),
        ("g_storagebox",     "generic",   "storage box"),
        ("c_black",          "color",     "black plastic box"),
        ("c_clear",          "color",     "clear plastic box"),
        ("c_transparent",    "color",     "transparent plastic box"),
        ("c_orange",         "color",     "orange plastic box"),
        ("c_white",          "color",     "white plastic box"),
        ("c_translucent",    "color",     "translucent plastic box"),
        ("d_wafercarrier",   "domain",    "wafer carrier"),
        ("d_foup",           "domain",    "FOUP"),
        ("d_fooup_long",     "domain",    "front opening unified pod"),
        ("d_semi",           "domain",    "semiconductor wafer carrier"),
        ("d_cassette",       "domain",    "wafer cassette"),
        ("d_carrierbox",     "domain",    "wafer carrier box"),
        ("s_handlecase",     "descript",  "plastic carrying case with a handle"),
        ("s_industrial",     "descript",  "industrial plastic container"),
        ("s_boxy",           "descript",  "boxy plastic object"),
        ("s_center",         "descript",  "the object in the center"),
        ("s_cube",           "descript",  "cube shaped plastic case"),
        ("s_sidehandle",     "descript",  "square plastic box with a handle on the side"),
        # ── 2차: 1차 결과를 보고 추가한 것들 ──────────────────────────────────
        # 1차에서 (a) 색 지정은 **몸체 색이 맞을 때만** 걸리고 두 톤이면 검정부만 집었다
        # (b) 도메인 용어 중 `front opening unified pod` 만 유일하게 통했다. 그 두 축을 판다.
        ("t_twotone",        "twotone",   "black and white plastic box"),
        ("t_whitedoor",      "twotone",   "plastic box with a white door"),
        ("t_whole",          "twotone",   "the whole box including the transparent parts"),
        ("d_pod",            "domain",    "wafer carrier pod"),
        ("d_reticle",        "domain",    "reticle pod"),
        ("d_shipping",       "domain",    "semiconductor shipping box"),
        ("g_thebox",         "generic",   "the box"),
        ("g_carrying",       "generic",   "carrying box"),
        ("g_lidbox",         "generic",   "plastic box with a lid"),
        ("s_ontable",        "descript",  "large plastic box on the table"),
        ("s_rectangular",    "descript",  "rectangular plastic enclosure"),
    ],
    "flange": [
        ("f_circletop",      "shape",     "circle on top of the box"),      # 현행 기본값
        ("f_blackplate",     "shape",     "black plate on top of the box"),
        ("f_squareplate",    "shape",     "square plate on top of the box"),
        ("f_topplate",       "shape",     "top plate"),
        ("f_crossplate",     "shape",     "cross shaped plate on top"),
        ("f_holetop",        "shape",     "round hole on top of the box"),
        ("f_platehole",      "shape",     "plate with a hole in the middle"),
        ("f_coverhole",      "shape",     "top cover plate with a central hole"),
        ("f_flange",         "domain",    "the flange on top of the box"),
        ("f_robotflange",    "domain",    "robotic handling flange"),
        ("f_kinematic",      "domain",    "kinematic coupling plate"),
        ("f_gripper",        "domain",    "gripper interface plate on top of the container"),
        ("f_lifthandle",     "func",      "lifting handle on top of the box"),
        ("f_lid",            "func",      "lid"),
        ("f_fixture",        "func",      "the black fixture on the top surface"),
        ("f_bracket",        "func",      "black square bracket on top"),
        # ── 2차: 1차 최선(`black square bracket on top`, 9/9)의 주변을 판다 ────
        ("f_platehole2",     "shape",     "black plate with a round hole on top of the box"),
        ("f_squareflange",   "domain",    "square flange"),
        ("f_handling",       "domain",    "handling plate"),
        ("f_robottarget",    "domain",    "robot gripper target plate"),
        ("f_mounting",       "shape",     "top mounting plate with a hole"),
        ("f_holeinplate",    "shape",     "circular hole in a black plate"),
        ("f_blackpart",      "func",      "the black part on top"),
        ("f_couplinglid",    "func",      "coupling plate on the lid"),
    ],
}

# 오버레이 색 (BGR)
C_SEL = (80, 220, 80)      # 선택된 인스턴스
C_OTH = (220, 220, 60)     # 나머지 인스턴스
C_TXT = (255, 255, 255)


# `--ref-full-slug` 기본값. 🔴 «주었는가» 를 판별해야 해서 상수로 뺀다 —
#   `--rebuild-sheets` 는 참조를 재계산하지 못하므로 함께 주면 **막아야** 한다.
PARSER_DEFAULT_REF = "s_boxy,d_fooup_long,s_cube"

def sha8(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:8]


# ── GT-free 형상 지표 ───────────────────────────────────────────────────────────
def mask_metrics(m: np.ndarray) -> dict:
    """마스크 하나의 «생김새» 를 GT 없이 기술한다.

    🔴 어느 값도 «맞다» 를 뜻하지 않는다. 배경을 통째로 집어도 area_frac 은 클 수 있다
       (교훈 #15). 오버레이 육안 확인과 **함께** 읽어야 한다.
    """
    H, W = m.shape
    a = int(m.sum())
    if a == 0:
        return {"area_frac": 0.0, "n_cc": 0, "cc_main_frac": 0.0, "solidity": 0.0,
                "bbox_fill": 0.0, "cx": 0.0, "cy": 0.0, "border_frac": 0.0,
                "bbox": None}
    u8 = m.astype(np.uint8)
    n_lab, lab, stats, cent = cv2.connectedComponentsWithStats(u8, 8)
    areas = stats[1:, cv2.CC_STAT_AREA]
    big = int((areas >= 0.01 * a).sum())          # 1% 미만 파편은 안 센다
    main = float(areas.max()) / a

    ys, xs = np.nonzero(m)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    bbox_fill = a / max((x1 - x0 + 1) * (y1 - y0 + 1), 1)

    cnts, _ = cv2.findContours(u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hull_a = sum(cv2.contourArea(cv2.convexHull(c)) for c in cnts) or 1.0
    solidity = min(a / hull_a, 1.0)

    border = int(m[0].sum() + m[-1].sum() + m[:, 0].sum() + m[:, -1].sum())
    perim = 2 * (H + W)

    return {"area_frac": a / (H * W), "n_cc": big, "cc_main_frac": main,
            "solidity": float(solidity), "bbox_fill": float(bbox_fill),
            "cx": float(xs.mean()) / W, "cy": float(ys.mean()) / H,
            "border_frac": border / perim, "bbox": [x0, y0, x1, y1]}


def ref_region(body: np.ndarray) -> np.ndarray:
    """«몸체 ∪ 몸체 바로 위» — flange 가 있어도 되는 영역.

    🔴 몸체 마스크 자체를 포함 검사에 쓰면 **거짓 기각**이 난다 — `full` 프롬프트가 상면
       플랜지를 몸체로 안 보고 빼 버리는 경우가 실제로 있었다(주황 2장, `in_full` 0.01/0.65).
       flange 는 정의상 몸체 **위로 튀어나온다**. 그래서 «몸체의 x 범위에서, 몸체 최상단보다
       위» 를 허용 영역에 더한다. 옆·앞·아래(문의 링·손잡이)는 여전히 걸린다.
    """
    cols = body.any(axis=0)
    above = (np.cumsum(body, axis=0) == 0) & cols[None, :]
    return body | above


def ref_metrics(m: np.ndarray, body: np.ndarray | None) -> dict:
    """flange 후보를 **물체 기준**으로 기술한다 (이미지 기준이 아니라).

    🔴 초판은 `cy`(이미지 기준 중심 높이)로 «상면인가» 를 판정했는데 **거짓 통과**를 냈다 —
       정면 문의 링, 옆면 손잡이가 전부 통과했다(`top mounting plate with a hole` 9/9 인데
       육안으론 3장이 엉뚱한 것). 물체가 화면 어디에 있느냐에 따라 `cy` 가 아무 뜻이 없다.
       기준을 **`full` 마스크의 bbox** 로 바꾸면 «물체의 위쪽인가» 를 실제로 묻게 된다.
       (`body` 는 같은 이미지의 `full` 프롬프트 여러 개의 합집합 — GT 가 아니라 대리 기준이다.)
    """
    if body is None or not body.any():
        return {"in_region": -1.0, "rel_y": -1.0, "rel_area": -1.0}
    ys, _ = np.nonzero(body)
    y0, y1 = int(ys.min()), int(ys.max())
    a = int(m.sum())
    if a == 0:
        return {"in_region": 0.0, "rel_y": 1.0, "rel_area": 0.0}
    my = np.nonzero(m)[0]
    return {"in_region": float((m & ref_region(body)).sum()) / a,
            "rel_y": float((my.mean() - y0) / max(y1 - y0, 1)),
            "rel_area": a / float(body.sum())}


FULL_AREA = (0.10, 0.92)   # `full` 마스크 면적비 허용 구간. --full-area-min/max 로 바꾼다.
# 🔴 기본값 0.10 은 **흰 배경 단일 물체 9장**(물체가 화면의 ~46%)에 맞춰 잡은 것이다.
#    클린룸·로드포트 전경처럼 FOUP 이 화면의 1~8% 인 사진에서는 **맞게 집은 마스크를 떨어뜨린다**
#    (웹 237장 예비 스윕에서 상위 프롬프트의 «실패» 7장이 전부 이 경우였다).
#    → 배경이 있는 데이터에서는 하한을 낮춰야 한다. 문턱은 **데이터에 딸린 값**이다.


def plausible(target: str, mt: dict, n_inst: int, rm: dict | None = None) -> tuple[bool, str]:
    """«눈으로 볼 값어치가 있는가» 를 거르는 **휴리스틱**. 순위가 아니라 필터다.

    ⚠️ 통과 = 맞다가 아니다. 떨어진 것 중에 맞는 게 있을 수 있으니 오버레이는 전부 저장한다.
    🔴 사유 문자열은 **영문**이다 — 오버레이 배너를 `cv2.putText` 로 그리는데 한글 폰트가 없어
       한글을 넣으면 `??????` 로 깨진다(`viz.dim_sheet` 와 같은 제약). 뜻은 report.md 에 적는다.
    """
    if n_inst == 0:
        return False, "no detection"
    if target == "full":
        if not (FULL_AREA[0] <= mt["area_frac"] <= FULL_AREA[1]):
            return False, f"area {mt['area_frac']:.3f}"
        if mt["cc_main_frac"] < 0.80:
            return False, f"fragmented cc_main {mt['cc_main_frac']:.2f}"
        if mt["solidity"] < 0.70:
            return False, f"solidity {mt['solidity']:.2f}"
        if mt["border_frac"] > 0.55:
            return False, f"border {mt['border_frac']:.2f} (background?)"
    else:
        if not (0.001 <= mt["area_frac"] <= 0.30):
            return False, f"area {mt['area_frac']:.4f}"
        if mt["cc_main_frac"] < 0.55:
            return False, f"fragmented cc_main {mt['cc_main_frac']:.2f}"
        if rm and rm["in_region"] >= 0.0:
            # ★ 물체 기준 — 여기가 거짓 통과를 막는 곳이다.
            if rm["in_region"] < 0.80:
                return False, f"in_region {rm['in_region']:.2f} (off body/top)"
            if rm["rel_y"] > 0.28:
                return False, f"rel_y {rm['rel_y']:.2f} (not upper part)"
            if not (0.004 <= rm["rel_area"] <= 0.30):
                return False, f"rel_area {rm['rel_area']:.3f}"
        elif mt["cy"] > 0.62:                      # ← 기준 마스크가 없을 때의 약한 대체
            return False, f"cy {mt['cy']:.2f} (no ref, weak)"
    return True, "ok"


# ── 오버레이 / 시트 ─────────────────────────────────────────────────────────────
def draw_overlay(bgr: np.ndarray, masks: np.ndarray | None, k: int,
                 title: str, sub: str, ref: np.ndarray | None = None,
                 max_inst: int = 12) -> np.ndarray:
    """🔴 **선택된 인스턴스는 무슨 일이 있어도 그린다.**

    초판은 호출부에서 `masks[:max_inst]` 로 자르고 `min(k, max_inst-1)` 을 넘겼다. 인스턴스가
    상한을 넘으면 **엉뚱한 마스크가 «선택» 으로 초록 칠해진다** — 표의 숫자는 맞는데 그림만
    틀리는, 가장 잡기 어려운 종류의 오류다(실제로 `top mounting plate with a hole` 이
    30개 인스턴스를 내서 문의 링·옆 손잡이가 초록으로 그려졌다).
    자르기는 **여기 안에서**, 선택 마스크를 먼저 넣고 한다.
    """
    if masks is not None and len(masks):
        others = [masks[i] for i in range(len(masks)) if i != k][:max_inst - 1]
        masks, k = np.stack([masks[k]] + others) if others else masks[k:k + 1], 0
    out = bgr.copy()
    if ref is not None and ref.any():
        # 물체 기준 프레임(= full 마스크) — 자홍 윤곽 + 상단 28% 선.
        # 「초록이 이 안에, 그리고 이 선 위에 있는가」가 flange 판정의 실질이다.
        cs, _ = cv2.findContours(ref.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, cs, -1, (200, 60, 200), 2)
        ys, xs = np.nonzero(ref)
        yl = int(ys.min() + 0.28 * (ys.max() - ys.min()))
        cv2.line(out, (int(xs.min()), yl), (int(xs.max()), yl), (200, 60, 200), 1, cv2.LINE_AA)
    if masks is not None and len(masks):
        for i, m in enumerate(masks):
            if i == k:
                continue
            cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL,
                                     cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(out, cs, -1, C_OTH, 2)
        sel = masks[k]
        lay = out.copy()
        lay[sel] = C_SEL
        out = cv2.addWeighted(lay, 0.40, out, 0.60, 0)
        cs, _ = cv2.findContours(sel.astype(np.uint8), cv2.RETR_EXTERNAL,
                                 cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, cs, -1, (0, 255, 0), 3)
    return banner(out, title, sub)


def banner(img: np.ndarray, title: str, sub: str) -> np.ndarray:
    H, W = img.shape[:2]
    fs = max(0.45, min(1.0, W / 900.0))
    bh = int(28 * fs * 2 + 12)
    bar = np.zeros((bh, W, 3), np.uint8)
    cv2.putText(bar, title[:90], (8, int(24 * fs + 4)),
                cv2.FONT_HERSHEY_SIMPLEX, fs * 0.72, C_TXT, max(1, int(2 * fs)), cv2.LINE_AA)
    cv2.putText(bar, sub[:110], (8, int(24 * fs * 2 + 6)),
                cv2.FONT_HERSHEY_SIMPLEX, fs * 0.56, (170, 220, 255), max(1, int(fs)), cv2.LINE_AA)
    return np.vstack([bar, img])


def fit(img: np.ndarray, w: int, h: int) -> np.ndarray:
    ih, iw = img.shape[:2]
    s = min(w / iw, h / ih)
    r = cv2.resize(img, (max(1, int(iw * s)), max(1, int(ih * s))), interpolation=cv2.INTER_AREA)
    c = np.full((h, w, 3), 24, np.uint8)
    y, x = (h - r.shape[0]) // 2, (w - r.shape[1]) // 2
    c[y:y + r.shape[0], x:x + r.shape[1]] = r
    return c


def grid_sheet(cells: list[np.ndarray], ncol: int, cw: int, ch: int,
               header: str) -> np.ndarray:
    nrow = (len(cells) + ncol - 1) // ncol
    sheet = np.full((nrow * ch, ncol * cw, 3), 18, np.uint8)
    for i, c in enumerate(cells):
        r, q = divmod(i, ncol)
        sheet[r * ch:(r + 1) * ch, q * cw:(q + 1) * cw] = fit(c, cw, ch)
    hb = np.zeros((44, sheet.shape[1], 3), np.uint8)
    cv2.putText(hb, header, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, C_TXT, 2, cv2.LINE_AA)
    return np.vstack([hb, sheet])


# ── 본체 ────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    global FULL_AREA
    ap = argparse.ArgumentParser(description="SAM3 텍스트 프롬프트 스윕 (실사진)")
    ap.add_argument("--imgs", default="assets/real_imgs", help="이미지 디렉토리 또는 파일들")
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", default="full,flange")
    ap.add_argument("--ckpt", default=str(DEFAULT_CKPT))
    ap.add_argument("--confidence", type=float, default=0.05,
                    help="낮게 두고 점수를 기록한다 — 임계값은 사후에 정하는 편이 낫다(§35-2m-2)")
    ap.add_argument("--select", default="score", choices=["score", "center", "largest"])
    ap.add_argument("--max-inst", type=int, default=12, help="오버레이에 그릴 인스턴스 상한")
    ap.add_argument("--ref-full-slug", default=PARSER_DEFAULT_REF,
                    help="flange 판정의 **물체 기준 프레임**으로 쓸 full 프롬프트 slug (쉼표, 합집합). "
                         "GT 가 아니라 대리 기준이다 — 이게 틀리면 flange 판정도 함께 틀린다. "
                         "여러 개를 합치는 이유는 프롬프트 하나가 상면을 빠뜨려도 다른 게 덮으라고")
    ap.add_argument("--limit-prompts", type=int, default=0, help="앞 N 개만 (시험용)")
    ap.add_argument("--full-area-min", type=float, default=FULL_AREA[0],
                    help="`full` 판정의 마스크 면적비 하한. 🔴 기본 0.10 은 흰 배경 단일 물체 "
                         "기준이라 **배경이 있는 사진에서 맞는 마스크를 떨어뜨린다**")
    ap.add_argument("--full-area-max", type=float, default=FULL_AREA[1],
                    help="`full` 판정의 마스크 면적비 상한")
    ap.add_argument("--appearance", default=None,
                    help="몸체 외관 라벨 JSON {파일명|stem: black|orange|clear|twotone}. "
                         "기본은 이미지 디렉토리의 appearance.json")
    ap.add_argument("--note", default="")
    ap.add_argument("--instances", default=None,
                    help="이미지 파일 하나 — 그 이미지에 `--prompt-text` 를 돌려 **인스턴스를 "
                         "하나씩 따로** 그린다. 오버레이의 민트색 윤곽이 무엇인지 보는 용도")
    ap.add_argument("--prompt-text", default=None, help="--instances 와 함께 쓰는 프롬프트")
    ap.add_argument("--prompts-json", default=None,
                    help="내장 목록 대신 쓸 프롬프트 JSON — {target: [[slug, 범주, 프롬프트], …]}. "
                         "🔴 `flange` 만 재고 싶어도 **`full` 을 몇 개 같이 넣어야** 한다 — "
                         "flange 판정이 그 마스크를 물체 기준 프레임으로 쓴다(`--ref-full-slug`)")
    ap.add_argument("--rebuild-sheets", action="store_true",
                    help="추론 없이 **기존 `<out>` 의 results.json + ov/ 로 시트만** 다시 그린다. "
                         "시트 구성을 바꿀 때 60초짜리 재추론을 안 하려고 (모델도 안 올린다)")
    a = ap.parse_args(argv)

    FULL_AREA = (a.full_area_min, a.full_area_max)

    if a.rebuild_sheets:
        # 🔴 **`--rebuild-sheets` 는 판정을 재계산하지 않는다** — `results.json` 의 `ok`/`why` 를
        #    그대로 다시 그릴 뿐이다. 그래서 `--ref-full-slug` 를 함께 주면 «참조를 고쳐 다시 냈다»
        #    고 착각하게 된다(실제로 그렇게 적은 적이 있다). 조용히 무시하지 말고 **막는다.**
        if a.ref_full_slug != PARSER_DEFAULT_REF:
            print("🔴 `--rebuild-sheets` 는 **판정을 재계산하지 않는다** — `--ref-full-slug` 는 "
                  "적용되지 않는다.\n"
                  "   참조를 바꾸려면 **전체를 다시 돌려야 한다**(추론이 다시 필요하다). "
                  "시트만 다시 그릴 것이면 `--ref-full-slug` 를 빼고 실행할 것.")
            return 2
        return rebuild_sheets(Path(a.out))

    if a.instances:
        return instance_sheet(Path(a.instances), a.prompt_text, Path(a.out),
                              Path(a.ckpt), a.confidence, a.select)

    if a.prompts_json:
        global PROMPTS
        raw = json.loads(Path(a.prompts_json).read_text())
        # ★ 항목은 `[slug, 범주, 프롬프트]` 인데, 장부·실험군 파일은 **네 번째로 메타**(출처·score·
        #   라운드)를 달고 다닌다. 앞 셋만 쓰고 **뒤는 버린다** — 메타 때문에 도구가 죽으면
        #   «기록을 남기는 것» 과 «그 파일을 그대로 돌리는 것» 이 배타가 된다.
        PROMPTS = {k: [tuple(x[:3]) for x in v] for k, v in raw.items() if not k.startswith("_")}
        bad = {k: [x for x in v if len(x) < 3] for k, v in raw.items() if not k.startswith("_")}
        if any(bad.values()):
            print(f"   🔴 항목이 3개 미만인 것이 있다 {bad} — `[slug, 범주, 프롬프트]` 여야 한다")
            return 2
        print(f"   프롬프트 목록 {a.prompts_json} → " +
              " · ".join(f"{k} {len(v)}개" for k, v in PROMPTS.items()))

    root = Path(a.out)
    (root / "masks").mkdir(parents=True, exist_ok=True)
    (root / "ov").mkdir(parents=True, exist_ok=True)
    (root / "sheets").mkdir(parents=True, exist_ok=True)

    p = Path(a.imgs)
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    imgs = sorted([q for q in p.iterdir() if q.suffix.lower() in exts]) if p.is_dir() else [p]
    if p.is_dir():
        # 🔴 «조용히 빠지는» 파일이 있으면 안 된다 — `.webp` 14장이 목록에 없어서 237장
        #    스윕이 223장으로 돌았고 로그만 봐서는 알 수 없었다. 건너뛴 것은 반드시 센다.
        skip = [q.name for q in p.iterdir()
                if q.is_file() and q.suffix.lower() not in exts
                and q.suffix.lower() not in {".json", ".md", ".txt", ".csv"}]
        if skip:
            print(f"   ⚠️ 이미지가 아니라고 판단해 건너뛴 파일 {len(skip)}개: "
                  f"{sorted(skip)[:6]}{' …' if len(skip) > 6 else ''}")
    if not imgs:
        print(f"🔴 이미지가 없다: {a.imgs}")
        return 1
    # 🔴 `foup2.jpeg` 와 `foup2.png` 는 stem 이 같다 — 그대로 쓰면 마스크·오버레이가 서로를
    #    덮어써 «다른 이미지의 결과» 가 조용히 섞인다(교훈 #21 의 성질). 충돌하면 확장자를 붙인다.
    from collections import Counter
    dup = {k for k, v in Counter(q.stem for q in imgs).items() if v > 1}
    name = {q: (f"{q.stem}_{q.suffix[1:].lower()}" if q.stem in dup else q.stem) for q in imgs}
    if dup:
        print(f"   ⚠️ stem 충돌 {sorted(dup)} → 확장자를 붙여 구분한다")

    # ★ 몸체 외관 라벨 — 색 지정 프롬프트("black plastic box")는 **조건부**라서
    #   전체 평균으로 보면 «나쁜 프롬프트» 로 오독된다. 외관 축으로 갈라야 뜻이 산다.
    ap_map, ap_src = {}, None
    cand = Path(a.appearance) if a.appearance else (
        (p / "appearance.json") if p.is_dir() else p.parent / "appearance.json")
    if cand.exists():
        raw = json.loads(cand.read_text())
        ap_map = {k: v for k, v in raw.items() if not k.startswith("_")}
        ap_src = str(cand)

    def appear(q: Path) -> str:
        for k in (q.name, name[q], q.stem):
            if k in ap_map:
                return ap_map[k]
        return "unknown"

    app = {name[q]: appear(q) for q in imgs}
    if ap_src:
        miss = [k for k, v in app.items() if v == "unknown"]
        print(f"   외관 라벨 {ap_src} → " +
              ", ".join(f"{k}:{v}" for k, v in sorted(app.items(), key=lambda kv: kv[1])))
        if miss:
            print(f"   ⚠️ 라벨 없음: {miss} → 'unknown' 으로 묶인다")

    targets = [t.strip() for t in a.target.split(",") if t.strip()]
    for t in targets:
        if t not in PROMPTS:
            print(f"🔴 모르는 target: {t}")
            return 1

    print(f"== SAM3 프롬프트 스윕 | 이미지 {len(imgs)} | target {targets} | conf {a.confidence}")
    for t in targets:
        n = len(PROMPTS[t]) if not a.limit_prompts else min(a.limit_prompts, len(PROMPTS[t]))
        print(f"   · {t}: 프롬프트 {n} → 추론 {n * len(imgs)}")

    from spatial_vision.stages.segment_sam3 import build
    from spatial_vision.contracts import select_index
    import torch
    from PIL import Image

    t0 = time.time()
    processor, device = build(Path(a.ckpt), a.confidence)
    print(f"   모델 로드 {time.time() - t0:.1f}s ({device})")

    rows = []
    ov_cache = {}          # (target, img_stem, slug) -> 오버레이 경로
    n_done = 0
    t_inf = 0.0

    # ★ target 순서를 강제한다 — flange 판정이 같은 이미지의 `full` 마스크를 기준으로 쓴다.
    #   순서가 뒤집히면 기준이 없어 «약한 대체» 로 조용히 떨어진다.
    targets = sorted(targets, key=lambda t: 0 if t == "full" else 1)
    ref_full: dict[str, np.ndarray] = {}
    ref_slugs = {s.strip() for s in a.ref_full_slug.split(",") if s.strip()}
    known = {s for s, _, _ in PROMPTS["full"]}
    # 🔴 **«하나도 못 찾을 때만» 경고하면 안 된다** (2026-08-27 수정). 셋 중 하나만 매칭돼도
    #    기준 프레임이 참조 한 장으로 만들어져 **flange 통과가 21 → 0 으로 무너졌다** —
    #    그런데 경고가 없어서 «flange 프롬프트가 다 나빠졌다» 로 읽힐 뻔했다(§37-2 의 «3개 미만이면
    #    약해진다» 가 조용히 발생한 것). **몇 개가 잡혔는지, 무엇이 못 잡혔는지** 항상 찍는다.
    if "flange" in targets:
        hit, miss = sorted(ref_slugs & known), sorted(ref_slugs - known)
        if not hit:
            print(f"   🔴🔴 `--ref-full-slug {a.ref_full_slug}` 중 **아는 slug 이 없다** → "
                  "flange 판정이 약한 대체(이미지 기준 cy)로 떨어진다. 이 런의 flange 결과는 무효다.")
        else:
            mark = "🔴" if len(hit) < 3 else "   ·"
            print(f"   {mark} flange 기준 `full` 참조 **{len(hit)}개** 잡힘 {hit}"
                  + (f" · 못 잡음 {miss}" if miss else ""))
            if len(hit) < 3:
                print("      🔴 **3개 미만이면 물체 기준 프레임이 약해진다**(§37-2) — 참조 하나가 "
                      "한 이미지에서 어긋나면 그 이미지의 flange 가 전부 탈락한다. "
                      "`--ref-full-slug` 를 목록에 실제로 있는 slug 으로 고칠 것.")

    stems = []
    for ip in imgs:
        stem = name[ip]
        bgr = cv2.imread(str(ip))
        if bgr is None:
            print(f"   ⚠️ 못 읽음: {ip}")
            continue
        stems.append(stem)
        H, W = bgr.shape[:2]
        pil = Image.open(ip).convert("RGB")
        for t in targets:
            plist = PROMPTS[t][:a.limit_prompts] if a.limit_prompts else PROMPTS[t]
            (root / "masks" / stem / t).mkdir(parents=True, exist_ok=True)
            (root / "ov" / stem / t).mkdir(parents=True, exist_ok=True)
            for slug, cat, prompt in plist:
                ts = time.time()
                # ★ 프롬프트마다 set_image 를 다시 한다 — state 재사용은 프롬프트 간
                #   오염 여부가 검증되지 않았다. 신뢰성 > 속도(이 스윕은 1회성이다).
                # 🔴 **큰 사진 한 장이 스윕 전체를 죽인다** (2026-08-28). SAM3 는 마스크를
                #    «원본 해상도 × 제안 수» 로 내므로 6000×4000 짜리 웹사진에서
                #    `_forward_grounding` 의 sigmoid 가 14.5GB 를 한 번에 잡고 OOM 이 난다
                #    (79장 중 43번째에서 죽어 앞의 42장 결과가 results.json 없이 남았다).
                #    → **그 프롬프트만 반으로 줄여 다시** 시도하고, 줄인 사실을 행에 남긴다.
                #    전역 상한(`--max-side`)으로 하지 않는 이유는 **필요 없는 이미지까지
                #    해상도가 바뀌어** 다른 런과 비교가 깨지기 때문이다.
                shrink, out = 1.0, None
                while True:
                    try:
                        pil_i = pil if shrink == 1.0 else pil.resize(
                            (max(1, int(pil.width * shrink)), max(1, int(pil.height * shrink))),
                            Image.BILINEAR)
                        with torch.autocast("cuda", dtype=torch.bfloat16):
                            st = processor.set_image(pil_i)
                            out = processor.set_text_prompt(state=st, prompt=prompt)
                        break
                    except torch.OutOfMemoryError:
                        torch.cuda.empty_cache()
                        if shrink <= 0.25:
                            print(f"   🔴 [{stem}] {slug} — 0.25배에서도 OOM, 이 칸은 «미검출» 로 "
                                  "기록된다. 🔴 **그 프롬프트만 불리해지므로 서열에서 빼야 한다**")
                            out = {"masks": None, "scores": None}
                            break
                        shrink *= 0.5
                        print(f"   ⚠️ [{stem}] {slug} OOM → {shrink:.2f}배로 재시도 "
                              f"({pil.width}x{pil.height})")
                dt = time.time() - ts
                t_inf += dt
                n_done += 1

                masks, scores = out["masks"], out["scores"]
                n_inst = 0 if masks is None else len(masks)

                rec = {"image": stem, "appearance": app[stem], "target": t, "slug": slug,
                       "category": cat, "prompt": prompt, "n_inst": n_inst,
                       "img_w": W, "img_h": H, "sec": round(dt, 3), "shrink": shrink}

                if n_inst == 0:
                    rec.update({"score": 0.0, "score_max": 0.0, "area_frac": 0.0,
                                "n_cc": 0, "cc_main_frac": 0.0, "solidity": 0.0,
                                "bbox_fill": 0.0, "cx": 0.0, "cy": 0.0,
                                "border_frac": 0.0, "ok": 0,
                                "why": "oom" if shrink <= 0.25 else "no detection"})
                    ovp = root / "ov" / stem / t / f"{slug}.png"
                    cv2.imwrite(str(ovp), banner(bgr, f"[{slug}] {prompt}", "검출 0 (no detection)"))
                    ov_cache[(t, stem, slug)] = ovp
                    rows.append(rec)
                    continue

                def _np(x):
                    return np.asarray(x.detach().float().cpu()) if hasattr(x, "detach") else np.asarray(x)

                m = _np(masks)
                m = m.squeeze(1) if m.ndim == 4 else m
                m = m > 0.5 if m.dtype != bool else m
                if m.shape[1:] != (H, W):
                    # OOM 재시도로 줄여 넣은 경우 — **원본 해상도로 되돌린다**. 안 되돌리면
                    # 저장 마스크 크기가 다른 칸과 달라져 IoU 비교·오버레이가 조용히 깨진다.
                    m = np.stack([cv2.resize(x.astype(np.uint8), (W, H),
                                             interpolation=cv2.INTER_NEAREST).astype(bool)
                                  for x in m])
                s = _np(scores).reshape(-1)
                k = select_index(m, s, a.select, 0.3)

                mt = mask_metrics(m[k])
                rm = ref_metrics(m[k], ref_full.get(stem)) if t == "flange" else None
                ok, why = plausible(t, mt, n_inst, rm)
                rec.update({"score": float(s[k]), "score_max": float(s.max()),
                            **{kk: (round(vv, 5) if isinstance(vv, float) else vv)
                               for kk, vv in mt.items() if kk != "bbox"},
                            **{kk: round(vv, 4) for kk, vv in (rm or {}).items()},
                            "ok": int(ok), "why": why})
                rows.append(rec)
                if t == "full" and slug in ref_slugs and ok:
                    b = m[k].astype(bool)
                    ref_full[stem] = b if stem not in ref_full else (ref_full[stem] | b)

                cv2.imwrite(str(root / "masks" / stem / t / f"{slug}.png"),
                            (m[k].astype(np.uint8) * 255))
                sub = (f"score {s[k]:.3f} | inst {n_inst} | area {mt['area_frac']:.3f} "
                       f"| cc {mt['n_cc']} | sol {mt['solidity']:.2f}")
                if rm and rm["in_region"] >= 0.0:
                    sub += (f" | in_region {rm['in_region']:.2f} | rel_y {rm['rel_y']:.2f}"
                            f" | rel_a {rm['rel_area']:.3f}")
                sub += f" | {'OK' if ok else why}"
                ovp = root / "ov" / stem / t / f"{slug}.png"
                cv2.imwrite(str(ovp), draw_overlay(bgr, m, k, f"[{slug}] {prompt}", sub,
                                                   ref_full.get(stem) if t == "flange" else None,
                                                   a.max_inst))
                ov_cache[(t, stem, slug)] = ovp

        torch.cuda.empty_cache()      # 이미지마다 비운다 — 해상도가 제각각이라 파편화가 쌓인다
        # 🔴 **끝에 한 번만 쓰면 안 된다** — OOM 으로 43번째에서 죽었을 때 앞의 42장이
        #    `results.json` 없이 마스크만 남아 지표(score·area·why)가 통째로 날아갔다.
        #    `fetch_foup_images.py` 의 manifest 와 **같은 함정**이다. 이미지마다 쓴다.
        (root / "results_partial.json").write_text(
            json.dumps({"meta": {"partial": True, "images_done": len(stems)}, "rows": rows}))
        print(f"   [{stem}] 누적 {n_done} 추론 · {time.time() - t0:.0f}s", flush=True)

    perf, cons = make_sheets(root, rows, stems, targets, ov_cache)
    fl_ref = flange_coverage(root, rows, stems, perf) if "flange" in targets else None

    # ── 표 / 리포트 ─────────────────────────────────────────────────────────────
    write_csv(root, rows)

    meta = {"note": a.note, "confidence": a.confidence, "select": a.select,
            "full_area": list(FULL_AREA),
            "appearance_src": ap_src, "ref_full_slug": a.ref_full_slug,
            "flange_ref_slug": fl_ref,
            "images": [{"file": str(q), "key": name[q], "appearance": app[name[q]],
                        "sha8": sha8(q)} for q in imgs],
            "n_inference": n_done, "sec_total": round(time.time() - t0, 1),
            "sec_inference": round(t_inf, 1), "ckpt": a.ckpt}
    (root / "results.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=2,
                                                  ensure_ascii=False))
    nbad = verify(root, rows)
    meta["verify_mismatch"] = nbad
    write_report(root, rows, stems, targets, meta, a, app, perf, cons)
    print(f"\n✅ {n_done} 추론 · {time.time() - t0:.0f}s → {root}/report.md")
    return 0


def instance_sheet(img: Path, prompt: str, out: Path, ckpt: Path,
                   conf: float, select: str) -> int:
    """이미지 한 장 × 프롬프트 하나 → **인스턴스를 하나씩 따로** 그린 시트.

    ★ 왜 필요한가 — 스윕 오버레이에서 초록은 «선택된 하나» 이고 민트색 윤곽은 «나머지 후보» 다.
      한 화면에 겹쳐 있으면 «저 민트도 마스크인가» 가 헷갈린다. 여기서는 후보를 한 칸에
      하나씩 놓아, 각각이 무엇을 집었고 점수가 얼마인지 따로 본다.
    🔴 저장되는 마스크는 **선택된 하나뿐**이다. 나머지는 어디에도 안 쓰인다.
    """
    if not prompt:
        print("🔴 --instances 에는 --prompt-text 가 필요하다")
        return 1
    import torch
    from PIL import Image
    from spatial_vision.stages.segment_sam3 import build
    from spatial_vision.contracts import select_index

    bgr = cv2.imread(str(img))
    if bgr is None:
        print(f"🔴 못 읽음: {img}")
        return 1
    processor, _ = build(ckpt, conf)
    with torch.autocast("cuda", dtype=torch.bfloat16):
        st = processor.set_image(Image.open(img).convert("RGB"))
        o = processor.set_text_prompt(state=st, prompt=prompt)

    def _np(x):
        return np.asarray(x.detach().float().cpu()) if hasattr(x, "detach") else np.asarray(x)

    masks, scores = o["masks"], o["scores"]
    if masks is None or len(masks) == 0:
        print("   검출 0")
        return 0
    m = _np(masks)
    m = m.squeeze(1) if m.ndim == 4 else m
    m = m > 0.5 if m.dtype != bool else m
    s = _np(scores).reshape(-1)
    k = select_index(m, s, select, 0.3)
    order = list(np.argsort(-s))          # 점수 내림차순 — 선택된 것이 왜 뽑혔는지 보이게

    cells = []
    for rank, i in enumerate(order, 1):
        v = bgr.copy()
        col = (80, 220, 80) if i == k else (220, 220, 60)
        lay = v.copy()
        lay[m[i]] = col
        v = cv2.addWeighted(lay, 0.45, v, 0.55, 0)
        cs, _ = cv2.findContours(m[i].astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(v, cs, -1, col, 3)
        mt = mask_metrics(m[i])
        tag = "*** SELECTED (saved as mask) ***" if i == k else "not used (drawn cyan in overlay)"
        cells.append(banner(v, f"inst #{rank}/{len(order)}  (index {i})  {tag}",
                            f"score {s[i]:.3f} | area {mt['area_frac']:.4f} | "
                            f"cc {mt['n_cc']} | sol {mt['solidity']:.2f}"))
    out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:40].strip("_")
    p = out / f"instances__{img.stem}__{slug}.png"
    cv2.imwrite(str(p), grid_sheet(cells, 3, 620, 500,
                                   f'{img.name}   "{prompt}"   {len(order)} instances   '
                                   f'green = selected (the only one saved)'))
    print(f"   인스턴스 {len(order)}개 · 선택 index {k} (score {s[k]:.3f}) → {p}")
    return 0


def rebuild_sheets(root: Path) -> int:
    """`<out>/results.json` + 이미 있는 `ov/` 로 시트만 다시 그린다 (추론·모델 로드 0).

    🔴 **오버레이 자체는 다시 안 그린다** — `ov/*.png` 를 그대로 쓴다. 오버레이 그리는 코드를
       고쳤다면 이걸로는 반영이 안 되므로 전체를 다시 돌려야 한다.
    """
    rp = root / "results.json"
    if not rp.exists():
        print(f"🔴 {rp} 가 없다 — 먼저 스윕을 한 번 돌려야 한다")
        return 1
    d = json.loads(rp.read_text())
    rows = d["rows"]
    stems = list(dict.fromkeys(r["image"] for r in rows))
    targets = [t for t in ("full", "flange") if any(r["target"] == t for r in rows)]
    ov_cache = {(r["target"], r["image"], r["slug"]):
                root / "ov" / r["image"] / r["target"] / f"{r['slug']}.png" for r in rows}
    miss = [k for k, v in ov_cache.items() if not v.exists()]
    if miss:
        print(f"   ⚠️ 오버레이 없음 {len(miss)}건 (그 칸은 비워 둔다): {miss[:3]}")
    print(f"== 시트만 재생성 | 이미지 {len(stems)} | target {targets} | 레코드 {len(rows)}")
    perf, cons = make_sheets(root, rows, stems, targets, ov_cache)
    meta = d.get("meta", {})
    if "flange" in targets and "full" in targets:
        # 🔴 rebuild 에서도 기준 slug 을 meta 에 되돌려 놓아야 리포트가 `?` 를 안 쓴다.
        meta["flange_ref_slug"] = flange_coverage(root, rows, stems, perf)
    write_csv(root, rows)
    (root / "results.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=2,
                                                  ensure_ascii=False))
    # 리포트도 같이 쓴다 — 안 그러면 report.md 가 옛 시트 구성을 가리킨다.
    args_like = argparse.Namespace(
        note=meta.get("note", ""), confidence=meta.get("confidence"),
        select=meta.get("select"), ref_full_slug=meta.get("ref_full_slug", "(기록 없음)"))
    write_report(root, rows, stems, targets, meta, args_like,
                 {r["image"]: r["appearance"] for r in rows}, perf, cons)
    print(f"✅ → {root}/sheets/ · {root}/report.md")
    return 0


def area_consensus(rows, stems, t, slugs, tol: float = 0.25) -> dict:
    """프롬프트 **끼리** 면적을 대조해 «같은 것을 집었나» 를 본다 (GT 대용).

    ★ 통과 수만으로는 «전체를 집은 것» 과 «일부만 집은 것» 이 구분되지 않는다 — 실제로
      `rectangular plastic enclosure` 가 투톤 2장에서 **흰 문만** 집고도 9/9 통과했다
      (면적 0.27 vs 나머지 0.49). 여러 프롬프트가 같은 이미지에서 같은 면적을 내면 그게
      합의값이고, 거기서 크게 벗어난 칸이 «다른 것을 집은» 칸이다.
    🔴 합의가 곧 정답은 아니다 — 전부 같이 틀리면 못 잡는다(교훈: GT-free 지표의 공통 한계).
    """
    med = {}
    for st in stems:
        v = [r["area_frac"] for r in rows
             if r["target"] == t and r["image"] == st and r["slug"] in slugs and r["ok"]]
        med[st] = float(np.median(v)) if v else 0.0
    dev = {}
    for sl in slugs:
        bad = []
        for st in stems:
            m = med[st]
            r = next((r for r in rows if r["target"] == t and r["image"] == st
                      and r["slug"] == sl), None)
            if r and r["ok"] and m > 0 and abs(r["area_frac"] - m) / m > tol:
                bad.append((st, r["area_frac"], m))
        dev[sl] = bad
    return {"median": med, "dev": dev}


def matrix_sheet(rows, stems, t, plist, ov_cache, title: str,
                 dev: dict | None = None) -> np.ndarray:
    """행=프롬프트, 열=이미지 축소판. `plist` 를 걸러 넘기면 부분 매트릭스가 된다."""
    # 🔴 제목과 열 이름을 같은 줄에 두면 긴 제목이 열 이름을 덮는다 → 두 줄로 나눈다.
    cw, ch, lw, hh = 210, 175, 330, 64
    mat = np.full((len(plist) * ch + hh, lw + len(stems) * cw, 3), 18, np.uint8)
    cv2.putText(mat, title, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.75, C_TXT, 2, cv2.LINE_AA)
    for j, st in enumerate(stems):
        cv2.putText(mat, st[:22], (lw + j * cw + 6, 54),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (170, 220, 255), 1, cv2.LINE_AA)
    for i, (sl, cat, prompt) in enumerate(plist):
        y = hh + i * ch
        cv2.putText(mat, sl, (8, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58, C_TXT, 2, cv2.LINE_AA)
        cv2.putText(mat, prompt[:38], (8, y + 48), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (170, 220, 255), 1, cv2.LINE_AA)
        nok = sum(1 for r in rows if r["target"] == t and r["slug"] == sl and r["ok"])
        cv2.putText(mat, f"pass {nok}/{len(stems)}", (8, y + 72),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 255, 120) if nok else (120, 120, 255),
                    1, cv2.LINE_AA)
        nbad = len((dev or {}).get(sl, []))
        if nbad:
            # 🔴 «통과했지만 남들과 다른 것을 집은» 칸 수. 통과 수만 보면 안 보인다.
            cv2.putText(mat, f"area dev {nbad}", (8, y + 96),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 255), 2, cv2.LINE_AA)
        badset = {b[0] for b in (dev or {}).get(sl, [])}
        for j, st in enumerate(stems):
            q = ov_cache.get((t, st, sl))
            if q is not None and Path(q).exists():
                mat[y:y + ch, lw + j * cw:lw + (j + 1) * cw] = fit(cv2.imread(str(q)), cw, ch)
            if st in badset:
                cv2.rectangle(mat, (lw + j * cw + 1, y + 1),
                              (lw + (j + 1) * cw - 2, y + ch - 2), (90, 90, 255), 3)
    return mat


def make_sheets(root: Path, rows, stems, targets, ov_cache) -> tuple[dict, dict]:
    """전체 시트 + **전 이미지 통과(N/N)** 만 모은 시트.

    ★ 전자는 «무엇이 있었나» 를 남기는 기록이고, 후자는 «무엇을 쓸까» 를 고르는 화면이다.
      섞으면 60행을 매번 훑게 된다. 파일을 나눠 두면 후보만 보고 판단할 수 있다.

    ⚠️ 프롬프트 목록은 `PROMPTS` 상수가 아니라 **`rows` 에서** 뽑는다 — 상수를 나중에 고쳐도
       옛 런을 그대로 다시 그릴 수 있어야 하고, `--limit-prompts` 도 자동으로 반영된다.
    """
    # 🔴 파일명에 **순위**가 들어가므로 순위가 바뀌면 옛 파일이 남아 중복이 된다
    #    (`full__04__g_case.png` 와 `full__04__s_rectangular.png` 가 공존했다).
    #    덮어쓰기로는 못 지운다 — 디렉토리를 비우고 쓴다.
    pdir = root / "sheets" / "perfect"
    if pdir.exists():
        for q in pdir.glob("*.png"):
            q.unlink()
    pdir.mkdir(parents=True, exist_ok=True)
    n_img = len(stems)
    out, cons = {}, {}
    for t in targets:
        plist = list(dict.fromkeys((r["slug"], r["category"], r["prompt"])
                                   for r in rows if r["target"] == t))
        for stem in stems:
            cells = [cv2.imread(str(ov_cache[(t, stem, sl)])) for sl, _, _ in plist
                     if (t, stem, sl) in ov_cache]
            if cells:
                cv2.imwrite(str(root / "sheets" / f"by_image__{t}__{stem}.png"),
                            grid_sheet(cells, 5, 460, 380,
                                       f"{stem} / target={t} : all prompts"))
        for sl, cat, prompt in plist:
            cells = [cv2.imread(str(ov_cache[(t, st, sl)])) for st in stems
                     if (t, st, sl) in ov_cache]
            if cells:
                cv2.imwrite(str(root / "sheets" / f"by_prompt__{t}__{sl}.png"),
                            grid_sheet(cells, 3, 620, 500,
                                       f'target={t}  "{prompt}"  [{sl}/{cat}] : all images'))
        def _med(sl):
            v = [r["score"] for r in rows
                 if r["target"] == t and r["slug"] == sl and r["n_inst"] > 0]
            return float(np.median(v)) if v else 0.0

        perf = [(sl, cat, pr) for sl, cat, pr in plist
                if sum(1 for r in rows if r["target"] == t and r["slug"] == sl and r["ok"]) == n_img]
        # 합의 면적 이탈은 **전 이미지 통과 프롬프트끼리** 잰다 — 떨어진 것을 섞으면 기준이 흐려진다.
        ac = area_consensus(rows, stems, t, [s for s, _, _ in perf])
        dev = ac["dev"]
        cons[t] = ac

        cv2.imwrite(str(root / "sheets" / f"matrix__{t}.png"),
                    matrix_sheet(rows, stems, t, plist, ov_cache,
                                 f"target={t}   rows=prompt   cols=image   (ALL {len(plist)})",
                                 dev))

        # ── 전 이미지 통과만 ────────────────────────────────────────────────
        # ★ 정렬은 «이탈 적은 순 → score 중앙 높은 순». 통과 수는 전부 같으니 못 가르고,
        #   score 만으로 세우면 «남들과 다른 것을 집은» 프롬프트가 위로 올라온다.
        perf.sort(key=lambda x: (len(dev.get(x[0], [])), -_med(x[0])))
        out[t] = perf
        if not perf:
            print(f"   ⚠️ target={t}: {n_img}/{n_img} 통과 프롬프트가 없다 → perfect 시트 생략")
            continue
        cv2.imwrite(str(root / "sheets" / f"perfect__{t}.png"),
                    matrix_sheet(rows, stems, t, perf, ov_cache,
                                 f"target={t}   PASS {n_img}/{n_img} ONLY   "
                                 f"({len(perf)}/{len(plist)} prompts)   "
                                 f"sorted by area-dev then median score   "
                                 f"[red box = area differs from prompt consensus]", dev))
        for rank, (sl, cat, prompt) in enumerate(perf, 1):
            cells = [cv2.imread(str(ov_cache[(t, st, sl)])) for st in stems
                     if (t, st, sl) in ov_cache]
            if cells:
                nb = len(dev.get(sl, []))
                cv2.imwrite(str(root / "sheets" / "perfect" /
                                f"{t}__{rank:02d}__{sl}.png"),
                            grid_sheet(cells, 3, 620, 500,
                                       f'#{rank}  target={t}  "{prompt}"  [{sl}/{cat}]  '
                                       f'PASS {n_img}/{n_img}  score {_med(sl):.3f}  '
                                       + (f'!! area dev {nb}/{n_img}' if nb else 'area dev 0')))
        nclean = sum(1 for s, _, _ in perf if not dev.get(s))
        print(f"   ✅ target={t}: {n_img}/{n_img} 통과 {len(perf)}/{len(plist)}개 "
              f"(그중 면적 이탈 0 인 것 {nclean}개) → "
              f"sheets/perfect__{t}.png + sheets/perfect/{t}__*.png")
    return out, cons


CSV_COLS = ["image", "appearance", "target", "category", "slug", "prompt", "n_inst",
            "score", "score_max", "area_frac", "n_cc", "cc_main_frac", "solidity",
            "bbox_fill", "cx", "cy", "border_frac", "in_region", "rel_y", "rel_area",
            "flange_in_full", "ok", "why", "sec", "img_w", "img_h"]


def write_csv(root: Path, rows) -> None:
    """🔴 `--rebuild-sheets` 에서도 **반드시 같이 쓴다.** 리포트·시트만 갱신하고 CSV 를 두면
       같은 디렉토리 안에서 «표에는 있는데 CSV 에는 없는 열» 이 생겨 산출물이 서로 어긋난다.
    """
    with open(root / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in CSV_COLS})


def flange_coverage(root: Path, rows, stems, perf) -> str | None:
    """`full` 마스크가 **top flange 를 포함했는가** — 프롬프트별로 잰다.

    🔴 왜 중요한가 — `pose_fp --primary full` 은 `mask_full` 과 `full.ply` 를 맞춘다. 그런데
       **pose 원점이 flange 상면 중심**이다(`PIPELINE_PLAN` 원점 규약). 마스크에서 그 부분이
       통째로 빠지면 «경계가 조금 틀린» 게 아니라 «기준 구조물이 없는» 것이다.
       면적으로는 4~6% 라 IoU·면적비 같은 기존 지표가 이 결손을 **전혀 못 잡는다**(교훈 #6·#13).

    기준 flange 마스크는 flange 서열 1위(전 이미지 통과·이탈 0)를 쓴다 — GT 가 아니라 대리다.
    """
    ref = (perf.get("flange") or [None])[0]
    if ref is None:
        return None
    ref_slug = ref[0]
    hit = 0
    for r in rows:
        if r["target"] != "full":
            continue
        # 검출 0 인 프롬프트는 마스크 파일 자체가 없다 — imread 경고를 내지 말고 건너뛴다.
        pf = root / "masks" / r["image"] / "full" / f"{r['slug']}.png"
        pg = root / "masks" / r["image"] / "flange" / f"{ref_slug}.png"
        if not (pf.exists() and pg.exists()):
            r["flange_in_full"] = ""
            continue
        f, g = cv2.imread(str(pf), 0), cv2.imread(str(pg), 0)
        if f is None or g is None:
            r["flange_in_full"] = ""
            continue
        fl = g > 127
        r["flange_in_full"] = round(float(((f > 127) & fl).sum()) / max(int(fl.sum()), 1), 4)
        hit += 1
    print(f"   · `full` 의 flange 포함률을 {hit}건에 대해 계산했다 (기준 flange = `{ref[2]}`)")
    return ref_slug


def verify(root: Path, rows) -> int:
    """저장된 마스크를 **다시 읽어** 표의 값과 맞는지 본다 — «결과가 엉켰나» 를 잡는 유일한 방법.

    파이프라인이 프롬프트별로 파일을 쓰다 보면 **다른 프롬프트의 결과가 그 자리에 있는** 사고가
    난다(stem 충돌·인덱스 어긋남). 지표는 추론 직후 메모리에서 계산하므로, 디스크의 마스크를
    다시 읽어 같은 값이 나오는지 대조하면 그 사고만 걸러진다.
    """
    bad = []
    for r in rows:
        if r["n_inst"] == 0:
            continue
        p = root / "masks" / r["image"] / r["target"] / f"{r['slug']}.png"
        m = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if m is None:
            bad.append((r, "마스크 파일 없음"))
            continue
        got = mask_metrics(m > 127)
        if abs(got["area_frac"] - r["area_frac"]) > 1e-4 or abs(got["cx"] - r["cx"]) > 1e-3:
            bad.append((r, f"area {got['area_frac']:.5f} vs {r['area_frac']:.5f} · "
                           f"cx {got['cx']:.3f} vs {r['cx']:.3f}"))
    if bad:
        print(f"   🔴 배선 검증 실패 {len(bad)}건 — 디스크 마스크와 표가 다르다")
        for r, w in bad[:5]:
            print(f"      {r['image']}/{r['target']}/{r['slug']}: {w}")
    else:
        print(f"   ✅ 배선 검증 통과 — 마스크 {sum(1 for r in rows if r['n_inst'])}개 전부 표와 일치")
    return len(bad)


def write_report(root: Path, rows, stems, targets, meta, a, app, perf, cons):
    L = ["# SAM3 텍스트 프롬프트 스윕 — 실사진",
         "",
         f"- 이미지 **{len(stems)}장** · 추론 **{meta['n_inference']}회** · "
         f"{meta['sec_total']}초 (추론만 {meta['sec_inference']}초)",
         f"- `--confidence {a.confidence}` · `--select {a.select}`",
         "- 배선 검증(디스크 마스크 ↔ 표): " +
         ("✅ 전부 일치" if meta.get("verify_mismatch") == 0
          else f"🔴 **불일치 {meta.get('verify_mismatch')}건 — 아래를 읽기 전에 원인을 찾을 것**"),
         f"- 메모: {a.note or '—'}",
         ""]

    # ── 한 줄 결론 — 전 외관에서 통과한 프롬프트 ─────────────────────────────────
    apps_all = sorted({app[s] for s in stems})
    L += ["## 결론 — **전 이미지 통과** 프롬프트", "",
          "«몸체 색을 몰라도 되는» 기본값 후보다. **면적 이탈 적은 순 → score 중앙 내림차순**",
          "(이탈 = 다른 프롬프트들과 다른 것을 집었다는 뜻, 아래 절).", ""]
    for t in targets:
        sub = [r for r in rows if r["target"] == t]
        dv = (cons.get(t) or {}).get("dev", {})
        L += [f"**`{t}`** — {len(perf.get(t, []))}/{len({r['slug'] for r in sub})}개", "",
              "| # | 프롬프트 | 범주 | score 중앙 | 면적 이탈 |", "|---|---|---|---|---|"]
        for rank, (sl, cat, pr) in enumerate(perf.get(t, []), 1):
            sc = [r["score"] for r in sub if r["slug"] == sl and r["n_inst"] > 0]
            nb = len(dv.get(sl, []))
            L.append(f"| {rank} | `{pr}` | {cat} | "
                     f"{(float(np.median(sc)) if sc else 0.0):.3f} | " +
                     ("✅ 0" if not nb else f"🔴 **{nb}/{len(stems)}**") + " |")
        if not perf.get(t):
            L.append("| — | 🔴 전 이미지를 통과한 프롬프트가 없다 | | | |")
        L += ["", f"→ `sheets/perfect__{t}.png` · `sheets/perfect/{t}__NN__*.png`", ""]
    # ── 합의 면적 이탈 ─────────────────────────────────────────────────────────
    L += ["", "### 🔴 «통과» 했지만 **남들과 다른 것을 집은** 칸", "",
          "통과 수만으로는 «전체를 집은 것» 과 «일부만 집은 것» 이 안 갈린다. 전 이미지 통과",
          "프롬프트끼리 같은 이미지에서 낸 **면적 중앙값**을 합의값으로 보고, 25% 넘게 벗어난",
          "칸을 표시한다 (시트에서는 **빨간 테두리**, 행 라벨에 `area dev N`).", ""]
    any_dev = False
    for t in targets:
        dv = (cons.get(t) or {}).get("dev", {})
        bad = [(sl, b) for sl, b in dv.items() if b]
        if not bad:
            L.append(f"**`{t}`** — 이탈 없음 ✅")
            continue
        any_dev = True
        L += [f"**`{t}`**", "",
              "| 프롬프트 | 이탈 | 어느 이미지 (면적 → 합의값) |", "|---|---|---|"]
        pr = {r["slug"]: r["prompt"] for r in rows if r["target"] == t}
        for sl, b in sorted(bad, key=lambda x: -len(x[1])):
            L.append(f"| `{pr[sl]}` | **{len(b)}/{len(stems)}** | " +
                     ", ".join(f"`{im}` ({a1:.3f} → {m1:.3f})" for im, a1, m1 in b[:4]) + " |")
        L.append("")
    if any_dev:
        L += ["⚠️ 이탈이 곧 «틀림» 은 아니다 — **합의 쪽이 틀렸을 수도** 있다. 빨간 칸을 열어 본다.",
              "🔴 그리고 **전부 같이 틀리면 이 검사로 못 잡는다** (GT-free 지표의 공통 한계).", ""]

    # ── full 이 flange 를 포함했나 ───────────────────────────────────────────────
    cov = [r for r in rows if r["target"] == "full" and r.get("flange_in_full") != ""
           and r.get("flange_in_full") is not None]
    if cov and perf.get("full"):
        L += ["", "### 🔴🔴 `full` 마스크가 **top flange 를 포함했는가**", "",
              "`pose_fp --primary full` 은 `mask_full` 을 `full.ply` 와 맞추는데, **pose 원점이",
              "flange 상면 중심**이다. 마스크에서 그 부분이 통째로 빠지면 «경계가 조금 틀린» 게",
              "아니라 **«기준 구조물이 없는»** 것이다. flange 는 면적의 4~6% 라 **면적비·볼록성·",
              "IoU 같은 지표가 이 결손을 원리적으로 못 잡는다**(교훈 #6·#13) — 그래서 따로 잰다.",
              "",
              f"기준 flange 마스크 = flange 서열 1위 `{meta.get('flange_ref_slug') or '?'}`. GT 가 아니라 대리다.", ""]
        head = [s for s in stems]
        L += ["| full 프롬프트 | " + " | ".join(f"`{h[:11]}`" for h in head) + " | 중앙 |",
              "|---|" + "---|" * (len(head) + 1)]
        cv_ = {(r["slug"], r["image"]): r["flange_in_full"] for r in cov}
        for sl, _, pr in perf["full"]:
            v = [cv_.get((sl, h)) for h in head]
            vv = [x for x in v if x is not None]
            L.append(f"| `{pr}` | " + " | ".join(
                "—" if x is None else (f"**{x:.2f}**" if x < 0.5 else f"{x:.2f}") for x in v) +
                f" | {(float(np.median(vv)) if vv else 0.0):.2f} |")
        L += ["", "**굵은 값(<0.50) = flange 를 놓쳤다.** 그 프롬프트는 다른 지표를 다 통과해도",
              "`--primary full` 경로에 쓰면 안 된다.", ""]
        bad_img = [h for h in head
                   if np.median([cv_[(s, h)] for s, _, _ in perf["full"] if (s, h) in cv_]) < 0.5]
        if bad_img:
            L += [f"⚠️ **{', '.join('`' + b + '`' for b in bad_img)}** 는 프롬프트를 바꿔도 대부분 놓친다 —",
                  "프롬프트가 아니라 **이미지 조건**(반투명 몸체 등)이 만든 결손이다. "
                  "그 조건에서 살아남는 프롬프트가 있는지 열에서 찾는다.", ""]

    L += ["🔴 이 목록은 **분할만** 본 것이다. 최종 판정은 `run_group_a.py --sam3-text` 전 체인에서 한다.",
          "",
         "## 🔴 읽는 법 — 이 표는 «순위표» 가 아니다",
         "",
         "실사진이라 **GT 가 없다**. 여기 숫자는 전부 GT-free 형상 지표이고 `ok` 는",
         "«눈으로 볼 값어치가 있는가» 를 거르는 **휴리스틱**이다 — 통과가 «맞다» 를 뜻하지 않는다",
         "(배경을 통째로 집어도 면적비는 크다, 교훈 #15). **판정은 오버레이를 보고 한다.**",
         "",
         "1. **`sheets/perfect__<target>.png`** — 전 이미지 통과한 것만 (score 중앙 내림차순). "
         "**여기서 고른다**",
         "2. `sheets/perfect/<target>__NN__<slug>.png` — 그 후보 하나를 전 이미지로 크게",
         "3. `sheets/matrix__<target>.png` — **전수**(모든 프롬프트 × 모든 이미지). "
         "«왜 떨어졌나» 를 볼 때만 연다",
         "4. 흥미로운 이미지는 `sheets/by_image__<target>__<img>.png` 로 프롬프트끼리 비교",
         "4. `score` 가 낮아 떨어진 것은 임계값 문제일 수 있다 — §35-2m-2 처럼",
         "   **자신감만 낮고 마스크는 정확한** 경우가 실제로 있었다. 그래서 conf 를 낮게 두고 돌렸다.",
         "",
         "휴리스틱 사유(`why`)는 오버레이 배너에 영문으로 찍힌다 — cv2 폰트에 한글이 없다:",
         "`no detection` 검출 0 · `area` 면적비 범위 밖 · `fragmented cc_main` 조각남 ·",
         "`solidity` 볼록성 낮음(≈ 배경/그림자를 함께 집음) · `border (background?)` 테두리 접촉 과다 ·",
         "`in_region` `rel_y` `rel_area` — flange 전용 **물체 기준** 값(아래).",
         "",
         "### flange 판정은 «물체 기준» 이다",
         "",
         f"같은 이미지의 `full` 최선 마스크(`--ref-full-slug {a.ref_full_slug}`)를 **기준 프레임**으로 쓴다.",
         "오버레이의 **자홍 윤곽 = 그 기준 마스크**, **자홍 가로선 = 물체 높이의 위 28%** 다.",
         "«초록이 자홍 안에, 자홍 선 위에 있는가» 가 판정의 실질이다.",
         "",
         "| 값 | 뜻 | 통과 조건 |",
         "|---|---|---|",
         "| `in_region` | flange 마스크 중 **«몸체 ∪ 몸체 바로 위»** 에 든 비율 | ≥ 0.80 |",
         "| `rel_y` | 몸체 bbox 안에서의 상대 높이 (0=꼭대기, 음수=몸체보다 위) | ≤ 0.28 |",
         "| `rel_area` | 몸체 면적 대비 flange 면적 | 0.004 ~ 0.30 |",
         "",
         "🔴 두 번 고쳤다. **(1) 이미지 기준 `cy`** → **거짓 통과**. 정면 문의 링과 옆면 손잡이가",
         "«상면 플랜지» 로 9/9 통과했다 — 물체가 화면 어디에 있느냐에 따라 `cy` 는 아무 뜻이 없다.",
         "**(2) 몸체 마스크 포함 검사** → **거짓 기각**. `full` 프롬프트가 상면 플랜지를 몸체로 안 보고",
         "빼 버리는 경우가 있어(주황 2장) 진짜 플랜지가 «몸체 밖» 으로 떨어졌다. flange 는 정의상",
         "몸체 **위로 튀어나오므로** 허용 영역에 «몸체 바로 위» 를 더했다.",
         "**이 기준 마스크가 틀리면 flange 판정도 함께 틀린다** — GT 가 아니라 대리다.",
         "",
         "🔴 **«통과 수» 를 프롬프트 서열로 읽으면 색 지정 프롬프트를 오독한다.** 색 지정은",
         "**몸체 색이 맞을 때만** 걸리고 아니면 조용히 검출 0 이 된다 — 전체 평균에서는 나빠 보이는데",
         "제 색에서는 최선일 수 있다. 그래서 **외관 교차표를 따로 낸다**(아래).",
         ""]

    ap_order = ["black", "orange", "clear", "twotone", "unknown"]
    apps = [x for x in ap_order if x in set(app.values())]
    if apps:
        L += ["## 이미지 × 몸체 외관", "",
              "| 외관 | 이미지 |", "|---|---|"]
        for x in apps:
            L.append(f"| **{x}** | " + ", ".join(f"`{k}`" for k in stems if app[k] == x) + " |")
        L += ["", f"라벨 출처: `{meta.get('appearance_src') or '—'}` (육안 분류, 고쳐도 된다)", ""]

    for t in targets:
        sub = [r for r in rows if r["target"] == t]
        if not sub:
            continue
        slugs = []
        for r in sub:
            if r["slug"] not in [s[0] for s in slugs]:
                slugs.append((r["slug"], r["category"], r["prompt"]))
        agg = []
        for sl, cat, pr in slugs:
            g = [r for r in sub if r["slug"] == sl]
            npass = sum(r["ok"] for r in g)
            ndet = sum(1 for r in g if r["n_inst"] > 0)
            sc = [r["score"] for r in g if r["n_inst"] > 0]
            af = [r["area_frac"] for r in g if r["ok"]]
            agg.append({"slug": sl, "cat": cat, "prompt": pr, "npass": npass,
                        "ndet": ndet, "n": len(g),
                        "score_med": float(np.median(sc)) if sc else 0.0,
                        "inst_med": float(np.median([r["n_inst"] for r in g])),
                        "area_med": float(np.median(af)) if af else 0.0})
        agg.sort(key=lambda d: (-d["npass"], -d["score_med"]))

        L += [f"## target = `{t}` — 프롬프트 서열 (휴리스틱 통과 수 기준)", "",
              "| 프롬프트 | 범주 | 통과 | 검출 | score 중앙 | 인스턴스 중앙 | 면적비 중앙 |",
              "|---|---|---|---|---|---|---|"]
        for d in agg:
            L.append(f"| `{d['prompt']}` | {d['cat']} | **{d['npass']}/{d['n']}** | "
                     f"{d['ndet']}/{d['n']} | {d['score_med']:.3f} | {d['inst_med']:.0f} | "
                     f"{d['area_med']:.3f} |")
        L += ["", f"→ `sheets/matrix__{t}.png`", ""]

        # ── 2요인 교차표 ────────────────────────────────────────────────────
        # `category` 가 `D:<서술어>/A:<소속구>` 꼴이면 요인별로 합쳐서 낸다.
        # ★ 프롬프트 하나하나의 서열보다 **어느 축이 지배하는가**가 이전 가능한 결론이다.
        fac = [(re.match(r"D:([^/]+)/A:(.+)$", r["category"]), r) for r in sub]
        fac = [(m.group(1), m.group(2), r) for m, r in fac if m]
        if fac:
            ds = list(dict.fromkeys(d for d, _, _ in fac))
            as_ = list(dict.fromkeys(x for _, x, _ in fac))
            cell = {}
            for d, x, r in fac:
                cell.setdefault((d, x), []).append(r["ok"])
            L += [f"### target = `{t}` — **2요인 교차표** (행 = 서술어, 열 = 소속구)", "",
                  "| 서술어 \\ 소속구 | " + " | ".join(f"`{x}`" for x in as_) + " | 행 평균 |",
                  "|---|" + "---|" * (len(as_) + 1)]
            for d in ds:
                v = [cell.get((d, x), []) for x in as_]
                tot = [k for g in v for k in g]
                L.append(f"| **{d}** | " +
                         " | ".join(f"{sum(g)}/{len(g)}" if g else "—" for g in v) +
                         f" | {100 * sum(tot) / max(len(tot), 1):.0f}% |")
            col = [[k for d in ds for k in cell.get((d, x), [])] for x in as_]
            L += ["| **열 평균** | " +
                  " | ".join(f"**{100 * sum(g) / max(len(g), 1):.0f}%**" for g in col) + " | |",
                  "",
                  "🔴 **평균만 보면 안 된다 — 상호작용이 있다.** 강한 서술어는 소속구를 붙이면",
                  "나빠지고, 약한 서술어는 소속구가 살려낸다. 표 안의 칸을 보고 고른다.", ""]

        # ── 외관 교차표 ─────────────────────────────────────────────────────
        if apps:
            cnt = {x: sum(1 for k in stems if app[k] == x) for x in apps}
            L += [f"### target = `{t}` — **외관별** 통과 수 (분모는 그 외관의 장수)", "",
                  "| 프롬프트 | " + " | ".join(f"{x} ({cnt[x]})" for x in apps) + " | 전체 |",
                  "|---|" + "---|" * (len(apps) + 1)]
            for d in agg:
                cells = []
                for x in apps:
                    g = [r for r in sub if r["slug"] == d["slug"] and r["appearance"] == x]
                    k = sum(r["ok"] for r in g)
                    cells.append(f"**{k}**" if k == len(g) and g else str(k))
                L.append(f"| `{d['prompt']}` | " + " | ".join(cells) +
                         f" | {d['npass']}/{d['n']} |")
            L += ["", "★ **한 외관에서만 굵은 프롬프트**는 «나쁜» 게 아니라 «조건부» 다 — "
                  "`--preset` 과 짝지어 쓰면 된다. 전 외관에서 굵은 것만이 «몸체 색을 몰라도 되는» 기본값이다.",
                  ""]

        # ── 휴리스틱이 떨어뜨렸지만 볼 값어치가 있는 것 ─────────────────────
        drop = [r for r in sub if not r["ok"] and r["n_inst"] > 0 and r["score"] >= 0.30]
        drop.sort(key=lambda r: -r["score"])
        if drop:
            L += [f"### target = `{t}` — 🔴 휴리스틱이 떨어뜨렸지만 **score 가 높은** 것 (눈으로 볼 것)", "",
                  "자동 필터는 형상만 본다. score 가 높은데 떨어졌다면 «모델은 확신하는데 모양이",
                  "예상과 다른» 경우다 — 필터가 틀렸을 수도, 정말 엉뚱한 것을 집었을 수도 있다.", "",
                  "| 이미지 | 외관 | 프롬프트 | score | 떨어진 사유 | 오버레이 |", "|---|---|---|---|---|---|"]
            for r in drop[:20]:
                L.append(f"| `{r['image']}` | {r['appearance']} | `{r['prompt']}` | "
                         f"{r['score']:.3f} | `{r['why']}` | "
                         f"`ov/{r['image']}/{t}/{r['slug']}.png` |")
            if len(drop) > 20:
                L.append(f"| … | | 나머지 {len(drop) - 20}건은 `results.csv` 에서 "
                         "`ok==0 & score>=0.3` 으로 | | | |")
            L.append("")

        L += [f"### target = `{t}` — 이미지별로 통과한 프롬프트", "",
              "| 이미지 | 외관 | 통과 수 | 최고 score 프롬프트 |", "|---|---|---|---|"]
        for st in stems:
            g = [r for r in sub if r["image"] == st]
            okg = [r for r in g if r["ok"]]
            best = max(okg, key=lambda r: r["score"]) if okg else None
            L.append(f"| `{st}` | {app[st]} | {len(okg)}/{len(g)} | " +
                     (f"`{best['prompt']}` (score {best['score']:.3f}, "
                      f"면적 {best['area_frac']:.3f})" if best else "— **전멸**") + " |")
        L += ["", "🔴 «전멸» 행은 프롬프트가 아니라 **이미지 조건**(배경·크롭·색)을 의심한다.", ""]

        dead = [d for d in agg if d["ndet"] == 0]
        if dead:
            L += [f"### target = `{t}` — 검출 0 (개념 자체를 못 잡는다)", "",
                  ", ".join(f"`{d['prompt']}`" for d in dead), "",
                  "⚠️ 임계값 문제가 아니다 — `--confidence` 를 낮춰도 후보가 안 나온다는 뜻이다.", ""]

    L += ["## 다음에 할 것", "",
          "- 살아남은 프롬프트를 `run_group_a.py --sam3-text --text-prompt \"…\"` 로 **실촬영**에 건다",
          "- **전 외관에서 통과한 것 = 몸체 색을 몰라도 되는 기본값**, 한 외관에서만 통과한 것 =",
          "  `--preset` 과 짝지을 조건부 프롬프트. 둘을 섞어 «최선» 하나로 적으면 안 된다",
          "- 🔴 이 스윕은 **분할만** 잰다. 분할이 좋다고 pose 가 좋아진다는 보장이 없다",
          "  (§35-2n-② 가 «마스크는 맞는데 pose 가 틀렸다» 를 가르는 이유다). 최종 판정은 T그룹 전 체인에서 한다",
          "- 🔴 여기서 고른 프롬프트를 **같은 9장으로 검증하면 안 된다** — 고른 데이터와 검증 데이터가",
          "  같으면 검증이 아니다(§35-2o-4). 실촬영 20~40장에서 다시 확인한다",
          ""]
    (root / "report.md").write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
