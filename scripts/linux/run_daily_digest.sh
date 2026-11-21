#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/myAgent/daily_digest"
mkdir -p "$state_dir"
today="$(date +%F)"
state_file="$state_dir/last_successful_run.txt"
[[ -f "$state_file" && "$(cat "$state_file")" == "$today" ]] && exit 0
"$project_root/.venv/bin/python" "$project_root/content-crawler/run_anniversary_digest.py" >>"$state_dir/daily_digest.log" 2>&1
printf '%s\n' "$today" >"$state_file"
