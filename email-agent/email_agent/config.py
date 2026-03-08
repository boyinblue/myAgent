import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Settings:
    email: str
    app_password: str
    imap_host: str = "imap.daum.net"
    imap_port: int = 993
    inbox_name: str = "INBOX"
    spam_name: str = "Spam"


def load_settings() -> Settings:
    email_agent_root = Path(__file__).resolve().parents[1]
    workspace_root = email_agent_root.parents[0]

    # 1) 루트 .env 우선 로드 (권장)
    root_env = workspace_root / ".env"
    if root_env.exists():
        load_dotenv(dotenv_path=root_env)

    # 2) email-agent/.env가 있으면 override 허용 (호환성)
    project_env = email_agent_root / ".env"
    if project_env.exists():
        load_dotenv(dotenv_path=project_env, override=True)

    email = os.getenv("DAUM_EMAIL", "").strip()
    app_password = os.getenv("DAUM_APP_PASSWORD", "").strip()
    if not email or not app_password:
        raise ValueError("DAUM_EMAIL / DAUM_APP_PASSWORD is required (root .env or email-agent/.env)")

    return Settings(
        email=email,
        app_password=app_password,
        imap_host=os.getenv("DAUM_IMAP_HOST", "imap.daum.net").strip(),
        imap_port=int(os.getenv("DAUM_IMAP_PORT", "993").strip()),
        inbox_name=os.getenv("MAILBOX_INBOX", "INBOX").strip(),
        spam_name=os.getenv("MAILBOX_SPAM", "Spam").strip(),
    )
