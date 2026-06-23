# -*- coding: utf-8 -*-
"""Generate a self-contained index.html (data inlined) for the dashboard."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = r"C:\Users\hikim\Desktop\workplace\YoutubeAnalysis"
SITE = os.path.join(PROJ, "site")
data = json.load(open(os.path.join(SITE, "data.json"), encoding="utf-8"))
DATE = data["date"]
N = len(data["rows"])
nKR = sum(1 for r in data["rows"] if r["country"] == "한국")
nJP = N - nKR
nDEEP = sum(1 for r in data["rows"] + data.get("rising", []) if "watch" in r["analysis"])

TPL = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>한·일 유튜브 이슈 트렌드 · __DATE__</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{
  --bg:#f4f5f7; --surface:#ffffff; --text:#15171a; --muted:#6b7280; --line:#e6e8eb;
  --accent:#fa5252; --accent2:#4263eb; --chip:#eef0f3; --shadow:0 1px 3px rgba(16,24,40,.06),0 8px 24px rgba(16,24,40,.05);
  --watch:#e64980;
}
html[data-theme="dark"]{
  --bg:#0e0f12; --surface:#17191d; --text:#e8eaed; --muted:#9aa0a6; --line:#262a30;
  --chip:#22262c; --shadow:0 1px 2px rgba(0,0,0,.5),0 10px 30px rgba(0,0,0,.4);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:"Pretendard","Inter",-apple-system,system-ui,"Noto Sans KR","Noto Sans JP",sans-serif;
  -webkit-font-smoothing:antialiased;letter-spacing:-.01em}
a{color:inherit;text-decoration:none}
.wrap{max-width:1280px;margin:0 auto;padding:0 20px}

header.top{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--surface) 88%,transparent);
  backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--line)}
.top .wrap{display:flex;align-items:center;justify-content:space-between;height:64px;gap:16px}
.brand{display:flex;align-items:center;gap:11px;min-width:0}
.logo{width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,var(--accent),var(--accent2));
  display:grid;place-items:center;color:#fff;font-weight:800;font-size:18px;flex:none}
.brand h1{font-size:17px;font-weight:800;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.brand .sub{font-size:12px;color:var(--muted);margin-top:1px}
.tools{display:flex;align-items:center;gap:10px}
.badge-live{font-size:11px;font-weight:700;color:var(--accent);border:1px solid color-mix(in srgb,var(--accent) 40%,transparent);
  padding:4px 9px;border-radius:999px;background:color-mix(in srgb,var(--accent) 8%,transparent);white-space:nowrap}
.icon-btn{width:38px;height:38px;border-radius:10px;border:1px solid var(--line);background:var(--surface);
  cursor:pointer;font-size:16px;display:grid;place-items:center;color:var(--text)}

.hero{padding:30px 0 6px}
.hero h2{margin:0 0 6px;font-size:26px;font-weight:800;letter-spacing:-.02em}
.hero p{margin:0;color:var(--muted);font-size:14px;line-height:1.6}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 16px;box-shadow:var(--shadow)}
.stat b{display:block;font-size:22px;font-weight:800}
.stat span{font-size:12px;color:var(--muted)}

.controls{position:sticky;top:64px;z-index:40;background:color-mix(in srgb,var(--bg) 90%,transparent);
  backdrop-filter:blur(6px);padding:16px 0 12px;margin-top:14px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.seg{display:inline-flex;background:var(--chip);border-radius:11px;padding:3px}
.seg button{border:0;background:transparent;color:var(--muted);padding:7px 14px;border-radius:9px;
  font-weight:700;font-size:13px;cursor:pointer;font-family:inherit}
.seg button.on{background:var(--surface);color:var(--text);box-shadow:0 1px 2px rgba(0,0,0,.08)}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:var(--surface);color:var(--muted);padding:7px 13px;border-radius:999px;
  font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;transition:.12s}
.chip.on{color:#fff;border-color:transparent}
.search{flex:1;min-width:180px;display:flex;align-items:center;gap:8px;background:var(--surface);
  border:1px solid var(--line);border-radius:11px;padding:0 13px}
.search input{border:0;outline:0;background:transparent;color:var(--text);font-size:14px;
  padding:11px 0;width:100%;font-family:inherit}
.select{background:var(--surface);border:1px solid var(--line);border-radius:11px;color:var(--text);
  padding:10px 12px;font-size:13px;font-weight:600;font-family:inherit;cursor:pointer}
.count{color:var(--muted);font-size:13px;font-weight:600;margin-left:auto}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px;padding:8px 0 60px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:18px;overflow:hidden;
  box-shadow:var(--shadow);display:flex;flex-direction:column;transition:transform .14s ease,box-shadow .14s ease}
.card:hover{transform:translateY(-3px);box-shadow:0 6px 16px rgba(16,24,40,.1),0 18px 48px rgba(16,24,40,.12)}
.thumb{position:relative;aspect-ratio:16/9;background:#000;overflow:hidden}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.thumb .ov{position:absolute;display:flex;gap:6px;align-items:center}
.ov.tl{top:10px;left:10px}
.ov.tr{top:10px;right:10px}
.ov.br{bottom:10px;right:10px}
.rank{background:rgba(0,0,0,.78);color:#fff;font-weight:800;font-size:12px;width:26px;height:26px;
  border-radius:8px;display:grid;place-items:center}
.rank.r1{background:linear-gradient(135deg,#ffd43b,#fab005);color:#3b2f00}
.flagchip{background:rgba(0,0,0,.7);color:#fff;font-size:12px;padding:4px 8px;border-radius:8px;font-weight:700}
.dur{background:rgba(0,0,0,.8);color:#fff;font-size:11px;padding:3px 7px;border-radius:6px;font-weight:700}
.tag{position:absolute;left:10px;bottom:10px;font-size:11px;font-weight:800;padding:4px 9px;border-radius:8px;color:#fff}

.body{padding:14px 15px 15px;display:flex;flex-direction:column;gap:9px;flex:1}
.title{font-size:15px;font-weight:700;line-height:1.4;margin:0;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:42px}
.chan{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:12.5px;font-weight:600}
.chan .av{width:18px;height:18px;border-radius:50%;background:linear-gradient(135deg,var(--accent2),var(--watch));flex:none}
.metrics{display:flex;gap:6px;flex-wrap:wrap}
.m{background:var(--chip);border-radius:8px;padding:4px 9px;font-size:11.5px;font-weight:700;color:var(--text)}
.m small{color:var(--muted);font-weight:600}
.posted{font-size:11.5px;color:var(--muted)}
.hl{background:color-mix(in srgb,var(--accent2) 7%,transparent);border-left:3px solid var(--accent2);
  border-radius:0 10px 10px 0;padding:10px 12px;font-size:13px;font-weight:600;line-height:1.6;color:var(--text)}
.tip{font-size:12.5px;color:var(--muted);line-height:1.6}
.tl{display:flex;flex-direction:column;gap:5px;background:color-mix(in srgb,var(--accent) 6%,transparent);
  border-left:3px solid var(--accent);border-radius:0 10px 10px 0;padding:9px 11px}
.tl-h{font-size:11px;font-weight:800;color:var(--accent);letter-spacing:.02em}
.tl-row{display:flex;gap:8px;font-size:12px;line-height:1.45}
.tl-t{flex:none;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums;min-width:78px}
.tl-d{color:var(--text)}
.rsum+.tl{margin-top:2px;padding:7px 9px}
.rsum+.tl .tl-t{min-width:64px;font-size:11px}
.rsum+.tl .tl-row{font-size:11px}
.tip.warn{color:#e8590c}
html[data-theme="dark"] .tip.warn{color:#ffa94d}
.foot{display:flex;align-items:center;gap:8px;margin-top:auto;padding-top:4px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;padding:8px 12px;border-radius:10px}
.btn.play{background:var(--accent);color:#fff}
.btn.art{background:var(--chip);color:var(--text)}
.aly{margin-left:auto;font-size:10.5px;font-weight:800;color:var(--muted);border:1px solid var(--line);
  padding:4px 8px;border-radius:999px}
.aly.deep{color:#fff;background:var(--watch);border-color:transparent}
footer.ft{border-top:1px solid var(--line);padding:22px 0 50px;color:var(--muted);font-size:12px;line-height:1.7}
.empty{text-align:center;color:var(--muted);padding:70px 0;font-size:15px}
/* rising star */
.rising{margin:20px 0 8px;padding:20px;border:1px solid color-mix(in srgb,#f59f00 30%,var(--line));border-radius:20px;
  background:linear-gradient(135deg,color-mix(in srgb,#fab005 11%,var(--surface)),var(--surface))}
.rising-head{display:flex;align-items:center;gap:14px;margin-bottom:16px}
.rs-badge{background:linear-gradient(135deg,#ffd43b,#f59f00);color:#3b2f00;font-weight:800;font-size:13px;padding:9px 15px;border-radius:999px;white-space:nowrap}
.rising-head h3{margin:0;font-size:18px;font-weight:800}
.rising-head p{margin:3px 0 0;color:var(--muted);font-size:12.5px}
.rising-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px}
.rcard{display:flex;gap:12px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px;box-shadow:var(--shadow);transition:transform .12s}
.rcard:hover{transform:translateY(-2px)}
.rthumb{position:relative;width:92px;height:124px;flex:none;border-radius:10px;overflow:hidden;background:#000}
.rthumb img{width:100%;height:100%;object-fit:cover}
.rrank{position:absolute;top:6px;left:6px;width:24px;height:24px;border-radius:7px;background:linear-gradient(135deg,#ffd43b,#fab005);color:#3b2f00;font-weight:800;display:grid;place-items:center;font-size:13px}
.rbody{min-width:0;display:flex;flex-direction:column;gap:6px}
.rtitle{font-size:13.5px;font-weight:700;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.rchan{font-size:12px;color:var(--muted);font-weight:600}
.rstats{display:flex;gap:5px;flex-wrap:wrap}
.rs{font-size:11px;font-weight:700;padding:3px 7px;border-radius:7px;background:var(--chip)}
.rs.mult{background:#fff3bf;color:#92400e}
html[data-theme="dark"] .rs.mult{background:#5c4813;color:#ffe08a}
.rsum{font-size:11.5px;color:var(--text);line-height:1.5;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
@media(max-width:520px){.brand .sub{display:none}.hero h2{font-size:22px}}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <div class="brand">
    <div class="logo">▶</div>
    <div><h1>한·일 유튜브 이슈 트렌드</h1><div class="sub">개인 크리에이터 채널 · 주제별 Top 3</div></div>
  </div>
  <div class="tools">
    <span class="badge-live">● __DATE__ 기준</span>
    <button class="icon-btn" id="theme" title="다크모드">🌙</button>
  </div>
</div></header>

<div class="wrap">
  <section class="hero">
    <h2>오늘 가장 이슈된 영상, 한눈에</h2>
    <p>한국·일본 유튜브 인기 피드를 9개 주제별로 모아 <b>개인 크리에이터 채널의 롱폼</b> 영상만 추렸습니다(<b>쇼츠·라이브 제외</b>). 조회수·좋아요·댓글과 최근성을 가중한 <b>이슈점수</b> 순.</p>
    <div class="stats">
      <div class="stat"><b>__N__</b><span>롱폼 영상</span></div>
      <div class="stat"><b>🇰🇷 __NKR__</b><span>한국</span></div>
      <div class="stat"><b>🇯🇵 __NJP__</b><span>일본</span></div>
      <div class="stat"><b>9</b><span>주제 카테고리</span></div>
      <div class="stat"><b>🎬 __NDEEP__</b><span>/watch 심층분석</span></div>
    </div>
  </section>

  <section class="rising">
    <div class="rising-head">
      <span class="rs-badge">⭐ RISING STAR</span>
      <div>
        <h3>구독자 1만 이하, 조회수 폭발한 <b>롱폼</b> 영상</h3>
        <p>트렌딩 밖에서 발굴 · 쇼츠 제외 · 소형 채널의 롱폼 흥행은 드물어 소수만 선정</p>
      </div>
    </div>
    <div class="rising-grid" id="rising"></div>
  </section>

  <section class="controls">
    <div class="row" style="margin-bottom:10px">
      <div class="seg" id="country">
        <button data-c="all" class="on">전체</button>
        <button data-c="한국">🇰🇷 한국</button>
        <button data-c="일본">🇯🇵 일본</button>
      </div>
      <div class="search">🔍<input id="q" placeholder="제목·채널·내용 검색"></div>
      <select class="select" id="sort">
        <option value="issue">이슈점수순</option>
        <option value="views">조회수순</option>
        <option value="recent">최신순</option>
      </select>
    </div>
    <div class="row">
      <div class="chips" id="topics"></div>
      <span class="count" id="count"></span>
    </div>
  </section>

  <section class="grid" id="grid"></section>
</div>

<footer class="ft"><div class="wrap">
  <b>방법론</b> · YouTube Data API mostPopular(KR/JP×카테고리) 수집 → 음반사·방송사·신문사·게임사·공식 아티스트 채널 제외 후 개인채널만 추출.
  이슈점수 = (조회수 + 좋아요×20 + 댓글×100) ÷ √게시경과h. ※ API상 '24시간 조회 증가량'은 직접 제공되지 않아 누적 통계 기반 근사치.
  <b>분석</b> 배지가 ‘/watch 심층’인 카드는 영상 다운로드 후 프레임+자막으로 직접 분석. ⚠️ 표시는 자극·클릭베이트 우려로 교차확인 권장.
</div></footer>

<script>
const DATA = __DATA__;
const TOPICS = ["경제","정치","연예","TV쇼","음악","게임","스포츠","IT·테크","라이프"];
const TCOLOR = {"경제":"#e8590c","정치":"#f08c00","연예":"#2f9e44","TV쇼":"#1971c2","음악":"#9c36b5","게임":"#6741d9","스포츠":"#0ca678","IT·테크":"#1098ad","라이프":"#e8418c"};
let state={country:"all",topic:"all",q:"",sort:"issue"};

const fmt=n=>n>=10000?(n/10000).toFixed(n>=100000?0:1).replace(/\.0$/,'')+"만":n.toLocaleString();
const esc=s=>(s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function tlBlock(r){
  if(!r.timeline||!r.timeline.length) return "";
  return '<div class="tl"><div class="tl-h">⏱ /watch 타임라인</div>'+
    r.timeline.map(t=>`<div class="tl-row"><span class="tl-t">${esc(t[0])}</span><span class="tl-d">${esc(t[1])}</span></div>`).join("")+'</div>';
}

function chips(){
  const el=document.getElementById("topics");
  const mk=(v,label)=>`<button class="chip ${state.topic===v?'on':''}" data-t="${v}" ${state.topic===v&&v!=='all'?`style="background:${TCOLOR[v]}"`:''}>${label}</button>`;
  el.innerHTML=mk("all","전체 주제")+TOPICS.map(t=>mk(t,t)).join("");
  el.querySelectorAll(".chip").forEach(b=>b.onclick=()=>{state.topic=b.dataset.t;chips();render();});
}

function render(){
  let rows=DATA.rows.filter(r=>
    (state.country==="all"||r.country===state.country)&&
    (state.topic==="all"||r.topic===state.topic)&&
    (state.q===""||(r.title+r.channel+r.summary+r.tip).toLowerCase().includes(state.q)));
  if(state.sort==="views")rows=[...rows].sort((a,b)=>b.views-a.views);
  else if(state.sort==="recent")rows=[...rows].sort((a,b)=>a.hours-b.hours);
  else rows=[...rows].sort((a,b)=>b.issue-a.issue);
  document.getElementById("count").textContent=`${rows.length}개 영상`;
  const g=document.getElementById("grid");
  if(!rows.length){g.innerHTML='<div class="empty">조건에 맞는 영상이 없습니다.</div>';return;}
  g.innerHTML=rows.map(r=>{
    const deep=r.analysis.includes("watch");
    const warn=r.tip.includes("⚠️");
    const art=r.article_url?`<a class="btn art" href="${r.article_url}" target="_blank">📄 관련기사</a>`:"";
    return `<article class="card">
      <div class="thumb">
        <a href="${r.url}" target="_blank"><img loading="lazy" src="${r.thumb}" alt=""></a>
        <div class="ov tl"><span class="rank ${r.rank===1?'r1':''}">${r.rank}</span><span class="flagchip">${r.flag}</span></div>
        <div class="ov br"><span class="dur">${esc(r.duration)}</span></div>
        <span class="tag" style="background:${TCOLOR[r.topic]}">${r.topic}</span>
      </div>
      <div class="body">
        <a href="${r.url}" target="_blank"><h3 class="title">${esc(r.title)}</h3></a>
        <div class="chan"><span class="av"></span>${esc(r.channel)}</div>
        <div class="metrics">
          <span class="m">👁 ${fmt(r.views)}</span>
          <span class="m">👍 ${fmt(r.likes)}</span>
          <span class="m">💬 ${fmt(r.comments)}</span>
          <span class="m">🔥 <small>이슈</small> ${fmt(r.issue)}</span>
        </div>
        <div class="posted">게시 ${r.published} · ${r.hours}시간 전</div>
        <div class="hl">${esc(r.summary)}</div>
        ${tlBlock(r)||`<div class="tip ${warn?'warn':''}">💡 ${esc(r.tip)}</div>`}
        <div class="foot">
          <a class="btn play" href="${r.url}" target="_blank">▶ 영상</a>
          ${art}
          <span class="aly ${deep?'deep':''}">${deep?'🎬 /watch 심층':'메타+자막'}</span>
        </div>
      </div>
    </article>`;}).join("");
}

document.querySelectorAll("#country button").forEach(b=>b.onclick=()=>{
  state.country=b.dataset.c;
  document.querySelectorAll("#country button").forEach(x=>x.classList.toggle("on",x===b));render();});
document.getElementById("q").oninput=e=>{state.q=e.target.value.toLowerCase().trim();render();};
document.getElementById("sort").onchange=e=>{state.sort=e.target.value;render();};
const themeBtn=document.getElementById("theme");
themeBtn.onclick=()=>{const d=document.documentElement.getAttribute("data-theme")==="dark";
  document.documentElement.setAttribute("data-theme",d?"light":"dark");themeBtn.textContent=d?"🌙":"☀️";};

function renderRising(){
  const g=document.getElementById("rising");
  g.innerHTML=(DATA.rising||[]).map(r=>`
    <a class="rcard" href="${r.url}" target="_blank">
      <div class="rthumb"><img loading="lazy" src="${r.thumb}" alt=""><span class="rrank">${r.rank}</span></div>
      <div class="rbody">
        <div class="rtitle">${esc(r.title)}</div>
        <div class="rchan">${r.flag} ${esc(r.channel)}${r.genre?' · '+esc(r.genre):''}</div>
        <div class="rstats">
          <span class="rs">👤 구독 ${fmt(r.subscribers)}</span>
          <span class="rs">👁 ${fmt(r.views)}</span>
          <span class="rs mult">🚀 구독대비 ${r.views_per_sub}배</span>
        </div>
        <div class="rsum">${esc(r.summary)}</div>
        ${tlBlock(r)}
      </div>
    </a>`).join("");
}
chips();render();renderRising();
</script>
</body>
</html>"""

html = (TPL.replace("__DATA__", json.dumps(data, ensure_ascii=False))
           .replace("__DATE__", DATE).replace("__N__", str(N))
           .replace("__NKR__", str(nKR)).replace("__NJP__", str(nJP)).replace("__NDEEP__", str(nDEEP)))
open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(html)
print("SITE:", os.path.join(SITE, "index.html"), "(", len(html), "bytes )")
