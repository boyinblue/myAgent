#!/usr/bin/env bash
set -euo pipefail

REMOVE_RUNNER=false
REMOVE_CACHE=false
FORCE=false

for arg in "$@"; do
  case "$arg" in
    --remove-runner) REMOVE_RUNNER=true ;;
    --remove-cache)  REMOVE_CACHE=true ;;
    --force|-y)      FORCE=true ;;
    *)
      echo "알 수 없는 옵션: $arg"
      echo "사용법: $0 [--remove-runner] [--remove-cache] [--force]"
      exit 1
      ;;
  esac
done

confirm() {
  local prompt="$1"
  if [ "$FORCE" = true ]; then
    return 0
  fi
  read -r -p "$prompt [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *) return 1 ;;
  esac
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== [1/4] myAgent systemd 서비스 중지 및 비활성화 ==="
mapfile -t units < <(systemctl list-unit-files --type=service --no-legend 2>/dev/null | awk '{print $1}' | grep -E '^myagent-.*\.service$' || true)

for unit in "${units[@]}"; do
  if confirm "systemd 서비스 '$unit' 을(를) 중지하고 제거할까요?"; then
    sudo systemctl stop "$unit" || true
    sudo systemctl disable "$unit" || true
    if [ -f "/etc/systemd/system/$unit" ]; then
      sudo rm -f "/etc/systemd/system/$unit"
    fi
    echo "제거 완료: $unit"
  else
    echo "건너뜀: $unit"
  fi
done

if [ "${#units[@]}" -gt 0 ]; then
  sudo systemctl daemon-reload
fi

echo ""
echo "=== [2/4] GitHub Actions 셀프 호스팅 러너 서비스 점검 ==="
if [ "$REMOVE_RUNNER" = true ] && [ -d "$HOME/actions-runner" ]; then
  if confirm "기존 '$HOME/actions-runner' 서비스를 중지/제거할까요?"; then
    (
      cd "$HOME/actions-runner"
      if [ -f "./svc.sh" ]; then
        sudo ./svc.sh stop || true
        sudo ./svc.sh uninstall || true
      fi
    )
    echo "러너 서비스 해제 완료 (폴더는 유지됨)"
  fi
else
  echo "러너 서비스 정리는 건너뛰었습니다. (--remove-runner 옵션으로 활성화 가능)"
fi

echo ""
echo "=== [3/4] 남아 있는 myAgent 관련 프로세스 종료 ==="
pids="$(pgrep -f "$PROJECT_ROOT" || true)"
if [ -n "$pids" ]; then
  echo "감지된 PID: $pids"
  if confirm "위 관련 프로세스를 종료할까요?"; then
    pkill -f "$PROJECT_ROOT" || true
    echo "프로세스 종료 신호 전송 완료"
  fi
else
  echo "실행 중인 잔여 프로세스가 없습니다."
fi

echo ""
echo "=== [4/4] 선택적 캐시 정리 ==="
if [ "$REMOVE_CACHE" = true ]; then
  find "$PROJECT_ROOT" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
  rm -rf "$PROJECT_ROOT/.pytest_cache" "$PROJECT_ROOT/.ruff_cache" 2>/dev/null || true
  echo "__pycache__ 및 테스트/린트 캐시 정리 완료"
else
  echo "캐시 삭제는 생략되었습니다. (--remove-cache 옵션으로 활성화 가능)"
fi

echo ""
echo "정리 작업이 완료되었습니다."
