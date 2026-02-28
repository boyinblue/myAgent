# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
# 콘텐츠 크롤러 PowerShell 스크립트

param(
    [string]$ConfigFile = "config.json"
)

# Python 스크립트 실행
$pythonScript = Join-Path $PSScriptRoot "main.py"

if (-not (Test-Path $pythonScript)) {
    Write-Host "[ERROR] main.py 파일을 찾을 수 없습니다." -ForegroundColor Red
    exit 1
}

Write-Host "콘텐츠 크롤러 시작..." -ForegroundColor Green
python $pythonScript

if ($LASTEXITCODE -eq 0) {
    Write-Host "크롤링 완료 (성공)" -ForegroundColor Green
} else {
    Write-Host "크롤링 실패 (종료 코드: $LASTEXITCODE)" -ForegroundColor Red
}
