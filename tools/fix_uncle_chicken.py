# -*- coding: utf-8 -*-
"""엉클스 치킨 포스트 이미지 재스크랩"""
import requests
from bs4 import BeautifulSoup
import sqlite3
import json
import sys
import time

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

DB_PATH = 'archive/archive_index.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

posts = conn.execute(
    'SELECT id, title, url, images FROM posts WHERE title LIKE ?',
    ('%엉클%',)
).fetchall()

headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1'}

for post in posts:
    post_id = post['id']
    title = post['title']
    url = post['url']
    images_raw = post['images'] or '[]'

    print(f'=== ID {post_id}: {title[:50]}')

    try:
        imgs = json.loads(images_raw)
        current_url = imgs[0]['url'] if imgs and isinstance(imgs[0], dict) else ''
        print(f'  현재 이미지: {current_url[:90]}')
    except Exception:
        current_url = ''
        print('  이미지 없음')

    # 모바일 URL 구성
    if 'blog.naver.com' not in url:
        print('  Naver 블로그 아님 - 건너뜀')
        print()
        continue

    parts = url.replace('https://blog.naver.com/', '').split('/')
    if len(parts) < 2:
        print('  URL 파싱 실패 - 건너뜀')
        print()
        continue

    mobile_url = f'https://m.blog.naver.com/{parts[0]}/{parts[1]}'
    print(f'  모바일 URL: {mobile_url}')

    try:
        resp = requests.get(mobile_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        og_img = soup.find('meta', property='og:image')

        if og_img:
            new_url = og_img.get('content', '')
            print(f'  새 og:image: {new_url[:90]}')

            if new_url and new_url != current_url:
                # DB 업데이트
                new_images = json.dumps([{'url': new_url}], ensure_ascii=False)
                conn.execute('UPDATE posts SET images = ? WHERE id = ?', (new_images, post_id))
                conn.commit()
                print(f'  -> DB 업데이트 완료!')
            else:
                print(f'  -> 기존과 동일 또는 빈 URL, 건너뜀')
        else:
            print('  og:image 없음 - 건너뜀')
    except Exception as e:
        print(f'  오류: {e}')

    time.sleep(0.5)
    print()

conn.close()
print('완료')
