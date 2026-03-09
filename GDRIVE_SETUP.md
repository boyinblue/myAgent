# Google Drive API 설정 가이드

`/gdrive` 명령어를 사용하려면 Google Cloud에서 서비스 계정 키를 발급받아야 합니다.

## 📋 사전 준비

- Google 계정
- Google Cloud Console 접근 권한

## 🔧 설정 단계

### 1. Google Cloud Console 접속

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 선택 또는 새 프로젝트 생성

### 2. Google Drive API 활성화

1. 좌측 메뉴 > **"API 및 서비스"** > **"라이브러리"**
2. 검색창에 **"Google Drive API"** 입력
3. **"Google Drive API"** 선택
4. **"사용"** 버튼 클릭

### 3. 서비스 계정 생성

1. 좌측 메뉴 > **"API 및 서비스"** > **"사용자 인증 정보"**
2. 상단 **"+ 사용자 인증 정보 만들기"** 클릭
3. **"서비스 계정"** 선택
4. 서비스 계정 세부정보 입력:
   - **서비스 계정 이름**: `myAgent-gdrive` (원하는 이름)
   - **서비스 계정 ID**: 자동 생성됨
   - **설명**: `MyAgent Google Drive access`
5. **"만들기 및 계속하기"** 클릭
6. 역할 선택 (선택사항, 건너뛰기 가능)
7. **"완료"** 클릭

### 4. 서비스 계정 키(JSON) 다운로드

1. 생성된 서비스 계정 목록에서 방금 만든 계정 클릭
2. **"키"** 탭으로 이동
3. **"키 추가"** > **"새 키 만들기"** 클릭
4. **"JSON"** 선택
5. **"만들기"** 클릭
6. JSON 파일이 자동으로 다운로드됩니다

### 5. 키 파일 배치

1. 다운로드한 JSON 파일을 **프로젝트 루트**로 이동:
   ```
   C:\Users\user\Documents\Porjects\myAgent\credentials.json
   ```

2. 파일 이름을 정확히 `credentials.json`으로 변경

### 6. Google Drive 공유 설정

서비스 계정으로 파일에 접근하려면 **공유 설정**이 필요합니다:

1. 다운로드한 `credentials.json` 파일을 열어서 `client_email` 값을 복사
   ```json
   {
     "type": "service_account",
     "client_email": "myagent-gdrive@PROJECT_ID.iam.gserviceaccount.com",
     ...
   }
   ```

2. Google Drive에서 접근하려는 폴더/파일을 **서비스 계정 이메일**과 공유:
   - Google Drive 접속
   - 접근할 폴더 우클릭 > **"공유"**
   - 복사한 `client_email` 주소 입력
   - 권한: **"뷰어"** (읽기 전용) 또는 **"편집자"**
   - **"보내기"** 클릭

## ✅ 테스트

설정 완료 후 다음 명령어로 테스트:

```bash
.venv\Scripts\python.exe chatbot\autopilot.py "/gdrive"
```

또는 텔레그램 봇에서:
```
/gdrive
```

## 🔒 보안 주의사항

**⚠️ 중요**: `credentials.json` 파일은 민감한 정보입니다.

1. `.gitignore`에 이미 추가되어 있어 Git에 커밋되지 않습니다
2. 절대 공개 저장소에 업로드하지 마세요
3. 권한 최소화 원칙 준수 (읽기 전용으로 충분하면 뷰어 권한만)

## 📂 파일 구조

설정 완료 후:
```
myAgent/
├── credentials.json          ← 서비스 계정 키 (Git 제외)
├── chatbot/
│   └── autopilot.py
├── tools/
│   └── gdrive.py
└── .gitignore               ← credentials.json 포함
```

## 🐛 트러블슈팅

### "인증 파일이 존재하지 않습니다"
- `credentials.json` 파일이 프로젝트 루트에 있는지 확인
- 파일 이름이 정확히 `credentials.json`인지 확인

### "검색 결과가 없습니다"
- 서비스 계정 이메일로 폴더/파일이 공유되었는지 확인
- Google Drive에서 공유 설정 다시 확인

### "API 에러 발생"
- Google Drive API가 활성화되었는지 확인
- 서비스 계정에 적절한 권한이 있는지 확인
- 할당량 초과 여부 확인 (Google Cloud Console에서 확인)

## 📚 참고 자료

- [Google Drive API 문서](https://developers.google.com/drive/api/guides/about-sdk)
- [서비스 계정 가이드](https://cloud.google.com/iam/docs/service-accounts)
- [Python Quickstart](https://developers.google.com/drive/api/quickstart/python)
