"""Archive maintenance utilities.

Commands:
- regen-index: regenerate archive/index.json from markdown files
- scan-nonpost: detect (and optionally delete) non-post markdown files
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "archive"


def _extract_frontmatter(path: Path) -> Tuple[Dict[str, str], str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}, ""

    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    fm_text = text[3:end]
    body = text[end + 4 :].strip()
    meta: Dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip("'\"")
    return meta, body


def _detect_non_post_reason(url: str, title: str, body: str) -> Optional[str]:
    normalized_url = (url or "").strip()
    normalized_title = (title or "").strip()
    body_text = (body or "").strip()

    if "/category/" in normalized_url:
        return "tistory_category"
    if re.search(r"tistory\.com/tag/", normalized_url, re.IGNORECASE):
        return "tistory_tag"
    if "blog.naver.com" in normalized_url and not re.search(r"/\d{6,}", normalized_url):
        return "naver_non_post"

    if body_text in {"", "(본문 없음)"}:
        alpha_title = normalized_title.replace(" ", "").replace("-", "")
        if normalized_title and normalized_title == normalized_title.upper() and alpha_title.isalpha():
            return "all_caps_no_body"

    return None


def cmd_regen_index(archive_root: Path) -> int:
    crawler_root = PROJECT_ROOT / "content-crawler"
    if str(crawler_root) not in sys.path:
        sys.path.insert(0, str(crawler_root))

    from archive_manager import ArchiveManager  # pylint: disable=import-outside-toplevel

    manager = ArchiveManager(archive_root)
    index_path = manager.update_index("all", platform="mixed")

    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    total_posts = len(index_data.get("posts", []))
    print(f"[OK] index regenerated: {index_path}")
    print(f"[OK] total posts: {total_posts}")
    return 0


def cmd_scan_nonpost(
    archive_root: Path,
    output_json: bool,
    limit: int,
    delete: bool,
    dry_run: bool,
) -> int:
    matches: List[Dict[str, str]] = []
    for md in sorted(archive_root.rglob("*.md")):
        meta, body = _extract_frontmatter(md)
        reason = _detect_non_post_reason(meta.get("url", ""), meta.get("title", ""), body)
        if not reason:
            continue

        matches.append(
            {
                "reason": reason,
                "path": str(md.relative_to(archive_root)),
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
            }
        )

    if output_json:
        print(json.dumps(matches, ensure_ascii=False, indent=2))
    else:
        print(f"[INFO] non-post candidates: {len(matches)}")
        grouped: Dict[str, int] = {}
        for row in matches:
            grouped[row["reason"]] = grouped.get(row["reason"], 0) + 1
        for reason, count in sorted(grouped.items()):
            print(f"  - {reason}: {count}")

        preview = matches if limit <= 0 else matches[:limit]
        if preview:
            print("\n[INFO] sample:")
            for row in preview:
                print(f"  - [{row['reason']}] {row['path']}")
                print(f"    title: {row['title']}")
                print(f"    url:   {row['url']}")

    if not delete:
        return 0

    db_path = archive_root / "archive_index.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    deleted_files = 0
    deleted_db_rows = 0

    for row in matches:
        file_path = archive_root / row["path"]
        if dry_run:
            print(f"[DRY-RUN] delete file: {file_path}")
        else:
            try:
                file_path.unlink(missing_ok=True)
                deleted_files += 1
            except Exception as exc:
                print(f"[WARN] failed to delete file: {file_path} ({exc})")

        url = (row.get("url") or "").strip()
        if not url:
            continue
        if dry_run:
            print(f"[DRY-RUN] delete db rows by url: {url}")
        else:
            deleted_db_rows += cur.execute("DELETE FROM posts WHERE url = ?", (url,)).rowcount

    if not dry_run:
        conn.commit()
    conn.close()

    print(f"[OK] deleted files: {deleted_files}")
    print(f"[OK] deleted db rows: {deleted_db_rows}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive maintenance utilities")
    parser.add_argument(
        "--archive-root",
        default=str(DEFAULT_ARCHIVE_ROOT),
        help="Path to archive root (default: ./archive)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("regen-index", help="Regenerate archive/index.json")

    scan = sub.add_parser("scan-nonpost", help="Scan markdown files for non-post candidates")
    scan.add_argument("--json", action="store_true", help="Print full result as JSON")
    scan.add_argument("--limit", type=int, default=20, help="Sample count to print (0 = all)")
    scan.add_argument("--delete", action="store_true", help="Delete matched files and DB rows")
    scan.add_argument("--dry-run", action="store_true", help="Preview delete actions only")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    archive_root = Path(args.archive_root).resolve()

    if not archive_root.exists():
        print(f"[ERROR] archive root not found: {archive_root}")
        return 1

    if args.command == "regen-index":
        return cmd_regen_index(archive_root)

    if args.command == "scan-nonpost":
        return cmd_scan_nonpost(
            archive_root=archive_root,
            output_json=bool(args.json),
            limit=int(args.limit),
            delete=bool(args.delete),
            dry_run=bool(args.dry_run),
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
