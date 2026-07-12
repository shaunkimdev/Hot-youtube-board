# -*- coding: utf-8 -*-
"""Daily pipeline orchestrator.
Runs: discover2        (Search API, 12개 고정 주제 x KR/JP/US 수집, 라이브/공식채널 제외)
   -> longform_rising  (longform filter + subscriber lookup)
   -> rising_search    (Rising Star Best5 via Search API, 쇼츠 제외)
   -> build_auto       (data.json + Excel + self-contained website)

Requires env var GOOGLE_API_KEY. Run:  python run_daily.py
"""
import subprocess, sys, os, datetime, io
# force UTF-8 stdout: collected titles/channels can now contain any script (Bengali,
# Devanagari, Cyrillic, ...) now that US/GB/DE/FR are in scope, and Windows' default
# console codepage (cp949 under a Korean locale) can't encode most of them -> crash.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "run.log")

def log(msg):
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def main():
    if not os.environ.get("GOOGLE_API_KEY"):
        log("ERROR: GOOGLE_API_KEY not set."); return 1
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    steps = ["discover2.py", "longform_rising.py", "rising_search.py"]
    if os.environ.get("GEMINI_API_KEY"):
        steps.append("summarize_llm.py")   # Gemini API summaries (/watch behavior)
    else:
        log("note: GEMINI_API_KEY not set -> skipping LLM summaries (build will use fallback)")
    steps.append("build_auto.py")
    log(f"=== daily run start ({datetime.date.today().isoformat()}) ===")
    for s in steps:
        log(f"-> {s}")
        r = subprocess.run([sys.executable, os.path.join(HERE, s)], cwd=HERE, env=env,
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            log(f"FAILED {s} (exit {r.returncode})\n{r.stderr[-1500:]}"); return r.returncode
        tail = (r.stdout or "").strip().splitlines()[-1:]
        log(f"   ok {s} {tail}")
    log("=== daily run done ===")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
