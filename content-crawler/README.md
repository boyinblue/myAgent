# Content Crawler v2.1 (콘텐츠 크롤러)

<!-- 파일 인코딩: UTF-8 -->

**다중 플랫폼 자동 콘텐츠 수집 & 아카이브 시스템**

네이버 블로그, Tistory, GitHub Pages, YouTube에서 콘텐츠를 자동으로 수집하고 매일 아침 Anniversary 포스트를 텔레그램으로 알려줍니다.

## 주요 기능 ✨

- **🔄 다중 플랫폼**: 네이버, Tistory, GitHub Pages, YouTube 통합 지원
- **📊 스마트 크롤링**: RSS + 리스트 페이지 + 내부 링크 + Sitemap 활용
- **📅 자동 다이제스트**: 일일 정해진 시간에 몇 년 전 오늘의 포스트 텔레그램 발송
- **🔐 보안**: 민감한 정보(.env)를 git에서 제외하고 안전하게 관리
- **📦 스마트 아카이브**: 자동 폴더링(년/월), 중복 제거, 메타데이터 인덱싱

## 빠른 시작 🚀

### 1단계: 설치

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일 편집: TELEGRAM_BOT_TOKEN 등 입력
```

### 2단계: 설정

`config.json`에서 블로그 정보 설정:

```json
{
  "platforms": {
    "naver_blog": {
      "enabled": true,
      "blog_id": "boyinblue"
    },
    "tistory": {
      "enabled": true,
      "blogs": [
        {"name": "blog1", "blog_url": "https://blog1.tistory.com"},
        {"name": "blog2", "blog_url": "https://blog2.tistory.com"}
      ]
    },
    "github_pages": {
      "enabled": true,
      "blogs": [
        {"name": "site1", "blog_url": "https://username.github.io"}
      ]
    },
    "youtube": {
      "enabled": true,
      "channels": [
        {"name": "channel", "channel_url": "https://www.youtube.com/@username"}
      ]
    }
  }
}
```

### 3단계: 실행

```bash
# 기본 크롤링
python main.py

# 텔레그램 테스트
python main.py --test-telegram

# 일일 다이제스트 실행 (스케줄러)
python main.py --schedule
```

## 사용 방법 📖

### 기본 명령어

```bash
# 모든 플랫폼 크롤링
python main.py

# RSS의 한계를 넘어 이전 글까지 (네이버만)
python main.py --full

# 포스트 본문도 저장
python main.py --fetch-content

# 테스트 모드 (최대 10개)
python main.py --max-posts 10
```

### 고급 옵션

```bash
--full                  # 리스트 페이지까지 크롤링
--follow-internal       # 포스트 내 링크도 추가 (네이버)
--use-sitemap           # Sitemap 활용 (Tistory)
--fetch-content         # 본문도 함께 저장
--summarize             # Ollama로 요약
--max-posts N           # 최대 N개까지만
--test-telegram         # 텔레그램 설정 테스트
--schedule              # 스케줄러 모드 (일일 다이제스트)
```

### 예시

```bash
# 전체 크롤 + 내부 링크 수집 (처음 한 번)
python main.py --full --follow-internal --use-sitemap

# 빠른 일일 업데이트
python main.py

# 자동화된 일일 다이제스트
python main.py --schedule
```

## 구조 📁

```
content-crawler/
├── main.py                      # 메인 실행 스크립트
├── scheduler.py                 # Anniversary 스케줄러
├── config.json                  # 플랫폼 설정
├── .env                         # 민감 정보 (gitignore 됨)
├── crawlers/                    # 플랫폼별 크롤러
│   ├── naver_blog.py
│   ├── tistory_blog.py
│   ├── github_pages.py
│   └── youtube.py
├── utils/
│   ├── secrets.py               # 환경 변수 관리
│   └── telegram_notifier.py     # 텔레그램 알림
├── archive_manager.py           # 아카이브 저장
├── event_date_extractor.py      # 이벤트 날짜 추출
└── archive/                     # 저장된 주소
    ├── 2023/05/2023-05-03-*.md
    ├── index.json
    └── ...
```

## 플랫폼 지원 상황 📊

| 플랫폼 | RSS | 리스트 | 내부링크 | Sitemap | 상태 |
|--------|-----|--------|---------|---------|------|
| 네이버 블로그 | ✅ | ✅ | ✅ | ❌ | ✅ 완료 |
| Tistory | ✅ | ❌ | ❌ | ✅ | ✅ 완료 |
| GitHub Pages | ❌ | ✅ | ✅ | ❌ | ✅ 완료 |
| YouTube | ✅ | ❌ | ❌ | ❌ | ✅ 완료 |

## Anniversary 기능 🎂

일일 정해진 시간에 몇 년 전 오늘 작성된 포스트를 텔레그램으로 발송합니다.

### 설정

```json
"scheduler": {
  "enabled": true,
  "daily_digest_time": "08:00",
  "anniversary_days": [1, 7, 30, 365],
  "send_via_telegram": true
}
```

### 실행

```bash
# 스케줄러 시작
python main.py --schedule

# 또는 시스템 스케줄러에 추가:
# Linux crontab: 0 8 * * * cd /path && python main.py --schedule
# Windows Task Scheduler: 매일 08:00에 python main.py --schedule
```

### 예시 메시지

```
📆 오늘의 Anniversary Posts (3개)

1년 전 오늘 (2025-03-01)
제목: 어떤 포스트 제목
🔗 보기

365년 전 오늘 (1661-03-01)  
제목: 오래된 포스트
🔗 보기
```

## 설정 가이드 📝

자세한 설정 방법은 [SETUP.md](./SETUP.md)를 참고하세요.

## 고급 기법 🎯

고급 크롤링 기법은 [ADVANCED_FEATURES.md](./ADVANCED_FEATURES.md)를 참고하세요.

## 구현 상세 📚

전체 기능 설명: [IMPLEMENTATION.md](./IMPLEMENTATION.md)

## 주의사항 ⚠️

1. **네이버 블로그**: RSS는 최대 50개, 리스트는 최대 ~500개까지만 제공
2. **요청 속도**: `config.json`의 `request_interval_seconds` 조절로 조정
3. **민감 정보**: `.env` 파일은 절대 git에 커밋하지 마세요
4. **저작권**: 개인 아카이빙 목적으로만 사용하세요

## 문제 해결 🔧

### 텔레그램 메시지가 안 옵니다

```bash
# 설정 테스트
python main.py --test-telegram

# .env 파일 확인
cat .env
```

### 크롤링이 느립니다

```bash
# 테스트 모드로 확인
python main.py --max-posts 5

# 요청 간격 줄이기 (config.json)
"request_interval_seconds": 0.3
```

### 아래는 알려진 한계

- 네이버: 리스트 페이지 ~40-50페이지만 제공 (약 400-500개)
- Tistory: Sitemap이 없으면 RSS만 사용 가능
- GitHub Pages: URL 패턴에 따라 링크 감지 실패 가능

## 향후 계획 🗓️

- [ ] 수정된 콘텐츠 감지 (`--force` 옵션)
- [ ] 더 깊은 크롤링 (검색 엔진 활용)
- [ ] Discord, Slack 알림 지원
- [ ] 웹 UI 대시보드
- [ ] LLM 기반 자동 요약

## 저작권 📜

개인용 콘텐츠 아카이빙 목적. 각 플랫폼의 이용약관 준수.

---

**마지막 업데이트**: 2026-03-01 | **버전**: v2.1
