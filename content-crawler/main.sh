#!/bin/bash
# 파일 인코딩: UTF-8
# 콘텐츠 크롤러 Bash 스크립트

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/main.py"
CONFIG_FILE="${1:-config.json}"

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "[ERROR] main.py 파일을 찾을 수 없습니다."
    exit 1
fi

echo "콘텐츠 크롤러 시작..."
python3 "$PYTHON_SCRIPT"

if [ $? -eq 0 ]; then
    echo "크롤링 완료 (성공)"
else
    echo "크롤링 실패"
    exit 1
fi
