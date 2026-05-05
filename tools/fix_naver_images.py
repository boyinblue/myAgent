"""
Naver 블로그 구형 blogthumb 이미지를 og:image 방식으로 재갱신하는 스크립트
"""
import sys, json, requests, time
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sys.path.insert(0, 'content-crawler')
from archive_manager import ArchiveManager

mgr = ArchiveManager()
headers = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
}

mgr.cur.execute('SELECT id, url, images FROM posts WHERE platform=?', ('NaverBlog',))
rows = mgr.cur.fetchall()

old_posts = []
for r in rows:
    img = r[2]
    is_old = True
    if img and img.startswith('['):
        try:
            items = json.loads(img)
            url = items[0].get('url', '') if items and isinstance(items[0], dict) else ''
            if 'mblogthumb-phinf' in url or 'postfiles' in url:
                is_old = False
        except Exception:
            pass
    if is_old:
        old_posts.append((r[0], r[1]))

print(f'재갱신 대상: {len(old_posts)}개')
updated = 0
failed = 0

for i, (post_id, post_url) in enumerate(old_posts):
    mobile_url = post_url.replace('https://blog.naver.com/', 'https://m.blog.naver.com/')
    try:
        resp = requests.get(mobile_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        og_img = soup.find('meta', attrs={'property': 'og:image'})
        if og_img and og_img.get('content'):
            img_url = og_img['content']
            img_json = json.dumps([{'url': img_url}])
            mgr.cur.execute('UPDATE posts SET images=? WHERE id=?', (img_json, post_id))
            updated += 1
        else:
            failed += 1
        if (i + 1) % 20 == 0:
            mgr.conn.commit()
            print(f'  진행: {i+1}/{len(old_posts)} (갱신:{updated} 실패:{failed})')
        time.sleep(0.3)
    except Exception as e:
        failed += 1
        print(f'  오류 ID={post_id}: {e}')

mgr.conn.commit()
print(f'완료: 갱신={updated} 실패={failed}')
