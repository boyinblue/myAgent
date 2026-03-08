#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""웹 대시보드 실행 스크립트"""

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
    # ngrok_manager를 직접 import
    import ngrok_manager
    ngrok_manager.main()
