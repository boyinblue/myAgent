"""포스트 DB 무결성 검사"""
import sqlite3
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ARCHIVE_DB = _PROJECT_ROOT / "archive" / "archive_index.db"


def validate_posts() -> str:
    """아카이브 DB에서 누락/불완전한 포스트 데이터를 찾습니다."""
    if not _ARCHIVE_DB.exists():
        return f"[ERROR] 아카이브 데이터베이스를 찾을 수 없습니다: {_ARCHIVE_DB}"

    try:
        conn = sqlite3.connect(_ARCHIVE_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM posts")
        total = cursor.fetchone()["total"]

        issues = []

        cursor.execute("SELECT COUNT(*) as cnt FROM posts WHERE title IS NULL OR title = ''")
        missing_title = cursor.fetchone()["cnt"]
        if missing_title > 0:
            issues.append(f"❌ 제목 누락: {missing_title}건")

        cursor.execute("SELECT COUNT(*) as cnt FROM posts WHERE url IS NULL OR url = ''")
        missing_url = cursor.fetchone()["cnt"]
        if missing_url > 0:
            issues.append(f"❌ URL 누락: {missing_url}건")

        cursor.execute("SELECT COUNT(*) as cnt FROM posts WHERE media_name IS NULL OR media_name = ''")
        missing_media = cursor.fetchone()["cnt"]
        if missing_media > 0:
            issues.append(f"⚠️ 미디어명 누락: {missing_media}건")

        cursor.execute("SELECT COUNT(*) as cnt FROM posts WHERE published_date IS NULL OR published_date = ''")
        missing_date = cursor.fetchone()["cnt"]
        if missing_date > 0:
            issues.append(f"⚠️ 날짜 누락: {missing_date}건")

        cursor.execute("SELECT COUNT(*) as cnt FROM posts WHERE platform IS NULL OR platform = ''")
        missing_platform = cursor.fetchone()["cnt"]
        if missing_platform > 0:
            issues.append(f"❌ 플랫폼 누락: {missing_platform}건")

        cursor.execute("SELECT COUNT(*) as cnt FROM posts WHERE keywords IS NULL OR keywords = ''")
        missing_keywords = cursor.fetchone()["cnt"]
        if missing_keywords > 0:
            issues.append(f"ℹ️ 키워드 누락: {missing_keywords}건 (선택 필드)")

        cursor.execute("""
            SELECT id, title, url, media_name, published_date, platform
            FROM posts
            WHERE
                (title IS NULL OR title = '')
                OR (url IS NULL OR url = '')
                OR (platform IS NULL OR platform = '')
            LIMIT 5
        """)
        samples = cursor.fetchall()

        conn.close()

        if not issues:
            return f"✅ 포스트 무결성 검사 완료\n📊 전체 {total}건, 문제 없음"

        result = [f"📊 포스트 무결성 검사 결과 (전체 {total}건)\n"]
        result.extend(issues)

        if samples:
            result.append("\n🔍 누락 포스트 샘플:")
            for idx, row in enumerate(samples, 1):
                title = row["title"] or "(제목 없음)"
                url = row["url"] or "(URL 없음)"
                platform = row["platform"] or "(플랫폼 없음)"
                media_name = row["media_name"] or "(미디어 없음)"
                result.append(f"  {idx}. {title} | {platform} | {media_name} | {url}")

        return "\n".join(result)

    except sqlite3.Error as e:
        return f"[ERROR] DB 조회 실패: {e}"
    except Exception as e:
        return f"[ERROR] 검사 중 오류 발생: {e}"


def validate_archive() -> str:
    """하위 호환용 alias"""
    return validate_posts()


if __name__ == "__main__":
    result = validate_posts()
    print(result)
