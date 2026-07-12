"""Build the Codex-reviewed 2026-07-12 XPost clips from watch assets."""
import json, re, subprocess, html, sys
from pathlib import Path
from deep_translator import GoogleTranslator
from prepare_cardnews_watch import TEXT

ROOT=Path(__file__).resolve().parents[1]; DATE='2026-07-12'; OUT=ROOT/f'영상클립_{DATE}'
RANGES={'udxYHYOSj2s':(262,55),'3AA6uDcAzq4':(293,55),'pGia4GyLt-w':(856,55),'weIvS-cLNYA':(296,55),'NETK5jl-wVA':(294,55),'AuQFFqEo5y0':(350,55),'ZcXMi--AOjk':(601,55),'Y6VWPBmr1bg':(833,55),'1cWGmoIZ8fk':(322,55)}
REGION={'udxYHYOSj2s':'KR','3AA6uDcAzq4':'KR','pGia4GyLt-w':'KR','weIvS-cLNYA':'JP','NETK5jl-wVA':'JP','AuQFFqEo5y0':'JP','ZcXMi--AOjk':'US','Y6VWPBmr1bg':'US','1cWGmoIZ8fk':'US'}
TARGETS={'KR':[('한국인타겟',None),('일본인타겟','ja')],'JP':[('일본인타겟',None)],'US':[('한국인타겟','ko'),('일본인타겟','ja')]}
TOP=json.loads((ROOT/'pipeline'/'top3_v3.json').read_text(encoding='utf-8'))
META={v['video_id']:v for items in TOP.values() for v in items}
HOOKS={'pGia4GyLt-w':'편의점 빵이 이렇게 부드럽다고? 외국인의 한마디가 반응을 터뜨렸다'}
JA_OVERRIDES={'pGia4GyLt-w':(
 'コンビニパンがこんなに柔らかい？ 外国人のひと言に反響',
 '外国人出演者が韓国のコンビニスイーツとパンを実食。想像以上の柔らかさと品質に驚くリアクションが見どころです。',
 '食文化の違いがリアクションにはっきり表れる、55秒でも見どころ十分の場面です。')}
DETAILS={'pGia4GyLt-w':{
 'body':'한국 편의점 빵을 처음 맛본 외국인 출연자는 한입 먹자마자 “왜 이렇게 부드럽지?”라며 놀랍니다. 크림이 느끼할 것이라는 예상과 달리 가볍고 촉촉하다고 평가하고, 우유와 함께 먹은 뒤에는 “완전히 다르다”는 반응까지 보입니다. 남아프리카공화국 편의점에서는 기대하기 어려운 품질이라는 비교가 이어지면서 단순한 먹방이 문화 차이 이야기로 바뀝니다.',
 'points':['“왜 이렇게 부드럽지?”라는 첫 반응에서 표정이 바로 달라집니다.','우유와 함께 먹기 전후의 평가가 어떻게 바뀌는지 볼 수 있습니다.','한국을 떠난 뒤에야 익숙한 맛의 가치를 깨닫는다는 결론이 공감을 부릅니다.'],
 'ja_body':'韓国のコンビニパンを初めて食べた外国人出演者は、一口で「どうしてこんなに柔らかいの？」と驚きます。重そうに見えたクリームも、実際には軽くてしっとり。牛乳と一緒に食べると「まったく違う」と評価がさらに変わります。南アフリカのコンビニでは想像しにくい品質だという比較から、単なる食レポが文化の違いを語る場面へと変わっていきます。',
 'ja_points':['「どうしてこんなに柔らかいの？」という第一声と表情の変化。','牛乳と合わせる前後で評価がどう変わるか。','韓国を離れて初めて身近な味の価値に気づく、共感を呼ぶ結論。']}}
def sec(t):
 p=[float(x) for x in t.split(':')]; z=0
 for x in p:z=z*60+x
 return z
def cues(text,start,dur):
 out=[]
 for line in text.splitlines():
  m=re.match(r'\[([^\]]+)\]\s*(.*)',line)
  if not m:continue
  s=sec(m.group(1));
  text=html.unescape(m.group(2)).replace('[__]','').replace('[Music]','').replace('[music]','').strip(' >')
  if start<=s<=start+dur and text:out.append((s-start,text))
 return out
def stamp(x):
 ms=int(max(0,x)*1000); h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000);return f'{h:02}:{m:02}:{s:02},{ms:03}'
def count(n): return f'{n/10000:.1f}만회' if n>=10000 else f'{n:,}회'
def count_ja(n): return f'{n/10000:.1f}万回' if n>=10000 else f'{n:,}回'
def post_text(vid,target):
 v=META[vid]; title,summary,why=TEXT[vid]
 hook=HOOKS.get(vid,title)
 detail=DETAILS.get(vid,{}); body=detail.get('body',summary)
 points=detail.get('points',[why,'영상 속 핵심 발언과 반응의 변화를 확인할 수 있습니다.'])
 ko=(f'🔥 {hook}\n\n{body}\n\n왜 봐야 할까?\n'+''.join(f'• {p}\n' for p in points)+
     f'\n55초 클립에서 실제 반응을 확인해보세요.\n\n🎬 채널: {v["channel"]}\n'
     f'👀 조회수: {count(v["views"])}\n🔗 원본 영상: {v["url"]}\n\n'
     f'#유튜브이슈 #바이럴영상 #오늘의영상')
 if target!='일본인타겟': return ko+'\n'
 if vid in JA_OVERRIDES: ja_title,ja_summary,ja_why=JA_OVERRIDES[vid]
 else:
  tr=GoogleTranslator(source='ko',target='ja')
  ja_title=tr.translate(hook); ja_summary=tr.translate(summary); ja_why=tr.translate(why)
 ja_body=detail.get('ja_body',ja_summary); ja_points=detail.get('ja_points',[ja_why])
 ja=(f'🔥 {ja_title}\n\n{ja_body}\n\n見どころ\n'+''.join(f'・{p}\n' for p in ja_points)+
     f'\n55秒のクリップで実際のリアクションをチェック。\n\n🎬 チャンネル: {v["channel"]}\n'
     f'👀 再生回数: {count_ja(v["views"])}\n🔗 元動画: {v["url"]}\n\n'
     f'#YouTube話題 #バズ動画 #今日の動画')
 return '[한국어 포스팅]\n'+ko+'\n\n---\n\n[日本語ポスト]\n'+ja+'\n'
def main():
 only=sys.argv[2] if len(sys.argv)>2 and sys.argv[1]=='--captions-only' else None
 captions_only='--captions-only' in sys.argv
 for n,(vid,(start,dur)) in enumerate(RANGES.items(),1):
  if only and vid!=only: continue
  d=json.loads((ROOT/'site'/'assets'/vid/'watch.json').read_text(encoding='utf-8')); src=Path(d['source_video'])
  reg=REGION[vid]; cs=cues(d['transcript'],start,dur)
  for target,lang in TARGETS[reg]:
   od=OUT/target;od.mkdir(parents=True,exist_ok=True); vf='scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720'
   out=od/f'{n:02}_{vid}_{reg}_{"원본자막" if not lang else lang+"자막"}_16x9.mp4'
   if captions_only:
    (od/f'캡션_{out.stem}.txt').write_text(post_text(vid,target),encoding='utf-8')
    continue
   if lang and cs:
    texts=[x[1] for x in cs]; trans=GoogleTranslator(source='auto',target=lang).translate_batch(texts)
    sp=od/f'{n:02}_{vid}_{lang}.srt'; blocks=[]
    for i,((at,_),tx) in enumerate(zip(cs,trans),1):
     end=(cs[i][0] if i<len(cs) else dur);blocks.append(f'{i}\n{stamp(at)} --> {stamp(min(end,at+5))}\n{tx}')
    sp.write_text('\n\n'.join(blocks)+'\n',encoding='utf-8'); esc=str(sp.resolve()).replace('\\','/').replace(':','\\:')
    font='Malgun Gothic' if lang=='ko' else 'Yu Gothic';vf+=f",subtitles='{esc}':force_style='FontName={font},FontSize=16,Bold=1,BorderStyle=3,Outline=2,Alignment=2,MarginV=70'"
   if out.exists() and not lang:
    continue
   subprocess.run(['ffmpeg','-y','-ss',str(start),'-i',str(src),'-t',str(dur),'-vf',vf,'-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart',str(out)],check=True)
   (od/f'캡션_{out.stem}.txt').write_text(post_text(vid,target),encoding='utf-8')
if __name__=='__main__':main()
