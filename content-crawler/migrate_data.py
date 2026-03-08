import sqlite3
import os

db_abs_path = os.path.abspath('./../archive/archive_index.db')
conn = sqlite3.connect(db_abs_path)
cur = conn.cursor()

print("=== achieves → posts 데이터 마이그레이션 ===")

try:
    # 1. achieves 데이터를 posts로 복제
    sql = '''
    INSERT INTO posts 
    (id, title, url, platform, media_name, category, keywords, tags, images, 
     gdrive_id, file_path, file_hash, comment, score, remind_count, 
     crawler_version, is_parsed, archived, created_at, event_dates, 
     published_date, db_updated_at, last_sync_at)
    SELECT 
    id, title, url, platform, media_name, category, keywords, tags, images, 
    gdrive_id, file_path, file_hash, comment, score, remind_count, 
    crawler_version, is_parsed, archived, created_at, event_dates,
    NULL, db_updated_at, last_sync_at
    FROM achieves
    '''
    cur.execute(sql)
    conn.commit()
    
    # 2. 마이그레이션 결과 확인
    cur.execute("SELECT COUNT(*) FROM posts")
    posts_count = cur.fetchone()[0]
    print(f"✅ 마이그레이션 완료: {posts_count}개의 레코드")
    
    # 3. autoincrement 시퀀스 업데이트
    cur.execute("SELECT MAX(id) FROM posts")
    max_id = cur.fetchone()[0]
    print(f"✅ Max ID: {max_id}")
    
    # 4. achieves 테이블 삭제
    cur.execute("DROP TABLE achieves")
    conn.commit()
    print(f"✅ achieves 테이블 삭제 완료")
    
    # 5. 샘플 데이터 확인
    cur.execute("SELECT id, title, url, platform FROM posts LIMIT 3")
    print("\n샘플 데이터 (처음 3개):")
    for row in cur.fetchall():
        print(f"  ID={row[0]}: {row[1][:30]}... ({row[3]})")
    
except Exception as e:
    print(f"❌ 마이그레이션 실패: {e}")
    conn.rollback()

finally:
    conn.close()
