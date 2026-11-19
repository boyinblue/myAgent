import json
import os
import time
from pathlib import Path
import requests

DEFAULT_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]
SYSTEM_PROMPT = "간결하고 정확하게 한국어로 답변하세요."


def load_dotenv_if_exists(env_path: Path) -> None:
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def load_gemini_model(config_path: Path) -> str:
    default_model = "gemini-flash-lite-latest"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        model = config.get("autopilot", {}).get("models", {}).get("gemini")
        return str(model or default_model).strip()
    except (OSError, json.JSONDecodeError, AttributeError):
        return default_model


def call_gemini(contents: list[dict], system_prompt: str, primary_model: str) -> str:
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    models = list(dict.fromkeys([m for m in [primary_model, *DEFAULT_MODELS] if m]))
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
    }

    last_exc: Exception | None = None
    for idx, model in enumerate(models):
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        max_retries = 3 if idx == 0 else 1
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    url,
                    headers={"x-goog-api-key": api_key},
                    json=payload,
                    timeout=120,
                )
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    resp.raise_for_status()
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return ""
                parts = candidates[0].get("content", {}).get("parts", [])
                return "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
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


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv_if_exists(project_root / ".env")

    model = load_gemini_model(project_root / "config.json")
    history: list[dict] = []

    print(f"Gemini CLI 시작 (model={model}). 종료: exit / quit, 대화 초기화: clear")

    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료")
            break

        if not user_input:
            continue
        cmd = user_input.lower()
        if cmd in {"exit", "quit"}:
            print("종료")
            break
        if cmd == "clear":
            history.clear()
            print("대화 이력을 초기화했습니다.")
            continue

        turn = {"role": "user", "parts": [{"text": user_input}]}
        contents = [*history, turn]

        try:
            reply = call_gemini(contents, SYSTEM_PROMPT, model)
        except Exception as exc:
            print(f"[오류] {exc}")
            continue

        if reply:
            history.append(turn)
            history.append({"role": "model", "parts": [{"text": reply}]})
            # 최근 10턴(20개 메시지)만 유지해 컨텍스트 크기 제한
            if len(history) > 20:
                history = history[-20:]
        print(f"Gemini> {reply}")


if __name__ == "__main__":
    main()
