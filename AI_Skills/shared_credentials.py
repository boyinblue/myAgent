import os
import sys
from pathlib import Path
from typing import Optional


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _PROJECT_ROOT / ".env"
_LOADED = False


def _load_env_fallback() -> None:
    if not _ENV_FILE.exists():
        return
    try:
        with _ENV_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    except Exception:
        return


def _load_via_content_crawler_secrets() -> bool:
    content_crawler_root = _PROJECT_ROOT / "content-crawler"
    if not content_crawler_root.exists():
        return False

    root_str = str(content_crawler_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    try:
        from utils import secrets as crawler_secrets  # type: ignore

        loaded = crawler_secrets.load_environment()
        return bool(loaded)
    except Exception:
        return False


def load_shared_environment() -> None:
    global _LOADED
    if _LOADED:
        return

    used_existing_loader = _load_via_content_crawler_secrets()
    if not used_existing_loader:
        try:
            from dotenv import load_dotenv

            if _ENV_FILE.exists():
                load_dotenv(_ENV_FILE)
        except Exception:
            _load_env_fallback()

    _LOADED = True


def get_shared_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    load_shared_environment()
    value = os.getenv(key)
    if value:
        return value
    return default
