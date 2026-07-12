"""Shared adapter for the installed ``watch`` skill.

The skill is an agent skill, not a Python package.  This module invokes its
bundled ``scripts/watch.py`` and turns the markdown report into stable project
assets that the dashboard, card-news and clip builders can reuse.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
ASSETS = PROJECT / "site" / "assets"
THUMBS = HERE / "thumbs"


def find_watch_script() -> Path | None:
    candidates = []
    if os.environ.get("WATCH_SKILL_DIR"):
        candidates.append(Path(os.environ["WATCH_SKILL_DIR"]) / "scripts" / "watch.py")
    home = Path.home()
    candidates += [
        home / ".agents" / "skills" / "watch" / "scripts" / "watch.py",
        home / ".codex" / "skills" / "watch" / "scripts" / "watch.py",
    ]
    # Backward compatibility with the old Claude plugin cache.
    candidates += sorted(
        (home / ".claude" / "plugins" / "cache" / "claude-video" / "watch").glob("*/scripts/watch.py"),
        reverse=True,
    )
    return next((p for p in candidates if p.is_file()), None)


def _parse_report(report: str) -> tuple[list[dict], str]:
    frames = []
    pattern = re.compile(r"^- `([^`]+)` \(t=([^,]+), reason=([^\)]+)\)$", re.M)
    for path, timestamp, reason in pattern.findall(report):
        frames.append({"path": path, "timestamp": timestamp, "seconds": _seconds(timestamp), "reason": reason})
    transcript = ""
    match = re.search(r"## Transcript.*?```\s*\n(.*?)\n```", report, re.S)
    if match:
        transcript = match.group(1).strip()
    return frames, transcript


def _seconds(value: str) -> float:
    parts = [float(x) for x in value.strip().split(":")]
    total = 0.0
    for part in parts:
        total = total * 60 + part
    return total


def _find_video(work: Path) -> Path | None:
    extensions = {".mp4", ".webm", ".mkv", ".mov"}
    return next((p for p in work.rglob("*") if p.suffix.lower() in extensions), None)


def run_watch(video: dict, max_frames: int = 12, force: bool = False) -> dict:
    """Run watch once and return/update ``site/assets/<id>/watch.json``."""
    vid = video["video_id"]
    work = ASSETS / vid
    manifest_path = work / "watch.json"
    if manifest_path.exists() and not force:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if data.get("frames") or data.get("transcript"):
            return data

    script = find_watch_script()
    if not script:
        raise RuntimeError("watch skill not found; install it or set WATCH_SKILL_DIR")
    work.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(script), video["url"], "--detail", "balanced",
        "--max-frames", str(max_frames), "--resolution", "512",
        "--out-dir", str(work),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    # Some YouTube formats reject the web client with 403 while the public
    # Android VR client still works without browser cookies. Download through
    # that client and feed the local file back to the real watch skill so frame
    # selection and Whisper transcription remain watch-owned.
    if result.returncode:
        manual = work / "manual"
        manual.mkdir(parents=True, exist_ok=True)
        fallback = manual / "source.mp4"
        if not fallback.exists():
            subprocess.run([
                "yt-dlp", "--no-playlist", "--extractor-args", "youtube:player_client=android_vr",
                "-f", "best[height<=720]/best", "--retries", "5", "--fragment-retries", "5",
                "-o", str(fallback), video["url"],
            ], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if fallback.exists():
            local_cmd = cmd[:]
            local_cmd[2] = str(fallback)
            result = subprocess.run(local_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    frames, transcript = _parse_report(result.stdout or "")
    source = _find_video(work)
    data = {
        "video_id": vid,
        "url": video["url"],
        "watch_script": str(script),
        "exit_code": result.returncode,
        "frames": frames,
        "transcript": transcript,
        "source_video": str(source) if source else "",
    }
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Card-news uses this as its visual source. Prefer a scene near the middle,
    # avoiding intro/outro frames when possible.
    if frames:
        representative = frames[len(frames) // 2]["path"]
        src = Path(representative)
        if src.exists():
            THUMBS.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, THUMBS / f"{vid}.jpg")
    if result.returncode and not frames and not transcript:
        raise RuntimeError((result.stderr or result.stdout or "watch failed")[-800:])
    return data


def update_analysis(video_id: str, summary: str, tip: str, timeline: list) -> None:
    path = ASSETS / video_id / "watch.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update({"summary": summary, "tip": tip, "timeline": timeline})
    if timeline:
        match = re.search(r"(?:\d+:)?\d+:\d+", str(timeline[0][0]))
        if match:
            data["highlight_start"] = _seconds(match.group(0))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_watch(video_id: str) -> dict:
    path = ASSETS / video_id / "watch.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
