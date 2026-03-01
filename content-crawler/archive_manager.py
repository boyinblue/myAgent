# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""아카이브 관리자

마크다운 파일 생성, 디렉토리 구조 관리, index.json 업데이트를 담당합니다.
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class ArchiveManager:
    """콘텐츠 아카이브 관리자"""

    def __init__(self, archive_root: str = "./archive"):
        """
        Args:
            archive_root: 아카이브 루트 디렉토리
        """
        self.archive_root = archive_root
        os.makedirs(archive_root, exist_ok=True)
        # 캐시된 인덱스
        self._index_data = None

    def load_index(self):
        """index.json 파일을 불러와 캐시하고 반환합니다."""
        index_path = os.path.join(self.archive_root, "index.json")
        if not os.path.exists(index_path):
            return {"posts": []}
        if self._index_data is None:
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    self._index_data = json.load(f)
            except Exception:
                self._index_data = {"posts": []}
        return self._index_data

    def is_archived(self, url: str) -> bool:
        """
        URL이 이미 아카이브되었는지 확인합니다.
        
        Args:
            url: 확인할 URL
            
        Returns:
            True if URL is already archived, False otherwise
        """
        index_data = self.load_index()
        posts = index_data.get("posts", [])
        
        for post in posts:
            if post.get("url") == url or post.get("link") == url:
                return True
        return False

    def get_archive_path(self, year: int, month: int) -> str:
        """아카이브 디렉토리 경로를 반환합니다."""
        path = os.path.join(self.archive_root, f"{year:04d}", f"{month:02d}")
        os.makedirs(path, exist_ok=True)
        return path

    def generate_filename(self, created_date: str, title: str) -> str:
        """
        마크다운 파일명을 생성합니다.

        Args:
            created_date: 작성 날짜 (YYYY-MM-DD 또는 ISO 형식)
            title: 포스트 제목

        Returns:
            파일명 (YYYY-MM-DD-title.md 형식)
        """
        # 날짜 파싱
        if "T" in created_date:
            date_part = created_date.split("T")[0]
        else:
            date_part = created_date

        # 제목 정제 (마크다운 파일명으로 사용 가능하도록)
        title_slug = self._slugify_title(title)

        return f"{date_part}-{title_slug}.md"

    @staticmethod
    def _slugify_title(title: str, max_length: int = 50) -> str:
        """제목을 파일명으로 사용 가능한 형태로 변환합니다."""
        # 특수 문자 제거/변환
        slug = title.strip()
        # 슬래시, 역슬래시 제거
        slug = slug.replace("/", "-").replace("\\", "-")
        # 기타 특수 문자 제거 (마크다운 파일명으로 허용되는 것만)
        slug = "".join(c if c.isalnum() or c in "-_ " else "" for c in slug)
        # 공백을 하이픈으로
        slug = slug.replace(" ", "-")
        # 연속된 하이픈 정리
        while "--" in slug:
            slug = slug.replace("--", "-")
        # 길이 제한
        slug = slug[:max_length].rstrip("-")
        return slug or "untitled"

    def create_markdown_file(
        self,
        title: str,
        url: str,
        content: str,
        created_at: str,
        event_dates: List[str],
        category: str = "",
        tags: List[str] = None,
    ) -> str:
        """
        마크다운 파일을 생성합니다.

        Args:
            title: 포스트 제목
            url: 원본 URL
            content: 포스트 본문
            created_at: 작성 날짜 (YYYY-MM-DDTHH:MM:SS 형식)
            event_dates: 이벤트 날짜 리스트
            category: 카테고리
            tags: 태그 리스트

        Returns:
            저장된 파일 경로
        """
        # 날짜 파싱 (유효하지 않으면 오늘 날짜 사용)
        date_part = None
        if isinstance(created_at, str) and created_at:
            if "T" in created_at:
                date_part = created_at.split("T")[0]
            else:
                date_part = created_at
        if not date_part:
            date_part = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 안전하게 숫자로 변환
        try:
            year, month, day = int(date_part[:4]), int(date_part[5:7]), int(date_part[8:10])
        except Exception:
            # 형식 오류 시 오늘 날짜로 대체
            ymd = datetime.now(timezone.utc).strftime("%Y-%m-%d").split("-")
            year, month, day = int(ymd[0]), int(ymd[1]), int(ymd[2])

        # 디렉토리 경로
        archive_path = self.get_archive_path(year, month)

        # 파일명
        filename = self.generate_filename(created_at, title)
        filepath = os.path.join(archive_path, filename)

        # Frontmatter 생성
        frontmatter = {
            "title": title,
            "url": url,
            "created_at": created_at,
            "event_dates": event_dates,
            "category": category,
            "tags": tags or [],
        }

        # 마크다운 내용 생성
        markdown_content = self._generate_markdown(frontmatter, content)

        # 파일 저장
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        return filepath

    @staticmethod
    def _generate_markdown(frontmatter: Dict, content: str) -> str:
        """YAML Frontmatter + 본문 마크다운을 생성합니다."""
        lines = ["---"]

        # Frontmatter
        for key, value in frontmatter.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - \"{item}\"")
            else:
                lines.append(f"{key}: \"{value}\"")

        lines.append("---")
        lines.append("")
        lines.append(f"# {frontmatter['title']}")
        lines.append("")
        lines.append(content)

        return "\n".join(lines)

    def update_index(self, blog_id: str, platform: str = "naver_blog"):
        """
        아카이브의 모든 마크다운 파일을 검사하여 index.json을 생성/업데이트합니다.

        Args:
            blog_id: 블로그 ID
            platform: 플랫폼명
        """
        posts = []
        post_id = 1

        # 아카이브 디렉토리 순회
        for year_dir in sorted(Path(self.archive_root).glob("*/")): # type: ignore
            if not year_dir.is_dir():
                continue

            for month_dir in sorted(year_dir.glob("*/")):
                if not month_dir.is_dir():
                    continue

                for md_file in sorted(month_dir.glob("*.md")):
                    # 메타데이터 추출
                    post_meta = self._extract_frontmatter(md_file)
                    if post_meta:
                        post_meta["id"] = post_id
                        post_meta["file_path"] = str(md_file.relative_to(self.archive_root))
                        post_meta["archived"] = True
                        post_meta["word_count"] = self._count_words(md_file)

                        posts.append(post_meta)
                        post_id += 1

        # index.json 생성
        index_data = {
            "platform": platform,
            "blog_id": blog_id,
            "total_posts": len(posts),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "posts": posts,
        }

        index_path = os.path.join(self.archive_root, "index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        # 캐시 새로고침
        self._index_data = index_data
        print(f"[+] index.json 생성/업데이트: {index_path} ({len(posts)}개 포스트)")
        return index_path

    @staticmethod
    def _extract_frontmatter(filepath: Path) -> Optional[Dict]:
        """마크다운 파일에서 Frontmatter를 추출합니다."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Frontmatter 추출 (--- 사이)
            if not content.startswith("---"):
                return None

            end_index = content.find("\n---\n", 4)
            if end_index == -1:
                return None

            frontmatter_str = content[4:end_index]

            # YAML 파싱 (간단한 구현)
            meta = {}
            for line in frontmatter_str.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if ": " in line:
                    key, value = line.split(": ", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    meta[key] = value
                elif line.endswith(":"):
                    # 배열 시작
                    key = line[:-1].strip()
                    meta[key] = []

            return meta
        except Exception as e:
            print(f"[!] Frontmatter 추출 실패 ({filepath}): {e}")
            return None

    @staticmethod
    def _count_words(filepath: Path) -> int:
        """마크다운 파일의 단어 수를 계산합니다."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Frontmatter 제거
            if content.startswith("---"):
                end_index = content.find("\n---\n", 4)
                if end_index != -1:
                    content = content[end_index + 5:]

            # 단어 수 계산 (공백 기준)
            words = content.split()
            return len(words)
        except Exception:
            return 0
