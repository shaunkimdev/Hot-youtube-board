# -*- coding: utf-8 -*-
"""Build XPost clips according to XPost.md."""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from deep_translator import GoogleTranslator

from watch_runtime import load_watch, run_watch

ROOT = HERE.parent
SITE = ROOT / "site" / "data.json"
DATE = os.environ.get("RUN_DATE") or datetime.date.today().isoformat()
OUT_ROOT = ROOT / f"영상클립_{DATE}"
TARGET_KR = OUT_ROOT / "한국인타겟"
TARGET_JP = OUT_ROOT / "일본인타겟"
OLD_CLIP_DIRS = [path for path in ROOT.glob("영상클립_*") if path.name != f"영상클립_{DATE}"]
TMP_SUBS = ROOT / ".tools" / "tmp_subs"


def safe_name(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", value or "").strip()


def video_id_from_url(url: str) -> str:
    match = re.search(r"[?&]v=([^&]+)", url)
    return match.group(1) if match else url.rsplit("/", 1)[-1]


def format_views(number: int | None) -> str:
    number = int(number or 0)
    if number >= 10000:
        return f"{number / 10000:.1f}만"
    return f"{number:,}"


def format_ratio(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}배"


def transcript_cues(text: str) -> list[tuple[float, str]]:
    cues = []
    for raw in (text or "").splitlines():
        match = re.match(r"\[([0-9:]+)\]\s*(.*)", raw.strip())
        if not match:
            continue
        stamp = match.group(1)
        parts = [float(part) for part in stamp.split(":")]
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + part
        content = re.sub(r"\s+", " ", match.group(2)).strip(" >")
        if content and content.lower() not in {"[music]", "[__]"}:
            cues.append((seconds, content))
    return cues


def srt_stamp(seconds: float) -> str:
    ms = int(max(0.0, seconds) * 1000)
    hour, ms = divmod(ms, 3600000)
    minute, ms = divmod(ms, 60000)
    second, ms = divmod(ms, 1000)
    return f"{hour:02}:{minute:02}:{second:02},{ms:03}"


def previous_video_ids() -> set[str]:
    ids: set[str] = set()
    pattern = re.compile(r"([A-Za-z0-9_-]{11})")
    for clip_dir in OLD_CLIP_DIRS:
        for file_path in clip_dir.rglob("*"):
            if not file_path.is_file():
                continue
            match = pattern.search(file_path.name)
            if match:
                ids.add(match.group(1))
                continue
            if file_path.suffix.lower() == ".txt":
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                for url in re.findall(r"https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})", text):
                    ids.add(url)
    return ids


def highlight_score(row: dict) -> tuple:
    return (
        row.get("views_per_sub") is not None,
        row.get("views_per_sub") or -1.0,
        row.get("issue") or 0,
        row.get("comments") or 0,
        row.get("likes") or 0,
        row.get("views") or 0,
    )


def select_region_rows(payload: dict, region: str, limit: int, excluded: set[str]) -> list[dict]:
    rows = [row for row in payload["rows"] if row["region"] == region]
    rows.sort(key=highlight_score, reverse=True)
    selected = []
    seen = set()
    for row in rows:
        video_id = video_id_from_url(row["url"])
        if video_id in excluded or video_id in seen:
            continue
        seen.add(video_id)
        enriched = dict(row)
        enriched["video_id"] = video_id
        selected.append(enriched)
        if len(selected) >= limit:
            break
    return selected


def ensure_watch(row: dict) -> dict:
    watch = load_watch(row["video_id"])
    if watch.get("source_video") and Path(watch["source_video"]).exists():
        return watch
    return run_watch(
        {
            "video_id": row["video_id"],
            "url": row["url"],
            "title": row["title"],
            "channel": row["channel"],
        },
        max_frames=12,
        force=False,
    )


def clip_window(row: dict, watch: dict) -> tuple[float, float]:
    highlight = watch.get("highlight_start")
    if highlight is None and watch.get("timeline"):
        match = re.search(r"(?:\d+:)?\d+:\d+", str(watch["timeline"][0][0]))
        if match:
            parts = [float(part) for part in match.group(0).split(":")]
            highlight = 0.0
            for part in parts:
                highlight = highlight * 60 + part
    if highlight is None and watch.get("frames"):
        highlight = watch["frames"][len(watch["frames"]) // 2].get("seconds", 30.0)
    if highlight is None:
        highlight = 30.0
    return max(0.0, float(highlight) - 8.0), 55.0


def build_subtitle_cues(watch: dict, start: float, duration: float) -> list[tuple[float, float, str]]:
    cues = []
    raw_cues = transcript_cues(watch.get("transcript", ""))
    end = start + duration
    in_range = [(sec, text) for sec, text in raw_cues if start <= sec <= end]
    for index, (sec, text) in enumerate(in_range):
        next_sec = in_range[index + 1][0] if index + 1 < len(in_range) else min(end, sec + 4.0)
        cues.append((max(0.0, sec - start), min(duration, next_sec - start), text))
    return cues


def fallback_subtitle_cues(row: dict, duration: float) -> list[tuple[float, float, str]]:
    summary = re.sub(r"\s+", " ", row.get("summary") or row.get("title") or "").strip()
    if not summary:
        summary = row.get("title", "Highlight clip")
    return [(0.3, min(duration, 5.8), summary[:90])]


def translate_batch(lines: list[str], language_code: str) -> list[str]:
    if not lines:
        return []
    translator = GoogleTranslator(source="auto", target=language_code)
    translated = translator.translate_batch(lines)
    return translated if isinstance(translated, list) else [translated]


def write_srt(path: Path, cues: list[tuple[float, float, str]], language_code: str) -> None:
    translated = translate_batch([cue[2] for cue in cues], language_code)
    blocks = []
    for index, ((start, end, _), text) in enumerate(zip(cues, translated), 1):
        blocks.append(f"{index}\n{srt_stamp(start)} --> {srt_stamp(end)}\n{text}")
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def headline(row: dict) -> str:
    topic = row.get("topic", "")
    ratio = format_ratio(row.get("views_per_sub"))
    if ratio != "-":
        return f"{topic} 영상인데 구독자 대비 {ratio} 조회가 붙은 이유"
    return f"지금 반응이 붙는 {topic} 영상 포인트"


def reasons(row: dict) -> list[str]:
    topic = row.get("topic", "")
    return [
        f"{topic} 카테고리 안에서도 반응 지표가 강하게 붙은 영상입니다.",
        f"조회수 {format_views(row.get('views'))}, 댓글 {format_views(row.get('comments'))}로 장면 반응이 분명합니다.",
        "55초 안에 핵심 장면만 바로 확인할 수 있습니다.",
    ]


def build_caption_text(row: dict, audience: str, clip_start: float, clip_duration: float, subtitle_note: str) -> str:
    ko_lines = [
        f"🔥 {headline(row)}",
        "",
        f"{row.get('summary', row['title'])}",
        "",
        "왜 봐야 할까?",
    ]
    for reason in reasons(row):
        ko_lines.append(f"- {reason}")
    ko_lines += [
        "",
        f"📺 채널: {row['channel']}",
        f"👀 조회수: {format_views(row.get('views'))}",
        f"🔗 원본 영상: {row['url']}",
        "",
        f"#{safe_name(row.get('topic', '')).replace(' ', '')} #오늘의영상 #유튜브이슈",
    ]

    if audience == "한국인타겟":
        foreign_lines = [
            "[English]",
            "Watch the strongest moment from today's viral clip.",
            "The reactions hit immediately in this 55-second highlight.",
            f"Original: {row['url']}",
            "#YouTube #ViralClip",
        ]
    else:
        foreign_lines = [
            "[日本語]",
            "今日いちばん反応が強かった場面だけを55秒で見られます。",
            "空気が変わる瞬間をそのまま確認できます。",
            f"元動画: {row['url']}",
            "#YouTube #話題動画",
        ]

    guide_lines = [
        "[영상 파일 안내]",
        f"- 파일: 생성 대상 클립",
        f"- 원본 {int(clip_start)}~{int(clip_start + clip_duration)}초 구간",
        f"- 자막: {subtitle_note}, 16:9",
    ]
    return "\n".join(ko_lines + ["", "---", ""] + foreign_lines + ["", "---", ""] + guide_lines)


def render_clip(
    row: dict,
    audience: str,
    output_dir: Path,
    subtitle_lang: str | None,
    subtitle_status: str,
    order_num: int,
) -> None:
    watch = ensure_watch(row)
    source = Path(watch.get("source_video", ""))
    if not source.exists():
        raise RuntimeError(f"missing source video: {row['video_id']}")
    clip_start, clip_duration = clip_window(row, watch)
    vf = "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720"
    subtitle_note = "원문 자막 유지"
    if subtitle_lang:
        cues = build_subtitle_cues(watch, clip_start, clip_duration)
        if not cues:
            cues = fallback_subtitle_cues(row, clip_duration)
        TMP_SUBS.mkdir(parents=True, exist_ok=True)
        subtitle_path = TMP_SUBS / f"tmp_{row['video_id']}_{subtitle_lang}.srt"
        write_srt(subtitle_path, cues, subtitle_lang)
        esc = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:")
        font_name = "Malgun Gothic" if subtitle_lang == "ko" else "Yu Gothic"
        vf += (
            f",subtitles='{esc}':"
            f"force_style='FontName={font_name},FontSize=16,Bold=1,BorderStyle=3,Outline=2,Alignment=2,MarginV=70'"
        )
        subtitle_note = "한국어 자막" if subtitle_lang == "ko" else "일본어 자막"

    stem = (
        f"{order_num:02d}_"
        f"{safe_name(row.get('topic', 'clip'))}_"
        f"{safe_name(row['channel'])}_"
        f"{safe_name(row['title'])[:30]}_"
        f"{subtitle_status}_16x9"
    )
    mp4_path = output_dir / f"{stem}.mp4"
    txt_path = output_dir / f"캡션_{stem}.txt"
    if mp4_path.exists() and txt_path.exists():
        print(f"[build_xpost_watch] skip existing -> {mp4_path}")
        return
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{clip_start:.2f}",
            "-i",
            str(source),
            "-t",
            f"{clip_duration:.2f}",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(mp4_path),
        ],
        check=True,
    )
    txt_path.write_text(
        build_caption_text(row, audience, clip_start, clip_duration, subtitle_note),
        encoding="utf-8",
    )
    print(f"[build_xpost_watch] {audience} -> {mp4_path}")


def main() -> None:
    payload = json.loads(SITE.read_text(encoding="utf-8"))
    excluded = previous_video_ids()
    kr_rows = select_region_rows(payload, "KR", 5, excluded)
    jp_rows = select_region_rows(payload, "JP", 5, excluded)
    us_rows = select_region_rows(payload, "US", 5, excluded)

    TARGET_KR.mkdir(parents=True, exist_ok=True)
    TARGET_JP.mkdir(parents=True, exist_ok=True)

    order = 1
    for row in kr_rows:
        render_clip(row, "한국인타겟", TARGET_KR, None, "원문유지", order)
        order += 1
    for row in us_rows:
        render_clip(row, "한국인타겟", TARGET_KR, "ko", "한국어자막", order)
        order += 1

    order = 1
    for row in kr_rows:
        render_clip(row, "일본인타겟", TARGET_JP, "ja", "일본어자막", order)
        order += 1
    for row in jp_rows:
        render_clip(row, "일본인타겟", TARGET_JP, None, "원문유지", order)
        order += 1
    for row in us_rows:
        render_clip(row, "일본인타겟", TARGET_JP, "ja", "일본어자막", order)
        order += 1

    print(
        f"[build_xpost_watch] KR target={len(kr_rows) + len(us_rows)} clips, "
        f"JP target={len(kr_rows) + len(jp_rows) + len(us_rows)} clips"
    )


if __name__ == "__main__":
    main()
