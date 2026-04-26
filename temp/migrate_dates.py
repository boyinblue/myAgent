import sqlite3
from pathlib import Path
from datetime import datetime
import re

db_path = Path(r'C:\Users\user\Documents\Porjects\myAgent\archive\archive_index.db')
con = sqlite3.connect(str(db_path))
cur = con.cursor()

def parse_date(created_at_str):
    """Try multiple date formats and return ISO format or empty string"""
    if not created_at_str or created_at_str == 'None':
        return ''
    
    created_at_str = str(created_at_str).strip()
    
    # Try ISO format first
    if 'T' in created_at_str and len(created_at_str) >= 19:
        try:
            dt = datetime.fromisoformat(created_at_str.split('+')[0])
            return dt.isoformat()
        except:
            pass
    
    # Try Korean date format: "YYYY. M. D. HH:MM" or "YYYY. M. D. HH:MM:SS"
    match = re.match(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{1,2}):(\d{2})(?::(\d{2}))?', created_at_str)
    if match:
        try:
            y, m, d, h, min, s = match.groups()
            dt = datetime(int(y), int(m), int(d), int(h), int(min), int(s or 0))
            return dt.isoformat()
        except:
            pass
    
    # Try RSS/Email date format: "Fri, 13 Jul 2018 08:53:08 +0900"
    try:
        # Remove timezone part
        date_part = re.sub(r'\s*[+-]\d{4}$', '', created_at_str)
        dt = datetime.strptime(date_part, '%a, %d %b %Y %H:%M:%S')
        return dt.isoformat()
    except:
        pass
    
    # If all else fails, return empty
    return ''

# Get all posts
rows = cur.execute('SELECT id, created_at FROM posts WHERE created_at IS NOT NULL').fetchall()
print(f'Total posts to migrate: {len(rows)}')

updated = 0
failed = 0

for post_id, created_at in rows:
    published_date = parse_date(created_at)
    if published_date:
        cur.execute('UPDATE posts SET published_date = ? WHERE id = ?', (published_date, post_id))
        updated += 1
    else:
        failed += 1

con.commit()
print(f'Updated: {updated}')
print(f'Failed to parse: {failed}')

# Verify
result = cur.execute('SELECT COUNT(*) FROM posts WHERE published_date IS NOT NULL').fetchone()
print(f'Posts with published_date after migration: {result[0]}')

# Sample of updated data
print()
print('Sample of migrated data:')
rows = cur.execute('SELECT id, title, created_at, published_date FROM posts WHERE published_date IS NOT NULL LIMIT 10').fetchall()
for r in rows:
    print(f"  ID {r[0]}: {r[2][:30]} -> {r[3][:30]}")

con.close()
