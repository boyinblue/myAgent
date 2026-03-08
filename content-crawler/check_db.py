import sqlite3

conn = sqlite3.connect('archive_index.db')
cur = conn.cursor()

# 테이블 목록 확인
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('=== 현재 테이블 목록 ===')
for table in tables:
    print(f'- {table[0]}')

# 각 테이블의 데이터 개수 확인
print()
for table in tables:
    cur.execute(f'SELECT COUNT(*) FROM {table[0]}')
    count = cur.fetchone()[0]
    print(f'{table[0]}: {count}개')

# posts 테이블이 있으면 스키마 확인
print()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='posts'")
if cur.fetchone():
    print('=== posts 테이블 스키마 ===')
    cur.execute("PRAGMA table_info(posts)")
    for col in cur.fetchall():
        print(f'{col[1]} ({col[2]})')

# achieves 테이블이 있으면 스키마 확인
print()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='achieves'")
if cur.fetchone():
    print('=== achieves 테이블 스키마 ===')
    cur.execute("PRAGMA table_info(achieves)")
    for col in cur.fetchall():
        print(f'{col[1]} ({col[2]})')

conn.close()
