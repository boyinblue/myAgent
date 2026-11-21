#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

LOCK_FILE="/tmp/myagent_gdrive_sync.lock"
LOG_FILE="${PROJECT_ROOT}/logs/gdrive_sync.log"
mkdir -p "${PROJECT_ROOT}/logs"

MODE="${1:-bisync}"
shift || true
EXTRA_ARGS=("$@")

if [[ -e "$LOCK_FILE" ]]; then
  LOCK_PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "$LOCK_PID" ]] && kill -0 "$LOCK_PID" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 이미 다른 gdrive 동기화 작업이 실행 중입니다. (PID: $LOCK_PID)"
    echo "--- 관련 프로세스 (ps aux) ---"
    ps aux | grep -E "sync_gdrive|sync_all|rclone" | grep -v grep || true
    echo "--- 최근 로그 (tail -n 10) ---"
    tail -n 10 "$LOG_FILE" 2>/dev/null || echo "로그 파일이 없습니다."
    exit 0
  else
    rm -f "$LOCK_FILE"
  fi
fi

echo "$$" > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

LOCAL_PATH="$PROJECT_ROOT"
REMOTE_PATH="gdrive:[Projects]/myAgent"

EXCLUDES=(
  --exclude "credentials/**"
  --exclude ".credentials/**"
  --exclude "logs/**"
  --exclude ".logs/**"
  --exclude ".db/**"
  --exclude ".runtime/**"
  --exclude ".venv/**"
  --exclude "venv/**"
  --exclude ".git/**"
  --exclude "**/__pycache__/**"
  --exclude "*.pyc"
  --exclude "*.pyo"
  --exclude "*.bak.*"
  --exclude ".env*"
  --exclude "*credential*.json"
  --exclude "*token*.json"
  --exclude "client_secret*.json"
  --exclude "service_account*.json"
  --exclude "*.log"
  --exclude "*.jsonl"
  --exclude "*.db"
  --exclude "*.db-wal"
  --exclude "*.db-shm"
  --exclude "*.db-journal"
  --exclude "*.sqlite"
  --exclude "*.sqlite3"
  --exclude ".DS_Store"
  --exclude "Thumbs.db"
  --exclude "*.swp"
  --exclude "*.swo"
  --exclude "*~"
  --exclude "*.tmp"
  --exclude "*.temp"
  --exclude ".pytest_cache/**"
  --exclude ".ruff_cache/**"
  --exclude ".mypy_cache/**"
  --exclude ".cache/**"
  --exclude ".vscode/**"
  --exclude ".vscode-server/**"
  --exclude ".codex/**"
  --exclude "actions-runner/**"
  --exclude "node_modules/**"
)

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 시작: mode=${MODE}, local=${LOCAL_PATH}, remote=${REMOTE_PATH}"
  case "$MODE" in
    bisync)
      rclone bisync "$LOCAL_PATH" "$REMOTE_PATH" \
        "${EXCLUDES[@]}" \
        --conflict-resolve newer \
        --create-empty-src-dirs \
        --fast-list \
        "${EXTRA_ARGS[@]}" \
        -v
      ;;
    copy)
      rclone copy "$REMOTE_PATH" "$LOCAL_PATH" "${EXCLUDES[@]}" --fast-list "${EXTRA_ARGS[@]}" -v
      ;;
    sync)
      rclone sync "$REMOTE_PATH" "$LOCAL_PATH" "${EXCLUDES[@]}" --fast-list "${EXTRA_ARGS[@]}" -v
      ;;
    *)
      echo "지원하지 않는 모드입니다: $MODE (bisync | copy | sync)" >&2
      exit 1
      ;;
  esac
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 종료: mode=${MODE}"
} >> "$LOG_FILE" 2>&1
