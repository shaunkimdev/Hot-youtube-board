# -*- coding: utf-8 -*-
"""Replicate the /watch behavior with the Gemini API (for unattended CI).

For SELECTED videos (country(KR/JP) issue-score top5 across all topics + all Rising
Star): yt-dlp download -> ffmpeg frames + captions -> send frames+transcript to Gemini
  (multimodal) -> 100자 요약 + 시청자 도움 한 줄.   == what /watch does.
For the rest: text-only summary from title+description+captions (cheap, no download).

Writes summaries.json = { video_id: {"summary","tip","analysis"} } which build_auto.py
prefers over the hand-authored EN3 / description fallback.

Env: GEMINI_API_KEY (required — separate from the GOOGLE_API_KEY used for the
     YouTube Data API elsewhere in this pipeline; a key can hold both scopes if
     the Generative Language API is enabled on it, but a dedicated key is safer),
     GEMINI_MODEL (default gemini-3.1-flash-lite — cheapest current multimodal
     model, used for both the frame-based deep pass and the text-only pass),
     DEEP_MAX (safety cap on # of frame-based deep analyses, default 20 — headroom
     above the structural max of 5(KR)+5(JP)+5(rising)=15 so nothing gets truncated).
Deps: ffmpeg, yt-dlp (CLI), google-genai (pip).
"""
import os, re, json, glob, subprocess, tempfile, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
DEEP_MAX = int(os.environ.get("DEEP_MAX", "20"))
WATCH = "/watch 심층분석(Gemini)"
META = "메타데이터+자막(Gemini)"

try:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])  # raises if unset
except Exception as e:
    print("gemini SDK/key not ready:", e, file=sys.stderr); client = None

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "tip": {"type": "string"},
        "timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "range": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["range", "note"],
            },
        },
    },
    "required": ["summary", "tip", "timeline"],
}


# ---------- clip mechanics (minimal /watch) ----------
def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

_COOKIES = os.path.join(HERE, "cookies.txt")
def _ck():
    return ["--cookies", _COOKIES] if os.path.exists(_COOKIES) else []

def download(url, path):
    _run(["yt-dlp", "-f", "best[height<=480]/best", "--no-playlist",
          "--no-warnings", *_ck(), "-o", path, url])
    return os.path.exists(path)

def video_duration(path):
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "json", path])
    try: return float(json.loads(r.stdout)["format"]["duration"])
    except Exception: return 0.0

def extract_frames(path, n, outdir):
    os.makedirs(outdir, exist_ok=True)
    d = video_duration(path)
    fps = max(min(n / max(d, 1), 2.0), 0.05)
    _run(["ffmpeg", "-i", path, "-vf", f"fps={fps},scale=512:-1",
          "-frames:v", str(n), os.path.join(outdir, "f_%03d.jpg"), "-y"])
    return sorted(glob.glob(os.path.join(outdir, "f_*.jpg")))[:n]

def fetch_captions(url, outdir):
    _run(["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs",
          "--sub-langs", "ko,ja,en", "--convert-subs", "vtt", *_ck(),
          "--no-warnings", "-o", os.path.join(outdir, "sub"), url])
    lines = []
    for vtt in glob.glob(os.path.join(outdir, "*.vtt")):
        for ln in open(vtt, encoding="utf-8", errors="ignore"):
            ln = ln.strip()
            if not ln or "-->" in ln or ln.isdigit() or ln.startswith("WEBVTT"):
                continue
            ln = re.sub(r"<[^>]+>", "", ln)
            if not lines or lines[-1] != ln:
                lines.append(ln)
        break
    return " ".join(lines)[:4000]


# ---------- Gemini summary ----------
def call_gemini(title, channel, transcript, frames, dur_sec=0):
    if client is None:
        return None
    parts = []
    for fp in (frames or [])[:12]:
        try:
            b = open(fp, "rb").read()
            parts.append(types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=b)))
        except Exception:
            pass
    has_frames = bool(parts)
    note = "첨부된 프레임 이미지와 자막을 근거로, " if has_frames else "제목·설명·자막을 근거로, "
    # 길이에 따라 2~5구간
    nseg = 2 if dur_sec <= 20 else 3 if dur_sec <= 90 else 4 if dur_sec <= 360 else 5
    tl_rule = (f"timeline: 영상(약 {int(dur_sec)}초)을 시간 순서로 {nseg}개 구간으로 나눠 각 구간을 "
               'range("0:00~M:SS")와 note(해당 구간 한 줄 내용)로 채워라. ') if has_frames else \
              'timeline: 프레임 분석이 없으므로 빈 배열로 둬라. '
    prompt = (f"다음 유튜브 영상을 한국어로 분석해줘.\n제목: {title}\n채널: {channel}\n"
              f"자막/대사: {transcript[:3000] or '(없음)'}\n\n"
              f"{note}{tl_rule}\n"
              "summary는 영상 내용을 100자 내외로 상세 요약할 것. "
              "tip은 시청자가 알면 도움될 점 한 문장(자극·클릭베이트면 ⚠️로 시작).")
    parts.append(prompt)
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=RESPONSE_SCHEMA,
                max_output_tokens=800,
            ),
        )
        d = json.loads(resp.text)
        tl = [[str(t.get("range", "")), str(t.get("note", ""))] for t in d.get("timeline", [])]
        return d.get("summary", "").strip(), d.get("tip", "").strip(), tl
    except Exception as e:
        print("gemini err:", e, file=sys.stderr); return None


def summarize(v, deep):
    """v: video dict from top3_v3/rising2. Returns (summary, tip, analysis, timeline)."""
    title, channel = v["title"], v["channel"]
    desc = " ".join((v.get("description") or "").split())
    dur = v.get("duration_sec", 0)
    if deep:
        with tempfile.TemporaryDirectory() as td:
            mp4 = os.path.join(td, "v.mp4")
            transcript = fetch_captions(v["url"], td)
            frames = []
            if download(v["url"], mp4):
                frames = extract_frames(mp4, 12, os.path.join(td, "fr"))
            r = call_gemini(title, channel, transcript or desc, frames, dur)
            if r:
                return r[0], r[1], (WATCH if frames else META), r[2]
    # text-only
    r = call_gemini(title, channel, desc, None, dur)
    if r:
        return r[0], r[1], META, r[2]
    # last-resort fallback (no API)
    base = desc if len(desc) >= 20 else title
    return (base[:99], "자동 요약(미검수) — 원본 영상 확인 권장.", META + "(fallback)", [])


def main():
    top = json.load(open(os.path.join(HERE, "top3_v3.json"), encoding="utf-8"))
    rising = json.load(open(os.path.join(HERE, "rising2.json"), encoding="utf-8"))[:5]
    # DEEP set (/watch 심층분석 대상): 나라(KR/JP)별 이슈점수 top5(전 주제 통합) + 모든 라이징스타
    deep_ids = set(v["video_id"] for v in rising)
    for region in ("KR", "JP"):
        pool = [v for k, lst in top.items() if k.startswith(region + "|") for v in lst]
        pool.sort(key=lambda v: v.get("issue_score", 0), reverse=True)
        deep_ids.update(v["video_id"] for v in pool[:5])
    # safety cap (구조상 최대 5+5+5=15건이라 기본값에서는 잘리지 않음)
    deep_ids = set(list(deep_ids)[:DEEP_MAX])

    out = {}
    allv = [v for lst in top.values() for v in lst] + rising
    for v in allv:
        vid = v["video_id"]
        if vid in out: continue
        deep = vid in deep_ids
        s, t, a, tl = summarize(v, deep)
        out[vid] = {"summary": s, "tip": t, "analysis": a, "timeline": tl}
        print(f"[{'DEEP' if deep else 'text'}] {channel_safe(v)} :: {s[:40]}")
    json.dump(out, open(os.path.join(HERE, "summaries.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"summaries.json written: {len(out)} videos ({len(deep_ids)} deep)")

def channel_safe(v):
    return (v.get("channel") or "")[:18]

if __name__ == "__main__":
    raise SystemExit(main())
