# Quick Start Guide (빠른 시작 가이드)

<!-- 파일 인코딩: UTF-8 -->

## 📋 사전 요구사항

- **Python 3.8+** 설치 필요
- **인터넷 연결** (네이버 블로그 크롤링을 위해)

## 🚀 1단계: 환경 설정

### 1.1 가상환경 생성 및 활성화

**Windows PowerShell:**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS/Linux (Bash):**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 1.2 패키지 설치

```bash
pip install -r requirements.txt
```

## 🧪 2단계: 테스트 실행

작은 규모로 동작을 확인합니다:

```bash
python test_example.py
```

예상 결과:
- `test_archive/` 디렉토리에 마크다운 파일 2개 생성
- `test_archive/index.json` 생성

## 🎯 3단계: 실제 크롤링

### 3.1 설정 확인

`config.json`에서 네이버 블로그 ID를 확인하세요:

```json
{
  "platforms": {
    "naver_blog": {
      "enabled": true,
      "blog_id": "boyinblue",    ← 여기 수정
      "request_interval_seconds": 60
    }
  }
}
```

### 3.2 메타데이터만 수집 (빠름)

RSS 피드에서 포스트 제목, 날짜, URL만 수집합니다:

```bash
python main.py
```

결과:
- `storage/naver_blog/posts.json` - 메타데이터
- `archive/` - 마크다운 파일 + index.json

### 3.3 본문도 함께 수집 (느림)

각 포스트의 본문을 다운로드합니다 (시간이 오래 걸림):

```bash
python main.py --fetch-content
```

⚠️ **주의**: 
- 약 2200개 포스트 다운로드에 약 **2~3시간** 소요
- 네이버 서버 보호를 위해 자동으로 1분 간격 대기

### 3.4 테스트 (적은 포스트만)

상위 10개 포스트만 테스트:

```bash
python main.py --max-posts 10
```

또는 본문까지:

```bash
python main.py --fetch-content --max-posts 50
```

### 3.5 아카이브 저장 건너뛰기

메타데이터만 저장하고 싶다면:

```bash
python main.py --no-archive
```

## 📊 생성된 파일 구조

```
project/
├── storage/
│   └── naver_blog/
│       └── posts.json              ← 모든 포스트 메타데이터
├── archive/
│   ├── index.json                  ← 포스트 목록 (검색용)
│   ├── 2024/
│   │   ├── 01/
│   │   │   ├── 2024-01-15-포스트제목.md
│   │   │   ├── 2024-01-20-다른제목.md
│   │   │   └── ...
│   │   ├── 02/
│   │   └── ...
│   ├── 2023/
│   ├── 2022/
│   └── ...
```

## 🔍 저장된 포스트 검색

### Python으로 검색

```python
import json

# index.json 로드
with open("archive/index.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 2024년 1월 포스트 검색
jan_2024 = [p for p in data["posts"] 
           if p["created_at"].startswith("2024-01")]
print(f"2024년 1월 포스트: {len(jan_2024)}개")

# 특정 날짜의 이벤트 검색
event_date = "2024-01-15"
posts_on_date = [p for p in data["posts"] 
                if event_date in p.get("event_dates", [])]
print(f"{event_date}의 이벤트: {len(posts_on_date)}개 포스트")

# 특정 카테고리 검색
tech_posts = [p for p in data["posts"] 
              if p.get("category") == "기술"]
print(f"기술 포스트: {len(tech_posts)}개")
```

### 마크다운 파일 직접 열기

마크다운 에디터(VS Code, Typora 등)에서 직접 열어 볼 수 있습니다:

```
archive/2024/01/2024-01-15-포스트제목.md
```

## ⚙️ 고급 옵션

모든 옵션 보기:

```bash
python main.py --help
```

## 🐛 문제 해결

### 1. "ModuleNotFoundError: No module named 'feedparser'"

→ `pip install -r requirements.txt` 다시 실행

### 2. "연결 시간 초과"

→ 인터넷 연결 확인, 또는 시간을 두고 다시 시도

### 3. "본문을 찾을 수 없음"

→ 네이버 블로그 HTML 구조가 변경되었을 수 있음 (크롤러 업데이트 필요)

## 💡 팁

- **정기 실행**: 추가된 포스트만 다시 크롤 (중복 체크 후 진행)
- **백업**: `archive/` 폴더를 git이나 클라우드에 백업하세요
- **분석**: `archive/index.json`을 이용해 다양한 분석 가능

## 📝 명령어 요약

| 명령어 | 설명 |
|--------|------|
| `python main.py` | 메타데이터 수집 + 아카이브 ⭐ |
| `python main.py --fetch-content` | 본문까지 포함 (느림) |
| `python main.py --max-posts 50` | 상위 50개만 |
| `python main.py --no-archive` | 메타데이터만 저장 |
| `python test_example.py` | 테스트 실행 |

더 자세한 정보는 [README.md](README.md)와 [ARCHIVE_STRUCTURE.md](ARCHIVE_STRUCTURE.md)를 참조하세요.
