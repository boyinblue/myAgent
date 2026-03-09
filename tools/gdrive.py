import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def get_gdrive_service():
    """
    구글 드라이브 API 서비스 객체를 초기화합니다.
    인증 파일(credentials.json)이 필요합니다.
    """
    SERVICE_ACCOUNT_FILE = 'credentials.json'
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"❌ 에러: 인증 파일({SERVICE_ACCOUNT_FILE})이 존재하지 않습니다.")
        return None

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    return build('drive', 'v3', credentials=creds)


def list_files(service, folder_id='root', indent=0):
    """
    지정한 폴더 내의 파일과 디렉토리를 재귀적으로 탐색합니다.
    """
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()

        items = results.get('files', [])

        if not items and indent == 0:
            print('검색 결과가 없습니다.')
            return

        for item in items:
            prefix = "  " * indent
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                print(f"{prefix}📁 {item['name']} (ID: {item['id']})")
                list_files(service, item['id'], indent + 1)
            else:
                print(f"{prefix}📄 {item['name']} (ID: {item['id']})")

    except HttpError as error:
        print(f"❌ API 에러 발생: {error}")


if __name__ == "__main__":
    print("📡 구글 드라이브 연결 시도 중...")
    service = get_gdrive_service()

    if service:
        print("\n--- [ 구글 드라이브 파일 구조 ] ---")
        list_files(service, folder_id='root')
        print("\n✅ 탐색 완료")