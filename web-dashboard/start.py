#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""웹 대시보드 로컬 실행 스크립트"""

import os
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

    dashboard_app.app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=True)
