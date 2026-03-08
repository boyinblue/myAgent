#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anniversary digest runner for GitHub Actions"""

import os
import sys

from scheduler import AnniversaryFinder
from utils.telegram_notifier import TelegramNotifier


def main():
    """Run anniversary digest and send via Telegram"""

    # Load TELEGRAM_BOT_TOKEN from dotenv
    from dotenv import load_dotenv
    load_dotenv()
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    # Verify Telegram token is set
    if not TELEGRAM_BOT_TOKEN:
        print('❌ TELEGRAM_BOT_TOKEN not set')
        sys.exit(1)
    
    # Find anniversary posts
    finder = AnniversaryFinder('../archive')
    if not os.path.exists(finder.db_file):
        print(f'❌ Archive DB not found: {finder.db_file}')
        sys.exit(1)

    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN)
    messages = finder.format_anniversary_message(posts)

    posts = finder.find_anniversary_posts([1, 7, 30, 365])
    
    if posts:
        # Send digest via Telegram
        notifier.send_digest('📆 오늘의 Anniversary Posts', messages)
        print(f'✅ Sent anniversary digest with {len(posts)} posts')
        sys.exit(0)
    else:
        messages = ["오늘의 anniversary 포스트가 없습니다."]
        notifier.send_digest('📆 오늘의 Anniversary Posts', messages)
        print('ℹ️ No anniversary posts found today')
        sys.exit(0)


if __name__ == '__main__':
    main()
