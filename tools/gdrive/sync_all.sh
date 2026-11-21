#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/parksejin/project/myAgent"
LOG_FILE="${PROJECT_ROOT}/logs/gdrive_sync.log"
mkdir -p "${PROJECT_ROOT}/logs"

cd "$PROJECT_ROOT"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [sync_all] Git 원격 변경사항 확인 시작" >> "$LOG_FILE"
if git diff --quiet && git diff --cached --quiet; then
  git pull --rebase >> "$LOG_FILE" 2>&1 || echo "[$(date '+%Y-%m-%d %H:%M:%S')] [sync_all] git pull 경고 (계속 진행)" >> "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [sync_all] 로컬 미커밋 변경사항이 있어 git pull 건너뜀" >> "$LOG_FILE"
fi

"${PROJECT_ROOT}/tools/gdrive/sync_gdrive.sh" bisync
