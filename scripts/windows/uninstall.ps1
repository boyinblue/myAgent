<#
.SYNOPSIS
    myAgent Windows 서비스, 예약 작업, 실행 중인 관련 프로세스 및 선택적 임시/빌드 파일을 제거합니다.
.EXAMPLE
    .\uninstall.ps1
    .\uninstall.ps1 -RemoveCache
    .\uninstall.ps1 -Force
#>
[CmdletBinding(SupportsShouldProcess)]
param (
    [switch]$RemoveCache,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# 서비스명 및 작업 스케줄러 이름 패턴을 실제 환경에 맞게 조정하세요.
$ServicePatterns = @("*myagent*", "*myAgent*")
$TaskPatterns    = @("*myAgent*", "*myagent*")
$ScriptKeywords  = @("telegram_bot.py", "autopilot.py", "dashboard", "main.py")

function Confirm-Action {
    param([string]$Message)
    if ($Force) { return $true }
    $answer = Read-Host "$Message [y/N]"
    return ($answer -match "^(y|yes)$")
}

Write-Host "=== [1/4] myAgent 관련 Windows 서비스 점검 및 제거 ===" -ForegroundColor Cyan
foreach ($pattern in $ServicePatterns) {
    $services = Get-Service -Name $pattern -ErrorAction SilentlyContinue
    foreach ($svc in $services) {
        if (-not (Confirm-Action "서비스 '$($svc.Name)' (상태: $($svc.Status)) 을(를) 중지하고 제거할까요?")) {
            Write-Host "건너뜀: $($svc.Name)" -ForegroundColor Yellow
            continue
        }

        if ($svc.Status -ne "Stopped") {
            Write-Host "서비스 중지 중: $($svc.Name)"
            Stop-Service -Name $svc.Name -Force -ErrorAction SilentlyContinue
        }

        # NSSM으로 등록된 경우 nssm remove 시도 후 sc.exe delete fallback
        $nssm = Get-Command nssm -ErrorAction SilentlyContinue
        if ($nssm) {
            & nssm stop $svc.Name 2>$null
            & nssm remove $svc.Name confirm 2>$null
        }

        if (Get-Service -Name $svc.Name -ErrorAction SilentlyContinue) {
            & sc.exe delete $svc.Name | Out-Null
        }
        Write-Host "제거 완료(서비스): $($svc.Name)" -ForegroundColor Green
    }
}

Write-Host "`n=== [2/4] myAgent 관련 작업 스케줄러(Scheduled Task) 제거 ===" -ForegroundColor Cyan
foreach ($pattern in $TaskPatterns) {
    $tasks = Get-ScheduledTask -TaskName $pattern -ErrorAction SilentlyContinue
    foreach ($task in $tasks) {
        if (-not (Confirm-Action "예약 작업 '$($task.TaskPath)$($task.TaskName)' 을(를) 제거할까요?")) {
            Write-Host "건너뜀: $($task.TaskName)" -ForegroundColor Yellow
            continue
        }
        Stop-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -Confirm:$false
        Write-Host "제거 완료(예약 작업): $($task.TaskName)" -ForegroundColor Green
    }
}

Write-Host "`n=== [3/4] 실행 중인 myAgent 관련 프로세스 종료 ===" -ForegroundColor Cyan
$procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $cmd = $_.CommandLine
    if (-not $cmd) { return $false }
    ($cmd -match "myAgent") -and ($ScriptKeywords | Where-Object { $cmd -like "*$_*" })
}

foreach ($p in $procs) {
    if (-not (Confirm-Action "프로세스 PID $($p.ProcessId) ($($p.Name)) 을(를) 종료할까요?`n  명령: $($p.CommandLine)")) {
        Write-Host "건너뜀: PID $($p.ProcessId)" -ForegroundColor Yellow
        continue
    }
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "종료 완료: PID $($p.ProcessId)" -ForegroundColor Green
}

Write-Host "`n=== [4/4] 선택적 캐시/임시 디렉터리 정리 ===" -ForegroundColor Cyan
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if ($RemoveCache) {
    $cacheTargets = @(
        (Join-Path $projectRoot ".pytest_cache"),
        (Join-Path $projectRoot ".ruff_cache")
    )
    Get-ChildItem -Path $projectRoot -Directory -Filter "__pycache__" -Recurse -ErrorAction SilentlyContinue |
        ForEach-Object { $cacheTargets += $_.FullName }

    foreach ($target in ($cacheTargets | Select-Object -Unique)) {
        if (Test-Path $target) {
            Remove-Item -Path $target -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "캐시 삭제: $target" -ForegroundColor Green
        }
    }
} else {
    Write-Host "캐시 삭제는 생략되었습니다. (캐시까지 지우려면 -RemoveCache 옵션 사용)" -ForegroundColor DarkGray
}

Write-Host "`n정리 작업이 완료되었습니다." -ForegroundColor Cyan
