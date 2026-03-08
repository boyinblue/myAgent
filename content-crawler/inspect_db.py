import sqlite3
import os

db_path = './../archive/archive_index.db'
db_abs_path = os.path.abspath(db_path)

print(f"DB 파일: {db_abs_path}")
print(f"파일 크기: {os.path.getsize(db_abs_path)} bytes")
print()

try:
    conn = sqlite3.connect(db_abs_path)
    cur = conn.cursor()
    
    # 모든 테이블 확인
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    
    print(f"=== 테이블 목록 ({len(tables)}개) ===")
    if not tables:
        print("테이블이 없음")
    else:
        for table in tables:
            print(f"- {table[0]}")
            
            # 각 테이블의 스키마와 데이터 확인
            cur.execute(f"PRAGMA table_info({table[0]})")
            columns = cur.fetchall()
            print(f"  컬럼수: {len(columns)}")
            
            cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cur.fetchone()[0]
            print(f"  레코드수: {count}")
            
            if count > 0:
                cur.execute(f"SELECT * FROM {table[0]} LIMIT 1")
                sample = cur.fetchone()
                print(f"  샘플: {sample}")
    
    # sqlite_sequence 테이블 확인 (autoincrement 상태)
    print()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
    if cur.fetchone():
        print("=== Autoincrement 시퀀스 ===")
        cur.execute("SELECT * FROM sqlite_sequence")
        for seq in cur.fetchall():
            print(f"- {seq[0]}: {seq[1]}")
    
    conn.close()
    
except Exception as e:
    print(f"DB 접근 실패: {e}")
