import json
import os
import runpy
import sys
import re
from urllib.parse import urlparse

import requests

from github_dispatch import trigger_content_crawler_workflow, create_github_issue_from_feedback
from archive_search import search_archive
from archive_validate import validate_archive
from web_dashboard_launcher import launch_dashboard, stop_dashboard
from runtime_config import get_config_value
from shared_credentials import get_shared_secret, load_shared_environment


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_MD_PATH = os.path.join(ROOT_DIR, "SKILLS.md")
DEFAULT_SKILLS_PROMPT_MAX_CHARS = 4500

load_shared_environment()


def load_skills_markdown() -> str:
    if not os.path.exists(SKILLS_MD_PATH):
        return ""
    with open(SKILLS_MD_PATH, "r", encoding="utf-8") as f:
        return f.read()


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


def _get_slash_commands_help() -> str:
    """사용 가능한 슬래시 명령어 목록을 반환합니다."""
    return """📌 사용 가능한 슬래시 명령어:

/search <키워드> - 아카이브에서 키워드 검색
/validate - 아카이브 무결성 검사
/issue <설명> - GitHub 이슈 등록
/dashboard - 웹 대시보드 실행
/dashboard_stop - 웹 대시보드 종료
/archive <URL> - URL을 아카이브에 추가
/help - 이 도움말 표시

💡 슬래시 명령어는 LLM 라우팅을 건너뛰고 즉시 실행됩니다.
예: /search 와인"""


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


def autopilot(user_prompt: str):
    raw_skills_md = load_skills_markdown()
    skills_md = build_skills_context(raw_skills_md, get_skills_prompt_max_chars())

    # 슬래시 명령어 처리 (최우선)
    command, args = _parse_slash_command(user_prompt)
    if command:
        if command == "help":
            print(_get_slash_commands_help())
            return
        elif command == "search":
            if not args:
                print("❌ 검색할 키워드를 입력해주세요. 예: /search 와인")
                return
            keyword = _prepare_search_keyword(args)
            if keyword:
                result = search_archive(keyword)
                print(result)
            else:
                print("❌ 검색할 키워드를 입력해주세요.")
            return
        elif command == "validate":
            result = validate_archive()
            print(result)
            return
        elif command == "issue":
            if not args:
                print("❌ 이슈 내용을 입력해주세요. 예: /issue 대시보드 토큰 문제")
                return
            result = create_github_issue_from_feedback(args)
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
            result = search_archive(keyword)
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
        result = validate_archive()
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
            result = search_archive(keyword)
            print(result)
        else:
            print("❌ 검색할 키워드를 입력해주세요.")
        return
    
    if action == "archive_validate":
        result = validate_archive()
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