import sqlite3
import os

db_abs_path = os.path.abspath('./../archive/archive_index.db')
conn = sqlite3.connect(db_abs_path)
cur = conn.cursor()

print("=== 데이터 마이그레이션 준비 ===")

# 1. achieves 테이블의 데이터 개수 확인
cur.execute("SELECT COUNT(*) FROM achieves")
count = cur.fetchone()[0]
print(f"1️⃣ achieves 테이블 데이터: {count}개")

# 2. achieves 테이블의 컬럼 확인
cur.execute("PRAGMA table_info(achieves)")
achieves_cols = cur.fetchall()
print(f"2️⃣ achieves 컬럼수: {len(achieves_cols)}")
for col in achieves_cols:
    print(f"   - {col[1]} ({col[2]})")

# 3. posts 테이블의 컬럼 확인
cur.execute("PRAGMA table_info(posts)")
posts_cols = cur.fetchall()
print(f"3️⃣ posts 컬럼수: {len(posts_cols)}")
for col in posts_cols:
    print(f"   - {col[1]} ({col[2]})")

# 4. 공통 컬럼 찾기
achieves_col_names = {col[1] for col in achieves_cols}
posts_col_names = {col[1] for col in posts_cols}
common_cols = achieves_col_names & posts_col_names
print(f"4️⃣ 공통 컬럼: {common_cols}")

# 5. achieves에만 있는 컬럼
achieves_only = achieves_col_names - posts_col_names
print(f"5️⃣ achieves에만 있는 컬럼: {achieves_only}")

# 6. posts에만 있는 컬럼
posts_only = posts_col_names - achieves_col_names
print(f"6️⃣ posts에만 있는 컬럼: {posts_only}")

conn.close()
