# 웹 대시보드

포트포워딩 없이 ngrok을 통해 임시로 웹 대시보드에 접속할 수 있습니다.

또한 Windows 환경에서는 작업 스케줄러를 이용하여 웹 대시보드를 백그라운드에서 자동 실행할 수 있습니다.

## 사전 요구사항

### 1. ngrok 설치

```powershell
# Windows (Chocolatey)
choco install ngrok

# 또는 https://ngrok.com/download 에서 다운로드
```

### 2. Python 패키지 설치

```powershell
pip install Flask requests python-dotenv
```

### 3. 환경 변수 설정

프로젝트 루트의 `.env` 파일에 다음 내용을 추가합니다.

```env
FLASK_SECRET_KEY=your-secret-key-here
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
GITHUB_TOKEN=your-github-token
GITHUB_REPOSITORY=boyinblue/myAgent
```

## 파일 구조

```text
myAgent/
├── .venv/
│   └── Scripts/
│       ├── python.exe
│       └── pythonw.exe
│
└── web-dashboard/
    ├── app.py
    ├── start.py
    ├── launch_hidden.py
    └── start.log
```

| 파일 | 설명 |
|------|------|
| `app.py` | Flask 웹 대시보드 애플리케이션 |
| `start.py` | 웹 서버 시작 스크립트. DB 마이그레이션 및 시작 시 자동 크롤링 확인 수행 |
| `launch_hidden.py` | 콘솔 창 없이 웹 서버를 백그라운드에서 실행하는 런처 |
| `start.log` | 백그라운드 실행 시 시작 메시지, 서버 로그 및 오류 기록 |
| `python.exe` | 일반 Python 실행 파일. 콘솔 창 표시 |
| `pythonw.exe` | 콘솔 창 없이 Python 프로그램 실행 |

## 실행 방법

### 1. 텔레그램 봇으로 실행 (권장)

텔레그램 봇에게 다음 메시지를 보냅니다.

```text
웹 대시보드 시작
```

또는

```text
대시보드 열기
```

봇이 자동으로 다음 작업을 수행합니다.

1. Flask 웹 서버 시작
2. ngrok 터널 생성
3. 일회용 접속 URL을 텔레그램으로 전송

종료하려면 다음 메시지를 보냅니다.

```text
대시보드 종료
```

### 2. 수동 실행

프로젝트 루트에서 다음 명령어를 실행합니다.

```powershell
cd web-dashboard
python start.py
```

이 방식은 콘솔 창에서 서버 실행 로그를 직접 확인할 수 있습니다.

서버를 종료하려면 `Ctrl + C`를 누릅니다.

### 3. 백그라운드 실행 (Windows)

Windows에서 콘솔 창 없이 웹 대시보드를 실행하려면 `launch_hidden.py`를 사용합니다.

프로젝트 루트 디렉터리에서 실행합니다.

```powershell
.\.venv\Scripts\pythonw.exe web-dashboard\launch_hidden.py
```

`pythonw.exe`를 사용하므로 별도의 콘솔 창이 표시되지 않습니다.

실행 로그는 다음 파일에 기록됩니다.

```text
web-dashboard/start.log
```

로그 파일을 확인하면 서버 시작 여부, DB 마이그레이션 결과, 자동 크롤링 확인 결과 및 오류 내용을 확인할 수 있습니다.

### 4. Windows 시작 시 자동 실행

Windows 로그인 시 웹 대시보드가 자동으로 실행되도록 작업 스케줄러(Task Scheduler)를 설정합니다.

실행 방법:

1. `Win + R`을 누릅니다.
2. `taskschd.msc`를 입력하여 작업 스케줄러를 실행합니다.
3. 작업 스케줄러 라이브러리에서 새 작업을 생성합니다.
4. 트리거를 `사용자가 로그온할 때`로 설정합니다.
5. 동작을 `프로그램 시작`으로 설정하고 다음 값을 입력합니다.

**프로그램/스크립트**

```text
C:\Users\<사용자명>\Documents\Projects\myAgent\.venv\Scripts\pythonw.exe
```

**인수 추가**

```text
web-dashboard\launch_hidden.py
```

**시작 위치**

```text
C:\Users\<사용자명>\Documents\Projects\myAgent
```

6. 작업을 저장하고 실행하여 정상 동작하는지 확인합니다.

이 설정을 사용하면 Windows 로그인 시 다음과 같이 동작합니다.

- Python 웹 서버가 백그라운드에서 실행됩니다.
- 별도의 검은색 콘솔 창이 표시되지 않습니다.
- 웹 대시보드는 로컬 주소 `http://127.0.0.1:5000`에서 접근할 수 있습니다.
- 실행 로그는 `web-dashboard/start.log`에 기록됩니다.

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

- ngrok 무료 플랜은 2시간 세션 제한이 있습니다.
- URL을 타인과 공유하지 마세요.
- 수동 실행 시 사용 후 `Ctrl + C`로 서버를 종료하세요.
- 백그라운드 실행 시 작업 스케줄러에서 해당 작업을 종료할 수 있습니다.
- 백그라운드 실행 중 문제가 발생하면 `web-dashboard/start.log`를 확인하세요.
- `pythonw.exe`는 콘솔 출력을 표시하지 않으므로 로그 파일을 통해 실행 상태와 오류를 확인해야 합니다.

## 텔레그램 명령어

| 명령어 | 설명 |
|--------|------|
| `웹 대시보드 시작` | 대시보드 실행 및 URL 전송 |
| `대시보드 열기` | 대시보드 실행 및 URL 전송 |
| `대시보드 종료` | 실행 중인 대시보드 종료 |
| `웹 중지` | 실행 중인 대시보드 종료 |