"""
Naver 블로그 구형 blogthumb 이미지를 og:image 방식으로 재갱신 (디버그)
"""
import sys, json, requests, time
from bs4 import BeautifulSoup

sys.path.insert(0, 'content-crawler')
from archive_manager import ArchiveManager

print("ArchiveManager 생성 중...", flush=True)
mgr = ArchiveManager()
print(f"DB 경로: {mgr.conn}",flush=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
}

mgr.cur.execute('SELECT id, url, images FROM posts WHERE platform=?', ('NaverBlog',))
rows = mgr.cur.fetchall()
print(f"Naver 포스트 총: {len(rows)}개", flush=True)

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

print(f"재갱신 대상: {len(old_posts)}개", flush=True)

# Before 상태
mgr.cur.execute('SELECT COUNT(*) FROM posts WHERE platform=? AND images LIKE ?', ('NaverBlog', '%mblogthumb-phinf%'))
print(f"BEFORE: mblogthumb-phinf count = {mgr.cur.fetchone()[0]}", flush=True)

updated = 0
failed = 0
test_count = 5  # 먼저 5개만 테스트

for i, (post_id, post_url) in enumerate(old_posts[:test_count]):
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
            print(f"  [+] ID={post_id} updated", flush=True)
        else:
            failed += 1
            print(f"  [-] ID={post_id} og:image not found", flush=True)
        time.sleep(0.3)
    except Exception as e:
        failed += 1
        print(f"  [!] ID={post_id} error: {e}", flush=True)

print(f"테스트 커밋 중...", flush=True)
mgr.conn.commit()
print(f"커밋 완료", flush=True)

# After 상태
mgr.cur.execute('SELECT COUNT(*) FROM posts WHERE platform=? AND images LIKE ?', ('NaverBlog', '%mblogthumb-phinf%'))
print(f"AFTER: mblogthumb-phinf count = {mgr.cur.fetchone()[0]}", flush=True)

print(f"테스트 완료: 갱신={updated} 실패={failed}", flush=True)
mgr.conn.close()
print("DB 연결 종료", flush=True)
