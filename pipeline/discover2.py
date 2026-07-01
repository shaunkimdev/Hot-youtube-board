# -*- coding: utf-8 -*-
"""v2 discovery: more categories, exclude LIVE broadcasts, personal channels only."""
import os, json, math, urllib.request, urllib.parse, datetime, sys, io
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
KEY = os.environ["GOOGLE_API_KEY"]
NOW = datetime.datetime.now(datetime.timezone.utc)
HERE = os.path.dirname(os.path.abspath(__file__))

# category -> topic (single-cat ones); 24/25 split by keyword.
# Politics(정치) is intentionally dropped. 재테크/자기계발 come from discover_topics.py (Search API),
# because the mostPopular chart returns no Education/personal-finance content for KR/JP.
CATS = [10, 20, 24, 25, 17, 28, 26]
REGIONS = ["KR", "JP"]
SINGLE = {10: "음악", 20: "게임", 17: "스포츠", 28: "IT·테크", 26: "라이프"}
# native-script required for local-relevance topics (exclude foreign viral)
NATIVE_CATS = {24, 25, 17, 28, 26}  # not music(10)/gaming(20) which are global

KW = {
 "economy": ["경제","증시","주가","주식","코스피","코스닥","금리","환율","부동산","집값","물가","연봉","월급","투자","비트코인","코인","반도체","수출","gdp","삼성전자",
              "経済","株","株価","円安","円高","金利","為替","物価","投資","ビットコイン","不動産","給料","年収","日経","g7"],
 "politics": ["정치","대통령","국회","여당","야당","민주당","국민의힘","장관","총리","선거","의원","청와대","대선","탄핵","외교","정부","北",
               "政治","首相","総理","選挙","国会","議員","内閣","与党","野党","政権","大統領","外交","政府","自民党","市長"],
 "celeb": ["연예","배우","아이돌","가수","스캔들","열애","결혼","이혼","논란","유튜버","인플루언서","셀럽","연예인",
            "芸能","俳優","女優","アイドル","歌手","熱愛","結婚","離婚","スキャンダル","炎上","インフルエンサー"],
 "tvshow": ["예능","프로그램","방송","쇼","드라마","무한도전","런닝맨","나혼자","미운우리","라디오스타","출연","콩트",
             "バラエティ","番組","ドラマ","放送","ショー","テレビ","出演","コント","あるある"],
}

def http(url):
    with urllib.request.urlopen(url, timeout=30) as r: return json.load(r)

def fetch(region, cat):
    items, page = [], None
    for _ in range(2):
        p = {"part":"snippet,statistics,contentDetails,liveStreamingDetails","chart":"mostPopular",
             "regionCode":region,"videoCategoryId":cat,"maxResults":50,"key":KEY}
        if page: p["pageToken"]=page
        try: d = http("https://www.googleapis.com/youtube/v3/videos?"+urllib.parse.urlencode(p))
        except Exception as e: print("!",region,cat,e,file=sys.stderr); break
        items += d.get("items", []); page = d.get("nextPageToken")
        if not page: break
    return items

def hours_since(iso):
    try: return max((NOW-datetime.datetime.fromisoformat(iso.replace("Z","+00:00"))).total_seconds()/3600,0.5)
    except: return 999.0

def iso_dur(s):
    import re
    m=re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",s or "")
    if not m: return 0,""
    h,mi,se=(int(x) if x else 0 for x in m.groups()); tot=h*3600+mi*60+se
    return tot,(f"{h}:{mi:02d}:{se:02d}" if h else f"{mi}:{se:02d}")

def native(region,t):
    for ch in t:
        o=ord(ch)
        if region=="KR" and (0xAC00<=o<=0xD7A3 or 0x1100<=o<=0x11FF or 0x3130<=o<=0x318F): return True
        if region=="JP" and (0x3040<=o<=0x309F or 0x30A0<=o<=0x30FF): return True
    return False

def classify(cat,title):
    if cat in SINGLE: return SINGLE[cat]
    t=title.lower(); hit=lambda ks: any(k.lower() in t for k in ks)
    if cat==24: return "TV쇼" if hit(KW["tvshow"]) else "연예"
    if cat==25:  # News&Politics -> 경제만 추출 (정치·일반뉴스 제외)
        return "경제" if hit(KW["economy"]) else "기타"
    return "기타"

def thumb(sn):
    th=sn.get("thumbnails",{})
    for k in ("maxres","standard","high","medium","default"):
        if k in th: return th[k]["url"]
    return ""

# ---- official-channel detector (from filter_personal, extended) ----
OFFICIAL_TOKENS=["- topic"," topic","vevo","smtown","hybe","belift","bighit","big hit","source music",
 "jyp","yg entertainment","starship","pledis","stone music","1thek","genie music","dreamus","kakao entertainment",
 "kozco","ador official","records","엔터테인먼트","레이블","sbs","mbc","kbs","jtbc","tv조선","채널a","mbn","ytn",
 "연합뉴스","매일신문","조선일보","한겨레","동아일보","경향신문","한국경제","매일경제","한경","테レビ","テレビ",
 "ニュース","新聞","放送局","報道ステーション","ann","nhk","tbs","フジ","日テレ","テレ朝","文化人放送局","カンテレ","公式",
 "projectmoon","project moon","capcom","lost ark","로스트아크","riot games","nexon","넥슨","스마일게이트","pearl abyss",
 "mihoyo","hoyoverse","music awards","ceipa","mama awards"," inc","ⓒ","공식채널",
 "warner music","universal music","sony music","avex","victor entertainment","pony canyon","king record",
 # new-category official: leagues/brands/tourism
 "kbo","k league","k리그","프로야구","npb","j.league","jリーグ","espn","dazn","삼성전자","samsung","lg전자",
 "apple","google","마이크로소프트","microsoft","관광공사","tourism","jal","ana official"]
OFFICIAL_ARTIST={"i-dle (아이들)","babymonster","bangtantv","blackpink","le sserafim","illit","katseye","evan",
 "ive","aespa","newjeans","nmixx","twice","stray kids","seventeen","tomorrow x together","txt","엔믹스",
 "米津玄師","kenshi yonezu","kenshi yonezu  米津玄師","mazzel","m!lk","aぇ! group","aぇ!group","hey! say! jump",
 "hey!say!jump","snow man","king & prince","naniwa danshi","なにわ男子","travis japan","be:first","jo1","ini",
 "timelesz","ado","yoasobi","official髭男dism"," official髭男","janet jackson","超特急","be:first"}
def is_official(title):
    t=(title or "").lower().strip()
    return any(x in t for x in OFFICIAL_ARTIST) or any(x in t for x in OFFICIAL_TOKENS)

rows=[]; seen=set(); n_live=0; n_official=0
for region in REGIONS:
    for cat in CATS:
        for it in fetch(region,cat):
            vid=it["id"]
            if (region,vid) in seen: continue
            seen.add((region,vid))
            sn=it["snippet"]; st=it.get("statistics",{})
            is_live = "liveStreamingDetails" in it  # was/is a live broadcast (incl premieres)
            if is_live: n_live+=1; continue
            if cat in NATIVE_CATS and not native(region, sn.get("title","")): continue
            if is_official(sn.get("channelTitle","")): n_official+=1; continue
            views=int(st.get("viewCount",0) or 0); likes=int(st.get("likeCount",0) or 0); comments=int(st.get("commentCount",0) or 0)
            hrs=hours_since(sn.get("publishedAt","")); ds,dl=iso_dur(it.get("contentDetails",{}).get("duration",""))
            issue=(views+20*likes+100*comments)/math.sqrt(hrs)
            rows.append({"region":region,"topic":classify(cat,sn.get("title","")),"category_id":cat,
              "video_id":vid,"url":f"https://www.youtube.com/watch?v={vid}","title":sn.get("title",""),
              "channel":sn.get("channelTitle",""),"published_at":sn.get("publishedAt",""),"hours_since":round(hrs,1),
              "duration_sec":ds,"duration":dl,"views":views,"likes":likes,"comments":comments,
              "views_per_hour":round(views/hrs),"issue_score":round(issue),"thumbnail":thumb(sn),
              "description":(sn.get("description","") or "")[:600],"is_live":is_live})

groups=defaultdict(list)
for r in rows: groups[(r["region"],r["topic"])].append(r)
top={}
for k,lst in groups.items():
    if k[1]=="기타": continue
    lst.sort(key=lambda x:x["issue_score"],reverse=True)
    top[f"{k[0]}|{k[1]}"]=lst[:3]
json.dump(top,open(os.path.join(HERE,"top3_v2.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
json.dump(rows,open(os.path.join(HERE,"candidates2.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(f"personal non-live videos: {len(rows)} | excluded live: {n_live} | excluded official: {n_official}")
ORDER=["경제","재테크","자기계발","연예","TV쇼","음악","게임","스포츠","IT·테크","라이프"]
for region in REGIONS:
    print("="*60,region)
    for o in ORDER:
        k=next((kk for kk in top if kk.startswith(region+"|") and kk.split("|")[1]==o),None)
        lst=top.get(k,[])
        print(f"[{o}] {len(lst)}건")
        for i,v in enumerate(lst,1):
            print(f"  {i}. {v['channel']} [{v['duration']}] issue={v['issue_score']:,} :: {v['title'][:40]}")
