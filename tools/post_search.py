"""포스트에서 키워드 검색"""
import sqlite3
import re
from pathlib import Path
from typing import List


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ARCHIVE_DB = _PROJECT_ROOT / "archive" / "archive_index.db"


def _tokenize_keyword(keyword: str) -> List[str]:
    """입력 검색어를 토큰으로 분리합니다."""
    normalized = re.sub(r"\s+", " ", (keyword or "").strip())
    if not normalized:
        return []

    parts = re.split(r"[\s,|/]+", normalized)
    tokens: List[str] = []
    for part in parts:
        token = part.strip().strip("'\"“”‘’()[]{}")
        if not token:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def search_posts(keyword: str, limit: int = 10) -> str:
    """아카이브 DB에서 포스트를 검색하여 결과를 반환합니다."""
    if not _ARCHIVE_DB.exists():
        return f"[ERROR] 아카이브 데이터베이스를 찾을 수 없습니다: {_ARCHIVE_DB}"

    keyword = (keyword or "").strip()
    if not keyword:
        return "[ERROR] 검색 키워드가 비어 있습니다."

    tokens = _tokenize_keyword(keyword)
    if not tokens:
        return "[ERROR] 검색 키워드를 해석할 수 없습니다."

    try:
        conn = sqlite3.connect(_ARCHIVE_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        base_select = """
        SELECT
            title,
            media_name,
            url,
            published_date,
            keywords,
            tags,
            platform,
            images
        FROM posts
        """

        fields = ["title", "keywords", "tags", "media_name"]
        per_token_clause = "(" + " OR ".join([f"{field} LIKE ?" for field in fields]) + ")"

        where_and = " AND ".join([per_token_clause] * len(tokens))
        query_and = base_select + f" WHERE {where_and} " + """
        ORDER BY published_date DESC
        LIMIT ?
        """

        params_and: List[str | int] = []
        for token in tokens:
            pattern = f"%{token}%"
            params_and.extend([pattern] * len(fields))
        params_and.append(limit)

        cursor.execute(query_and, params_and)
        rows = cursor.fetchall()

        if not rows and len(tokens) > 1:
            where_or = " OR ".join([per_token_clause] * len(tokens))
            query_or = base_select + f" WHERE {where_or} " + """
            ORDER BY published_date DESC
            LIMIT ?
            """
            params_or: List[str | int] = []
            for token in tokens:
                pattern = f"%{token}%"
                params_or.extend([pattern] * len(fields))
            params_or.append(limit)
            cursor.execute(query_or, params_or)
            rows = cursor.fetchall()

        conn.close()

        if not rows:
            return f"❌ '{keyword}' 키워드를 포함하는 포스트가 없습니다."

        results = [f"🔍 '{keyword}' 포스트 검색 결과 ({len(rows)}건):\n"]

        for idx, row in enumerate(rows, 1):
            title = row["title"] or "제목 없음"
            media_name = row["media_name"] or "미디어 미상"
            url = row["url"] or ""
            published = row["published_date"] or "날짜 미상"
            platform = row["platform"] or "플랫폼 미상"
            keywords = (row["keywords"] or "")[:100]
            images_json = row["images"] or ""

            # 첫 번째 이미지 URL 추출
            thumbnail_url = ""
            if images_json:
                try:
                    import json
                    images_list = json.loads(images_json)
                    if images_list and isinstance(images_list, list) and len(images_list) > 0:
                        first_image = images_list[0]
                        if isinstance(first_image, dict):
                            thumbnail_url = first_image.get("url", "")
                        elif isinstance(first_image, str):
                            thumbnail_url = first_image
                except Exception:
                    pass

            result_text = (
                f"\n{idx}. {title}\n"
                f"   📝 {media_name} | {platform}\n"
                f"   📅 {published}\n"
            )

            if thumbnail_url:
                result_text += f"   🖼️ {thumbnail_url}\n"

            if keywords:
                result_text += f"   🏷️ {keywords}\n"

            if url:
                result_text += f"   🔗 {url}\n"

            results.append(result_text)

        return "".join(results)

    except sqlite3.Error as e:
        return f"[ERROR] DB 조회 실패: {e}"
    except Exception as e:
        return f"[ERROR] 검색 중 오류 발생: {e}"


def search_random_posts(count: int = 3) -> str:
    """아카이브 DB에서 랜덤 포스트를 반환합니다."""
    if not _ARCHIVE_DB.exists():
        return f"[ERROR] 아카이브 데이터베이스를 찾을 수 없습니다: {_ARCHIVE_DB}"

    try:
        conn = sqlite3.connect(_ARCHIVE_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
        SELECT
            title,
            media_name,
            url,
            published_date,
            keywords,
            tags,
            platform,
            images
        FROM posts
        ORDER BY RANDOM()
        LIMIT ?
        """

        cursor.execute(query, (count,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "❌ 포스트가 없습니다."

        results = [f"🎲 랜덤 포스트 ({len(rows)}건):\n"]

        for idx, row in enumerate(rows, 1):
            title = row["title"] or "제목 없음"
            media_name = row["media_name"] or "미디어 미상"
            url = row["url"] or ""
            published = row["published_date"] or "날짜 미상"
            platform = row["platform"] or "플랫폼 미상"
            keywords = (row["keywords"] or "")[:100]
            images_json = row["images"] or ""

            # 첫 번째 이미지 URL 추출
            thumbnail_url = ""
            if images_json:
                try:
                    import json
                    images_list = json.loads(images_json)
                    if images_list and isinstance(images_list, list) and len(images_list) > 0:
                        first_image = images_list[0]
                        if isinstance(first_image, dict):
                            thumbnail_url = first_image.get("url", "")
                        elif isinstance(first_image, str):
                            thumbnail_url = first_image
                except Exception:
                    pass

            result_text = (
                f"\n{idx}. {title}\n"
                f"   📝 {media_name} | {platform}\n"
                f"   📅 {published}\n"
            )

            if thumbnail_url:
                result_text += f"   🖼️ {thumbnail_url}\n"

            if keywords:
                result_text += f"   🏷️ {keywords}\n"

            if url:
                result_text += f"   🔗 {url}\n"

            results.append(result_text)

        return "".join(results)

    except sqlite3.Error as e:
        return f"[ERROR] DB 조회 실패: {e}"
    except Exception as e:
        return f"[ERROR] 랜덤 포스트 조회 중 오류 발생: {e}"


def search_archive(keyword: str, limit: int = 10) -> str:
    """하위 호환용 alias"""
    return search_posts(keyword, limit)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python post_search.py <keyword>")
        sys.exit(1)

    keyword = " ".join(sys.argv[1:])
    result = search_posts(keyword)
    print(result)
