# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""아카이브 관리자

마크다운 파일 생성, 디렉토리 구조 관리, index.json 업데이트를 담당합니다.
"""

import os
import sys
import json
import sqlite3
import requests
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlsplit, urlunsplit, parse_qsl
import os  # os.path.basename 사용을 위해 os도 확인 필요
import re

# Windows 콘솔 UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

class ArchiveManager:
    """콘텐츠 아카이브 관리자"""

    def __init__(self, archive_root: str = None, db_path: str = None):
        """
        Args:
            archive_root: 아카이브 루트 디렉토리 (None이면 환경변수 또는 기본값 사용)
            db_path: 인덱스용 SQLite 데이터베이스 경로 (None이면 환경변수 또는 기본값 사용)
        """
        project_root = Path(__file__).resolve().parents[1]

        archive_root_value = archive_root or os.getenv('ARCHIVE_ROOT', 'archive')
        archive_root_path = Path(archive_root_value)
        if not archive_root_path.is_absolute():
            archive_root_path = project_root / archive_root_path
        self.archive_root = str(archive_root_path.resolve())

        db_path_value = db_path or os.getenv('ARCHIVE_DB', os.path.join(self.archive_root, 'archive_index.db'))
        db_path_obj = Path(db_path_value)
        if not db_path_obj.is_absolute():
            db_path_obj = project_root / db_path_obj
        db_path_resolved = str(db_path_obj.resolve())

        os.makedirs(self.archive_root, exist_ok=True)

        self.conn = sqlite3.connect(db_path_resolved, check_same_thread=False)

        # 결과를 dict처럼 사용 가능하게 함
        self.conn.row_factory = sqlite3.Row

        self.cur = self.conn.cursor()
        self._image_url_health_cache: Dict[str, bool] = {}
        self._create_table()
        self._create_local_images_table()

    def _create_table(self):
        # 중복 방지를 위해 link를 UNIQUE 키로 설정
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS posts (
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
                published_date TEXT,            -- 원본 발행일
                db_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_sync_at DATETIME           -- 마지막 정합성 체크 시간
            )
        ''')

        # 레코드 수정 시 db_updated_at을 자동으로 갱신하는 트리거 추가
        self.cur.execute('''
            CREATE TRIGGER IF NOT EXISTS update_post_timestamp
            AFTER UPDATE ON posts
            BEGIN
                UPDATE posts SET db_updated_at = CURRENT_TIMESTAMP WHERE id = old.id;
            END
        ''')
        self.conn.commit()

    def _create_local_images_table(self):
        """로컬 이미지 인덱싱용 테이블을 생성합니다."""
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS local_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_uid TEXT UNIQUE,
                file_path TEXT UNIQUE,
                file_name TEXT,
                location TEXT,
                comment TEXT,
                source_root TEXT,
                size_bytes INTEGER,
                modified_at TEXT,
                created_at TEXT,
                db_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 기존 DB 마이그레이션: image_uid 컬럼이 없으면 추가
        cols = self.cur.execute("PRAGMA table_info(local_images)").fetchall()
        col_names = {c[1] for c in cols}
        if 'image_uid' not in col_names:
            self.cur.execute("ALTER TABLE local_images ADD COLUMN image_uid TEXT")

        self.cur.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_local_images_image_uid
            ON local_images(image_uid)
        ''')

        self.cur.execute('''
            CREATE TRIGGER IF NOT EXISTS update_local_images_timestamp
            AFTER UPDATE ON local_images
            BEGIN
                UPDATE local_images SET db_updated_at = CURRENT_TIMESTAMP WHERE id = old.id;
            END
        ''')
        self.conn.commit()

    @staticmethod
    def _is_image_file(path_obj: Path) -> bool:
        return path_obj.suffix.lower() in {
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.svg'
        }

    @staticmethod
    def _build_image_comment(path_obj: Path) -> str:
        # 파일명을 기본 코멘트로 사용 (필요 시 수동 편집 가능)
        return path_obj.stem.replace('_', ' ').replace('-', ' ').strip()

    @staticmethod
    def _compute_image_uid(path_obj: Path) -> str:
        """파일 내용 기반 고유 식별자(SHA256)를 반환합니다."""
        sha = hashlib.sha256()
        with open(path_obj, 'rb') as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()

    def index_local_images(self, roots: List[str]) -> Dict[str, int]:
        """지정한 로컬 루트 디렉토리의 이미지 파일을 DB(local_images)로 인덱싱합니다."""
        inserted = 0
        updated = 0
        skipped = 0
        scanned = 0

        normalized_roots: List[Path] = []
        seen = set()
        for root in roots or []:
            if not root:
                continue
            rp = Path(root).resolve()
            key = str(rp).lower()
            if key in seen:
                continue
            seen.add(key)
            normalized_roots.append(rp)

        for root in normalized_roots:
            if not root.exists() or not root.is_dir():
                print(f"[i] 로컬 이미지 인덱싱 건너뜀(디렉토리 없음): {root}")
                continue

            for path_obj in root.rglob('*'):
                if not path_obj.is_file():
                    continue
                if not self._is_image_file(path_obj):
                    continue

                scanned += 1
                try:
                    stat = path_obj.stat()
                    image_uid = self._compute_image_uid(path_obj)
                    file_path = str(path_obj.resolve())
                    file_name = path_obj.name
                    try:
                        location = str(path_obj.parent.resolve().relative_to(root))
                    except Exception:
                        location = str(path_obj.parent.resolve())

                    comment = self._build_image_comment(path_obj)
                    size_bytes = int(stat.st_size)
                    modified_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
                    created_at = datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat()
                    source_root = str(root)

                    existing = self.cur.execute(
                        "SELECT id FROM local_images WHERE image_uid = ? LIMIT 1",
                        (image_uid,),
                    ).fetchone()

                    if existing is None:
                        existing = self.cur.execute(
                            "SELECT id FROM local_images WHERE file_path = ? LIMIT 1",
                            (file_path,),
                        ).fetchone()

                    if existing:
                        self.cur.execute('''
                            UPDATE local_images
                            SET
                                image_uid = ?,
                                file_name = ?,
                                file_path = ?,
                                location = ?,
                                comment = ?,
                                source_root = ?,
                                size_bytes = ?,
                                modified_at = ?,
                                created_at = ?
                            WHERE id = ?
                        ''', (image_uid, file_name, file_path, location, comment, source_root, size_bytes, modified_at, created_at, existing[0]))
                        updated += 1
                    else:
                        self.cur.execute('''
                            INSERT INTO local_images (
                                image_uid, file_path, file_name, location, comment,
                                source_root, size_bytes, modified_at, created_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (image_uid, file_path, file_name, location, comment, source_root, size_bytes, modified_at, created_at))
                        inserted += 1
                except Exception:
                    skipped += 1

        self.conn.commit()
        return {
            "scanned": scanned,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
        }

    @staticmethod
    def _normalize_url(url: str) -> str:
        """
        URL을 정규화합니다 (중복 체크용).
        
        - m.blog.naver.com → blog.naver.com
        - 쿼리 파라미터 제거 (단, YouTube는 제외)
        - 마지막 슬래시 제거
        
        Args:
            url: 원본 URL
            
        Returns:
            정규화된 URL
        """
        if not url:
            return url

        normalized = str(url).strip()
        if not normalized:
            return normalized

        # 모바일 URL → 데스크톱 URL
        normalized = normalized.replace("://m.blog.naver.com", "://blog.naver.com")

        try:
            parts = urlsplit(normalized)
            scheme = (parts.scheme or "").lower()
            netloc = (parts.netloc or "").lower()
            path = parts.path or ""

            # 기본 포트 제거
            if netloc.endswith(":80") and scheme == "http":
                netloc = netloc[:-3]
            elif netloc.endswith(":443") and scheme == "https":
                netloc = netloc[:-4]

            # path 마지막 슬래시 제거 (루트 제외)
            if path != "/" and path.endswith("/"):
                path = path.rstrip("/")

            query = ""
            is_youtube = ("youtube.com" in netloc) or ("youtu.be" in netloc)
            if is_youtube:
                # YouTube는 v=만 유지
                for key, value in parse_qsl(parts.query, keep_blank_values=False):
                    if key == "v" and value:
                        query = f"v={value}"
                        break

            # fragment 제거
            normalized = urlunsplit((scheme, netloc, path, query, ""))
        except Exception:
            # 파싱 실패 시 보수적으로 기존 규칙 적용
            if "?" in normalized and not ("youtube.com" in normalized or "youtu.be" in normalized):
                normalized = normalized.split("?")[0]
            if normalized.endswith("/"):
                normalized = normalized.rstrip("/")

        return normalized

    def upsert_by_url(self, url: str, title: str = "제목 없음", platform: str = "Unknown"):
        """URL을 기준으로 DB에 데이터를 추가하거나 업데이트합니다."""
        url = self._normalize_url(url)
        sql = '''
            INSERT INTO posts (url, title, platform, db_updated_at)
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
                INSERT INTO posts (url, title, platform, media_name, created_at, file_path)
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

    # URL을 기준으로 title, media_name, platform이 모두 존재하는지 확인하여 아카이브 여부 판단
    def is_archived(self, url: str) -> bool:
        """
        URL이 이미 아카이브되었는지 확인합니다.
        
        Args:
            url: 확인할 URL
            
        Returns:
            True if URL is already archived, False otherwise
        """
        # URL 정규화 (m.blog.naver.com → blog.naver.com, 쿼리 제거)
        url = self._normalize_url(url)
        
        sql = "SELECT title, platform, media_name FROM posts WHERE url = ? LIMIT 1"
        self.cur.execute(sql, (url,))

        # sqlite3 SELECT의 rowcount는 신뢰할 수 없으므로 fetchone()으로 존재 여부 판단
        row = self.cur.fetchone()
        if row is None:
            return False

        record = dict(row)
        if record.get('title') and record.get('platform') and record.get('media_name'):
            return True

        return False

    def should_skip_crawl(self, url: str, crawler_version: str) -> bool:
        """같은 크롤러 버전으로 이미 처리된 URL이면 재크롤링을 건너뜁니다."""
        normalized_url = self._normalize_url(url)
        sql = """
            SELECT title, platform, media_name, crawler_version, images, tags
            FROM posts
            WHERE url = ?
            LIMIT 1
        """

        try:
            self.cur.execute(sql, (normalized_url,))
            row = self.cur.fetchone()
        except sqlite3.Error as e:
            print(f"❌ 크롤링 스킵 여부 조회 에러: {e}")
            return False

        if row is None:
            return False

        record = dict(row)
        is_complete = bool(record.get("title") and record.get("platform") and record.get("media_name"))
        if not is_complete:
            return False

        existing_version = (record.get("crawler_version") or "").strip()
        if not existing_version or existing_version != (crawler_version or "").strip():
            return False

        tags_raw = record.get("tags")
        if tags_raw:
            parsed_tags = []
            try:
                parsed_tags = json.loads(tags_raw) if isinstance(tags_raw, str) else list(tags_raw)
            except Exception:
                parsed_tags = [str(tags_raw)]

            normalized_tags = {str(tag).strip().lower() for tag in parsed_tags if str(tag).strip()}
            if "__private__" in normalized_tags or "private" in normalized_tags:
                return True

        images_raw = record.get("images")
        if not images_raw:
            return False

        try:
            parsed_images = json.loads(images_raw) if isinstance(images_raw, str) else images_raw
        except Exception:
            parsed_images = images_raw

        if isinstance(parsed_images, list):
            for entry in parsed_images:
                if isinstance(entry, dict) and (entry.get("url") or "").strip():
                    return True
                if isinstance(entry, str) and entry.strip():
                    return True
            return False

        return bool(str(parsed_images).strip())

    def needs_rearchive(self, url: str, title: str, platform_type: str, media_name: str, created_at: str) -> bool:
        """기존 레코드의 파일 경로나 날짜가 현재 메타데이터와 다르면 True를 반환합니다."""
        normalized_url = self._normalize_url(url)

        try:
            row = self.cur.execute(
                "SELECT file_path, created_at FROM posts WHERE url = ? LIMIT 1",
                (normalized_url,),
            ).fetchone()
        except sqlite3.Error as e:
            print(f"❌ 재아카이브 필요 여부 조회 에러: {e}")
            return False

        if row is None:
            return False

        existing_created_at = (row["created_at"] or "").strip()
        existing_file_path = (row["file_path"] or "").strip()

        try:
            year, month, day = self._slugify_created_date(created_at)
            expected_dir = self.get_archive_path(year, month)
            expected_name = self.generate_filename(year, month, day, platform_type, media_name, title)
            expected_path = str(Path(expected_dir) / expected_name)
        except Exception:
            return False

        if not existing_file_path:
            return True

        existing_path = str(Path(existing_file_path).resolve()) if existing_file_path else ""
        expected_path = str(Path(expected_path).resolve())

        if existing_path != expected_path:
            return True

        return existing_created_at != (created_at or "").strip()

    def has_representative_image(self, url: str) -> bool:
        """URL 레코드에 유효한 대표 이미지(첫 이미지 URL + 접근 가능)가 있는지 확인합니다."""
        url = self._normalize_url(url)
        sql = "SELECT images FROM posts WHERE url = ? LIMIT 1"
        try:
            self.cur.execute(sql, (url,))
            row = self.cur.fetchone()
            if row is None:
                return False

            images_raw = row[0] if not isinstance(row, sqlite3.Row) else row["images"]
            if not images_raw:
                return False

            # JSON 문자열(list[dict|str])을 우선 파싱
            try:
                parsed = json.loads(images_raw)
            except Exception:
                parsed = None

            first_url = ""
            if isinstance(parsed, list) and parsed:
                for entry in parsed:
                    if isinstance(entry, dict):
                        candidate = (entry.get("url") or "").strip()
                    elif isinstance(entry, str):
                        candidate = entry.strip()
                    else:
                        candidate = ""
                    if candidate:
                        first_url = candidate
                        break

            if not first_url:
                first_url = str(images_raw).strip()
            if not first_url:
                return False

            return self._is_image_url_reachable(first_url)

        except sqlite3.Error as e:
            print(f"❌ 대표 이미지 조회 에러: {e}")
            return False

    def _is_image_url_reachable(self, image_url: str) -> bool:
        """대표 이미지 URL이 실제 접근 가능한지 확인합니다."""
        target = (image_url or "").strip()
        if not target:
            return False

        # data URI / 로컬 경로는 네트워크 검증 없이 존재로 간주
        if target.startswith("data:image/") or target.startswith("/"):
            return True

        if target in self._image_url_health_cache:
            return self._image_url_health_cache[target]

        if not (target.startswith("http://") or target.startswith("https://")):
            self._image_url_health_cache[target] = True
            return True

        try:
            # 우선 HEAD로 빠르게 체크
            resp = requests.head(target, timeout=5, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 405:
                # HEAD 미지원 서버는 GET으로 폴백
                resp = requests.get(target, timeout=8, stream=True, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            ok = 200 <= resp.status_code < 400
            self._image_url_health_cache[target] = ok
            return ok
        except Exception:
            self._image_url_health_cache[target] = False
            return False

    def needs_content_refresh(self, url: str) -> bool:
        """이미 아카이브되어 있으나 대표 이미지가 없는 경우 True를 반환합니다."""
        if not self.is_archived(url):
            return False
        return not self.has_representative_image(url)

    def get_post_id_by_url(self, url: str):
        """URL로 post_id를 찾습니다."""
        # URL 정규화 (m.blog.naver.com → blog.naver.com, 쿼리 제거)
        url = self._normalize_url(url)
        
        sql = "SELECT id FROM posts WHERE url = ? LIMIT 1"
        try:
            self.cur.execute(sql, (url,))
            record = self.cur.fetchone()
            if record:
                return record[0]
        except sqlite3.Error as e:
            print(f"❌ DB 조회 에러: {e}")
        return None

    def update_post_metadata(self, post_id, **kwargs):
        """특정 ID의 메타데이터를 직접 수정합니다."""
        if not kwargs:
            return
        
        # 1. 쿼리 생성: "title = ?, platform = ?" 형태
        sets = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [post_id]
        
        # 2. 업데이트 실행 (트리거가 db_updated_at을 자동으로 갱신합니다)
        sql = f"UPDATE posts SET {sets} WHERE id = ?"
        
        try:
            self.cur.execute(sql, values)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"❌ 업데이트 중 DB 에러 발생 (ID {post_id}): {e}")

    def get_incomplete_posts(self):
        """title, media_name, platform 중 하나라도 누락된 레코드를 찾습니다."""
        sql = '''
            SELECT id, url, title, media_name, platform, file_path, created_at
            FROM posts 
            WHERE (title IS NULL OR title = '') 
               OR (media_name IS NULL OR media_name = '') 
               OR (platform IS NULL OR platform = '')
        '''

        self.cur.execute(sql)
        return self.cur.fetchall()

    def backfill_crawler_versions(self) -> int:
        """기존 마크다운 frontmatter의 crawler_version을 DB로 역채웁니다."""
        rows = self.cur.execute(
            '''
                SELECT id, file_path
                FROM posts
                WHERE crawler_version IS NULL OR crawler_version = ''
            '''
        ).fetchall()

        updated = 0
        for row in rows:
            file_path = row["file_path"]
            if not file_path:
                continue

            path_candidates = [Path(file_path)]
            if not Path(file_path).is_absolute():
                project_root = Path(self.archive_root).parent
                normalized_path = file_path.lstrip("./\\")
                path_candidates.extend([
                    Path(self.archive_root) / file_path,
                    project_root / file_path,
                    project_root / normalized_path,
                ])

            path_obj = next((candidate for candidate in path_candidates if candidate.exists()), None)
            if path_obj is None:
                continue

            frontmatter = self._extract_frontmatter(path_obj) or {}
            crawler_version = (frontmatter.get("crawler_version") or "").strip()
            if not crawler_version:
                continue

            self.cur.execute(
                "UPDATE posts SET crawler_version = ? WHERE id = ?",
                (crawler_version, row["id"]),
            )
            updated += 1

        if updated:
            self.conn.commit()

        return updated

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

    def cleanup_duplicate_url_files(self) -> Dict[str, Any]:
        """같은 URL을 가진 중복 md 파일을 정리하고 리포트를 남깁니다."""
        archive_root_path = Path(self.archive_root).resolve()
        project_root = archive_root_path.parent
        report_path = project_root / "temp" / "duplicate_url_cleanup_report.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        url_to_paths: Dict[str, List[Path]] = {}
        file_meta: Dict[Path, Dict[str, Any]] = {}

        for md_file in sorted(archive_root_path.rglob("*.md")):
            frontmatter = self._extract_frontmatter(md_file) or {}
            raw_url = (frontmatter.get("url") or "").strip()
            if not raw_url:
                continue

            normalized_url = self._normalize_url(raw_url)
            file_meta[md_file] = frontmatter
            url_to_paths.setdefault(normalized_url, []).append(md_file)

        duplicate_groups = {url: paths for url, paths in url_to_paths.items() if len(paths) > 1}

        deleted_files: List[str] = []
        updated_db_paths = 0
        group_lines: List[str] = []

        for normalized_url, paths in sorted(duplicate_groups.items(), key=lambda item: item[0]):
            db_row = None
            try:
                db_row = self.cur.execute(
                    "SELECT file_path, created_at FROM posts WHERE url = ? LIMIT 1",
                    (normalized_url,),
                ).fetchone()
            except sqlite3.Error:
                db_row = None

            db_file_path = ""
            if db_row is not None:
                if isinstance(db_row, sqlite3.Row):
                    db_file_path = (db_row["file_path"] or "").strip()
                else:
                    db_file_path = str(db_row[0] or "").strip()

            resolved_db_path = ""
            if db_file_path:
                db_path_obj = Path(db_file_path)
                if not db_path_obj.is_absolute():
                    db_path_obj = archive_root_path / db_path_obj
                resolved_db_path = str(db_path_obj.resolve())

            canonical_path: Optional[Path] = None
            if resolved_db_path:
                for path in paths:
                    if str(path.resolve()) == resolved_db_path:
                        canonical_path = path
                        break

            if canonical_path is None:
                def _score(path: Path) -> tuple:
                    meta = file_meta.get(path, {})
                    created_at = (meta.get("created_at") or "").strip()
                    title = (meta.get("title") or "").strip()
                    has_created = 1 if created_at else 0
                    has_title = 1 if title else 0
                    return (has_created, has_title, -len(path.name), str(path))

                canonical_path = sorted(paths, key=_score, reverse=True)[0]

            if db_row is not None:
                canonical_created_at = (file_meta.get(canonical_path, {}).get("created_at") or "").strip()
                try:
                    self.cur.execute(
                        "UPDATE posts SET file_path = ?, created_at = COALESCE(NULLIF(created_at, ''), ?) WHERE url = ?",
                        (str(canonical_path.resolve()), canonical_created_at, normalized_url),
                    )
                    updated_db_paths += 1
                except sqlite3.Error:
                    pass

            removed_paths: List[str] = []
            for path in paths:
                if path == canonical_path:
                    continue
                try:
                    path.unlink()
                    removed_paths.append(str(path.resolve()))
                    deleted_files.append(str(path.resolve()))
                except Exception as delete_error:
                    removed_paths.append(f"DELETE_FAILED:{path.resolve()}:{delete_error}")

            group_lines.append(f"URL\t{normalized_url}")
            group_lines.append(f"KEEP\t{canonical_path.resolve()}")
            for removed in removed_paths:
                group_lines.append(f"DELETE\t{removed}")
            group_lines.append("")

        if duplicate_groups:
            self.conn.commit()

        # 2단계: URL 매칭에서 누락된 -dupN.md 파일 패턴 기반 정리
        import re as _re
        dup_pattern = _re.compile(r'^(.+)-dup\d+\.md$')
        for md_file in sorted(archive_root_path.rglob("*.md")):
            m = dup_pattern.match(md_file.name)
            if not m:
                continue
            canonical_name = m.group(1) + ".md"
            canonical_path = md_file.parent / canonical_name
            if canonical_path.exists():
                try:
                    md_file.unlink()
                    deleted_files.append(str(md_file.resolve()))
                    group_lines.append(f"URL\t(pattern-based)")
                    group_lines.append(f"KEEP\t{canonical_path.resolve()}")
                    group_lines.append(f"DELETE\t{md_file.resolve()}")
                    group_lines.append("")
                except Exception as delete_error:
                    group_lines.append(f"DELETE_FAILED\t{md_file.resolve()}:{delete_error}")

        with open(report_path, "w", encoding="utf-8") as report_file:
            report_file.write(f"duplicate_groups\t{len(duplicate_groups)}\n")
            report_file.write(f"deleted_files\t{len(deleted_files)}\n")
            report_file.write(f"updated_db_paths\t{updated_db_paths}\n")
            report_file.write("\n")
            for line in group_lines:
                report_file.write(line + "\n")

        return {
            "duplicate_groups": len(duplicate_groups),
            "deleted_files": len(deleted_files),
            "updated_db_paths": updated_db_paths,
            "report_path": str(report_path),
        }

    def get_duplicate_url_file_metrics(self) -> Dict[str, Any]:
        """현재 archive 내 URL 중복 md 상태를 집계합니다."""
        archive_root_path = Path(self.archive_root).resolve()
        url_counts: Dict[str, int] = {}

        for md_file in archive_root_path.rglob("*.md"):
            frontmatter = self._extract_frontmatter(md_file) or {}
            raw_url = (frontmatter.get("url") or "").strip()
            if not raw_url:
                continue
            normalized_url = self._normalize_url(raw_url)
            url_counts[normalized_url] = url_counts.get(normalized_url, 0) + 1

        duplicate_groups = sum(1 for count in url_counts.values() if count > 1)
        duplicate_files = sum(count - 1 for count in url_counts.values() if count > 1)
        return {
            "tracked_urls": len(url_counts),
            "duplicate_groups": duplicate_groups,
            "duplicate_files": duplicate_files,
        }

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

            # 2-1. 네이버 모바일 본문 날짜 형식 (예: 2024. 9. 25. 10:39)
            if not date_obj:
                normalized = (created_date or "").strip()
                for fmt in ("%Y. %m. %d. %H:%M", "%Y. %m. %d. %H:%M:%S", "%Y. %m. %d."):
                    try:
                        date_obj = datetime.strptime(normalized, fmt)
                        break
                    except:
                        pass

        # 3. 파싱 실패 시 현재 시간 (UTC)
        if not date_obj:
            date_obj = datetime.now(timezone.utc)

        return date_obj.year, date_obj.month, date_obj.day

    @staticmethod
    def _ensure_list(value):
        """입력값을 안전한 리스트로 정규화합니다."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple) or isinstance(value, set):
            return list(value)
        return [value]

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
        """
        # URL 정규화 (m.blog.naver.com → blog.naver.com, 쿼리 제거)
        url = self._normalize_url(url)

        # 동일 URL의 기존 파일 경로를 먼저 조회합니다.
        # 재아카이브 시 경로가 바뀌면 이전 md를 정리하는 데 사용합니다.
        old_file_path = ""
        try:
            existing_row = self.cur.execute(
                "SELECT file_path FROM posts WHERE url = ? LIMIT 1",
                (url,),
            ).fetchone()
            if existing_row is not None:
                if isinstance(existing_row, sqlite3.Row):
                    old_file_path = (existing_row["file_path"] or "").strip()
                else:
                    old_file_path = str(existing_row[0] or "").strip()
        except sqlite3.Error:
            old_file_path = ""

        # 날짜 파싱 (유효하지 않으면 오늘 날짜 사용)
        year, month, day = self._slugify_created_date(created_at)

        # 디렉토리 경로
        archive_path = self.get_archive_path(year, month)

        # 파일명
        filename = self.generate_filename(year, month, day, platform_type, media_name, title)
        filepath = os.path.join(archive_path, filename)

        # Frontmatter 생성 / 기존 파일이 있으면 병합
        safe_event_dates = self._ensure_list(event_dates)
        safe_tags = self._ensure_list(tags)
        safe_keywords = self._ensure_list(keywords)
        safe_images = [img for img in self._ensure_list(images) if img is not None]

        frontmatter = {
            "title": title,
            "url": url,
            "platform": platform_type,
            "media_name": media_name,
            "created_at": created_at,
            "event_dates": safe_event_dates,
            "category": category,
            "tags": safe_tags,
            "comments": comments or "",
            "keywords": safe_keywords,
            "crawler_version": crawler_version,
            "images": safe_images,
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
                                if not isinstance(img, dict):
                                    continue
                                image_url = img.get("url")
                                if image_url and image_url not in seen:
                                    seen.add(image_url)
                                    combined.append(img)
                            frontmatter[key] = combined
                        else:
                            combined = [item for item in (existing[key] + frontmatter.get(key, [])) if item is not None]
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

        # DB에 포스트 저장 (중요!)
        try:
            # images를 JSON 문자열로 변환
            import json
            images_json = json.dumps(safe_images, ensure_ascii=False) if safe_images else ""
            tags_json = json.dumps(safe_tags, ensure_ascii=False) if safe_tags else "[]"
            comment_text = comments or ""
            
            self.cur.execute('''
                INSERT INTO posts (url, title, platform, media_name, created_at, file_path, images, tags, comment, crawler_version, db_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    platform=excluded.platform,
                    media_name=excluded.media_name,
                    created_at=excluded.created_at,
                    file_path=excluded.file_path,
                    images=excluded.images,
                    tags=excluded.tags,
                    comment=excluded.comment,
                    crawler_version=excluded.crawler_version,
                    db_updated_at=CURRENT_TIMESTAMP
            ''', (url, title, platform_type, media_name, created_at, filepath, images_json, tags_json, comment_text, crawler_version))
            self.conn.commit()
            # 저장된 ID 가져오기
            result = self.cur.execute('SELECT id FROM posts WHERE url = ?', (url,)).fetchone()
            if result:
                post_id = result[0]
                print(f"[+] DB 저장 완료: ID={post_id}, URL={url}")

            # 동일 URL의 이전 파일이 다른 경로에 남아 있으면 정리
            try:
                if old_file_path:
                    new_resolved = str(Path(filepath).resolve())
                    old_resolved = str(Path(old_file_path).resolve())
                    archive_root_resolved = str(Path(self.archive_root).resolve())
                    old_in_archive = old_resolved.startswith(archive_root_resolved)
                    if old_in_archive and old_resolved != new_resolved and os.path.exists(old_resolved):
                        os.remove(old_resolved)
                        print(f"[i] 동일 URL 이전 파일 정리: {old_resolved}")
            except Exception as cleanup_error:
                print(f"[!] 이전 파일 정리 실패: {cleanup_error}")
        except sqlite3.Error as e:
            print(f"[!] DB 저장 실패: {e}")

        return filepath

    def upsert_private_post(
        self,
        title: str,
        url: str,
        platform_type: str,
        media_name: str,
        created_at: str = "",
        tags: List[str] = None,
        comments: str = "",
        crawler_version: str = "",
        images: List[Dict] = None,
    ) -> None:
        """비공개 글을 마크다운 없이 DB에만 저장/갱신합니다."""
        normalized_url = self._normalize_url(url)
        safe_tags = self._ensure_list(tags)
        normalized_tags = {str(tag).strip().lower() for tag in safe_tags if str(tag).strip()}
        if "__private__" not in normalized_tags:
            safe_tags.append("__private__")
        if "private" not in normalized_tags:
            safe_tags.append("private")

        safe_images = [img for img in self._ensure_list(images) if img is not None]
        tags_json = json.dumps(safe_tags, ensure_ascii=False)
        images_json = json.dumps(safe_images, ensure_ascii=False) if safe_images else ""

        try:
            self.cur.execute(
                '''
                    INSERT INTO posts (url, title, platform, media_name, created_at, file_path, images, tags, comment, crawler_version, db_updated_at)
                    VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(url) DO UPDATE SET
                        title=excluded.title,
                        platform=excluded.platform,
                        media_name=excluded.media_name,
                        created_at=excluded.created_at,
                        file_path=NULL,
                        images=excluded.images,
                        tags=excluded.tags,
                        comment=excluded.comment,
                        crawler_version=excluded.crawler_version,
                        db_updated_at=CURRENT_TIMESTAMP
                ''',
                (
                    normalized_url,
                    title,
                    platform_type,
                    media_name,
                    created_at or "",
                    images_json,
                    tags_json,
                    comments or "",
                    crawler_version,
                ),
            )
            self.conn.commit()
            print(f"[+] 비공개 글 DB 저장 완료(파일 생성 안 함): {normalized_url}")
        except sqlite3.Error as e:
            print(f"[!] 비공개 글 DB 저장 실패: {e}")

    @staticmethod
    def _generate_markdown(frontmatter: Dict, content: str) -> str:
        """YAML Frontmatter + 본문 마크다운을 생성합니다."""
        lines = ["---"]

        # Frontmatter
        for key, value in frontmatter.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    if item is None:
                        continue
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
        lines.append(content or "")

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
    # archive_root와 db_path는 환경변수에서 가져오거나 None으로 기본값 사용
    manager = ArchiveManager()

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
        manager.cur.execute("SELECT COUNT(*) FROM posts")
        count = manager.cur.fetchone()[0]
        print(f"현재 DB에 저장된 콘텐츠 수: {count}개")
        print("사용법 예시: python archive_manager.py --url '주소' --title '제목'")
    
    print("===================================")