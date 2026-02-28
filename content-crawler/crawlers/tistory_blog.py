# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""티스토리 블로그 RSS 크롤러"""

import feedparser
import requests
from typing import Dict, List, Optional
import time


class TistoryBlogCrawler:
    """간단한 티스토리 블로그 RSS 크롤러"""

    def __init__(self, blog_url: str, request_interval: float = 1.0):
        """
        Args:
            blog_url: 블로그 기본 주소 (예: https://frankler.tistory.com)
            request_interval: 요청 간격 (초)
        """
        self.blog_url = blog_url.rstrip("/")
        self.rss_url = f"{self.blog_url}/rss"
        self.request_interval = request_interval
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
            post = {
                "title": entry.get("title", "제목 없음"),
                "published": entry.get("published", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
            }
            posts.append(post)
            time.sleep(self.request_interval)
        return posts

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
                posts.append({"title": "", "published": "", "link": href, "summary": ""})
            print(f"[i] 사이트맵에서 {len(posts)}개 링크를 찾았습니다.")
        except Exception as e:
            print(f"[!] 사이트맵 읽기 실패: {e}")
        return posts

    def crawl(self, max_posts: int = None, use_sitemap: bool = False) -> List[Dict]:
        print(f"[*] 티스토리 블로그 크롤러 시작 ({self.blog_url})")
        feed = self.fetch_rss()
        if not feed:
            return []
        posts = self.parse_feed_entries(feed, max_posts)

        if use_sitemap and (max_posts is None or len(posts) < max_posts):
            print("[i] 사이트맵 옵션 활성화: sitemap.xml에서 추가 링크를 수집합니다.")
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
