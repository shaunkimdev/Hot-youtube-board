"""Render Instagram cardnews pages."""
from __future__ import annotations

import os
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
FONT_DIR = r"C:\Windows\Fonts"
F_BLACK = os.path.join(FONT_DIR, "NotoSansKR-Bold.ttf")
F_BOLD = os.path.join(FONT_DIR, "NotoSansKR-Bold.ttf")
F_REGULAR = os.path.join(FONT_DIR, "NotoSansKR-Regular.ttf")
F_JP_BOLD = os.path.join(FONT_DIR, "YuGothB.ttc")
F_JP_REGULAR = os.path.join(FONT_DIR, "YuGothR.ttc")

WHITE = (255, 255, 255, 255)
MUTED = (232, 232, 232, 255)
YELLOW = (255, 214, 10, 255)

_CMAP_CACHE: dict[str, set[int]] = {}
CIRCLED = ["①", "②", "③", "★"]


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _cmap(path: str) -> set[int]:
    if path not in _CMAP_CACHE:
        from fontTools.ttLib import TTFont

        tt = TTFont(path, fontNumber=0, lazy=True)
        chars = set()
        for table in tt["cmap"].tables:
            chars |= set(table.cmap.keys())
        _CMAP_CACHE[path] = chars
    return _CMAP_CACHE[path]


def _has_glyph(path: str, char: str) -> bool:
    return char == " " or ord(char) in _cmap(path)


def _fallback_path(primary_path: str) -> str:
    return F_JP_BOLD if primary_path in (F_BLACK, F_BOLD) else F_JP_REGULAR


def _segments(text: str, primary_path: str) -> list[tuple[str, bool]]:
    if not text:
        return []
    chunks: list[tuple[str, bool]] = []
    current = text[0]
    fallback = not _has_glyph(primary_path, text[0])
    for char in text[1:]:
        use_fallback = not _has_glyph(primary_path, char)
        if use_fallback == fallback:
            current += char
        else:
            chunks.append((current, fallback))
            current = char
            fallback = use_fallback
    chunks.append((current, fallback))
    return chunks


def mixed_text_length(draw: ImageDraw.ImageDraw, text: str, primary_font: ImageFont.FreeTypeFont) -> float:
    fallback_font = font(_fallback_path(primary_font.path), primary_font.size)
    return sum(
        draw.textlength(chunk, font=fallback_font if use_fallback else primary_font)
        for chunk, use_fallback in _segments(text, primary_font.path)
    )


def mixed_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, primary_font, fill) -> float:
    fallback_font = font(_fallback_path(primary_font.path), primary_font.size)
    x, y = xy
    for chunk, use_fallback in _segments(text, primary_font.path):
        active_font = fallback_font if use_fallback else primary_font
        draw.text((x, y), chunk, font=active_font, fill=fill)
        x += draw.textlength(chunk, font=active_font)
    return x


def wrap_text(draw: ImageDraw.ImageDraw, text: str, active_font, max_width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        if mixed_text_length(draw, trial, active_font) <= max_width or not current:
            current = trial
        else:
            lines.append(current.strip())
            current = char
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current.strip())
    if len(lines) == max_lines and current and mixed_text_length(draw, current, active_font) > max_width:
        lines[-1] = lines[-1][:-1].rstrip() + "…"
    return [line for line in lines if line]


def fetch_thumbnail(video_id: str, cache_dir: str) -> Image.Image:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    path = Path(cache_dir) / f"{video_id}.jpg"
    if path.exists():
        return Image.open(path).convert("RGB")
    for name in ("maxresdefault.jpg", "hqdefault.jpg"):
        url = f"https://i.ytimg.com/vi/{video_id}/{name}"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(request, timeout=20).read()
            if len(data) < 2000:
                continue
            image = Image.open(BytesIO(data)).convert("RGB")
            image.save(path, quality=92)
            return image
        except Exception:
            continue
    raise RuntimeError(f"failed to fetch thumbnail for {video_id}")


def load_visual(video_id: str, cache_dir: str, image_path: str | None = None) -> Image.Image:
    if image_path and Path(image_path).exists():
        return Image.open(image_path).convert("RGB")
    return fetch_thumbnail(video_id, cache_dir)


def cover_image(image: Image.Image) -> Image.Image:
    scale = max(W / image.width, H / image.height)
    resized = image.resize((int(image.width * scale) + 1, int(image.height * scale) + 1), Image.LANCZOS)
    left = (resized.width - W) // 2
    top = (resized.height - H) // 2
    return resized.crop((left, top, left + W, top + H))


def rounded_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def gradient_overlay(size, top_alpha=0.15, mid_alpha=0.45, bottom_alpha=0.8):
    width, height = size
    overlay = Image.new("L", (1, height), 0)
    for y in range(height):
        t = y / max(height - 1, 1)
        if t < 0.35:
            alpha = top_alpha + (mid_alpha - top_alpha) * (t / 0.35)
        elif t < 0.7:
            alpha = mid_alpha
        else:
            alpha = mid_alpha + (bottom_alpha - mid_alpha) * ((t - 0.7) / 0.3)
        overlay.putpixel((0, y), int(alpha * 255))
    overlay = overlay.resize((width, height))
    black = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    black.putalpha(overlay)
    return black


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
        for index in range(7):
            if index % 2 == 1:
                draw.rectangle((x, y + index * stripe_h, x + w, y + (index + 1) * stripe_h), fill=(255, 255, 255, 255))
        draw.rectangle((x, y, x + w * 0.4, y + h * 0.5), fill=(60, 59, 110, 255))
    draw.rounded_rectangle((x, y, x + w, y + h), radius, outline=(255, 255, 255, 160), width=2)


def watermark(base: Image.Image) -> None:
    draw = ImageDraw.Draw(base)
    active_font = font(F_BLACK, 40)
    text = "H"
    text_w = draw.textlength(text, font=active_font)
    cx = W // 2
    y = H - 88
    r = 34
    draw.ellipse((cx - r, y - r, cx + r, y + r), fill=(0, 0, 0, 110))
    draw.text((cx - text_w / 2, y - 30), text, font=active_font, fill=(255, 255, 255, 230))


def fit_title_channel(draw, title: str, channel: str, active_font, max_width: int) -> str:
    suffix = f" · {channel}"
    if mixed_text_length(draw, title + suffix, active_font) <= max_width:
        return title + suffix
    trimmed = title
    while trimmed and mixed_text_length(draw, trimmed + "…" + suffix, active_font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + "…" if trimmed else title[:8] + "…") + suffix


def make_cover(video_id, cache_dir, out_path, country_code, country_name, date_str, page_total, rank_lines):
    thumb = cover_image(fetch_thumbnail(video_id, cache_dir))
    base = thumb.convert("RGBA")
    base.alpha_composite(gradient_overlay((W, H)))
    draw = ImageDraw.Draw(base)

    logo_bold = font(F_BLACK, 30)
    logo_regular = font(F_REGULAR, 22)
    rounded_rect(draw, (64, 56, 260, 150), 14, (0, 0, 0, 235))
    draw.text((84, 68), "HOT", font=logo_bold, fill=WHITE)
    draw.text((84, 106), "YouTube", font=logo_regular, fill=WHITE)

    page_font = font(F_BOLD, 32)
    date_font = font(F_BOLD, 44)
    tag_font = font(F_BOLD, 40)
    page_text = f"1/{page_total}"
    tag_text = f"{country_name} TOP"

    draw.text((W - 64 - draw.textlength(page_text, font=page_font), 56), page_text, font=page_font, fill=WHITE)
    draw.text((W - 64 - draw.textlength(date_str, font=date_font), 96), date_str, font=date_font, fill=WHITE)
    draw.text((W - 64 - draw.textlength(tag_text, font=tag_font), 152), tag_text, font=tag_font, fill=WHITE)
    draw_flag_icon(draw, W - 64 - draw.textlength(tag_text, font=tag_font) - 52, 156, 44, 32, country_code)

    title_font = font(F_BLACK, 104)
    draw.text((72, 320), "오늘의", font=title_font, fill=WHITE)
    draw.text((72, 452), "유튜브 이슈", font=title_font, fill=WHITE)

    item_font = font(F_BOLD, 36)
    num_font = font(F_BLACK, 40)
    panel_top = 706
    panel_bottom = panel_top + 110 + len(rank_lines) * 72
    rounded_rect(draw, (56, panel_top, 1024, panel_bottom), 24, (0, 0, 0, 150))

    draw_flag_icon(draw, 84, panel_top + 24, 44, 32, country_code)
    draw.text((140, panel_top + 18), f"{country_name} TODAY", font=tag_font, fill=WHITE)

    y = panel_top + 92
    max_width = 1024 - 150 - 24
    for index, (label, title, channel) in enumerate(rank_lines):
        mark = CIRCLED[index if label != "star" else 3]
        color = YELLOW if label == "star" else WHITE
        draw.text((84, y), mark, font=num_font, fill=color)
        line = fit_title_channel(draw, title, channel, item_font, max_width)
        mixed_text(draw, (150, y + 2), line, item_font, WHITE)
        y += 72

    footer_font = font(F_BOLD, 40)
    draw_flag_icon(draw, 72, H - 116, 44, 32, country_code)
    draw.text((128, H - 112), country_name, font=footer_font, fill=(255, 255, 255, 200))
    base.convert("RGB").save(out_path, quality=95)


def make_segment_card(
    video_id: str,
    cache_dir: str,
    out_path: str,
    image_path: str | None,
    page_num: int,
    page_total: int,
    country_code: str,
    header_text: str,
    badge_text: str,
    video_title: str,
    channel_name: str,
    views_text: str,
    segment_title: str,
    segment_desc: str,
    segment_note: str,
):
    image = cover_image(load_visual(video_id, cache_dir, image_path))
    base = image.convert("RGBA")
    base.alpha_composite(gradient_overlay((W, H), top_alpha=0.05, mid_alpha=0.28, bottom_alpha=0.78))
    draw = ImageDraw.Draw(base)

    page_font = font(F_BOLD, 30)
    page_text = f"{page_num}/{page_total}"
    page_w = draw.textlength(page_text, font=page_font)
    rounded_rect(draw, (W - 64 - page_w - 32, 48, W - 64, 104), 16, (0, 0, 0, 150))
    draw.text((W - 64 - page_w - 16, 60), page_text, font=page_font, fill=WHITE)

    header_font = font(F_BOLD, 33)
    badge_font = font(F_BOLD, 30)
    meta_title_font = font(F_BOLD, 28)
    meta_font = font(F_REGULAR, 24)
    title_font = font(F_BLACK, 64)
    desc_font = font(F_REGULAR, 34)
    note_font = font(F_BOLD, 32)

    panel_left = 56
    panel_right = 980
    panel_top = 720
    panel_bottom = H - 110
    rounded_rect(draw, (panel_left, panel_top, panel_right, panel_bottom), 24, (0, 0, 0, 165))

    x = panel_left + 34
    y = panel_top + 26
    draw_flag_icon(draw, x, y + 2, 40, 30, country_code)
    mixed_text(draw, (x + 54, y), header_text, header_font, WHITE)
    y += 58

    rounded_rect(draw, (x, y, x + 124, y + 44), 12, (255, 214, 10, 240))
    draw.text((x + 18, y + 5), badge_text, font=badge_font, fill=(14, 14, 14, 255))

    meta_x = x + 146
    title_lines = wrap_text(draw, video_title, meta_title_font, panel_right - meta_x - 34, 1)
    mixed_text(draw, (meta_x, y - 1), title_lines[0] if title_lines else video_title[:22], meta_title_font, WHITE)
    meta_line = f"{channel_name} · 조회수 {views_text}"
    mixed_text(draw, (meta_x, y + 28), meta_line, meta_font, (215, 215, 215, 255))
    y += 74

    max_width = panel_right - panel_left - 68
    for line in wrap_text(draw, segment_title, title_font, max_width, 1):
        mixed_text(draw, (x, y), line, title_font, WHITE)
        y += 74

    for line in wrap_text(draw, segment_desc, desc_font, max_width, 2):
        mixed_text(draw, (x, y), line, desc_font, MUTED)
        y += 48

    y += 10
    for line in wrap_text(draw, segment_note, note_font, max_width, 2):
        mixed_text(draw, (x, y), line, note_font, YELLOW)
        y += 42

    watermark(base)
    base.convert("RGB").save(out_path, quality=95)
