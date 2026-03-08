import sqlite3

conn = sqlite3.connect('./../archive/archive_index.db')
cur = conn.cursor()

# YouTube 데이터 확인
cur.execute("SELECT COUNT(*) FROM posts WHERE platform = 'YouTube'")
youtube_count = cur.fetchone()[0]
print(f'YouTube 포스트: {youtube_count}개')

# NaverBlog 데이터 확인  
cur.execute("SELECT COUNT(*) FROM posts WHERE platform = 'NaverBlog'")
naver_count = cur.fetchone()[0]
print(f'NaverBlog 포스트: {naver_count}개')

# 최신 데이터 확인
cur.execute("SELECT id, title, platform, created_at FROM posts ORDER BY id DESC LIMIT 3")
print('\n최신 3개 데이터:')
for row in cur.fetchall():
    print(f'  ID={row[0]}: {row[1][:30]}... ({row[2]})')

conn.close()
