# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""네이버 블로그 크롤러

RSS 피드 및 포스트 본문을 크롤링합니다.
"""

import os
import feedparser
import requests
import urllib.request
import urllib.parse
import json
from typing import Dict, Optional, List
from datetime import datetime
import time
import random
from collections import deque
from urllib.parse import urlparse, parse_qs, urljoin
from urllib import robotparser

try:
    from crawlers.google_api import search_naver_blog_posts
except Exception:
    search_naver_blog_posts = None


class NaverBlogCrawler:
    """네이버 블로그 크롤러"""

    def __init__(
        self,
        blog_id: str,
        rss_url: str = None,
        request_interval: float = 1.0,
        archive_mgr=None,
        request_interval_min: float = None,
        request_interval_max: float = None,
    ):
        """
        Args:
            blog_id: 블로그 ID (예: boyinblue)
            rss_url: RSS 피드 URL을 직접 지정하면 기본 형식을 무시합니다.
            request_interval: 요청 간격 (초)
            archive_mgr: 아카이브 관리자 인스턴스
        """
        self.blog_id = blog_id
        self.archive_mgr = archive_mgr
        # Naver RSS URL. 변경될 수 있으므로 옵션 허용.
        if rss_url:
            self.rss_url = rss_url
        else:
            self.rss_url = f"https://rss.blog.naver.com/{blog_id}.xml"
        self.request_interval = request_interval
        self.request_interval_min = request_interval if request_interval_min is None else request_interval_min
        self.request_interval_max = request_interval if request_interval_max is None else request_interval_max
        if self.request_interval_min > self.request_interval_max:
            self.request_interval_min, self.request_interval_max = self.request_interval_max, self.request_interval_min
        self._robots_cache = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def _sleep_with_jitter(self):
        delay = random.uniform(self.request_interval_min, self.request_interval_max)
        time.sleep(max(0.0, delay))

    def _normalize_naver_post_url(self, url: str) -> str:
        if not url:
            return ""
        normalized_url = url.strip()

        if "blog.naver.com/PostView.naver" in normalized_url:
            parsed = urlparse(normalized_url)
            params = parse_qs(parsed.query)
            blog_id = (params.get("blogId") or [""])[0]
            log_no = (params.get("logNo") or [""])[0]
            if blog_id and log_no:
                return f"https://m.blog.naver.com/{blog_id}/{log_no}"

        if "blog.naver.com" in normalized_url and "m.blog.naver.com" not in normalized_url:
            return normalized_url.replace("//blog.naver.com", "//m.blog.naver.com")

        return normalized_url

    def _is_internal_blog_url(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if host not in {"blog.naver.com", "m.blog.naver.com"}:
            return False

        path_parts = [p for p in parsed.path.split("/") if p]
        if not path_parts:
            return False

        first = path_parts[0].lower()
        return first == self.blog_id.lower() or parsed.path.lower().startswith("/postview.naver")

    def _can_fetch_with_robots(self, target_url: str, respect_robots: bool = True) -> bool:
        if not respect_robots:
            return True

        parsed = urlparse(target_url)
        host = parsed.netloc.lower()
        if not host:
            return False

        rp = self._robots_cache.get(host)
        if rp is None:
            robots_url = f"{parsed.scheme or 'https'}://{host}/robots.txt"
            rp = robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                return True
            self._robots_cache[host] = rp

        try:
            return rp.can_fetch(self.headers.get("User-Agent", "*"), target_url)
        except Exception:
            return True

    def save_page_to_file(self, url, content):
        """다운로드 받은 페이지를 파일로 저장합니다."""
        import hashlib
        import os

        # temp 폴더 생성
        temp_dir = "./temp"
        os.makedirs(temp_dir, exist_ok=True)

        # URL을 기반으로 파일명 생성 (해시 사용)
        url_hash = hashlib.md5(url.encode()).hexdigest()
        filename = f"{url_hash}.html"
        filepath = os.path.join(temp_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[+] 페이지 저장됨: {filepath}")
        return filepath


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

    def parse_feed_entries(
        self, feed: feedparser.FeedParserDict, max_posts: int = None) -> List[Dict]:
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

    def parse_url(self, url, respect_robots: bool = True):
        """단일 URL을 파싱하여 포스트 정보를 리턴합니다."""
        print(f"[*] {url}에서 포스트 정보 추출 중...")

        try:
            normalized_url = self._normalize_naver_post_url(url)

            if normalized_url != url:
                print(f"[*] 모바일 URL로 변환: {normalized_url}")

            if not self._can_fetch_with_robots(normalized_url, respect_robots=respect_robots):
                print(f"[i] robots.txt 정책으로 건너뜀: {normalized_url}")
                return None

            self._sleep_with_jitter()

            resp = requests.get(normalized_url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            # 페이지를 파일로 저장
            saved_filepath = self.save_page_to_file(normalized_url, resp.text)

            # 저장된 파일에서 파싱
            with open(saved_filepath, "r", encoding="utf-8") as f:
                html_content = f.read()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # title 추출: og:title 우선
            og_title = soup.find("meta", attrs={"property": "og:title"})
            if og_title and og_title.get("content"):
                title = og_title.get("content").strip()
            else:
                title = soup.title.string.strip() if soup.title and soup.title.string else "제목 없음"
            print(f"제목: {title}")

            # 내부 포스트 링크만 추출 (크롤링 가능한 링크)
            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                link_text = a_tag.get_text(strip=True)
                if not href:
                    continue
                
                # 절대 URL로 변환
                absolute_url = urljoin(url, href)
                
                # 정규화 시도
                normalized = self._normalize_naver_post_url(absolute_url)
                
                # 내부 블로그 포스트 링크만 추가
                if normalized and self._is_internal_blog_url(normalized):
                    links.append({"url": normalized, "text": link_text})

            # 중복 제거
            seen_urls = set()
            unique_links = []
            for link in links:
                if link['url'] not in seen_urls:
                    seen_urls.add(link['url'])
                    unique_links.append(link)
            links = unique_links

            if links:
                print(f"[*] 내부 포스트 링크 발견: {len(links)}개")
                for i, link in enumerate(links[:5]):  # 처음 5개만 출력
                    print(f"  {i+1}. {link['url']}")

            post = {
                "title": title,
                "link": url,
                "platform": "NaverBlog",
                "media_name": self.blog_id,
                "resolved_url": normalized_url,
                "links": links,  # 추출된 링크들 추가
                "saved_file": saved_filepath,
            }

            # archive_mgr이 있으면 URL로 찾은 포스트의 title을 업데이트
            if self.archive_mgr is not None:
                try:
                    # 정규화된 URL(모바일) 우선으로 시도, 없으면 원본 URL로 시도
                    post_id = self.archive_mgr.get_post_id_by_url(normalized_url)
                    lookup_url = normalized_url
                    
                    if not post_id and normalized_url != url:
                        post_id = self.archive_mgr.get_post_id_by_url(url)
                        lookup_url = url
                    
                    if post_id:
                        self.archive_mgr.update_post_metadata(post_id, title=title)
                        print(f"[+] 아카이브 업데이트(제목): ID={post_id}, title={title}, lookup_url={lookup_url}, platform={post['platform']}, media_name={post['media_name']}")
                    else:
                        print(f"[i] URL에 해당하는 포스트가 아카이브에 없습니다: {url}")
                except Exception as e:
                    print(f"[!] 아카이브 업데이트 실패: {e}")
            else:
                print(f"[!] 아카이브 관리자 인스턴스가 제공되지 않았습니다. 메타데이터 업데이트를 건너뜁니다.")

            return post

        except Exception as e:
            print(f"[!] {url}에 접근할 수 없습니다: {e}")

        return None

    def crawl_internal_links(
        self,
        seed_urls: List[str],
        max_pages: int = 100,
        max_depth: int = 2,
        respect_robots: bool = True,
    ) -> List[Dict]:
        """내부 링크를 BFS로 순회하며 포스트를 수집합니다."""
        discovered: List[Dict] = []
        queue = deque()
        visited = set()

        for seed in seed_urls:
            normalized = self._normalize_naver_post_url(seed)
            if normalized and normalized not in visited:
                queue.append((normalized, 0))

        while queue and len(visited) < max_pages:
            current_url, depth = queue.popleft()
            if current_url in visited:
                continue
            visited.add(current_url)

            if not self._is_internal_blog_url(current_url):
                continue

            if not self._can_fetch_with_robots(current_url, respect_robots=respect_robots):
                print(f"[i] robots.txt 정책으로 건너뜀: {current_url}")
                continue

            post = self.parse_url(current_url, respect_robots=respect_robots)
            if post:
                discovered.append(post)

                if depth < max_depth:
                    # parse_url()에서 이미 정규화되고 필터링된 링크를 받음
                    for link in post.get("links", []):
                        normalized_url = link.get("url")
                        if normalized_url and normalized_url not in visited:
                            queue.append((normalized_url, depth + 1))

        return discovered

    def get_naver_blog_list(self, client_id, client_secret, blog_id):
        results = []
        display = 100  # 한 번에 가져올 개수 (최대 100)
        start = 1      # 시작 위치
        
        # 본인 블로그 글만 찾기 위해 'site:blog.naver.com/아이디' 쿼리 사용
        encText = urllib.parse.quote(f"\"blog.naver.com/{blog_id}\"")
        
        while start <= 1000:  # 검색 API는 최대 1000개까지 조회 가능
            url = f"https://openapi.naver.com/v1/search/blog.json?query={encText}&display={display}&start={start}"
            
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            
            try:
                response = urllib.request.urlopen(request)
                rescode = response.getcode()
                
                if rescode == 200:
                    response_body = response.read()
                    data = json.loads(response_body.decode('utf-8'))
                    
                    items = data.get('items', [])
                    if not items:
                        break

                    for item in items:
                        # 링크가 블로그 글인지 확인 (네이버 블로그 글은 'blog.naver.com' 포함)
                        print(f"Checking link: {item.get('link', '')}")
                        if f'blog.naver.com/{self.blog_id}' in item.get('link', ''):
                            results.append({
                                "title": item.get("title", "제목 없음"),
                                "published": item.get("postdate", ""),
                                "link": item.get("link", ""),
                                "summary": item.get("description", ""),
                            })
                        
                    start += display
                else:
                    print(f"Error Code: {rescode}")
                    break
            except Exception as e:
                print(f"Exception: {e}")
                break
                
        return results

    def crawl(
        self,
        max_posts: int = None,
        follow_internal_links: bool = False,
        internal_max_pages: int = 100,
        internal_max_depth: int = 2,
        respect_robots: bool = True,
        use_google_search: bool = False,
        google_cse_id: str = "",
    ) -> List[Dict]:
        """
        블로그를 크롤링합니다.

        Args:
            max_posts: 최대 크롤링 포스트 수

        Returns:
            포스트 리스트
        """

        posts: List[Dict] = []

        print(f"[*] RSS 크롤러 시작(블로그: {self.blog_id})")

        feed = self.fetch_rss()
        if feed:
            posts = self.parse_feed_entries(feed, max_posts)

        print(f"[*] Naver API를 통한 추가 포스트 검색 중...")

        # Naver API를 사용하여 추가 포스트 검색
        client_id = os.getenv("NAVER_CLIENT_ID")
        client_secret = os.getenv("NAVER_CLIENT_SECRET")

        if client_id and client_secret:
            api_posts = self.get_naver_blog_list(client_id, client_secret, self.blog_id)
            print(f"Raw Data from Naver API: {api_posts[:2]}...")  # API 응답의 일부를 출력하여 확인
            posts.extend(api_posts)

        if use_google_search and search_naver_blog_posts:
            google_key = os.getenv("GOOGLE_API_KEY")
            cse_id = (google_cse_id or os.getenv("GOOGLE_CSE_ID") or "").strip()
            if google_key and cse_id:
                print(f"[*] Google Custom Search로 site:blog.naver.com/{self.blog_id} 검색 중...")
                google_posts = search_naver_blog_posts(self.blog_id, google_key, cse_id, max_results=100)
                posts.extend(google_posts)

        # 링크 중복 제거
        dedup = {}
        for post in posts:
            link = self._normalize_naver_post_url(post.get("link", ""))
            if not link:
                continue
            post["link"] = link
            dedup[link] = post
        posts = list(dedup.values())

        if follow_internal_links:
            seed_urls = [p.get("link", "") for p in posts if p.get("link")]
            internal_posts = self.crawl_internal_links(
                seed_urls=seed_urls,
                max_pages=internal_max_pages,
                max_depth=internal_max_depth,
                respect_robots=respect_robots,
            )
            for post in internal_posts:
                link = self._normalize_naver_post_url(post.get("link", ""))
                if not link:
                    continue
                post["link"] = link
                dedup[link] = post
            posts = list(dedup.values())

        print(f"[+] 총 {len(posts)}개 포스트 크롤링 완료")
        return posts
