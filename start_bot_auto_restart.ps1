# Telegram Bot 자동 재시작 스크립트
# 1분마다 봇의 상태를 확인하고, 죽어있으면 자동으로 재시작합니다

$projectRoot = 'C:\Users\user\Documents\Porjects\myAgent'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$botScript = Join-Path $projectRoot 'chatbot\telegram_bot.py'
$lockFile = [Environment]::GetFolderPath('LocalApplicationData') + '\myAgent\chatbot_logs\telegram_bot.lock'
$logFile = [Environment]::GetFolderPath('LocalApplicationData') + '\myAgent\chatbot_logs\auto_restart.log'

function Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $msg = "[$timestamp] $Message"
    Add-Content -Path $logFile -Value $msg
    Write-Host $msg
}

function IsProcessAlive {
    param([int]$ProcessId)
    try {
        $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        return ($null -ne $proc)
    }
    catch {
        return $false
    }
}

function RestartBot {
    Log "봇 재시작 시도..."
    
    # 기존 프로세스 종료
    if (Test-Path $lockFile) {
        $oldPid = Get-Content $lockFile -ErrorAction SilentlyContinue
        if ($oldPid) {
            $oldProc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
            if ($null -ne $oldProc) {
                Log "  PID $oldPid 종료"
                Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 2
            }
        }
    }

    # 새 프로세스 시작
    try {
        Start-Job -ScriptBlock {
            param($python, $script, $root)
            Set-Location $root
            & $python $script
        } -ArgumentList $venvPython, $botScript, $projectRoot -ErrorAction Stop | Out-Null
        
        Log "  봇 시작됨"
        return $true
    }
    catch {
        Log "  시작 실패: $_"
        return $false
    }
}

Log "================================"
Log "Bot Auto-Restart Daemon Start"
Log "================================"

# 메인 루프
while ($true) {
    Start-Sleep -Seconds 60
    
    if (-not (Test-Path $lockFile)) {
        Log "Lock file 없음 - 재시작"
        RestartBot | Out-Null
        continue
    }

    $botPid = Get-Content $lockFile -ErrorAction SilentlyContinue
    if (-not $botPid) {
        Log "Lock file 비어있음 - 재시작"
        RestartBot | Out-Null
        continue
    }

    if (-not (IsProcessAlive $botPid)) {
        Log "PID $botPid 프로세스 죽음 - 재시작"
        RestartBot | Out-Null
    }
    else {
        Log "Bot OK (PID: $botPid)"
    }
}

