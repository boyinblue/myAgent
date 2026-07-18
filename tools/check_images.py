# -*- coding: utf-8 -*-
import sqlite3, json, sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('archive/archive_index.db')
conn.row_factory = sqlite3.Row

rows = conn.execute('SELECT id, title, images FROM posts WHERE title LIKE ?', ('%엉클%',)).fetchall()
for r in rows:
    imgs = json.loads(r['images'] or '[]')
    url = imgs[0]['url'] if imgs and isinstance(imgs[0], dict) else ''
    print(r['id'], r['title'][:40])
    print(' ', url[:90])

cnt = conn.execute("SELECT COUNT(*) FROM posts WHERE platform='NaverBlog' AND images LIKE '%blogthumb.pstatic.net%'").fetchone()[0]
print(f'\nblogthumb 남은 포스트: {cnt}')
conn.close()
