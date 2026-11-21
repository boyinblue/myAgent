#!/usr/bin/env python3
"""Extract Naver Blog post URLs and publication dates from PDFs in this folder."""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

from pypdf import PdfReader


START_MONTH = date(2014, 1, 1)
END_MONTH = date(2026, 12, 1)
URL_PATTERN = re.compile(
    r"https?://(?:m\.)?blog\.naver\.com/[^\s<>\"']+",
    re.IGNORECASE,
)
DATE_PATTERNS = (
    re.compile(
        r"(?P<year>\d{4})\s*[./-]\s*(?P<month>\d{1,2})"
        r"\s*[./-]\s*(?P<day>\d{1,2})"
    ),
    re.compile(
        r"(?P<year>\d{4})년\s*(?P<month>\d{1,2})월\s*(?P<day>\d{1,2})일?"
    ),
)
TRAILING_URL_PUNCTUATION = ".,;:!?)]}"
OWNER_BLOG_ID = "boyinblue"


@dataclass
class ExtractedUrl:
    url: str
    blog_id: str
    is_owner_post: bool
    source_pdf: str
    page: int
    dates: set[date] = field(default_factory=set)


def parse_date(text: str) -> date | None:
    matches = []
    for pattern in DATE_PATTERNS:
        matches.extend(pattern.finditer(text))
    for match in sorted(matches, key=lambda item: item.start()):
        try:
            return date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )
        except ValueError:
            continue
    return None


def find_publication_date(text: str) -> date | None:
    return parse_date(text)


def get_blog_identity(url: str) -> tuple[str, str, bool] | None:
    parsed = urlsplit(url)
    if parsed.hostname is None or parsed.hostname.lower() not in {
        "blog.naver.com",
        "m.blog.naver.com",
    }:
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)
    if path_parts and path_parts[0].lower() in {"postview.nhn", "postview.naver"}:
        blog_id = query.get("blogId", [""])[0]
        post_id = query.get("logNo", [""])[0]
    else:
        blog_id = path_parts[0] if path_parts else ""
        post_id = path_parts[1] if len(path_parts) > 1 else ""
        if not post_id:
            post_id = query.get("logNo", [""])[0]
        if not blog_id:
            blog_id = query.get("blogId", [""])[0]

    is_owner_post = blog_id.lower() == OWNER_BLOG_ID and bool(post_id)
    if is_owner_post:
        canonical_url = f"https://blog.naver.com/{OWNER_BLOG_ID}/{post_id}"
    else:
        canonical_host = "blog.naver.com"
        canonical_path = parsed.path.rstrip("/") or "/"
        canonical_url = urlunsplit(
            ("https", canonical_host, canonical_path, parsed.query, "")
        )
    return canonical_url, blog_id, is_owner_post


def extract_urls(pdf_paths: list[Path]) -> tuple[list[ExtractedUrl], int, int]:
    urls_by_key: dict[str, ExtractedUrl] = {}
    pages_scanned = 0
    pages_with_urls = 0
    total = len(pdf_paths)

    for idx, pdf_path in enumerate(pdf_paths, start=1):
        print(f"[{idx}/{total}] Reading {pdf_path.name}......", flush=True)
        reader = PdfReader(str(pdf_path), strict=False)
        for page_number, page in enumerate(reader.pages, start=1):
            pages_scanned += 1
            text = page.extract_text() or ""
            urls = {
                match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
                for match in URL_PATTERN.finditer(text)
            }
            identities = {
                identity
                for url in urls
                if (identity := get_blog_identity(url)) is not None
            }
            if not identities:
                continue

            pages_with_urls += 1
            published = find_publication_date(text)
            for canonical_url, blog_id, is_owner_post in identities:
                record = urls_by_key.get(canonical_url)
                if record is None:
                    record = ExtractedUrl(
                        url=canonical_url,
                        blog_id=blog_id,
                        is_owner_post=is_owner_post,
                        source_pdf=pdf_path.name,
                        page=page_number,
                    )
                    urls_by_key[canonical_url] = record
                if is_owner_post and published:
                    record.dates.add(published)

    records = sorted(urls_by_key.values(), key=lambda record: record.url)
    return records, pages_scanned, pages_with_urls


def write_url_list(path: Path, records: list[ExtractedUrl]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=(
                "date",
                "url",
                "blog_id",
                "is_owner_post",
                "date_status",
                "source_pdf",
                "page",
            ),
        )
        writer.writeheader()
        writer.writerows(
            {
                "date": next(iter(record.dates)).isoformat()
                if record.is_owner_post and len(record.dates) == 1
                else "",
                "url": record.url,
                "blog_id": record.blog_id,
                "is_owner_post": record.is_owner_post,
                "date_status": (
                    "not_owner_post"
                    if not record.is_owner_post
                    else "dated"
                    if len(record.dates) == 1
                    else "ambiguous"
                    if len(record.dates) > 1
                    else "undated"
                ),
                "source_pdf": record.source_pdf,
                "page": record.page,
            }
            for record in records
        )


def write_readme(
    path: Path,
    pdf_paths: list[Path],
    records: list[ExtractedUrl],
    pages_scanned: int,
    pages_with_urls: int,
) -> None:
    owner_posts = [record for record in records if record.is_owner_post]
    dated_owner_posts = [
        record for record in owner_posts if len(record.dates) == 1
    ]
    counts = Counter(
        (next(iter(record.dates)).year, next(iter(record.dates)).month)
        for record in dated_owner_posts
    )
    ambiguous_dates = sum(len(record.dates) > 1 for record in owner_posts)
    undated_posts = sum(not record.dates for record in owner_posts)
    outside_range = sum(
        not START_MONTH
        <= date(next(iter(record.dates)).year, next(iter(record.dates)).month, 1)
        <= END_MONTH
        for record in dated_owner_posts
    )
    lines = [
        "# 네이버 블로그 PDF URL 추출",
        "",
        "이 디렉터리에 넣은 네이버 블로그 PDF에서 네이버 블로그 URL을 추출합니다. "
        f"월별 글 수는 `{OWNER_BLOG_ID}` 계정의 게시글 URL 중 날짜를 하나로 판별할 수 있는 항목을 집계합니다.",
        "",
        "## 실행 방법",
        "",
        "Python 3.10 이상과 `pypdf`가 필요합니다.",
        "",
        "```powershell",
        "python -m pip install pypdf",
        "python extract_naver_blog_urls.py",
        "python crawl_uncrawled_urls.py",
        "```",
        "",
        "스크립트는 현재 디렉터리의 PDF 전체를 읽어 `blog_urls.csv`와 이 README를 갱신합니다. "
        "CSV에는 추출한 전체 네이버 블로그 URL, 블로그 ID, 게시글 여부, 날짜 판별 상태, "
        "원본 PDF 파일명, 페이지 번호가 포함됩니다. "
        "`date_status`가 `ambiguous` 또는 `undated`인 소유자 게시글은 월별 집계에서 제외됩니다.",
        "`crawl_uncrawled_urls.py`는 CSV의 `boyinblue` 게시글 중 프로젝트 아카이브에 없는 URL만 "
        "기존 네이버 크롤러로 가져옵니다. robots.txt 정책을 따르며, 결과는 `crawl_results.csv`에 기록합니다. "
        "아카이브 DB를 진행 상태로 사용하므로 중단 후 다시 실행해도 이미 수집된 글은 건너뜁니다.",
        "",
        "## 처리 결과",
        "",
        f"- PDF 파일: {len(pdf_paths)}개",
        f"- 검사한 페이지: {pages_scanned:,}페이지",
        f"- URL이 포함된 페이지: {pages_with_urls:,}페이지",
        f"- 중복 제거한 전체 블로그 URL: {len(records):,}개",
        f"- `{OWNER_BLOG_ID}` 게시글 URL: {len(owner_posts):,}개",
        f"- 날짜를 하나로 판별한 소유자 게시글: {len(dated_owner_posts):,}개",
        f"- 날짜가 없거나 여러 날짜로 판별된 소유자 게시글: "
        f"{undated_posts + ambiguous_dates:,}개 "
        f"(날짜 없음 {undated_posts:,}, 날짜 모호 {ambiguous_dates:,})",
        f"- 지정한 집계 범위 밖의 날짜: {outside_range:,}개",
        "- 집계 기간: 2014년 1월~2026년 12월",
        "",
        "월별 빈칸은 현재 폴더의 PDF에서 해당 월로 판별된 글이 없다는 뜻이며, "
        "그 달에 블로그 글이 없었다는 뜻은 아닙니다.",
        "",
        "## 월별 게시글 수",
        "",
        "| 연도 | 1월 | 2월 | 3월 | 4월 | 5월 | 6월 | 7월 | 8월 | 9월 | 10월 | 11월 | 12월 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    month_widths = {
        month: max(
            2,
            *(len(f"{counts[(year, month)]:,}") for year in range(START_MONTH.year, END_MONTH.year + 1)),
        )
        for month in range(1, 13)
    }
    for year in range(START_MONTH.year, END_MONTH.year + 1):
        monthly_counts = " | ".join(
            (
                f"{counts[(year, month)]:02,}" if counts[(year, month)] else ""
            ).rjust(month_widths[month])
            for month in range(1, 13)
        )
        lines.append(f"| {year} | {monthly_counts} |")
    lines.extend(
        [
            "",
            "## 비고",
            "",
            "- 2016년에는 작성된 블로그 글이 없습니다.",
            "- 2020년 9월부터 12월까지 작성된 블로그 글이 없습니다.",
            "",
            "## 입력 PDF",
            "",
        ]
    )
    lines.extend(f"- `{pdf_path.name}`" for pdf_path in pdf_paths)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    directory = Path(__file__).resolve().parent
    pdf_paths = sorted(
        (path for path in directory.glob("*.pdf") if path.is_file()),
        key=lambda path: path.name.casefold(),
    )
    if not pdf_paths:
        print(f"No PDF files found in {directory}", file=sys.stderr)
        return 1

    records, pages_scanned, pages_with_urls = extract_urls(pdf_paths)

    write_url_list(directory / "blog_urls.csv", records)
    write_readme(
        directory / "README.md",
        pdf_paths,
        records,
        pages_scanned,
        pages_with_urls,
    )
    print(
        f"Extracted {len(records):,} unique URLs from {len(pdf_paths)} PDFs "
        f"({pages_scanned:,} pages scanned, {pages_with_urls:,} URL-bearing pages)."
    )
    print(f"URL list: {directory / 'blog_urls.csv'}")
    print(f"Monthly counts: {directory / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
