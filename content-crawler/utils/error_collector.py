#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""에러 로그 수집 및 관리"""

import sys
from typing import List


class ErrorCollector:
    """크롤링 중 발생하는 에러를 수집합니다."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.original_stdout = sys.stdout
        
    def __enter__(self):
        """Context manager enter"""
        sys.stdout = self
        return self
        
    def __exit__(self, *args):
        """Context manager exit"""
        sys.stdout = self.original_stdout
        
    def write(self, message: str):
        """stdout에 쓰기"""
        self.original_stdout.write(message)
        
        # [ERROR] 또는 [!] 메시지 수집
        if "[ERROR]" in message or "[!]" in message:
            clean_msg = message.strip()
            if clean_msg and clean_msg not in self.errors:
                self.errors.append(clean_msg)
    
    def flush(self):
        """flush 호출 시"""
        pass
    
    def add_error(self, error_msg: str):
        """직접 에러 추가"""
        if error_msg and error_msg not in self.errors:
            self.errors.append(error_msg)
    
    def has_errors(self) -> bool:
        """에러가 있는지 확인"""
        return len(self.errors) > 0
    
    def get_errors_text(self) -> str:
        """에러 목록을 텍스트로 반환"""
        if not self.errors:
            return ""
        
        text = "❌ **크롤링 중 발생한 에러들:**\n\n"
        for i, error in enumerate(self.errors, 1):
            text += f"{i}. {error}\n"
        
        return text
    
    def get_errors_html(self) -> str:
        """에러 목록을 HTML로 반환 (Telegram)"""
        if not self.errors:
            return ""
        
        html = "❌ <b>크롤링 중 발생한 에러들:</b>\n\n"
        for i, error in enumerate(self.errors, 1):
            html += f"{i}. <code>{self._escape_html(error)}</code>\n"
        
        return html
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """HTML 특수 문자 이스케이프"""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        return text
