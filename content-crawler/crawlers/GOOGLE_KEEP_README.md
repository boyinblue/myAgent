# Google Keep 크롤러 상태

## ❌ 현재 상태: 사용 불가능

`gkeepapi` 라이브러리를 통한 Google Keep 접근이 불가능합니다.

### 문제 원인

- Google은 2022년 5월부터 "보안 수준이 낮은 앱" 액세스를 완전히 차단
- Google Keep에는 공식 API가 존재하지 않음
- 비공식 라이브러리(`gkeepapi`)는 더 이상 작동하지 않음

### 오류 메시지

```
gkeepapi.exception.LoginException: BadAuthentication
```

### 시도한 해결책

1. ✅ gkeepapi 최신 버전 설치 (0.17.1)
2. ✅ `authenticate()` 메서드 사용 (login은 deprecated)
3. ✅ Google 앱 비밀번호 사용
4. ❌ 여전히 BadAuthentication 오류 발생

## 🔧 대안

### 1. Google Takeout (권장)

일회성으로 Keep 데이터를 추출:

1. https://takeout.google.com/settings/takeout 접속
2. "선택 해제" → "Keep"만 선택
3. "다음 단계" → "내보내기 만들기"
4. JSON 파일 다운로드

**장점:**
- 공식적으로 지원됨
- 모든 데이터 포함
- 안전함

**단점:**
- 수동 작업 필요
- 실시간 동기화 불가

### 2. Notion API 사용

Notion으로 메모를 옮기고 공식 API 사용:

```bash
pip install notion-client
```

```python
from notion_client import Client

notion = Client(auth="your_integration_token")
results = notion.databases.query(database_id="your_database_id")
```

**장점:**
- 공식 API 지원
- 풍부한 기능
- 실시간 동기화

**단점:**
- Keep에서 Notion으로 마이그레이션 필요
- 학습 곡선

### 3. Obsidian (로컬 파일)

마크다운 파일로 메모 관리:

```python
from pathlib import Path

vault_path = Path("~/Documents/ObsidianVault")
notes = list(vault_path.glob("**/*.md"))
```

**장점:**
- 완전한 로컬 제어
- API 제한 없음
- 빠른 속도

**단점:**
- Keep에서 마이그레이션 필요
- 클라우드 동기화 별도 설정

### 4. Selenium 웹 스크래핑 (비추천)

Keep 웹 UI를 Selenium으로 제어:

**단점:**
- 복잡한 구현
- 느린 속도
- UI 변경 시 깨짐
- Google의 봇 탐지 위험

## 📝 결론

**Google Keep을 계속 사용하려면:**
- Google Takeout으로 정기적으로 백업
- Keep 웹 UI를 직접 사용

**프로그래밍 방식 접근이 필요하면:**
- Notion, Obsidian 등 공식 API를 지원하는 서비스로 마이그레이션

## 참고 자료

- [gkeepapi GitHub Issues](https://github.com/kiwiz/gkeepapi/issues)
- [Google Takeout](https://takeout.google.com)
- [Notion API](https://developers.notion.com)
- [Google Keep 웹](https://keep.google.com)
