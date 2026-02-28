# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""GitHub Pages 정적 사이트 크롤러"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import time
import re


class GitHubPagesCrawler:
    """GitHub Pages와 유사한 정적 사이트의 블로그 포스트를 크롤링합니다."""

    def __init__(self, blog_url: str, request_interval: float = 1.0):
        """
        Args:
            blog_url: 블로그 기본 주소 (예: https://boyinblue.github.io)
            request_interval: 요청 간격 (초)
        """
        self.blog_url = blog_url.rstrip("/")
        self.request_interval = request_interval
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def _extract_date_from_url(self, url: str) -> Optional[str]:
        """URL에서 날짜 패턴을 추출합니다 (YYYY-MM-DD 형식)."""
        match = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", url)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        return None

    def crawl_index_page(self, index_url: Optional[str] = None) -> List[Dict]:
        """
        블로그 인덱스 페이지를 파싱하여 포스트 링크를 찾습니다.

        Args:
            index_url: 인덱스 페이지 URL (기본: /blog, /posts, 또는 루트)

        Returns:
            포스트 메타데이터 리스트
        """
        posts: List[Dict] = []

        # 가능한 인덱스 페이지 경로
        if not index_url:
            possible_paths = ["", "/blog", "/posts", "/archive"]
        else:
            possible_paths = [index_url]

        for path in possible_paths:
            url = f"{self.blog_url}{path}" if path else self.blog_url
            try:
                print(f"[*] {url}에서 포스트 링크 탐색 중...")
                resp = requests.get(url, headers=self.headers, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                # 모든 링크 추출
                for link in soup.find_all("a", href=True):
                    href = link["href"]

                    # 상대 URL을 절대 URL로 변환
                    if href.startswith("/"):
                        href = f"{self.blog_url}{href}"
                    elif not href.startswith("http"):
                        href = f"{self.blog_url}/{href}"

                    # 외부 링크 제외
                    if not href.startswith(self.blog_url):
                        continue

                    title = link.get_text(strip=True)
                    if not title:
                        continue

                    # 날짜 추출
                    published = self._extract_date_from_url(href)

                    posts.append({
                        "title": title,
                        "published": published or "",
                        "link": href,
                        "summary": "",
                    })

                print(f"[i] {len(posts)}개 링크를 찾았습니다.")
                time.sleep(self.request_interval)
                break  # 첫 번째 성공한 경로에서 중단

            except Exception as e:
                print(f"[!] {url} 크롤 실패: {e}")
                continue

        # 중복 제거
        unique_posts = {p["link"]: p for p in posts}.values()
        return list(unique_posts)

    def fetch_post_content(self, post_url: str) -> Optional[str]:
        """포스트 본문을 가져옵니다."""
        try:
            print(f"[*] 포스트 본문 다운로드: {post_url}")
            response = requests.get(post_url, headers=self.headers, timeout=10)
            response.encoding = "utf-8"
            response.raise_for_status()

            # HTML 파싱 - 일반적인 블로그 콘텐츠 영역 찾기
            soup = BeautifulSoup(response.text, "html.parser")
            content_div = (
                soup.find("article")
                or soup.find("div", {"class": re.compile(r"content|post|main")})
                or soup.find("main")
            )

            if not content_div:
                print(f"[!] 본문 영역을 찾을 수 없습니다.")
                return ""

            text = content_div.get_text(separator="\n", strip=True)
            return text

        except Exception as e:
            print(f"[ERROR] 본문 다운로드 실패 ({post_url}): {e}")
            return ""

    def crawl(
        self,
        fetch_content: bool = False,
        max_posts: int = None,
        index_url: Optional[str] = None,
    ) -> List[Dict]:
        """
        정적 사이트를 크롤링합니다.

        Args:
            fetch_content: 포스트 본문도 가져올지 여부
            max_posts: 최대 크롤링 포스트 수
            index_url: 블로그 인덱스 페이지 경로

        Returns:
            포스트 리스트
        """
        print(f"[*] GitHub Pages 크롤러 시작 ({self.blog_url})")

        posts = self.crawl_index_page(index_url)
        if max_posts:
            posts = posts[:max_posts]

        if fetch_content and posts:
            print(f"\n[*] {len(posts)}개 포스트의 본문을 다운로드합니다...")
            enriched_posts = []
            for idx, post in enumerate(posts):
                if post.get("link"):
                    content = self.fetch_post_content(post["link"])
                    post["content"] = content
                    enriched_posts.append(post)

                    if (idx + 1) % 10 == 0:
                        print(f"[+] {idx + 1}/{len(posts)} 완료")

                    time.sleep(self.request_interval)

            posts = enriched_posts

        print(f"[+] 총 {len(posts)}개 포스트 크롤링 완료")
        return posts
