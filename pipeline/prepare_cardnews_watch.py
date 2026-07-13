"""Prepare cardnews info blocks with transcript-led 3-part segments."""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from watch_runtime import load_watch, run_watch

ROOT = HERE.parent
SITE = ROOT / "site" / "data.json"
SCRATCH = HERE / "scratch"
THUMBS = HERE / "thumbs"
DATE = os.environ.get("RUN_DATE") or datetime.date.today().isoformat()

COUNTRY_BY_REGION = {
    "KR": ("한국", "🇰🇷"),
    "JP": ("일본", "🇯🇵"),
    "US": ("미국", "🇺🇸"),
}
MANDATORY_TOPIC_BY_REGION = {
    "KR": "일본핫이슈",
}
SEGMENT_TITLES = ["초반핵심", "중반핵심", "후반핵심"]


def short_text(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def strip_review_markers(value: str) -> str:
    text = value or ""
    patterns = [
        r"자동\s*요약[^.!\n]*",
        r"미검수[^.!\n]*",
        r"자동\s*요약\s*\(.*?\)",
        r"미검수\s*\(.*?\)",
    ]
    for pattern in patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return " ".join(text.split()).strip()


def parse_timecode(value: str) -> float | None:
    match = re.search(r"(?:\d+:)?\d+:\d+", value or "")
    if not match:
        return None
    total = 0.0
    for part in match.group(0).split(":"):
        total = total * 60 + float(part)
    return total


def format_views(number: int | None) -> str:
    number = int(number or 0)
    if number >= 10000:
        return f"{number / 10000:.1f}만"
    return f"{number:,}"


def format_ratio(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}배"


def transcript_lines(text: str) -> list[tuple[float, str]]:
    lines: list[tuple[float, str]] = []
    for raw in (text or "").splitlines():
        match = re.match(r"\[([0-9:]+)\]\s*(.*)", raw.strip())
        if not match:
            continue
        seconds = parse_timecode(match.group(1))
        content = strip_review_markers(re.sub(r"\s+", " ", match.group(2)).strip(" >"))
        if seconds is None or not content:
            continue
        if content.lower() in {"[music]", "[__]"}:
            continue
        lines.append((seconds, content))
    return lines


def video_duration(path: str) -> float:
    if not path or not Path(path).exists():
        return 0.0
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        return float((result.stdout or "").strip())
    except ValueError:
        return 0.0


def nearest_frame(frames: list[dict], target_seconds: float) -> dict | None:
    if not frames:
        return None
    return min(frames, key=lambda frame: abs(frame.get("seconds", 0.0) - target_seconds))


def fallback_segment_text(row: dict, index: int) -> tuple[str, str]:
    summary = strip_review_markers(row.get("summary", ""))
    tip = strip_review_markers(row.get("tip", ""))
    parts = [part for part in re.split(r"(?<=[.!?])\s+|(?<=다\.)\s+", f"{summary} {tip}".strip()) if part]
    main = parts[index] if index < len(parts) else summary or row.get("title", "")
    note = parts[index + 1] if index + 1 < len(parts) else tip or summary or row.get("title", "")
    return short_text(main, 58), short_text(note, 74)


def build_segments_from_transcript(row: dict, watch: dict, duration: float) -> list[dict]:
    transcript = transcript_lines(watch.get("transcript", ""))
    frames = sorted(watch.get("frames", []), key=lambda item: item.get("seconds", 0.0))
    if not transcript:
        return []

    max_seconds = max([duration] + [sec for sec, _ in transcript] + [60.0])
    boundaries = [0.0, max_seconds / 3, max_seconds * 2 / 3, max_seconds]
    segments = []
    for index in range(3):
        start = boundaries[index]
        end = boundaries[index + 1]
        segment_lines = [text for sec, text in transcript if start <= sec <= end]
        main = " ".join(segment_lines[:2]).strip()
        intro = " ".join(segment_lines[2:4]).strip()
        if not main:
            main, intro = fallback_segment_text(row, index)
        else:
            main = short_text(main, 58)
            intro = short_text(intro or fallback_segment_text(row, index)[1], 74)
        target = (start + end) / 2
        frame = nearest_frame(frames, target)
        segments.append(
            {
                "index": index + 1,
                "label": f"{index + 1}/3",
                "range": f"{int(start // 60)}:{int(start % 60):02d}~{int(end // 60)}:{int(end % 60):02d}",
                "title": SEGMENT_TITLES[index],
                "summary": strip_review_markers(main),
                "note": strip_review_markers(intro),
                "image": frame.get("path") if frame else str(THUMBS / f"{row['video_id']}.jpg"),
                "seconds": target,
            }
        )
    return segments


def build_segments(row: dict, watch: dict) -> list[dict]:
    duration = video_duration(watch.get("source_video", ""))
    transcript_segments = build_segments_from_transcript(row, watch, duration)
    if transcript_segments:
        return transcript_segments

    frames = sorted(watch.get("frames", []), key=lambda item: item.get("seconds", 0.0))
    max_seconds = max([frame.get("seconds", 0.0) for frame in frames] + [duration, 60.0])
    segments = []
    for index in range(3):
        start = max_seconds * index / 3
        end = max_seconds * (index + 1) / 3
        target = (start + end) / 2
        frame = nearest_frame(frames, target)
        main, intro = fallback_segment_text(row, index)
        segments.append(
            {
                "index": index + 1,
                "label": f"{index + 1}/3",
                "range": f"{int(start // 60)}:{int(start % 60):02d}~{int(end // 60)}:{int(end % 60):02d}",
                "title": SEGMENT_TITLES[index],
                "summary": main,
                "note": intro,
                "image": frame.get("path") if frame else str(THUMBS / f"{row['video_id']}.jpg"),
                "seconds": target,
            }
        )
    return segments


def select_region_rows(payload: dict, region: str) -> list[dict]:
    rows = [row for row in payload["rows"] if row["region"] == region]
    rows.sort(
        key=lambda row: (
            row.get("views_per_sub") is not None,
            row.get("views_per_sub") or -1.0,
            row.get("issue") or 0,
            row.get("views") or 0,
        ),
        reverse=True,
    )
    selected: list[dict] = []
    seen = set()
    mandatory_topic = MANDATORY_TOPIC_BY_REGION.get(region)
    if mandatory_topic:
        mandatory_rows = [row for row in rows if row.get("topic") == mandatory_topic]
        if mandatory_rows:
            row = mandatory_rows[0]
            video_id = video_id_from_url(row["url"])
            seen.add(video_id)
            enriched = dict(row)
            enriched["video_id"] = video_id
            selected.append(enriched)
    for row in rows:
        video_id = video_id_from_url(row["url"])
        if video_id in seen:
            continue
        seen.add(video_id)
        enriched = dict(row)
        enriched["video_id"] = video_id
        selected.append(enriched)
        if len(selected) >= 3:
            break
    return selected


def video_id_from_url(url: str) -> str:
    match = re.search(r"[?&]v=([^&]+)", url)
    return match.group(1) if match else url.rsplit("/", 1)[-1]


def select_rising(payload: dict, region: str) -> dict | None:
    for row in payload.get("rising", []):
        if row["region"] == region:
            enriched = dict(row)
            enriched["video_id"] = video_id_from_url(row["url"])
            return enriched
    return None


def prepare_entry(row: dict, entry_type: str, rank: int) -> dict:
    video = {
        "video_id": row["video_id"],
        "url": row["url"],
        "title": row["title"],
        "channel": row["channel"],
    }
    watch = load_watch(row["video_id"])
    if not watch or (not watch.get("frames") and not watch.get("transcript")):
        watch = run_watch(video, max_frames=12, force=False)
    segments = build_segments(row, watch)

    country, flag = COUNTRY_BY_REGION[row["region"]]
    return {
        "type": entry_type,
        "rank": rank,
        "country": country,
        "flag": flag,
        "region": row["region"],
        "video_id": row["video_id"],
        "title_full": row["title"],
        "title_card": short_text(row["title"], 34),
        "channel": row["channel"],
        "views_text": format_views(row.get("views")),
        "subs_text": format_views(row.get("subscribers")),
        "ratio_text": format_ratio(row.get("views_per_sub")),
        "summary": short_text(strip_review_markers(row.get("summary", "")), 120),
        "why": short_text(strip_review_markers(row.get("tip", "")), 120),
        "url": row["url"],
        "segments": segments,
    }


def main() -> None:
    payload = json.loads(SITE.read_text(encoding="utf-8"))
    SCRATCH.mkdir(parents=True, exist_ok=True)
    THUMBS.mkdir(parents=True, exist_ok=True)

    for region, (country, _) in COUNTRY_BY_REGION.items():
        items = [prepare_entry(row, "top3", rank) for rank, row in enumerate(select_region_rows(payload, region), 1)]
        rising = select_rising(payload, region)
        top_ids = {item["video_id"] for item in items}
        if rising and rising["video_id"] not in top_ids:
            items.append(prepare_entry(rising, "rising", len(items) + 1))
        out_path = SCRATCH / f"info_{country}.json"
        out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[prepare_cardnews_watch] {country}: {len(items)} items -> {out_path}")


if __name__ == "__main__":
    main()
