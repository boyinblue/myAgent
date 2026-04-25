# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""일일 다이제스트 스케줄러 및 anniversary 기능"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import schedule
import time


class AnniversaryFinder:
    """몇 년 전 오늘의 포스트를 찾습니다."""

    def __init__(self, archive_root: str = "./archive"):
        """
        Args:
            archive_root: 아카이브 루트 디렉토리
        """
        self.archive_root = archive_root
        self.db_file = os.path.join(archive_root, "archive_index.db")

    def find_anniversary_posts(self, years_back: List[int] = None) -> List[Dict]:
        """
        몇 년 전 오늘의 포스트를 찾습니다.

        Args:
            years_back: 몇 년 전까지 찾을지 (기본: [1, 7, 30, 365])

        Returns:
            anniversary 포스트 리스트
        """
        if years_back is None:
            years_back = [1, 7, 30, 365]

        if not os.path.exists(self.db_file):
            print(f"[!] DB 파일이 없습니다: {self.db_file}")
            return []

        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT title, url, created_at
                                FROM posts
                WHERE created_at IS NOT NULL
                  AND created_at != ''
                """
            )
            posts = [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            print(f"[!] DB 조회 실패: {exc}")
            return []
        finally:
            try:
                conn.close()
            except Exception:
                pass

        anniversary_posts: List[Dict] = []

        today = datetime.now()
        today_month_day = f"{today.month:02d}-{today.day:02d}"

        for post in posts:
            published = post.get("created_at", "")
            if not published:
                continue

            try:
                # 날짜 파싱 (ISO format 또는 YYYY-MM-DD)
                if "T" in published:
                    pub_date = datetime.fromisoformat(published.split("T")[0])
                else:
                    pub_date = datetime.strptime(published, "%Y-%m-%d")

                pub_month_day = f"{pub_date.month:02d}-{pub_date.day:02d}"

                # 오늘과 같은 월일인지 확인
                if pub_month_day == today_month_day:
                    years_diff = today.year - pub_date.year
                    if years_diff in years_back:
                        anniversary_posts.append(
                            {
                                "title": post.get("title", "제목 없음"),
                                "link": post.get("url", ""),
                                "published": pub_date.strftime("%Y-%m-%d"),
                                "years_ago": years_diff,
                            }
                        )

            except (ValueError, IndexError):
                continue

        return sorted(anniversary_posts, key=lambda x: x.get("years_ago", 999))

    def format_anniversary_message(self, posts: List[Dict]) -> List[str]:
        """
        anniversary 포스트들을 텍스트 메시지로 포맷합니다.

        Returns:
            포맷된 메시지 리스트
        """
        messages: List[str] = []

        if not posts:
            return ["오늘의 anniversary 포스트가 없습니다."]

        for post in posts:
            years_ago = post.get("years_ago", "?")
            title = post.get("title", "제목 없음")
            link = post.get("link", "") or post.get("url", "")
            date = post.get("published", "").split("T")[0] if post.get("published") else ""

            msg = f"<b>{years_ago}년 전 오늘</b> ({date})\n{title}"
            if link:
                msg += f"\n🔗 <a href='{link}'>보기</a>"
            messages.append(msg)

        return messages


class DailyDigestScheduler:
    """일일 다이제스트를 스케줄링하고 발송합니다."""

    def __init__(self, config: Dict, telegram_notifier=None):
        """
        Args:
            config: 설정 딕셔너리 (scheduler 섹션)
            telegram_notifier: TelegramNotifier 인스턴스
        """
        self.config = config
        self.notifier = telegram_notifier
        self.archive_root = config.get("archive_root", "./archive")

    def should_run_scheduler(self) -> bool:
        """스케줄러가 활성화되어 있는지 확인합니다."""
        enabled = self.config.get("enabled", False)
        has_notifier = self.notifier is not None
        is_configured = self.notifier.is_configured() if self.notifier else False

        if not enabled:
            print("[!] 스케줄러가 config.json에서 'enabled: false'로 설정되어 있습니다.")
        if not has_notifier:
            print("[!] 텔레그램 알리미가 초기화되지 않았습니다.")
        if has_notifier and not is_configured:
            print("[!] 텔레그램이 설정되지 않았습니다. .env 파일에서 TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID를 확인하세요.")

        return enabled and has_notifier and is_configured

    def send_daily_digest(self):
        """일일 다이제스트를 발송합니다."""
        print(f"\n[*] 일일 다이제스트 발송 중... ({datetime.now()})")

        anniversary_days = self.config.get("anniversary_days", [1, 7, 30, 365])
        finder = AnniversaryFinder(self.archive_root)
        anniversary_posts = finder.find_anniversary_posts(anniversary_days)

        if anniversary_posts:
            messages = finder.format_anniversary_message(anniversary_posts)
            title = f"📆 오늘의 Anniversary Posts ({len(anniversary_posts)}개)"
            self.notifier.send_digest(title, messages)
        else:
            print("[i] 오늘의 anniversary 포스트가 없습니다.")

    def start(self):
        """스케줄러를 시작합니다."""
        if not self.should_run_scheduler():
            return

        schedule_time = self.config.get("daily_digest_time", "08:00")
        print(f"[*] 일일 다이제스트 스케줄 설정: 매일 {schedule_time}")

        schedule.every().day.at(schedule_time).do(self.send_daily_digest)

        print("[*] 스케줄러 시작. Ctrl+C로 종료할 수 있습니다.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 확인
        except KeyboardInterrupt:
            print("\n[*] 스케줄러 종료")
