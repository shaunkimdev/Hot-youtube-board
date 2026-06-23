# -*- coding: utf-8 -*-
"""Automation build: like build_all3 but AUTO-summarizes videos missing from the
hand-authored EN3 dict (so unattended daily runs always produce output).
Outputs dated + 'latest' data.json, Excel, and self-contained index.html."""
import json, os, re, urllib.request, datetime, subprocess, sys
import xlsxwriter
from enrich3 import EN3, WATCH, META, TIMELINE

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SITE = os.path.join(PROJ, "site"); os.makedirs(SITE, exist_ok=True)
DATE = os.environ.get("RUN_DATE") or datetime.date.today().isoformat()
THUMB = os.path.join(HERE, "thumbs"); os.makedirs(THUMB, exist_ok=True)
top = json.load(open(os.path.join(HERE, "top3_v3.json"), encoding="utf-8"))
rising_raw = json.load(open(os.path.join(HERE, "rising2.json"), encoding="utf-8"))[:5]
# LLM summaries (from summarize_llm.py) take priority over hand-authored EN3.
SUMMARIES = {}
_sp = os.path.join(HERE, "summaries.json")
if os.path.exists(_sp):
    SUMMARIES = json.load(open(_sp, encoding="utf-8"))
ORDER = ["경제", "정치", "연예", "TV쇼", "음악", "게임", "스포츠", "IT·테크", "라이프"]

def auto_summary(v):
    """Fallback ~100자 summary from description/title when not hand-authored."""
    d = " ".join((v.get("description") or "").split())
    d = re.sub(r"https?://\S+", "", d).strip()
    base = d if len(d) >= 20 else v["title"]
    return (base[:98] + "…") if len(base) > 99 else base

def dl(vid, url):
    p = os.path.join(THUMB, f"{vid}.jpg")
    if os.path.exists(p) and os.path.getsize(p) > 0: return p
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        open(p, "wb").write(urllib.request.urlopen(req, timeout=20).read()); return p
    except Exception: return None

def base(v, region):
    cc = "한국" if region == "KR" else "일본"; flag = "🇰🇷" if region == "KR" else "🇯🇵"
    vid = v["video_id"]
    timeline = TIMELINE.get(vid, [])
    if vid in SUMMARIES:  # Claude API result (preferred)
        s = SUMMARIES[vid]
        en = (s.get("summary", ""), s.get("tip", ""), "", "", s.get("analysis", META))
        timeline = s.get("timeline", timeline)
    elif vid in EN3:      # hand-authored
        en = EN3[vid]
    else:                 # description fallback
        en = (auto_summary(v), "자동 요약(미검수) — 원본 영상으로 내용을 확인하세요.", "", "", META + "(자동)")
    return {"date": DATE, "country": cc, "region": region, "flag": flag,
        "title": v["title"], "channel": v["channel"], "published": v["published_at"][:10],
        "hours": v.get("hours_since", 0), "duration": v["duration"], "views": v["views"],
        "likes": v.get("likes", 0), "comments": v.get("comments", 0), "issue": v.get("issue_score", 0),
        "summary": en[0], "tip": en[1], "article_title": en[2], "article_url": en[3],
        "url": v["url"], "thumb": v["thumbnail"], "analysis": en[4], "timeline": timeline}

RISE_GENRE = {"GxS8Val7Gs4": "스포츠", "1L2FHEMSY_0": "연예", "hvsrOgrqzM4": "경제", "V_FvHTM9krs": "연예", "SYEChi_5gXU": "음악"}
rows = []
for region in ["KR", "JP"]:
    for o in ORDER:
        k = next((kk for kk in top if kk.startswith(region + "|") and kk.split("|")[1] == o), None)
        if not k: continue
        for rank, v in enumerate(top[k], 1):
            r = base(v, region); r["topic"] = o; r["rank"] = rank
            r["_t"] = dl(v["video_id"], v["thumbnail"]); rows.append(r)
rising = []
for rank, v in enumerate(rising_raw, 1):
    r = base(v, v["region"]); r["topic"] = "라이징스타"; r["rank"] = rank
    r["subscribers"] = v["subscribers"]; r["views_per_sub"] = v["views_per_sub"]
    r["genre"] = RISE_GENRE.get(v["video_id"], ""); r["_t"] = dl(v["video_id"], v["thumbnail"]); rising.append(r)

clean = lambda L: [{k: v for k, v in r.items() if k != "_t"} for r in L]
payload = {"date": DATE, "rows": clean(rows), "rising": clean(rising)}
json.dump(payload, open(os.path.join(SITE, "data.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# dated archive copy
arch = os.path.join(SITE, "archive"); os.makedirs(arch, exist_ok=True)
json.dump(payload, open(os.path.join(arch, f"data_{DATE}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# Excel (dated)
OUT = os.path.join(PROJ, f"YouTube이슈분석_개인채널_{DATE}.xlsx")
wb = xlsxwriter.Workbook(OUT, {"strings_to_urls": False})
hd = wb.add_format({"bold": True, "bg_color": "#2F5496", "font_color": "white", "border": 1, "text_wrap": True, "align": "center", "valign": "vcenter"})
cl = wb.add_format({"border": 1, "valign": "top", "text_wrap": True, "font_size": 9}); cc_ = wb.add_format({"border": 1, "align": "center", "valign": "vcenter", "font_size": 9})
nm = wb.add_format({"border": 1, "align": "right", "valign": "vcenter", "num_format": "#,##0", "font_size": 9})
def tl_text(d):
    if d.get("timeline"):
        return "⏱ 타임라인\n" + "\n".join(f"· {t[0]}  {t[1]}" for t in d["timeline"])
    return d["tip"]
COLS = ["날짜","국가","주제","순위","제목","채널","게시일","길이","조회수","좋아요","댓글","이슈점수","상세요약","도움내용/⏱타임라인","영상링크","분석방식"]
for name, data in [("전체", rows), ("라이징스타", rising)]:
    ws = wb.add_worksheet(name)
    for c, h in enumerate(COLS): ws.write(0, c, h, hd)
    for i, d in enumerate(data, 1):
        ws.write_row(i, 0, [d["date"], d["country"], d["topic"], d["rank"], d["title"], d["channel"], d["published"], d["duration"]], cc_)
        for col, key in [(8,"views"),(9,"likes"),(10,"comments"),(11,"issue")]: ws.write_number(i, col, d[key], nm)
        ws.write(i, 12, d["summary"], cl); ws.write(i, 13, tl_text(d), cl); ws.write_url(i, 14, d["url"], cc_, "▶"); ws.write(i, 15, d["analysis"], cc_)
wb.close()

# regenerate self-contained site
subprocess.run([sys.executable, os.path.join(HERE, "make_site.py")], check=True,
               env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
print(f"[build_auto] {DATE}: main {len(rows)} + rising {len(rising)} -> {OUT}")
