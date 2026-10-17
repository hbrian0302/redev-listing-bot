# 재개발 매물 파이프라인 — 운영 가이드

## 개요

매일 08:30 자동 크롤 → AI 판별/추출 → 카드 생성 → 텔레그램 검수 → 스레드 발행까지 이어지는 6단계 반자동 파이프라인.

| 단계 | 스크립트 | 역할 |
|------|---------|------|
| 1. discover | `discover.py` | 제휴 블로그 크롤, 신규 매물 감지 |
| 2. classify_extract | `classify_extract.py` | 재개발 여부 AI 판별 + 구조화 데이터 추출 |
| 3. generate | `generate.py` | 카드뉴스 이미지 생성 |
| 4. review_bot | `review_bot.py` | 텔레그램 검수 봇 (승인/수정/반려) |
| 5. publish | `publish.py` | 스레드(Threads) 발행 |

- **비용 0원**: claude -p Max OAuth 사용 (API 과금 없음)
- **반자동**: 검수 봇에서 승인해야만 발행됨. 자동 폭주 없음.

---

## 1단계: 최초 1회 셋업 (사용자 액션)

아래 a → d 순서대로 진행한다.

### a. 소스 블로그 등록

`pipeline/sources.json`을 열어 `EXAMPLE_AGENT_BLOG` 항목을 실제 제휴 중개사의 네이버 blog_id로 교체하거나 추가한다.

```json
[
  { "type": "naver_blog", "id": "실제_blog_id_1", "label": "중개사 이름" },
  { "type": "naver_blog", "id": "실제_blog_id_2", "label": "중개사 이름2" }
]
```

다음 discover 실행부터 즉시 반영된다.

### b. 검수 봇 토큰 keyring 등록

@BotFather에서 새 봇을 만들고 받은 토큰을 keyring에 등록한다:

```bash
cd ~/agents/telegram-claude && uv run --with keyring python3 -c \
  "import keyring, getpass; keyring.set_password('redev_market', 'review_bot_token', getpass.getpass('봇 토큰: ').strip())"
```

chat id는 telegram-claude `.env`의 `ALLOWED_USER_ID`를 자동 재사용한다.
다른 채팅방으로 받고 싶다면 chat id도 등록:

```bash
cd ~/agents/telegram-claude && uv run --with keyring python3 -c \
  "import keyring; keyring.set_password('redev_market', 'review_chat_id', '123456789')"
```

### c. 스레드 세션 1회 로그인

Playwright 헤드풀 모드로 재개발 계정에 로그인 후 세션을 저장한다 (plan 03 Task 14 Step 1 스니펫 참고):

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.threads.net/login")
    # 브라우저에서 수동 로그인 완료 후 Enter
    input("로그인 완료 후 Enter...")
    context.storage_state(path="/Users/USER/.threads_redev_session.json")
    browser.close()
```

세션 유효 기간은 약 30일. 만료 시 재실행.

### d. 베이스라인 1회 실행 (첫 실행 폭주 방지)

기존 블로그 글을 모두 "이미 본 것"으로 처리한다. 카드는 생성하지 않는다:

```bash
cd ~/agents/telegram-claude && uv run --with jinja2 python \
  "/path/to/repo/pipeline/discover.py" --baseline
```

이 단계를 건너뛰면 첫 실행 시 수백 개 매물이 한꺼번에 쏟아진다.

---

## 2단계: launchd 등록 (사용자 액션 — 토큰 등록 후)

> ⚠️ **cron 사용 금지.** keychain/OAuth 접근이 필요한 프로세스는 반드시 launchd LaunchAgent로 등록해야 한다. cron은 keychain에 접근할 수 없다.

```bash
# plist 복사
cp "/path/to/repo/pipeline/launchd/"com.example.redev-*.plist \
  ~/Library/LaunchAgents/

# 등록 및 시작
launchctl load ~/Library/LaunchAgents/com.example.redev-discover.plist
launchctl load ~/Library/LaunchAgents/com.example.redev-review.plist

# 등록 확인
launchctl list | grep redev
```

review 봇이 정상 시작되면 텔레그램에 "🟢 재개발 매물 검수 봇 시작" 메시지가 온다.

**정지/재시작:**

```bash
launchctl unload ~/Library/LaunchAgents/com.example.redev-review.plist
launchctl load   ~/Library/LaunchAgents/com.example.redev-review.plist
```

---

## 3단계: watchdog 등록 (사용자 액션)

기존 `com.example.watchdog`(매시간, launchctl 상태만 읽는 비침습 감시)의 감시 라벨 목록에 `com.example.redev-review`를 추가한다.

추가하면 review 봇이 예기치 않게 죽었을 때 텔레그램으로 알림을 받는다.

watchdog 스크립트/설정 위치는 기존 bot-watchdog 셋업 문서 참조.

---

## 일상 운영 흐름

```
매일 08:30
  └─ discover.py 자동 실행
       └─ 신규 매물 감지 시 → 카드 생성 → 텔레그램 전송
            └─ [승인] → publish.py로 스레드 발행
            └─ [수정] → 텍스트 수정 후 재전송
            └─ [반려] → 해당 매물 건너뜀
```

discover가 실행되어도 신규 매물이 없으면 텔레그램 알림 없음.

---

## 발행 사용법 (publish.py)

**드라이런 — 작성창까지만 (스크린샷으로 확인):**

```bash
cd ~/agents/telegram-claude && uv run python \
  "/path/to/repo/pipeline/publish.py" \
  --dry-run --now
```

**실제 발행 1건:**

```bash
cd ~/agents/telegram-claude && uv run python \
  "/path/to/repo/pipeline/publish.py" \
  --count 1 --now
```

> 하루 3개 미만 권장. 스팸 감지 방지 및 계정 보호.

---

## 유지보수

| 상황 | 조치 |
|------|------|
| 스레드 세션 만료 (~30일) | `~/.threads_redev_session.json` 재생성 (셋업 c 단계 반복) |
| 블로그 추가 | `pipeline/sources.json` 편집 → 다음 discover부터 반영 |
| 봇 응답 없음 | `launchctl list \| grep redev` 상태 확인 후 reload |
| 발행 실패 | `pipeline/discover.log`, `pipeline/review_bot.log` 확인 |

**로그 파일:**

- `pipeline/discover.log` / `pipeline/discover.error.log` — 크롤 로그
- `pipeline/review_bot.log` / `pipeline/review_bot.error.log` — 검수 봇 로그

---

## 인스타그램 fast-follow (예정)

스레드 안정화 후 `publish.py`에 `insta_post()` 함수 추가 예정.

- 별도 세션: `~/.insta_redev_session.json`
- DB 플래그: `published_insta` 컬럼
- 본 단계(Phase 2 M5) 범위 밖.
