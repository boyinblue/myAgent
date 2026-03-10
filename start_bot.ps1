# Telegram Bot 시작 스크립트
# 올바른 Python 환경을 강제하고 유효성을 검사합니다

param(
    [switch]$Background = $false,
    [switch]$AutoRestart = $false
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$botScript = Join-Path $projectRoot 'chatbot\telegram_bot.py'

# ===== 환경 유효성 검사 =====
Write-Host "🔍 환경 검증 중..." -ForegroundColor Cyan

if (-not (Test-Path $venvPython)) {
    Write-Host "❌ Virtual environment Python not found!" -ForegroundColor Red
    Write-Host "경로: $venvPython" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $botScript)) {
    Write-Host "❌ Bot script not found!" -ForegroundColor Red
    Write-Host "경로: $botScript" -ForegroundColor Yellow
    exit 1
}

# Python 버전 확인
try {
    $pythonVersion = & $venvPython --version 2>&1
    Write-Host "✅ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python 실행 실패: $_" -ForegroundColor Red
    exit 1
}

# Python 경로 확인
$pythonExe = & $venvPython -c "import sys; print(sys.executable)"
if ($pythonExe -notmatch "\.venv") {
    Write-Host "⚠️  경고: venv가 아닌 시스템 Python 감지됨!" -ForegroundColor Yellow
    Write-Host "경로: $pythonExe" -ForegroundColor Yellow
    Write-Host "venv Python 사용을 강제합니다." -ForegroundColor Cyan
}

# ===== 봇 시작 =====
Write-Host ""
Write-Host "🚀 Telegram Bot 시작 중..." -ForegroundColor Green
Write-Host "📍 Python: $venvPython" -ForegroundColor Cyan
Write-Host "📍 Script: $botScript" -ForegroundColor Cyan

if ($AutoRestart) {
    Write-Host "🔄 Auto-restart 활성화됨" -ForegroundColor Cyan
}

if ($Background) {
    Write-Host "⏳ 백그라운드 실행..." -ForegroundColor Yellow
    Start-Job -ScriptBlock {
        param($python, $script)
        Set-Location $python | Split-Path -Parent | Split-Path -Parent
        & $python $script
    } -ArgumentList $venvPython, $botScript | Out-Null
    Write-Host "✅ Bot started (background job)" -ForegroundColor Green
} else {
    Write-Host "▶️  포그라운드 실행 (Ctrl+C 로 종료)" -ForegroundColor Yellow
    & $venvPython $botScript
}

