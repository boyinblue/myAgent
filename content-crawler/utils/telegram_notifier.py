# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""텔레그램 메시지 발송 기능"""

import requests
from typing import Optional, List
from utils.secrets import get_telegram_token, get_telegram_chat_id


class TelegramNotifier:
    """텔레그램 봇을 통해 메시지를 발송합니다."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Args:
            token: 텔레그램 봇 토큰 (환경변수 미설정 시)
            chat_id: 수신자 채팅 ID
        """
        self.token = token or get_telegram_token()
        self.chat_id = chat_id or get_telegram_chat_id()
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None

    def is_configured(self) -> bool:
        """텔레그램이 설정되었는지 확인합니다."""
        return bool(self.token and self.chat_id)

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        메시지를 발송합니다.

        Args:
            message: 발송 메시지 (HTML 형식 지원)
            parse_mode: 파싱 모드 ("HTML" 또는 "Markdown")

        Returns:
            성공 여부
        """
        if not self.is_configured():
            print("[!] 텔레그램이 설정되지 않았습니다.")
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"[+] 텔레그램 메시지 발송 성공")
            return True
        except Exception as e:
            print(f"[ERROR] 텔레그램 발송 실패: {e}")
            return False

    def send_digest(self, title: str, items: List[str]) -> bool:
        """
        다이제스트 형식의 메시지를 발송합니다.

        Args:
            title: 제목
            items: 항목 리스트

        Returns:
            성공 여부
        """
        if not items:
            print("[!] 발송할 항목이 없습니다.")
            return False

        message = f"<b>{title}</b>\n\n"
        for item in items[:50]:  # 최대 50개까지만
            message += f"• {item}\n"

        if len(items) > 50:
            message += f"\n... 외 {len(items) - 50}개 항목"

        return self.send_message(message)

    def send_errors(self, errors: List[str]) -> bool:
        """
        에러 메시지 리스트를 발송합니다.

        Args:
            errors: 에러 메시지 리스트

        Returns:
            성공 여부
        """
        if not errors:
            return False

        message = "<b>❌ 크롤링 중 발생한 에러들:</b>\n\n"
        for i, error in enumerate(errors[:20], 1):  # 최대 20개까지만
            message += f"{i}. <code>{self._escape_html(error)}</code>\n"

        if len(errors) > 20:
            message += f"\n... 외 {len(errors) - 20}개 에러"

        return self.send_message(message)

    @staticmethod
    def _escape_html(text: str) -> str:
        """HTML 특수 문자 이스케이프"""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        return text
