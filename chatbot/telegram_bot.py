import io
import os
import logging
import sys
import json
import asyncio
import importlib
import subprocess
import tempfile
import atexit
import ctypes
import math
import re
import base64
import mimetypes
import sqlite3
import random
from typing import Optional, Tuple
from html import unescape
from datetime import datetime, timezone
from pathlib import Path
from contextlib import redirect_stdout
from urllib.parse import urlparse
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 1. 경로 설정 및 모듈 import 준비
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# chatbot 디렉토리를 우선 경로에 추가 (이동된 스킬 모듈)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# AI_Skills 디렉토리는 하위 호환 fallback으로 유지
ai_skills_dir = os.path.join(parent_dir, "AI_Skills")
if ai_skills_dir not in sys.path:
    sys.path.append(ai_skills_dir)

try:
    # autopilot.py를 모듈로 직접 가져옴
    import autopilot
except ImportError:
    autopilot = None


def _reload_ai_skill_modules() -> bool:
    """스킬 모듈을 핫리로드하여 재시작 없이 최신 코드를 반영합니다."""
    global autopilot

    module_order = [
        "runtime_config",
        "shared_credentials",
        "issue",
        "diary",
        "post_search",
        "post_validate",
        "dashboard",
        "autopilot",
    ]

    missing_modules = []

    for module_name in module_order:
        try:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing_modules.append(module_name)
            continue
        except Exception as exc:
            logging.error(f"스킬 모듈 로드 실패({module_name}): {exc}")
            if module_name == "autopilot":
                return False

    autopilot = sys.modules.get("autopilot")
    if autopilot is None:
        logging.error("autopilot 모듈 로드 실패")
        return False

    if missing_modules:
        logging.warning(f"선택 모듈 누락(동작 계속): {', '.join(missing_modules)}")

    return True

# 로그 설정 (FW 디버깅용 로그처럼)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# 환경변수 설정(위치 : 프로젝트 루트의 .env)
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

TOKEN = (os.getenv('TELEGRAM_BOT_TOKEN') or '').strip()
chat_id_raw = (os.getenv('TELEGRAM_CHAT_ID') or '').strip()
CHAT_ID = int(chat_id_raw) if chat_id_raw.isdigit() else 0

EXPECTED_VENV_PYTHON = str((Path(parent_dir) / ".venv" / "Scripts" / "python.exe").resolve())
CURRENT_PYTHON = str(Path(sys.executable).resolve())

print(f"[*] Telegram Bot Token: {'Set' if TOKEN else 'Not Set'}")
print(f"[*] Telegram Chat ID: {'Set' if CHAT_ID else 'Not Set'}")
print(f"[*] Python executable: {CURRENT_PYTHON}")


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
BOT_LOCK_FILE = CHATBOT_LOG_FILE.with_name("telegram_bot.lock")
_WINDOWS_MUTEX_HANDLE = None
_WINDOWS_MUTEX_NAME = "Global\\myAgent_telegram_bot_singleton"

GDRIVE_CREDENTIAL_FILE = Path(parent_dir) / "google_oauth2_credentials.json"
GDRIVE_TOKEN_FILE = Path(parent_dir) / "google_oauth2_token.json"
GDRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.readonly",
]
GDRIVE_PAGE_SIZE = 10
GDRIVE_SELECTED_TARGETS: dict[int, dict] = {}
ARCHIVE_DB_PATH = Path(os.getenv("ARCHIVE_DB", Path(parent_dir) / "archive" / "archive_index.db"))
RANDOM_IMAGE_COMMANDS = {"/randomimage", "/randimage", "/image random", "/img random"}


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False

    # Windows에서는 os.kill(pid, 0)가 신뢰되지 않는 경우가 있어 tasklist 우선 사용
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            output = (result.stdout or "").strip()
            if not output or "No tasks are running" in output:
                return False
            return str(pid) in output
        except Exception:
            return False

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _acquire_single_instance_lock(lock_path: Path) -> bool:
    current_pid = os.getpid()

    # 1) Windows 전용 전역 mutex (가장 우선, 가장 신뢰성 높음)
    if os.name == "nt":
        global _WINDOWS_MUTEX_HANDLE
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, _WINDOWS_MUTEX_NAME)
        if not handle:
            print("[!] Windows mutex 생성 실패")
            return False
        # ERROR_ALREADY_EXISTS = 183
        if kernel32.GetLastError() == 183:
            print("[!] 이미 텔레그램 봇이 실행 중입니다. (Windows mutex)")
            return False
        _WINDOWS_MUTEX_HANDLE = handle

    # 2) 보조 파일 락 (진단/가시성 목적)
    def _try_create_lock() -> bool:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(str(current_pid))
            return True
        except FileExistsError:
            return False

    if _try_create_lock():
        return True

    existing_pid = 0
    try:
        existing_pid_raw = lock_path.read_text(encoding="utf-8").strip()
        existing_pid = int(existing_pid_raw)
    except Exception:
        existing_pid = 0

    if existing_pid and existing_pid != current_pid and _is_pid_alive(existing_pid):
        print(f"[!] 이미 텔레그램 봇이 실행 중입니다. (PID: {existing_pid})")
        print(f"[!] 중복 실행을 방지하기 위해 종료합니다. 락 파일: {lock_path}")
        return False

    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass

    if _try_create_lock():
        return True

    print(f"[!] 락 파일 획득 실패: {lock_path}")
    return False


def _release_single_instance_lock(lock_path: Path) -> None:
    # 파일 락 해제
    try:
        if lock_path.exists():
            lock_pid_raw = lock_path.read_text(encoding="utf-8").strip()
            lock_pid = int(lock_pid_raw) if lock_pid_raw.isdigit() else -1
            if lock_pid == os.getpid():
                lock_path.unlink(missing_ok=True)
    except Exception:
        pass

    # Windows mutex 해제
    if os.name == "nt":
        global _WINDOWS_MUTEX_HANDLE
        try:
            if _WINDOWS_MUTEX_HANDLE:
                ctypes.windll.kernel32.ReleaseMutex(_WINDOWS_MUTEX_HANDLE)
                ctypes.windll.kernel32.CloseHandle(_WINDOWS_MUTEX_HANDLE)
                _WINDOWS_MUTEX_HANDLE = None
        except Exception:
            pass


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


def _extract_html_title(html_text: str, fallback: str) -> str:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    return unescape((title_match.group(1).strip() if title_match else fallback))


def _html_to_plain_text(html_text: str) -> str:
    text = html_text
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|h1|h2|h3|h4|h5|h6|tr|section|article)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_google_keep_text(html_text: str) -> str:
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html_text, flags=re.IGNORECASE | re.DOTALL)
    body_html = body_match.group(1) if body_match else html_text

    # Google Keep 내보내기는 체크리스트/메모 본문이 body에 단순하게 들어있는 경우가 많다.
    text = _html_to_plain_text(body_html)
    text = re.sub(r"\n?\s*Google Keep\s*\n?", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_html_image_sources(html_text: str) -> list[str]:
    matches = re.findall(r"<img[^>]+src=[\"']([^\"']+)[\"']", html_text, flags=re.IGNORECASE)
    unique: list[str] = []
    seen = set()
    for src in matches:
        value = (src or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _decode_data_uri_image(src: str) -> Optional[tuple[io.BytesIO, str]]:
    match = re.match(r"data:(image/[^;]+);base64,(.+)", src, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None

    mime_type = match.group(1).lower()
    encoded = re.sub(r"\s+", "", match.group(2))
    try:
        raw = base64.b64decode(encoded)
    except Exception:
        return None

    ext = mimetypes.guess_extension(mime_type) or ".bin"
    bio = io.BytesIO(raw)
    bio.name = f"keep_image{ext}"
    return bio, mime_type


def _find_sibling_drive_file(service, parent_id: str, file_name: str) -> Optional[dict]:
    safe_name = file_name.replace("'", "\\'")
    resp = service.files().list(
        q=f"'{parent_id}' in parents and name = '{safe_name}' and trashed = false",
        fields="files(id,name,mimeType)",
        pageSize=5,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = resp.get("files", [])
    return files[0] if files else None


async def _send_google_keep_images(context: ContextTypes.DEFAULT_TYPE, chat_id: int, service, parent_id: Optional[str], html_text: str) -> int:
    image_sources = _extract_html_image_sources(html_text)
    if not image_sources:
        return 0

    sent_count = 0
    for src in image_sources[:5]:
        if src.startswith("data:image/"):
            decoded = _decode_data_uri_image(src)
            if not decoded:
                continue
            image_doc, _ = decoded
            try:
                await context.bot.send_photo(chat_id=chat_id, photo=image_doc)
                sent_count += 1
            except Exception:
                continue
            continue

        parsed = urlparse(src)
        if parsed.scheme in {"http", "https"}:
            try:
                await context.bot.send_photo(chat_id=chat_id, photo=src)
                sent_count += 1
            except Exception:
                continue
            continue

        if not parent_id:
            continue

        file_name = Path(parsed.path or src).name
        if not file_name:
            continue

        sibling = _find_sibling_drive_file(service, parent_id, file_name)
        if not sibling:
            continue

        try:
            raw = service.files().get_media(fileId=sibling["id"], supportsAllDrives=True).execute()
            photo = io.BytesIO(raw if isinstance(raw, bytes) else bytes(str(raw), "utf-8"))
            photo.name = sibling.get("name") or file_name
            await context.bot.send_photo(chat_id=chat_id, photo=photo)
            sent_count += 1
        except Exception:
            continue

    return sent_count


def _get_gdrive_service_non_interactive() -> Tuple[Optional[object], str]:
    """OAuth 토큰 기반으로 Google Drive 서비스 객체를 반환합니다."""
    if not GDRIVE_CREDENTIAL_FILE.exists():
        return None, "❌ google_oauth2_credentials.json 파일이 없습니다."

    if not GDRIVE_TOKEN_FILE.exists():
        return None, "⏳ OAuth 인증 토큰이 없습니다.\n터미널에서 1회 인증: python tools/gdrive.py --init-auth"

    try:
        creds = Credentials.from_authorized_user_file(str(GDRIVE_TOKEN_FILE), GDRIVE_SCOPES)
    except Exception as exc:
        return None, f"❌ OAuth 토큰 로드 실패: {exc}"

    try:
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                return None, "⏳ OAuth 토큰이 유효하지 않습니다.\npython tools/gdrive.py --init-auth 로 재인증해주세요."

        service = build("drive", "v3", credentials=creds)
        return service, ""
    except Exception as exc:
        return None, f"❌ 구글 드라이브 인증 실패: {exc}"


def _gdrive_get_folder_info(service, folder_id: str) -> Tuple[str, Optional[str]]:
    if folder_id == "root":
        return "내 드라이브", None

    meta = service.files().get(
        fileId=folder_id,
        fields="id,name,parents",
        supportsAllDrives=True,
    ).execute()
    parent_id = (meta.get("parents") or [None])[0]
    return meta.get("name", "(이름없음)"), parent_id


def _gdrive_list_children(service, folder_id: str) -> list[dict]:
    resp = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id,name,mimeType,modifiedTime)",
        orderBy="folder,name_natural",
        pageSize=200,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    return resp.get("files", [])


def _gdrive_make_browser_text(folder_name: str, folder_id: str, page: int, total_pages: int, total_items: int) -> str:
    return (
        "📁 GDrive 브라우저\n"
        f"폴더: {folder_name}\n"
        f"ID: {folder_id}\n"
        f"페이지: {page + 1}/{max(1, total_pages)}  (항목 {total_items}개)\n\n"
        "- 폴더 버튼: 하위 폴더 진입\n"
        "- 파일 버튼: 해당 파일 연결\n"
        "- '현재 폴더 연결': 현재 폴더 ID 연결"
    )


def _truncate_label(name: str, limit: int = 28) -> str:
    text = (name or "(이름없음)").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


async def _send_random_local_image(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """local_images 테이블에서 랜덤 이미지를 하나 선택해 전송합니다."""
    if not ARCHIVE_DB_PATH.exists():
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ 아카이브 DB가 없습니다. 먼저 로컬 이미지 인덱싱을 실행해주세요.",
        )
        return

    conn = None
    try:
        conn = sqlite3.connect(str(ARCHIVE_DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        candidates = cur.execute(
            """
            SELECT file_path, file_name, location, comment
            FROM local_images
            ORDER BY RANDOM()
            LIMIT 30
            """
        ).fetchall()
    except sqlite3.Error as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ DB 조회 실패: {exc}")
        return
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not candidates:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "📭 등록된 로컬 이미지가 없습니다.\n"
                "예: python content-crawler/main.py --no-archive --index-local-images --local-image-root <이미지폴더>"
            ),
        )
        return

    random.shuffle(candidates)
    selected = None
    selected_path = None
    for row in candidates:
        file_path = (row["file_path"] or "").strip()
        if not file_path:
            continue
        path_obj = Path(file_path)
        if path_obj.exists() and path_obj.is_file():
            selected = row
            selected_path = path_obj
            break

    if selected is None or selected_path is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ DB에는 이미지가 있지만 실제 파일을 찾지 못했습니다. 경로를 다시 인덱싱해주세요.",
        )
        return

    caption = (
        "🎲 랜덤 이미지\n"
        f"파일: {selected['file_name'] or selected_path.name}\n"
        f"위치: {selected['location'] or '(없음)'}\n"
        f"코멘트: {selected['comment'] or '(없음)'}"
    )

    suffix = selected_path.suffix.lower()
    try:
        with selected_path.open("rb") as f:
            if suffix in {".svg"}:
                await context.bot.send_document(chat_id=chat_id, document=f, caption=caption)
            else:
                await context.bot.send_photo(chat_id=chat_id, photo=f, caption=caption)
        _append_chatbot_log(
            event="random_image_sent",
            chat_id=chat_id,
            user_text="/randomimage",
            bot_output=str(selected_path),
        )
    except Exception as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ 이미지 전송 실패: {exc}")


def _gdrive_make_keyboard(folder_id: str, page: int, items: list[dict], parent_id: Optional[str]) -> InlineKeyboardMarkup:
    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / GDRIVE_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))

    start = page * GDRIVE_PAGE_SIZE
    end = start + GDRIVE_PAGE_SIZE
    page_items = items[start:end]

    rows: list[list[InlineKeyboardButton]] = []
    for item in page_items:
        item_id = item.get("id", "")
        name = _truncate_label(item.get("name", ""))
        mime_type = item.get("mimeType", "")
        if mime_type == "application/vnd.google-apps.folder":
            rows.append([InlineKeyboardButton(f"📁 {name}", callback_data=f"gdrv|ls|{item_id}|0")])
        else:
            rows.append([InlineKeyboardButton(f"📄 {name}", callback_data=f"gdrv|pick|{item_id}")])

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀ 이전", callback_data=f"gdrv|ls|{folder_id}|{page - 1}"))
    nav_row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="gdrv|noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("다음 ▶", callback_data=f"gdrv|ls|{folder_id}|{page + 1}"))
    rows.append(nav_row)

    action_row: list[InlineKeyboardButton] = []
    if parent_id:
        action_row.append(InlineKeyboardButton("⬆ 상위 폴더", callback_data=f"gdrv|ls|{parent_id}|0"))
    action_row.append(InlineKeyboardButton("✅ 현재 폴더 연결", callback_data=f"gdrv|pick|{folder_id}"))
    rows.append(action_row)

    rows.append([InlineKeyboardButton("🔄 새로고침", callback_data=f"gdrv|ls|{folder_id}|{page}")])
    return InlineKeyboardMarkup(rows)


async def _send_gdrive_browser(chat_id: int, context: ContextTypes.DEFAULT_TYPE, folder_id: str = "root", page: int = 0) -> None:
    service, err = _get_gdrive_service_non_interactive()
    if service is None:
        await context.bot.send_message(chat_id=chat_id, text=err)
        return

    try:
        folder_name, parent_id = _gdrive_get_folder_info(service, folder_id)
        items = _gdrive_list_children(service, folder_id)
    except HttpError as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ GDrive 조회 실패: {exc}")
        return
    except Exception as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ GDrive 조회 오류: {exc}")
        return

    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / GDRIVE_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))

    text = _gdrive_make_browser_text(folder_name, folder_id, page, total_pages, total_items)
    keyboard = _gdrive_make_keyboard(folder_id, page, items, parent_id)
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)


async def _update_gdrive_browser(query, folder_id: str, page: int) -> None:
    service, err = _get_gdrive_service_non_interactive()
    if service is None:
        await query.edit_message_text(text=err)
        return

    try:
        folder_name, parent_id = _gdrive_get_folder_info(service, folder_id)
        items = _gdrive_list_children(service, folder_id)
    except HttpError as exc:
        await query.edit_message_text(text=f"❌ GDrive 조회 실패: {exc}")
        return
    except Exception as exc:
        await query.edit_message_text(text=f"❌ GDrive 조회 오류: {exc}")
        return

    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / GDRIVE_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))

    text = _gdrive_make_browser_text(folder_name, folder_id, page, total_pages, total_items)
    keyboard = _gdrive_make_keyboard(folder_id, page, items, parent_id)
    await query.edit_message_text(text=text, reply_markup=keyboard)


async def _select_gdrive_target(query, chat_id: int, target_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    service, err = _get_gdrive_service_non_interactive()
    if service is None:
        await context.bot.send_message(chat_id=chat_id, text=err)
        return

    try:
        meta = service.files().get(
            fileId=target_id,
            fields="id,name,mimeType,webViewLink,parents",
            supportsAllDrives=True,
        ).execute()
    except HttpError as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ 항목 조회 실패: {exc}")
        return
    except Exception as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ 항목 조회 오류: {exc}")
        return

    mime_type = meta.get("mimeType", "")
    target_type = "folder" if mime_type == "application/vnd.google-apps.folder" else "file"
    GDRIVE_SELECTED_TARGETS[chat_id] = {
        "id": meta.get("id"),
        "name": meta.get("name"),
        "type": target_type,
        "webViewLink": meta.get("webViewLink"),
    }

    is_html = (
        target_type == "file"
        and (
            (meta.get("mimeType") or "").lower() in {"text/html", "application/xhtml+xml"}
            or (meta.get("name") or "").lower().endswith((".html", ".htm"))
        )
    )
    if not is_html:
        return

    try:
        raw = service.files().get_media(fileId=target_id, supportsAllDrives=True).execute()
        if isinstance(raw, bytes):
            html_text = raw.decode("utf-8", errors="replace")
        else:
            html_text = str(raw)
    except HttpError as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ HTML 다운로드 실패: {exc}")
        return
    except Exception as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ HTML 처리 실패: {exc}")
        return

    title = _extract_html_title(html_text, meta.get("name") or "(제목 없음)")
    text = _extract_google_keep_text(html_text)

    if not text:
        text = "(본문 텍스트를 추출하지 못했습니다.)"

    preview = text[:3000]
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "🧾 HTML 미리보기\n"
            f"제목: {title}\n"
            f"파일: {meta.get('name', '(이름없음)')}\n\n"
            f"{preview}"
        ),
    )

    image_count = await _send_google_keep_images(
        context=context,
        chat_id=chat_id,
        service=service,
        parent_id=(meta.get("parents") or [None])[0],
        html_text=html_text,
    )

    try:
        doc = io.BytesIO(html_text.encode("utf-8", errors="replace"))
        doc.name = meta.get("name") or "preview.html"
        await context.bot.send_document(
            chat_id=chat_id,
            document=doc,
            caption="📎 원본 HTML 파일",
        )
    except Exception as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ 원본 HTML 전송 실패: {exc}")


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


def _split_output_and_image_urls(text: str) -> Tuple[str, list[str]]:
    """출력 텍스트에서 이미지 URL 라인을 분리합니다.

    포맷 예: "   🖼️ https://..."
    """
    lines = (text or "").splitlines()
    cleaned_lines: list[str] = []
    image_urls: list[str] = []

    for line in lines:
        match = re.match(r"^\s*🖼️\s+(.+?)\s*$", line)
        if not match:
            cleaned_lines.append(line)
            continue

        candidate = match.group(1).strip()
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc and candidate not in image_urls:
            image_urls.append(candidate)
            continue

        # URL 형식이 아니면 원문 보존
        cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines).strip()
    return cleaned_text, image_urls

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.message.text is None:
        return

    user_text = update.message.text.strip()
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
    
    if user_text.lower() == "/restart":
        await context.bot.send_message(chat_id=chat_id, text="🔄 챗봇을 재시작합니다...")
        _append_chatbot_log(
            event="restart_requested",
            chat_id=chat_id,
            user_text=user_text,
        )

        def _restart_process() -> None:
            import time

            time.sleep(1)
            os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])

        asyncio.create_task(asyncio.to_thread(_restart_process))
        return

    if user_text.lower() == "/save":
        await context.bot.send_message(chat_id=chat_id, text="💾 git_auto_commit.py 실행 중입니다...")

        script_path = os.path.join(parent_dir, "tools", "git_auto_commit.py")
        if not os.path.exists(script_path):
            await context.bot.send_message(chat_id=chat_id, text="❌ 스크립트를 찾을 수 없습니다: tools/git_auto_commit.py")
            _append_chatbot_log(
                event="save_failed",
                chat_id=chat_id,
                user_text=user_text,
                error="missing_git_auto_commit_script",
            )
            return

        try:
            proc = await asyncio.wait_for(
                asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, script_path],
                    input="y\n",
                    capture_output=True,
                    text=True,
                    cwd=parent_dir,
                    timeout=180,
                    check=False,
                ),
                timeout=190,
            )
            output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            if not output:
                output = "(출력 없음)"
            await context.bot.send_message(chat_id=chat_id, text=f"✅ /save 실행 완료\n{output[:3800]}")
            _append_chatbot_log(
                event="save_executed",
                chat_id=chat_id,
                user_text=user_text,
                bot_output=output[:1000],
            )
        except asyncio.TimeoutError:
            await context.bot.send_message(chat_id=chat_id, text="⏱️ /save 실행 시간이 초과되었습니다.")
            _append_chatbot_log(
                event="save_timeout",
                chat_id=chat_id,
                user_text=user_text,
                error="save_timeout",
            )
        except Exception as exc:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ /save 실행 중 오류: {exc}")
            _append_chatbot_log(
                event="save_failed",
                chat_id=chat_id,
                user_text=user_text,
                error=str(exc),
            )
        return

    if user_text.lower().startswith("/gdrive"):
        _append_chatbot_log(
            event="gdrive_browser_opened",
            chat_id=chat_id,
            user_text=user_text,
        )
        await _send_gdrive_browser(chat_id=chat_id, context=context, folder_id="root", page=0)
        return

    if user_text.lower() in RANDOM_IMAGE_COMMANDS:
        await _send_random_local_image(chat_id=chat_id, context=context)
        return

    await context.bot.send_message(chat_id=chat_id, text=f"추론중...")

    if not _reload_ai_skill_modules() or autopilot is None:
        await context.bot.send_message(chat_id=chat_id, text="❌ 내부 모듈 로드 실패: chatbot 스킬 모듈 경로를 확인해주세요.")
        _append_chatbot_log(
            event="reload_failed",
            chat_id=chat_id,
            user_text=user_text,
            error="hot_reload_failed",
        )
        return

    def _run_autopilot_capture(prompt: str) -> str:
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                autopilot.autopilot(prompt)
            return f.getvalue().strip()
        finally:
            f.close()

    normalized_user_text = (user_text or "").strip().lower()
    inference_timeout = 180 if normalized_user_text.startswith("/gdrive") else 90

    # 2. 다른 모듈의 함수를 별도 스레드에서 실행하고 표준 출력을 가져옵니다.
    try:
        output = await asyncio.wait_for(
            asyncio.to_thread(_run_autopilot_capture, user_text),
            timeout=inference_timeout,
        )

        # 3. 결과 메시지 송신
        if output:
            cleaned_output, image_urls = _split_output_and_image_urls(output)
            reply_markup = _build_commands_keyboard() if "📌 주요 슬래시 명령어" in cleaned_output else None

            if cleaned_output:
                await context.bot.send_message(chat_id=chat_id, text=f"{cleaned_output[:4000]}", reply_markup=reply_markup)

            # 검색 결과에 포함된 이미지 URL은 실제 이미지로 전송
            for image_url in image_urls[:5]:
                try:
                    await context.bot.send_photo(chat_id=chat_id, photo=image_url)
                except Exception as photo_exc:
                    logging.warning(f"이미지 전송 실패({image_url}): {photo_exc}")
                    await context.bot.send_message(chat_id=chat_id, text=f"🖼️ 이미지 링크: {image_url}")

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

    except asyncio.TimeoutError:
        if normalized_user_text.startswith("/gdrive"):
            timeout_msg = "⏱️ /gdrive 실행 시간이 초과되었습니다. OAuth 초기 인증( python tools/gdrive.py --init-auth )을 먼저 완료한 뒤 다시 시도해 주세요."
        else:
            timeout_msg = "⏱️ 추론 시간이 초과되었습니다. 더 짧게 요청하거나 /search, /validate 같은 슬래시 명령어를 사용해 주세요."
        await context.bot.send_message(chat_id=chat_id, text=timeout_msg)
        _append_chatbot_log(
            event="inference_timeout",
            chat_id=chat_id,
            user_text=user_text,
            error=f"autopilot_timeout_{inference_timeout}s",
        )
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ 에러 발생: {str(e)}")
        _append_chatbot_log(
            event="handler_exception",
            chat_id=chat_id,
            user_text=user_text,
            error=str(e),
        )

def _build_commands_keyboard() -> InlineKeyboardMarkup:
    """도움말 메시지에 첨부할 인라인 키보드를 반환합니다."""
    rows = [
        [InlineKeyboardButton("/post random", callback_data="/post random"),
         InlineKeyboardButton("/health", callback_data="/health")],
        [InlineKeyboardButton("/search <키워드>", callback_data="/search 키워드"),
         InlineKeyboardButton("/diary 오늘", callback_data="/diary 오늘")],
        [InlineKeyboardButton("/issue create <내용>", callback_data="/issue create 내용"),
         InlineKeyboardButton("/gdrive", callback_data="/gdrive")],
        [InlineKeyboardButton("/randomimage", callback_data="/randomimage"),
         InlineKeyboardButton("/calc 1+1", callback_data="/calc 1+1")],
        [InlineKeyboardButton("/ver", callback_data="/ver")],
        [InlineKeyboardButton("/help", callback_data="/help")],
    ]
    return InlineKeyboardMarkup(rows)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """인라인 키보드 버튼 클릭 처리 — callback_data 를 명령어로 실행합니다."""
    query = update.callback_query
    await query.answer()  # 버튼 로딩 스피너 제거

    chat_id = query.message.chat_id
    command_text = query.data  # 예: "/calc 1+1"

    if command_text.startswith("gdrv|"):
        parts = command_text.split("|")
        if len(parts) < 2:
            await context.bot.send_message(chat_id=chat_id, text="❌ 잘못된 GDrive 콜백 데이터입니다.")
            return

        action = parts[1]
        target = parts[2] if len(parts) >= 3 else ""
        page_raw = parts[3] if len(parts) >= 4 else "0"

        if action == "noop":
            return

        if action == "ls":
            try:
                page = int(page_raw)
            except ValueError:
                page = 0
            await _update_gdrive_browser(query, folder_id=target or "root", page=page)
            return

        if action == "pick":
            await _select_gdrive_target(query, chat_id=chat_id, target_id=target, context=context)
            return

        await context.bot.send_message(chat_id=chat_id, text="❌ 지원되지 않는 GDrive 액션입니다.")
        return

    if command_text.strip().lower() == "/gdrive":
        await _send_gdrive_browser(chat_id=chat_id, context=context, folder_id="root", page=0)
        return

    if command_text.strip().lower() in RANDOM_IMAGE_COMMANDS:
        await _send_random_local_image(chat_id=chat_id, context=context)
        return
 
 
    # 실행 전 사용자에게 어떤 명령어가 실행되는지 알림
    await context.bot.send_message(chat_id=chat_id, text=f"▶️ {command_text}")

    if not _reload_ai_skill_modules() or autopilot is None:
        await context.bot.send_message(chat_id=chat_id, text="❌ 내부 모듈 로드 실패")
        return

    def _run() -> str:
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                autopilot.autopilot(command_text)
            return f.getvalue().strip()
        finally:
            f.close()

    cb_timeout = 180 if command_text.startswith("/gdrive") else 90
    try:
        output = await asyncio.wait_for(asyncio.to_thread(_run), timeout=cb_timeout)
        if output:
            reply_markup = _build_commands_keyboard() if "📌 주요 슬래시 명령어" in output else None
            await context.bot.send_message(chat_id=chat_id, text=output[:4000], reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=chat_id, text="✅ 완료되었으나 출력이 없습니다.")
    except asyncio.TimeoutError:
        await context.bot.send_message(chat_id=chat_id, text="⏱️ 실행 시간이 초과되었습니다.")
    except Exception as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ 오류: {exc}")

if __name__ == '__main__':
    if CURRENT_PYTHON.lower() != EXPECTED_VENV_PYTHON.lower():
        print("[!] 잘못된 Python 환경으로 실행되었습니다.")
        print(f"[!] 현재: {CURRENT_PYTHON}")
        print(f"[!] 권장: {EXPECTED_VENV_PYTHON}")
        print("[!] 아래 명령으로 실행하세요:")
        print(f"    {EXPECTED_VENV_PYTHON} chatbot/telegram_bot.py")
        sys.exit(1)

    if not _acquire_single_instance_lock(BOT_LOCK_FILE):
        _append_chatbot_log(event="startup_blocked", chat_id=CHAT_ID, error="duplicate_instance")
        sys.exit(1)

    atexit.register(_release_single_instance_lock, BOT_LOCK_FILE)

    if not validate_runtime_config():
        _release_single_instance_lock(BOT_LOCK_FILE)
        sys.exit(1)

    application = ApplicationBuilder().token(TOKEN).build()
    
    # 메시지를 받으면 handle_message 함수 실행
    echo_handler = MessageHandler(filters.TEXT, handle_message)
    application.add_handler(echo_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    print("[*] 텔레그램 봇이 가동되었습니다.")
    
    # 봇 시작 시 텔레그램으로 알림 전송
    async def send_startup_message():
        try:
            await application.bot.send_message(
                chat_id=CHAT_ID,
                text="✅ 챗봇이 시작되었습니다."
            )
        except Exception as e:
            print(f"[!] 시작 메시지 전송 실패: {e}")
    
    # 이벤트 루프에서 시작 메시지 전송
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(send_startup_message())
    
    try:
        application.run_polling()
    finally:
        _release_single_instance_lock(BOT_LOCK_FILE)