#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="$project_root/.venv/bin/python"
[[ -x "$python_bin" ]] || { echo "Python not found: $python_bin" >&2; exit 1; }
exec "$python_bin" "$project_root/chatbot/telegram_bot.py"
