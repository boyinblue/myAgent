#!/usr/bin/env bash
set -e

# 프로젝트 루트 경로 자동 감지
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "$PROJECT_ROOT" ]; then
    echo "Error: 프로젝트 루트를 찾을 수 없습니다: $PROJECT_ROOT"
    exit 1
fi

# 가상환경 파이썬 경로 확인
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    echo "Error: Python 환경을 찾을 수 없습니다: $PYTHON_BIN"
    exit 1
fi

echo ""
echo "=== myAgent 리눅스 자동 시작 서비스 등록 (systemd user) ==="

# systemd 유저 디렉토리 및 로그 디렉토리 생성
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

LOG_DIR="$HOME/.local/share/myAgent/logs"
mkdir -p "$LOG_DIR"

# ─────────────────────────────────────────────
# 1. 텔레그램 봇 서비스 등록 (항상 자동 재시작)
# ─────────────────────────────────────────────
echo "[*] 텔레그램 봇 서비스 등록 중..."
cat << EOF > "$SYSTEMD_USER_DIR/myagent-telegram.service"
[Unit]
Description=myAgent Telegram Bot (Auto-restart)
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_ROOT
ExecStart=$PYTHON_BIN chatbot/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/telegram_bot.log
StandardError=append:$LOG_DIR/telegram_bot.log

[Install]
WantedBy=default.target
EOF

# ─────────────────────────────────────────────
# 2. 웹 대시보드 서비스 등록
# ─────────────────────────────────────────────
echo "[*] 웹 대시보드 서비스 등록 중..."
cat << EOF > "$SYSTEMD_USER_DIR/myagent-dashboard.service"
[Unit]
Description=myAgent Web Dashboard (http://127.0.0.1:5000)
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_ROOT
ExecStart=$PYTHON_BIN web-dashboard/start.py
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/dashboard.log
StandardError=append:$LOG_DIR/dashboard.log

[Install]
WantedBy=default.target
EOF

# ─────────────────────────────────────────────
# 3. Content Crawler 서비스 및 타이머 등록 (매일 08:00)
# ─────────────────────────────────────────────
echo "[*] 콘텐츠 크롤러 스케줄(타이머) 등록 중..."
cat << EOF > "$SYSTEMD_USER_DIR/myagent-crawler.service"
[Unit]
Description=myAgent Content Crawler Job

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_ROOT
ExecStart=$PYTHON_BIN content-crawler/main.py --schedule
StandardOutput=append:$LOG_DIR/crawler.log
StandardError=append:$LOG_DIR/crawler.log
EOF

cat << EOF > "$SYSTEMD_USER_DIR/myagent-crawler.timer"
[Unit]
Description=Run myAgent Content Crawler daily at 08:00

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

# ─────────────────────────────────────────────
# systemd 데몬 리로드 및 서비스 활성화
# ─────────────────────────────────────────────
systemctl --user daemon-reload

systemctl --user enable --now myagent-telegram.service
systemctl --user enable --now myagent-dashboard.service
systemctl --user enable --now myagent-crawler.timer

echo ""
echo "완료! 서비스가 등록되었으며 즉시 백그라운드에서 실행됩니다."
echo ""
echo "=== 등록된 서비스 상태 확인 ==="
echo "  systemctl --user status myagent-telegram"
echo "  systemctl --user status myagent-dashboard"
echo "  systemctl --user status myagent-crawler.timer"
echo ""
echo "서비스를 중지/비활성화하려면:"
echo "  systemctl --user stop myagent-telegram"
echo "  systemctl --user disable myagent-telegram"
