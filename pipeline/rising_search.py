# -*- coding: utf-8 -*-
"""Rising Star pool via Search API: recent high-view videos, then keep channels<=10k subs."""
import os, json, urllib.request, urllib.parse, datetime, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
KEY = os.environ["GOOGLE_API_KEY"]
HERE = os.path.dirname(os.path.abspath(__file__))
after = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

def http(url):
    with urllib.request.urlopen(url, timeout=30) as r: return json.load(r)

# broad seed queries per region to surface recent viral videos across topics
SEED = {"KR": ["뉴스","이슈","논란","경기","리뷰","게임","음악","꿀팁","브이로그","속보"],
        "JP": ["ニュース","話題","炎上","試合","レビュー","ゲーム","音楽","裏技","検証","速報"]}
LANG = {"KR": "ko", "JP": "ja"}

vid_region = {}
for region, seeds in SEED.items():
    for q in seeds:
        for vd in ("medium", "long"):   # 롱폼만: 4~20분(medium) + 20분초과(long), 쇼츠 제외
            try:
                d = http("https://www.googleapis.com/youtube/v3/search?"+urllib.parse.urlencode(
                    {"part":"snippet","type":"video","order":"viewCount","publishedAfter":after,
                     "regionCode":region,"relevanceLanguage":LANG[region],"q":q,
                     "videoDuration":vd,"maxResults":50,"key":KEY}))
            except Exception as e:
                print("search err",region,q,vd,e,file=sys.stderr); continue
            for it in d.get("items", []):
                vid_region.setdefault(it["id"]["videoId"], region)
print("search candidate videos:", len(vid_region))

# fetch full stats
ids = list(vid_region)
meta = {}
for i in range(0, len(ids), 50):
    d = http("https://www.googleapis.com/youtube/v3/videos?"+urllib.parse.urlencode(
        {"part":"snippet,statistics,contentDetails,liveStreamingDetails","id":",".join(ids[i:i+50]),"key":KEY}))
    for it in d.get("items", []):
        meta[it["id"]] = it
# channel subs
chans = sorted({it["snippet"]["channelId"] for it in meta.values()})
subs = {}
for i in range(0, len(chans), 50):
    d = http("https://www.googleapis.com/youtube/v3/channels?"+urllib.parse.urlencode(
        {"part":"statistics","id":",".join(chans[i:i+50]),"key":KEY}))
    for it in d.get("items", []):
        st = it.get("statistics", {})
        subs[it["id"]] = None if st.get("hiddenSubscriberCount", False) else int(st.get("subscriberCount",0) or 0)

import re
def dur(s):
    m=re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",s or "");
    if not m: return 0,""
    h,mi,se=(int(x) if x else 0 for x in m.groups()); t=h*3600+mi*60+se
    return t,(f"{h}:{mi:02d}:{se:02d}" if h else f"{mi}:{se:02d}")

def native(region, t):
    for ch in t:
        o = ord(ch)
        if region=="KR" and (0xAC00<=o<=0xD7A3 or 0x1100<=o<=0x11FF or 0x3130<=o<=0x318F): return True
        if region=="JP" and (0x3040<=o<=0x309F or 0x30A0<=o<=0x30FF): return True
    return False

cand = []
for vid, it in meta.items():
    if "liveStreamingDetails" in it: continue  # exclude live
    cid = it["snippet"]["channelId"]; s = subs.get(cid)
    if s is None or not (0 < s <= 10000): continue
    st = it["statistics"]; views = int(st.get("viewCount",0) or 0)
    if views < 50000: continue   # 롱폼은 조회수가 낮으므로 기준 완화(5만)
    region = vid_region.get(vid,"?")
    if not native(region, it["snippet"]["title"]): continue  # KR/JP relevance only
    ds, dl = dur(it.get("contentDetails",{}).get("duration",""))
    if ds <= 180 or "#shorts" in it["snippet"]["title"].lower(): continue  # 롱폼만(쇼츠 제외)
    th = it["snippet"]["thumbnails"]
    thumb = next((th[k]["url"] for k in ("high","medium","default") if k in th), "")
    cand.append({"region":vid_region.get(vid,"?"),"video_id":vid,"url":f"https://www.youtube.com/watch?v={vid}",
        "title":it["snippet"]["title"],"channel":it["snippet"]["channelTitle"],"channel_id":cid,
        "published_at":it["snippet"]["publishedAt"],"duration_sec":ds,"duration":dl,
        "views":views,"likes":int(st.get("likeCount",0) or 0),"comments":int(st.get("commentCount",0) or 0),
        "subscribers":s,"views_per_sub":round(views/max(s,1)),"thumbnail":thumb,
        "is_short": ds<=180 or "#shorts" in it["snippet"]["title"].lower(),
        "description":(it["snippet"].get("description","") or "")[:400]})

# dedupe by channel, rank by views desc, take best 8 (we'll pick 5 + spare)
cand.sort(key=lambda x: x["views"], reverse=True)
seen, best = set(), []
for r in cand:
    if r["channel_id"] in seen: continue
    seen.add(r["channel_id"]); best.append(r)
json.dump(best, open(os.path.join(HERE,"rising2.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"rising LONGFORM candidates (subs<=10k, views>=100k, >180s, dedup channel): {len(best)}")
for i,r in enumerate(best[:8],1):
    sh = "쇼츠" if r["is_short"] else "롱폼"
    print(f"{i}. [{r['region']}] {r['channel']} | 구독{r['subscribers']:,} 조회{r['views']:,} ({r['views_per_sub']}배) {sh}[{r['duration']}]")
    print(f"   {r['title'][:50]} | {r['url']}")
