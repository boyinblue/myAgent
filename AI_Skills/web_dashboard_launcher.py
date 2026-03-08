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
import shutil
from pathlib import Path

project_root = Path(__file__).parent.parent
web_dashboard_dir = project_root / "web-dashboard"

def find_ngrok_exe():
    """ngrok 실행 파일 찾기"""
    # 1) PATH에서 검색
    ngrok_path = shutil.which('ngrok')
    if ngrok_path and Path(ngrok_path).exists():
        return ngrok_path

    # 2) Windows where 명령 fallback
    if os.name == 'nt':
        try:
            proc = subprocess.run(
                ['where', 'ngrok'],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.splitlines():
                    candidate = line.strip()
                    if candidate and Path(candidate).exists():
                        return candidate
        except Exception:
            pass

    # 3) 일반 설치 경로 검색 (환경변수 + 홈 디렉토리 기반)
    home = Path.home()
    possible_paths = [
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'ngrok' / ('ngrok.exe' if os.name == 'nt' else 'ngrok'),
        home / 'AppData' / 'Local' / 'Programs' / 'ngrok' / 'ngrok.exe',
        Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / 'ngrok' / 'ngrok.exe',
        Path('C:\\Program Files (x86)') / 'ngrok' / 'ngrok.exe',
        Path(os.environ.get('USERPROFILE', str(home))) / 'ngrok' / ('ngrok.exe' if os.name == 'nt' else 'ngrok'),
        home / 'ngrok' / ('ngrok.exe' if os.name == 'nt' else 'ngrok'),
    ]

    for path in possible_paths:
        try:
            if path and path.exists() and path.is_file():
                return str(path)
        except Exception:
            continue

    return None

def launch_dashboard():
    """웹 대시보드 실행"""
    
    # ngrok 설치 확인
    ngrok_exe = find_ngrok_exe()
    if not ngrok_exe:
        return {
            'success': False,
            'message': '❌ <b>ngrok이 설치되어 있지 않습니다.</b>\n\n설치: https://ngrok.com/download'
        }
    
    # ngrok 정상 작동 확인
    try:
        result = subprocess.run([ngrok_exe, 'version'], capture_output=True, text=True, check=True, timeout=5)
    except subprocess.CalledProcessError as e:
        # ngrok 인증 오류인 경우
        stderr = e.stderr if e.stderr else ""
        stdout = e.stdout if e.stdout else ""
        combined = f"{stderr} {stdout}"
        
        if 'authentication failed' in combined or 'authtoken' in combined:
            return {
                'success': False,
                'message': '''❌ <b>ngrok 인증 오류</b>

ngrok v3+ 에서는 계정 및 authtoken 이 필요합니다.

<b>설정 방법:</b>
1️⃣ https://ngrok.com/signup 에서 가입
2️⃣ https://dashboard.ngrok.com/get-started/your-authtoken 에서 authtoken 복사  
3️⃣ 터미널에서 실행:
<code>ngrok config add-authtoken YOUR_AUTHTOKEN</code>

설정 후 다시 시도해주세요.'''
            }
        return {
            'success': False,
            'message': f'❌ ngrok 실행 오류\n\n설치를 다시 확인해주세요.\n오류: {e}'
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'message': '❌ ngrok 타임아웃 오류\n\n설치를 확인한 후 다시 시도해주세요.'
        }
    
    # 이미 실행 중인지 확인 (PID 파일)
    pid_file = web_dashboard_dir / '.dashboard.pid'
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # 프로세스가 실행 중인지 확인
            os.kill(pid, 0)
            # 실행 중이면 재시작하여 URL을 다시 전송
            stop_result = stop_dashboard()
            if not stop_result.get('success'):
                return {
                    'success': False,
                    'message': '⚠️ 기존 대시보드 종료에 실패했습니다. 잠시 후 다시 시도해주세요.'
                }
        except (OSError, ValueError):
            # 프로세스가 없으면 PID 파일 삭제
            pid_file.unlink()
    
    # 백그라운드에서 원격(텔레그램) 대시보드 실행
    start_script = web_dashboard_dir / 'start_remote.py'
    
    if not start_script.exists():
        return {
            'success': False,
            'message': '❌ start_remote.py 파일을 찾을 수 없습니다.'
        }
    
    # 프로젝트 루트에서 실행하도록 cwd 설정
    project_root = web_dashboard_dir.parent
    
    # 백그라운드 프로세스로 실행
    process = subprocess.Popen(
        [sys.executable, str(start_script)],
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True  # 세션 분리
    )

    # 초기 부팅 실패(포트 충돌/ngrok 오류 등) 조기 감지
    import time
    time.sleep(2)
    if process.poll() is not None:
        stdout, stderr = process.communicate(timeout=2)
        error_text = (stderr or stdout or 'unknown error').strip()
        return {
            'success': False,
            'message': f'❌ 웹 대시보드 시작 실패\n\n{error_text[:500]}'
        }
    
    # PID 저장
    pid_file.write_text(str(process.pid))
    
    return {
        'success': True,
        'message': f'''🚀 웹 대시보드를 시작했습니다.

⏳ 약 5초 후 접속 URL이 전송됩니다.
📱 텔레그램에서 URL을 받으면 클릭하세요.

ℹ️ 로컬 대시보드와 분리된 원격 모드로 실행됩니다.

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
