#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""웹 대시보드 로컬 실행 스크립트"""

import os
import socket
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# web-dashboard 폴더를 sys.path에 추가
web_dashboard_dir = Path(__file__).parent
if str(web_dashboard_dir) not in sys.path:
    sys.path.insert(0, str(web_dashboard_dir))

# content-crawler를 sys.path에 추가 (telegram_notifier 접근용)
content_crawler = project_root / 'content-crawler'
if str(content_crawler) not in sys.path:
    sys.path.insert(0, str(content_crawler))


def get_lan_ip() -> str:
    """Return the preferred LAN address without sending network traffic."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('8.8.8.8', 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return '127.0.0.1'
    finally:
        sock.close()

if __name__ == '__main__':
    # 프로젝트 루트의 .env 로드
    try:
        from dotenv import load_dotenv
        load_dotenv(project_root / '.env')
    except ImportError:
        pass  # python-dotenv 미설치 시 무시

    # 로컬 모드: 토큰 없이 localhost 대시보드 접근 허용
    os.environ['DASHBOARD_LOCAL_MODE'] = '1'

    import app as dashboard_app
    from ngrok_manager import generate_access_token

    dashboard_port = int(os.getenv('DASHBOARD_LOCAL_PORT', '5000'))
    token_minutes = int(os.getenv('DASHBOARD_LAN_TOKEN_MINUTES', '720'))
    token_max_uses = int(os.getenv('DASHBOARD_LAN_TOKEN_MAX_USES', '20'))
    lan_token = generate_access_token(
        expires_minutes=token_minutes,
        max_uses=token_max_uses,
    )
    lan_url = f'http://{get_lan_ip()}:{dashboard_port}/?token={lan_token}'
    
    # DB 마이그레이션 실행
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        try:
            from archive_manager import ArchiveManager
            _archive_manager = ArchiveManager()
            print("[*] DB 마이그레이션 완료")
        except Exception as e:
            print(f"[!] DB 마이그레이션 실패: {e}")
    
    # WERKZEUG_RUN_MAIN이 설정된 경우 reloader가 재시작한 자식 프로세스이므로 건너뜀
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        try:
            auto_result = dashboard_app.auto_trigger_crawl_if_due()
            print(f"[*] startup auto-crawl check: {auto_result}")
        except Exception as exc:
            print(f"[!] startup auto-crawl check failed: {exc}")

    print(f'[*] 로컬 접속: http://127.0.0.1:{dashboard_port}')
    print(f'[*] LAN 접속 ({token_minutes}분, 최대 {token_max_uses}회 인증): {lan_url}')
    dashboard_app.app.run(
        host='0.0.0.0',
        port=dashboard_port,
        debug=False,
        use_reloader=False,
    )
