# Content Crawler (콘텐츠 크롤러)

<!-- 파일 인코딩: UTF-8 -->

다양한 플랫폼(네이버 블로그, 유튜브, 티스토리 등)에서 콘텐츠를 수집하는 종합 크롤러입니다.

## 목표

- 여러 플랫폼의 포스트/영상 메타데이터 자동 수집
- 시스템 보호를 위한 요청 속도 제한 (1분에 1회 정도)
- 수집한 데이터를 구조화된 형식으로 저장

## 지원 예정 플랫폼

| 플랫폼 | 상태 | 수집 방식 | 속도 제한 |
|--------|------|---------|---------|
| 네이버 블로그 | ✅ 개발중 | RSS | ~1분/요청 |
| 유튜브 | 📋 예정 | API/RSS | TBD |
| 티스토리 블로그 | ✅ 개발중 | RSS | ~1분/요청 |

## 프로젝트 구조

```
content-crawler/
├── README.md                  # 이 파일
├── requirements.txt           # Python 패키지 의존성
├── config.json               # 크롤러 설정 파일
├── crawlers/                 # 플랫폼별 크롤러 모듈
│   ├── __init__.py
│   ├── naver_blog.py         # 네이버 블로그 크롤러
│   ├── youtube.py            # 유튜브 크롤러
│   └── tistory_blog.py       # 티스토리 크롤러
├── storage/                  # 수집된 데이터 저장소
│   ├── naver_blog/          # 네이버 블로그 데이터
│   ├── youtube/             # 유튜브 데이터
│   └── tistory/             # 티스토리 데이터
├── main.py                   # 실행 스크립트 (Python)
├── main.ps1                  # 실행 스크립트 (PowerShell)
└── main.sh                   # 실행 스크립트 (Bash)
```

## 1단계: 네이버 블로그 RSS 수집

### 개요

네이버 블로그의 RSS 피드를 읽어 최신 포스트 정보를 수집합니다.

### 사양

- **RSS 주소**: `https://rss.blog.naver.com/{blogId}.xml` (또는 구형 `http://blog.naver.com/RSS/{blogId}`)
  *주의*: 네이버 RSS는 최대 50개 정도의 최근 글만 노출합니다.
  
  > **한계점 및 해결책**
  > 
  > 1. **리스트 페이지 한계**: 네이버 블로그는 리스트 페이지를 최대 40~50페이지(약 400~500개)까지만 제공합니다. 폐기가 매우 많다면 더 이전 글은 접근 불가능할 수 있습니다.
  > 
  > 2. **카테고리 내 링크 수집** (`--follow-internal`): 크롤된 각 포스트 본문 내에 코시는 "카테고리의 다른 글" 또는 "관련 글" 링크를 자동으로 따라가며 수집합니다. 이는:
  >    - 링크가 같은 블로그 ID를 포함한다면 포함됩니다.
  >    - 리스트 페이지의 한계를 어느 정도 우회할 수 있습니다.
  >    - 그 대신 추가 HTTP 요청이 발생하므로 속도 제한에 더 신경써야 합니다.
  > 
  > 3. **매우 오래된 글이 필요한 경우**:
  >    - 네이버에서 제공하는 블로그 데이터 다운로드 기능 사용
  >    - 수동 백업
  >    - 검색 엔진이나 웹 아카이브 활용
- **블로그ID**: `boyinblue` (설정에서 `rss_url` 직접 지정 가능)
- **예시**:
  ```json
  "naver_blog": {
    "enabled": true,
    "blog_id": "boyinblue",
    "rss_url": "https://rss.blog.naver.com/boyinblue.xml",
    "request_interval_seconds": 60
  }
  ```
- **속도 제한**: 요청 간격 최소(예: 1분)

### 수집 정보

각 포스트별로 다음 정보를 수집합니다:
- 제목 (title)
- 작성 날짜 (published)
- 포스트 URL (link)
- 요약 (summary)
- 카테고리 (category - 있을 경우)

### 저장 형식

JSON 형식으로 저장:
```json
{
  "platform": "naver_blog",
  "blog_id": "boyinblue",
  "last_updated": "2026-02-28T10:30:00Z",
  "posts": [
    {
      "title": "포스트 제목",
      "published": "2026-02-28T10:00:00Z",
      "link": "https://blog.naver.com/boyinblue/123456789",
      "summary": "포스트 요약...",
      "category": "카테고리명"
    }
  ]
}
```

## 실행 방법

### Python으로 실행

```bash
# 가상환경 활성화 (Linux/macOS)
source venv/bin/activate

# 가상환경 활성화 (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# 크롤러 실행
python main.py [옵션]
```

옵션 예:
- `--use-sitemap`: 티스토리의 `sitemap.xml`을 읽어 가능한 모든 링크 수집
- `--max-posts N`: 테스트용으로 최대 N개까지만
- `--no-archive`: 인덱스만 갱신, 아카이브 생성을 건너뜀

### PowerShell로 실행

```powershell
.\main.ps1
```

### Bash로 실행

```bash
bash main.sh
```

## 설정 파일 (config.json)

## 테스트

```bash
# 설치 후 아래 커맨드로 실행
pip install -r requirements.txt
pytest tests/
```


```json
{
  "platforms": {
    "naver_blog": {
      "enabled": true,
      "blog_id": "boyinblue",
      "request_interval_seconds": 60
    },
    "youtube": {
      "enabled": false,
      "channels": [],
      "api_key": ""
    },
    "tistory": {
      "enabled": false,
      "blog_url": ""
    }
  },
  "output_directory": "./storage",
  "log_level": "INFO"
}
```

## 패키지 의존성

- `feedparser` - RSS 피드 파싱
- `requests` - HTTP 요청
- `schedule` - 주기적 작업 스케줄링 (옵션)

## 주의사항

- **로봇 배제 표준(robots.txt) 준수**: 각 플랫폼의 robots.txt 확인
- **이용약관 준수**: 크롤링 전 이용약관 검토
- **서버 부하**: 너무 많은 요청을 동시에 보내지 말 것
- **개인정보 보호**: 수집한 데이터의 개인정보 보호 주의

## 향후 계획

1. ✅ 네이버 블로그 RSS 크롤러 구현
2. 📋 데이터 중복 제거 로직 추가
3. 📋 유튜브 API 크롤러 구현
4. 📋 티스토리 RSS 크롤러 구현
5. 📋 웹 대시보드 (수집 현황 시각화)
