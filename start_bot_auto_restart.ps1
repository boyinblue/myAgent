# Telegram Bot 자동 재시작 스크립트
# 1분마다 봇의 상태를 확인하고, 죽어있으면 자동으로 재시작합니다
# 이 스크립트는 백그라운드에서 숨김 모드로 실행됩니다

$projectRoot = $PSScriptRoot
if (-not (Test-Path $projectRoot)) {
    exit 1
}

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$botScript = Join-Path $projectRoot 'chatbot\telegram_bot.py'
$lockFile = [Environment]::GetFolderPath('LocalApplicationData') + '\myAgent\chatbot_logs\telegram_bot.lock'
$logFile = [Environment]::GetFolderPath('LocalApplicationData') + '\myAgent\chatbot_logs\auto_restart.log'
$logDir = Split-Path $logFile -Parent
$stdoutLog = Join-Path $logDir 'telegram_bot_stdout.log'
$stderrLog = Join-Path $logDir 'telegram_bot_stderr.log'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $msg = "[$timestamp] $Message"
    Add-Content -Path $logFile -Value $msg
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

    if (Test-Path $lockFile) {
        $oldPidText = Get-Content $lockFile -ErrorAction SilentlyContinue
        $oldPid = 0
        if ([int]::TryParse("$oldPidText", [ref]$oldPid) -and (IsProcessAlive $oldPid)) {
            Log "  기존 봇이 실행 중입니다 (PID: $oldPid)"
            return $true
        }
        Remove-Item -LiteralPath $lockFile -Force -ErrorAction Stop
        Log "  오래된 lock file 삭제"
    }

    # 새 프로세스 시작
    try {
        $process = Start-Process `
            -FilePath $venvPython `
            -ArgumentList "`"$botScript`"" `
            -WorkingDirectory $projectRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdoutLog `
            -RedirectStandardError $stderrLog `
            -PassThru `
            -ErrorAction Stop

        for ($attempt = 0; $attempt -lt 15; $attempt++) {
            if (Test-Path $lockFile) {
                $botPid = Get-Content $lockFile -ErrorAction SilentlyContinue
                if ($botPid -eq $process.Id) {
                    Log "  봇 시작됨 (PID: $botPid)"
                    return $true
                }
            }
            if (-not (IsProcessAlive $process.Id)) {
                Log "  봇 프로세스가 시작 직후 종료됨 (PID: $($process.Id)); stderr: $stderrLog"
                return $false
            }
            Start-Sleep -Seconds 1
        }

        Log "  lock file 확인 시간 초과; 시작 프로세스를 종료합니다 (PID: $($process.Id))"
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        if (Test-Path $lockFile) {
            $lockPid = Get-Content $lockFile -ErrorAction SilentlyContinue
            if ($lockPid -eq $process.Id) {
                Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue
            }
        }
        return $false
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
    if (-not (Test-Path $lockFile)) {
        Log "Lock file 없음 - 재시작"
        RestartBot | Out-Null
    }
    else {
        $botPid = Get-Content $lockFile -ErrorAction SilentlyContinue
        if (-not $botPid) {
            Log "Lock file 비어있음 - 재시작"
            RestartBot | Out-Null
        }
        elseif (-not (IsProcessAlive $botPid)) {
            Log "PID $botPid 프로세스 죽음 - 재시작"
            RestartBot | Out-Null
        }
        else {
            Log "Bot OK (PID: $botPid)"
        }
    }

    Start-Sleep -Seconds 60
}

