# /calc

[RESPONSE_MODE] python_script

## 목표
`tools/calc.py`를 실행해서 계산 결과를 출력한다.

## 입력 규칙
- 기본: `/calc <수식>`
- 예시:
  - `/calc 1+2*3`
  - `/calc (10-3)/7`
  - `/calc sqrt(16)+pi`

## 스크립트 생성 규칙
- 반드시 Python 코드만 반환한다.
- 첫 줄은 `# _slash_calc_runner.py` 형식의 파일명 주석으로 시작한다.
- `subprocess.run`으로 `tools/calc.py`를 호출한다.
- 파이썬 실행기는 `sys.executable`을 사용한다.
- 작업 디렉터리는 `Path(__file__).resolve().parent.parent`로 계산한 프로젝트 루트로 설정한다.
- 인코딩은 `utf-8`, `errors='replace'`를 사용한다.
- 인자는 `/calc` 이후 텍스트를 그대로 전달한다.
- 실행 결과는 `stdout` 우선, 없으면 `stderr`를 출력한다.
- `subprocess.run`은 `capture_output=True`, `text=True`를 사용한다.
- `input()` 호출 및 사용자 입력 프롬프트 출력은 금지한다.

## 예외 처리
- 인자가 없으면 `❌ 사용법: /calc <수식>`을 출력한다.
- 타임아웃(15초) 시 `⏱️ /calc 실행 시간이 초과되었습니다.`를 출력한다.
- 출력이 비어 있으면 `[ERROR] /calc 실행 결과가 비어 있습니다.`를 출력한다.
