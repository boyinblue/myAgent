# Content Crawler v2.1 (콘텐츠 크롤러)

<!-- 파일 인코딩: UTF-8 -->

**다중 플랫폼 자동 콘텐츠 수집 & 아카이브 시스템**

네이버 블로그, Tistory, GitHub Pages, YouTube에서 콘텐츠를 자동으로 수집하고 Anniversary 포스트와 Random Post 3개를 텔레그램으로 알려줍니다.

## 주요 기능 ✨

- **🔄 다중 플랫폼**: 네이버, Tistory, GitHub Pages, YouTube 통합 지원
- **📊 스마트 크롤링**: RSS + 리스트 페이지 + 내부 링크 + Sitemap 활용
- **📅 자동 다이제스트**: PC 로그인 후 하루 한 번, 몇 년 전 오늘의 포스트와 Random Post 3개를 텔레그램으로 발송
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

# 기념일 다이제스트 즉시 발송
python run_anniversary_digest.py
```

## 사용 방법 📖

### 기본 명령어

```bash
# 모든 플랫폼 크롤링
python main.py

# 테스트 모드 (최대 10개)
python main.py --max-posts 10
```

### 고급 옵션

```bash
--use-sitemap           # Sitemap 활용 (Tistory)
--max-posts N           # 최대 N개까지만
--test-telegram         # 텔레그램 설정 테스트
--schedule              # 상주형 고정 시간 스케줄러 모드
```

### 예시

```bash
# 전체 크롤 + 내부 링크 수집 (처음 한 번)
python main.py --use-sitemap

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

Windows PC 로그인 시 오늘의 기념일 포스트와 Random Post 3개를 확인해 텔레그램으로 보냅니다. Random Post는 기존 `/post random`처럼 플랫폼·제목·날짜·URL을 한 메시지에 표시하며, 웹페이지 미리보기는 사용하지 않습니다. 기념일 포스트가 없으면 그 안내를 함께 보내며, 성공적으로 발송된 경우 하루 한 번만 실행됩니다. PC가 꺼져 있던 날의 다이제스트는 다음 로그인 때 현재 날짜 기준으로 발송합니다.

### 작업 스케줄러 등록

저장소 루트에서 PowerShell로 한 번 실행합니다.

```powershell
.\tools\setup_daily_digest.ps1
```

태스크는 사용자 로그인 시 실행되며, Telegram 발송에 실패하면 최대 3회 재시도합니다. 마지막 성공 날짜는 `%LOCALAPPDATA%\myAgent\daily_digest`에 저장되고 실행 로그는 `daily_digest.log`에서 확인할 수 있습니다.

```powershell
# 지금 바로 실행
Start-ScheduledTask -TaskName 'myAgent_DailyDigest'

# 태스크 제거
Unregister-ScheduledTask -TaskName 'myAgent_DailyDigest' -Confirm:$false
```

### 예시 메시지

```
📆 오늘의 Daily Digest

오늘의 기념일 포스트가 없습니다.

🎲 랜덤 포스트 추천 (3개)
1. [Tistory] 게시물 제목
   📅 2024-01-02
   🔗 https://example.com/post
...
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
