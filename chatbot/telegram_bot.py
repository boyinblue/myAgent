import io
import os
import logging
import sys
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from contextlib import redirect_stdout
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# 1. 경로 설정 및 모듈 import 준비
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# AI_Skills 디렉토리를 경로에 추가하여 autopilot 모듈을 직접 import
ai_skills_dir = os.path.join(parent_dir, "AI_Skills")
if ai_skills_dir not in sys.path:
    sys.path.insert(0, ai_skills_dir)

try:
    # autopilot.py를 모듈로 직접 가져옴
    import autopilot
except ImportError:
    autopilot = None

# 로그 설정 (FW 디버깅용 로그처럼)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# 환경변수 설정(위치 : 프로젝트 루트의 .env)
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

TOKEN = (os.getenv('TELEGRAM_BOT_TOKEN') or '').strip()
chat_id_raw = (os.getenv('TELEGRAM_CHAT_ID') or '').strip()
CHAT_ID = int(chat_id_raw) if chat_id_raw.isdigit() else 0

print(f"[*] Telegram Bot Token: {'Set' if TOKEN else 'Not Set'}")
print(f"[*] Telegram Chat ID: {'Set' if CHAT_ID else 'Not Set'}")


def _resolve_chatbot_log_file() -> Path:
    custom_dir = (os.getenv("CHATBOT_LOG_DIR") or "").strip()
    if custom_dir:
        log_dir = Path(custom_dir)
    else:
        local_app_data = (os.getenv("LOCALAPPDATA") or "").strip()
        if local_app_data:
            log_dir = Path(local_app_data) / "myAgent" / "chatbot_logs"
        else:
            log_dir = Path(tempfile.gettempdir()) / "myAgent" / "chatbot_logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "telegram_bot.jsonl"


CHATBOT_LOG_FILE = _resolve_chatbot_log_file()
print(f"[*] Chatbot runtime log file: {CHATBOT_LOG_FILE}")


def _append_chatbot_log(event: str, chat_id: int, user_text: str = "", bot_output: str = "", error: str = "") -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "chat_id": chat_id,
        "user_text": user_text,
        "bot_output": bot_output,
        "error": error,
    }
    try:
        with CHATBOT_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as log_error:
        logging.error(f"Failed to write chatbot runtime log: {log_error}")


_append_chatbot_log(event="startup", chat_id=CHAT_ID)


def validate_runtime_config() -> bool:
    if not os.path.exists(dotenv_path):
        print(f"[!] .env 파일을 찾을 수 없습니다: {dotenv_path}")
        _append_chatbot_log(event="config_invalid", chat_id=CHAT_ID, error=f"missing_env:{dotenv_path}")
        return False

    if not TOKEN:
        print("[!] TELEGRAM_BOT_TOKEN이 비어 있습니다. .env를 확인하세요.")
        _append_chatbot_log(event="config_invalid", chat_id=CHAT_ID, error="missing_TELEGRAM_BOT_TOKEN")
        return False

    if ':' not in TOKEN:
        print("[!] TELEGRAM_BOT_TOKEN 형식이 올바르지 않습니다. BotFather에서 새 토큰을 발급받아 설정하세요.")
        _append_chatbot_log(event="config_invalid", chat_id=CHAT_ID, error="invalid_TELEGRAM_BOT_TOKEN_format")
        return False

    if not CHAT_ID:
        print("[!] TELEGRAM_CHAT_ID가 비어있거나 숫자가 아닙니다. .env를 확인하세요.")
        _append_chatbot_log(event="config_invalid", chat_id=CHAT_ID, error="missing_or_invalid_TELEGRAM_CHAT_ID")
        return False

    return True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.effective_chat.id

    # 🔐 화이트리스트 체크: 본인이 아니면 무시 (보안)
    if chat_id != CHAT_ID:
        logging.warning(f"Unauthorized access attempt by ID: {chat_id}")
        _append_chatbot_log(
            event="unauthorized_access",
            chat_id=chat_id,
            user_text=user_text,
        )
        return
    
    await context.bot.send_message(chat_id=chat_id, text=f"추론중...")

    # 2. 다른 모듈의 함수를 실행하고 표준 출력을 가져오는 핵심 로직
    f = io.StringIO()
    try:
        # redirect_stdout을 사용하여 해당 블록 내의 모든 print를 f에 저장
        with redirect_stdout(f):
            # 모듈 내부 함수 직접 호출

            autopilot.autopilot(user_text)
        
        # 가로챈 출력 결과 가져오기
        output = f.getvalue().strip()

        # 3. 결과 메시지 송신
        if output:
            # 텔레그램 메시지 길이 제한(4096자)을 고려하여 슬라이싱 가능
            await context.bot.send_message(chat_id=chat_id, text=f"{output[:4000]}")
            _append_chatbot_log(
                event="response_sent",
                chat_id=chat_id,
                user_text=user_text,
                bot_output=output,
            )
        else:
            await context.bot.send_message(chat_id=chat_id, text="✅ 작업은 완료되었으나 출력된 로그가 없습니다.")
            _append_chatbot_log(
                event="empty_output",
                chat_id=chat_id,
                user_text=user_text,
            )

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ 에러 발생: {str(e)}")
        _append_chatbot_log(
            event="handler_exception",
            chat_id=chat_id,
            user_text=user_text,
            error=str(e),
        )
    finally:
        f.close()

if __name__ == '__main__':
    if not validate_runtime_config():
        sys.exit(1)

    application = ApplicationBuilder().token(TOKEN).build()
    
    # 메시지를 받으면 handle_message 함수 실행
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    application.add_handler(echo_handler)
    
    print("[*] 텔레그램 봇이 가동되었습니다.")
    application.run_polling()