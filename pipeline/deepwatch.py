# -*- coding: utf-8 -*-
"""Drive the /watch skill over the rank-1 (per topic) + selected rising videos.
Downloads video (<=720p), extracts frames, pulls native ko/ja captions into
site/assets/<video_id>/. Idempotent: skips a video whose frames already exist.
Then writes a deduped, time-sampled transcript.txt next to the frames so the
summary/timeline step can read it cheaply."""
import os, sys, re, json, glob, subprocess, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SKILL = r"C:\Users\hikim\.claude\plugins\cache\claude-video\watch\0.1.3\scripts\watch.py"
PROJ = r"C:\Users\hikim\Desktop\workplace\YoutubeAnalysis"
ASSETS = os.path.join(PROJ, "site", "assets")
os.makedirs(ASSETS, exist_ok=True)

TARGETS = json.load(open(os.path.join(PROJ, "pipeline", "watch_targets.json"), encoding="utf-8"))

def compact_vtt(path):
    """Return [(hh:mm:ss, text)] deduped (auto-caption rolls repeat lines)."""
    rows, last, ts = [], None, "00:00:00"
    for ln in open(path, encoding="utf-8", errors="ignore"):
        m = re.match(r"(\d\d:\d\d:\d\d)\.\d+ -->", ln)
        if m:
            ts = m.group(1); continue
        t = re.sub(r"<[^>]+>", "", ln).strip()
        if not t or t in ("WEBVTT",) or t.startswith(("Kind:", "Language:", "NOTE")):
            continue
        if t == last:
            continue
        last = t
        rows.append((ts, t))
    return rows

def sample(rows, n=45):
    """Even time sampling to ~n lines so long videos stay cheap to read."""
    if len(rows) <= n:
        return rows
    step = len(rows) / n
    return [rows[int(i*step)] for i in range(n)]

def run_watch(vid, url, outdir):
    frames = glob.glob(os.path.join(outdir, "frames", "frame_*.jpg"))
    if frames:
        print(f"  [skip] {vid}: {len(frames)} frames already present")
        return True
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    cmd = [sys.executable, SKILL, url, "--max-frames", "12", "--resolution", "480", "--out-dir", outdir]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    ok = bool(glob.glob(os.path.join(outdir, "frames", "frame_*.jpg")))
    print(f"  [{'ok' if ok else 'FAIL'}] {vid} (exit {r.returncode})")
    if not ok:
        print("    stderr tail:", (r.stderr or "")[-400:].replace("\n", " "))
    return ok

def write_transcript(vid, outdir):
    vtts = sorted(glob.glob(os.path.join(outdir, "download", "*.vtt")))
    # prefer ko/ja original
    def pr(p):
        n = os.path.basename(p).lower()
        return (".ko" in n)*0 + (".ja" in n and ".ko" not in n)*1 or (0 if ".ko" in n else (1 if ".ja" in n else (2 if "orig" in n else 3)))
    if not vtts:
        print(f"    no captions for {vid} (frames-only)")
        return 0
    vtts.sort(key=lambda p: (0 if ".ko" in p.lower() else 1 if ".ja" in p.lower() else 2 if "orig" in p.lower() else 3))
    rows = compact_vtt(vtts[0])
    s = sample(rows, 45)
    out = os.path.join(outdir, "transcript.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# source caption: {os.path.basename(vtts[0])} | full {len(rows)} lines -> sampled {len(s)}\n")
        for ts, t in s:
            f.write(f"[{ts}] {t}\n")
    print(f"    transcript {vid}: {len(rows)} lines -> {len(s)} sampled")
    return len(rows)

def main():
    only = set(sys.argv[1:])  # optionally restrict to given video ids
    for t in TARGETS:
        vid = t["video_id"]
        if only and vid not in only:
            continue
        outdir = os.path.join(ASSETS, vid)
        print(f"-> {t['topic']}/{t['region']} {vid} :: {t['title'][:40]}")
        if run_watch(vid, t["url"], outdir):
            write_transcript(vid, outdir)
    print("deepwatch done.")

if __name__ == "__main__":
    raise SystemExit(main())
