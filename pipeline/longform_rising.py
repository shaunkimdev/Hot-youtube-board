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
ch_subs = {}; ch_country = {}
for i in range(0, len(chans), 50):
    d = http("https://www.googleapis.com/youtube/v3/channels?"+urllib.parse.urlencode(
        {"part":"statistics,snippet","id":",".join(chans[i:i+50]),"key":KEY}))
    for it in d.get("items", []):
        st = it.get("statistics", {})
        ch_subs[it["id"]] = None if st.get("hiddenSubscriberCount", False) else int(st.get("subscriberCount", 0) or 0)
        ch_country[it["id"]] = it.get("snippet", {}).get("country")
for r in rows:
    cid = vid2ch.get(r["video_id"]); r["channel_id"] = cid; r["subscribers"] = ch_subs.get(cid)
    r["channel_country"] = ch_country.get(cid)

# 특별 카테고리는 해외 제작 영상만 허용한다. 국가를 공개하지 않은 채널은 검색 리전/언어를
# 근거로 후보에 남기되, KR/JP로 명시된 채널은 확실히 제외한다.
rows = [r for r in rows if not (r.get("topic") == "한일글로벌"
                                and r.get("channel_country") in {"KR", "JP"})]

# ---- longform filter (for MAIN topic categories) ----
def is_short(r):
    t = r["title"].lower()
    return r["duration_sec"] <= 180 or "#shorts" in t or "#short" in t
long_rows = [r for r in rows if not is_short(r)]
print(f"pool {len(rows)} -> longform {len(long_rows)} (excluded shorts {len(rows)-len(long_rows)})")

# ---- ranking metric: 구독자 대비 조회수 (views / subscribers) ----
# A tiny channel with a handful of views can post a huge ratio (e.g. 50 views / 2 subs
# = 25x) without the video actually being "an issue" to anyone. MIN_VIEWS_RANK is an
# absolute view-count floor a video must clear before it's even eligible to be ranked
# by that ratio, so the ratio only ever measures genuine breakout reach.
# 10만(100k) views is the threshold commonly used in Korean digital-media/marketing
# commentary as the point a video has "가시적인 화제성" (visible public buzz) rather
# than niche-audience traction — consistent with this pipeline's own existing floors
# (rising_search.py already requires >=50k, longform_rising's old rising gate >=200k).
MIN_VIEWS_RANK = 100_000
# MIN_LIKE_RATIO: spam/bot-view filter. Real breakout videos across every category we've
# observed (economy talk shows, drama recaps, reaction content, travel vlogs) land at
# 0.5%+ likes/views; content with view counts inflated by bots, ad networks, or pure
# reposts/rips consistently shows <0.1% (e.g. an actual case: 129k views on 8 likes =
# 0.006%). Below 0.1% the view count is not credible evidence of real audience reach,
# so such videos are excluded from ranking entirely rather than just down-weighted.
MIN_LIKE_RATIO = 0.001
def rank_eligible(r):
    return (r["views"] >= MIN_VIEWS_RANK and r.get("subscribers") is not None
            and r["subscribers"] > 0
            and r.get("likes", 0) / r["views"] >= MIN_LIKE_RATIO)
for r in long_rows:
    r["views_per_sub"] = round(r["views"] / r["subscribers"], 2) if rank_eligible(r) else None

json.dump(long_rows, open(os.path.join(HERE,"longform_all.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- longform top3 per (region, topic), ranked by 구독자대비조회수 (views_per_sub) ----
groups = defaultdict(list)
for r in long_rows:
    special_ok = (r.get("topic") == "한일글로벌" and r["views"] >= 20_000
                  and r.get("likes", 0) / max(r["views"], 1) >= MIN_LIKE_RATIO)
    if r["topic"] != "기타" and (rank_eligible(r) or special_ok):
        groups[(r["region"], r["topic"])].append(r)
top = {}
for k, lst in groups.items():
    # 한일글로벌은 XPost용 특별 카테고리이므로 요청대로 화제성 점수 Top3를 고정한다.
    # 일반 카테고리는 기존 카드뉴스 기준(구독자 대비 조회수)을 유지한다.
    metric = "issue_score" if k[1] == "한일글로벌" else "views_per_sub"
    lst.sort(key=lambda x: x.get(metric) or 0, reverse=True)
    top[f"{k[0]}|{k[1]}"] = lst[:3]
json.dump(top, open(os.path.join(HERE,"top3_v3.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- Rising Star: from LONGFORM pool only (쇼츠 제외), ranked by 구독자대비조회수 ----
RISE_MIN_VIEWS = 200000
cand = [r for r in long_rows if r["subscribers"] is not None and 0 < r["subscribers"] <= 10000
        and r["views"] >= RISE_MIN_VIEWS]
for r in cand: r["views_per_sub"] = round(r["views"]/max(r["subscribers"],1), 2)
cand.sort(key=lambda x: x["views_per_sub"], reverse=True)
seen_ch, rising = set(), []
for r in cand:
    if r["channel_id"] in seen_ch: continue
    seen_ch.add(r["channel_id"])
    rising.append(dict(r))
    if len(rising) >= 5: break
json.dump(rising, open(os.path.join(HERE,"rising.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- report ----
ORDER=["해외반응","스캔들","IT","돈","여행","갈등","e스포츠","연애","사회핫이슈","라이프","일본핫이슈","한일글로벌"]
for region in ["KR","JP","US"]:
    print("="*60, region)
    for o in ORDER:
        k=next((kk for kk in top if kk.startswith(region+"|") and kk.split("|")[1]==o),None)
        lst=top.get(k,[])
        print(f"[{o}] {len(lst)}건", end="  ")
        for v in lst:
            s=v["subscribers"]; ss=f"{s:,}" if s is not None else "비공개"
            print(f"| {v['channel']}[{v['duration']}]구독{ss}(조회/구독 {v['views_per_sub']}배)", end="")
        print()
print("\n"+"="*60, "RISING STAR Best5 (구독≤1만, 조회수≥20만, 채널중복제거)")
for i,v in enumerate(rising,1):
    print(f"{i}. [{v['region']}/{v['topic']}] {v['channel']} | 구독 {v['subscribers']:,} | 조회 {v['views']:,} | 구독대비 {v['views_per_sub']}배 | [{v['duration']}]")
    print(f"   {v['title'][:50]} | {v['url']}")
