# Content Archive (콘텐츠 아카이브)

<!-- 파일 인코딩: UTF-8 -->

수집한 블로그 콘텐츠를 체계적으로 저장하고 관리합니다.

## 📂 아카이브 구조

```
archive/
├── README.md                       # 이 파일
├── index.json                      # 전체 포스트 메타데이터 (검색/필터용)
├── 2024/                           # 연도별 디렉토리
│   ├── 01/                         # 월별 디렉토리
│   │   ├── 2024-01-15-post-title.md
│   │   ├── 2024-01-20-another-title.md
│   │   └── ...
│   ├── 02/
│   ├── 03/
│   └── ...
├── 2023/
│   ├── 01/
│   ├── 02/
│   └── ...
├── 2022/
├── 2021/
└── ... (과거 연도)
```

### 디렉토리 계층 설계 이유

- **연도/월별 분류**: 2200개의 글을 단일 폴더에 넣으면 파일시스템 성능 저하
- **월별 세분화**: 대략 월 15~20개 글 정도로 관리 가능한 수준
- **지연 로딩 가능**: 필요한 월만 로드할 수 있음

---

## 📝 마크다운 파일 포맷

### 파일명 규칙

```
YYYY-MM-DD-포스트제목.md
```

예:
- `2024-01-15-첫-블로그-글.md`
- `2024-02-20-새로운-프로젝트.md`

### 파일 내용 구조 (Frontmatter + 본문)

```markdown
---
title: "블로그 포스트 제목"
url: "https://blog.naver.com/boyinblue/123456789"
created_at: "2024-01-15T14:30:00"
event_dates:
  - "2024-01-10"
  - "2024-01-15"
category: "기술"
tags:
  - "Python"
  - "크롤링"
---

# 블로그 포스트 제목

포스트 본문 내용이 여기에 저장됩니다...

## 서브 섹션

더 자세한 내용...
```

### 메타데이터 필드 설명

| 필드 | 설명 | 예시 |
|------|------|------|
| `title` | 포스트 제목 | "파이썬으로 크롤러 만들기" |
| `url` | 원본 블로그 URL | "https://blog.naver.com/boyinblue/123456" |
| `created_at` | 포스트 작성 날짜/시간 | "2024-01-15T14:30:00" |
| `event_dates` | 글이 다루는 이벤트 날짜 (1개 이상) | ["2024-01-10", "2024-01-15"] |
| `category` | 블로그 카테고리 | "기술", "일상", "여행" |
| `tags` | 태그 목록 (검색 용이) | ["Python", "크롤링", "자동화"] |

---

## 📊 전체 목록 파일 (index.json)

archiving 후 모든 포스트의 메타데이터를 한 곳에서 검색할 수 있도록:

```json
{
  "platform": "naver_blog",
  "blog_id": "boyinblue",
  "total_posts": 2200,
  "last_updated": "2026-02-28T10:30:00Z",
  "posts": [
    {
      "id": 1,
      "title": "블로그 포스트 제목",
      "url": "https://blog.naver.com/boyinblue/123456789",
      "created_at": "2024-01-15T14:30:00Z",
      "event_dates": ["2024-01-10", "2024-01-15"],
      "category": "기술",
      "tags": ["Python", "크롤링"],
      "file_path": "archive/2024/01/2024-01-15-post-title.md",
      "word_count": 1250,
      "archived": true
    },
    {
      "id": 2,
      "title": "다른 포스트",
      "url": "https://blog.naver.com/boyinblue/987654321",
      "created_at": "2024-01-20T10:00:00Z",
      "event_dates": ["2024-01-18"],
      "category": "일상",
      "tags": ["일기"],
      "file_path": "archive/2024/01/2024-01-20-another-post.md",
      "word_count": 800,
      "archived": true
    }
  ]
}
```

### index.json의 용도

- ✅ 전체 포스트 빠른 검색
- ✅ 카테고리/태그별 필터링
- ✅ 이벤트 날짜로 시간대별 검색
- ✅ 단어 수로 포스트 길이 파악

---

## 🔍 이벤트 날짜(event_dates) 구조

같은 날짜로 작성했지만 다른 날짜의 내용을 다루는 경우가 많으므로:

```
작성 날짜: 2024-02-15 (블로그에 올린 날짜)
event_dates: ["2024-02-10", "2024-02-12", "2024-02-15"]  (글이 다루는 날짜들)
```

이를 통해:
- "2월 10일에 뭐했나?" → event_dates에 "2024-02-10" 포함된 글들 검색
- 시대별 기록 추적 가능

---

## 💡 분석/검색 활용

### 예시 쿼리

```python
# 2024년 1월의 모든 포스트 조회
import json
with open("archive/index.json", "r", encoding="utf-8") as f:
    data = json.load(f)
    
jan_2024 = [p for p in data["posts"] 
           if p["created_at"].startswith("2024-01")]

# 특정 태그 검색
python_posts = [p for p in data["posts"] 
               if "Python" in p["tags"]]

# 특정 이벤트 날짜 검색
event_date = "2024-01-15"
posts_on_date = [p for p in data["posts"] 
                if event_date in p["event_dates"]]
```

---

## 📈 성능 고려사항

| 항목 | 용도 |
|------|------|
| **마크다운 파일** | 원본 내용 보존, 버전 관리 용이 |
| **index.json** | 빠른 메타데이터 검색 (2200개도 JSON은 가벼움) |
| **월별 디렉토리** | 파일시스템 부하 감소, 병렬 처리 가능 |

---

## 🔄 자동 아카이빙 워크플로우

1. RSS 피드에서 포스트 메타데이터 수집 → `storage/naver_blog/posts.json`
2. 포스트 본문 크롤 (추후 구현) → 마크다운 파일 생성
3. `archive/{연도}/{월}/` 디렉토리에 저장
4. **`archive/index.json`** 자동 생성/업데이트

---

## 🎯 확장 가능 구조

이 구조는 다른 플랫폼(유튜브, 티스토리)으로도 쉽게 확장 가능:

```
archive/
├── naver_blog/
│   ├── index.json
│   ├── 2024/
│   └── 2023/
├── tistory/
│   ├── index.json
│   ├── 2024/
│   └── 2023/
└── youtube/
    ├── index.json
    └── 2024/
```

---

## 📋 요약

| 특징 | 설명 |
|------|------|
| **계층 구조** | 연도/월별로 분류하여 약 200-300개 파일/폴더 관리 |
| **메타데이터** | YAML Frontmatter로 마크다운 파일에 내장 |
| **전체 목록** | index.json으로 빠른 검색/필터링 |
| **이벤트 날짜** | 배열로 최대 3~5개 날짜 기록 |
| **확장성** | 새로운 플랫폼 추가 시에도 동일 구조 유지 |
