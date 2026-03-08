#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""웹 대시보드 런처 스킬

텔레그램 봇에서 웹 대시보드를 요청하면 ngrok 터널을 생성하고
일회용 접속 URL을 전송합니다.
"""

import os
import sys
import subprocess
import signal
from pathlib import Path

project_root = Path(__file__).parent.parent
web_dashboard_dir = project_root / "web-dashboard"

def launch_dashboard():
    """웹 대시보드 실행"""
    
    # ngrok 설치 확인
    try:
        subprocess.run(['ngrok', 'version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {
            'success': False,
            'message': '❌ ngrok이 설치되어 있지 않습니다.\n\n설치: https://ngrok.com/download'
        }
    
    # 이미 실행 중인지 확인 (PID 파일)
    pid_file = web_dashboard_dir / '.dashboard.pid'
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # 프로세스가 실행 중인지 확인
            os.kill(pid, 0)
            return {
                'success': False,
                'message': '⚠️ 웹 대시보드가 이미 실행 중입니다.\n종료하려면: stop_dashboard 명령을 사용하세요.'
            }
        except (OSError, ValueError):
            # 프로세스가 없으면 PID 파일 삭제
            pid_file.unlink()
    
    # 백그라운드에서 대시보드 실행
    start_script = web_dashboard_dir / 'start.py'
    
    if not start_script.exists():
        return {
            'success': False,
            'message': '❌ start.py 파일을 찾을 수 없습니다.'
        }
    
    # 백그라운드 프로세스로 실행
    process = subprocess.Popen(
        [sys.executable, str(start_script)],
        cwd=str(web_dashboard_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True  # 세션 분리
    )
    
    # PID 저장
    pid_file.write_text(str(process.pid))
    
    return {
        'success': True,
        'message': f'''🚀 웹 대시보드를 시작했습니다.

⏳ 약 5초 후 접속 URL이 전송됩니다.
📱 텔레그램에서 URL을 받으면 클릭하세요.

ℹ️ 백그라운드에서 실행 중입니다 (PID: {process.pid})
🛑 종료하려면: stop_dashboard 명령 사용'''
    }

def stop_dashboard():
    """웹 대시보드 종료"""
    pid_file = web_dashboard_dir / '.dashboard.pid'
    
    if not pid_file.exists():
        return {
            'success': False,
            'message': '⚠️ 실행 중인 대시보드가 없습니다.'
        }
    
    try:
        pid = int(pid_file.read_text().strip())
        
        # 프로세스 종료
        try:
            # Windows와 Unix 모두 지원
            if os.name == 'nt':  # Windows
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], check=True)
            else:  # Unix-like
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            
            pid_file.unlink()
            
            return {
                'success': True,
                'message': f'✅ 웹 대시보드를 종료했습니다. (PID: {pid})'
            }
        except (OSError, subprocess.CalledProcessError) as e:
            pid_file.unlink()  # PID 파일은 제거
            return {
                'success': False,
                'message': f'⚠️ 프로세스 종료 실패: {e}\nPID 파일은 삭제되었습니다.'
            }
    except (ValueError, FileNotFoundError) as e:
        pid_file.unlink()
        return {
            'success': False,
            'message': f'⚠️ 잘못된 PID 파일: {e}'
        }

if __name__ == '__main__':
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python web_dashboard_launcher.py [launch|stop]")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action == 'launch':
        result = launch_dashboard()
    elif action == 'stop':
        result = stop_dashboard()
    else:
        result = {'success': False, 'message': f'Unknown action: {action}'}
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
