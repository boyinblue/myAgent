import os
import pickle
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

# .env 파일 로드
load_dotenv()

# 환경 변수에서 설정값 가져오기
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY")

# 권한 범위 (파일 업로드 및 관리)
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_gdrive_service():
    creds = None
    # 이전에 인증한 토큰이 있으면 로드
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # 인증 정보가 없거나 유효하지 않으면 로그인창 띄움
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)

def upload_files(local_directory, folder_id=None):
    service = get_gdrive_service()

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
            response = service.files().list(q=query, fields="files(id)").execute()
            files = response.get('files', [])

            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            media = MediaFileUpload(file_path, resumable=True)

            if len(files) > 1:
                for file in files:
                    service.files().delete(fileId=file['id']).execute()
                    print(f"  [!] 중복 파일 삭제: {filename} ({file['id']})")

            file_metadata = {'name': filename, 'parents': [folder_id]}
            file = service.files().create(body=file_metadata, media_body=media).execute()
            print(f"  ✅ 완료! File ID: {file.get('id')}")
        
        else:
            upload_files(file_path, folder_id)  # 하위 폴더 재귀적으로 처리

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