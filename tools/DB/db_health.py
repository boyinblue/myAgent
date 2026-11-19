"""Simple DB health checks for archive_index.db."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "archive" / "archive_index.db"


def check_missing_dates(db_path: Path, platform: str, limit: int) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total = cur.execute(
        "SELECT COUNT(*) AS cnt FROM posts WHERE platform = ?",
        (platform,),
    ).fetchone()["cnt"]

    with_dates = cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM posts
        WHERE platform = ?
          AND published_date IS NOT NULL
          AND published_date != ''
          AND published_date != 'None'
        """,
        (platform,),
    ).fetchone()["cnt"]

    missing = total - with_dates
    ratio = (missing * 100.0 / total) if total else 0.0

    print(f"[INFO] platform: {platform}")
    print(f"[INFO] total posts: {total}")
    print(f"[INFO] with published_date: {with_dates}")
    print(f"[INFO] missing published_date: {missing} ({ratio:.2f}%)")

    rows = cur.execute(
        """
        SELECT id, title, url, published_date, created_at
        FROM posts
        WHERE platform = ?
          AND (published_date IS NULL OR published_date = '' OR published_date = 'None')
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (platform, limit),
    ).fetchall()

    if rows:
        print("\n[INFO] sample missing-date rows:")
        for row in rows:
            title = (row["title"] or "")[:70]
            print(f"  - id={row['id']} title={title}")
            print(f"    url={row['url']}")
            print(f"    published_date={row['published_date']} created_at={row['created_at']}")

    conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive DB health checks")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Path to archive_index.db (default: ./archive/archive_index.db)",
    )
    parser.add_argument("--platform", default="Tistory", help="Platform name to check")
    parser.add_argument(
        "--check",
        default="missing_dates",
        choices=["missing_dates"],
        help="Health check type",
    )
    parser.add_argument("--limit", type=int, default=20, help="Sample row count")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    if not db_path.exists():
        print(f"[ERROR] DB not found: {db_path}")
        return 1

    if args.check == "missing_dates":
        return check_missing_dates(db_path=db_path, platform=args.platform, limit=int(args.limit))

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
