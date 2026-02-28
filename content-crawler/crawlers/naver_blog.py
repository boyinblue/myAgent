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

    def _crawl_list_page(self, page: int) -> List[Dict]:
        """블로그 목록 페이지를 스크레이핑하여 추가 포스트 링크를 가져옵니다."""
        posts: List[Dict] = []
        try:
            url = (
                f"https://blog.naver.com/PostList.naver?blogId={self.blog_id}"
                f"&from=postList&orderBy=post.date&page={page}"
            )
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 링크 식별: logNo 파라미터 포함
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "logNo=" in href and self.blog_id in href:
                    title = a.get_text(strip=True)
                    if not title:
                        continue
                    posts.append({"title": title, "link": href, "published": ""})
        except Exception as e:
            print(f"[!] 리스트 페이지 {page} 크롤 실패: {e}")
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

    def fetch_post_content(self, post_url: str) -> Optional[str]:
        """포스트 본문을 가져옵니다."""
        try:
            print(f"[*] 포스트 본문 다운로드: {post_url}")
            response = requests.get(post_url, headers=self.headers, timeout=10)
            response.encoding = "utf-8"
            response.raise_for_status()

            # HTML 파싱
            soup = BeautifulSoup(response.text, "html.parser")

            # 네이버 블로그 본문 영역 찾기
            # (다양한 선택자 시도)
            content_div = (
                soup.find("div", {"class": "se-main-container"})
                or soup.find("div", {"id": "postViewArea"})
                or soup.find("div", {"class": "post-view"})
            )

            if not content_div:
                print(f"[!] 본문 영역을 찾을 수 없습니다.")
                return ""

            # 텍스트 추출
            text = content_div.get_text(separator="\n", strip=True)
            return text

        except Exception as e:
            print(f"[ERROR] 본문 다운로드 실패 ({post_url}): {e}")
            return ""

    def fetch_post_with_content(self, post_url: str, post_data: Dict) -> Dict:
        """포스트 메타데이터 + 본문을 함께 반환합니다."""
        content = self.fetch_post_content(post_url)

        enriched_post = post_data.copy()
        enriched_post["content"] = content

        # 속도 제한
        time.sleep(self.request_interval)

        return enriched_post

    def _extract_internal_links(self, html: str) -> List[str]:
        """본문 HTML에서 같은 블로그의 다른 포스트 링크를 찾아 반환합니다."""
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "logNo=" in href and self.blog_id in href:
                # 절대 URL이 아닐 경우 보완
                if href.startswith("/"):
                    href = "https://blog.naver.com" + href
                if href not in links:
                    links.append(href)
        return links

    def crawl(
        self,
        fetch_content: bool = False,
        max_posts: int = None,
        full: bool = False,
        follow_internal: bool = False,
    ) -> List[Dict]:
        """
        블로그를 크롤링합니다.

        Args:
            fetch_content: Boolean, 포스트 본문도 가져올지 여부
            max_posts: 최대 크롤링 포스트 수
            full: RSS에 없는 이전 글도 함께 가져오려면 True (페이지 스크래핑)
            follow_internal: 크롤된 포스트 본문에서 블로그 내부 링크를 추출하여 추가로 수집

        Returns:
            포스트 리스트
        """
        print(f"[*] 네이버 블로그 크롤러 시작 (블로그: {self.blog_id})")

        posts: List[Dict] = []
        feed = self.fetch_rss()
        if feed:
            posts = self.parse_feed_entries(feed, max_posts)

        # RSS에 없는 글까지 확장
        if full and (max_posts is None or len(posts) < max_posts):
            print("[i] 전체 크롤 옵션 활성화: 리스트 페이지에서 추가 포스트를 스크레이핑합니다.")
            page = 1
            scraped_pages = 0
            while True:
                if max_posts and len(posts) >= max_posts:
                    break
                more = self._crawl_list_page(page)
                scraped_pages += 1
                if not more:
                    print(f"[i] 리스트 페이지 {page}에 더 이상 포스트가 없습니다 (총 {scraped_pages}페이지 크롤됨).")
                    break
                for p in more:
                    if max_posts and len(posts) >= max_posts:
                        break
                    # 중복 링크 건너뛰기
                    if p["link"] not in {x.get("link") for x in posts}:
                        posts.append(p)
                page += 1
                time.sleep(self.request_interval)
            print(f"[i] 전체 크롤링: 리스트 페이지 {scraped_pages}페이지를 확인하여 총 {len(posts)}개 포스트를 찾았습니다.")

        # 본문을 가져오기 전 혹은 후에 내부 링크 수집
        if follow_internal and posts:
            print("[i] 내부 링크 추출 옵션 활성화: 각 포스트 본문에서 같은 블로그 링크를 찾습니다.")
            seen = {p.get("link") for p in posts}
            for idx, post in enumerate(list(posts)):
                url = post.get("link")
                if not url:
                    continue
                try:
                    resp = requests.get(url, headers=self.headers, timeout=10)
                    resp.raise_for_status()
                    new_links = self._extract_internal_links(resp.text)
                    for link in new_links:
                        if link not in seen:
                            posts.append({
                                "title": "",
                                "published": "",
                                "link": link,
                                "summary": "",
                                "category": "",
                            })
                            seen.add(link)
                    time.sleep(self.request_interval)
                except Exception as e:
                    print(f"[!] 내부 링크 검색 실패 ({url}): {e}")
                if max_posts and len(posts) >= max_posts:
                    break
            print(f"[i] 내부 링크 크롤 결과, 총 {len(posts)}개 포스트 목록이 생성되었습니다.")

        if fetch_content and posts:
            print(f"\n[*] {len(posts)}개 포스트의 본문을 다운로드합니다...")
            enriched_posts = []
            for idx, post in enumerate(posts):
                if post.get("link"):
                    enriched_post = self.fetch_post_with_content(
                        post["link"], post
                    )
                    enriched_posts.append(enriched_post)

                    if (idx + 1) % 10 == 0:
                        print(f"[+] {idx + 1}/{len(posts)} 완료")

            posts = enriched_posts

        print(f"[+] 총 {len(posts)}개 포스트 크롤링 완료")
        return posts
