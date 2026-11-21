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

# 동기화 제외 패턴:
# - 기존 credentials, logs 디렉터리 및 숨김 관리 폴더
# - DB 파일 및 임시/캐시 파일
FILTER_RULES=(
  "--exclude" "credentials/**"
  "--exclude" ".credentials/**"
  "--exclude" "logs/**"
  "--exclude" ".logs/**"
  "--exclude" ".db/**"
  "--exclude" ".runtime/**"
  "--exclude" ".venv/**"
  "--exclude" "venv/**"
  "--exclude" ".git/**"
  "--exclude" "**/__pycache__/**"
  "--exclude" "*.pyc"
  "--exclude" "*.pyo"
  "--exclude" "*.bak.*"
  "--exclude" ".env*"
  "--exclude" "*credential*.json"
  "--exclude" "*token*.json"
  "--exclude" "client_secret*.json"
  "--exclude" "service_account*.json"
  "--exclude" "*.log"
  "--exclude" "*.jsonl"
  "--exclude" "*.db"
  "--exclude" "*.db-wal"
  "--exclude" "*.db-shm"
  "--exclude" "*.db-journal"
  "--exclude" "*.sqlite"
  "--exclude" "*.sqlite3"
  "--exclude" ".DS_Store"
  "--exclude" "Thumbs.db"
  "--exclude" "*.swp"
  "--exclude" "*.swo"
  "--exclude" "*~"
  "--exclude" "*.tmp"
  "--exclude" "*.temp"
  "--exclude" ".pytest_cache/**"
  "--exclude" ".ruff_cache/**"
  "--exclude" ".mypy_cache/**"
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

apply_local_sh_permissions() {
  local count=0
  while IFS= read -r -d '' sh_file; do
    if [ ! -x "$sh_file" ]; then
      if [ -z "$DRY_RUN_FLAG" ]; then
        chmod +x "$sh_file"
      fi
      count=$((count + 1))
    fi
  done < <(
    find "$PROJECT_ROOT" \
      \( -path "${PROJECT_ROOT}/.venv" -o -path "${PROJECT_ROOT}/venv" -o -path "${PROJECT_ROOT}/.git" -o -path "${PROJECT_ROOT}/.runtime" -o -path "${PROJECT_ROOT}/credentials" -o -path "${PROJECT_ROOT}/logs" -o -path "*/__pycache__" \) -prune -o \
      -type f -name "*.sh" -print0
  )

  if [ -n "$DRY_RUN_FLAG" ]; then
    log "[DRY-RUN] 실행 권한 대상 *.sh 파일 점검 완료 (권한 미부여 수: ${count})"
  else
    log "로컬 *.sh 실행 권한(chmod +x) 적용 완료 (신규 부여: ${count}개)"
  fi
}

cleanup_gdrive_duplicates() {
  if [ -n "$DRY_RUN_FLAG" ]; then
    log "[DRY-RUN] Google Drive 중복 파일 정리 미리보기: ${REMOTE_TARGET}"
    rclone dedupe "$REMOTE_TARGET" \
      --dedupe-mode newest \
      --dry-run \
      -v 2>&1 | tee -a "$LOG_FILE"
  else
    log "Google Drive 중복 파일 정리(최신 1개 유지): ${REMOTE_TARGET}"
    rclone dedupe "$REMOTE_TARGET" \
      --dedupe-mode newest \
      -v 2>&1 | tee -a "$LOG_FILE"
  fi
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

# 1) Google Drive 중복 파일 정리 (최신 파일만 남김)
cleanup_gdrive_duplicates

# 2) 로컬 *.sh 파일 실행 권한 자동 부여
apply_local_sh_permissions

log "완료: mode=${MODE}"
