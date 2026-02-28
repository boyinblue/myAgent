# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""유튜브 채널 크롤러"""

import feedparser
import requests
import re
from typing import List, Dict, Optional
import time


class YouTubeCrawler:
    """유튜브 채널의 영상을 크롤링합니다."""

    def __init__(self, channel_id: Optional[str] = None, channel_url: Optional[str] = None, request_interval: float = 1.0):
        """
        Args:
            channel_id: 채널 ID (예: UCxxx...) - 이 방식이 가장 안정적
            channel_url: 채널 URL (예: https://www.youtube.com/@saejinpark4614)
                        channel_id가 없으면 이 URL에서 채널 ID를 추출하려 시도
            request_interval: 요청 간격 (초)
        """
        self.channel_id = channel_id
        self.channel_url = channel_url
        self.request_interval = request_interval
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # 채널 URL이 주어졌으면 채널 ID 추출 시도
        if not self.channel_id and self.channel_url:
            self.channel_id = self._extract_channel_id_from_url(channel_url)

    def _extract_channel_id_from_url(self, url: str) -> Optional[str]:
        """
        유튜브 채널 URL에서 채널 ID를 추출합니다.
        
        지원하는 형식:
        - https://www.youtube.com/@username  (핸들)
        - https://www.youtube.com/c/CustomName (커스텀 URL)
        - https://www.youtube.com/channel/UCxxx... (채널 ID)
        """
        # 이미 채널 ID 형식
        if "channel/" in url:
            match = re.search(r"channel/(UC[a-zA-Z0-9_-]{22})", url)
            if match:
                return match.group(1)

        # 핸들 또는 커스텀 URL에서 채널 ID 추출 (페이지 파싱 필요)
        try:
            print(f"[*] 유튜브 채널 URL에서 채널 ID 추출 중: {url}")
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            # HTML에서 채널 ID 찾기
            match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', resp.text)
            if match:
                return match.group(1)

            print(f"[!] HTML에서 채널 ID를 찾을 수 없습니다.")
        except Exception as e:
            print(f"[!] 채널 ID 추출 실패: {e}")

        return None

    def fetch_rss(self) -> Optional[feedparser.FeedParserDict]:
        """유튜브 채널의 RSS 피드를 가져옵니다."""
        if not self.channel_id:
            print("[ERROR] 채널 ID가 설정되지 않았습니다.")
            return None

        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={self.channel_id}"
        try:
            print(f"[*] 유튜브 RSS 피드를 가져오는 중... ({rss_url})")
            response = requests.get(rss_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if feed.bozo:
                print(f"[!] RSS 파싱 경고: {feed.bozo_exception}")

            return feed
        except Exception as e:
            print(f"[ERROR] 유튜브 RSS 가져오기 실패: {e}")
            return None

    def parse_feed_entries(self, feed: feedparser.FeedParserDict, max_videos: int = None) -> List[Dict]:
        """RSS 피드에서 영상 정보를 추출합니다."""
        videos: List[Dict] = []

        if not feed or not feed.entries:
            print("[!] 피드에 항목이 없습니다.")
            return videos

        entries = feed.entries[:max_videos] if max_videos else feed.entries

        for entry in entries:
            # 유튜브 RSS의 항목 분석
            video_url = entry.get("link", "")
            video_id = None
            if "v=" in video_url:
                video_id = video_url.split("v=")[-1].split("&")[0]

            video = {
                "title": entry.get("title", "제목 없음"),
                "published": entry.get("published", ""),
                "link": video_url,
                "video_id": video_id,
                "summary": entry.get("summary", ""),
                "author": entry.get("author", ""),
            }
            videos.append(video)
            time.sleep(self.request_interval * 0.1)  # RSS 파싱은 덜 무거움

        return videos

    def crawl(self, max_videos: int = None) -> List[Dict]:
        """
        유튜브 채널을 크롤링합니다.

        Args:
            max_videos: 최대 크롤링 영상 수

        Returns:
            영상 리스트
        """
        print(f"[*] 유튜브 크롤러 시작 (채널 ID: {self.channel_id})")

        if not self.channel_id:
            print("[ERROR] 채널 ID가 없어 크롤링할 수 없습니다.")
            return []

        feed = self.fetch_rss()
        if not feed:
            return []

        videos = self.parse_feed_entries(feed, max_videos)
        print(f"[+] 총 {len(videos)}개 영상 크롤링 완료")
        return videos
