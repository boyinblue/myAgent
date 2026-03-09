import gkeepapi
import os
import json
import dotenv
import sys
import io
import platform
from pathlib import Path

# Windows에서 UTF-8 이모지 출력을 위한 설정
if platform.system() == 'Windows':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def get_token_path():
    """토큰 저장 경로 반환"""
    return Path(__file__).parent / ".keep_token"

def save_token(keep):
    """인증 토큰 저장"""
    try:
        token = keep.getMasterToken()
        token_path = get_token_path()
        with open(token_path, 'w') as f:
            json.dump({'token': token}, f)
        print(f"✅ 토큰 저장 완료: {token_path}")
        return True
    except Exception as e:
        print(f"⚠️  토큰 저장 실패: {e}")
        return False

def load_token(keep, email):
    """저장된 토큰으로 로그인 시도"""
    token_path = get_token_path()
    if not token_path.exists():
        return False
    
    try:
        with open(token_path, 'r') as f:
            data = json.load(f)
            token = data.get('token')
        
        if token:
            print("🔑 저장된 토큰으로 로그인 시도 중...")
            keep.resume(email, token)
            keep.sync()
            print("✅ 토큰 로그인 성공")
            return True
    except Exception as e:
        print(f"⚠️  토큰 로그인 실패: {e}")
        # 토큰이 만료되었을 수 있으므로 삭제
        try:
            token_path.unlink()
        except:
            pass
    
    return False

def fetch_keep_notes(email, app_password):
    keep = gkeepapi.Keep()
    
    # 1. 저장된 토큰으로 로그인 시도
    if not load_token(keep, email):
        # 2. 토큰 로그인 실패 시 앱 비밀번호로 로그인
        print(f"🔐 앱 비밀번호로 로그인 시도 중... ({email})")
        
        try:
            # authenticate 메서드 사용 (login은 deprecated)
            keep.authenticate(email, app_password)
            print("✅ 로그인 성공!")
            save_token(keep)
            
        except gkeepapi.exception.LoginException as e:
            print(f"❌ 인증 실패: {e}")
            print("")
            print("⚠️  Google Keep API 접근이 차단되었을 수 있습니다.")
            print("")
            print("📌 알려진 문제:")
            print("   Google이 2022년부터 '보안 수준이 낮은 앱' 액세스를 차단했습니다.")
            print("   gkeepapi는 비공식 라이브러리로, 작동하지 않을 수 있습니다.")
            print("")
            print("🔧 대안:")
            print("   1. Google Takeout으로 Keep 데이터 내보내기")
            print("      https://takeout.google.com/settings/takeout")
            print("   2. Notion, Obsidian 등 다른 메모 앱 사용")
            print("   3. Keep 웹 UI를 직접 사용")
            return
        except Exception as e:
            print(f"❌ 예상치 못한 오류: {e}")
            return

    # 모든 메모 가져오기
    try:
        notes = list(keep.all())
        print(f"\n📚 총 {len(notes)}개의 메모를 찾았습니다.\n")
        
        for idx, note in enumerate(notes, 1):
            print(f"{idx}. 제목: {note.title or '(제목 없음)'}")
            text = note.text[:100] + "..." if len(note.text) > 100 else note.text
            print(f"   내용: {text}")
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ 메모 가져오기 실패: {e}")

if __name__ == "__main__":
    # .env 파일에서 이메일과 앱 비밀번호를 읽어옵니다.
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    dotenv.load_dotenv(dotenv_path)

    EMAIL = os.getenv("GOOGLE_EMAIL")
    APP_PASSWORD = os.getenv("GOOGLE_APP_PASSWORD")

    if not EMAIL or not APP_PASSWORD:
        print("❌ GOOGLE_EMAIL과 GOOGLE_APP_PASSWORD 환경 변수가 설정되어 있지 않습니다.")
        print("")
        print("📝 Google 앱 비밀번호 생성 방법:")
        print("   1. https://myaccount.google.com/apppasswords 접속")
        print("   2. '앱 비밀번호 만들기' 클릭")
        print("   3. 앱 이름 입력 (예: MyAgent Keep)")
        print("   4. 생성된 16자리 비밀번호를 .env 파일의 GOOGLE_APP_PASSWORD에 입력")
        print("")
        print("⚠️  주의: 일반 비밀번호가 아닌 앱 비밀번호를 사용해야 합니다.")
        print("")

        # 사용자 입력을 통해 이메일과 앱 비밀번호를 받을 수도 있습니다.
        EMAIL = input("이메일을 입력하세요: ")
        APP_PASSWORD = input("앱 비밀번호를 입력하세요 (16자리): ")

    fetch_keep_notes(EMAIL, APP_PASSWORD)