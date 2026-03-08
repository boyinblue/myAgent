#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""웹 대시보드 원격 실행 스크립트 (ngrok + 텔레그램 URL 전송)"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

web_dashboard_dir = Path(__file__).parent
if str(web_dashboard_dir) not in sys.path:
    sys.path.insert(0, str(web_dashboard_dir))

content_crawler = project_root / 'content-crawler'
if str(content_crawler) not in sys.path:
    sys.path.insert(0, str(content_crawler))


if __name__ == '__main__':
    os.environ['DASHBOARD_LOCAL_MODE'] = '0'
    import ngrok_manager
    ngrok_manager.main()
