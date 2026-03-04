# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""아카이브 관리자

마크다운 파일 생성, 디렉토리 구조 관리, index.json 업데이트를 담당합니다.
"""

import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import unquote
import os  # os.path.basename 사용을 위해 os도 확인 필요
import re

class ArchiveManager:
    """콘텐츠 아카이브 관리자"""

    def __init__(self, archive_root: str = "./../archive", db_path: str = './../archive/archive_index.db'):
        """
        Args:
            archive_root: 아카이브 루트 디렉토리
            db_path: 인덱스용 SQLite 데이터베이스 경로
        """
        self.archive_root = archive_root
        os.makedirs(archive_root, exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)

        # 결과를 dict처럼 사용 가능하게 함
        self.conn.row_factory = sqlite3.Row

        self.cur = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        # 중복 방지를 위해 link를 UNIQUE 키로 설정
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS achieves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                url TEXT UNIQUE,                -- 중복 방지 핵심 키

                platform TEXT,                 
                media_name TEXT,
                category TEXT,
                keywords TEXT,
                tags TEXT,                      -- JSON 문자열로 저장
                images TEXT,
                                                                                                    
                gdrive_id TEXT,                 -- 구글 드라이브 파일 고유 ID
                file_path TEXT,                 -- 로컬 저장 경로
                file_hash TEXT,                 -- 로컬 파일 내용의 MD5 (수정 여부 판단용)
                         
                comment TEXT,
                score INTEGER DEFAULT 0,        -- 페이지 점수
                remind_count INTEGER DEFAULT 0, -- 리마인드 발행 횟수

                crawler_version TEXT,
                is_parsed BOOLEAN DEFAULT 0,    -- 파싱 완료 여부
                archived BOOLEAN DEFAULT 0,     -- 최종 보관 완료 여부

                created_at TEXT,                -- ISO8601 형식 저장 권장
                event_dates TEXT,               -- JSON 문자열로 저장
                db_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_sync_at DATETIME           -- 마지막 정합성 체크 시간
            )
        ''')

        # 레코드 수정 시 db_updated_at을 자동으로 갱신하는 트리거 추가
        self.cur.execute('''
            CREATE TRIGGER IF NOT EXISTS update_achieve_timestamp
            AFTER UPDATE ON achieves
            BEGIN
                UPDATE achieves SET db_updated_at = CURRENT_TIMESTAMP WHERE id = old.id;
            END
        ''')
        self.conn.commit()

    def upsert_by_url(self, url: str, title: str = "제목 없음", platform: str = "Unknown"):
        """URL을 기준으로 DB에 데이터를 추가하거나 업데이트합니다."""
        sql = '''
            INSERT INTO achieves (url, title, platform, db_updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,
                platform=excluded.platform,
                db_updated_at=CURRENT_TIMESTAMP
        '''
        try:
            self.cur.execute(sql, (url, title, platform))
            self.conn.commit()
            if self.cur.rowcount > 0:
                print(f"✅ 성공: {url} 데이터가 반영되었습니다.")
        except sqlite3.Error as e:
            print(f"❌ DB 에러: {e}")

    def import_json(self, json_path: str):
        """기존 JSON 파일을 읽어 SQLite DB로 마이그레이션합니다."""
        import json
        
        if not os.path.exists(json_path):
            print(f"❌ 파일을 찾을 수 없습니다: {json_path}")
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            posts = data.get("posts", [])

        print(f"[*] 총 {len(posts)}개의 데이터를 마이그레이션 시작합니다...")
        
        count = 0
        for post in posts:
            # JSON 키와 DB 컬럼 매핑 (필요한 것만 추출)
            url = post.get("url")
            if not url: continue
            
            title = post.get("title", "")
            platform = post.get("platform") or post.get("platform_type", "Unknown")
            media_name = post.get("media_name", "")
            created_at = post.get("created_at", "")
            file_path = post.get("file_path", "")
            
            # DB insert (ON CONFLICT 구문 덕분에 중복 걱정 없습니다)
            sql = '''
                INSERT INTO achieves (url, title, platform, media_name, created_at, file_path)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    platform=excluded.platform,
                    media_name=excluded.media_name,
                    file_path=excluded.file_path
            '''
            self.cur.execute(sql, (url, title, platform, media_name, created_at, file_path))
            count += 1
            
        self.conn.commit()
        print(f"✅ 마이그레이션 완료: {count}개의 레코드가 처리되었습니다.")

    def update_post_metadata(self, post_id, **kwargs):
        """특정 ID의 메타데이터를 직접 수정합니다."""
        if not kwargs:
            return
        
        # 1. 쿼리 생성: "title = ?, platform = ?" 형태
        sets = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [post_id]
        
        # 2. 업데이트 실행 (트리거가 db_updated_at을 자동으로 갱신합니다)
        sql = f"UPDATE achieves SET {sets} WHERE id = ?"
        
        try:
            self.cur.execute(sql, values)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"❌ 업데이트 중 DB 에러 발생 (ID {post_id}): {e}")

    def get_incomplete_posts(self):
        """title, media_name, platform 중 하나라도 누락된 레코드를 찾습니다."""
        sql = '''
            SELECT id, url, title, media_name, platform, file_path, created_at
            FROM achieves 
            WHERE (title IS NULL OR title = '') 
               OR (media_name IS NULL OR media_name = '') 
               OR (platform IS NULL OR platform = '')
        '''

        self.cur.execute(sql)
        return self.cur.fetchall()

    def lint_data(self):
        """누락되거나 부실한 데이터를 리스트업합니다."""
        incomplete = self.get_incomplete_posts()
        if not incomplete:
            print("✨ 모든 데이터가 완벽합니다!")
            return
        
        print(f"🔍 총 {len(incomplete)}개의 부실 데이터 발견:")
        for p in incomplete:
            print(f"  [ID {p['id']}] {p['url']} (누락: {' '.join([k for k,v in dict(p).items() if not v])})")

    def fix_data(self):
        incomplete = self.get_incomplete_posts()
        fixed_count = 0

        # 패턴: 날짜(10자)-플랫폼-미디어명-제목.md
        # 예: 2026-03-02-Tistory-frankler-제목.md
        pattern = re.compile(r'(\d{4}-\d{2}-\d{2})-([^-]+)-([^-]+)-(.*)\.md')

        for p in incomplete:
            if not p['file_path']: continue

            # 1. 파일명만 추출 및 URL 디코딩 (%EC%8B%9C... -> 한글)
            filename = unquote(os.path.basename(p['file_path']))
            match = pattern.search(filename)

            if match:
                c_date, platform, media, title = match.groups()

                updates = {}
                if not p['title'] or p['title'] == 'untitled': 
                    updates['title'] = title.replace('-', ' ') # 하이픈을 공백으로
                if not p['platform']: updates['platform'] = platform
                if not p['media_name']: updates['media_name'] = media
                if not p['created_at']: updates['created_at'] = c_date

                if updates:
                    self.update_post_metadata(p['id'], **updates)
                    fixed_count += 1

        print(f"🛠️ 자동 보정 완료: {fixed_count}개의 레코드를 '지능적'으로 수정했습니다.")

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

    def generate_filename(self, created_year, created_month, created_day, platform_type, media_name, title: str) -> str:
        """
        마크다운 파일명을 생성합니다.

        Args:
            created_date: 작성 날짜 (YYYY-MM-DD 또는 ISO 형식)
            title: 포스트 제목

        Returns:
            파일명 (YYYY-MM-DD-title.md 형식)
        """
        # 날짜 파싱
        date_part = f"{created_year:04d}-{created_month:02d}-{created_day:02d}"

        # 제목 정제 (마크다운 파일명으로 사용 가능하도록)
        title_slug = self._slugify_title(title)

        return f"{date_part}-{platform_type}-{media_name}-{title_slug}.md"

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

    @staticmethod
    def _slugify_created_date(created_date: str):
        """작성 날짜를 [year, month, day] 리스트로 변환합니다."""
        date_obj = None

        if isinstance(created_date, str) and created_date:
            # 1. RFC 2822 (네이버 RSS 등)
            try:
                import email.utils
                date_obj = email.utils.parsedate_to_datetime(created_date)
            except:
                pass

            # 2. ISO 8601 (T 포함) 또는 YYYY-MM-DD
            if not date_obj:
                try:
                    clean_date = created_date.split("T")[0] if "T" in created_date else created_date[:10]
                    date_obj = datetime.strptime(clean_date, "%Y-%m-%d")
                except:
                    pass

        # 3. 파싱 실패 시 현재 시간 (UTC)
        if not date_obj:
            date_obj = datetime.now(timezone.utc)

        return date_obj.year, date_obj.month, date_obj.day

    def create_markdown_file(
        self,
        title: str,
        url: str,
        platform_type: str,
        media_name: str,
        content: str,
        created_at: str,
        event_dates: List[str],
        category: str = "",
        tags: List[str] = None,
        comments: str = "",
        keywords: List[str] = None,
        crawler_version: str = "",
        images: List[Dict] = None,
        raw_html: str = "",
        raw_dir: str = None,
    ) -> str:
        """
        마크다운 파일을 생성하거나 기존 파일을 업데이트합니다.

        Args:
            title: 포스트 제목
            url: 원본 URL
            platform_type: 플랫폼 타입 (예: NaverBlog, Tistory 등)
            content: 포스트 본문
            created_at: 작성 날짜 (YYYY-MM-DDTHH:MM:SS 형식)
            event_dates: 이벤트 날짜 리스트
            category: 카테고리
            tags: 태그 리스트
            comments: 코멘트 또는 내부 노트
            keywords: 추출된 키워드 리스트
            crawler_version: 이 크롤러 버전 (아카이브 업데이트 추적용)

        Returns:
            저장된 파일 경로
        """        # 날짜 파싱 (유효하지 않으면 오늘 날짜 사용)
        year, month, day = self._slugify_created_date(created_at)

        # 디렉토리 경로
        archive_path = self.get_archive_path(year, month)

        # 파일명
        filename = self.generate_filename(year, month, day, platform_type, media_name, title)
        filepath = os.path.join(archive_path, filename)

        # URL
        if url and url.startswith("http://blog.naver.com") and "?" in url:
            url = url.split("?")[0]

        # Frontmatter 생성 / 기존 파일이 있으면 병합
        frontmatter = {
            "title": title,
            "url": url,
            "platform": platform_type,
            "media_name": media_name,
            "created_at": created_at,
            "event_dates": event_dates,
            "category": category,
            "tags": tags or [],
            "comments": comments or "",
            "keywords": keywords or [],
            "crawler_version": crawler_version,
            "images": images or [],
        }

        # 기존 파일이 존재하면 frontmatter 병합 (버전 비교 등)
        if os.path.exists(filepath):
            existing = self._extract_frontmatter(Path(filepath)) or {}
            # 보존할 필드들
            for key in ["tags", "comments", "keywords", "images"]:
                if existing.get(key):
                    # 목록 병합 처리
                    if isinstance(existing[key], list) and isinstance(frontmatter.get(key), list):
                        if key == "images":
                            # 이미지 리스트는 url 기준으로 중복 제거
                            seen = set()
                            combined = []
                            for img in existing[key] + frontmatter.get(key, []):
                                url = img.get("url")
                                if url and url not in seen:
                                    seen.add(url)
                                    combined.append(img)
                            frontmatter[key] = combined
                        else:
                            combined = existing[key] + frontmatter.get(key, [])
                            frontmatter[key] = list(dict.fromkeys(combined))
                    elif isinstance(existing[key], str):
                        frontmatter[key] = frontmatter.get(key) or existing[key]
            # 버전이 바뀌었으면 로그
            if existing.get("crawler_version") and existing.get("crawler_version") != crawler_version:
                print(f"[i] crawler_version 변경: {existing.get('crawler_version')} → {crawler_version} (파일 {filepath})")
            # created_at 유지
            if existing.get("created_at"):
                frontmatter["created_at"] = existing.get("created_at")

        # 마크다운 내용 생성
        markdown_content = self._generate_markdown(frontmatter, content)

        # 파일 저장 (덮어쓰기)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # 원본 HTML 저장
        if raw_dir and raw_html:
            try:
                # raw_dir 아래에 동일한 연/월 구조로 저장
                raw_path = os.path.join(raw_dir, str(year), f"{month:02d}")
                os.makedirs(raw_path, exist_ok=True)
                raw_file = os.path.join(raw_path, filename + ".html")
                with open(raw_file, "w", encoding="utf-8") as rf:
                    rf.write(raw_html)
            except Exception as e:
                print(f"[!] raw_html 저장 실패: {e}")

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
                    # handle dictionary items (e.g. image metadata)
                    if isinstance(item, dict):
                        lines.append(f"  -")
                        for subkey, subval in item.items():
                            lines.append(f"      {subkey}: \"{subval}\"")
                    else:
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
                        post_meta["url"] = post_meta.get("url")
                        if post_meta["url"] and post_meta["url"].startswith("https://blog.naver.com"):
                            # 네이버 블로그 URL에서 쿼리 파라미터 제거
                            post_meta["url"] = post_meta["url"].split("?")[0]
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

    def summarize_with_ollama(self, text: str) -> Optional[str]:
        """Ollama CLI를 이용해 간단히 텍스트를 요약합니다.

        Ollama가 설치되어 있지 않거나 실패하면 None을 반환합니다.
        """
        try:
            import subprocess
            # 최소한 문자열을 전달해 모델을 호출
            proc = subprocess.run(
                ["ollama", "run", "llama2", "--prompt", text],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
            else:
                print(f"[!] Ollama 요약 오류: {proc.stderr}")
        except Exception as e:
            print(f"[!] Ollama 실행 실패: {e}")
        return None

if __name__ == "__main__":
    import argparse

    # 인자 파서 설정
    parser = argparse.ArgumentParser(description="Archive Manager CLI")
    parser.add_argument("--url", type=str, help="추가할 콘텐츠의 URL")
    parser.add_argument("--import_file", help="JSON 파일 마이그레이션 경로 (예: index.json)")
    parser.add_argument("--check", action="store_true", help="누락 데이터 확인")
    parser.add_argument("--fix", action="store_true", help="누락 데이터 수정")

    args = parser.parse_args()

    # 1. 매니저 초기화 (이때 DB 파일과 테이블이 생성됩니다)
    # archive_root와 db_path는 필요에 따라 수정하세요.
    manager = ArchiveManager(archive_root="../archive", db_path="../archive/archive_index.db")

    if args.url:
        print(f"[*] 데이터 추가 시도 중: {args.url}")
        manager.upsert_by_url(args.url, args.title, args.platform)
    elif args.import_file:
        manager.import_json(args.import_file)
    elif args.check:
        manager.lint_data()
    elif args.fix:
        manager.fix_data()
    else:
        # 인자 없이 실행했을 때의 기본 동작 (상태 점검 등)
        print("=== Archive Manager Status ===")
        manager.cur.execute("SELECT COUNT(*) FROM achieves")
        count = manager.cur.fetchone()[0]
        print(f"현재 DB에 저장된 콘텐츠 수: {count}개")
        print("사용법 예시: python archive_manager.py --url '주소' --title '제목'")
    
    print("===================================")