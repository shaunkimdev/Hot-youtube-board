# GitHub Actions + Pages 로 매일 자동 업데이트 (Gemini API + /watch)

## 결론 먼저
- **내 컴퓨터가 꺼져 있어도 됩니다.** GitHub Actions는 GitHub의 클라우드 서버(우분투)에서 cron으로 실행됩니다. 내 PC와 무관.
- **Gemini API로 `/watch` 동작을 자동 재현합니다.** `/watch`는 원래 Claude Code의 플러그인(슬래시 명령)이지만, 무인 CI에서는 그 동작(영상 다운로드 → 프레임 추출 → 자막 → 멀티모달 요약)을 **Gemini API**(`google-genai`)로 그대로 재현합니다 → `pipeline/summarize_llm.py`. 결과 품질은 `/watch`와 사실상 동일하며, 비용은 훨씬 저렴합니다(모델: `gemini-3.1-flash-lite`).
- (참고) 진짜 `/watch` 슬래시 명령을 그대로 쓰려면 `anthropics/claude-code-base-action`으로 Claude Code를 헤드리스(`claude -p`) 실행하고 claude-video 플러그인을 설치하는 방법도 있지만, 다중 영상 루프엔 위 API 재현 방식이 더 적합합니다.

---

## 동작 구조
```
.github/workflows/daily.yml   ← 매일 KST 08:00 클라우드에서 실행
requirements.txt              ← yt-dlp, xlsxwriter, google-genai
pipeline/run_daily.py
   ├ discover2.py        트렌딩 수집 + 라이브/공식/해외/쇼츠 제외
   ├ longform_rising.py  롱폼 필터 + 구독자수 조회
   ├ rising_search.py    라이징스타 Best5
   ├ summarize_llm.py    ★Gemini API로 요약 (상위+라이징=프레임 deep, 나머지=텍스트)
   └ build_auto.py       data.json + 엑셀 + 사이트 (summaries.json 우선 사용)
site/                     ← 결과물 (GitHub Pages가 이걸 공개)
```

---

## 따라하기 (10단계)

### 1. API 키 2개 준비
- **YouTube Data API v3 키**: Google Cloud Console → API 및 서비스 → 사용 설정 "YouTube Data API v3" → 사용자 인증 정보 → API 키 생성. (이미 쓰던 `GOOGLE_API_KEY` 그대로 사용 가능)
- **Gemini API 키**: aistudio.google.com/apikey → 키 생성 (`AIza...`). 무료 발급, 결제수단 불필요.
  (주의: YouTube 키와 이름이 겹치지 않도록 시크릿 이름은 `GEMINI_API_KEY`로 별도 등록)

### 2. GitHub 저장소 만들기
- github.com → New repository → 이름 예 `youtube-issue-dashboard` → **Private 가능**(Pages는 Private도 무료 배포됨, 단 사이트 URL은 공개됨).
- 이 프로젝트 폴더(`pipeline/`, `site/`, `.github/`, `requirements.txt`)를 그대로 올립니다:
```bash
cd C:\Users\hikim\Desktop\workplace\YoutubeAnalysis
git init && git add . && git commit -m "init dashboard"
git branch -M main
git remote add origin https://github.com/<당신아이디>/youtube-issue-dashboard.git
git push -u origin main
```
> `thumbs/`, 대용량 영상 파일은 올릴 필요 없습니다. `.gitignore`에 `pipeline/thumbs/`, `pipeline/*.mp4`, `pipeline/cookies.txt` 추가 권장.

### 3. 저장소 시크릿 등록
저장소 → **Settings → Secrets and variables → Actions → New repository secret**:
- `GOOGLE_API_KEY` = (YouTube 키)
- `GEMINI_API_KEY` = (Gemini 키)
- (선택) `YT_COOKIES` = (8번 참고, YouTube 차단 회피용)

### 4. GitHub Pages 켜기
저장소 → **Settings → Pages → Build and deployment → Source = "GitHub Actions"** 선택.

### 5. 워크플로우 확인
`.github/workflows/daily.yml` 이미 포함돼 있습니다. 스케줄은 `cron: "0 23 * * *"` = **UTC 23시 = 한국 08시**. 원하는 시각으로 바꾸세요(분 시 일 월 요일, UTC 기준).

### 6. 첫 실행 (수동)
저장소 → **Actions 탭 → daily-youtube-dashboard → Run workflow** 버튼. 2~3분 후 초록 체크.

### 7. 사이트 주소 확인
Actions 로그 마지막 `deploy-pages` 단계 또는 Settings → Pages 상단에 URL 표시:
`https://<당신아이디>.github.io/youtube-issue-dashboard/`
→ 이제 **매일 자동으로 이 주소가 갱신**됩니다. (PC 꺼져 있어도)

### 8. (중요) YouTube 다운로드 차단 대비 — 쿠키
GitHub 클라우드 IP는 YouTube가 봇으로 보고 `403/429`로 막을 수 있습니다(특히 영상 다운로드). 대비책:
- 브라우저 확장 "Get cookies.txt LOCALLY"로 youtube.com 쿠키를 Netscape 형식으로 내보내기 → 그 **파일 전체 내용**을 시크릿 `YT_COOKIES`에 붙여넣기. 워크플로우가 `pipeline/cookies.txt`로 저장해 yt-dlp에 사용합니다.
- 쿠키 없이도 **자막·텍스트 요약은 대부분 동작**합니다(다운로드가 필요한 프레임 deep 분석만 영향). 막히면 `summarize_llm.py`가 자동으로 텍스트 요약으로 폴백합니다.
- 추가 안정화: `DEEP_MAX`를 5~8로 낮춰 다운로드 횟수를 줄이면 차단 확률↓.

### 9. 비용·쿼터 감 잡기
- **YouTube API**: 하루 1회 실행에 약 2,000~3,000 units 소비(무료 일 10,000 한도 내). 여유 충분.
- **Gemini API**: `summarize_llm.py`는 deep(프레임 12장+자막) 약 10~12개 + 텍스트 요약 20여 개.
  - `gemini-3.1-flash-lite` 기준 대략 **하루 $0.05 미만** 수준(Claude 대비 훨씬 저렴).
  - 워크플로우의 `GEMINI_MODEL`, `DEEP_MAX`로 조절. 텍스트 요약만(프레임 0) 쓰면 거의 무료.
- **GitHub Actions**: Public 저장소 무료 무제한. Private도 월 2,000분 무료(이 작업은 회당 2~3분이라 충분).
- **GitHub Pages**: 무료.

### 10. 스케줄 유지(주의)
GitHub는 **60일간 저장소 활동이 없으면 예약(cron) 워크플로우를 자동 비활성화**합니다. 본 워크플로우는 매일 결과를 커밋하므로 활동이 계속 생겨 **자동으로 유지**됩니다. (혹시 비활성화되면 Actions 탭에서 "Enable" 한 번 누르면 됨)

---

## 자주 묻는 점
- **PC를 꺼도 정말 되나요?** 네. 실행은 GitHub 서버에서 일어납니다. PC·인터넷 연결 모두 불필요.
- **`/watch` 플러그인을 그대로 쓰는 건가요?** 동작(프레임+자막→멀티모달 분석)을 Gemini API로 100% 재현합니다. 진짜 슬래시 명령을 고집한다면 `claude-code-base-action` + 플러그인 설치 방식으로 교체 가능(요청 시 워크플로우 제공).
- **요약 품질은?** Gemini API가 매 영상을 새로 분석하므로 사람이 쓴 것과 유사한 100자 요약이 매일 자동 생성됩니다(`분석방식`에 `/watch 심층분석(Gemini)` 또는 `메타데이터+자막(Gemini)` 표기).
- **실패하면?** Actions 탭에 빨간 표시 + 로그. `pipeline/run.log`도 남습니다. 실패 알림(Slack/메일)이 필요하면 워크플로우에 webhook 스텝 추가.

---

## 로컬에서 먼저 테스트
```bash
cd C:\Users\hikim\Desktop\workplace\YoutubeAnalysis
set GOOGLE_API_KEY=...YouTube키...
set GEMINI_API_KEY=AIza...
python pipeline\run_daily.py
```
→ `site/index.html` 갱신 확인 후 push 하면 동일하게 클라우드에서 매일 돌아갑니다.
