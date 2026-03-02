# -*- coding: utf-8 -*-
# 이 스크립트는 Python 3 설치 후 프로젝트용 가상환경을 만들고 필요한 패키지를 설치합니다.
# 한글이 포함되어 있으므로 UTF-8 인코딩입니다.

$envDir = "venv"
if (-not (Test-Path $envDir)) {
    python -m venv $envDir
    Write-Host "가상환경 생성됨: $envDir"
} else {
    Write-Host "이미 가상환경이 존재합니다."
}

# 가상환경 활성화
. "$envDir\Scripts\Activate.ps1"

# pip 최신화 및 패키지 설치
pip install --upgrade pip
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
} else {
    Write-Host "requirements.txt 파일을 찾을 수 없습니다. 필요시 생성하세요."
}