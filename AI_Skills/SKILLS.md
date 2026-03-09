# Autopilot Skills Specification

이 문서는 `autopilot.py`가 LLM 라우팅/응답 생성 시 참조하는 스킬 규칙만 담습니다.

## Output Contract
- 라우터 판단 결과는 JSON으로만 반환
- 스키마: `{"action":"chat|python_code|github_action|github_issue|archive_search|archive_validate|web_dashboard_launch|web_dashboard_stop","skill":"skill_name","reason":"short reason","url":"optional_target_url","keyword":"optional_search_keyword"}`

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

### 5) `github_issue_feedback`
- **action**: `github_issue`
- **when**: 챗봇 사용 중 불편사항/오류/개선요청을 GitHub 이슈로 등록 요청
- **heuristic**: ("이슈"|"issue") + ("등록"|"생성"|"작성"|"올려"|"create"|"open"|"report")
- **output**: 생성된 이슈 번호와 URL
- **실행 규칙**:
  - 사용자 요청 텍스트를 요약해 이슈 제목/본문 자동 생성
  - GitHub Issues API로 `owner/repo`에 이슈 생성
  - 기본 라벨: `chatbot`, `feedback` (설정으로 변경 가능)

### 6) `archive_search`
- **action**: `archive_search`
- **when**: 아카이브에서 키워드 검색 또는 검색 결과 확인 요청
- **heuristic**: ("검색"|"찾기"|"find") 키워드
- **output**: 최대 10건 (제목, 작성자, 플랫폼, 날짜, 요약, URL)
- **사용 예**:
  - "와인 검색해줘" → 와인 키워드로 포스트 검색
  - "아카이브에 와인 입력하면 포스트가 별로 안 나와" → 와인 검색 (검색 품질 확인)
  - "네이버 검색 결과 보여줘" → 네이버 키워드로 검색

### 7) `archive_validate`
- **action**: `archive_validate`
- **when**: 아카이브 DB의 데이터 무결성 검사 요청 (필수 필드 누락 여부 확인)
- **heuristic**: ("무결성"|"검증"|"누락"|"불완전"|"validate"|"integrity") + ("아카이브"|"archive"|"db") 키워드
- **output**: 전체 건수, 누락 필드별 통계 (제목, URL, 플랫폼 등), 샘플 레코드
- **주의**: 검색 결과 수량 문제는 `archive_search` 사용 (데이터 누락이 아닌 검색 품질 이슈)

### 8) `web_dashboard_launch`
- **action**: `web_dashboard_launch`
- **when**: 웹 대시보드 실행 요청
- **heuristic**: ("대시보드"|"웹"|"dashboard"|"web") + ("시작"|"실행"|"열기"|"launch"|"start"|"open") 키워드
- **output**: ngrok 터널 생성, 텔레그램으로 일회용 URL 전송

### 9) `web_dashboard_stop`
- **action**: `web_dashboard_stop`
- **when**: 웹 대시보드 종료 요청
- **heuristic**: ("대시보드"|"웹"|"dashboard"|"web") + ("종료"|"중지"|"닫기"|"stop"|"close"|"shutdown") 키워드
- **output**: 실행 중인 대시보드 프로세스 종료

## Examples
- "https://blog.naver.com/xxx/123 추가" → `content_crawler_dispatch` (heuristic)
- "챗봇 불편한 점 이슈 등록해줘" → `github_issue_feedback` (heuristic)
- "파이썬 검색" → `archive_search` (heuristic)
- "와인으로 검색하면 결과가 하나만 나와" → `archive_search` (LLM router)
- "아카이브에 제목 없는 항목 찾기" → `archive_validate` (LLM router)
- "아카이브 무결성 검증" → `archive_validate` (heuristic)
- "웹 대시보드 시작" → `web_dashboard_launch` (heuristic)
- "대시보드 종료" → `web_dashboard_stop` (heuristic)
- "오늘 할 일 정리" → `explain_or_chat` (LLM router)

## Config & Env
- 비보안 설정: `config.json`의 `autopilot` 섹션
- 보안 크레덴셜: 루트 `.env`
- `.env` 직접 수정 금지, `.env.example`만 업데이트


