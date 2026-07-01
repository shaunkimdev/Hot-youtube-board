# -*- coding: utf-8 -*-
"""Build a static image gallery (site/assets/gallery.html) from manifest.json:
per analyzed video -> thumbnail + /watch frames + related subject images."""
import os, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
PROJ = r"C:\Users\hikim\Desktop\workplace\YoutubeAnalysis"
ASSETS = os.path.join(PROJ, "site", "assets")
man = json.load(open(os.path.join(ASSETS, "manifest.json"), encoding="utf-8"))

FLAG = {"KR": "🇰🇷", "JP": "🇯🇵"}
cards = []
for vid, d in man.items():
    im = d["images"]
    def cell(src, label):
        return f'<figure><img loading="lazy" src="{vid}/{src}" alt=""><figcaption>{label}</figcaption></figure>'
    pics = []
    if im.get("thumb"): pics.append(cell(im["thumb"], "썸네일"))
    for i, r in enumerate(im.get("related", []), 1): pics.append(cell(r, f"관련주제 {i}"))
    for i, f in enumerate(im.get("frames", []), 1): pics.append(cell(f, f"/watch 프레임 {i}"))
    cards.append(f"""<section class="card">
  <h2>{FLAG.get(d['region'],'')} <span class="tp">{d['topic']}</span> {d['title']}</h2>
  <div class="strip">{''.join(pics)}</div>
  <a class="vlink" href="https://www.youtube.com/watch?v={vid}" target="_blank">▶ 원본 영상</a>
</section>""")

html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>이미지 자료 · 한·일 유튜브 이슈 분석</title>
<style>
 body{{margin:0;background:#0e0f12;color:#e8eaed;font-family:Pretendard,system-ui,"Noto Sans KR","Noto Sans JP",sans-serif}}
 .wrap{{max-width:1200px;margin:0 auto;padding:24px 18px 60px}}
 h1{{font-size:22px}} .sub{{color:#9aa0a6;font-size:13px;margin-bottom:18px}}
 .card{{background:#17191d;border:1px solid #262a30;border-radius:16px;padding:14px 16px;margin-bottom:16px}}
 .card h2{{font-size:15px;font-weight:700;line-height:1.4;margin:0 0 10px}}
 .tp{{background:#4263eb;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:6px}}
 .strip{{display:flex;gap:8px;overflow-x:auto;padding-bottom:6px}}
 figure{{margin:0;flex:none;width:200px}}
 figure img{{width:200px;height:120px;object-fit:cover;border-radius:8px;background:#000;display:block}}
 figcaption{{font-size:11px;color:#9aa0a6;margin-top:4px}}
 .vlink{{display:inline-block;margin-top:8px;color:#fa5252;font-size:12px;font-weight:700;text-decoration:none}}
</style></head><body><div class="wrap">
<h1>📸 이미지 자료 모음</h1>
<div class="sub">/watch 심층분석 대상 영상별 · 썸네일 + /watch 추출 프레임 + 관련주제 이미지(Wikimedia)</div>
{''.join(cards)}
</div></body></html>"""
open(os.path.join(ASSETS, "gallery.html"), "w", encoding="utf-8").write(html)
print("gallery ->", os.path.join(ASSETS, "gallery.html"), f"({len(man)} videos)")
