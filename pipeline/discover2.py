# -*- coding: utf-8 -*-
"""Search-API discovery for fixed categories, per region (KR/JP/US only).

Categories:
- 핫이슈
- 사건사고

Rules:
- Personal creator channels only
- Exclude LIVE streams
- Longform only (4~20 minutes from search, then shorts filtered again)
- Search-API query based collection
"""
import datetime
import io
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

KEY = os.environ["GOOGLE_API_KEY"]
NOW = datetime.datetime.now(datetime.timezone.utc)
HERE = os.path.dirname(os.path.abspath(__file__))
AFTER = (NOW - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
REGIONS = ["KR", "JP", "US"]
LANG = {"KR": "ko", "JP": "ja", "US": "en"}
MIN_VIEWS = 20000

QUERIES = {
    "핫이슈": {
        "KR": ["핫이슈", "이슈 분석"],
        "JP": ["話題 ニュース", "トレンド 解説"],
        "US": ["viral issue commentary", "trending topic breakdown"],
    },
    "사건사고": {
        "KR": ["사건사고", "사건 사고 분석"],
        "JP": ["事件事故", "事件 解説"],
        "US": ["incident commentary", "crime case breakdown"],
    }
}

OFFICIAL_TOKENS = [
    "- topic",
    " topic",
    "official",
    "vevo",
    "records",
    "records japan",
    "music",
    "label",
    "entertainment",
    "news",
    "일보",
    "신문",
    "방송",
    "뉴스",
    "공식",
    "언론",
    "연합뉴스",
    "sbs",
    "mbc",
    "kbs",
    "jtbc",
    "ytn",
    "mbn",
    "채널a",
    "tv조선",
    "nhk",
    "ann",
    "fnn",
    "tbs",
    "tv asahi",
    "nippon tv",
    "reuters",
    "bloomberg",
    "cnn",
    "fox news",
    "nbc news",
    "abc news",
    "cbs news",
    "msnbc",
    "bbc",
    "itv",
    "sky news",
    "the guardian",
    "the new york times",
    "washington post",
    "associated press",
    "npr",
    "league",
    "lck",
    "lpl",
    "lec",
    "lcs",
    "kbo",
    "npb",
    "j.league",
    "premier league",
    "riot games",
    "nexon",
    "apple",
    "google",
    "microsoft",
    "samsung",
    "lg",
    "tourism",
    "official artist",
]


def is_official(title):
    text = (title or "").lower().strip()
    return any(token in text for token in OFFICIAL_TOKENS)


def http(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def hours_since(iso):
    try:
        published = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return max((NOW - published).total_seconds() / 3600, 0.5)
    except Exception:
        return 999.0


def iso_dur(value):
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0, ""
    hours, minutes, seconds = (int(part) if part else 0 for part in match.groups())
    total = hours * 3600 + minutes * 60 + seconds
    label = f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
    return total, label


def native(region, text):
    if region == "KR":
        return any(
            0xAC00 <= ord(ch) <= 0xD7A3
            or 0x1100 <= ord(ch) <= 0x11FF
            or 0x3130 <= ord(ch) <= 0x318F
            for ch in text
        )
    if region == "JP":
        return any(0x3040 <= ord(ch) <= 0x309F or 0x30A0 <= ord(ch) <= 0x30FF for ch in text)
    if region == "US":
        foreign_ranges = (
            (0xAC00, 0xD7A3),
            (0x1100, 0x11FF),
            (0x3130, 0x318F),
            (0x3040, 0x30FF),
            (0x4E00, 0x9FFF),
            (0x0600, 0x06FF),
            (0x0400, 0x04FF),
            (0x0E00, 0x0E7F),
            (0x0590, 0x05FF),
            (0x0370, 0x03FF),
            (0x0900, 0x097F),
            (0x0980, 0x09FF),
            (0x0A00, 0x0A7F),
            (0x0A80, 0x0AFF),
            (0x0B80, 0x0BFF),
            (0x0C00, 0x0C7F),
            (0x0C80, 0x0CFF),
            (0x0D00, 0x0D7F),
        )
        return not any(any(lo <= ord(ch) <= hi for lo, hi in foreign_ranges) for ch in text)
    return False


def thumb(snippet):
    thumbs = snippet.get("thumbnails", {})
    for key in ("maxres", "standard", "high", "medium", "default"):
        if key in thumbs:
            return thumbs[key]["url"]
    return ""


errors = []
vid_meta = {}
for topic, regions in QUERIES.items():
    for region, queries in regions.items():
        for query in queries:
            try:
                data = http(
                    "https://www.googleapis.com/youtube/v3/search?"
                    + urllib.parse.urlencode(
                        {
                            "part": "snippet",
                            "type": "video",
                            "order": "viewCount",
                            "publishedAfter": AFTER,
                            "regionCode": region,
                            "relevanceLanguage": LANG[region],
                            "q": query,
                            "videoDuration": "medium",
                            "maxResults": 50,
                            "key": KEY,
                        }
                    )
                )
            except Exception as exc:
                errors.append(f"{region}/{topic}/{query}: {exc}")
                print("search err", topic, region, query, exc, file=sys.stderr)
                continue

            for item in data.get("items", []):
                vid_meta.setdefault(item["id"]["videoId"], (region, topic))

print("search candidate videos:", len(vid_meta))

ids = list(vid_meta)
rows = []
n_live = 0
n_official = 0
for index in range(0, len(ids), 50):
    data = http(
        "https://www.googleapis.com/youtube/v3/videos?"
        + urllib.parse.urlencode(
            {
                "part": "snippet,statistics,contentDetails,liveStreamingDetails",
                "id": ",".join(ids[index:index + 50]),
                "key": KEY,
            }
        )
    )
    for item in data.get("items", []):
        video_id = item["id"]
        region, topic = vid_meta[video_id]
        if "liveStreamingDetails" in item:
            n_live += 1
            continue

        snippet = item["snippet"]
        stats = item.get("statistics", {})
        title = snippet.get("title", "")
        if not native(region, title):
            continue
        if is_official(snippet.get("channelTitle", "")):
            n_official += 1
            continue

        duration_sec, duration_label = iso_dur(item.get("contentDetails", {}).get("duration", ""))
        if duration_sec <= 180 or "#shorts" in title.lower() or "#short" in title.lower():
            continue

        views = int(stats.get("viewCount", 0) or 0)
        if views < MIN_VIEWS:
            continue

        likes = int(stats.get("likeCount", 0) or 0)
        comments = int(stats.get("commentCount", 0) or 0)
        hrs = hours_since(snippet.get("publishedAt", ""))
        issue = (views + 20 * likes + 100 * comments) / math.sqrt(hrs)
        rows.append(
            {
                "region": region,
                "topic": topic,
                "category_id": 0,
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": title,
                "channel": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "hours_since": round(hrs, 1),
                "duration_sec": duration_sec,
                "duration": duration_label,
                "views": views,
                "likes": likes,
                "comments": comments,
                "views_per_hour": round(views / hrs),
                "issue_score": round(issue),
                "thumbnail": thumb(snippet),
                "description": (snippet.get("description", "") or "")[:600],
                "is_live": False,
            }
        )

groups = defaultdict(list)
for row in rows:
    groups[(row["region"], row["topic"])].append(row)

top = {}
for key, values in groups.items():
    values.sort(key=lambda row: row["issue_score"], reverse=True)
    top[f"{key[0]}|{key[1]}"] = values[:3]

json.dump(top, open(os.path.join(HERE, "top3_v2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(rows, open(os.path.join(HERE, "candidates2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"personal non-live videos: {len(rows)} | excluded live: {n_live} | excluded official: {n_official}")

ORDER = list(QUERIES.keys())
for region in REGIONS:
    print("=" * 60, region)
    for topic in ORDER:
        picks = top.get(f"{region}|{topic}", [])
        print(f"[{topic}] {len(picks)}건")
        for index, item in enumerate(picks, 1):
            print(
                f"  {index}. {item['channel']} [{item['duration']}] "
                f"issue={item['issue_score']:,} :: {item['title'][:40]}"
            )

if errors and not rows:
    print(
        f"FATAL: all {len(errors)} YouTube API calls failed, 0 videos collected. "
        f"First error: {errors[0]}",
        file=sys.stderr,
    )
    sys.exit(1)
