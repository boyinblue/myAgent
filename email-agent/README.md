# email-agent

Daum 메일 스팸/프로모션 정리를 위한 CLI 에이전트입니다.

- IMAP으로 메일 수집
- 발신자별 수신량 집계 (많이 받은 순)
- `List-Unsubscribe`/본문 링크 기반 수신거부 후보 추출
- 사용자 확인 후 실행 (기본은 DRY-RUN)

## 1) 설치

```bash
pip install -r requirements.txt
```

## 2) 환경 변수

`.env.example`를 `.env`로 복사 후 설정:

```env
DAUM_EMAIL=your_id@daum.net
DAUM_APP_PASSWORD=your_app_password
DAUM_IMAP_HOST=imap.daum.net
DAUM_IMAP_PORT=993
MAILBOX_INBOX=INBOX
MAILBOX_SPAM=Spam
```

## 3) 실행

미리보기 모드(기본):

```bash
python main.py --limit 300 --include-spam
```

실행 모드(실제 링크 호출):

```bash
python main.py --limit 300 --include-spam --apply
```

## 안전 기본값

- 기본 모드는 `DRY-RUN`입니다.
- 본문 링크는 `unsubscribe/optout/수신거부` 키워드가 포함된 URL만 후보로 취급합니다.
- 실행 전 사용자 확인(`y`)을 한 번 더 받습니다.

## 참고

Daum은 공개 메일 API 대신 IMAP 접근이 현실적인 방식입니다.

## 문제 해결

`imaplib.IMAP4.error: LOGIN failed. Invalid login/password.` 가 나오면:

- `email-agent/.env` 파일이 실제로 로드되는지 확인 (`DAUM_EMAIL`, `DAUM_APP_PASSWORD`)
- `DAUM_APP_PASSWORD`는 일반 비밀번호가 아니라 앱 비밀번호 사용
- `DAUM_EMAIL`은 `id@daum.net` 형식 권장 (코드에서 `id` 형식도 자동 시도)
- 서버 값 확인: `DAUM_IMAP_HOST=imap.daum.net`, `DAUM_IMAP_PORT=993`
