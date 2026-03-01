#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anniversary digest runner for GitHub Actions"""

import os
import sys

from scheduler import AnniversaryFinder
from utils.telegram_notifier import TelegramNotifier


def main():
    """Run anniversary digest and send via Telegram"""
    # Verify Telegram token is set
    if not os.environ.get('TELEGRAM_BOT_TOKEN'):
        print('❌ TELEGRAM_BOT_TOKEN not set')
        sys.exit(1)
    
    # Find anniversary posts
    finder = AnniversaryFinder('./archive')
    posts = finder.find_anniversary_posts([1, 7, 30, 365])
    
    if posts:
        # Send digest via Telegram
        notifier = TelegramNotifier()
        messages = finder.format_anniversary_message(posts)
        notifier.send_digest('📆 오늘의 Anniversary Posts', messages)
        print(f'✅ Sent anniversary digest with {len(posts)} posts')
        sys.exit(0)
    else:
        print('ℹ️ No anniversary posts found today')
        sys.exit(0)


if __name__ == '__main__':
    main()
