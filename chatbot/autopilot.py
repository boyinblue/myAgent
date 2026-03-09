import json
import os
import runpy
import sys
import re
import subprocess
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

import requests

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ROOT_DIR)
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

# Load environment variables
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

try:
    from issue import (
        trigger_content_crawler_workflow,
        create_github_issue_from_feedback,
        list_open_github_issues,
        list_closed_github_issues,
    )
except Exception:
    def trigger_content_crawler_workflow(target_url: str) -> str:
        return "[ERROR] issue 모듈을 찾을 수 없습니다."

    def create_github_issue_from_feedback(user_prompt: str) -> str:
        return "[ERROR] issue 모듈을 찾을 수 없습니다."

    def list_open_github_issues() -> str:
        return "[ERROR] issue 모듈을 찾을 수 없습니다."

    def list_closed_github_issues() -> str:
        return "[ERROR] issue 모듈을 찾을 수 없습니다."

try:
    from diary import find_post_by_date
except Exception:
    def find_post_by_date(date_input: str) -> str:
        return "[ERROR] diary 모듈을 찾을 수 없습니다."

try:
    from post_search import search_posts, search_random_posts
except Exception:
    def search_posts(keyword: str, limit: int = 10) -> str:
        return "[ERROR] post_search 모듈을 찾을 수 없습니다."
    
    def search_random_posts(count: int = 3) -> str:
        return "[ERROR] post_search 모듈을 찾을 수 없습니다."

try:
    from post_validate import validate_posts
except Exception:
    def validate_posts() -> str:
        return "[ERROR] post_validate 모듈을 찾을 수 없습니다."

try:
    from dashboard import launch_dashboard, stop_dashboard
except Exception:
    def launch_dashboard() -> dict:
        return {"success": False, "message": "[ERROR] dashboard 모듈을 찾을 수 없습니다."}

    def stop_dashboard() -> dict:
        return {"success": False, "message": "[ERROR] dashboard 모듈을 찾을 수 없습니다."}

try:
    from runtime_config import get_config_value
except Exception:
    def get_config_value(path: str, default=None):
        return default

try:
    from shared_credentials import get_shared_secret, load_shared_environment
except Exception:
    def get_shared_secret(key: str, default: str = "") -> str:
        return default

    def load_shared_environment() -> None:
        return


SKILLS_MD_PATH = os.path.join(ROOT_DIR, "SKILLS.md")
LEGACY_SKILLS_MD_PATH = os.path.join(os.path.dirname(ROOT_DIR), "AI_Skills", "SKILLS.md")
DEFAULT_SKILLS_PROMPT_MAX_CHARS = 4500

load_shared_environment()


def load_skills_markdown() -> str:
    candidates = [SKILLS_MD_PATH, LEGACY_SKILLS_MD_PATH]
    for path in candidates:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _extract_markdown_section(markdown_text: str, heading: str) -> str:
    lines = (markdown_text or "").splitlines()
    if not lines:
        return ""

    start = -1
    for i, line in enumerate(lines):
        if line.strip() == heading.strip():
            start = i
            break
    if start < 0:
        return ""

    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break

    return "\n".join(lines[start:end]).strip()


def _compact_markdown(markdown_text: str) -> str:
    compact_lines = []
    for raw in (markdown_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            compact_lines.append(line)
            continue
        if line.startswith("-"):
            compact_lines.append(line)
            continue
        if line.startswith("###"):
            compact_lines.append(line)
            continue
        compact_lines.append(re.sub(r"\s+", " ", line))
    return "\n".join(compact_lines).strip()


def get_skills_prompt_max_chars() -> int:
    raw = get_config_value(
        "autopilot.skills_prompt_max_chars",
        os.getenv("AUTOPILOT_SKILLS_MAX_CHARS", str(DEFAULT_SKILLS_PROMPT_MAX_CHARS)),
    )
    try:
        value = int(raw)
        return max(1000, min(value, 20000))
    except Exception:
        return DEFAULT_SKILLS_PROMPT_MAX_CHARS


def build_skills_context(skills_md: str, max_chars: int) -> str:
    content = (skills_md or "").strip()
    if not content:
        return ""

    if len(content) <= max_chars:
        return content

    selected_sections = []
    for heading in ["## Output Contract", "## Skills", "## Examples", "## Config & Env"]:
        section = _extract_markdown_section(content, heading)
        if section:
            selected_sections.append(section)

    if not selected_sections:
        compact = _compact_markdown(content)
        return compact[:max_chars]

    merged = "\n\n".join(selected_sections)
    compact = _compact_markdown(merged)
    if len(compact) <= max_chars:
        return compact

    tail_note = "\n\n[skills_context_truncated]"
    return compact[: max_chars - len(tail_note)] + tail_note


def ask_ollama(prompt: str, system_prompt: str, model: str = "gemma2:9b") -> str:
    url = "http://localhost:11434/api/generate"
    data = {
        "model": model,
        "prompt": f"{system_prompt}\n\nUser task: {prompt}",
        "stream": False,
    }
    response = requests.post(url, json=data, timeout=120)
    response.raise_for_status()
    return response.json().get("response", "").strip()


def ask_gemini(prompt: str, system_prompt: str, model: str = "gemini-1.5-flash") -> str:
    api_key = (get_shared_secret("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY가 설정되지 않았습니다.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{system_prompt}\n\nUser task: {prompt}"
                    }
                ]
            }
        ]
    }

    response = requests.post(url, json=body, timeout=120)
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [p.get("text", "") for p in parts if p.get("text")]
    return "\n".join(texts).strip()


def ask_model(prompt: str, system_prompt: str) -> str:
    provider = str(
        get_config_value(
            "autopilot.provider",
            os.getenv("AUTOPILOT_PROVIDER", "ollama"),
        )
    ).strip().lower()

    if provider == "gemini":
        model = str(
            get_config_value(
                "autopilot.models.gemini",
                os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            )
        )
        return ask_gemini(prompt, system_prompt, model=model)

    model = str(
        get_config_value(
            "autopilot.models.ollama",
            os.getenv("OLLAMA_MODEL", "gemma2:9b"),
        )
    )
    return ask_ollama(prompt, system_prompt, model=model)


def _extract_router_json(raw: str) -> dict | None:
    text = (raw or "").strip()
    if not text:
        return None

    # 1) code fence 제거
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # 2) 그대로 JSON 시도
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 3) 텍스트 중간에 포함된 첫 JSON 객체 추출
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue

    return None


def _normalize_router_decision(parsed: dict | None) -> dict:
    if not parsed:
        return {"action": "chat", "skill": "fallback_chat", "reason": "router_parse_failed"}

    action = str(parsed.get("action", "")).strip().lower()
    skill = str(parsed.get("skill", "")).strip() or "fallback_chat"
    reason = str(parsed.get("reason", "")).strip() or "router_ok"
    url = str(parsed.get("url", "")).strip()
    keyword = str(parsed.get("keyword", "")).strip()

    if action not in {"chat", "python_code", "github_action", "github_issue", "archive_search", "archive_validate", "web_dashboard_launch", "web_dashboard_stop"}:
        return {"action": "chat", "skill": "fallback_chat", "reason": "router_invalid_action"}

    normalized = {"action": action, "skill": skill, "reason": reason}
    if url:
        normalized["url"] = url
    if keyword:
        normalized["keyword"] = keyword
    return normalized


def _extract_first_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s'\"<>]+", text or "")
    if not match:
        return None
    url = match.group(0).rstrip('.,)"]')
    try:
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return url
    except Exception:
        return None
    return None


def _has_archive_intent(text: str) -> bool:
    lower = (text or "").lower()
    keywords = [
        "아카이브",
        "추가해줘",
        "추가해 줘",
        "저장",
        "archive",
        "content-crawler",
        "run_crowler",
    ]
    return any(k in lower for k in keywords)


def _has_search_intent(text: str) -> bool:
    lower = (text or "").lower()
    keywords = [
        "검색",
        "찾아줘",
        "찾아 줘",
        "찾기",
        "search",
        "find",
    ]
    return any(k in lower for k in keywords)


def _has_issue_intent(text: str) -> bool:
    lower = (text or "").lower()
    issue_terms = [
        "이슈",
        "issue",
        "깃허브 이슈",
        "github issue",
    ]
    create_terms = [
        "등록",
        "생성",
        "작성",
        "올려",
        "만들",
        "create",
        "open",
        "report",
    ]
    discomfort_terms = [
        "불편",
        "안돼",
        "안 됨",
        "문제",
        "오류",
        "버그",
        "에러",
        "개선",
        "개선해줘",
    ]

    explicit_issue = any(term in lower for term in issue_terms)
    create_request = any(term in lower for term in create_terms)
    has_discomfort = any(term in lower for term in discomfort_terms)

    if explicit_issue and create_request:
        return True

    if ("github" in lower or "깃허브" in lower) and (explicit_issue or has_discomfort) and create_request:
        return True

    return False


def _has_validate_intent(text: str) -> bool:
    lower = (text or "").lower()
    keywords = [
        "무결성",
        "검증",
        "누락",
        "불완전",
        "validate",
        "integrity",
        "check",
    ]
    return any(k in lower for k in keywords) and ("아카이브" in lower or "archive" in lower or "db" in lower.replace("database", "db"))


def _has_dashboard_launch_intent(text: str) -> bool:
    lower = (text or "").lower()
    # 웹 대시보드 실행 관련 키워드
    keywords = [
        "웹페이지", "웹 페이지", "대시보드", "웹 대시보드",
        "web dashboard", "web page", "dashboard", "webpage"
    ]
    actions = ["보여", "보여줘", "열", "열어", "열어줘", "시작", "실행"]
    
    # 웹/페이지 또는 대시보드 키워드 확인
    has_webpage = any(k in lower for k in keywords)
    has_action = "웹" in lower or "페이지" in lower or "대시보드" in lower or any(a in lower for a in actions)
    
    return has_webpage or has_action


def _has_dashboard_stop_intent(text: str) -> bool:
    lower = (text or "").lower()
    # 웹 대시보드 종료 관련 키워드
    keywords = [
        "웹페이지", "웹 페이지", "대시보드", "웹 대시보드",
        "web dashboard", "web page", "dashboard", "webpage"
    ]
    actions = ["종료", "중지", "닫", "닫아", "stop", "close", "shutdown"]
    
    has_webpage = any(k in lower for k in keywords)
    has_action = any(a in lower for a in actions)
    
    return has_webpage and has_action


def _extract_search_keyword(text: str) -> str:
    """검색 요청 문장에서 실제 검색어를 휴리스틱으로 추출합니다."""
    source = (text or "").strip()
    if not source:
        return ""

    # 따옴표 안의 문구를 우선 사용
    quoted = re.findall(r"['\"“”‘’](.+?)['\"“”‘’]", source)
    if quoted:
        return quoted[0].strip()

    cleaned = source
    patterns = [
        r"아카이브(에서|에)?",
        r"(좀\s*)?(한\s*번\s*)?검색(해\s*줘|해줘|해\s*주세요|해주세요|해\s*봐|해봐|해\s*줘요|해줘요)?",
        r"(좀\s*)?(한\s*번\s*)?찾(아\s*줘|아줘|아\s*주세요|아주세요|아\s*봐|아봐)?",
        r"search(\s+for)?",
        r"find",
        r"related\s+to",
        r"about",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"[?!.~,]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    tail_noises = ["해줘", "해주세요", "알려줘", "보여줘", "줘", "요", "좀"]
    for noise in tail_noises:
        if cleaned.endswith(noise):
            cleaned = cleaned[: -len(noise)].strip()

    return cleaned


def _normalize_search_keyword_with_llm(user_prompt: str, heuristic_keyword: str) -> str:
    """LLM으로 검색어를 정돈합니다. 실패 시 빈 문자열을 반환합니다."""
    if not heuristic_keyword:
        return ""

    system_prompt = (
        "You normalize archive search queries for SQL LIKE search. "
        "Return ONLY JSON like {\"keyword\":\"...\"}. "
        "Keep 핵심 명사/영문 키워드, remove request words, particles, and polite endings. "
        "Do not add explanations."
    )
    user_text = (
        f"original_user_prompt: {user_prompt}\n"
        f"heuristic_keyword: {heuristic_keyword}\n"
        "output JSON only"
    )

    raw = ask_model(user_text, system_prompt)
    parsed = _extract_router_json(raw)
    if isinstance(parsed, dict):
        keyword = str(parsed.get("keyword", "")).strip()
        if keyword:
            return keyword

    # JSON 파싱 실패 시 텍스트 응답 폴백 처리
    raw_text = (raw or "").strip().strip('`').strip()
    raw_text = re.sub(r"^keyword\s*[:=]\s*", "", raw_text, flags=re.IGNORECASE).strip()
    return raw_text


def _prepare_search_keyword(user_prompt: str) -> str:
    """휴리스틱 추출 후 LLM 정규화를 시도하고, 실패하면 휴리스틱 결과를 사용합니다."""
    heuristic_keyword = _extract_search_keyword(user_prompt)
    if not heuristic_keyword:
        return ""

    try:
        normalized = _normalize_search_keyword_with_llm(user_prompt, heuristic_keyword)
        normalized = (normalized or "").strip()
        if normalized:
            return normalized
    except Exception:
        pass

    return heuristic_keyword


def _parse_slash_command(text: str) -> tuple:
    """슬래시 명령어를 파싱합니다.
    
    Returns:
        (command, args): command는 슬래시 없는 명령어, args는 나머지 텍스트
                        슬래시 명령어가 아니면 (None, original_text)
    """
    text = (text or "").strip()
    if not text.startswith("/"):
        return (None, text)
    
    # 첫 공백 또는 줄바꿈까지가 명령어
    parts = text[1:].split(maxsplit=1)
    if not parts:
        return (None, text)
    
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    return (command, args)


def _get_command_help(command_name: str) -> str:
    """특정 명령어에 대한 도움말을 반환합니다."""
    help_texts = {
        "post": """📌 /post 명령어

사용법:
  /post <키워드> - 포스트 검색
  /post random - 랜덤 포스트 3개 출력
  /post <URL> - URL을 아카이브에 추가
  /post search <키워드> - 포스트 검색
  /post validate - 포스트 무결성 검증

예시:
  /post 와인
  /post random
  /post https://blog.naver.com/...""",
        
        "diary": """📌 /diary 명령어

사용법:
  /diary <날짜> - 특정 날짜 근처의 포스트 조회

형식:
  YYYYMMDD 또는 YYMMDD

예시:
  /diary 20260309
  /diary 260309""",
        
        "issue": """📌 /issue 명령어

사용법:
  /issue create <내용> - GitHub 이슈 등록
  /issue list - 열린 이슈 목록
  /issue history - 닫힌 이슈 목록

예시:
  /issue create 대시보드 토큰 문제
  /issue list""",
        
        "search": """📌 /search 명령어

사용법:
  /search <키워드> - 포스트 검색

예시:
  /search 코스트코
  /search python""",
        
        "health": """📌 /health 명령어

사용법:
  /health - 시스템 상태 확인

표시 정보:
  - 챗봇 실행 상태
  - 대시보드 실행 상태
  - 디스크 용량
  - 포스트 개수""",
        
        "ver": """📌 /ver 명령어

사용법:
  /ver - 버전 정보 표시

표시 정보:
  - Python 버전
  - Git 커밋 해시
  - Git 브랜치
  - 프로젝트 경로""",
        
        "restart": """📌 /restart 명령어

사용법:
  /restart - 챗봇 재시작

주의: 재시작 중에는 메시지에 응답할 수 없습니다.""",
        
        "save": """📌 /save 명령어

사용법:
  /save - 변경사항 커밋 및 푸시

기능: tools/git_auto_commit.py를 실행합니다.""",
        
        "dashboard": """📌 /dashboard 명령어

사용법:
  /dashboard start - 대시보드 시작
  /dashboard stop - 대시보드 종료
  /dashboard status - 대시보드 상태 확인""",

        "gdrive": """📌 /gdrive 명령어

사용법:
  /gdrive - 구글 드라이브 파일/폴더 탐색

사전 준비:
  - 프로젝트 루트에 credentials.json 배치
  - 서비스 계정에 드라이브 조회 권한 부여""",

        "shell": """📌 $ 쉘 명령어

사용법:
  $<명령어> - 쉘 명령어 직접 실행

예시:
  $pip install requests
  $python --version
  $dir
  $git status

주의:
  - 명령어는 프로젝트 루트에서 실행됩니다
  - 타임아웃: 5분
  - 위험한 명령어 실행 시 주의하세요""",
    }
    
    normalized = command_name.lower().strip()
    return help_texts.get(normalized, f"❌ '{command_name}' 명령어에 대한 도움말이 없습니다.\n\n{_get_slash_commands_help()}")


def _get_slash_commands_help() -> str:
    """사용 가능한 슬래시 명령어 목록을 반환합니다."""
    return """📌 주요 슬래시 명령어:

/post <키워드> - 포스트 검색
/post random - 랜덤 포스트 3개
/post <URL> - URL 아카이브에 추가
/diary <날짜> - 날짜 근처 포스트 조회
/issue create <내용> - 이슈 등록
/search <키워드> - 검색
/health - 시스템 상태 확인
/ver - 버전 정보
/gdrive - 구글 드라이브 탐색
/restart - 챗봇 재시작
/save - 변경사항 커밋
/help - 명령어 목록

💻 쉘 명령어:
$<명령어> - 쉘 명령어 직접 실행 (예: $pip install requests)"""


def _get_health_status() -> str:
    """챗봇 및 시스템 상태 정보를 반환합니다."""
    lines = ["🏥 시스템 상태\n"]
    
    # 1. 챗봇 상태
    lines.append("✅ 챗봇: 실행 중")
    
    # 2. 대시보드 상태
    try:
        script_path = os.path.join(PROJECT_ROOT, "tools", "dashboard.py")
        if os.path.exists(script_path):
            proc = subprocess.run(
                [sys.executable, script_path, "status"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
                check=False,
            )
            dashboard_status = (proc.stdout or "").strip()
            if "실행 중" in dashboard_status or "running" in dashboard_status.lower():
                lines.append("✅ 대시보드: 실행 중")
            else:
                lines.append("⚪ 대시보드: 중지됨")
        else:
            lines.append("❓ 대시보드: 스크립트 없음")
    except Exception:
        lines.append("❓ 대시보드: 상태 확인 실패")
    
    # 3. 디스크 용량
    try:
        usage = shutil.disk_usage(PROJECT_ROOT)
        total_gb = usage.total / (1024 ** 3)
        used_gb = usage.used / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        percent = (usage.used / usage.total) * 100
        lines.append(f"💾 디스크: {free_gb:.1f}GB 여유 (전체 {total_gb:.1f}GB, 사용률 {percent:.1f}%)")
    except Exception as e:
        lines.append(f"❌ 디스크: 조회 실패 ({e})")
    
    # 4. 포스트 개수
    try:
        db_path = Path(PROJECT_ROOT) / "archive" / "archive_index.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM posts")
            post_count = cursor.fetchone()[0]
            conn.close()
            lines.append(f"📚 포스트: {post_count:,}개")
        else:
            lines.append("❓ 포스트: DB 파일 없음")
    except Exception as e:
        lines.append(f"❌ 포스트: 조회 실패 ({e})")
    
    return "\n".join(lines)


def _get_version_info() -> str:
    """버전 정보를 반환합니다."""
    lines = ["ℹ️ 버전 정보\n"]
    
    # Python 버전
    lines.append(f"🐍 Python: {sys.version.split()[0]}")
    
    # Git 커밋 정보
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=PROJECT_ROOT,
            check=False,
        )
        if result.returncode == 0:
            commit_hash = result.stdout.strip()
            lines.append(f"📌 Git Commit: {commit_hash}")
        
        # Git 브랜치
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=PROJECT_ROOT,
            check=False,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            lines.append(f"🌿 Git Branch: {branch}")
    except Exception:
        lines.append("❓ Git: 정보 조회 실패")
    
    # 프로젝트 경로
    lines.append(f"📂 Project: {PROJECT_ROOT}")
    
    return "\n".join(lines)


def _load_help_markdown() -> str:
    """help.md 파일이 있으면 내용을 반환하고, 없으면 빈 문자열을 반환합니다."""
    candidates = [
        os.path.join(ROOT_DIR, "help.md"),
        os.path.join(os.path.dirname(ROOT_DIR), "help.md"),
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as exc:
                return f"[ERROR] help.md 읽기 실패: {exc}"

    return ""


def _resolve_command_markdown_path(command: str) -> str:
    """/command 에 대응하는 markdown 파일 경로를 반환합니다. 없으면 빈 문자열."""
    normalized = (command or "").strip().lower()
    if not normalized or not re.fullmatch(r"[a-z0-9_-]+", normalized):
        return ""

    file_name = f"{normalized}.md"
    candidates = [
        os.path.join(ROOT_DIR, file_name),
        os.path.join(os.path.dirname(ROOT_DIR), file_name),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def _extract_fenced_python_code(raw_text: str) -> str:
    """LLM 응답에서 ```python ... ``` 코드블록을 추출합니다."""
    text = (raw_text or "").strip()
    if not text:
        return ""

    patterns = [
        r"```python\s*(.*?)\s*```",
        r"```py\s*(.*?)\s*```",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return (match.group(1) or "").strip()

    return ""


def _execute_python_from_text(raw_text: str, command: str) -> bool:
    """텍스트가 파이썬 스크립트면 실행하고 True를 반환합니다."""
    rendered = (raw_text or "").strip()
    if not rendered:
        return False

    # 1) '# script_name.py' 헤더가 있는 기존 포맷 우선 처리
    script_path = extract_python_code(rendered)
    if script_path:
        print(f"[INFO] markdown 명령에서 생성된 스크립트 실행: {os.path.basename(script_path)}")
        execute_script(script_path)
        return True

    # 2) fenced python 코드블록 처리
    code_block = _extract_fenced_python_code(rendered)
    if not code_block:
        return False

    safe_command = re.sub(r"[^a-z0-9_-]", "_", (command or "").lower()) or "slash"
    script_name = f"_slash_{safe_command}_auto.py"
    script_path = os.path.join(ROOT_DIR, script_name)

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code_block)

    print(f"[INFO] markdown 명령의 python 코드블록 실행: {script_name}")
    execute_script(script_path)
    return True


def _handle_markdown_command(command: str, args: str, skills_md: str) -> bool:
    """/command 에 대응하는 markdown가 있으면 LLM 처리 후 출력합니다."""
    markdown_path = _resolve_command_markdown_path(command)
    if not markdown_path:
        return False

    try:
        with open(markdown_path, "r", encoding="utf-8") as f:
            markdown_text = f.read().strip()
    except Exception as exc:
        print(f"[ERROR] {os.path.basename(markdown_path)} 읽기 실패: {exc}")
        return True

    if not markdown_text:
        print(f"[ERROR] {os.path.basename(markdown_path)} 파일이 비어 있습니다.")
        return True

    user_args = (args or "").strip()
    render_prompt = (
        f"사용자가 '/{command}' 명령을 요청했습니다. 아래 markdown 문서를 기반으로 한국어로 안내하세요. "
        "문서에 없는 기능을 추가하지 말고, 문서 내용을 간결하고 읽기 쉽게 정리해 답변하세요."
    )
    if user_args:
        render_prompt += f"\n\n추가 사용자 입력: {user_args}"

    render_prompt += f"\n\n[{os.path.basename(markdown_path)}]\n{markdown_text}"

    try:
        rendered = answer_chat(render_prompt, skills_md)
        if (rendered or "").strip():
            try:
                if not _execute_python_from_text(rendered, command):
                    print(rendered.strip())
            except Exception as exec_err:
                print(f"[ERROR] python 스크립트 실행 실패: {exec_err}")
        else:
            print(markdown_text)
    except Exception:
        print(markdown_text)

    return True


def _run_tools_dashboard_command(subcommand: str) -> str:
    """tools/dashboard.py를 실행해 대시보드를 제어합니다."""
    normalized = (subcommand or "").strip().lower()
    action_map = {
        "start": "launch",
        "stop": "stop",
        "status": "status",
    }
    action = action_map.get(normalized)
    if not action:
        return "❌ /dashboard 명령은 start | stop | status 중 하나를 사용하세요."

    script_path = os.path.join(os.path.dirname(ROOT_DIR), "tools", "dashboard.py")
    if not os.path.exists(script_path):
        return f"[ERROR] 대시보드 런처를 찾을 수 없습니다: {script_path}"

    try:
        proc = subprocess.run(
            [sys.executable, script_path, action],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(ROOT_DIR),
            check=False,
        )
    except Exception as exc:
        return f"[ERROR] 대시보드 명령 실행 실패: {exc}"

    output = (proc.stdout or "").strip()
    if not output:
        output = (proc.stderr or "").strip()

    if not output:
        return "[ERROR] 대시보드 명령 실행 결과가 비어 있습니다."

    try:
        data = json.loads(output)
        if isinstance(data, dict):
            message = str(data.get("message", "")).strip()
            if message:
                return message
            return output
    except Exception:
        pass

    return output


def _run_gdrive_command() -> str:
    """tools/gdrive.py를 실행해 구글 드라이브를 탐색합니다."""
    script_path = os.path.join(PROJECT_ROOT, "tools", "gdrive.py")
    if not os.path.exists(script_path):
        return f"[ERROR] gdrive 스크립트를 찾을 수 없습니다: {script_path}"

    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=PROJECT_ROOT,
            check=False,
        )
    except Exception as exc:
        return f"[ERROR] /gdrive 실행 실패: {exc}"

    output = (proc.stdout or "").strip()
    stderr_output = (proc.stderr or "").strip()
    if not output:
        output = stderr_output

    if not output:
        return "[ERROR] /gdrive 실행 결과가 비어 있습니다."

    if "ModuleNotFoundError" in output and "google" in output:
        return (
            "❌ Google Drive 의존성 패키지가 설치되지 않았습니다.\n"
            "다음 명령으로 설치하세요:\n"
            "pip install google-api-python-client google-auth"
        )

    if "credentials.json" in output and "존재하지 않습니다" in output:
        return (
            "❌ credentials.json 파일이 없습니다.\n"
            "프로젝트 루트에 서비스 계정 키 파일을 배치한 뒤 다시 시도하세요."
        )

    return output


def decide_action(user_prompt: str, skills_md: str) -> dict:
    system_prompt = (
        "You are an autopilot router. "
        "Use the skill definitions below to choose the best action. "
        "Return ONLY JSON with this schema: "
        '{"action":"chat|python_code|github_action|github_issue|archive_search|archive_validate|web_dashboard_launch|web_dashboard_stop","skill":"skill_name","reason":"short reason","url":"optional_target_url","keyword":"optional_search_keyword"}.\n\n'
        f"[SKILL_DEFINITIONS]\n{skills_md}"
    )
    raw = ask_model(user_prompt, system_prompt)
    parsed = _extract_router_json(raw)
    return _normalize_router_decision(parsed)


def generate_python_code(user_prompt: str, skills_md: str) -> str:
    system_prompt = (
        "You are a Python code generator. "
        "Follow the skill definitions. "
        "The first line MUST be a filename comment like '# script_name.py'. "
        "Return ONLY runnable Python code. No markdown fences.\n\n"
        f"[SKILL_DEFINITIONS]\n{skills_md}"
    )
    return ask_model(user_prompt, system_prompt)


def answer_chat(user_prompt: str, skills_md: str) -> str:
    system_prompt = (
        "You are a helpful assistant. "
        "Use the skill definitions for tone and boundaries.\n\n"
        f"[SKILL_DEFINITIONS]\n{skills_md}"
    )
    return ask_model(user_prompt, system_prompt)


def local_natural_fallback(user_prompt: str, reason: str = "fallback") -> str:
    return (
        "요청은 확인했어요. 현재 AI 추론 경로에 일시적인 문제가 있어 기본 모드로 응답합니다.\n"
        f"- 상태: {reason}\n"
        "- 안내: URL 아카이브 요청이라면 URL을 다시 한 번 보내주세요.\n"
        "- 예시: 아카이브에 추가해줘 https://blog.naver.com/아이디/포스트번호"
    )


def extract_python_code(raw_text: str) -> str | None:
    lines = raw_text.split("\n")
    code_lines = []
    script_name = ""

    for line in lines:
        if line.strip().startswith("```"):
            continue
        if not script_name and line.strip().startswith("# "):
            script_name = line.strip()[2:].strip()
        code_lines.append(line)

    if not script_name:
        return None

    script_path = os.path.join(ROOT_DIR, script_name)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("\n".join(code_lines).strip())
    return script_path


def execute_script(script_path: str):
    runpy.run_path(script_path, run_name="__main__")


def _send_telegram_message(message: str) -> bool:
    """텔레그램으로 메시지를 전송합니다."""
    try:
        token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
        chat_id_raw = os.getenv('TELEGRAM_CHAT_ID', '').strip()
        
        if not token or not chat_id_raw:
            return False
        
        chat_id = int(chat_id_raw) if chat_id_raw.isdigit() else 0
        if not chat_id:
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message[:4096],  # 텔레그램 메시지 길이 제한
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def autopilot(user_prompt: str):
    raw_skills_md = load_skills_markdown()
    skills_md = build_skills_context(raw_skills_md, get_skills_prompt_max_chars())

    # $ 쉘 명령어 처리 (최우선)
    if user_prompt.strip().startswith("$"):
        shell_command = user_prompt.strip()[1:].strip()
        if not shell_command:
            print("❌ 실행할 명령어를 입력해주세요. 예: $pip install requests")
            return
        
        print(f"🔧 쉘 명령어 실행 중: {shell_command}")
        
        telegram_msg_parts = [f"🔧 <b>쉘 명령어 실행</b>\n<code>{shell_command}</code>\n"]
        
        try:
            proc = subprocess.run(
                shell_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=PROJECT_ROOT,
                check=False,
            )
            
            output = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            
            if output:
                print(output)
                # 텔레그램용 출력 (길이 제한)
                output_preview = output[:1500] + "..." if len(output) > 1500 else output
                telegram_msg_parts.append(f"\n<b>출력:</b>\n<pre>{output_preview}</pre>")
            
            if stderr:
                print(stderr)
                stderr_preview = stderr[:1000] + "..." if len(stderr) > 1000 else stderr
                telegram_msg_parts.append(f"\n<b>오류:</b>\n<pre>{stderr_preview}</pre>")
            
            if proc.returncode != 0:
                status_msg = f"\n⚠️  명령어가 종료 코드 {proc.returncode}를 반환했습니다."
                print(status_msg)
                telegram_msg_parts.append(f"\n⚠️ 종료 코드: {proc.returncode}")
            else:
                status_msg = "\n✅ 명령어 실행 완료"
                print(status_msg)
                telegram_msg_parts.append("\n✅ 실행 완료")
            
            # 텔레그램으로 결과 전송
            telegram_msg = "".join(telegram_msg_parts)
            _send_telegram_message(telegram_msg)
                
        except subprocess.TimeoutExpired:
            error_msg = "❌ 명령어 실행 시간 초과 (5분)"
            print(error_msg)
            telegram_msg_parts.append(f"\n{error_msg}")
            _send_telegram_message("".join(telegram_msg_parts))
        except Exception as e:
            error_msg = f"❌ 명령어 실행 중 오류: {e}"
            print(error_msg)
            telegram_msg_parts.append(f"\n{error_msg}")
            _send_telegram_message("".join(telegram_msg_parts))
        return

    # 슬래시 명령어 처리 (최우선)
    command, args = _parse_slash_command(user_prompt)
    if command:
        if command == "post":
            raw_args = (args or "").strip()
            if not raw_args:
                print("❌ /post 명령은 URL 또는 하위 명령어를 입력해주세요. 예: /post <URL>, /post search <키워드>, /post validate, /post random")
                return

            detected_url = _extract_first_url(raw_args)
            if detected_url:
                result = trigger_content_crawler_workflow(detected_url)
                print(result)
                return

            parts = raw_args.split(maxsplit=1)
            subcommand = parts[0].lower()
            subargs = parts[1].strip() if len(parts) > 1 else ""

            if subcommand == "random":
                print(search_random_posts())
                return

            if subcommand == "search":
                if not subargs:
                    print("❌ /post search <키워드> 형식으로 입력해주세요.")
                    return
                keyword = _prepare_search_keyword(subargs)
                if keyword:
                    print(search_posts(keyword))
                else:
                    print("❌ 검색할 키워드를 입력해주세요.")
                return

            if subcommand == "validate":
                print(validate_posts())
                return

            # 서브커맨드가 search/validate/random이 아니면 전체를 검색어로 처리
            keyword = _prepare_search_keyword(raw_args)
            if keyword:
                print(search_posts(keyword))
            else:
                print("❌ 검색할 키워드를 입력해주세요.")
            return

        if command == "dashboard":
            first_arg = (args.split()[0].strip().lower() if args.strip() else "")
            if first_arg in {"start", "stop", "status"}:
                print(_run_tools_dashboard_command(first_arg))
                return

        if command == "gdrive":
            print(_run_gdrive_command())
            return

        if command == "issue":
            normalized_args = (args or "").strip()
            if not normalized_args:
                print("❌ 사용법: /issue create <내용> | /issue list | /issue history")
                return

            issue_parts = normalized_args.split(maxsplit=1)
            issue_subcommand = issue_parts[0].strip().lower()
            issue_payload = issue_parts[1].strip() if len(issue_parts) > 1 else ""

            if issue_subcommand == "list":
                print(list_open_github_issues())
                return

            if issue_subcommand == "history":
                print(list_closed_github_issues())
                return

            if issue_subcommand == "create":
                if not issue_payload:
                    print("❌ 이슈 내용을 입력해주세요. 예: /issue create 대시보드 토큰 문제")
                    return
                print(create_github_issue_from_feedback(issue_payload))
                return

            # 하위 명령어를 생략한 경우 기존 동작과 호환되도록 바로 생성 시도
            print(create_github_issue_from_feedback(normalized_args))
            return

        if command == "diary":
            date_input = (args or "").strip()
            if not date_input:
                print("❌ 사용법: /diary YYYYMMDD 또는 /diary YYMMDD")
                print("예: /diary 20260309 또는 /diary 260309")
                return
            print(find_post_by_date(date_input))
            return

        if command == "help":
            query = (args or "").strip()
            if query:
                # /help 질의어 - 특정 명령어 도움말
                print(_get_command_help(query))
            else:
                # /help - 전체 명령어 목록
                print(_get_slash_commands_help())
            return

        if command == "health":
            print(_get_health_status())
            return

        if command == "ver":
            print(_get_version_info())
            return

        if _handle_markdown_command(command, args, skills_md):
            return
        elif command == "search":
            if not args:
                print("❌ 검색할 키워드를 입력해주세요. 예: /search 와인")
                return
            keyword = _prepare_search_keyword(args)
            if keyword:
                result = search_posts(keyword)
                print(result)
            else:
                print("❌ 검색할 키워드를 입력해주세요.")
            return
        elif command == "validate":
            result = validate_posts()
            print(result)
            return
        elif command in ["dashboard", "dashboard_start", "dashboard_launch"]:
            result = launch_dashboard()
            print(result.get('message', ''))
            return
        elif command == "dashboard_stop":
            result = stop_dashboard()
            print(result.get('message', ''))
            return
        elif command == "archive":
            url = _extract_first_url(args)
            if not url:
                print("❌ 아카이브할 URL을 입력해주세요. 예: /archive https://blog.naver.com/...")
                return
            result = trigger_content_crawler_workflow(url)
            print(result)
            return
        else:
            print(f"❌ 알 수 없는 명령어: /{command}\n\n{_get_slash_commands_help()}")
            return

    # URL + 아카이브 의도는 LLM 라우터를 우회해 즉시 GitHub Action 실행
    detected_url = _extract_first_url(user_prompt)
    if detected_url and _has_archive_intent(user_prompt):
        result = trigger_content_crawler_workflow(detected_url)
        print(result)
        return
    
    # 검색 의도 감지 시 즉시 검색 실행
    if _has_search_intent(user_prompt):
        keyword = _prepare_search_keyword(user_prompt)
        if keyword:
            result = search_posts(keyword)
            print(result)
        else:
            print("❌ 검색할 키워드를 입력해주세요.")
        return

    # GitHub 이슈 등록 의도 감지 시 즉시 실행
    if _has_issue_intent(user_prompt):
        result = create_github_issue_from_feedback(user_prompt)
        print(result)
        return
    
    # 무결성 검증 의도 감지 시 즉시 실행
    if _has_validate_intent(user_prompt):
        result = validate_posts()
        print(result)
        return
    
    # 웹 대시보드 실행 의도 감지 시 즉시 실행
    if _has_dashboard_launch_intent(user_prompt):
        result = launch_dashboard()
        print(result.get('message', ''))
        return
    
    # 웹 대시보드 종료 의도 감지 시 즉시 실행
    if _has_dashboard_stop_intent(user_prompt):
        result = stop_dashboard()
        print(result.get('message', ''))
        return

    try:
        decision = decide_action(user_prompt, skills_md)
    except Exception as exc:
        print(local_natural_fallback(user_prompt, reason="router_exception"))
        return

    action = decision.get("action", "chat")
    skill = decision.get("skill", "unknown")
    reason = decision.get("reason", "")

    if action == "python_code":
        try:
            raw_output = generate_python_code(user_prompt, skills_md)
        except Exception as exc:
            print(f"[ERROR] 코드 생성 실패: {exc}")
            print(local_natural_fallback(user_prompt, reason="python_generation_exception"))
            return
        script_path = extract_python_code(raw_output)
        if not script_path:
            print("[ERROR] 코드 생성 결과에서 파일명을 찾지 못했습니다.")
            print(local_natural_fallback(user_prompt, reason="python_code_parse_failed"))
            return
        print(f"[INFO] 생성된 스크립트: {script_path}")
        try:
            execute_script(script_path)
        except Exception as exc:
            print(f"[ERROR] '{script_path}' 실행 중 오류: {exc}")
        return

    if action == "github_action":
        target_url = decision.get("url") or _extract_first_url(user_prompt)
        result = trigger_content_crawler_workflow(target_url or "")
        print(result)
        return

    if action == "github_issue":
        issue_prompt = decision.get("keyword") or user_prompt
        result = create_github_issue_from_feedback(issue_prompt)
        print(result)
        return
    
    if action == "archive_search":
        base_query = decision.get("keyword") or user_prompt
        keyword = _prepare_search_keyword(base_query)
        if keyword:
            result = search_posts(keyword)
            print(result)
        else:
            print("❌ 검색할 키워드를 입력해주세요.")
        return
    
    if action == "archive_validate":
        result = validate_posts()
        print(result)
        return
    
    if action == "web_dashboard_launch":
        result = launch_dashboard()
        print(result.get('message', ''))
        return
    
    if action == "web_dashboard_stop":
        result = stop_dashboard()
        print(result.get('message', ''))
        return

    try:
        text = answer_chat(user_prompt, skills_md)
        if text.strip():
            print(text)
            return
        print(local_natural_fallback(user_prompt, reason="empty_chat_response"))
    except Exception as exc:
        print(f"[ERROR] chat 응답 생성 실패: {exc}")
        print(local_natural_fallback(user_prompt, reason="chat_exception"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python autopilot.py <task_description>")
        sys.exit(1)

    task_description = " ".join(sys.argv[1:])
    autopilot(task_description)