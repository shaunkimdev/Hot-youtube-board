# -*- coding: utf-8 -*-
"""From existing personal+nonlive pool: keep LONGFORM only, fetch channel subs,
build longform top3 + Rising Star (subs<=10k, huge views) Best 5."""
import os, json, math, urllib.request, urllib.parse, sys, io
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
KEY = os.environ["GOOGLE_API_KEY"]
HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "candidates2.json"), encoding="utf-8"))

# extra official channels that slipped through (broadcasters/orgs)
EXTRA_OFFICIAL = ["obs","fnn","jfa","プライムオンライン","tv tokyo","テレ東","obs뉴스","obs경인"]
def extra_official(ch):
    t = (ch or "").lower()
    return any(x in t for x in EXTRA_OFFICIAL)
rows = [r for r in rows if not extra_official(r["channel"])]

def http(url):
    with urllib.request.urlopen(url, timeout=30) as r: return json.load(r)

# ---- fetch channelId + subscriber count for the FULL pool (need subs for rising star) ----
ids = [r["video_id"] for r in rows]
vid2ch = {}
for i in range(0, len(ids), 50):
    d = http("https://www.googleapis.com/youtube/v3/videos?"+urllib.parse.urlencode(
        {"part":"snippet","id":",".join(ids[i:i+50]),"key":KEY}))
    for it in d.get("items", []):
        vid2ch[it["id"]] = it["snippet"]["channelId"]
chans = sorted(set(vid2ch.values()))
ch_subs = {}
for i in range(0, len(chans), 50):
    d = http("https://www.googleapis.com/youtube/v3/channels?"+urllib.parse.urlencode(
        {"part":"statistics","id":",".join(chans[i:i+50]),"key":KEY}))
    for it in d.get("items", []):
        st = it.get("statistics", {})
        ch_subs[it["id"]] = None if st.get("hiddenSubscriberCount", False) else int(st.get("subscriberCount", 0) or 0)
for r in rows:
    cid = vid2ch.get(r["video_id"]); r["channel_id"] = cid; r["subscribers"] = ch_subs.get(cid)

# ---- longform filter (for MAIN topic categories) ----
def is_short(r):
    t = r["title"].lower()
    return r["duration_sec"] <= 180 or "#shorts" in t or "#short" in t
long_rows = [r for r in rows if not is_short(r)]
print(f"pool {len(rows)} -> longform {len(long_rows)} (excluded shorts {len(rows)-len(long_rows)})")

json.dump(long_rows, open(os.path.join(HERE,"longform_all.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- longform top3 per (region, topic) ----
groups = defaultdict(list)
for r in long_rows:
    if r["topic"] != "기타": groups[(r["region"], r["topic"])].append(r)
top = {}
for k, lst in groups.items():
    lst.sort(key=lambda x: x["issue_score"], reverse=True)
    top[f"{k[0]}|{k[1]}"] = lst[:3]
json.dump(top, open(os.path.join(HERE,"top3_v3.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- Rising Star: from FULL pool (shorts INCLUDED — tiny-channel virality is mostly shorts) ----
RISE_MIN_VIEWS = 200000
cand = [r for r in rows if r["subscribers"] is not None and 0 < r["subscribers"] <= 10000
        and r["views"] >= RISE_MIN_VIEWS]
cand.sort(key=lambda x: x["views"], reverse=True)
seen_ch, rising = set(), []
for r in cand:
    if r["channel_id"] in seen_ch: continue
    seen_ch.add(r["channel_id"])
    r2 = dict(r); r2["views_per_sub"] = round(r["views"]/max(r["subscribers"],1))
    rising.append(r2)
    if len(rising) >= 5: break
json.dump(rising, open(os.path.join(HERE,"rising.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- report ----
ORDER=["경제","정치","연예","TV쇼","음악","게임","스포츠","IT·테크","라이프"]
for region in ["KR","JP"]:
    print("="*60, region)
    for o in ORDER:
        k=next((kk for kk in top if kk.startswith(region+"|") and kk.split("|")[1]==o),None)
        lst=top.get(k,[])
        print(f"[{o}] {len(lst)}건", end="  ")
        for v in lst:
            s=v["subscribers"]; ss=f"{s:,}" if s is not None else "비공개"
            print(f"| {v['channel']}[{v['duration']}]구독{ss}", end="")
        print()
print("\n"+"="*60, "RISING STAR Best5 (구독≤1만, 조회수≥20만, 채널중복제거)")
for i,v in enumerate(rising,1):
    print(f"{i}. [{v['region']}/{v['topic']}] {v['channel']} | 구독 {v['subscribers']:,} | 조회 {v['views']:,} | 구독대비 {v['views_per_sub']}배 | [{v['duration']}]")
    print(f"   {v['title'][:50]} | {v['url']}")
