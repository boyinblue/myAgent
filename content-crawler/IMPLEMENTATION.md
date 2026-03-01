# 콘텐츠 크롤러 v2.1 - 최종 구현 설명

## 🎯 완성된 기능

### 1. 다중 플랫폼 지원 ✅

| 플랫폼 | 상태 | 특징 |
|--------|------|------|
| **네이버 블로그** | ✅ | RSS + 리스트 페이지 + 내부 링크 |
| **Tistory** | ✅ | 다중 블로그 + Sitemap 지원 |
| **GitHub Pages** | ✅ | 정적 사이트 링크 추출 |
| **YouTube** | ✅ | 채널 RSS 피드 |

### 2. 고급 크롤링 옵션 ✅

```bash
--full              # RSS의 한계를 넘어 리스트 페이지까지 크롤
--follow-internal   # 본문 내 같은 블로그 링크 자동 수집
--use-sitemap       # Tistory sitemap.xml 활용
--fetch-content     # 포스트 본문도 함께 저장
```

### 3. 민감한 정보 관리 ✅

- **`.env` 파일**: 텔레그램 토큰, API 키 등 안전하게 보관
- **`.gitignore`**: 민감 파일 git 제외
- **`secrets.py`**: 환경 변수 래퍼 모듈

### 4. 텔레그램 알림 ✅

```bash
# 테스트
python main.py --test-telegram

# 일일 다이제스트 (Anniversary posts)
python main.py --schedule
```

**기능:**
- 수년 전 오늘 작성된 포스트 자동 감지
- 설정 가능한 anniversary 기간 (1일, 7일, 30일, 365일 등)
- 매일 지정 시간에 텔레그램으로 발송

### 5. 아카이브 및 인덱싱 ✅

```
archive/
├── 2023/
│   ├── 05/
│   │   ├── 2023-05-03-포스트-제목.md
│   │   └── ...
│   └── ...
├── index.json          # 전체 포스트 메타데이터
└── ...
```

**특징:**
- 자동 폴더 구분 (년/월)
- 중복 체크로 재크롤링 방지
- 메타데이터 인덱스 유지

---

## 📋 통합된 구조

### 크롤러 모듈

```
crawlers/
├── naver_blog.py        # 네이버 RSS + 리스트 페이지
├── tistory_blog.py      # Tistory RSS + Sitemap
├── github_pages.py      # GitHub Pages 정적 사이트
└── youtube.py           # YouTube 채널 RSS
```

### 유틸리티 모듈

```
utils/
├── secrets.py           # 환경 변수 관리
└── telegram_notifier.py # 텔레그램 발송
```

### 메인 스크립트

```
main.py                 # 통합 실행 (모든 플랫폼)
scheduler.py            # 일일 다이제스트 & Anniversary 로직
archive_manager.py      # 아카이브 저장 로직
event_date_extractor.py # 포스트 내 이벤트 날짜 추출
```

---

## 🚀 사용 시나리오

### 시나리오 1: 전체 크롤링 (처음 설정)

```bash
python main.py --full --follow-internal --use-sitemap --fetch-content
```

결과:
- 네이버: RSS + 리스트 + 내부 링크 수집
- Tistory: Sitemap의 모든 포스트
- GitHub Pages: 모든 블로그 링크
- YouTube: 최신 영상

### 시나리오 2: 일일 업데이트

```bash
python main.py
```

결과:
- RSS 피드만 크롤링 (빠름)
- 새로운 포스트만 저장

### 시나리오 3: 매일 아침 다이제스트 (자동화)

**`.env` 설정:**
```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=82109175-8526
```

**`config.json` 설정:**
```json
"scheduler": {
  "enabled": true,
  "daily_digest_time": "08:00",
  "anniversary_days": [1, 7, 30, 365]
}
```

**실행:**
```bash
python main.py --schedule
```

또는 cron/스케줄러에 추가:
```bash
# Linux crontab
0 8 * * * cd /path/to/crawler && python main.py --schedule
```

---

## 🔧 설정 구조 (config.json)

```json
{
  "platforms": {
    "naver_blog": {
      "enabled": true,
      "blog_id": "boyinblue",
      "rss_url": "https://rss.blog.naver.com/boyinblue.xml",
      "request_interval_seconds": 0.5
    },
    "tistory": {
      "enabled": true,
      "blogs": [
        {"name": "frankler", "blog_url": "...", "request_interval_seconds": 0.5},
        {"name": "worldclassproduct", "blog_url": "...", "request_interval_seconds": 0.5}
      ]
    },
    "github_pages": {
      "enabled": true,
      "blogs": [
        {"name": "boyinblue", "blog_url": "https://boyinblue.github.io", ...},
        {"name": "esregnet0409", "blog_url": "https://esregnet0409.github.io", ...}
      ]
    },
    "youtube": {
      "enabled": true,
      "channels": [
        {"name": "saejinpark", "channel_url": "https://www.youtube.com/@saejinpark4614", ...}
      ]
    }
  },
  "scheduler": {
    "enabled": true,
    "daily_digest_time": "08:00",
    "anniversary_days": [1, 7, 30, 365],
    "send_via_telegram": true
  },
  "archive_root": "../archive"
}
```

---

## 📚 추가 문서

- [SETUP.md](./SETUP.md) - 상세 설정 가이드
- [ADVANCED_FEATURES.md](./ADVANCED_FEATURES.md) - 고급 크롤링 기법
- [README.md](./README.md) - 기본 사용법

---

## ⚠️ 알려진 한계

1. **네이버 블로그**: 리스트 페이지가 ~40-50페이지만 제공 (약 400-500개 한정)
2. **Tistory**: Sitemap이 없는 블로그는 RSS만 사용 가능
3. **GitHub Pages**: URL 패턴에 따라 감지 실패 가능
4. **YouTube**: API 없이 RSS만 사용 (최신 영상부터)

---

## 🛠️ 향후 개선 아이디어

- [ ] Modified content detection (`--force` 옵션)
- [ ] 검색 엔진 활용한 deeper 크롤링
- [ ] 다중 텔레그램 채널/사용자 지원
- [ ] 웹 UI 대시보드
- [ ] Discord, Slack 알림 지원
- [ ] 콘텐츠 요약 (LLM 활용)

---

## 📝 라이선스 & 저작권

개인용 아카이브 목적으로 개발되었습니다. 각 플랫폼의 이용약관을 준수하세요.

---

**마지막 업데이트**: 2026-03-01
