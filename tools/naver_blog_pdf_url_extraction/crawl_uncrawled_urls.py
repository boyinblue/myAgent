#!/usr/bin/env python3
"""Crawl owner blog URLs from blog_urls.csv that are not in the local archive."""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


OWNER_BLOG_ID = "boyinblue"
BATCH_SIZE = 10


def load_owner_urls(csv_path: Path) -> list[str]:
    urls = set()
    with csv_path.open("r", newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            if row.get("is_owner_post", "").strip().lower() != "true":
                continue
            key = post_key(row.get("url", ""))
            if not key or key[0] != OWNER_BLOG_ID:
                raise ValueError(f"Invalid owner post URL in {csv_path.name}")
            urls.add(f"https://blog.naver.com/{key[0]}/{key[1]}")
    return sorted(urls)


def post_key(url: str) -> tuple[str, str] | None:
    parsed = urlsplit(url.strip())
    if parsed.hostname is None or parsed.hostname.lower() not in {
        "blog.naver.com",
        "m.blog.naver.com",
    }:
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)
    if path_parts and path_parts[0].lower() in {
        "postview.naver",
        "postview.nhn",
    }:
        blog_id = (query.get("blogId") or [""])[0].lower()
        post_id = (query.get("logNo") or [""])[0]
    else:
        blog_id = path_parts[0].lower() if path_parts else ""
        post_id = path_parts[1] if len(path_parts) > 1 else ""
        if not post_id:
            post_id = (query.get("logNo") or [""])[0]
    if not blog_id or not post_id.isdigit():
        return None
    return blog_id, post_id


def is_archived(archive_mgr, url: str) -> bool:
    identity = post_key(url)
    if identity is None:
        return False
    blog_id, post_id = identity
    for scheme in ("https", "http"):
        for host in ("blog.naver.com", "m.blog.naver.com"):
            candidate = f"{scheme}://{host}/{blog_id}/{post_id}"
            if archive_mgr.is_archived(candidate):
                return True
    return False


def write_results(path: Path, results: dict[str, tuple[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.writer(output)
        writer.writerow(("url", "status", "detail"))
        writer.writerows(
            (url, status, detail)
            for url, (status, detail) in sorted(results.items())
        )


def last_log_line(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1][:500] if lines else ""


def run(dry_run: bool) -> int:
    directory = Path(__file__).resolve().parent
    project_root = directory.parents[1]
    archive_root = project_root / "archive"
    archive_db = archive_root / "archive_index.db"
    csv_path = directory / "blog_urls.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(f"URL list not found: {csv_path}")
    if not archive_db.is_file():
        raise FileNotFoundError(f"Project archive database not found: {archive_db}")

    crawler_path = project_root / "content-crawler"
    sys.path.insert(0, str(crawler_path))
    from archive_manager import ArchiveManager
    from crawlers.naver_blog import NaverBlogCrawler
    from main import CRAWLER_VERSION, archive_posts

    urls = load_owner_urls(csv_path)
    archive_mgr = ArchiveManager(
        archive_root=str(archive_root),
        db_path=str(archive_db),
    )
    try:
        results = {
            url: ("already_archived", "")
            for url in urls
            if is_archived(archive_mgr, url)
        }
        pending = [url for url in urls if url not in results]
        print(
            f"Owner post URLs: {len(urls)}; already archived: {len(results)}; "
            f"to crawl: {len(pending)}."
        )
        if dry_run:
            return 0

        results_path = directory / "crawl_results.csv"
        write_results(results_path, results)
        crawler = NaverBlogCrawler(
            OWNER_BLOG_ID,
            request_interval=1.0,
            request_interval_min=1.0,
            request_interval_max=1.5,
            archive_mgr=archive_mgr,
            crawler_version=CRAWLER_VERSION,
        )
        for start in range(0, len(pending), BATCH_SIZE):
            batch_urls = pending[start : start + BATCH_SIZE]
            fetched_posts = []
            for url in batch_urls:
                captured = io.StringIO()
                with redirect_stdout(captured):
                    post = crawler.parse_url(url, respect_robots=True)
                if post is None:
                    log = captured.getvalue()
                    status = (
                        "robots_blocked"
                        if "robots.txt 정책으로 건너뜀" in log
                        else "fetch_failed"
                    )
                    results[url] = (status, last_log_line(log))
                else:
                    fetched_posts.append(post)

            if fetched_posts:
                captured = io.StringIO()
                with redirect_stdout(captured):
                    archive_posts(
                        fetched_posts,
                        archive_mgr,
                        platform_type="NaverBlog",
                        media_name=OWNER_BLOG_ID,
                    )
                archive_log = captured.getvalue()
                for post in fetched_posts:
                    url = post.get("link", "")
                    if is_archived(archive_mgr, url):
                        results[url] = ("archived", "")
                    else:
                        results[url] = (
                            "archive_failed",
                            last_log_line(archive_log),
                        )

            write_results(results_path, results)
            processed = min(start + len(batch_urls), len(pending))
            counts = Counter(status for status, _ in results.values())
            print(
                f"Progress: {processed}/{len(pending)} attempts; "
                f"archived this run: {counts['archived']}; "
                f"fetch/robots/archive failures: "
                f"{counts['fetch_failed'] + counts['robots_blocked'] + counts['archive_failed']}."
            )

        counts = Counter(status for status, _ in results.values())
        print(
            f"Finished. Already archived: {counts['already_archived']}; "
            f"newly archived: {counts['archived']}; "
            f"fetch failed: {counts['fetch_failed']}; "
            f"robots blocked: {counts['robots_blocked']}; "
            f"archive failed: {counts['archive_failed']}."
        )
        print(f"Results: {results_path}")
        return int(
            bool(
                counts["fetch_failed"]
                or counts["robots_blocked"]
                or counts["archive_failed"]
            )
        )
    finally:
        archive_mgr.conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count uncrawled owner URLs without making network requests.",
    )
    args = parser.parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
