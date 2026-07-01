# -*- coding: utf-8 -*-
"""Collect 'related topic' images for each analyzed video into its asset folder.

Per video (site/assets/<video_id>/):
  thumb.jpg        -> the YouTube thumbnail (copied from pipeline/thumbs)
  frames/...       -> representative frames from /watch (already there)
  related_*.jpg    -> license-safe subject images via Wikimedia pageimages API

A web image search without an image API is unreliable/licensing-risky, so we use
Wikimedia (Commons-backed) which returns attributable images for the subject."""
import os, sys, json, shutil, urllib.request, urllib.parse, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PROJ = r"C:\Users\hikim\Desktop\workplace\YoutubeAnalysis"
ASSETS = os.path.join(PROJ, "site", "assets")
THUMBS = os.path.join(PROJ, "pipeline", "thumbs")
TARGETS = json.load(open(os.path.join(PROJ, "pipeline", "watch_targets.json"), encoding="utf-8"))

# video_id -> (wiki lang, [subject search keywords]) — 1~2 representative subjects each
KW = {
 "wE0r_DJxuJ0": ("ko", ["이재용", "삼성전자"]),
 "tlUcRjfR9xo": ("ja", ["ニューヨーク証券取引所", "アメリカ合衆国の経済"]),
 "XnU2fA8LdVs": ("ko", ["주식", "자산"]),
 "Li7Xz5oxyZ4": ("ja", ["インデックスファンド", "資産運用"]),
 "xAhHyjJ7nqs": ("ko", ["대한민국의 공무원", "영어"]),
 "2j31PDmGMSQ": ("ja", ["河野玄斗", "資格試験"]),
 "5hL7uPsISY0": ("ko", ["힙합 음악", "뮤직 비디오"]),
 "AMQI7HSZGXI": ("ja", ["B'z", "ロックンロール"]),
 "mIbZwBGThms": ("ko", ["비디오 게임", "숨바꼭질"]),
 "iluTnXaxTTw": ("ja", ["Minecraft", "テレビゲーム"]),
 "uX_Et5er1Ck": ("ko", ["홍명보", "대한민국 축구 국가대표팀"]),
 "u-dSw0lLgB8": ("ko", ["애플 (기업)", "아이폰"]),
 "24Apj_JlQcc": ("ja", ["アマゾン (企業)", "通信販売"]),
 "xYLNDE4RXsg": ("ko", ["유튜버", "브이로그"]),
 "Fz8pWHmuwNk": ("ja", ["FIFAワールドカップ", "サッカー"]),
 "HEFjisKMDKE": ("ko", ["홍명보", "FIFA"]),
}

def wiki_image(lang, kw):
    """Search Wikipedia and return the page's original image URL (or None)."""
    q = {"action": "query", "format": "json", "generator": "search",
         "gsrsearch": kw, "gsrlimit": 1, "prop": "pageimages",
         "piprop": "original|thumbnail", "pithumbsize": 700, "redirects": 1}
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(q)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "YoutubeAnalysis/1.0 (research)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
        pages = d.get("query", {}).get("pages", {})
        for p in pages.values():
            img = (p.get("original") or p.get("thumbnail") or {}).get("source")
            if img:
                return img
    except Exception as e:
        print("    wiki err", lang, kw, e)
    return None

def download(url, dest):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=25).read()
        if len(data) < 1500:  # too small / placeholder
            return False
        open(dest, "wb").write(data)
        return True
    except Exception as e:
        print("    dl err", e); return False

def main():
    manifest = {}
    for t in TARGETS:
        vid = t["video_id"]
        outdir = os.path.join(ASSETS, vid)
        os.makedirs(outdir, exist_ok=True)
        imgs = {"thumb": None, "frames": [], "related": []}
        # 1) youtube thumbnail
        src = os.path.join(THUMBS, f"{vid}.jpg")
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(outdir, "thumb.jpg")); imgs["thumb"] = "thumb.jpg"
        # 2) frames already present
        fr = sorted(os.path.basename(p) for p in __import__("glob").glob(os.path.join(outdir, "frames", "frame_*.jpg")))
        imgs["frames"] = [f"frames/{f}" for f in fr]
        # 3) related subject images
        lang, kws = KW.get(vid, ("ko", [t["title"][:20]]))
        n = 0
        for kw in kws:
            img = wiki_image(lang, kw)
            if not img:
                continue
            ext = ".png" if img.lower().split("?")[0].endswith(".png") else ".jpg"
            dest = os.path.join(outdir, f"related_{n+1}{ext}")
            if download(img, dest):
                imgs["related"].append(os.path.basename(dest)); n += 1
        manifest[vid] = {"topic": t["topic"], "region": t["region"], "title": t["title"], "images": imgs}
        print(f"  {t['topic']}/{t['region']} {vid}: thumb={bool(imgs['thumb'])} frames={len(imgs['frames'])} related={len(imgs['related'])}")
    json.dump(manifest, open(os.path.join(ASSETS, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("related_images done ->", os.path.join(ASSETS, "manifest.json"))

if __name__ == "__main__":
    raise SystemExit(main())
