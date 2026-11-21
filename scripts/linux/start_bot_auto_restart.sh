#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
log_dir="${XDG_STATE_HOME:-$HOME/.local/state}/myAgent"
mkdir -p "$log_dir"
while true; do
  "$project_root/scripts/linux/start_bot.sh" >>"$log_dir/telegram_bot.log" 2>&1 || true
  sleep 10
done
