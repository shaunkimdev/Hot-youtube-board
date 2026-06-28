# -*- coding: utf-8 -*-
"""Search-based discovery for 재테크(personal finance) & 자기계발(self-development).

The mostPopular chart (discover2.py) carries no Education/personal-finance content
for KR/JP, so these two topics are collected via the Search API instead and appended
to candidates2.json in the SAME schema, so longform_rising.py / build_auto.py pick
them up automatically (top3 per region|topic). Longform only — 쇼츠 제외."""
import os, json, math, re, urllib.request, urllib.parse, datetime, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
KEY = os.environ["GOOGLE_API_KEY"]
NOW = datetime.datetime.now(datetime.timezone.utc)
HERE = os.path.dirname(os.path.abspath(__file__))
AFTER = (NOW - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
MIN_VIEWS = 20000  # niche topics view less than trending

# 3 seed queries per (topic, region) — keeps Search quota modest (~48 calls)
QUERIES = {
 "재테크": {"KR": ["재테크", "주식 투자", "부동산 투자"],
           "JP": ["投資 初心者", "新nisa", "資産運用"]},
 "자기계발": {"KR": ["자기계발", "동기부여", "공부법"],
            "JP": ["自己啓発", "モチベーション", "勉強法"]},
}
LANG = {"KR": "ko", "JP": "ja"}

# reuse the official-channel blocklist concept from discover2 (broadcasters/labels/brands)
OFFICIAL_TOKENS = ["- topic", " topic", "vevo", "공식", "公式", "엔터테인먼트", "레이블", "sbs", "mbc", "kbs",
 "jtbc", "tv조선", "채널a", "mbn", "ytn", "연합뉴스", "한국경제", "매일경제", "한경", "ニュース", "新聞",
 "nhk", "tbs", "テレビ", "증권방송", "経済テレビ", "기획재정부", "금융감독원"]
def is_official(title):
    t = (title or "").lower().strip()
    return any(x in t for x in OFFICIAL_TOKENS)

def http(url):
    with urllib.request.urlopen(url, timeout=30) as r: return json.load(r)

def hours_since(iso):
    try: return max((NOW - datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds()/3600, 0.5)
    except: return 999.0

def iso_dur(s):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m: return 0, ""
    h, mi, se = (int(x) if x else 0 for x in m.groups()); tot = h*3600 + mi*60 + se
    return tot, (f"{h}:{mi:02d}:{se:02d}" if h else f"{mi}:{se:02d}")

def native(region, t):
    for ch in t:
        o = ord(ch)
        if region == "KR" and (0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F): return True
        if region == "JP" and (0x3040 <= o <= 0x309F or 0x30A0 <= o <= 0x30FF): return True
    return False

def thumb(sn):
    th = sn.get("thumbnails", {})
    for k in ("maxres", "standard", "high", "medium", "default"):
        if k in th: return th[k]["url"]
    return ""

# ---- search: collect video ids per (region, topic) ----
vid_meta = {}   # video_id -> (region, topic)
for topic, regions in QUERIES.items():
    for region, qs in regions.items():
        for q in qs:
            for vd in ("medium", "long"):  # 롱폼만 (4~20분 + 20분초과), 쇼츠 자동 제외
                try:
                    d = http("https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(
                        {"part": "snippet", "type": "video", "order": "viewCount", "publishedAfter": AFTER,
                         "regionCode": region, "relevanceLanguage": LANG[region], "q": q,
                         "videoDuration": vd, "maxResults": 50, "key": KEY}))
                except Exception as e:
                    print("search err", topic, region, q, vd, e, file=sys.stderr); continue
                for it in d.get("items", []):
                    vid_meta.setdefault(it["id"]["videoId"], (region, topic))
print("search candidate videos:", len(vid_meta))

# ---- fetch full stats ----
ids = list(vid_meta)
rows = []
for i in range(0, len(ids), 50):
    d = http("https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode(
        {"part": "snippet,statistics,contentDetails,liveStreamingDetails", "id": ",".join(ids[i:i+50]), "key": KEY}))
    for it in d.get("items", []):
        if "liveStreamingDetails" in it: continue           # 라이브 제외
        region, topic = vid_meta[it["id"]]
        sn = it["snippet"]; st = it.get("statistics", {})
        title = sn.get("title", "")
        if not native(region, title): continue              # KR/JP 관련성
        if is_official(sn.get("channelTitle", "")): continue # 공식/방송/언론 채널 제외
        ds, dl = iso_dur(it.get("contentDetails", {}).get("duration", ""))
        if ds <= 180 or "#shorts" in title.lower() or "#short" in title.lower(): continue  # 쇼츠 제외
        views = int(st.get("viewCount", 0) or 0)
        if views < MIN_VIEWS: continue
        likes = int(st.get("likeCount", 0) or 0); comments = int(st.get("commentCount", 0) or 0)
        hrs = hours_since(sn.get("publishedAt", ""))
        issue = (views + 20*likes + 100*comments) / math.sqrt(hrs)
        rows.append({"region": region, "topic": topic, "category_id": 0,
            "video_id": it["id"], "url": f"https://www.youtube.com/watch?v={it['id']}", "title": title,
            "channel": sn.get("channelTitle", ""), "published_at": sn.get("publishedAt", ""), "hours_since": round(hrs, 1),
            "duration_sec": ds, "duration": dl, "views": views, "likes": likes, "comments": comments,
            "views_per_hour": round(views/hrs), "issue_score": round(issue), "thumbnail": thumb(sn),
            "description": (sn.get("description", "") or "")[:600], "is_live": False})

# ---- merge into candidates2.json (dedup by region+video_id) ----
path = os.path.join(HERE, "candidates2.json")
existing = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
seen = {(r["region"], r["video_id"]) for r in existing}
added = 0
for r in rows:
    k = (r["region"], r["video_id"])
    if k in seen: continue
    seen.add(k); existing.append(r); added += 1
json.dump(existing, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"discover_topics: matched {len(rows)} longform videos, appended {added} new to candidates2.json")
from collections import Counter
c = Counter((r["region"], r["topic"]) for r in rows)
for region in ("KR", "JP"):
    for topic in ("재테크", "자기계발"):
        cnt = c.get((region, topic), 0)
        print(f"  [{region}] {topic}: {cnt}건", end="")
        best = sorted([r for r in rows if r["region"] == region and r["topic"] == topic],
                      key=lambda x: x["issue_score"], reverse=True)[:3]
        for v in best: print(f" | {v['channel'][:14]}[{v['duration']}]", end="")
        print()
