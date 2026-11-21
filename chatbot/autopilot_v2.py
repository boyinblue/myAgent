import json
import logging
import os
import runpy
import sys
import re
import time
import shlex
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
BOT_STARTED_AT = time.time()
MODEL_STATE_PATH = Path(PROJECT_ROOT) / ".runtime" / "autopilot_model_state.json"
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


def get_skills_prompt_max_chars() -> int:
    value = get_config_value(
        "autopilot.skills_prompt_max_chars",
        os.getenv("SKILLS_PROMPT_MAX_CHARS", DEFAULT_SKILLS_PROMPT_MAX_CHARS),
    )
    try:
        parsed = int(value)
        return max(500, parsed)
    except (TypeError, ValueError):
        return DEFAULT_SKILLS_PROMPT_MAX_CHARS


def build_skills_context(raw_skills_md: str, max_chars: int) -> str:
    text = (raw_skills_md or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...\n[TRUNCATED]"


def ask_ollama(prompt: str, system_prompt: str, model: str = "gemma2:9b") -> str:
    url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434") + "/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return str((data.get("message") or {}).get("content") or "").strip()
    except Exception as exc:
        raise RuntimeError(f"Ollama 요청 실패: {exc}") from exc


def ask_gemini(prompt: str, system_prompt: str, model: str = "gemini-1.5-flash") -> str:
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")

    fallback_models = [model] if model else []
    models_to_try = list(dict.fromkeys(fallback_models))

    data = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": prompt}]}],
    }

    last_exc: Exception | None = None
    for idx, target_model in enumerate(models_to_try):
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{target_model}:generateContent"
        )
        max_retries = 3 if idx == 0 else 1
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    headers={"x-goog-api-key": api_key},
                    json=data,
                    timeout=120,
                )
                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                response.raise_for_status()
                body = response.json()
                candidates = body.get("candidates", [])
                if not candidates:
                    return ""
                parts = candidates[0].get("content", {}).get("parts", [])
                texts = [p.get("text", "") for p in parts if p.get("text")]
                return "\n".join(texts).strip()
            except Exception as exc:
                last_exc = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in (401, 403):
                    raise RuntimeError(
                        f"Gemini 인증 실패 (HTTP {status}). GEMINI_API_KEY를 확인하세요."
                    ) from exc
                if status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                break

    raise RuntimeError(f"Gemini 요청 실패: {last_exc}") from last_exc


def ask_model(prompt: str, system_prompt: str) -> str:
    provider = str(
        get_config_value(
            "autopilot.provider",
            "ollama",
        )
    ).strip().lower()

    if provider == "gemini":
        configured = get_config_value("autopilot.models.gemini", ["gemini-flash-lite-latest"])
        models = configured if isinstance(configured, list) else [configured]
        try:
            if MODEL_STATE_PATH.is_file():
                last_model = json.loads(MODEL_STATE_PATH.read_text(encoding="utf-8")).get("last_successful_gemini_model")
                if last_model in models:
                    models = [last_model, *[item for item in models if item != last_model]]
        except Exception:
            pass
        last_error = None
        for model in models:
            try:
                result = ask_gemini(prompt, system_prompt, model=str(model))
                MODEL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                MODEL_STATE_PATH.write_text(json.dumps({"last_successful_gemini_model": model}), encoding="utf-8")
                return result
            except Exception as exc:
                last_error = exc
                continue
        logging.warning("All Gemini models failed; falling back to Ollama: %s", last_error)

    model = str(
        get_config_value(
            "autopilot.models.ollama",
            os.getenv("OLLAMA_MODEL", "gemma2:9b"),
        )
    )
    return ask_ollama(prompt, system_prompt, model=model)


def _strip_leading_router_json(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    # 1) 선두 ```json ... ``` 코드 펜스 제거
    cleaned = re.sub(
        r"^```(?:json)?\s*\{[\s\S]*?\}\s*```\s*",
        "",
        cleaned,
        count=1,
        flags=re.IGNORECASE,
    ).strip()

    # 2) 선두에 바로 붙은 JSON 객체가 있는 경우 제거
    if cleaned.startswith("{"):
        decoder = json.JSONDecoder()
        try:
            obj, end_idx = decoder.raw_decode(cleaned)
            if isinstance(obj, dict) and {"action", "skill"} & set(obj.keys()):
                cleaned = cleaned[end_idx:].lstrip(" \t\r\n-:")
        except json.JSONDecodeError:
            pass

    return cleaned.strip()


def answer_chat(user_prompt: str, skills_md: str) -> str:
    system_prompt = (
        "You are a helpful assistant. "
        "Use the skill definitions for tone and boundaries, "
        "but respond ONLY in natural plain text for the user. "
        "Do NOT output JSON objects, router metadata, or ```json code blocks.\n\n"
        f"[SKILL_DEFINITIONS]\n{skills_md}"
    )
    raw_reply = ask_model(user_prompt, system_prompt)
    return _strip_leading_router_json(raw_reply)
