import io
import os
import logging
import sys
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

# 환경변수 설정(위치 : ../.env)
load_dotenv(os.path.join('..', '.env'))
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID', 0))

print(f"[*] Telegram Bot Token: {'Set' if TOKEN else 'Not Set'}")
print(f"[*] Telegram Chat ID: {'Set' if CHAT_ID else 'Not Set'}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.effective_chat.id

    # 🔐 화이트리스트 체크: 본인이 아니면 무시 (보안)
    if chat_id != CHAT_ID:
        logging.warning(f"Unauthorized access attempt by ID: {chat_id}")
        return
    
    await context.bot.send_message(chat_id=chat_id, text=f"추론중...")

    # 2. 다른 모듈의 함수를 실행하고 표준 출력을 가져오는 핵심 로직
    f = io.StringIO()
    try:
        # redirect_stdout을 사용하여 해당 블록 내의 모든 print를 f에 저장
        with redirect_stdout(f):
            # 모듈 내부 함수 직접 호출
            autopilot.ask_ollama_and_run(user_text)
        
        # 가로챈 출력 결과 가져오기
        output = f.getvalue().strip()

        # 3. 결과 메시지 송신
        if output:
            # 텔레그램 메시지 길이 제한(4096자)을 고려하여 슬라이싱 가능
            await context.bot.send_message(chat_id=chat_id, text=f"{output[:4000]}")
        else:
            await context.bot.send_message(chat_id=chat_id, text="✅ 작업은 완료되었으나 출력된 로그가 없습니다.")

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ 에러 발생: {str(e)}")
    finally:
        f.close()

if __name__ == '__main__':
    # BotFather에게 받은 토큰 입력
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # 메시지를 받으면 handle_message 함수 실행
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    application.add_handler(echo_handler)
    
    print("[*] 텔레그램 봇이 가동되었습니다.")
    application.run_polling()