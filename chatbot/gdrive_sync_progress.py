import asyncio
import html
import re
from collections import deque
from pathlib import Path


def build_progress_bar(percent: int, width: int = 12) -> str:
    pct = max(0, min(100, int(percent)))
    filled = int(round(width * pct / 100))
    return f"[{'█' * filled}{'░' * (width - filled)}] {pct}%"


async def run_gdrive_sync_with_progress(update, script_path: Path, log_file: Path, cmd_args: list[str] | None = None):
    """gdrive sync 스크립트를 실행하며 progress bar를 갱신하고 종료 후 최근 20줄 로그를 보여줍니다."""
    args = cmd_args or []
    log_file.parent.mkdir(parents=True, exist_ok=True)

    status_msg = await update.message.reply_text(
        f"🔄 <b>Google Drive Sync 시작</b>\n{build_progress_bar(0)} 준비 중...",
        parse_mode="HTML",
    )

    pct_pattern = re.compile(r"(\d{1,3})%")
    recent_lines = deque(maxlen=20)
    last_percent = 0
    last_edit_time = 0.0

    proc = await asyncio.create_subprocess_exec(
        "bash",
        str(script_path),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    with open(log_file, "a", encoding="utf-8") as lf:
        while True:
            raw_line = await proc.stdout.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue

            lf.write(line + "\n")
            lf.flush()
            recent_lines.append(line)

            if "1. Deduplicating" in line or "dedupe" in line.lower():
                last_percent = max(last_percent, 15)
            elif "2. Running rclone" in line or "bisync" in line.lower() or "sync" in line.lower():
                last_percent = max(last_percent, 25)

            m = pct_pattern.search(line)
            if m and ("Transferred:" in line or "Checks:" in line):
                parsed = int(m.group(1))
                last_percent = max(last_percent, 25 + int(parsed * 0.70))

            now = asyncio.get_running_loop().time()
            if now - last_edit_time >= 2.0:
                last_edit_time = now
                safe_line = html.escape(line[:90])
                try:
                    await status_msg.edit_text(
                        f"🔄 <b>Google Drive Sync 진행 중</b>\n"
                        f"{build_progress_bar(last_percent)}\n"
                        f"<code>{safe_line}</code>",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

    return_code = await proc.wait()
    success = return_code == 0
    final_percent = 100 if success else last_percent
    status_label = "완료" if success else f"실패 (code={return_code})"
    icon = "✅" if success else "❌"

    tail_text = "\n".join(recent_lines) if recent_lines else "(출력된 로그 없음)"
    safe_tail = html.escape(tail_text)

    await status_msg.edit_text(
        f"{icon} <b>Google Drive Sync {status_label}</b>\n"
        f"{build_progress_bar(final_percent)}\n\n"
        f"📋 <b>최근 로그 (마지막 {len(recent_lines)}줄)</b>\n"
        f"<pre>{safe_tail}</pre>",
        parse_mode="HTML",
    )
