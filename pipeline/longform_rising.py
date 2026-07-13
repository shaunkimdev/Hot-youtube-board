# -*- coding: utf-8 -*-
"""Build longform top3 and Rising Star from the discovered candidate pool."""
import datetime
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

KEY = os.environ["GOOGLE_API_KEY"]
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
RUN_DATE = os.environ.get("RUN_DATE") or datetime.date.today().isoformat()

rows = json.load(open(os.path.join(HERE, "candidates2.json"), encoding="utf-8"))

EXTRA_OFFICIAL = [
    "obs", "fnn", "jfa", "tv tokyo", "obs뉴스", "obs경인",
]


def extra_official(channel):
    text = (channel or "").lower()
    return any(token in text for token in EXTRA_OFFICIAL)


def http(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def load_previous_selected_ids():
    """Collect selected video ids from the latest archive before RUN_DATE."""
    archive_dir = os.path.join(PROJ, "site", "archive")
    if not os.path.isdir(archive_dir):
        return set()

    target = datetime.date.fromisoformat(RUN_DATE)
    dated_files = []
    for name in os.listdir(archive_dir):
        match = re.fullmatch(r"data_(\d{4}-\d{2}-\d{2})\.json", name)
        if not match:
            continue
        day = datetime.date.fromisoformat(match.group(1))
        if day < target:
            dated_files.append((day, os.path.join(archive_dir, name)))

    if not dated_files:
        return set()

    _, latest_path = max(dated_files, key=lambda item: item[0])
    payload = json.load(open(latest_path, encoding="utf-8"))
    video_ids = set()
    for bucket in ("rows", "rising"):
        for item in payload.get(bucket, []):
            match = re.search(r"[?&]v=([^&]+)", item.get("url", ""))
            if match:
                video_ids.add(match.group(1))
    return video_ids


PREV_SELECTED_IDS = load_previous_selected_ids()
rows = [row for row in rows if not extra_official(row["channel"])]

# Fetch channel ids and subscriber counts for every candidate.
video_ids = [row["video_id"] for row in rows]
video_to_channel = {}
for index in range(0, len(video_ids), 50):
    data = http(
        "https://www.googleapis.com/youtube/v3/videos?"
        + urllib.parse.urlencode(
            {"part": "snippet", "id": ",".join(video_ids[index:index + 50]), "key": KEY}
        )
    )
    for item in data.get("items", []):
        video_to_channel[item["id"]] = item["snippet"]["channelId"]

channel_ids = sorted(set(video_to_channel.values()))
channel_subscribers = {}
for index in range(0, len(channel_ids), 50):
    data = http(
        "https://www.googleapis.com/youtube/v3/channels?"
        + urllib.parse.urlencode(
            {"part": "statistics", "id": ",".join(channel_ids[index:index + 50]), "key": KEY}
        )
    )
    for item in data.get("items", []):
        stats = item.get("statistics", {})
        channel_subscribers[item["id"]] = (
            None
            if stats.get("hiddenSubscriberCount", False)
            else int(stats.get("subscriberCount", 0) or 0)
        )

for row in rows:
    channel_id = video_to_channel.get(row["video_id"])
    row["channel_id"] = channel_id
    row["subscribers"] = channel_subscribers.get(channel_id)


def is_short(row):
    title = row["title"].lower()
    return row["duration_sec"] <= 180 or "#shorts" in title or "#short" in title


long_rows = [row for row in rows if not is_short(row)]
print(f"pool {len(rows)} -> longform {len(long_rows)} (excluded shorts {len(rows) - len(long_rows)})")

MIN_VIEWS_RANK = 100_000
MIN_LIKE_RATIO = 0.001


def rank_eligible(row):
    return (
        row["views"] >= MIN_VIEWS_RANK
        and row.get("subscribers") is not None
        and row["subscribers"] > 0
        and row.get("likes", 0) / row["views"] >= MIN_LIKE_RATIO
    )


for row in long_rows:
    row["views_per_sub"] = (
        round(row["views"] / row["subscribers"], 2) if rank_eligible(row) else None
    )

json.dump(
    long_rows,
    open(os.path.join(HERE, "longform_all.json"), "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)


def pick_top(rows_for_topic, limit=3):
    fresh = [row for row in rows_for_topic if row["video_id"] not in PREV_SELECTED_IDS]
    ranked = [row for row in fresh if rank_eligible(row)]
    ranked.sort(key=lambda row: row["views_per_sub"], reverse=True)
    picks = ranked[:limit]
    if len(picks) < limit:
        seen_ids = {row["video_id"] for row in picks}
        fallback = [row for row in fresh if row["video_id"] not in seen_ids]
        fallback.sort(key=lambda row: (row["issue_score"], row["views"]), reverse=True)
        picks.extend(fallback[: limit - len(picks)])
    return picks


groups = defaultdict(list)
for row in long_rows:
    if row["topic"] != "기타":
        groups[(row["region"], row["topic"])].append(row)

top = {}
for key, rows_for_topic in groups.items():
    picks = pick_top(rows_for_topic)
    if picks:
        top[f"{key[0]}|{key[1]}"] = picks

json.dump(
    top,
    open(os.path.join(HERE, "top3_v3.json"), "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)

RISE_MIN_VIEWS = 200000
rising_candidates = [
    row for row in long_rows
    if row["video_id"] not in PREV_SELECTED_IDS
    and row["subscribers"] is not None
    and 0 < row["subscribers"] <= 10000
    and row["views"] >= RISE_MIN_VIEWS
]
for row in rising_candidates:
    row["views_per_sub"] = round(row["views"] / max(row["subscribers"], 1), 2)
rising_candidates.sort(key=lambda row: row["views_per_sub"], reverse=True)

seen_channels = set()
rising = []
for row in rising_candidates:
    if row["channel_id"] in seen_channels:
        continue
    seen_channels.add(row["channel_id"])
    rising.append(dict(row))
    if len(rising) >= 5:
        break

json.dump(
    rising,
    open(os.path.join(HERE, "rising.json"), "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)

order = ["핫이슈", "사건사고"]
for region in ["KR", "JP", "US"]:
    print("=" * 60, region)
    for topic in order:
        key = f"{region}|{topic}"
        picks = top.get(key, [])
        print(f"[{topic}] {len(picks)}건", end="  ")
        for item in picks:
            subscribers = item["subscribers"]
            subs_text = f"{subscribers:,}" if subscribers is not None else "비공개"
            vps = item["views_per_sub"] if item["views_per_sub"] is not None else "-"
            print(f"| {item['channel']}[{item['duration']}] 구독{subs_text}(조회/구독 {vps}배)", end="")
        print()

print("\n" + "=" * 60, "RISING STAR Best5 (구독<=1만, 조회수>=20만, 채널중복제거)")
for index, item in enumerate(rising, 1):
    print(
        f"{index}. [{item['region']}/{item['topic']}] {item['channel']} | "
        f"구독 {item['subscribers']:,} | 조회 {item['views']:,} | "
        f"구독대비 {item['views_per_sub']}배 | [{item['duration']}]"
    )
    print(f"   {item['title'][:50]} | {item['url']}")
