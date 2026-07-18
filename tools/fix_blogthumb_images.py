# -*- coding: utf-8 -*-
"""blogthumb.pstatic.net URL을 가진 포스트의 이미지를 포스트 본문에서 재추출"""
import requests
from bs4 import BeautifulSoup
import sqlite3
import json
import sys
import time
import re

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

DB_PATH = 'archive/archive_index.db'

def get_image_from_post_body(url, headers):
    """포스트 본문 HTML에서 mblogthumb-phinf 이미지 URL 추출"""
    parts = url.replace('https://blog.naver.com/', '').split('/')
    if len(parts) < 2:
        return None

    mobile_url = f'https://m.blog.naver.com/{parts[0]}/{parts[1]}'
    try:
        resp = requests.get(mobile_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 1. 본문 내 이미지 태그에서 mblogthumb-phinf URL 찾기
        for img in soup.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if 'mblogthumb-phinf.pstatic.net' in src:
                # 블러 파라미터 제거 후 고해상도로
                src = src.replace('type=w80_blur', 'type=w800').replace('type=w2_blur', 'type=w800')
                return src

        # 2. se-image 컴포넌트 확인
        for div in soup.find_all(attrs={'class': re.compile(r'se-image')}):
            img = div.find('img')
            if img:
                src = img.get('src', '') or img.get('data-src', '')
                if 'pstatic.net' in src and 'blogthumb' not in src:
                    return src

        # 3. postlistview에서 이미지 링크 패턴 찾기
        text = resp.text
        matches = re.findall(r'(https://mblogthumb-phinf\.pstatic\.net/[^"\'<>\s]+)', text)
        if matches:
            url = matches[0].replace('type=w80_blur', 'type=w800').replace('type=w2_blur', 'type=w800')
            # 이스케이프 문자 제거
            url = url.replace('\\u002F', '/').replace('\\/', '/')
            return url

        return None
    except Exception as e:
        print(f'  오류: {e}')
        return None


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# blogthumb.pstatic.net URL을 가진 NaverBlog 포스트 찾기
posts = conn.execute(
    "SELECT id, title, url, images FROM posts WHERE platform='NaverBlog' AND images LIKE '%blogthumb.pstatic.net%'"
).fetchall()

print(f'blogthumb URL 포스트 수: {len(posts)}')

headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1'}

updated = 0
failed = 0

for post in posts:
    post_id = post['id']
    title = post['title'][:50]
    url = post['url']

    print(f'=== ID {post_id}: {title}')

    try:
        imgs = json.loads(post['images'] or '[]')
        current_url = imgs[0]['url'] if imgs and isinstance(imgs[0], dict) else ''
        print(f'  현재: {current_url[:80]}')
    except Exception:
        current_url = ''

    if 'blog.naver.com' not in url:
        print('  건너뜀 (Naver 아님)')
        continue

    new_url = get_image_from_post_body(url, headers)

    if new_url and 'blogthumb.pstatic.net' not in new_url:
        new_images = json.dumps([{'url': new_url}], ensure_ascii=False)
        conn.execute('UPDATE posts SET images = ? WHERE id = ?', (new_images, post_id))
        conn.commit()
        print(f'  -> 업데이트: {new_url[:80]}')
        updated += 1
    else:
        print(f'  -> mblogthumb URL 없음 (포기)')
        failed += 1

    time.sleep(0.5)
    print()

conn.close()
print(f'완료: 업데이트 {updated}개, 실패 {failed}개')
