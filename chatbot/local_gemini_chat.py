import json
import os
import time
from pathlib import Path
import requests

try:
    from .gemini_code_editor import (
        EDITOR_SYSTEM_PROMPT,
        EditSession,
        build_edit_prompt,
        extract_python_script,
    )
except ImportError:  # python chatbot/local_gemini_chat.py 로 직접 실행할 때
    from gemini_code_editor import (
        EDITOR_SYSTEM_PROMPT,
        EditSession,
        build_edit_prompt,
        extract_python_script,
    )

DEFAULT_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]
SYSTEM_PROMPT = "간결하고 정확하게 한국어로 답변하세요."
MAX_EDIT_ATTEMPTS = 3


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

    print(
        f"Gemini CLI 시작 (model={model}). 종료: exit / quit, 대화 초기화: clear\n"
        "소스 편집: /edit <요청> (생성 스크립트와 diff 확인 후 반영)"
    )

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

        if user_input.startswith("/edit "):
            edit_request = user_input[6:].strip()
            if not edit_request:
                print("사용법: /edit <편집 요청>")
                continue
            try:
                prompt = build_edit_prompt(project_root, edit_request)
                edit_contents = [{"role": "user", "parts": [{"text": prompt}]}]
                session = None
                diff = ""

                for attempt in range(1, MAX_EDIT_ATTEMPTS + 1):
                    reply = call_gemini(edit_contents, EDITOR_SYSTEM_PROMPT, model)
                    try:
                        script = extract_python_script(reply)
                        script_path = project_root / ".runtime" / "gemini_generated_edit.py"
                        script_path.parent.mkdir(parents=True, exist_ok=True)
                        script_path.write_text(script + "\n", encoding="utf-8")
                        print(
                            f"\n[Gemini 생성 스크립트 {attempt}/{MAX_EDIT_ATTEMPTS}]\n"
                            f"{script}\n[저장 위치] {script_path}"
                        )

                        candidate = EditSession(project_root)
                        candidate.run(script)
                        candidate_diff = candidate.diff()
                        if not candidate_diff:
                            raise ValueError("스크립트를 실행했지만 변경 사항이 없습니다.")
                        session = candidate
                        diff = candidate_diff
                        break
                    except Exception as edit_exc:
                        if attempt >= MAX_EDIT_ATTEMPTS:
                            raise RuntimeError(
                                f"{MAX_EDIT_ATTEMPTS}회 수정 후에도 실패했습니다: {edit_exc}"
                            ) from edit_exc
                        print(
                            f"[편집 스크립트 오류] {edit_exc}\n"
                            "오류 내용을 Gemini에 전달해 스크립트를 다시 생성합니다."
                        )
                        edit_contents.extend([
                            {"role": "model", "parts": [{"text": reply}]},
                            {
                                "role": "user",
                                "parts": [{
                                    "text": (
                                        "방금 생성한 스크립트 실행에 실패했습니다. "
                                        "아래 오류를 해결한 전체 Python 스크립트를 다시 작성하세요.\n\n"
                                        f"오류: {type(edit_exc).__name__}: {edit_exc}"
                                    )
                                }],
                            },
                        ])

                if session is None:
                    raise RuntimeError("유효한 편집 스크립트를 생성하지 못했습니다.")
                print(f"\n[예상 변경 사항]\n{diff}")
                answer = input("\n이 변경을 적용할까요? [y/N] ").strip().lower()
                if answer not in {"y", "yes"}:
                    print("변경을 취소했습니다.")
                    continue
                session.apply()
                print(f"{len(session.pending)}개 파일의 변경을 적용했습니다.")
            except Exception as exc:
                print(f"[편집 오류] {exc}")
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
