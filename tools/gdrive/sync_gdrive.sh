#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
GDRIVE_REMOTE="${GDRIVE_REMOTE:-gdrive}"
GDRIVE_DIR="${GDRIVE_DIR:-[Projects]/myAgent}"
REMOTE_TARGET="${GDRIVE_REMOTE}:${GDRIVE_DIR}"

MODE="${1:-bisync}"   # bisync | pull | push
RESYNC_FLAG=""
DRY_RUN_FLAG=""

for arg in "${@:2}"; do
  case "$arg" in
    --resync) RESYNC_FLAG="--resync" ;;
    --dry-run) DRY_RUN_FLAG="--dry-run" ;;
  esac
done

FILTER_RULES=(
  "--exclude" ".venv/**"
  "--exclude" "venv/**"
  "--exclude" "**/__pycache__/**"
  "--exclude" "*.pyc"
  "--exclude" ".git/**"
  "--exclude" ".runtime/**"
  "--exclude" "*.bak.*"
  "--exclude" ".env"
)

LOCK_FILE="/tmp/myagent_gdrive_sync.lock"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/gdrive_sync.log"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 이미 다른 gdrive 동기화 작업이 실행 중입니다." | tee -a "$LOG_FILE"
  exit 1
fi

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

if ! command -v rclone >/dev/null 2>&1; then
  log "[ERROR] rclone이 설치되어 있지 않습니다."
  exit 1
fi

log "시작: mode=${MODE}, local=${PROJECT_ROOT}, remote=${REMOTE_TARGET}"

case "$MODE" in
  bisync)
    BISYNC_WORKDIR="${HOME}/.cache/rclone/bisync"
    if [ -z "$RESYNC_FLAG" ] && { [ ! -d "$BISYNC_WORKDIR" ] || [ -z "$(ls -A "$BISYNC_WORKDIR" 2>/dev/null)" ]; }; then
      log "초기 bisync 상태가 없어 --resync를 적용합니다."
      RESYNC_FLAG="--resync"
    fi

    rclone bisync "$PROJECT_ROOT" "$REMOTE_TARGET" \
      "${FILTER_RULES[@]}" \
      --conflict-resolve newer \
      --create-empty-src-dirs \
      --fast-list \
      $RESYNC_FLAG \
      $DRY_RUN_FLAG \
      -v 2>&1 | tee -a "$LOG_FILE"
    ;;
  pull)
    rclone copy "$REMOTE_TARGET" "$PROJECT_ROOT" \
      "${FILTER_RULES[@]}" \
      --update \
      $DRY_RUN_FLAG \
      -v 2>&1 | tee -a "$LOG_FILE"
    ;;
  push)
    rclone copy "$PROJECT_ROOT" "$REMOTE_TARGET" \
      "${FILTER_RULES[@]}" \
      --update \
      $DRY_RUN_FLAG \
      -v 2>&1 | tee -a "$LOG_FILE"
    ;;
  *)
    log "[ERROR] 지원하지 않는 모드입니다: $MODE (사용 가능: bisync | pull | push)"
    exit 1
    ;;
esac

log "완료: mode=${MODE}"
