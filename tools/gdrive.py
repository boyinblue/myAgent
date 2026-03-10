#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Windows 콘솔 UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def get_gdrive_service():
    """
    구글 드라이브 API 서비스 객체를 초기화합니다.
    인증 파일(credentials.json)이 필요합니다 (서비스 계정 타입).
    """
    SERVICE_ACCOUNT_FILE = 'credentials.json'
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print("❌ 구글 드라이브 API 설정이 필요합니다.\n")
        print("credentials.json 파일을 생성하려면:")
        print("  1. GDRIVE_SETUP.md 파일 참고")
        print("  2. Google Cloud Console에서 '서비스 계정' 타입의 JSON 키 생성")
        print("  3. 다운받은 JSON 파일을 credentials.json으로 프로젝트 루트에 저장")
        print("\n⚠️  중요: 'installed' 응용 프로그램이 아닌 '서비스 계정' 타입이어야 합니다!")
        return None

    try:
        # 파일 로드하여 형식 확인
        import json
        with open(SERVICE_ACCOUNT_FILE, 'r') as f:
            cred_data = json.load(f)
        
        # OAuth 디바이스 타입 감지
        if "installed" in cred_data:
            print("❌ 잘못된 credentials 타입입니다!")
            print("\n현재: OAuth 2.0 Desktop 애플리케이션")
            print("필요: 서비스 계정\n")
            print("올바른 설정 방법:")
            print("  1. GDRIVE_SETUP.md 문서 확인")
            print("  2. Google Cloud Console > API 및 서비스 > 사용자 인증정보")
            print("  3. '서비스 계정' 생성 및 JSON 키 다운로드")
            print("  4. 다운로드한 파일을 credentials.json으로 저장")
            return None
        
        # 서비스 계정 검증
        if "type" in cred_data and cred_data["type"] != "service_account":
            print(f"❌ 지원하지 않는 credentials 타입: {cred_data['type']}")
            print("서비스 계정 타입만 지원합니다.")
            return None

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds)
    except json.JSONDecodeError:
        print("❌ credentials.json 파일이 유효한 JSON이 아닙니다.")
        return None
    except Exception as e:
        print(f"❌ 구글 드라이브 인증 실패: {e}")
        return None


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