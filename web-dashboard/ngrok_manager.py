# -*- coding: utf-8 -*-
"""ngrok 터널 관리자 및 텔레그램 알림"""

import os
import sys
import time
import subprocess
import requests
import secrets
from pathlib import Path
from datetime import datetime, timedelta
import shutil

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.telegram_notifier import TelegramNotifier

# 일회용 토큰 저장소 (메모리, ngrok_manager와 app.py가 공유)
active_tokens = {}

def find_ngrok_exe():
    """ngrok 실행 파일 경로 찾기"""
    # 1. shutil.which로 PATH에서 찾기
    ngrok_path = shutil.which('ngrok')
    if ngrok_path:
        return ngrok_path
    
    # 2. 설치된 경로들에서 찾기 (Windows)
    possible_paths = [
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'ngrok' / 'ngrok.exe',
        Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / 'ngrok' / 'ngrok.exe',
        Path('C:\\Program Files (x86)') / 'ngrok' / 'ngrok.exe',
        Path(os.environ.get('USERPROFILE', '')) / 'ngrok' / 'ngrok.exe',
    ]
    
    for path in possible_paths:
        if path.exists():
            return str(path)
    
    return None

def generate_access_token(expires_minutes=120):
    """일회용 접속 토큰 생성"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(minutes=expires_minutes)
    active_tokens[token] = {
        'created_at': datetime.now(),
        'expires_at': expires_at,
        'used': False
    }
    return token

class NgrokManager:
    """ngrok 터널 관리"""
    
    def __init__(self):
        self.process = None
        self.public_url = None
        self.notifier = TelegramNotifier()
    
    def start_tunnel(self, port=5000):
        """ngrok 터널 시작"""
        print(f"[*] ngrok 터널 시작 (포트: {port})...")
        
        # ngrok 실행 파일 찾기
        ngrok_exe = find_ngrok_exe()
        if not ngrok_exe:
            print("[!] ngrok을 찾을 수 없습니다.")
            print("[!] 설치해주세요: https://ngrok.com/download")
            return None
        
        print(f"[*] ngrok 경로: {ngrok_exe}")
        
        # ngrok 프로세스 시작
        try:
            self.process = subprocess.Popen(
                [ngrok_exe, 'http', str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except Exception as e:
            print(f"[!] ngrok 실행 실패: {e}")
            return None
        
        # ngrok API가 준비될 때까지 대기
        time.sleep(3)
        
        # ngrok URL 가져오기
        self.public_url = self._get_public_url()
        
        if self.public_url:
            print(f"[+] ngrok 터널 생성됨: {self.public_url}")
            return self.public_url
        else:
            print("[!] ngrok URL을 가져올 수 없습니다.")
            return None
    
    def _get_public_url(self):
        """ngrok 로컬 API에서 public URL 가져오기"""
        try:
            resp = requests.get('http://localhost:4040/api/tunnels', timeout=5)
            resp.raise_for_status()
            tunnels = resp.json().get('tunnels', [])
            
            if not tunnels:
                return None
            
            # HTTPS URL 우선
            for tunnel in tunnels:
                if tunnel.get('proto') == 'https':
                    return tunnel.get('public_url')
            
            # 없으면 첫 번째 URL
            return tunnels[0].get('public_url')
        
        except Exception as e:
            print(f"[!] ngrok API 오류: {e}")
            return None
    
    def send_access_url(self, expires_minutes=120):
        """일회용 토큰이 포함된 접속 URL을 텔레그램으로 전송"""
        if not self.public_url:
            print("[!] ngrok URL이 없습니다.")
            return False
        
        # 일회용 토큰 생성
        token = generate_access_token(expires_minutes=expires_minutes)
        
        # 접속 URL
        access_url = f"{self.public_url}/?token={token}"
        
        # 텔레그램 메시지
        message = f"""🌐 **웹 대시보드 접속 URL**

{access_url}

⚠️ **보안 안내**
- 일회용 URL입니다 (한 번만 사용 가능)
- {expires_minutes}분 후 자동 만료됩니다
- URL을 타인과 공유하지 마세요

📊 **대시보드 기능**
• 아카이브 포스트 검색/조회
• 플랫폼별 통계 및 차트
• 크롤링 수동 트리거
• 최근 크롤링 로그

⏰ ngrok 세션은 최대 2시간 유지됩니다."""
        
        # 텔레그램 전송
        success = self.notifier.send_message(message)
        
        if success:
            print(f"[+] 텔레그램으로 접속 URL 전송 완료")
            print(f"[+] 토큰: {token[:16]}...")
        else:
            print(f"[!] 텔레그램 전송 실패")
            print(f"[!] 수동 접속 URL: {access_url}")
        
        return success
    
    def stop_tunnel(self):
        """ngrok 터널 종료"""
        if self.process:
            print("[*] ngrok 터널 종료 중...")
            self.process.terminate()
            self.process.wait(timeout=5)
            print("[+] ngrok 터널 종료됨")

def main():
    """메인 함수 - Flask 앱과 ngrok 동시 실행"""
    import threading
    
    # app.py를 여기서 import (순환 참조 방지)
    from web_dashboard import app as flask_app
    
    # Flask 앱을 별도 스레드에서 실행
    def run_flask():
        flask_app.app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Flask 시작 대기
    time.sleep(2)
    
    # ngrok 터널 시작
    manager = NgrokManager()
    url = manager.start_tunnel(port=5000)
    
    if url:
        # 텔레그램으로 접속 URL 전송
        manager.send_access_url(expires_minutes=120)
        
        print("\n" + "="*60)
        print("웹 대시보드가 시작되었습니다.")
        print("Ctrl+C를 눌러 종료하세요.")
        print("="*60 + "\n")
        
        # 메인 스레드 유지
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[*] 종료 신호 받음...")
            manager.stop_tunnel()
    else:
        print("[!] ngrok 터널을 시작할 수 없습니다.")

if __name__ == '__main__':
    main()
