# 자동시작 스크립트 업데이트

## 문제점 분석

### 1. 경로 오류
- **원인**: 디렉토리명 변경으로 기존 태스크가 잘못된 경로를 참조
- **이전 경로**: `C:\Users\user\Documents\Porjects\myAgent` ❌ (오타)
- **현재 경로**: `C:\Users\user\Documents\Projects\myAgent` ✅ (정확)

### 2. 콘솔 창 표시 문제
- **원인**: `start_bot_auto_restart.ps1`이 포그라운드에서 실행되어 PowerShell 콘솔이 보임
- **영향**: PC 시작 시 불필요한 콘솔 창이 떠서 불편함

---

## 수정 사항

### ✅ 1. `setup_autostart.ps1` 수정
- 프로젝트 루트 경로 검증 추가
- Python 환경 경로 검증 추가
- 오류 발생 시 명확한 에러 메시지 표시

```powershell
$projectRoot = $PSScriptRoot
if (-not (Test-Path $projectRoot)) {
    Write-Error "프로젝트 루트를 찾을 수 없습니다: $projectRoot"
    exit 1
}

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Error "Python 환경을 찾을 수 없습니다: $venvPython"
    exit 1
}
```

### ✅ 2. `start_bot_auto_restart.ps1` 수정
- **로깅만 파일에 기록** (콘솔 출력 제거)
- 프로젝트 루트 경로 검증 추가
- 백그라운드 실행에 최적화

```powershell
# 변경 전: Write-Host로 콘솔에 출력
Add-Content -Path $logFile -Value $msg
Write-Host $msg  # ❌ 콘솔에도 표시됨

# 변경 후: 파일에만 기록
Add-Content -Path $logFile -Value $msg  # ✅ 로그만 기록
```

### ✅ 3. 태스크 스케줄러 설정
새로운 매개변수로 태스크 등록:
- `-WindowStyle Hidden`: 콘솔 창 숨김
- 정확한 경로 참조

```powershell
-Argument "-NoProfile -ExecutionPolicy RemoteSigned -NonInteractive -WindowStyle Hidden -File `"$autoRestartScript`""
```

---

## 적용 방법

### 관리자 권한으로 PowerShell 실행
```powershell
# Windows 10/11에서 Windows 키 누르고
Start-Process powershell -ArgumentList '-Command "cd ""C:\Users\user\Documents\Projects\myAgent"" ; .\setup_autostart.ps1"' -Verb RunAs
```

또는 PowerShell에서:
```powershell
cd 'C:\Users\user\Documents\Projects\myAgent'
.\setup_autostart.ps1
```

### 태스크 상태 확인
```powershell
Get-ScheduledTask -TaskName "myAgent_*" | Select-Object TaskName, State | Format-Table -AutoSize
```

### 즉시 테스트 (필요시)
```powershell
Start-ScheduledTask -TaskName 'myAgent_TelegramBot'
```

### 로그 확인
```powershell
$logPath = [Environment]::GetFolderPath('LocalApplicationData') + '\myAgent\chatbot_logs\auto_restart.log'
Get-Content -Path $logPath -Tail 50 # 최근 50줄
# 또는
tail -f $logPath  # 실시간 모니터링
```

---

## 등록된 서비스

| 서비스명 | 트리거 | 설명 |
|---------|--------|------|
| myAgent_TelegramBot | 로그인 시 | Telegram 봇 + 자동 재시작 (숨김 모드) |
| myAgent_WebDashboard | 로그인 시 | 웹 대시보드 (http://127.0.0.1:5000) |
| myAgent_Crawler | 매일 08:00 | 콘텐츠 크롤러 |
| myAgent_DailyDigest | 매일 06:00 | 일일 요약 (옵션) |

---

## 로그 파일 위치

```
%LOCALAPPDATA%\myAgent\
├── chatbot_logs\
│   ├── auto_restart.log          # 봇 재시작 로그
│   ├── telegram_bot_stdout.log   # 봇 표준 출력
│   ├── telegram_bot_stderr.log   # 봇 에러 출력
│   └── telegram_bot.lock         # 봇 PID 파일
├── dashboard_logs\
│   └── autostart_dashboard.log   # 대시보드 로그
└── crawler_logs\
    └── autostart_crawler.log     # 크롤러 로그
```

---

## 트러블슈팅

### 태스크가 실행되지 않는 경우
1. **경로 확인**: `C:\Users\user\Documents\Projects\myAgent` 존재 여부 확인
2. **Python 환경 확인**: `.venv\Scripts\python.exe` 존재 여부 확인
3. **로그 확인**: `%LOCALAPPDATA%\myAgent\chatbot_logs\auto_restart.log` 확인
4. **권한 확인**: 태스크 스케줄러에서 작업 권한 설정 확인

### 콘솔이 여전히 보이는 경우
- 태스크 스케줄러를 통해 다시 등록 (위의 적용 방법 참고)
- 또는 수동으로 태스크 편집에서 `-WindowStyle Hidden` 옵션 확인

---

**최종 수정 날짜**: 2026-11-14
**상태**: ✅ 수정 완료 (관리자 권한으로 `setup_autostart.ps1` 실행 필요)
