# /gdrive

[RESPONSE_MODE] python_script

## 목표
`tools/gdrive.py`를 실행해서 Google Drive 결과를 그대로 출력한다.

## 입력 규칙
- 기본: `/gdrive`
- 중복 제거: `/gdrive --dedupe`
- 특정 폴더: `/gdrive --folder-id <ID>`
- 조합: `/gdrive --dedupe --folder-id <ID>`

## 아카이브 저장 규칙
- Google Drive 내 `[아카이브]` 디렉토리를 기준으로 파일을 관리한다.
- 하위 폴더는 `YYYY/MM` 구조를 사용한다. 예: `2026/03`
- 파일 업로드/이동 전 반드시 파일명을 규칙에 맞게 rename한다.
- 제목(`제목`)에는 파일명에 사용할 수 없는 문자를 제거/치환한다.

### MD 파일명 규칙
- 형식: `YYYY-MM-DD-플랫폼-미디어ID-제목.md`

### HTML 파일명 규칙
- 형식: `YYYY-MM-DD-googlekeep-esregnet0409-제목.html`

### HTML 날짜(`YYYY-MM-DD`) 추출 규칙
- 아래 우선순위로 날짜를 결정한다.
  1. `<meta property="article:published_time">`, `<meta name="date">`, `<meta name="publish_date">` 값
  2. `<time datetime="...">` 값
  3. 본문 내 ISO 날짜 패턴: `YYYY-MM-DD` 또는 `YYYY/MM/DD`
  4. 파일 원본명에서 날짜 패턴 추출
  5. 위 값이 없으면 파일 수정일(`mtime`) 사용
- 시간/타임존이 포함된 경우 로컬 날짜로 변환한 뒤 `YYYY-MM-DD`만 사용한다.
- 어떤 단계로 날짜가 결정됐는지 로그로 출력한다. 예: `date_source=meta:article:published_time`

## 스크립트 생성 규칙
- 반드시 Python 코드만 반환한다.
- 첫 줄은 `# _slash_gdrive_runner.py` 형식의 파일명 주석으로 시작한다.
- `subprocess.run`으로 `tools/gdrive.py`를 호출한다.
- 파이썬 실행기는 `sys.executable`을 사용한다.
- 작업 디렉터리는 `Path(__file__).resolve().parent.parent`로 계산한 프로젝트 루트로 설정한다.
- 인코딩은 `utf-8`, `errors='replace'`를 사용한다.
- 기본 옵션 `--max-depth 2 --max-items 80`을 항상 포함한다.
- 사용자 입력 인자가 있으면 그대로 뒤에 추가한다.
- 실행 결과는 `stdout` 우선, 없으면 `stderr`를 출력한다.
- `subprocess.run`은 `capture_output=True`, `text=True`를 사용한다.
- `stdout`/`stderr`가 모두 비어 있으면 `[ERROR] /gdrive 실행 결과가 비어 있습니다.`를 출력한다.
- 절대 `print(None)`이 출력되지 않도록 문자열 fallback을 적용한다.
- 파일 업로드/정리 작업이 포함된 경우 위 아카이브 저장 규칙을 우선 적용한다.
- `gdrive.py` 경로는 문자열 결합이 아니라 `Path` 객체로 구성하고 `exists()`로 검증한다.
- 아래 구현은 금지한다:
  - `['python', 'tools/gdrive.py']`
  - `cwd='..'` 같은 상대 경로 상수
  - `input()` 호출(텔레그램 비대화형 실행에서 EOF 발생)
  - 사용자 입력 프롬프트 출력

## 예외 처리
- 타임아웃(90초):
  - `⏱️ /gdrive 실행 시간이 초과되었습니다.`
  - `python tools/gdrive.py --init-auth` 안내를 포함한다.
- 모듈 누락(`ModuleNotFoundError` + `google`):
  - `pip install google-api-python-client google-auth google-auth-oauthlib` 안내를 출력한다.
- 출력이 비어 있으면 `[ERROR] /gdrive 실행 결과가 비어 있습니다.`를 출력한다.
