# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""네이버 블로그 크롤러

RSS 피드 및 포스트 본문을 크롤링합니다.
"""

import feedparser
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional, List
from datetime import datetime
import time


class NaverBlogCrawler:
    """네이버 블로그 크롤러"""

    def __init__(self, blog_id: str, rss_url: str = None, request_interval: float = 1.0):
        """
        Args:
            blog_id: 블로그 ID (예: boyinblue)
            rss_url: RSS 피드 URL을 직접 지정하면 기본 형식을 무시합니다.
            request_interval: 요청 간격 (초)
        """
        self.blog_id = blog_id
        # Naver RSS URL. 변경될 수 있으므로 옵션 허용.
        if rss_url:
            self.rss_url = rss_url
        else:
            self.rss_url = f"https://rss.blog.naver.com/{blog_id}.xml"
        self.request_interval = request_interval
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def fetch_rss(self) -> Optional[feedparser.FeedParserDict]:
        """RSS 피드를 가져옵니다."""
        try:
            print(f"[*] RSS 피드를 가져오는 중... ({self.rss_url})")
            response = requests.get(self.rss_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if feed.bozo:
                print(f"[!] RSS 파싱 경고: {feed.bozo_exception}")

            return feed
        except Exception as e:
            print(f"[ERROR] RSS 가져오기 실패: {e}")
            return None

    def _crawl_link_page(self, url: str) -> List[Dict]:
        """블로그 페이지를 스크레이핑하여 추가 포스트 링크를 가져옵니다."""
        print(f"[*] {url} 스크레이핑 중...")
        posts: List[Dict] = []
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 링크 식별: logNo 파라미터 포함
            for a in soup.find_all("a", href=True):
                href = a["href"]
                print(f"[*] 발견된 링크: {href}")
                if "logNo=" in href and self.blog_id in href:
                    title = a.get_text(strip=True)
                    if not title:
                        continue
                    print(f"  [*] 페이지에서 발견된 포스트: {title} ({href})")
                    posts.append({"title": title, "link": href, "published": ""})
        except Exception as e:
            print(f"[!] 리스트 페이지 {url} 크롤 실패: {e}")
        return posts

    def parse_feed_entries(
        self, feed: feedparser.FeedParserDict, max_posts: int = None
    ) -> List[Dict]:
        """RSS 피드에서 포스트 메타데이터를 추출합니다."""
        posts = []

        if not feed or not feed.entries:
            print("[!] 피드에 항목이 없습니다.")
            return posts

        entries = feed.entries[:max_posts] if max_posts else feed.entries

        for idx, entry in enumerate(entries):
            post = {
                "title": entry.get("title", "제목 없음"),
                "published": entry.get("published", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "category": entry.get("category", ""),
            }
            posts.append(post)

            # 속도 제한
            if idx > 0 and idx % 10 == 0:
                print(f"[*] {idx}개 포스트 메타데이터 추출... 대기 중")
                time.sleep(self.request_interval)

        return posts

    def crawl(
        self,
        max_posts: int = None,
    ) -> List[Dict]:
        """
        블로그를 크롤링합니다.

        Args:
            max_posts: 최대 크롤링 포스트 수

        Returns:
            포스트 리스트
        """
        print(f"[*] 네이버 블로그 크롤러 시작 (블로그: {self.blog_id})")

        posts: List[Dict] = []
        feed = self.fetch_rss()
        if feed:
            posts = self.parse_feed_entries(feed, max_posts)

        print(f"[+] 총 {len(posts)}개 포스트 크롤링 완료")
        return posts
