import os
import urllib.request
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
FONT_DIR = r"C:\Windows\Fonts"
F_BLACK = os.path.join(FONT_DIR, "NotoSansKR-Bold.ttf")
F_BOLD = os.path.join(FONT_DIR, "NotoSansKR-Bold.ttf")
F_REGULAR = os.path.join(FONT_DIR, "NotoSansKR-Regular.ttf")
# Fallback for glyphs missing from Noto Sans KR (e.g. Japanese-only kanji in
# channel names like 桜庭スカッと劇場, 大谷解説TV) -- Noto Sans KR only bundles
# the hanja subset used in Korean, not the full Japanese kanji repertoire.
F_JP_BOLD = os.path.join(FONT_DIR, "YuGothB.ttc")
F_JP_REGULAR = os.path.join(FONT_DIR, "YuGothR.ttc")

WHITE = (255, 255, 255, 255)
YELLOW = (255, 214, 10, 255)
BLUE = (60, 120, 220, 255)

CIRCLED = ["①", "②", "③", "④", "⑤"]

FLAG_COLORS = {
    "KR": None, "JP": None, "US": None, "GB": None, "DE": None, "FR": None,
}


def font(path, size):
    return ImageFont.truetype(path, size)


_CMAP_CACHE = {}


def _cmap(path):
    if path not in _CMAP_CACHE:
        from fontTools.ttLib import TTFont
        tt = TTFont(path, fontNumber=0, lazy=True)
        chars = set()
        for table in tt["cmap"].tables:
            chars |= set(table.cmap.keys())
        _CMAP_CACHE[path] = chars
    return _CMAP_CACHE[path]


def _has_glyph(path, ch):
    if ch == " ":
        return True
    return ord(ch) in _cmap(path)


def _fallback_path_for(primary_path):
    return F_JP_BOLD if primary_path in (F_BLACK, F_BOLD) else F_JP_REGULAR


def _segments(text, primary_path):
    """Split text into (substring, use_fallback) runs based on glyph coverage
    of the primary font."""
    if not text:
        return []
    segs = []
    cur = text[0]
    cur_fb = not _has_glyph(primary_path, text[0])
    for ch in text[1:]:
        fb = not _has_glyph(primary_path, ch)
        if fb == cur_fb:
            cur += ch
        else:
            segs.append((cur, cur_fb))
            cur, cur_fb = ch, fb
    segs.append((cur, cur_fb))
    return segs


def mixed_length(draw, text, primary_font):
    fb_font = font(_fallback_path_for(primary_font.path), primary_font.size)
    total = 0
    for seg, is_fb in _segments(text, primary_font.path):
        total += draw.textlength(seg, font=fb_font if is_fb else primary_font)
    return total


def mixed_text(draw, xy, text, primary_font, fill):
    fb_font = font(_fallback_path_for(primary_font.path), primary_font.size)
    x, y = xy
    for seg, is_fb in _segments(text, primary_font.path):
        f = fb_font if is_fb else primary_font
        draw.text((x, y), seg, font=f, fill=fill)
        x += draw.textlength(seg, font=f)
    return x


def fetch_thumbnail(video_id, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{video_id}.jpg")
    if os.path.exists(path):
        return Image.open(path).convert("RGB")
    for name in ["maxresdefault.jpg", "hqdefault.jpg"]:
        url = f"https://i.ytimg.com/vi/{video_id}/{name}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=15).read()
            if len(data) < 2000:
                continue
            img = Image.open(BytesIO(data)).convert("RGB")
            img.save(path, quality=92)
            return img
        except Exception:
            continue
    raise RuntimeError(f"failed to fetch thumbnail for {video_id}")


def cover_image(img):
    tw, th = W, H
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale) + 1, int(ih * scale) + 1
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def rounded_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def fit_title_channel(draw, title, channel, fnt, max_width):
    """Fit '{title} · {channel}' into one line, shortening the title with an
    ellipsis as needed but always keeping the channel name fully intact."""
    suffix = f" · {channel}"
    if mixed_length(draw, title + suffix, fnt) <= max_width:
        return title + suffix
    t = title
    while t and mixed_length(draw, t + "…" + suffix, fnt) > max_width:
        t = t[:-1]
    if t:
        return t + "…" + suffix
    # channel name alone is already too wide; hard-truncate it too
    c = channel
    while c and mixed_length(draw, c + "…", fnt) > max_width:
        c = c[:-1]
    return (c + "…") if c else channel


def wrap_text(text, fnt, max_width, draw):
    lines = []
    cur = ""
    for ch in text:
        test = cur + ch
        w = draw.textlength(test, font=fnt)
        if w > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def gradient_overlay(size, top_alpha=0.0, mid_alpha=0.45, bottom_alpha=0.75):
    w, h = size
    overlay = Image.new("L", (1, h), 0)
    for y in range(h):
        t = y / h
        if t < 0.35:
            a = top_alpha + (mid_alpha - top_alpha) * (t / 0.35)
        elif t < 0.65:
            a = mid_alpha
        else:
            a = mid_alpha + (bottom_alpha - mid_alpha) * ((t - 0.65) / 0.35)
        overlay.putpixel((0, y), int(a * 255))
    overlay = overlay.resize((w, h))
    black = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    black.putalpha(overlay)
    return black


def watermark(base):
    d = ImageDraw.Draw(base)
    fnt = font(F_BLACK, 40)
    text = "H"
    tw = d.textlength(text, font=fnt)
    cx = W // 2
    y = H - 90
    circ_r = 34
    d.ellipse((cx - circ_r, y - circ_r + 10, cx + circ_r, y + circ_r + 10), fill=(0, 0, 0, 110))
    d.text((cx - tw / 2, y - 20), text, font=fnt, fill=(255, 255, 255, 230))


def draw_flag_icon(draw, x, y, w, h, code):
    radius = 4
    if code == "KR":
        draw.rounded_rectangle((x, y, x + w, y + h), radius, fill=(255, 255, 255, 255))
        cx, cy = x + w / 2, y + h / 2
        r = min(w, h) * 0.3
        draw.pieslice((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=(205, 40, 50, 255))
        draw.pieslice((cx - r, cy - r, cx + r, cy + r), 0, 180, fill=(30, 70, 160, 255))
    elif code == "JP":
        draw.rounded_rectangle((x, y, x + w, y + h), radius, fill=(255, 255, 255, 255))
        cx, cy = x + w / 2, y + h / 2
        r = min(w, h) * 0.3
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(188, 0, 45, 255))
    elif code == "US":
        draw.rounded_rectangle((x, y, x + w, y + h), radius, fill=(178, 34, 52, 255))
        stripe_h = h / 7
        for i in range(7):
            if i % 2 == 1:
                draw.rectangle((x, y + i * stripe_h, x + w, y + (i + 1) * stripe_h), fill=(255, 255, 255, 255))
        draw.rectangle((x, y, x + w * 0.4, y + h * 0.5), fill=(60, 59, 110, 255))
    elif code == "GB":
        draw.rectangle((x, y, x + w, y + h), fill=(1, 33, 105, 255))
        lw = max(2, int(h * 0.16))
        draw.line((x, y, x + w, y + h), fill=(255, 255, 255, 255), width=lw)
        draw.line((x + w, y, x, y + h), fill=(255, 255, 255, 255), width=lw)
        lw2 = max(1, int(h * 0.07))
        draw.line((x, y, x + w, y + h), fill=(200, 16, 46, 255), width=lw2)
        draw.line((x + w, y, x, y + h), fill=(200, 16, 46, 255), width=lw2)
        draw.rectangle((x + w / 2 - h * 0.17, y, x + w / 2 + h * 0.17, y + h), fill=(255, 255, 255, 255))
        draw.rectangle((x, y + h / 2 - h * 0.13, x + w, y + h / 2 + h * 0.13), fill=(255, 255, 255, 255))
        draw.rectangle((x + w / 2 - h * 0.09, y, x + w / 2 + h * 0.09, y + h), fill=(200, 16, 46, 255))
        draw.rectangle((x, y + h / 2 - h * 0.07, x + w, y + h / 2 + h * 0.07), fill=(200, 16, 46, 255))
        draw.rounded_rectangle((x, y, x + w, y + h), radius, outline=(255, 255, 255, 0), width=1)
    elif code == "DE":
        stripe_h = h / 3
        draw.rectangle((x, y, x + w, y + stripe_h), fill=(0, 0, 0, 255))
        draw.rectangle((x, y + stripe_h, x + w, y + 2 * stripe_h), fill=(221, 0, 0, 255))
        draw.rectangle((x, y + 2 * stripe_h, x + w, y + h), fill=(255, 206, 0, 255))
    elif code == "FR":
        stripe_w = w / 3
        draw.rectangle((x, y, x + stripe_w, y + h), fill=(0, 85, 164, 255))
        draw.rectangle((x + stripe_w, y, x + 2 * stripe_w, y + h), fill=(255, 255, 255, 255))
        draw.rectangle((x + 2 * stripe_w, y, x + w, y + h), fill=(239, 65, 53, 255))
    draw.rounded_rectangle((x, y, x + w, y + h), radius, outline=(255, 255, 255, 160), width=2)


def make_cover(video_id, cache_dir, out_path, country_code, country_name, date_str,
               page_total, rank_lines):
    thumb = cover_image(fetch_thumbnail(video_id, cache_dir))
    base = thumb.convert("RGBA")
    base.alpha_composite(gradient_overlay((W, H), 0.15, 0.45, 0.78))
    draw = ImageDraw.Draw(base)

    f_logo1 = font(F_BLACK, 30)
    f_logo2 = font(F_REGULAR, 22)
    rounded_rect(draw, (64, 56, 260, 150), 14, (0, 0, 0, 235))
    draw.text((84, 68), "HOT", font=f_logo1, fill=WHITE)
    draw.text((84, 106), "YouTube", font=f_logo2, fill=WHITE)

    f_page = font(F_BOLD, 32)
    f_date = font(F_BOLD, 44)
    f_tag = font(F_BOLD, 40)
    page_text = f"1/{page_total}"
    date_text = date_str
    tag_text = f"· {country_name} TOP3"

    tw = draw.textlength(page_text, font=f_page)
    draw.text((W - 64 - tw, 56), page_text, font=f_page, fill=WHITE)
    tw = draw.textlength(date_text, font=f_date)
    draw.text((W - 64 - tw, 96), date_text, font=f_date, fill=WHITE)
    tw = draw.textlength(tag_text, font=f_tag)
    flag_w, flag_h = 44, 32
    draw.text((W - 64 - tw, 152), tag_text, font=f_tag, fill=WHITE)
    draw_flag_icon(draw, W - 64 - tw - flag_w - 8, 152 + 4, flag_w, flag_h, country_code)

    f_title = font(F_BLACK, 108)
    draw.text((72, 330), "오늘의", font=f_title, fill=WHITE)
    draw.text((72, 460), "유튜브 이슈영상 순위", font=f_title, fill=WHITE)

    n_lines = len(rank_lines)
    panel_top = 700
    panel_bottom = panel_top + 90 + n_lines * 74 + 20
    rounded_rect(draw, (56, panel_top, 1024, panel_bottom), 24, (0, 0, 0, 150))

    f_tag2 = font(F_BOLD, 40)
    tag2_text = f"{country_name} TOP3"
    draw_flag_icon(draw, 84, panel_top + 24, 44, 32, country_code)
    draw.text((84 + 44 + 12, panel_top + 20), tag2_text, font=f_tag2, fill=WHITE)

    f_item = font(F_BOLD, 38)
    f_num = font(F_BLACK, 40)
    y = panel_top + 90
    for i, (label, title, channel) in enumerate(rank_lines):
        num_str = "★" if label == "star" else CIRCLED[i]
        color = YELLOW if label == "star" else WHITE
        draw.text((84, y), num_str, font=f_num, fill=color)
        max_w = 1024 - 150 - 20
        line = fit_title_channel(draw, title, channel, f_item, max_w)
        mixed_text(draw, (150, y + 2), line, f_item, WHITE)
        y += 74

    f_footer = font(F_BOLD, 40)
    footer_text = country_name
    draw_flag_icon(draw, 72, H - 116, 44, 32, country_code)
    draw.text((72 + 44 + 12, H - 112), footer_text, font=f_footer, fill=(255, 255, 255, 200))

    base.convert("RGB").save(out_path, quality=95)
    print("saved", out_path)


def make_body(video_id, cache_dir, out_path, page_num, page_total, country_code,
              rank_label, channel_name, title_text, desc_text, is_rising=False):
    thumb = cover_image(fetch_thumbnail(video_id, cache_dir))
    base = thumb.convert("RGBA")
    draw = ImageDraw.Draw(base)

    f_page = font(F_BOLD, 32)
    page_str = f"{page_num}/{page_total}"
    tw = draw.textlength(page_str, font=f_page)
    rounded_rect(draw, (W - 64 - tw - 32, 48, W - 64, 48 + 56), 16, (0, 0, 0, 150))
    draw.text((W - 64 - tw - 16, 60), page_str, font=f_page, fill=WHITE)

    f_title = font(F_BLACK, 72)
    f_label = font(F_BOLD, 44)
    f_desc = font(F_REGULAR, 38)
    f_star = font(F_BOLD, 48)

    max_w = W - 72 - 96 - 48
    title_lines = wrap_text(title_text, f_title, max_w, draw)[:2]
    desc_lines = wrap_text(desc_text, f_desc, max_w, draw)[:2]

    star_h = 64 if is_rising else 0
    label_text = f"{rank_label} · {channel_name}" if rank_label else channel_name
    label_w = mixed_length(draw, label_text, f_label) + 40 + 10
    content_w = max(
        [mixed_length(draw, t, f_title) for t in title_lines]
        + [mixed_length(draw, t, f_desc) for t in desc_lines]
        + [label_w]
    )
    panel_left = 56
    panel_width = min(max(content_w + 80, 600), 900)
    panel_right = panel_left + panel_width
    block_h = star_h + len(title_lines) * 86 + 20 + 56 + 20 + len(desc_lines) * 56 + 48
    panel_bottom = H - 140
    panel_top = panel_bottom - block_h
    rounded_rect(draw, (panel_left, panel_top, panel_right, panel_bottom), 24, (0, 0, 0, 160))

    y = panel_top + 24
    x = panel_left + 40
    if is_rising:
        draw.text((x, y), "★ 오늘의 라이징 스타", font=f_star, fill=YELLOW)
        y += star_h
    for line in title_lines:
        mixed_text(draw, (x, y), line, f_title, WHITE)
        y += 86
    y += 10
    draw_flag_icon(draw, x, y + 2, 40, 30, country_code)
    mixed_text(draw, (x + 40 + 10, y), label_text, f_label, WHITE)
    y += 56
    for line in desc_lines:
        mixed_text(draw, (x, y), line, f_desc, (242, 242, 242, 255))
        y += 56

    watermark(base)
    base.convert("RGB").save(out_path, quality=95)
    print("saved", out_path)
