"""아카이브에서 키워드 검색"""
import sqlite3
from pathlib import Path
from typing import List, Dict


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ARCHIVE_DB = _PROJECT_ROOT / "archive" / "archive_index.db"


def search_archive(keyword: str, limit: int = 10) -> str:
    """
    아카이브 DB에서 키워드를 검색하여 결과를 반환합니다.
    
    Args:
        keyword: 검색할 키워드
        limit: 최대 반환 개수
    
    Returns:
        검색 결과 문자열
    """
    if not _ARCHIVE_DB.exists():
        return f"[ERROR] 아카이브 데이터베이스를 찾을 수 없습니다: {_ARCHIVE_DB}"
    
    keyword = (keyword or "").strip()
    if not keyword:
        return "[ERROR] 검색 키워드가 비어 있습니다."
    
    try:
        conn = sqlite3.connect(_ARCHIVE_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 제목, 요약, 작성자에서 키워드 검색
        query = """
        SELECT 
            title, 
            author, 
            url, 
            published_date,
            summary,
            platform
        FROM archive_index
        WHERE 
            title LIKE ? 
            OR summary LIKE ? 
            OR author LIKE ?
        ORDER BY published_date DESC
        LIMIT ?
        """
        
        search_pattern = f"%{keyword}%"
        cursor.execute(query, (search_pattern, search_pattern, search_pattern, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return f"❌ '{keyword}' 키워드로 검색된 결과가 없습니다."
        
        results = [f"🔍 '{keyword}' 검색 결과 ({len(rows)}건):\n"]
        
        for idx, row in enumerate(rows, 1):
            title = row["title"] or "제목 없음"
            author = row["author"] or "작성자 미상"
            url = row["url"] or ""
            published = row["published_date"] or "날짜 미상"
            platform = row["platform"] or "플랫폼 미상"
            summary = (row["summary"] or "")[:100]  # 요약은 100자까지만
            
            result_text = (
                f"\n{idx}. {title}\n"
                f"   📝 {author} | {platform}\n"
                f"   📅 {published}\n"
            )
            
            if summary:
                result_text += f"   💬 {summary}...\n"
            
            if url:
                result_text += f"   🔗 {url}\n"
            
            results.append(result_text)
        
        return "".join(results)
    
    except sqlite3.Error as e:
        return f"[ERROR] DB 조회 실패: {e}"
    except Exception as e:
        return f"[ERROR] 검색 중 오류 발생: {e}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python archive_search.py <keyword>")
        sys.exit(1)
    
    keyword = " ".join(sys.argv[1:])
    result = search_archive(keyword)
    print(result)
