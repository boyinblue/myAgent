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


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _cleanup_residual_dashboard_processes() -> int:
    """PID 파일 기반 종료 외에 남은 대시보드/터널 프로세스를 정리합니다."""
    killed = 0

    if os.name == 'nt':
        # start.py / start_remote.py 잔여 python 프로세스 정리
        ps_cmd = (
            "$targets = Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'web-dashboard[\\\\/]start_remote.py|web-dashboard[\\\\/]start.py' }; "
            "$count = 0; foreach ($p in $targets) { try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; $count++ } catch {} }; "
            "Write-Output $count"
        )
        try:
            proc = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            extra = int((proc.stdout or '0').strip() or '0')
            killed += max(0, extra)
        except Exception:
            pass

        # ngrok 잔여 프로세스 정리
        try:
            ngrok_kill = subprocess.run(
                ['taskkill', '/F', '/IM', 'ngrok.exe'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            output = f"{ngrok_kill.stdout or ''} {ngrok_kill.stderr or ''}".lower()
            if 'success' in output or '성공' in output:
                killed += 1
        except Exception:
            pass
    else:
        try:
            subprocess.run(['pkill', '-f', 'web-dashboard/start_remote.py'], check=False, timeout=5)
            subprocess.run(['pkill', '-f', 'web-dashboard/start.py'], check=False, timeout=5)
            subprocess.run(['pkill', '-f', 'ngrok'], check=False, timeout=5)
        except Exception:
            pass

    return killed

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
    
    precheck_warning = ""

    # 이미 실행 중인지 확인 (PID 파일)
    pid_file = web_dashboard_dir / '.dashboard.pid'
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # 프로세스가 실행 중이면 재시작 시도
            if _pid_exists(pid):
                stop_result = stop_dashboard()
                if not stop_result.get('success'):
                    precheck_warning = f"⚠️ 기존 프로세스 종료 경고: {stop_result.get('message', '')}\n\n"
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
        'message': f'''{precheck_warning}🚀 웹 대시보드를 시작했습니다.

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

        if not _pid_exists(pid):
            pid_file.unlink(missing_ok=True)
            return {
                'success': True,
                'message': f'ℹ️ 기존 PID 파일만 정리했습니다. (PID: {pid})'
            }
        
        # 프로세스 종료
        try:
            # Windows와 Unix 모두 지원
            if os.name == 'nt':  # Windows
                result = subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(pid)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    detail = f"{result.stdout or ''} {result.stderr or ''}".lower()
                    pid_file.unlink(missing_ok=True)
                    if "not found" in detail or "no running instance" in detail or "cannot find" in detail:
                        return {
                            'success': True,
                            'message': f'ℹ️ 이미 종료된 프로세스였습니다. PID 파일만 정리했습니다. (PID: {pid})'
                        }
                    return {
                        'success': False,
                        'message': f'⚠️ 프로세스 종료 실패(PID: {pid}): {(result.stdout or result.stderr or "unknown error").strip()}'
                    }
            else:  # Unix-like
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            
            pid_file.unlink(missing_ok=True)
            
            return {
                'success': True,
                'message': f'✅ 웹 대시보드를 종료했습니다. (PID: {pid})'
            }
        except (OSError, subprocess.CalledProcessError) as e:
            pid_file.unlink(missing_ok=True)  # PID 파일은 제거
            fallback_killed = _cleanup_residual_dashboard_processes()
            if fallback_killed > 0:
                return {
                    'success': True,
                    'message': f'⚠️ PID 기반 종료는 실패했지만 잔여 프로세스 {fallback_killed}개를 강제 정리했습니다.'
                }
            return {
                'success': False,
                'message': f'⚠️ 프로세스 종료 실패: {e}\nPID 파일은 삭제되었습니다.'
            }
    except (ValueError, FileNotFoundError) as e:
        pid_file.unlink(missing_ok=True)
        fallback_killed = _cleanup_residual_dashboard_processes()
        if fallback_killed > 0:
            return {
                'success': True,
                'message': f'⚠️ PID 파일 오류가 있었지만 잔여 프로세스 {fallback_killed}개를 정리했습니다.'
            }
        return {
            'success': False,
            'message': f'⚠️ 잘못된 PID 파일: {e}'
        }


def get_dashboard_status():
    """웹 대시보드 상태 조회"""
    pid_file = web_dashboard_dir / '.dashboard.pid'

    if not pid_file.exists():
        return {
            'success': True,
            'running': False,
            'message': 'ℹ️ 웹 대시보드가 실행 중이 아닙니다.'
        }

    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, FileNotFoundError) as e:
        pid_file.unlink(missing_ok=True)
        return {
            'success': False,
            'running': False,
            'message': f'⚠️ 잘못된 PID 파일: {e}'
        }

    if _pid_exists(pid):
        return {
            'success': True,
            'running': True,
            'pid': pid,
            'message': f'✅ 웹 대시보드 실행 중입니다. (PID: {pid})'
        }

    pid_file.unlink(missing_ok=True)
    return {
        'success': True,
        'running': False,
        'message': f'ℹ️ 실행 중인 프로세스가 없어 PID 파일을 정리했습니다. (PID: {pid})'
    }

if __name__ == '__main__':
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python dashboard.py [launch|stop|status]")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action == 'launch':
        result = launch_dashboard()
    elif action == 'stop':
        result = stop_dashboard()
    elif action == 'status':
        result = get_dashboard_status()
    else:
        result = {'success': False, 'message': f'Unknown action: {action}'}
    
    print(json.dumps(result, ensure_ascii=True, indent=2))
