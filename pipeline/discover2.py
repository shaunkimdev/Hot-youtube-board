# -*- coding: utf-8 -*-
"""Search-API discovery across 11 FIXED thematic categories, per region
(KR/JP/US only). Personal channels only; LIVE 제외; 롱폼만(4~20분, 쇼츠 제외).

These 11 categories (해외반응/스캔들/IT/돈/여행/갈등/e스포츠/연애/사회핫이슈/라이프/
일본핫이슈) don't map onto YouTube's own videoCategoryId taxonomy, so — unlike the
old mostPopular-chart approach — collection here is 100% Search-API query based.

Quota note: search.list costs 100 units/call and the default YouTube Data API
quota caps search.list at ~100 calls/day *for the whole project* (shared with
rising_search.py). Region scope is intentionally limited to KR/JP/US (not the
earlier KR/JP/US/GB/DE/FR) and each (category, region) gets exactly 2 seed
queries x 1 duration(medium) = 10*3*2 + 일본핫이슈(2 regions)*2 = 64 calls here,
leaving headroom for rising_search.py's ~24 calls within the shared 100/day cap.

일본핫이슈 = 해외(자국 밖)에서 일본을 다루는 영상(문화·여행·이슈) -> JP 리전은 제외
(자국 이야기는 '해외 시선'이 아니므로)."""
import os, json, math, re, urllib.request, urllib.parse, datetime, sys, io
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
 "해외반응": {
   "KR": ["해외반응", "외국인 반응 한국"],
   "JP": ["海外の反応", "外国人 反応 日本"],
   "US": ["foreigners react", "foreign reaction video"],
 },
 "스캔들": {
   "KR": ["연예인 스캔들", "열애설"],
   "JP": ["芸能人 スキャンダル", "炎上 芸能人"],
   "US": ["celebrity scandal", "celebrity controversy"],
 },
 "IT": {
   "KR": ["IT 리뷰", "신제품 언박싱"],
   "JP": ["ガジェット レビュー", "新製品 開封"],
   "US": ["tech review", "new gadget unboxing"],
 },
 "돈": {
   "KR": ["재테크", "주식 투자"],
   "JP": ["投資 初心者", "新nisa"],
   "US": ["personal finance", "stock investing"],
 },
 "여행": {
   "KR": ["여행 브이로그", "여행 트러블"],
   "JP": ["旅行 トラブル", "海外旅行 vlog"],
   "US": ["travel vlog", "travel disaster"],
 },
 "갈등": {
   "KR": ["유튜버 논란", "저격 폭로"],
   "JP": ["炎上 事件", "暴露 対立"],
   "US": ["youtuber drama", "callout video"],
 },
 "e스포츠": {
   "KR": ["e스포츠 대회", "프로게이머"],
   "JP": ["eスポーツ 大会", "プロゲーマー"],
   "US": ["esports tournament", "pro gamer highlights"],
 },
 "연애": {
   "KR": ["연애 브이로그", "연애 고민 상담"],
   "JP": ["恋愛 vlog", "恋愛相談"],
   "US": ["dating vlog", "relationship advice"],
 },
 "사회핫이슈": {
   "KR": ["사회 이슈", "논란 사건"],
   "JP": ["社会問題", "話題 ニュース"],
   "US": ["social issue", "viral controversy"],
 },
 "라이프": {
   "KR": ["브이로그", "일상 꿀팁"],
   "JP": ["vlog 日常", "生活 裏技"],
   "US": ["daily vlog", "life hack"],
 },
 "일본핫이슈": {
   "KR": ["일본 여행 근황", "일본 이슈"],
   "US": ["japan news", "japan travel vlog"],
 },
}

# ---- official/broadcaster/label/press/league blocklist (personal channels only) ----
OFFICIAL_TOKENS = ["- topic", " topic", "vevo", "smtown", "hybe", "belift", "bighit", "big hit", "source music",
 "jyp", "yg entertainment", "starship", "pledis", "stone music", "1thek", "genie music", "dreamus", "kakao entertainment",
 "kozco", "ador official", "records", "엔터테인먼트", "레이블", "sbs", "mbc", "kbs", "jtbc", "tv조선", "채널a", "mbn", "ytn",
 "연합뉴스", "매일신문", "조선일보", "한겨레", "동아일보", "경향신문", "한국경제", "매일경제", "한경", "テレビ",
 "ニュース", "新聞", "放送局", "報道ステーション", "ann", "nhk", "tbs", "フジ", "日テレ", "テレ朝", "文化人放送局", "カンテレ", "公式",
 "riot games", "nexon", "넥슨", "스마일게이트", "pearl abyss", "esl", "blast premier", "valorant champions",
 "lck", "lpl", "lec", "lcs",
 "music awards", "ceipa", "mama awards", " inc", "ⓒ", "공식채널",
 "warner music", "universal music", "sony music", "avex", "victor entertainment", "pony canyon", "king record",
 "エイベックス", "ソニーミュージック", "ユニバーサルミュージック", "ワーナーミュージック", "being inc", "ビーイング",
 "entertainment", "엔터", "レーベル", "label", "music group", "records japan",
 "kbo", "k league", "k리그", "프로야구", "npb", "j.league", "jリーグ", "espn", "dazn", "삼성전자", "samsung", "lg전자",
 "apple", "google", "마이크로소프트", "microsoft", "관광공사", "tourism", "jal", "ana official",
 "olympic", "オリンピック", "日本相撲協会", "大相撲", "b.league", "bリーグ", "高校野球", "甲子園", "日本サッカー協会",
 "日本野球機構", "프로배구", "kbl", "kovo", "spotv", "spotvnow", "spotv now", "엠스플", "mbc스포츠", "sbs스포츠",
 "kbs n스포츠", "jtbc골프", "coupang play", "쿠팡플레이",
 "bbc", "itv", "sky news", "channel 4", "channel 5", "cnn", "fox news", "msnbc", "nbc news",
 "abc news", "cbs news", "npr", "the new york times", "washington post", "the guardian",
 "reuters", "associated press", "bloomberg", "cnbc", "nfl", "nba", "premier league",
 "ard", "zdf", "rtl", "sat.1", "pro7", "prosieben", "n-tv", "ntv", "der spiegel", "bild",
 "tagesschau", "zeit online", "süddeutsche zeitung", "handelsblatt",
 "tf1", "france 2", "france 3", "france info", "franceinfo", "bfmtv", "le monde", "le figaro",
 "libération", "l'équipe", "canal+", "m6", "capital.fr",
 "기획재정부", "금융감독원", "증권방송", "経済テレビ", "the motley fool",
 "テレビ朝日", "フジテレビ", "日本テレビ", "毎日放送", "朝日放送", "読売テレビ",
 "吉本興業", "ジャニーズ", "スターダスト", "ホリプロ", "サンミュージック"]
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
    if region == "KR":
        return any(0xAC00<=ord(ch)<=0xD7A3 or 0x1100<=ord(ch)<=0x11FF or 0x3130<=ord(ch)<=0x318F for ch in t)
    if region == "JP":
        return any(0x3040<=ord(ch)<=0x309F or 0x30A0<=ord(ch)<=0x30FF for ch in t)
    if region == "US":
        FOREIGN = ((0xAC00,0xD7A3),(0x1100,0x11FF),(0x3130,0x318F),(0x3040,0x30FF),
                   (0x4E00,0x9FFF),(0x0600,0x06FF),(0x0400,0x04FF),(0x0E00,0x0E7F),
                   (0x0590,0x05FF),(0x0370,0x03FF),(0x0900,0x097F),(0x0980,0x09FF),
                   (0x0A00,0x0A7F),(0x0A80,0x0AFF),(0x0B80,0x0BFF),(0x0C00,0x0C7F),
                   (0x0C80,0x0CFF),(0x0D00,0x0D7F))
        return not any(any(lo<=ord(ch)<=hi for lo,hi in FOREIGN) for ch in t)
    return False

def thumb(sn):
    th = sn.get("thumbnails", {})
    for k in ("maxres", "standard", "high", "medium", "default"):
        if k in th: return th[k]["url"]
    return ""

# ---- search: collect video ids per (region, topic) ----
errors = []
vid_meta = {}   # video_id -> (region, topic)
for topic, regions in QUERIES.items():
    for region, qs in regions.items():
        for q in qs:
            # medium(4~20분)만 검색 — 하루 100회인 search.list 할당량을 아끼기 위해
            # long(20분초과) 검색은 생략(쇼츠는 자동 제외).
            try:
                d = http("https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(
                    {"part": "snippet", "type": "video", "order": "viewCount", "publishedAfter": AFTER,
                     "regionCode": region, "relevanceLanguage": LANG[region], "q": q,
                     "videoDuration": "medium", "maxResults": 50, "key": KEY}))
            except Exception as e:
                errors.append(f"{region}/{topic}/{q}: {e}")
                print("search err", topic, region, q, e, file=sys.stderr); continue
            for it in d.get("items", []):
                vid_meta.setdefault(it["id"]["videoId"], (region, topic))
print("search candidate videos:", len(vid_meta))

# ---- fetch full stats ----
ids = list(vid_meta)
rows = []; n_live = 0; n_official = 0
for i in range(0, len(ids), 50):
    d = http("https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode(
        {"part": "snippet,statistics,contentDetails,liveStreamingDetails", "id": ",".join(ids[i:i+50]), "key": KEY}))
    for it in d.get("items", []):
        vid = it["id"]
        region, topic = vid_meta[vid]
        if "liveStreamingDetails" in it: n_live += 1; continue    # 라이브 제외
        sn = it["snippet"]; st = it.get("statistics", {})
        title = sn.get("title", "")
        if not native(region, title): continue                    # 리전 언어 관련성
        if is_official(sn.get("channelTitle", "")): n_official += 1; continue  # 공식/방송/언론 채널 제외
        ds, dl = iso_dur(it.get("contentDetails", {}).get("duration", ""))
        if ds <= 180 or "#shorts" in title.lower() or "#short" in title.lower(): continue  # 쇼츠 제외
        views = int(st.get("viewCount", 0) or 0)
        if views < MIN_VIEWS: continue
        likes = int(st.get("likeCount", 0) or 0); comments = int(st.get("commentCount", 0) or 0)
        hrs = hours_since(sn.get("publishedAt", ""))
        issue = (views + 20*likes + 100*comments) / math.sqrt(hrs)
        rows.append({"region": region, "topic": topic, "category_id": 0,
            "video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "title": title,
            "channel": sn.get("channelTitle", ""), "published_at": sn.get("publishedAt", ""), "hours_since": round(hrs, 1),
            "duration_sec": ds, "duration": dl, "views": views, "likes": likes, "comments": comments,
            "views_per_hour": round(views/hrs), "issue_score": round(issue), "thumbnail": thumb(sn),
            "description": (sn.get("description", "") or "")[:600], "is_live": False})

groups = defaultdict(list)
for r in rows: groups[(r["region"], r["topic"])].append(r)
top = {}
for k, lst in groups.items():
    lst.sort(key=lambda x: x["issue_score"], reverse=True)
    top[f"{k[0]}|{k[1]}"] = lst[:3]
json.dump(top, open(os.path.join(HERE, "top3_v2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(rows, open(os.path.join(HERE, "candidates2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"personal non-live videos: {len(rows)} | excluded live: {n_live} | excluded official: {n_official}")

ORDER = list(QUERIES.keys())
for region in REGIONS:
    print("="*60, region)
    for o in ORDER:
        lst = top.get(f"{region}|{o}", [])
        print(f"[{o}] {len(lst)}건")
        for i, v in enumerate(lst, 1):
            print(f"  {i}. {v['channel']} [{v['duration']}] issue={v['issue_score']:,} :: {v['title'][:40]}")

# if every API call failed (e.g. bad/quota-exceeded key), rows will be empty even
# though nothing "looked" wrong per-category -> fail loudly instead of silently
# producing an empty dashboard.
if errors and not rows:
    print(f"FATAL: all {len(errors)} YouTube API calls failed, 0 videos collected. "
          f"First error: {errors[0]}", file=sys.stderr)
    sys.exit(1)
