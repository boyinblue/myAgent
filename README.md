# myAgent

개인 자동화 에이전트 모음 저장소입니다. 현재는 네 가지 축으로 운영합니다.

- `content-crawler`: 블로그/영상 콘텐츠 수집 및 아카이브
- `AI_Skills`: 텔레그램 챗봇의 Autopilot 라우팅/스킬 실행
- `email-agent`: Daum 메일 정리 보조 도구
- `web-dashboard`: 아카이브 조회/관리 웹 대시보드 (ngrok 기반)

## Directory Layout

- `config.json`: 루트 통합 설정(비보안)
- `.env`: 루트 비밀값(토큰/비밀번호/API 키)
- `AI_Skills/SKILLS.md`: LLM 프롬프트 전용 스킬 정의
- `AI_Skills/INSTRUCTIONS.md`: 운영/개발자 지침
- `archive/`: 아카이브 결과물(DB/마크다운)
- `web-dashboard/`: 웹 대시보드 (Flask + ngrok)

## Config Policy

- 비보안 실행 설정은 `config.json`에 둡니다.
- 보안 정보는 `.env`에만 둡니다.
- `.env`는 자동 수정하지 않고, 변경 템플릿은 `.env.example`로 관리합니다.

## Autopilot Notes

- Heuristic 우선: URL 아카이브/검색/무결성 검사는 LLM 우회 실행
- LLM 라우팅은 `SKILLS.md`만 참조
- `skills_prompt_max_chars`로 스킬 컨텍스트 길이 보호(과도한 프롬프트 방지)

## Quick Start

1) 의존성 설치(각 프로젝트별)
2) 루트 `.env` 작성 (`.env.example` 참고)
3) 루트 `config.json` 확인
4) 실행:

- 콘텐츠 크롤러: `python content-crawler/main.py`
- 챗봇(텔레그램): `python chatbot/telegram_bot.py`
- 이메일 에이전트: `python email-agent/main.py`
- 웹 대시보드: 텔레그램 봇에게 "웹 대시보드 시작" 또는 `python web-dashboard/start.py`

## Web Dashboard

포트포워딩 없이 내부망에서 웹 대시보드를 사용할 수 있습니다.

- **실행**: 텔레그램 봇에게 "웹 대시보드 시작" 메시지 전송
- **접속**: 텔레그램으로 받은 일회용 URL로 접속 (ngrok 터널)
- **보안**: 일회용 토큰, 2시간 자동 만료, 무작위 URL
- **기능**: 아카이브 조회/검색, 통계, 크롤링 트리거

자세한 내용은 [web-dashboard/README.md](web-dashboard/README.md) 참고