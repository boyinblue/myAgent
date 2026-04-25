# PC 부팅 시 서비스 자동 시작 설정 스크립트
# 관리자 권한 없이 현재 사용자의 작업 스케줄러에 등록합니다

$projectRoot = $PSScriptRoot
$venvPython  = Join-Path $projectRoot '.venv\Scripts\python.exe'

# ─────────────────────────────────────────────
# 공통 헬퍼
# ─────────────────────────────────────────────
function Register-ServiceTask {
    param(
        [string]$TaskName,
        [string]$Description,
        [string]$PythonScript,
        [string]$LogFile
    )

    # 기존 태스크 제거
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    $logDir = Split-Path $LogFile -Parent
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

    $action  = New-ScheduledTaskAction `
        -Execute $venvPython `
        -Argument "`"$PythonScript`" >> `"$LogFile`" 2>&1" `
        -WorkingDirectory $projectRoot

    # 로그온 시 실행 (부팅 후 첫 로그인)
    $trigger = New-ScheduledTaskTrigger -AtLogOn

    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -MultipleInstances IgnoreNew

    $principal = New-ScheduledTaskPrincipal `
        -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
        -LogonType Interactive `
        -RunLevel Limited

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $Description `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null

    Write-Host "  [OK] 태스크 등록: $TaskName" -ForegroundColor Green
}

# ─────────────────────────────────────────────
# 1. 텔레그램 봇 자동 시작
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "=== 텔레그램 봇 자동 시작 등록 ===" -ForegroundColor Cyan

$botScript = Join-Path $projectRoot 'chatbot\telegram_bot.py'
$botLog    = Join-Path $env:LOCALAPPDATA 'myAgent\chatbot_logs\autostart_bot.log'

Register-ServiceTask `
    -TaskName    "myAgent_TelegramBot" `
    -Description "myAgent 텔레그램 봇 (로그인 시 자동 시작)" `
    -PythonScript $botScript `
    -LogFile $botLog

# ─────────────────────────────────────────────
# 2. 웹 대시보드 자동 시작
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "=== 웹 대시보드 자동 시작 등록 ===" -ForegroundColor Cyan

$dashScript = Join-Path $projectRoot 'web-dashboard\start.py'
$dashLog    = Join-Path $env:LOCALAPPDATA 'myAgent\dashboard_logs\autostart_dashboard.log'

Register-ServiceTask `
    -TaskName    "myAgent_WebDashboard" `
    -Description "myAgent 웹 대시보드 (로그인 시 자동 시작, http://127.0.0.1:5000)" `
    -PythonScript $dashScript `
    -LogFile $dashLog

# ─────────────────────────────────────────────
# 등록 결과 확인
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "=== 등록된 태스크 목록 ===" -ForegroundColor Cyan
Get-ScheduledTask -TaskName "myAgent_*" | Select-Object TaskName, State | Format-Table -AutoSize

Write-Host ""
Write-Host "완료! 다음 번 로그인부터 자동으로 시작됩니다." -ForegroundColor Yellow
Write-Host "지금 바로 시작하려면:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName 'myAgent_TelegramBot'" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskName 'myAgent_WebDashboard'" -ForegroundColor White
Write-Host ""
Write-Host "태스크를 제거하려면:" -ForegroundColor Yellow
Write-Host "  Unregister-ScheduledTask -TaskName 'myAgent_TelegramBot' -Confirm:`$false" -ForegroundColor White
Write-Host "  Unregister-ScheduledTask -TaskName 'myAgent_WebDashboard' -Confirm:`$false" -ForegroundColor White
