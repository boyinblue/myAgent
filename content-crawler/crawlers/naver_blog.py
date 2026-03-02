# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""네이버 블로그 크롤러

RSS 피드 및 포스트 본문을 크롤링합니다.
"""

import os
import feedparser
import requests
import urllib.request
import json
from typing import Dict, Optional, List
from datetime import datetime
import time
import archive_manager


class NaverBlogCrawler:
    """네이버 블로그 크롤러"""

    def __init__(self, blog_id: str, rss_url: str = None, request_interval: float = 1.0, archive_mgr=None):
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

        print(f"[+] 총 {len(posts)}개 포스트 크롤링 완료")
        return posts
