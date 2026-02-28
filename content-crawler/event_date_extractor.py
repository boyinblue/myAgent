# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""이벤트 날짜 추출 유틸리티

글 본문에서 날짜 패턴을 찾아 이벤트 날짜를 자동 추출합니다.
"""

import re
from datetime import datetime
from typing import List


class EventDateExtractor:
    """글 본문에서 이벤트 날짜를 추출합니다."""

    # 날짜 패턴 (한글/숫자 혼합)
    DATE_PATTERNS = [
        # YYYY-MM-DD 형식
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
        # YYYY년 MM월 DD일
        r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
        # MM월 DD일 (같은 해라고 가정)
        r"(\d{1,2})월\s*(\d{1,2})일",
    ]

    def __init__(self, current_year: int = None):
        """
        Args:
            current_year: MM월 DD일 패턴 인식 시 사용할 연도 (기본값: 현재 연도)
        """
        self.current_year = current_year or datetime.now().year

    def extract(self, text: str, created_date: str = None) -> List[str]:
        """
        텍스트에서 날짜를 추출합니다.

        Args:
            text: 추출 대상 텍스트
            created_date: 포스트 작성 날짜 (YYYY-MM-DD 형식) - 기본값으로 사용

        Returns:
            날짜 리스트 (정렬됨, 중복 제거됨, YYYY-MM-DD 형식)
        """
        dates = set()

        # 1. YYYY-MM-DD 형식
        matches = re.findall(self.DATE_PATTERNS[0], text)
        for y, m, d in matches:
            date_str = self._format_date(int(y), int(m), int(d))
            if date_str:
                dates.add(date_str)

        # 2. YYYY년 MM월 DD일 형식
        matches = re.findall(self.DATE_PATTERNS[1], text)
        for y, m, d in matches:
            date_str = self._format_date(int(y), int(m), int(d))
            if date_str:
                dates.add(date_str)

        # 3. MM월 DD일 형식 (현재 연도 가정)
        matches = re.findall(self.DATE_PATTERNS[2], text)
        for m, d in matches:
            date_str = self._format_date(self.current_year, int(m), int(d))
            if date_str:
                dates.add(date_str)

        # 작성 날짜도 추가 (있을 경우)
        if created_date:
            dates.add(created_date)

        # 정렬
        result = sorted(list(dates))
        return result

    @staticmethod
    def _format_date(year: int, month: int, day: int) -> str:
        """유효한 날짜인지 확인하고 YYYY-MM-DD 형식으로 변환합니다."""
        try:
            date_obj = datetime(year, month, day)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            # 유효하지 않은 날짜 (예: 13월, 32일)
            return None


if __name__ == "__main__":
    # 테스트
    extractor = EventDateExtractor()

    test_text = """
    2024년 1월 15일에 처음으로 파이썬을 배웠다.
    그 다음 1월 18일에 첫 프로젝트를 시작했고,
    2024-02-10에 완성했다.
    2월 15일에는 발표를 했다.
    """

    result = extractor.extract(test_text, created_date="2024-02-20")
    print("추출된 날짜:", result)
