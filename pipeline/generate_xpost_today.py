import json, os, re, subprocess, sys, urllib.request
from pathlib import Path
from watch_runtime import load_watch, run_watch
sys.stdout.reconfigure(encoding="utf-8",errors="replace")

DATE="2026-07-11"; ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/f"영상클립_{DATE}"; TMP=ROOT/"worktmp_xpost"/DATE
SELECT={
"KR":["pGia4GyLt-w","Oqla7-zzwPE","YtUAgkOjQtc","zQfHa_JNahM","YdZ2kJV44q4"],
"JP":["weIvS-cLNYA","NETK5jl-wVA","AuQFFqEo5y0","yiiG2LxNoB8","79QEYN-Hheo"],
"US":["ZcXMi--AOjk","Y4wXCpWuu2E","Y6VWPBmr1bg","trqa3ozcsig","If-sc_AwEco"]}

def run(a):
 print("+",*map(str,a),flush=True); subprocess.run(list(map(str,a)),check=True)
def safe(s): return re.sub(r'[\\/:*?"<>|]',"",s)[:35].strip() or "video"
def meta(vid):
 return json.loads(subprocess.check_output(["yt-dlp","--no-playlist","-J",f"https://youtu.be/{vid}"],text=True,encoding="utf-8"))
def srt_parse(p,start,end):
 if not p.exists(): return []
 txt=p.read_text(encoding="utf-8",errors="ignore").replace("\r\n","\n"); cues=[]
 for block in re.split(r"\n\s*\n",txt):
  lines=block.splitlines(); timing=next((x for x in lines if " --> " in x),None)
  if not timing: continue
  mm=re.findall(r"(\d\d):(\d\d):(\d\d)[,.](\d+)",timing)
  if len(mm)!=2: continue
  a=int(mm[0][0])*3600+int(mm[0][1])*60+int(mm[0][2])+int(mm[0][3][:3])/1000
  b=int(mm[1][0])*3600+int(mm[1][1])*60+int(mm[1][2])+int(mm[1][3][:3])/1000
  t=re.sub(r"<[^>]+>",""," ".join(lines[lines.index(timing)+1:])).strip()
  if b>=start and a<=end and t and (not cues or cues[-1][2]!=t): cues.append((max(0,a-start),min(end-start,b-start),t))
 return cues
def translate(lines,lang):
 if not lines:return []
 from deep_translator import GoogleTranslator
 code="ko" if lang=="Korean" else "ja"
 out=GoogleTranslator(source="auto",target=code).translate_batch(lines)
 return out if len(out)==len(lines) else lines
def ts(x):
 ms=round(x*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000); return f"{h:02}:{m:02}:{s:02},{ms:03}"
def write_srt(p,cues,lang):
 trans=translate([x[2] for x in cues],lang)
 p.write_text("\n\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}" for i,((a,b,_),t) in enumerate(zip(cues,trans),1))+"\n",encoding="utf-8")
def caption(p,m,target,start):
 second="English" if target=="한국인타겟" else "日本語"
 p.write_text(f"지금 화제인 영상: {m['title']}\n\n📺 채널: {m.get('channel','')}\n👀 원본 조회수: {m.get('view_count',0):,}\n✅ 40~60초 안에 핵심 장면을 확인하세요.\n\n🔗 원본 영상: {m['webpage_url']}\n\n#유튜브이슈 #오늘의영상 #바이럴\n\n---\n\n[{second} caption]\n{m['title']} — Watch the viral highlight now.\n\n#YouTube #ViralVideo\n\n---\n[영상 파일 안내]\n- 원본 {int(start)}~{int(start+55)}초 구간\n- 16:9 (1280×720)\n",encoding="utf-8")
def one(src,vid,num):
 d=TMP/vid; d.mkdir(parents=True,exist_ok=True); m=meta(vid); dur=float(m.get("duration") or 300)
 url=f"https://youtu.be/{vid}"
 watched=load_watch(vid)
 if not watched:
  try:
   watched=run_watch({"video_id":vid,"url":url,"title":m.get("title",""),"channel":m.get("channel","")},max_frames=12)
  except Exception as e:
   print(f"[watch fallback] {vid}: {e}")
   watched={}
 # Use the first analyzed timeline segment as the clip lead. If analysis did
 # not produce one, center the clip around a representative watch frame.
 suggested=watched.get("highlight_start")
 if suggested is None and watched.get("frames"):
  suggested=watched["frames"][len(watched["frames"])//2].get("seconds")
 start=max(5,min(dur-60,float(suggested) if suggested is not None else dur*.18))
 base=d/"source"
 code={"KR":"ko","JP":"ja","US":"en"}[src]
 if not (d/"source.mp4").exists():
  a=["yt-dlp","--no-playlist","-f","bv*[height<=720]+ba/b[height<=720]","--merge-output-format","mp4"]
  if src=="KR": a += ["--write-auto-sub","--write-sub","--sub-langs",code,"--convert-subs","srt"]
  a += ["--download-sections",f"*{start}-{start+55}","--force-keyframes-at-cuts","-o",str(base)+".%(ext)s",url]
  run(a)
 video=next(d.glob("source.mp4")); subs=list(d.glob("source.*.srt"))
 sub=next((x for x in subs if f".{code}." in x.name),subs[0] if subs else None)
 cues=srt_parse(sub,0,55) if sub else []
 if src=="US" and not cues:
  from youtube_transcript_api import YouTubeTranscriptApi
  api=YouTubeTranscriptApi(); available=api.list(vid)
  try: transcript=available.find_generated_transcript(["en"])
  except Exception: transcript=next(iter(available))
  fetched=transcript.fetch()
  cues=[(max(0,x.start-start),min(55,x.start+x.duration-start),x.text) for x in fetched if x.start+x.duration>=start and x.start<=start+55]
 targets=[]
 if src=="KR": targets=[("한국인타겟",None),("일본인타겟","Japanese")]
 elif src=="JP": targets=[("일본인타겟",None)]
 else: targets=[("한국인타겟","Korean"),("일본인타겟","Japanese")]
 for target,lang in targets:
  od=OUT/target;od.mkdir(parents=True,exist_ok=True); status="원본자막유지"; vf="scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720"
  if lang:
   sp=d/("target_ko.srt" if lang=="Korean" else "target_ja.srt"); write_srt(sp,cues,lang); status="한국어자막" if lang=="Korean" else "일본어자막"
   font="Malgun Gothic" if lang=="Korean" else "Yu Gothic"; esc=str(sp).replace('\\','/').replace(':','\\:')
   vf+=f",subtitles='{esc}':force_style='FontName={font},FontSize=16,Bold=1,BorderStyle=3,Outline=2,Alignment=2,MarginV=70'"
  stem=f"{num}_{safe(m.get('channel',''))}_{safe(m['title'])}_{status}_16x9"; out=od/(stem+".mp4")
  cap=od/("캡션_"+stem+".txt")
  if out.exists() and cap.exists(): continue
  run(["ffmpeg","-y","-i",video,"-vf",vf,"-c:v","libx264","-preset","medium","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-movflags","+faststart",out])
  caption(cap,m,target,start)
def main():
 TMP.mkdir(parents=True,exist_ok=True)
 done={"KR":5,"JP":5,"US":0}; n=1
 for src,ids in SELECT.items():
  for i,vid in enumerate(ids):
   if i>=done[src]: one(src,vid,n)
   n+=1
if __name__=="__main__": main()
