"""지정된 날짜에 가장 가까운 포스트 조회"""
import sqlite3
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ARCHIVE_DB = _PROJECT_ROOT / "archive" / "archive_index.db"


def _parse_date(date_str: str) -> Optional[str]:
    """YYYYMMDD 또는 YYMMDD 형식을 YYYY-MM-DD로 변환합니다."""
    cleaned = (date_str or "").strip()
    if not cleaned or not cleaned.isdigit():
        return None

    # YYYYMMDD (8자리)
    if len(cleaned) == 8:
        try:
            dt = datetime.strptime(cleaned, "%Y%m%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # YYMMDD (6자리) - 현재 세기 기준
    if len(cleaned) == 6:
        try:
            dt = datetime.strptime(cleaned, "%y%m%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


def _parse_rfc_date(rfc_date_str: str) -> Optional[datetime]:
    """RFC 2822 형식의 날짜 문자열을 파싱합니다. (예: 'Fri, 13 Jul 2018 08:53:08 +0900')"""
    if not rfc_date_str:
        return None
    
    try:
        # RFC 2822 형식
        return datetime.strptime(rfc_date_str, "%a, %d %b %Y %H:%M:%S %z")
    except ValueError:
        pass
    
    try:
        # 공백과 timezone 제거
        clean_str = rfc_date_str.rsplit(" ", 1)[0]
        return datetime.strptime(clean_str, "%a, %d %b %Y %H:%M:%S")
    except ValueError:
        pass
    try:
        # ISO 8601 형식 (2022-11-12T20:05:26+09:00)
        if "T" in rfc_date_str:
            # timezone 정보 제거 후 파싱
            date_part = rfc_date_str.split("T")[0]
            return datetime.strptime(date_part, "%Y-%m-%d")
    except ValueError:
        pass
    
    try:
        # YYYY-MM-DD 형식
        return datetime.strptime(rfc_date_str, "%Y-%m-%d")
    except ValueError:
        pass
    
    try:
        # YYYYMMDD 형식 (8자리 숫자)
        if len(rfc_date_str.strip()) == 8 and rfc_date_str.isdigit():
            return datetime.strptime(rfc_date_str, "%Y%m%d")
    except ValueError:
        pass
    
    return None


def _find_nearest_post(target_date_str: str) -> Optional[dict]:
    """지정된 날짜에 가장 가까운 포스트를 찾습니다."""
    if not _ARCHIVE_DB.exists():
        return None

    try:
        conn = sqlite3.connect(_ARCHIVE_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 모든 포스트를 조회 (published_date, created_at 포함)
        cursor.execute("""
            SELECT
                id,
                title,
                media_name,
                url,
                published_date,
                created_at,
                keywords,
                tags,
                platform
            FROM posts
            WHERE 
                (published_date IS NOT NULL AND published_date != '') OR
                (created_at IS NOT NULL AND created_at != '')
            ORDER BY created_at ASC, db_updated_at ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return None

        # 목표 날짜와 각 포스트 날짜 간 차이 계산
        try:
            target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
        except ValueError:
            return None

        nearest_post = None
        min_diff = timedelta(days=99999)

        for row in rows:
            pub_dt = None
            
            # 1순위: published_date
            pub_date_str = row["published_date"]
            if pub_date_str:
                try:
                    if len(pub_date_str) >= 10:
                        pub_date_str = pub_date_str[:10]
                    pub_dt = datetime.strptime(pub_date_str, "%Y-%m-%d")
                except (ValueError, IndexError, TypeError):
                    pass
            
            # 2순위: created_at (RFC 2822 형식)
            if not pub_dt:
                created_at_str = row["created_at"]
                if created_at_str:
                    pub_dt = _parse_rfc_date(created_at_str)
            
            if not pub_dt:
                continue

            diff = abs((pub_dt - target_dt).days)
            diff_td = timedelta(days=diff)

            if diff_td < min_diff:
                min_diff = diff_td
                nearest_post = dict(row)

        return nearest_post

    except sqlite3.Error:
        return None
    except Exception:
        return None
    except sqlite3.Error as e:
        import sys
        print(f"[DEBUG] SQL Error in _find_nearest_post: {e}", file=sys.stderr)
        return None
    except Exception as e:
        import sys
        print(f"[DEBUG] Exception in _find_nearest_post: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None


def find_post_by_date(date_input: str) -> str:
    """사용자 입력 날짜를 기반으로 가장 가까운 포스트를 찾아 반환합니다."""
    parsed_date = _parse_date(date_input)
    if not parsed_date:
        return (
            f"❌ 날짜 형식이 잘못되었습니다. "
            f"YYYYMMDD (예: 20260309) 또는 YYMMDD (예: 260309) 형식을 사용하세요."
        )

    if not _ARCHIVE_DB.exists():
        return f"[ERROR] 아카이브 데이터베이스를 찾을 수 없습니다: {_ARCHIVE_DB}"

    post = _find_nearest_post(parsed_date)
    if not post:
        # 더 자세한 에러 메시지 제공
        try:
            conn = sqlite3.connect(_ARCHIVE_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM posts WHERE created_at IS NOT NULL AND created_at != ''")
            dated_posts_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM posts")
            total_posts_count = cursor.fetchone()[0]
            conn.close()
            
            if dated_posts_count == 0:
                return (
                    f"❌ {parsed_date} 근처의 포스트를 찾을 수 없습니다.\n"
                    f"정보: 아카이브에 {total_posts_count}개의 포스트가 있지만, "
                    f"생성일/발행일 정보가 있는 포스트는 없습니다.\n"
                    f"💡 대신 '/search <키워드>' 명령으로 특정 키워드를 검색해보세요."
                )
            else:
                return (
                    f"❌ {parsed_date} 근처의 포스트를 찾을 수 없습니다.\n"
                    f"정보: 아카이브에 {total_posts_count}개 중 {dated_posts_count}개의 포스트만 "
                    f"날짜 정보를 가지고 있습니다.\n"
                    f"💡 다른 날짜를 시도하거나 '/search <키워드>' 명령으로 검색해보세요."
                )
        except Exception:
            return f"❌ {parsed_date} 근처의 포스트를 찾을 수 없습니다."

    # 목표 날짜로부터의 거리 계산 (UI 표시용)
    try:
        target_dt = datetime.strptime(parsed_date, "%Y-%m-%d")
        
        # published_date 또는 created_at에서 날짜 추출
        pub_date_str = None
        pub_dt = None
        
        # 1순위: published_date
        if post["published_date"]:
            try:
                pub_date_str = post["published_date"][:10] if post["published_date"] else ""
                pub_dt = datetime.strptime(pub_date_str, "%Y-%m-%d")
            except (ValueError, IndexError, TypeError):
                pass
        
        # 2순위: created_at
        if not pub_dt and post.get("created_at"):
            pub_dt = _parse_rfc_date(post["created_at"])
            if pub_dt:
                pub_date_str = pub_dt.strftime("%Y-%m-%d")
        
        if pub_dt:
            days_diff = abs((pub_dt - target_dt).days)
            diff_str = f" (목표일로부터 {days_diff}일 차이)" if days_diff > 0 else " (정확한 날짜)"
        else:
            diff_str = ""
            pub_date_str = "(날짜 미상)"
    except (ValueError, IndexError, TypeError, AttributeError):
        diff_str = ""
        pub_date_str = "(날짜 미상)"

    title = post["title"] or "(제목 없음)"
    media_name = post["media_name"] or "(미디어 미상)"
    platform = post["platform"] or "(플랫폼 미상)"
    url = post["url"] or ""
    published = pub_date_str or "(날짜 미상)"
    keywords = (post["keywords"] or "")[:100]

    result = [
        f"📅 {parsed_date} 가장 가까운 포스트{diff_str}:\n",
        f"📌 {title}\n",
        f"📝 {media_name} | {platform}\n",
        f"📆 {published}\n",
    ]

    if keywords:
        result.append(f"🏷️ {keywords}\n")

    if url:
        result.append(f"🔗 {url}\n")

    return "".join(result)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python diary.py <YYYYMMDD|YYMMDD>")
        sys.exit(1)

    date_input = sys.argv[1]
    result = find_post_by_date(date_input)
    print(result)
