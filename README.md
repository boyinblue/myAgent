# myAgent

개인 자동화 에이전트와 운영 도구를 모아 둔 저장소입니다. 주요 구성은 다음과 같습니다.

- `content-crawler`: 블로그/영상 콘텐츠 수집 및 아카이브
- `chatbot` 및 `AI_Skills`: 텔레그램 챗봇과 Autopilot 스킬 실행
- `email-agent`: Daum 메일 정리 보조 도구
- `web-dashboard`: 아카이브 조회/관리 웹 대시보드 (ngrok 기반)
- `ollama`, `tools`, `network`: 로컬 어시스턴트와 공용 운영/유틸리티 도구

## 제공 기능

- **콘텐츠 수집 및 아카이빙**: 네이버 블로그, Tistory, GitHub Pages, YouTube 콘텐츠를 수집해 연도별로 저장하고 검색 인덱스를 관리합니다.
- **텔레그램 자동화**: 자연어 요청과 슬래시 명령으로 아카이브 검색·검증, URL 저장, GitHub 이슈 등록, 대시보드 실행 등을 처리합니다.
- **기념일 다이제스트**: 과거 같은 날짜의 글과 Random Post 3개를 텔레그램으로 보냅니다. Windows PC 로그인 시 하루 한 번 확인합니다.
- **아카이브 대시보드**: 웹에서 아카이브를 검색·조회하고 통계를 확인하거나 크롤링을 실행할 수 있습니다.
- **메일 정리 보조**: Daum 메일 발신자를 분석하고 수신 거부 후보를 제안합니다. 기본은 미리보기이며, 실제 실행 전 확인을 받습니다.
- **로컬 문서 비서**: Ollama 기반 대화와 문서 검색(RAG)을 제공합니다.
- **운영 도구**: Google Drive 연동, 일기, 게시물 검색, 아카이브 무결성 점검, 네트워크 검사 등을 제공합니다.

## Directory Structure

주요 소스와 설정 파일의 구조입니다. 비밀값, 캐시, 로그 등 로컬·실행 데이터는 제외했습니다.

```text
.
├── .github/
│   └── workflows/            # GitHub Actions 실행 정의
├── AI_Skills/
│   └── SKILLS.md             # 챗봇 스킬 정의
├── archive/                  # 연도별 아카이브 및 검색 인덱스
├── chatbot/
│   ├── autopilot.py          # 요청 라우팅 및 자동 실행
│   └── telegram_bot.py       # 텔레그램 봇 진입점
├── content-crawler/
│   ├── crawlers/             # 블로그·영상 플랫폼별 수집기
│   ├── utils/                # 공용 수집 유틸리티
│   ├── main.py
│   └── README.md
├── docs/                     # 설정·운영 문서와 작업 목록
│   ├── GDRIVE_SETUP.md
│   └── TODO.md
├── email-agent/
│   ├── email_agent/          # 메일 처리 로직
│   ├── main.py
│   └── README.md
├── network/
│   └── network_scanner.py
├── ollama/                   # 로컬 LLM 어시스턴트
├── tools/                    # 아카이브·대시보드·자동화 도구
│   ├── run_daily_digest.ps1  # 로그인 시 하루 한 번 다이제스트 실행
│   └── setup_daily_digest.ps1
├── web-dashboard/
│   ├── templates/
│   ├── app.py
│   └── README.md
├── .gitignore
├── .env.example              # 비밀값 설정 예시
├── config.json               # 루트 통합 설정(비보안)
├── setup_autostart.ps1       # Windows 자동 시작 태스크 등록
├── start_bot.ps1             # 텔레그램 봇 실행 스크립트
├── start_bot_auto_restart.ps1
└── README.md
```

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

## Gemini 소스 편집 CLI

`GEMINI_API_KEY`를 루트 `.env`에 설정한 뒤 다음 명령으로 실행합니다.

```bash
python chatbot/local_gemini_chat.py
```

대화창에서 `/edit <요청>`을 입력하면 Gemini가 편집용 Python 스크립트를 생성합니다.
스크립트는 `.runtime/gemini_generated_edit.py`에 저장되고, 프로젝트 내부 파일만 접근할 수
있는 제한된 환경에서 실행됩니다. 실행 결과의 diff를 확인하고 `y`를 입력해야 실제 파일에
반영됩니다. 생성된 스크립트가 파싱·검증·실행에 실패하거나 변경 사항을 만들지 못하면 오류를
Gemini에 전달해 최대 3회까지 자동으로 다시 생성합니다.

```text
/edit chatbot/post_search.py의 검색 결과가 없을 때 안내 문구를 개선해줘
```

## Web Dashboard

포트포워딩 없이 내부망에서 웹 대시보드를 사용할 수 있습니다.

- **실행**: 텔레그램 봇에게 "웹 대시보드 시작" 메시지 전송
- **접속**: 텔레그램으로 받은 일회용 URL로 접속 (ngrok 터널)
- **보안**: 일회용 토큰, 2시간 자동 만료, 무작위 URL
- **기능**: 아카이브 조회/검색, 통계, 크롤링 트리거

자세한 내용은 [web-dashboard/README.md](web-dashboard/README.md) 참고
