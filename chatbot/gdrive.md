# /gdrive

구글 드라이브 파일 구조를 탐색합니다.

## 사용법
- `/gdrive` : 루트 폴더부터 재귀 탐색

## 사전 준비
1. Google Cloud에서 Service Account 키(JSON) 발급
2. 프로젝트 루트에 `credentials.json` 배치
3. 서비스 계정 이메일을 탐색 대상 드라이브(또는 공유드라이브)에 공유
4. `google-api-python-client`, `google-auth` 패키지 설치

## 실행 동작
`/gdrive`를 입력하면 내부적으로 `tools/gdrive.py`를 실행합니다.

## 오류 안내
- `인증 파일(credentials.json)이 존재하지 않습니다.`
  - 프로젝트 루트에 `credentials.json`이 있는지 확인하세요.
- `API 에러 발생`
  - 서비스 계정 권한 및 공유 설정을 확인하세요.
