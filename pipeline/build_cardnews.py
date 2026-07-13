# -*- coding: utf-8 -*-
"""Build today's per-country cardnews from pipeline/scratch/info_*.json."""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from cardnews_caption import save_caption
from cardnews_gen import make_cover, make_segment_card

ROOT = HERE.parent
SCRATCH = HERE / "scratch"
THUMBS = HERE / "thumbs"
DATE = os.environ.get("RUN_DATE") or datetime.date.today().isoformat()
DATE_DOT = DATE.replace("-", ".")
OUT_ROOT = ROOT / f"카드뉴스_{DATE}"

COUNTRIES = [
    ("한국", "KR"),
    ("일본", "JP"),
    ("미국", "US"),
]


def safe_name(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", value or "").strip()


def load_items(country: str) -> list[dict]:
    return json.loads((SCRATCH / f"info_{country}.json").read_text(encoding="utf-8"))


def build_caption_lines(country: str, top3: list[dict], rising: dict | None) -> list[str]:
    lines = [
        f"{DATE} 기준 {country} 오늘의 카드뉴스입니다.",
        "각 영상은 자막 내용을 기준으로 3개 카드로 나눴고, 각 카드에는 실제 장면 캡처를 넣었습니다.",
        "",
    ]
    for item in top3 + ([rising] if rising else []):
        if not item:
            continue
        label = f"TOP {item['rank']}" if item.get("type") == "top3" else "급상승"
        lines.append(f"[{label}] {item['title_full']}")
        lines.append(f"채널: {item['channel']} | 조회수: {item['views_text']}")
        for segment in item["segments"]:
            lines.append(f"{segment['label']} {segment['title']} | {segment['summary']}")
            lines.append(f"소개: {segment['note']}")
        lines.append(f"링크: {item['url']}")
        lines.append("")
    return lines


def build_country(country: str, code: str) -> None:
    items = load_items(country)
    top3 = [item for item in items if item.get("type") == "top3"]
    top3.sort(key=lambda item: item["rank"])
    rising = next((item for item in items if item.get("type") == "rising"), None)
    page_total = 1 + len(top3) * 3 + (3 if rising else 0)

    out_dir = OUT_ROOT / country
    out_dir.mkdir(parents=True, exist_ok=True)

    rank_lines = [(None, item["title_card"], item["channel"]) for item in top3]
    if rising:
        rank_lines.append(("star", rising["title_card"], rising["channel"]))
    make_cover(
        top3[0]["video_id"],
        str(THUMBS),
        str(out_dir / "01_cover.png"),
        code,
        country,
        DATE_DOT,
        page_total,
        rank_lines,
    )

    page_num = 2
    for item in top3 + ([rising] if rising else []):
        if not item:
            continue
        header_suffix = "급상승" if item.get("type") == "rising" else f"TOP {item['rank']}"
        header = f"{country} {header_suffix}"
        for segment in item["segments"]:
            out_name = (
                f"{page_num:02d}_{item['type']}_{item['video_id']}_{segment['label'].replace('/', '-')}_"
                f"{safe_name(item['channel'])}.png"
            )
            make_segment_card(
                item["video_id"],
                str(THUMBS),
                str(out_dir / out_name),
                segment.get("image"),
                page_num,
                page_total,
                code,
                header,
                segment["label"],
                item["title_card"],
                item["channel"],
                item["views_text"],
                segment["title"],
                segment["summary"],
                segment["note"],
            )
            page_num += 1

    save_caption(str(out_dir / f"캡션_{country}.docx"), build_caption_lines(country, top3, rising))
    print(f"[build_cardnews] {country}: {page_total} pages -> {out_dir}")


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    for country, code in COUNTRIES:
        build_country(country, code)


if __name__ == "__main__":
    main()
