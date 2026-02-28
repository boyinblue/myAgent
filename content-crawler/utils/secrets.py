# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""환경 변수 및 보안 설정 관리"""

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    load_dotenv = None


def _load_env_file_fallback(env_file):
    """python-dotenv 없이 .env 파일을 직접 파싱합니다."""
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    except Exception as e:
        print(f"[!] .env 파일 파싱 실패: {e}")


def load_environment():
    """환경 변수를 로드합니다 (.env 파일에서)."""
    env_file = Path(__file__).parent.parent / ".env"
    
    if not env_file.exists():
        print(f"[!] .env 파일을 찾을 수 없습니다: {env_file}")
        print(f"[i] .env.example을 복사하여 .env를 만드세요.")
        return False
    
    try:
        if HAS_DOTENV and load_dotenv:
            load_dotenv(env_file)
        else:
            _load_env_file_fallback(env_file)
        print(f"[*] 환경 설정 로드: {env_file}")
        return True
    except Exception as e:
        print(f"[!] 환경 로드 실패: {e}")
        return False


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    환경 변수에서 민감한 정보를 읽습니다.
    
    Args:
        key: 환경 변수명
        default: 기본값 (환경 변수가 없을 때)
    
    Returns:
        환경 변수 값 또는 기본값
    """
    value = os.getenv(key)
    if value:
        return value
    if default is not None:
        return default
    return None


def get_telegram_token() -> Optional[str]:
    """텔레그램 봇 토큰을 반환합니다."""
    return get_secret("TELEGRAM_BOT_TOKEN")


def get_telegram_chat_id() -> Optional[str]:
    """텔레그램 채팅 ID (수신자 전화번호 등)를 반환합니다."""
    return get_secret("TELEGRAM_CHAT_ID")


def get_youtube_api_key() -> Optional[str]:
    """YouTube API 키를 반환합니다."""
    return get_secret("YOUTUBE_API_KEY")
