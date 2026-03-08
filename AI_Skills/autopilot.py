import json
import os
import runpy
import sys
import re
from urllib.parse import urlparse

import requests

from github_dispatch import trigger_content_crawler_workflow
from runtime_config import get_config_value
from shared_credentials import get_shared_secret, load_shared_environment


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_MD_PATH = os.path.join(ROOT_DIR, "SKILLS.md")

load_shared_environment()


def load_skills_markdown() -> str:
    if not os.path.exists(SKILLS_MD_PATH):
        return ""
    with open(SKILLS_MD_PATH, "r", encoding="utf-8") as f:
        return f.read()


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

    if action not in {"chat", "python_code", "github_action"}:
        return {"action": "chat", "skill": "fallback_chat", "reason": "router_invalid_action"}

    normalized = {"action": action, "skill": skill, "reason": reason}
    if url:
        normalized["url"] = url
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


def decide_action(user_prompt: str, skills_md: str) -> dict:
    system_prompt = (
        "You are an autopilot router. "
        "Use the skill definitions below to choose the best action. "
        "Return ONLY JSON with this schema: "
        '{"action":"chat|python_code|github_action","skill":"skill_name","reason":"short reason","url":"optional_target_url"}.\n\n'
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
    skills_md = load_skills_markdown()

    # URL + 아카이브 의도는 LLM 라우터를 우회해 즉시 GitHub Action 실행
    detected_url = _extract_first_url(user_prompt)
    if detected_url and _has_archive_intent(user_prompt):
        result = trigger_content_crawler_workflow(detected_url)
        print(result)
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