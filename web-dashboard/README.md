# 웹 대시보드

포트포워딩 없이 ngrok을 통해 임시로 웹 대시보드에 접속할 수 있습니다.

## 사전 요구사항

1. **ngrok 설치**
   ```powershell
   # Windows (Chocolatey)
   choco install ngrok
   
   # 또는 https://ngrok.com/download 에서 다운로드
   ```

2. **Python 패키지 설치**
   ```powershell
   pip install Flask requests python-dotenv
   ```

3. **환경 변수 설정** (루트 `.env` 파일에 추가)
   ```
   FLASK_SECRET_KEY=your-secret-key-here
   TELEGRAM_BOT_TOKEN=your-bot-token
   TELEGRAM_CHAT_ID=your-chat-id
   GITHUB_TOKEN=your-github-token
   GITHUB_REPOSITORY=boyinblue/myAgent
   ```

## 실행 방법

### 1. 텔레그램 봇으로 실행 (권장)

텔레그램 봇에게 다음 메시지를 보냅니다:
```
웹 대시보드 시작
```

또는
```
대시보드 열기
```

봇이 자동으로:
1. Flask 웹 서버 시작
2. ngrok 터널 생성
3. 일회용 접속 URL을 텔레그램으로 전송

종료하려면:
```
대시보드 종료
```

### 2. 수동 실행

```powershell
cd web-dashboard
python start.py
```

## 보안 특징

- **일회용 토큰**: URL은 한 번만 사용 가능
- **시간 제한**: 2시간 후 자동 만료
- **무작위 URL**: ngrok이 추측하기 어려운 무작위 URL 생성
- **로컬 전용**: 외부에서 직접 접속 불가능

## 대시보드 기능

- 📊 전체 통계 및 플랫폼별 차트
- 🔍 포스트 검색 (제목, 내용)
- 📋 포스트 목록 조회 (페이지네이션)
- 🔄 크롤링 수동 트리거 (GitHub Actions)
- 🎯 플랫폼 필터링

## 주의사항

- ngrok 무료 플랜은 2시간 세션 제한이 있습니다
- URL을 타인과 공유하지 마세요
- 사용 후 Ctrl+C로 서버를 종료하세요 (또는 텔레그램 봇으로 "대시보드 종료")

## 텔레그램 명령어

| 명령어 | 설명 |
|--------|------|
| `웹 대시보드 시작` | 대시보드 실행 및 URL 전송 |
| `대시보드 열기` | 대시보드 실행 및 URL 전송 |
| `대시보드 종료` | 실행 중인 대시보드 종료 |
| `웹 중지` | 실행 중인 대시보드 종료 |
