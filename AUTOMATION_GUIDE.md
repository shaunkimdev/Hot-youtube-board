# 매일 자동 업데이트 가이드

한·일 유튜브 이슈 대시보드를 **매일 자동으로 갱신**하는 방법과 장단점 정리.

---

## 0. 먼저: 무엇이 자동화되고, 무엇이 안 되는가

파이프라인은 두 부분으로 나뉩니다.

| 단계 | 자동화 | 비고 |
|---|---|---|
| ① 수집·필터·랭킹 (트렌딩, 라이브/쇼츠/공식채널 제외, 구독자 조회, 라이징스타) | ✅ 완전 자동 | YouTube Data API만 있으면 됨 |
| ② 엑셀·data.json·웹사이트 생성 | ✅ 완전 자동 | `build_auto.py` |
| ③ **영상 상세요약(100자)** | ⚠️ 부분 | 아래 참고 |

**③이 핵심 이슈입니다.** 지금까지 만든 100자 요약은 `/watch`(영상 다운로드+프레임 분석)와 **사람이 직접 작성**한 것입니다. 무인 자동 실행에서는 이게 불가능하므로 `build_auto.py`는 **영상 설명문 기반 자동요약(미검수)**으로 대체합니다(`분석방식`에 `자동` 표기).

요약 품질을 자동으로 유지하려면 ③단계에 **LLM API**를 연결해야 합니다(현재 `pipeline/summarize_llm.py`가 **Gemini API**로 구현됨):
- 각 영상의 제목+설명+자막을 Gemini API에 보내 100자 요약 생성 → 비용은 영상당 극히 저렴(텍스트만).
- `/watch` 프레임 분석까지 무인 자동화하려면 yt-dlp 다운로드 + 프레임 + 멀티모달 API 호출이 필요(영상당 비용·시간 큼) → **상위 N개만** 선별 적용(현재 `DEEP_MAX`로 조절).

> 정리: **데이터·랭킹·대시보드는 오늘 만든 `pipeline/run_daily.py`로 100% 무인 자동화 가능**. 요약 품질을 사람 손 수준으로 유지하려면 LLM API 연결(중급 난이도)을 추가.

---

## 1. 실행 파이프라인 (이미 구성됨)

`pipeline/` 폴더:
```
run_daily.py        # 오케스트레이터 (이걸 스케줄에 등록)
 ├─ discover2.py        # mostPopular 수집 + 라이브/공식/해외 제외 + 주제분류
 ├─ longform_rising.py  # 롱폼(>180초) 필터 + 채널 구독자수 조회
 ├─ rising_search.py    # 라이징스타 Best5 (검색 API)
 └─ build_auto.py       # data.json + 엑셀 + 자체완결 index.html (+ archive/ 날짜별 보관)
```
**필요한 것**: 환경변수 `GOOGLE_API_KEY` (YouTube Data API v3 활성화), Python + `yt-dlp xlsxwriter`.
**수동 테스트**: `set GOOGLE_API_KEY=... && python pipeline\run_daily.py` (검증 완료 — 약 50초 소요).

---

## 2. 자동 실행 방법별 장단점

### ① Windows 작업 스케줄러 (로컬 PC) — ⭐가장 간단
매일 정해진 시각에 `run_daily.py` 실행.
```
schtasks /create /tn "YT이슈대시보드" /tr "cmd /c cd /d C:\Users\hikim\Desktop\workplace\YoutubeAnalysis && set GOOGLE_API_KEY=YOUR_KEY && python pipeline\run_daily.py" /sc daily /st 08:00
```
- **장점**: 추가 비용 0, 설정 5분, 기존 환경 그대로 사용, 디버깅 쉬움.
- **단점**: PC가 그 시각에 켜져 있어야 함(절전/종료 시 누락), 결과물이 로컬에만 있어 외부 공유하려면 별도 호스팅 필요, API 키가 평문 명령에 노출.
- **추천 대상**: 혼자 보거나 사내 PC에서 돌릴 때.

### ② GitHub Actions (cron) + GitHub Pages — ⭐외부 공개에 최적
GitHub 저장소에 코드 푸시 → Actions가 매일 실행 → 결과를 Pages로 자동 배포.
```yaml
# .github/workflows/daily.yml
name: daily-youtube-dashboard
on:
  schedule: [{ cron: "0 23 * * *" }]   # UTC 23:00 = KST 08:00
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install yt-dlp xlsxwriter
      - run: python pipeline/run_daily.py
        env: { GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }} }
      - run: |
          git config user.name bot && git config user.email bot@users.noreply.github.com
          git add -A && git commit -m "daily update $(date +%F)" || true
          git push
      - uses: actions/deploy-pages@v4   # site/ 를 Pages로 배포
```
- **장점**: 완전 무료(공개 저장소), PC 불필요(클라우드 실행), **자동으로 웹 URL 공개**(누구나 접속), 키는 Secrets로 안전 보관, 실행 이력·로그 자동 보존.
- **단점**: GitHub 사용법·git 푸시 필요, 무료 러너 월 사용시간 제한(이 작업은 1분 내외라 사실상 무한), `/watch` 영상 다운로드를 actions에서 하면 IP 차단·속도 이슈 가능(요약은 API 권장).
- **추천 대상**: 외부에 매일 공개하고 싶을 때(가장 권장).

### ③ 클라우드 서버리스 (AWS Lambda+EventBridge / GCP Cloud Run Jobs+Scheduler)
컨테이너/함수로 패키징 후 스케줄러가 트리거, 결과를 S3/Cloud Storage + CDN으로 서빙.
- **장점**: 매우 안정적, 확장성 좋음, 사내 인프라와 통합 용이, 실행시간 제한 넉넉(Cloud Run Jobs).
- **단점**: 초기 설정 복잡(IAM·컨테이너·배포), 소액이지만 비용 발생, ffmpeg/yt-dlp 포함 이미지 빌드 필요(`/watch`까지 할 경우).
- **추천 대상**: 팀·서비스 단위로 운영하거나 트래픽이 많을 때.

### ④ 상시 서버 / VPS + cron (Linux)
저렴한 VPS에 코드 두고 crontab 등록 + nginx로 `site/` 서빙.
```
0 23 * * *  cd /srv/yt && GOOGLE_API_KEY=... /usr/bin/python3 pipeline/run_daily.py >> run.log 2>&1
```
- **장점**: 완전한 제어, 항상 켜져 있음, `/watch`·DB·이메일 발송 등 무엇이든 자유롭게 확장.
- **단점**: 월 서버비(수천 원~), 서버 보안·유지보수 직접 책임, 설정 난이도 중간.
- **추천 대상**: 이미 VPS가 있거나 기능 확장 계획이 클 때.

### ⑤ 노코드 (n8n / Make / Zapier)
HTTP 노드로 YouTube API 호출 → 스프레드시트/노션에 적재.
- **장점**: 코딩 최소, GUI로 스케줄·알림(Slack·메일) 쉽게 연결, 비개발자 친화.
- **단점**: 복잡한 가공(주제분류·랭킹·`/watch`·엑셀 서식·웹빌드)은 한계 → 본 파이프라인을 그대로 옮기기 어려움, 유료 플랜 제한, 벤더 종속.
- **추천 대상**: "매일 표 한 장 + 슬랙 알림" 정도의 가벼운 버전.

---

## 3. 방법 비교 요약

| 방법 | 비용 | 난이도 | PC 꺼져도 OK | 웹 자동공개 | `/watch`·LLM 확장 |
|---|---|---|---|---|---|
| ① 작업 스케줄러 | 무료 | ★☆☆ | ✕ | ✕(별도) | △ |
| ② GitHub Actions+Pages | 무료 | ★★☆ | ✓ | ✓ | △(API 권장) |
| ③ 서버리스 | 소액 | ★★★ | ✓ | ✓ | ✓ |
| ④ VPS+cron | 소액 | ★★☆ | ✓ | ✓ | ✓ |
| ⑤ 노코드 | 무료~유료 | ★☆☆ | ✓ | △ | ✕ |

**추천**: 개인용·테스트 → **①**, 매일 공개 대시보드 → **②**, 본격 서비스 → **③/④**.

---

## 4. 운영 팁 / 주의

- **YouTube API 쿼터**: 기본 일 10,000 units. `mostPopular`(videos.list)=1 unit/호출, `channels.list`=1, **`search.list`=100 units**/호출. 현재 라이징스타 검색이 약 20회(=2,000 units)로 가장 큰 소비처 → 하루 1회 실행이면 충분히 여유. 검색 시드 수를 줄이면 절약.
- **날짜 누적**: `build_auto.py`가 `site/archive/data_YYYY-MM-DD.json`과 날짜별 엑셀을 남깁니다. 추세 비교·백필에 활용.
- **요약 품질**: `pipeline/summarize_llm.py`가 Gemini API 호출로 이미 이 역할을 하고 있어(제목+설명+자막 → 요약 프롬프트), 무인 상태에서도 100자 요약 품질이 유지됩니다.
- **`/watch` 무인 적용 시**: GitHub Actions/클라우드에서 대량 다운로드는 차단·rate-limit 위험. 상위 5~10개만, 쿠키/프록시 설정 후 적용 권장. 오늘 한 것처럼 "상위 일부만 심층, 나머지는 자막+메타"가 비용 대비 합리적.
- **실패 알림**: `run_daily.py`가 `run.log`를 남깁니다. ②/④에서는 실패 시 Slack/메일 웹훅을 추가하면 좋습니다.
- **키 보안**: 환경변수/Secrets로만 관리. 코드·명령 평문에 넣지 말 것(①의 단점).
