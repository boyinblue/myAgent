#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Send the anniversary digest using the local archive."""

import os
import sys

from scheduler import AnniversaryFinder
from utils.telegram_notifier import TelegramNotifier


def main():
    """Run anniversary digest and send via Telegram"""

    if sys.platform == 'win32':
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, 'reconfigure'):
                stream.reconfigure(encoding='utf-8', errors='replace')

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_root, '.env'))
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    if not TELEGRAM_BOT_TOKEN:
        print('❌ TELEGRAM_BOT_TOKEN not set')
        sys.exit(1)
    
    archive_root = os.path.join(project_root, 'archive')
    finder = AnniversaryFinder(archive_root)
    if not os.path.exists(finder.db_file):
        print(f'❌ Archive DB not found: {finder.db_file}')
        sys.exit(1)

    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN)
    anniversary_posts = finder.find_anniversary_posts([1, 7, 30, 365])
    anniversary_urls = [post.get('link') for post in anniversary_posts]
    random_posts = finder.find_random_posts(count=3, exclude_urls=anniversary_urls)
    messages = finder.format_daily_digest(anniversary_posts, random_posts)
    sent = notifier.send_digest('📆 오늘의 Daily Digest', messages)

    if not sent:
        print('❌ Daily digest delivery failed')
        sys.exit(1)

    print(
        f'✅ Sent daily digest with {len(anniversary_posts)} anniversary posts '
        f'and {len(random_posts)} random posts'
    )


if __name__ == '__main__':
    main()
