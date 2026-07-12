"""Prepare today's card-news info blocks from Codex-reviewed watch assets."""
import json, os
from pathlib import Path

HERE=Path(__file__).resolve().parent
TOP=json.loads((HERE/'top3_v3.json').read_text(encoding='utf-8'))
TEXT={
'udxYHYOSj2s':('외국인 부부가 경주에서 발견한 뜻밖의 배려','영국인 부부가 서울역부터 경주 한옥까지 이동하며 영어 표지판과 깨끗한 역사, 전통 풍경에 감탄합니다.','관광객의 실제 동선을 통해 한국 교통과 전통 공간이 어떻게 보이는지 확인할 수 있습니다.'),
'3AA6uDcAzq4':('BTS 공연 취소에 칠레 팬들이 거리로 나왔다','칠레 BTS 공연 취소 이후 여러 도시에서 팬들의 항의와 현지 언론 보도가 이어진 과정을 정리합니다.','현지 영상과 인터뷰가 포함됐지만 인원 규모와 원인은 원출처를 교차 확인할 필요가 있습니다.'),
'pGia4GyLt-w':('한국을 떠나면 생각나는 편의점 빵의 맛','외국인 출연자들이 한국 편의점 디저트와 빵을 맛보며 부드러운 식감과 품질을 평가합니다.','문화 차이를 음식 반응으로 자연스럽게 보여주는 장면이 명확해 짧게 보기 좋습니다.'),
'weIvS-cLNYA':('아기와 도쿄를 여행한 가족이 놀란 일상','외국인 가족이 지하철과 시부야, 테마파크를 여행하며 질서와 청결, 주변의 배려를 경험합니다.','도쿄의 일상을 외국인 시선으로 보여주지만 긍정적인 장면만 선별됐다는 점은 감안해야 합니다.'),
'NETK5jl-wVA':('외국인 여행자가 발견한 일본의 평범한 편리함','ATM과 자판기, 편의점, 공원 등 일본의 일상적인 시설을 여행자의 반응과 함께 소개합니다.','도시 인프라와 공공질서를 장면별로 비교해 볼 수 있는 영상입니다.'),
'AuQFFqEo5y0':('중국 야간열차에서 마주한 불편한 현실','외국인 여행자가 중국 열차의 입석과 장시간 이동 환경을 직접 촬영하며 여행 경험을 전합니다.','개인의 경험을 국가 전체로 일반화하지 말고 실제 촬영 장면 중심으로 보는 것이 좋습니다.'),
'ZcXMi--AOjk':('잉글랜드전 탈락 뒤 멕시코 방송이 쏟아낸 평가','멕시코 축구 패널들이 잉글랜드전 패배 원인과 선수 기용, 수비 실수를 두고 격론을 벌입니다.','감정적인 패널 발언과 경기 분석이 섞여 있어 사실과 의견을 구분해 볼 필요가 있습니다.'),
'Y6VWPBmr1bg':('유럽인이 미국에서 빠져드는 거대한 스케일','월드컵 여행을 소재로 미국의 경기장과 도로, 음식, 이동 문화를 유럽 도시와 비교합니다.','실제 사례보다 내레이션 중심의 미국 찬양형 콘텐츠라는 점을 감안해 소비해야 합니다.'),
'1cWGmoIZ8fk':('아르헨티나의 3대2 역전극에 반응이 폭발했다','아르헨티나와 이집트 경기의 득점 흐름과 여러 스트리머의 실시간 반응을 빠르게 엮었습니다.','경기 장면과 감정 변화가 선명해 하이라이트 클립으로 보기 좋습니다.'),
}

def fmt(n): return f'{n/10000:.1f}만' if n>=10000 else f'{n:,}회'
def main():
 by={r:[] for r in ('KR','JP','US')}
 for k,items in TOP.items():
  r=k.split('|')[0]
  if r in by: by[r]+=items
 names={'KR':'한국','JP':'일본','US':'미국'}; flags={'KR':'🇰🇷','JP':'🇯🇵','US':'🇺🇸'}
 out=HERE/'scratch'; out.mkdir(exist_ok=True)
 for r,items in by.items():
  unique={x['video_id']:x for x in items}
  picks=sorted(unique.values(),key=lambda x:x.get('views_per_sub') or 0,reverse=True)[:3]
  rows=[]
  for rank,v in enumerate(picks,1):
   title,desc,why=TEXT[v['video_id']]
   rows.append({'rank':rank,'flag':flags[r],'type':'top3','제목_한글':title,'제목_카드축약':title,
    '채널':v['channel'],'조회수_만':fmt(v['views']),'구독자_만':fmt(v.get('subscribers') or 0),
    '구독자대비조회수':f"{v.get('views_per_sub') or 0:.1f}배",'소개':desc,'봐야하는이유':why,'링크':v['url']})
  (out/f"info_{names[r]}.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__': main()
