import json
from pathlib import Path
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_PATH = _PROJECT_ROOT / "config.json"
_CONFIG_CACHE: dict | None = None


def _load_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    if not _CONFIG_PATH.exists():
        _CONFIG_CACHE = {}
        return _CONFIG_CACHE

    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as f:
            _CONFIG_CACHE = json.load(f)
    except Exception:
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE


def get_config_value(path: str, default: Any = None) -> Any:
    cfg = _load_config()
    current: Any = cfg

    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]

    return current
