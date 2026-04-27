# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""티스토리 블로그 RSS 크롤러"""

from os import link
from bs4 import BeautifulSoup
import feedparser
import re
import requests
from typing import Dict, List, Optional
import time
from datetime import datetime
import archive_manager

class TistoryBlogCrawler:
    """간단한 티스토리 블로그 RSS 크롤러"""

    def __init__(self, blog_url: str, request_interval: float = 1.0, archive_mgr=None, crawler_version: str = ""):
        """
        Args:
            blog_url: 블로그 기본 주소 (예: https://frankler.tistory.com)
            request_interval: 요청 간격 (초)
            archive_mgr: 아카이브 관리자 인스턴스
        """
        self.blog_url = blog_url.rstrip("/")
        self.rss_url = f"{self.blog_url}/rss"
        self.request_interval = request_interval
        self.archive_mgr = archive_mgr
        self.crawler_version = crawler_version
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def fetch_rss(self) -> Optional[feedparser.FeedParserDict]:
        try:
            print(f"[*] 티스토리 RSS를 가져오는 중... ({self.rss_url})")
            resp = requests.get(self.rss_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            if feed.bozo:
                print(f"[!] RSS 파싱 경고: {feed.bozo_exception}")
            return feed
        except Exception as e:
            print(f"[ERROR] 티스토리 RSS 실패: {e}")
            return None

    def parse_feed_entries(
        self, feed: feedparser.FeedParserDict, max_posts: int = None
    ) -> List[Dict]:
        posts: List[Dict] = []
        if not feed or not feed.entries:
            print("[!] 피드에 항목이 없습니다.")
            return posts
        entries = feed.entries[:max_posts] if max_posts else feed.entries
        for entry in entries:
            link = entry.get("link", "")
            if self.archive_mgr and self.crawler_version and self.archive_mgr.should_skip_crawl(link, self.crawler_version):
                continue

            post = {
                "title": entry.get("title", "제목 없음"),
                "published": entry.get("published", ""),
                "link": link,
                "summary": entry.get("summary", ""),
            }
            posts.append(post)
            #time.sleep(self.request_interval)
        return posts
    
    def parse_url(self, url):
        """단일 URL을 파싱하여 포스트 정보를 리턴합니다."""

        print(f"[*] {url}에서 포스트 정보 추출 중...")

        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.title.string if soup.title and soup.title.string else "제목 없음"

            published = ""
            published_meta = soup.find("meta", attrs={"property": "article:published_time"})
            if published_meta and published_meta.get("content"):
                published = published_meta.get("content").strip()

            if not published:
                time_tag = soup.find("time")
                if time_tag:
                    published = (time_tag.get("datetime") or time_tag.get_text(" ", strip=True) or "").strip()

            summary = ""
            og_description = soup.find("meta", attrs={"property": "og:description"})
            if og_description and og_description.get("content"):
                summary = og_description.get("content").strip()

            content_html = ""
            content_text = ""
            for selector in [
                ".tt_article_useless_p_margin",
                ".article-view",
                ".entry-content",
                "#content",
            ]:
                container = soup.select_one(selector)
                if container is not None:
                    content_html = str(container)
                    content_text = container.get_text("\n", strip=True)
                    break

            if not content_text:
                content_text = summary

            print(f"제목: {title}")

            post = {
                "title": title,
                "published": published,
                "link": url,
                "summary": summary,
                "content": content_text,
                "html": content_html,
            }
            return post

        except Exception as e:
            print(f"[!] {url}에 접근할 수 없습니다: {e}")

        return None

    def fetch_sitemap(self) -> List[Dict]:
        """블로그의 `sitemap.xml`을 가져와 포스트 링크 목록을 리턴합니다."""
        url = f"{self.blog_url}/sitemap.xml"
        print(f"[*] 사이트맵 가져오는 중... ({url})")
        posts: List[Dict] = []
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            # XML 파싱을 위해 표준 라이브러리 사용
            import xml.etree.ElementTree as ET

            root = ET.fromstring(resp.content)
            # 네임스페이스 고려
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for loc in root.findall(".//sm:loc", ns):
                href = loc.text.strip()
                # 카테고리/태그 페이지 제외
                if '/category/' in href or re.search(r'tistory\.com/tag/', href, re.IGNORECASE):
                    continue
                if self.archive_mgr:
                    if self.crawler_version and self.archive_mgr.should_skip_crawl(href, self.crawler_version):
                        continue
                post = self.parse_url(href)
                if post:
                    posts.append(post)
            print(f"[i] 사이트맵에서 {len(posts)}개 링크를 찾았습니다.")
        except Exception as e:
            print(f"[!] 사이트맵 읽기 실패: {e}")
        return posts

    def crawl(self, max_posts: int = None, archive_mgr=None) -> List[Dict]:
        print(f"[*] 티스토리 블로그 크롤러 시작 ({self.blog_url})")
        feed = self.fetch_rss()
        if not feed:
            return []
        posts = self.parse_feed_entries(feed, max_posts)

        print("[*] sitemap.xml에서 추가 링크를 수집합니다.")
        sitemap_posts = self.fetch_sitemap()
        existing = {p["link"] for p in posts}
        for sp in sitemap_posts:
            if max_posts and len(posts) >= max_posts:
                break
            if sp["link"] not in existing:
                posts.append(sp)
                existing.add(sp["link"])

        print(f"[+] 총 {len(posts)}개 포스트 크롤링 완료")
        return posts
