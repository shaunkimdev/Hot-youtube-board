# -*- coding: utf-8 -*-
"""Build today's per-country Instagram cardnews (PNG cards + docx caption)
from the info_*.json blocks under pipeline/scratch/, using cardnews_gen.py
(Pillow renderer) and cardnews_caption.py (docx writer) per cardnews_design.md."""
import json
import os
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cardnews_gen import make_cover, make_body
from cardnews_caption import save_caption

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SCRATCH = os.path.join(HERE, "scratch")
THUMBS = os.path.join(HERE, "thumbs")
DATE = "2026-07-09"
DATE_DOT = "2026.07.09"

COUNTRY_CODE = {"한국": "KR", "일본": "JP", "미국": "US"}
OUT_ROOT = os.path.join(PROJ, f"카드뉴스_{DATE}")


def vid(url):
    m = re.search(r"[?&]v=([^&]+)", url)
    return m.group(1) if m else url.rsplit("/", 1)[-1]


def safe(name):
    return re.sub(r'[\\/:*?"<>|]', "", name)


def load(country):
    with open(os.path.join(SCRATCH, f"info_{country}.json"), encoding="utf-8") as f:
        items = json.load(f)
    top3 = [it for it in items if it.get("type", "top3") == "top3"]
    top3.sort(key=lambda it: it["rank"])
    rising = next((it for it in items if it.get("type") == "rising"), None)
    return top3, rising


def build_country(country):
    code = COUNTRY_CODE[country]
    top3, rising = load(country)
    page_total = 5 if rising else 4
    out_dir = os.path.join(OUT_ROOT, country)
    os.makedirs(out_dir, exist_ok=True)

    rank_lines = [(None, it["제목_카드축약"], it["채널"]) for it in top3]
    if rising:
        rank_lines.append(("star", rising["제목_카드축약"], rising["채널"]))

    make_cover(
        vid(top3[0]["링크"]), THUMBS,
        os.path.join(out_dir, "01_표지.png"),
        code, country, DATE_DOT, page_total, rank_lines,
    )

    for it in top3:
        out_name = f"{it['rank']+1:02d}_{country}{it['rank']}위_{safe(it['채널'])}.png"
        make_body(
            vid(it["링크"]), THUMBS,
            os.path.join(out_dir, out_name),
            it["rank"] + 1, page_total, code,
            f"{country} {it['rank']}위", it["채널"],
            it["제목_카드축약"], it["소개"], is_rising=False,
        )

    if rising:
        out_name = f"{page_total:02d}_라이징_{safe(rising['채널'])}.png"
        rising_desc = rising["소개"] + f" 지금 급상승 중인 신흥 채널로, 구독자 대비 {rising['구독자대비조회수']} 터졌습니다. 팔로우·저장 ✅"
        make_body(
            vid(rising["링크"]), THUMBS,
            os.path.join(out_dir, out_name),
            page_total, page_total, code,
            "", rising["채널"],
            rising["제목_카드축약"], rising_desc, is_rising=True,
        )

    build_caption(country, top3, rising, out_dir)
    print(f"[{country}] {page_total}장 완료 -> {out_dir}")


def block(flag, country, label, it):
    lines = [
        f"{flag} {country} {label}",
        it["제목_한글"],
        f"📺 채널: {it['채널']}",
        f"👀 조회수: {it['조회수_만']}",
        f"🚀 구독자대비조회수: {it['구독자대비조회수']} (구독자 {it['구독자_만']} 대비)",
        f"📝 소개: {it['소개']}",
        f"✅ 봐야 하는 이유: {it['봐야하는이유']}",
        f"🔗 링크: {it['링크']}",
        "",
    ]
    return lines


def build_caption(country, top3, rising, out_dir):
    flag = top3[0]["flag"]
    top1 = top3[0]
    lines = [
        f"지금 {country}에서 가장 화제인 유튜브 영상 TOP3, 놓치면 후회합니다 🔥",
        f"{flag} {country}은 {top1['채널']}의 \"{top1['제목_카드축약']}\" 영상이 지금 실시간으로 터지며 1위에 올랐는데요.",
    ]
    if rising:
        lines.append(
            f"특히 급상승 라이징 스타 {rising['채널']}은 구독자 대비 조회수가 {rising['구독자대비조회수']}까지 폭발적으로 터진 화제의 신흥 채널입니다."
        )
    lines += [
        "내일은 또 어떤 영상이 터질지, 지금 저장하고 팔로우해서 가장 먼저 확인하세요 ✅",
        "",
        "—",
        "",
    ]
    for i, it in enumerate(top3, 1):
        lines += block(it["flag"], country, f"{i}위", it)
    if rising:
        lines += block(rising["flag"], country, "⭐ 라이징", rising)
    lines += ["—", ""]
    hashtag_extra = safe(top1["채널"]).replace(" ", "")
    lines.append(f"#유튜브순위 #유튜브이슈 #오늘의영상 #{country}유튜버")
    lines.append(f"#트렌드 #카드뉴스 #{hashtag_extra}")

    out_path = os.path.join(out_dir, f"캡션_{country}.docx")
    save_caption(out_path, lines)


if __name__ == "__main__":
    for country in ["한국", "일본", "미국"]:
        build_country(country)
