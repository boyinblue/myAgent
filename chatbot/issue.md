# /issue 명령 가이드

`/issue`는 GitHub 이슈를 조회/등록하는 명령입니다.

## 사용법

- `/issue create <내용>`
  - 동일/유사 이슈가 있는지 먼저 확인합니다.
  - 유사 이슈가 없으면 새 이슈를 등록합니다.
- `/issue list`
  - 현재 오픈(open)된 이슈 목록을 출력합니다.
- `/issue history`
  - 종료(closed)된 이슈 목록을 출력합니다.

## 예시

- `/issue create 대시보드 stop 후에도 접속이 됩니다`
- `/issue list`
- `/issue history`

## 참고

- GitHub 연동에는 `GITHUB_TOKEN`과 저장소 설정(`owner/repo`)이 필요합니다.
- 조회/등록 대상은 `chatbot`, `feedback` 라벨 이슈입니다.
