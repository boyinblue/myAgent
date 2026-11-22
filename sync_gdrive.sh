#!/usr/bin/env bash
set -euo pipefail

LOCAL_PATH="${1:-$HOME/project/myAgent}"
REMOTE_PATH="${2:-gdrive:[Projects]/myAgent}"
MODE="${3:-copy}" # copy | sync | bisync
DRY_RUN="${4:-}"

EXTRA_FLAGS=(
  --exclude ".git/**"
  --exclude ".venv/**"
  --exclude "__pycache__/**"
  --exclude "*.pyc"
  --exclude "**/dashboard.pid"
  --exclude "dashboard.pid"
  --exclude "*.conflict*"
  --exclude "**/*.conflict*"
  --exclude "web-dashboard/**/*.docx"
  --exclude ".tmp.driveupload/**"
  --progress
  --stats 1s
  --stats-one-line
)
DEDUPE_FLAGS=(
  dedupe
  --dedupe-mode newest
  --exclude ".git/**"
  --exclude ".venv/**"
  --exclude "__pycache__/**"
  --exclude "*.pyc"
  --exclude "**/dashboard.pid"
  --exclude "dashboard.pid"
  --exclude "*.conflict*"
  --exclude "**/*.conflict*"
  --exclude "web-dashboard/**/*.docx"
)

if [[ "$DRY_RUN" == "--dry-run" ]]; then
  EXTRA_FLAGS+=(--dry-run)
  DEDUPE_FLAGS+=(--dry-run)
fi

echo "1. Deduplicating remote files on $REMOTE_PATH (keeping newest)..."
rclone "${DEDUPE_FLAGS[@]}" "$REMOTE_PATH"

echo "2. Running rclone $MODE between '$LOCAL_PATH' and '$REMOTE_PATH'..."
case "$MODE" in
  copy)
    rclone copy "$REMOTE_PATH" "$LOCAL_PATH" "${EXTRA_FLAGS[@]}"
    ;;
  sync)
    rclone sync "$REMOTE_PATH" "$LOCAL_PATH" "${EXTRA_FLAGS[@]}"
    ;;
  bisync)
    rclone bisync "$REMOTE_PATH" "$LOCAL_PATH" "${EXTRA_FLAGS[@]}"
    ;;
  *)
    echo "Unsupported mode: $MODE (use copy, sync, or bisync)" >&2
    exit 1
    ;;
esac

echo "Done."
