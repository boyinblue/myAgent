# Autopilot Skills Specification

이 문서는 `autopilot.py`가 사용자 요청을 어떤 스킬로 처리할지 판단할 때 사용하는 규칙입니다.

## Output Contract
- 라우터 판단 결과는 JSON으로만 반환
- 스키마: `{"action":"chat|python_code|github_action|archive_search|archive_validate","skill":"skill_name","reason":"short reason","url":"optional_target_url","keyword":"optional_search_keyword"}`

## Performance Optimization
- **Heuristic First**: URL+아카이브, 검색, 무결성 검증 등 명확한 의도는 LLM 우회하여 즉시 실행
- **LLM Router Second**: 애매한 요청만 LLM 라우터 사용
- **Benefit**: 응답 속도 향상, 토큰 비용 절감

## Skills

### 1) `python_task_runner`
- **action**: `python_code`
- **사용 조건**:
  - 사용자가 자동화 스크립트 작성/실행을 요청
  - 파일 처리, 데이터 가공, API 호출, 배치 작업 등 코드 실행이 필요한 경우
- **실행 규칙**:
  - 결과 첫 줄은 반드시 파일명 주석: `# <name>.py`
  - 마크다운 코드펜스(```` `) 금지
  - 바로 실행 가능한 Python 코드로만 출력

### 2) `explain_or_chat`
- **action**: `chat`
- **사용 조건**:
  - 설명/요약/아이디어/가이드 요청
  - 코드 실행 없이 답변만 필요한 경우
- **실행 규칙**:
  - 짧고 명확하게 답변
  - 필요 시 단계별로 안내

### 3) `safety_fallback`
- **action**: `chat`
- **사용 조건**:
  - 요청이 애매하거나 분류 실패 시
- **실행 규칙**:
  - 안전한 일반 답변으로 처리
  - 라우터 reason에 실패 원인 짧게 표시

### 4) `content_crawler_dispatch`
- **action**: `github_action`
- **사용 조건**:
  - 사용자가 URL 아카이브를 요청
  - "URL 넣어서 content-crawler 실행" 또는 "run_crowler.yml 실행" 의도
- **Heuristic 우회 조건**:
  - 입력 텍스트에 `http://` 또는 `https://` URL 포함
  - 아래 의도 키워드 중 하나 이상 포함:
    - `아카이브`, `추가해줘`, `추가해 줘`, `저장`, `archive`, `content-crawler`, `run_crowler`
- **실행 규칙**:
  - 입력 텍스트에서 URL을 추출하거나 JSON의 `url` 필드를 사용
  - GitHub Actions `run_crowler.yml`을 `workflow_dispatch`로 호출
  - 호출 입력값: `url`
- **필수 환경변수**:
  - `GITHUB_TOKEN` (workflow dispatch 권한)
  - `GITHUB_REPO` (예: `owner/repo`)
- **선택 환경변수**:
  - `GITHUB_WORKFLOW_FILE` (기본 `run_crowler.yml`)
  - `GITHUB_REF_NAME` (기본 `main`)

### 5) `archive_search`
- **action**: `archive_search`
- **사용 조건**:
  - 사용자가 아카이브에서 콘텐츠 검색을 요청
  - "검색", "찾아줘", "찾기", "search", "find" 등의 키워드 포함
- *파이썬 검색해줘"
  - 기대 동작: `archive_search` with keyword="파이썬"
- "아카이브에서 딥러닝 찾아줘"
  - 기대 동작: `archive_search` with keyword="딥러닝"
- "*Heuristic 우회 조건**:
  - 입력 텍스트에 검색 의도 키워드 포함 시 즉시 실행
- **실행 규칙**:
  - 입력 텍스트에서 검색 키워드를 추출하거나 JSON의 `keyword` 필드를 사용
  - SQLite DB (`archive/archive_index.db`)에서 제목, 요약, 작성자 검색
  - 최대 10건 반환
  - 결과: 제목, 작성자, 플랫폼, 날짜, 요약, URL
- **예시**:
  - "파이썬 검색해줘" → `archive_search` with keyword="파이썬"
  - "아카이브에서 딥러닝 찾아줘" → `archive_search` with keyword="딥러닝"

## Prompt Examples
- "아카이브에 추가해줘 https://blog.naver.com/xxx/123"
  - 기대 동작: `content_crawler_dispatch` (Heuristic 우선)
- "이 URL을 content-crawler로 수집해줘 https://youtu.be/abc"
  - 기대 동작: `content_crawler_dispatch`
- "오늘 할 일 정리해줘"
  - 기대 동작: `explain_or_chat`

## Provider Selection
- 기본 provider: `ollama`
- 환경 변수 `AUTOPILOT_PROVIDER=gemini`이면 Gemini 사용
- Gemini 사용 시 `GOOGLE_API_KEY` 필요
- 선택 모델:
  - Ollama: `OLLAMA_MODEL` (기본 `gemma2:9b`)
  - Gemini: `GEMINI_MODEL` (기본 `gemini-1.5-flash`)

## Environment File Policy
- `.env` 파일은 자동 수정하지 않는다.
- 환경변수 변경이 필요하면 `.env.example`만 수정하고, 사용자에게 반영할 키를 안내한다.
- 신규 기능의 환경변수는 반드시 루트 `.env.example`에 먼저 문서화한다.
- `.env`에는 보안 크레덴셜(토큰/비밀번호/API 키)만 둔다.
- 비보안 실행 설정(모델명, provider, workflow 파일명, 브랜치, repo 등)은 `content-crawler/config.json`의 `autopilot` 섹션에 둔다.
