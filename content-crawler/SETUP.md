# 설정 가이드

다중 플랫폼 크롤러를 사용하기 위한 단계별 설정입니다.

## 1. 환경 변수 설정 (.env)

`.env` 파일을 생성하고 민감한 정보를 저장하세요:

```env
# 텔레그램 봇 토큰 (필수)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# 텔레그램 채팅 ID (수신자 전화번호 또는 채팅 ID)
TELEGRAM_CHAT_ID=82109175-8526

# YouTube API (선택)
YOUTUBE_API_KEY=your_api_key_here
```

**텔레그램 설정하기:**
1. Telegram에서 `@BotFather`와 대화
2. `/newbot` 명령어로 새 봇 생성
3. 얻은 토큰을 `TELEGRAM_BOT_TOKEN`에 입력
4. 봇과 개인 채팅 후, 봇이 보낸 메시지의 `chat_id` 확인

## 2. 플랫폼 설정 (config.json)

### 네이버 블로그

```json
"naver_blog": {
  "enabled": true,
  "blog_id": "boyinblue",
  "rss_url": "https://rss.blog.naver.com/boyinblue.xml",
  "request_interval_seconds": 0.5
}
```

### Tistory (다중 블로그)

```json
"tistory": {
  "enabled": true,
  "blogs": [
    {
      "name": "frankler",
      "blog_url": "https://frankler.tistory.com",
      "request_interval_seconds": 0.5
    },
    {
      "name": "worldclassproduct",
      "blog_url": "https://worldclassproduct.tistory.com",
      "request_interval_seconds": 0.5
    }
  ]
}
```

### GitHub Pages

```json
"github_pages": {
  "enabled": true,
  "blogs": [
    {
      "name": "boyinblue",
      "blog_url": "https://boyinblue.github.io",
      "request_interval_seconds": 1.0
    },
    {
      "name": "esregnet0409",
      "blog_url": "https://esregnet0409.github.io",
      "request_interval_seconds": 1.0
    }
  ]
}
```

### YouTube

```json
"youtube": {
  "enabled": true,
  "channels": [
    {
      "name": "saejinpark",
      "channel_url": "https://www.youtube.com/@saejinpark4614",
      "request_interval_seconds": 1.0
    }
  ]
}
```

### 스케줄러 (일일 다이제스트)

```json
"scheduler": {
  "enabled": true,
  "daily_digest_time": "08:00",
  "anniversary_days": [1, 7, 30, 365],
  "send_via_telegram": true
}
```

## 3. 사용 방법

### 모든 플랫폼 크롤링

```bash
python main.py
```

### 특정 옵션과 함께

```bash
# 이전 글도 포함 + 내부 링크 추가
python main.py --full --follow-internal --use-sitemap

# 텔레그램으로 본문 포함해서 발송
python main.py --fetch-content

# 에러 보고를 비활성화
python main.py --no-error-report
```

**아카이브 확장**
- 크롤러가 업데이트되면 기존 파일도 재작성됩니다 (`crawler_version` 저장).
- 게시물 정보에 태그, 요약(코멘트), 주요 키워드가 자동으로 추가됩니다.
- 수집된 메타데이터는 Frontmatter에 보존되며 중복 없이 병합됩니다.

# 최대 50개까지만 (테스트)
python main.py --max-posts 50
```

### 텔레그램 테스트

```bash
python main.py --test-telegram
```

### 스케줄러 실행 (일일 다이제스트)

```bash
python main.py --schedule
```
위 명령어를 `cron` (Linux/Mac) 또는 작업 스케줄러 (Windows)에 추가하면 자동으로 실행됩니다.

## 4. 일일 Anniversary 다이제스트

스케줄러를 활성화하면 매일 설정된 시간(예: 08:00)에 다음을 수행합니다:

1. 몇 년 전 오늘 작성된 포스트 찾기
2. 설정된 anniversary 기간 확인 (1일, 7일, 30일, 365일 전 등)
3. 텔레그램으로 목록 전달

**예시 메시지:**
```
📆 오늘의 Anniversary Posts (3개)

🔔 1년 전 오늘 (2025-03-01)
제목: 어떤 포스트 제목
🔗 보기

🔔 7년 전 오늘 (2019-03-01)
제목: 오래된 포스트
🔗 보기
```

## 5. 보안 주의 사항

- `.env` 파일은 절대 git에 커밋하지 마세요 (.gitignore에 포함됨)
- 텔레그램 토큰과 채팅 ID는 숨겨두세요
- 로컬 설정 파일은 접근 권한을 제한하세요

## 6. 문제 해결

**Q: 텔레그램 메시지가 안 옵니다**
- `python main.py --test-telegram`으로 설정 테스트
- `.env` 파일의 토큰과 채팅 ID 확인
- 봇이 차단되지 않았는지 확인

**Q: 크롤링이 느립니다**
- `request_interval_seconds`를 줄이거나 `--max-posts`로 테스트
- `--fetch-content` 옵션은 시간이 오래 걸리므로 필요할 때만 사용

**Q: 오래된 글이 많지 않습니다**
- [Advanced Features](./ADVANCED_FEATURES.md) 문서 참조
- 플랫폼 자체 한계가 있음을 이해하세요
