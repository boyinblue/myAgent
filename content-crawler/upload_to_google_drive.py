import os
import sys
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Windows 콘솔 UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# .env 파일 로드
load_dotenv(os.path.join('..', '.env'))

# 권한 범위 (파일 업로드 및 관리)
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_gdrive_service():
    """OAuth2 Desktop Credentials로 Google Drive API 인증"""
    CREDENTIAL_FILE = os.path.join('..', 'google_oauth2_credentials.json')
    TOKEN_FILE = os.path.join('..', 'google_oauth2_upload_token.json')
    
    if not os.path.exists(CREDENTIAL_FILE):
        print("❌ google_oauth2_credentials.json 파일을 찾을 수 없습니다.")
        print("프로젝트 루트에 OAuth2 Desktop JSON 파일을 저장하세요.")
        return None
    
    try:
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIAL_FILE, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(TOKEN_FILE, 'w', encoding='utf-8') as token:
                token.write(creds.to_json())

        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ 인증 실패: {e}")
        return None

def upload_files(local_directory, folder_id=None, service=None):
    if service is None:
        service = get_gdrive_service()
    
    if not service:
        print("❌ Google Drive 서비스 초기화 실패")
        return

    print(f"")
    print(f"📁 '{local_directory}' 디렉토리의 파일을 구글 드라이브에 업로드합니다...")

    for filename in os.listdir(local_directory):
        file_path = os.path.join(local_directory, filename)
        
        # 폴더 제외, 파일만 업로드
        if os.path.isfile(file_path):
            print(f"")
            print(f"  [*] 파일명 : {filename}")

            # 1. 같은 이름의 파일이 있는지 검색
            query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
            response = service.files().list(
                q=query, 
                fields="files(id,name,capabilities/canEdit)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            files = response.get('files', [])

            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            media = MediaFileUpload(file_path, resumable=True)

            if len(files) > 1:
                for file in files:
                    can_edit = bool((file.get('capabilities') or {}).get('canEdit'))
                    if not can_edit:
                        print(f"  [!] 삭제 권한 없음, 건너뜀: {filename} ({file['id']})")
                        continue
                    try:
                        service.files().delete(fileId=file['id'], supportsAllDrives=True).execute()
                        print(f"  [!] 중복 파일 삭제: {filename} ({file['id']})")
                    except HttpError as e:
                        if 'insufficientFilePermissions' in str(e):
                            print(f"  [!] 삭제 권한 부족, 건너뜀: {filename} ({file['id']})")
                            continue
                        raise

            file_metadata = {'name': filename, 'parents': [folder_id]}
            try:
                file = service.files().create(
                    body=file_metadata, 
                    media_body=media,
                    supportsAllDrives=True
                ).execute()
                print(f"  ✅ 완료! File ID: {file.get('id')}")
            except HttpError as e:
                if 'insufficientFilePermissions' in str(e):
                    print("  ❌ 업로드 권한이 부족합니다. 공유 드라이브에서 '콘텐츠 관리자' 이상 권한이 필요합니다.")
                    continue
                raise
        
        else:
            upload_files(file_path, folder_id, service=service)  # 하위 폴더 재귀적으로 처리

if __name__ == '__main__':
    # 업로드할 로컬 경로 (예: C:/AI_Skills/)
    LOCAL_DIR = '../archive' 
    # 구글 드라이브 내 특정 폴더에 넣고 싶다면 폴더 ID 입력 (선택사항)
    TARGET_FOLDER_ID = "1w0WOLRsWPhOME-JHtN09zUN7813akL5K"

    if not os.path.exists(LOCAL_DIR):
        os.makedirs(LOCAL_DIR)
        print(f"📂 {LOCAL_DIR} 디렉토리가 없어 생성했습니다. 파일을 넣고 다시 실행하세요.")
    else:
        upload_files(LOCAL_DIR, TARGET_FOLDER_ID)