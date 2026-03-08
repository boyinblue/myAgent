#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""웹 대시보드 실행 스크립트"""

import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if __name__ == '__main__':
    # ngrok_manager를 패키지로 import
    from web_dashboard import ngrok_manager
    ngrok_manager.main()
