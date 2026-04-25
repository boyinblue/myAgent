#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import argparse
import io
import re
import sqlite3
from urllib.parse import urlparse
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# Windows 콘솔 UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OAUTH_CREDENTIAL_FILE = PROJECT_ROOT / "google_oauth2_credentials.json"
TOKEN_FILE = PROJECT_ROOT / "google_oauth2_token.json"
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.readonly',
]


def _collect_files_in_folder(service, folder_id: str):
    files = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id,name,mimeType,modifiedTime)",
            pageSize=200,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files


def dedupe_files_by_name(service, folder_id: str = "root"):
    """동일 폴더(및 하위 폴더) 내 중복 파일명 정리: 최신 1개 보존, 나머지 삭제"""
    print("\n🧹 중복 파일명 정리 시작...")

    folders_to_visit = [folder_id]
    visited = set()
    scanned_folders = 0
    duplicate_group_total = 0
    deleted_total = 0
    skipped_total = 0

    while folders_to_visit:
        current_folder_id = folders_to_visit.pop(0)
        if current_folder_id in visited:
            continue
        visited.add(current_folder_id)
        scanned_folders += 1

        all_items = _collect_files_in_folder(service, current_folder_id)
        folder_items = [item for item in all_items if item.get("mimeType") == "application/vnd.google-apps.folder"]
        file_items = [item for item in all_items if item.get("mimeType") != "application/vnd.google-apps.folder"]

        for folder in folder_items:
            subfolder_id = folder.get("id")
            if subfolder_id and subfolder_id not in visited:
                folders_to_visit.append(subfolder_id)

        grouped = defaultdict(list)
        for item in file_items:
            grouped[(item.get("name") or "").strip()].append(item)

        duplicate_groups = {name: items for name, items in grouped.items() if name and len(items) > 1}
        if not duplicate_groups:
            continue

        duplicate_group_total += len(duplicate_groups)
        print(f"\n📂 폴더: {current_folder_id} / 중복 그룹 {len(duplicate_groups)}개")

        for name, items in duplicate_groups.items():
            items_sorted = sorted(items, key=lambda x: x.get("modifiedTime") or "", reverse=True)
            keep_item = items_sorted[0]
            print(f"\n📌 파일명: {name}")
            print(f"   유지: {keep_item.get('id')}")

            for item in items_sorted[1:]:
                file_id = item.get("id")
                try:
                    service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
                    deleted_total += 1
                    print(f"   삭제: {file_id}")
                except HttpError as error:
                    skipped_total += 1
                    print(f"   건너뜀(권한/오류): {file_id} -> {error}")

    if duplicate_group_total == 0:
        print("✅ 중복 파일명이 없습니다.")
        return

    print("\n✅ 중복 정리 완료")
    print(f"- 스캔 폴더: {scanned_folders}")
    print(f"- 중복 그룹: {duplicate_group_total}")
    print(f"- 삭제: {deleted_total}")
    print(f"- 건너뜀: {skipped_total}")


def _sanitize_filename_part(text: str) -> str:
    value = (text or "").strip()
    value = re.sub(r'[\\/:*?"<>|]+', '-', value)
    value = re.sub(r'\s+', '-', value)
    value = re.sub(r'-+', '-', value)
    return value.strip('-') or "untitled"


def _extract_date_from_filename(name: str) -> str | None:
    base = os.path.basename(name or "")
    patterns = [
        r"(20\d{2})[-_/](\d{2})[-_/](\d{2})",
        r"(20\d{2})(\d{2})(\d{2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, base)
        if not m:
            continue
        y, mo, d = m.group(1), m.group(2), m.group(3)
        try:
            datetime(int(y), int(mo), int(d))
            return f"{y}-{mo}-{d}"
        except ValueError:
            continue
    return None


def _extract_date_from_html_text(html_text: str) -> tuple[str | None, str]:
    text = html_text or ""

    meta_patterns = [
        (r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']', 'meta:article:published_time'),
        (r'<meta[^>]+name=["\']publish_date["\'][^>]+content=["\']([^"\']+)["\']', 'meta:publish_date'),
        (r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)["\']', 'meta:date'),
        (r'<time[^>]+datetime=["\']([^"\']+)["\']', 'time:datetime'),
    ]
    for pattern, source in meta_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = m.group(1)
        date_match = re.search(r'(20\d{2})[-_/](\d{2})[-_/](\d{2})', candidate)
        if date_match:
            return f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}", source

    body_match = re.search(r'(20\d{2})[-_/](\d{2})[-_/](\d{2})', text)
    if body_match:
        return f"{body_match.group(1)}-{body_match.group(2)}-{body_match.group(3)}", 'body:date-pattern'

    return None, 'none'


def _extract_title_from_html_text(html_text: str) -> str | None:
    text = html_text or ""
    patterns = [
        r'<title[^>]*>(.*?)</title>',
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<h1[^>]*>(.*?)</h1>',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            continue
        candidate = re.sub(r'<[^>]+>', ' ', m.group(1))
        candidate = re.sub(r'\s+', ' ', candidate).strip()
        if candidate:
            return candidate
    return None


def _strip_keep_prefix(stem: str) -> str:
    value = (stem or '').strip()
    value = re.sub(r'^20\d{2}-\d{2}-\d{2}-GoogleKeep-esregnet0409-', '', value, flags=re.IGNORECASE)
    value = re.sub(r'^20\d{2}-\d{2}-\d{2}-googlekeep-esregnet0409-', '', value, flags=re.IGNORECASE)
    return value.strip('- ') or 'untitled'


def _derive_keep_title_part(file_name: str, html_text: str | None = None) -> str:
    title_from_html = _extract_title_from_html_text(html_text or "") if html_text else None
    if title_from_html:
        return _sanitize_filename_part(title_from_html)

    stem = os.path.splitext(os.path.basename(file_name or ''))[0]
    return _sanitize_filename_part(_strip_keep_prefix(stem))


def _derive_display_title(file_name: str, html_text: str | None = None) -> str:
    title_from_html = _extract_title_from_html_text(html_text or "") if html_text else None
    if title_from_html:
        return title_from_html
    stem = _strip_keep_prefix(os.path.splitext(os.path.basename(file_name or ''))[0])
    return stem.replace('-', ' ').strip() or '제목 없음'


def _build_keep_target_stem(date_str: str, title_part: str) -> str:
    return f"{date_str}-GoogleKeep-esregnet0409-{title_part}"


def _archive_pair_key(file_name: str) -> str:
    stem = os.path.splitext(os.path.basename(file_name or ''))[0]
    return _sanitize_filename_part(_strip_keep_prefix(stem)).lower()


def _download_text_preview(service, file_id: str, limit_bytes: int = 1024 * 1024) -> str:
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=256 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
        if buffer.tell() >= limit_bytes:
            break
    data = buffer.getvalue()[:limit_bytes]
    return data.decode('utf-8', errors='replace')


def _find_or_create_child_folder(service, parent_id: str, folder_name: str) -> str:
    safe_name = folder_name.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' "
        f"and name = '{safe_name}' and trashed = false"
    )
    resp = service.files().list(
        q=query,
        fields="files(id,name)",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    items = resp.get('files', [])
    if items:
        return items[0]['id']

    created = service.files().create(
        body={
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id],
        },
        fields='id',
        supportsAllDrives=True,
    ).execute()
    return created['id']


def _find_archive_root_folder_id(service, root_name: str = "[아카이브]") -> str | None:
    safe_name = root_name.replace("'", "\\'")
    query = (
        "mimeType = 'application/vnd.google-apps.folder' "
        f"and name = '{safe_name}' and trashed = false"
    )
    resp = service.files().list(
        q=query,
        fields="files(id,name,parents)",
        pageSize=50,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    items = resp.get('files', [])
    if not items:
        return None
    for item in items:
        parents = item.get('parents') or []
        if 'root' in parents:
            return item['id']
    return items[0]['id']


def _collect_archive_files_recursive(service, folder_id: str) -> list[dict]:
    queue = [folder_id]
    visited = set()
    collected: list[dict] = []

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        page_token = None
        while True:
            resp = service.files().list(
                q=f"'{current}' in parents and trashed = false",
                fields="nextPageToken, files(id,name,mimeType,parents,modifiedTime)",
                pageSize=200,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            items = resp.get('files', [])
            for item in items:
                if item.get('mimeType') == 'application/vnd.google-apps.folder':
                    queue.append(item['id'])
                else:
                    collected.append(item)
            page_token = resp.get('nextPageToken')
            if not page_token:
                break

    return collected


def _extract_html_image_basenames(html_text: str) -> list[str]:
    """HTML에서 상대/절대 img src의 파일명만 추출합니다."""
    text = html_text or ""
    srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', text, flags=re.IGNORECASE)
    names: list[str] = []
    seen = set()
    for src in srcs:
        value = (src or '').strip()
        if not value:
            continue
        if value.startswith('data:'):
            continue
        parsed = urlparse(value)
        path_part = parsed.path or value
        base = os.path.basename(path_part)
        if not base:
            continue
        lower = base.lower()
        if not (lower.endswith('.jpg') or lower.endswith('.jpeg') or lower.endswith('.png') or lower.endswith('.gif') or lower.endswith('.webp')):
            continue
        if lower in seen:
            continue
        seen.add(lower)
        names.append(base)
    return names


def repair_archive_html_images(service, archive_root_name: str = "[아카이브]"):
    """[아카이브] 내 HTML의 이미지 참조를 검사하고, 누락 이미지를 HTML 폴더로 이동합니다."""
    print("\n🩹 [아카이브] HTML 이미지 참조 복구 시작...")
    archive_root_id = _find_archive_root_folder_id(service, root_name=archive_root_name)
    if not archive_root_id:
        print(f"❌ '{archive_root_name}' 폴더를 찾지 못했습니다.")
        return

    targets = _collect_archive_files_recursive(service, archive_root_id)
    if not targets:
        print("✅ 처리할 파일이 없습니다.")
        return

    html_items = [item for item in targets if (item.get('name') or '').lower().endswith('.html')]
    image_items = [
        item for item in targets
        if (item.get('name') or '').lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
    ]

    images_by_name: dict[str, list[dict]] = defaultdict(list)
    for image in image_items:
        images_by_name[(image.get('name') or '').lower()].append(image)

    checked_html = 0
    moved_images = 0
    unresolved_refs = 0
    ambiguous_refs = 0

    for html_item in html_items:
        checked_html += 1
        html_name = html_item.get('name', '')
        html_parent = (html_item.get('parents') or [None])[0]
        if not html_parent:
            continue

        try:
            html_text = _download_text_preview(service, html_item['id'])
        except Exception:
            continue

        referenced = _extract_html_image_basenames(html_text)
        if not referenced:
            continue

        for image_name in referenced:
            key = image_name.lower()
            candidates = images_by_name.get(key, [])
            if not candidates:
                unresolved_refs += 1
                print(f"⚠️ 이미지 파일 없음: {html_name} -> {image_name}")
                continue

            in_same_parent = [c for c in candidates if (c.get('parents') or [None])[0] == html_parent]
            if in_same_parent:
                continue

            if len(candidates) > 1:
                ambiguous_refs += 1
                print(f"⚠️ 후보 다수(건너뜀): {html_name} -> {image_name} ({len(candidates)}개)")
                continue

            image_item = candidates[0]
            current_parent = (image_item.get('parents') or [None])[0]
            if not current_parent:
                unresolved_refs += 1
                continue

            # 동일 이름 파일이 이미 HTML 폴더에 있는지 확인
            safe_name = image_name.replace("'", "\\'")
            dup_q = (
                f"'{html_parent}' in parents and name = '{safe_name}' and trashed = false"
            )
            dup_resp = service.files().list(
                q=dup_q,
                fields='files(id,name)',
                pageSize=2,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            if dup_resp.get('files'):
                continue

            try:
                service.files().update(
                    fileId=image_item['id'],
                    addParents=html_parent,
                    removeParents=current_parent,
                    supportsAllDrives=True,
                    fields='id,name,parents',
                ).execute()
                moved_images += 1
                image_item['parents'] = [html_parent]
                print(f"✅ 이미지 이동: {image_name} -> HTML 폴더 ({html_name})")
            except HttpError as error:
                unresolved_refs += 1
                print(f"⚠️ 이미지 이동 실패: {image_name} -> {error}")

    print("\n✅ HTML 이미지 복구 완료")
    print(f"- 점검 HTML: {checked_html}")
    print(f"- 이동 이미지: {moved_images}")
    print(f"- 미해결 참조: {unresolved_refs}")
    print(f"- 후보 다수(수동 확인): {ambiguous_refs}")


def _dedupe_archive_md_by_name(service, archive_root_id: str) -> tuple[int, int]:
    """[아카이브] 전체에서 동일한 md 파일명 중 최신 1개만 남기고 삭제합니다."""
    targets = _collect_archive_files_recursive(service, archive_root_id)
    md_files = [item for item in targets if (item.get('name') or '').lower().endswith('.md')]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in md_files:
        grouped[(item.get('name') or '').strip().lower()].append(item)

    duplicate_groups = 0
    deleted = 0
    for name, items in grouped.items():
        if not name or len(items) <= 1:
            continue
        duplicate_groups += 1
        items_sorted = sorted(
            items,
            key=lambda x: ((x.get('modifiedTime') or ''), (x.get('id') or '')),
            reverse=True,
        )
        keep_item = items_sorted[0]
        print(f"🧹 중복 md 정리: {name} (유지: {keep_item.get('id')})")
        for item in items_sorted[1:]:
            file_id = item.get('id')
            try:
                service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
                deleted += 1
                print(f"   삭제: {file_id}")
            except HttpError as error:
                print(f"   건너뜀(삭제 실패): {file_id} -> {error}")

    return duplicate_groups, deleted


def _build_target_name(file_name: str, date_str: str, title_part: str) -> str:
    lower_name = (file_name or '').lower()
    if lower_name.endswith('.md'):
        parts = (os.path.splitext(file_name)[0] or '').split('-')
        platform = _sanitize_filename_part(parts[3] if len(parts) >= 4 else 'unknown')
        media_id = _sanitize_filename_part(parts[4] if len(parts) >= 5 else 'unknown')
        return f"{date_str}-{platform}-{media_id}-{title_part}.md"
    keep_stem = _build_keep_target_stem(date_str, title_part)
    if lower_name.endswith('.json'):
        return f"{keep_stem}.json"
    return f"{keep_stem}.html"


def _move_and_rename_item(service, item: dict, target_name: str, target_parent_id: str) -> tuple[dict, bool, bool]:
    current_parent = (item.get('parents') or [None])[0]
    should_move = current_parent != target_parent_id
    should_rename = item.get('name') != target_name

    updated = dict(item)
    if not should_move and not should_rename:
        return updated, False, False

    kwargs = {
        'fileId': item['id'],
        'supportsAllDrives': True,
        'fields': 'id,name,parents,webViewLink',
    }
    if should_rename:
        kwargs['body'] = {'name': target_name}
    if should_move:
        kwargs['addParents'] = target_parent_id
        if current_parent:
            kwargs['removeParents'] = current_parent

    result = service.files().update(**kwargs).execute()
    updated.update(result)
    return updated, should_rename, should_move


def _open_archive_db() -> sqlite3.Connection:
    archive_root = PROJECT_ROOT / 'archive'
    archive_root.mkdir(parents=True, exist_ok=True)
    db_path = archive_root / 'archive_index.db'

    conn = sqlite3.connect(str(db_path), timeout=30)
    cur = conn.cursor()
    try:
        cur.execute('PRAGMA journal_mode=WAL')
    except sqlite3.OperationalError:
        pass
    cur.execute('PRAGMA busy_timeout = 30000')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE,
            platform TEXT,
            media_name TEXT,
            category TEXT,
            keywords TEXT,
            tags TEXT,
            images TEXT,
            gdrive_id TEXT,
            file_path TEXT,
            file_hash TEXT,
            comment TEXT,
            score INTEGER DEFAULT 0,
            remind_count INTEGER DEFAULT 0,
            crawler_version TEXT,
            is_parsed BOOLEAN DEFAULT 0,
            archived BOOLEAN DEFAULT 0,
            created_at TEXT,
            event_dates TEXT,
            published_date TEXT,
            db_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_sync_at DATETIME
        )
    ''')
    cur.execute('''
        CREATE TRIGGER IF NOT EXISTS update_post_timestamp
        AFTER UPDATE ON posts
        BEGIN
            UPDATE posts SET db_updated_at = CURRENT_TIMESTAMP WHERE id = old.id;
        END
    ''')
    conn.commit()
    return conn


def sync_archive_keep_to_db(service, archive_root_name: str = "[아카이브]"):
    print("\n🗂️ [아카이브] Google Keep HTML/JSON 정리 및 DB 동기화 시작...")
    archive_root_id = _find_archive_root_folder_id(service, root_name=archive_root_name)
    if not archive_root_id:
        print(f"❌ '{archive_root_name}' 폴더를 찾지 못했습니다.")
        return

    targets = _collect_archive_files_recursive(service, archive_root_id)
    if not targets:
        print("✅ 처리할 파일이 없습니다.")
        return

    html_items = [item for item in targets if (item.get('name') or '').lower().endswith('.html')]
    json_items = [item for item in targets if (item.get('name') or '').lower().endswith('.json')]

    json_map: dict[tuple[str | None, str], list[dict]] = defaultdict(list)
    for json_item in json_items:
        parent_id = (json_item.get('parents') or [None])[0]
        json_map[(parent_id, _archive_pair_key(json_item.get('name', '')))].append(json_item)

    conn = _open_archive_db()
    cur = conn.cursor()
    synced = 0
    renamed = 0
    moved = 0
    json_renamed = 0
    json_moved = 0
    skipped = 0

    try:
        for item in html_items:
            original_name = item.get('name', '')
            original_parent = (item.get('parents') or [None])[0]

            date_str = None
            date_source = 'unknown'
            html_text = ''
            try:
                html_text = _download_text_preview(service, item['id'])
                extracted, source = _extract_date_from_html_text(html_text)
                if extracted:
                    date_str = extracted
                    date_source = source
            except Exception:
                html_text = ''

            if not date_str:
                date_from_name = _extract_date_from_filename(original_name)
                if date_from_name:
                    date_str = date_from_name
                    date_source = 'filename'

            if not date_str:
                modified = item.get('modifiedTime', '')
                dt_match = re.match(r'(20\d{2})-(\d{2})-(\d{2})', modified)
                if dt_match:
                    date_str = f"{dt_match.group(1)}-{dt_match.group(2)}-{dt_match.group(3)}"
                    date_source = 'modifiedTime'

            if not date_str:
                skipped += 1
                print(f"⚠️ 날짜 추출 실패, 건너뜀: {original_name}")
                continue

            title_part = _derive_keep_title_part(original_name, html_text)
            display_title = _derive_display_title(original_name, html_text)
            target_stem = _build_keep_target_stem(date_str, title_part)
            target_html_name = f"{target_stem}.html"

            year, month, _ = date_str.split('-')
            year_folder_id = _find_or_create_child_folder(service, archive_root_id, year)
            month_folder_id = _find_or_create_child_folder(service, year_folder_id, month)

            updated_html, did_rename, did_move = _move_and_rename_item(
                service,
                item,
                target_html_name,
                month_folder_id,
            )
            renamed += int(did_rename)
            moved += int(did_move)

            pair_key = _archive_pair_key(original_name)
            candidate_lists = [
                json_map.get((original_parent, pair_key), []),
                json_map.get((original_parent, _archive_pair_key(target_html_name)), []),
            ]
            json_item = None
            for candidates in candidate_lists:
                if candidates:
                    json_item = candidates.pop(0)
                    break

            if json_item:
                target_json_name = f"{target_stem}.json"
                _, did_json_rename, did_json_move = _move_and_rename_item(
                    service,
                    json_item,
                    target_json_name,
                    month_folder_id,
                )
                json_renamed += int(did_json_rename)
                json_moved += int(did_json_move)

            html_meta = service.files().get(
                fileId=updated_html['id'],
                fields='id,name,webViewLink,parents',
                supportsAllDrives=True,
            ).execute()
            drive_url = html_meta.get('webViewLink') or f"https://drive.google.com/file/d/{updated_html['id']}/view"
            relative_path = f"{archive_root_name}/{year}/{month}/{html_meta.get('name', target_html_name)}"

            cur.execute(
                '''
                INSERT INTO posts (
                    url, title, platform, media_name, created_at, published_date,
                    file_path, gdrive_id, db_updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    platform=excluded.platform,
                    media_name=excluded.media_name,
                    created_at=excluded.created_at,
                    published_date=excluded.published_date,
                    file_path=excluded.file_path,
                    gdrive_id=excluded.gdrive_id,
                    db_updated_at=CURRENT_TIMESTAMP
                ''',
                (
                    drive_url,
                    display_title,
                    'GoogleKeep',
                    'esregnet0409',
                    date_str,
                    date_str,
                    relative_path,
                    updated_html['id'],
                ),
            )
            synced += 1
            print(
                f"✅ DB 동기화: {html_meta.get('name', target_html_name)} "
                f"(date_source={date_source}, url={drive_url})"
            )

        conn.commit()
    except sqlite3.Error as error:
        conn.rollback()
        print(f"❌ 아카이브 DB 동기화 실패: {error}")
        return
    finally:
        conn.close()

    print("\n✅ [아카이브] DB 동기화 완료")
    print(f"- HTML DB 반영: {synced}")
    print(f"- HTML 이름 변경: {renamed}")
    print(f"- HTML 폴더 이동: {moved}")
    print(f"- JSON 이름 변경: {json_renamed}")
    print(f"- JSON 폴더 이동: {json_moved}")
    print(f"- 건너뜀: {skipped}")


def enforce_archive_naming(service, archive_root_name: str = "[아카이브]"):
    print("\n🗂️ 아카이브 파일명/경로 규칙 강제 시작...")
    archive_root_id = _find_archive_root_folder_id(service, root_name=archive_root_name)
    if not archive_root_id:
        print(f"❌ '{archive_root_name}' 폴더를 찾지 못했습니다.")
        return

    targets = _collect_archive_files_recursive(service, archive_root_id)
    if not targets:
        print("✅ 처리할 파일이 없습니다.")
        return

    renamed = 0
    moved = 0
    skipped = 0

    for item in targets:
        original_name = item.get('name', '')
        lower_name = original_name.lower()
        if not (lower_name.endswith('.md') or lower_name.endswith('.html')):
            skipped += 1
            continue

        date_str = None
        date_source = 'unknown'

        if lower_name.endswith('.html'):
            try:
                html_text = _download_text_preview(service, item['id'])
                extracted, source = _extract_date_from_html_text(html_text)
                if extracted:
                    date_str = extracted
                    date_source = source
            except Exception:
                pass

        if not date_str:
            date_from_name = _extract_date_from_filename(original_name)
            if date_from_name:
                date_str = date_from_name
                date_source = 'filename'

        if not date_str:
            modified = item.get('modifiedTime', '')
            dt_match = re.match(r'(20\d{2})-(\d{2})-(\d{2})', modified)
            if dt_match:
                date_str = f"{dt_match.group(1)}-{dt_match.group(2)}-{dt_match.group(3)}"
                date_source = 'modifiedTime'

        if not date_str:
            skipped += 1
            print(f"⚠️ 날짜 추출 실패, 건너뜀: {original_name}")
            continue

        title_source = os.path.splitext(original_name)[0]
        if re.match(r'^20\d{2}-\d{2}-\d{2}-', title_source):
            parts = title_source.split('-')
            if lower_name.endswith('.md') and len(parts) >= 6:
                # YYYY-MM-DD-platform-media-title.md
                title_source = '-'.join(parts[5:]) or title_source
            elif lower_name.endswith('.html') and len(parts) >= 6 and parts[3].lower() == 'googlekeep':
                # YYYY-MM-DD-GoogleKeep-esregnet0409-title.html
                title_source = '-'.join(parts[5:]) or title_source
            else:
                title_source = '-'.join(parts[3:]) or title_source
        title_part = _sanitize_filename_part(title_source)
        target_name = _build_target_name(original_name, date_str, title_part)

        year, month, _ = date_str.split('-')
        year_folder_id = _find_or_create_child_folder(service, archive_root_id, year)
        month_folder_id = _find_or_create_child_folder(service, year_folder_id, month)

        current_parent = (item.get('parents') or [None])[0]
        should_move = current_parent != month_folder_id
        should_rename = original_name != target_name

        if not should_move and not should_rename:
            continue

        update_body = {'name': target_name} if should_rename else None
        kwargs = {
            'fileId': item['id'],
            'supportsAllDrives': True,
            'fields': 'id,name,parents',
        }
        if update_body:
            kwargs['body'] = update_body
        if should_move:
            kwargs['addParents'] = month_folder_id
            if current_parent:
                kwargs['removeParents'] = current_parent

        try:
            service.files().update(**kwargs).execute()
            if should_rename:
                renamed += 1
            if should_move:
                moved += 1
            print(f"✅ {original_name} -> {target_name} (date_source={date_source}, path={year}/{month})")
        except HttpError as error:
            skipped += 1
            print(f"⚠️ 업데이트 실패: {original_name} -> {error}")

    print("\n✅ 아카이브 규칙 적용 완료")
    print(f"- 이름 변경: {renamed}")
    print(f"- 폴더 이동: {moved}")
    print(f"- 건너뜀/실패: {skipped}")

    duplicate_groups, deleted = _dedupe_archive_md_by_name(service, archive_root_id)
    print(f"- 중복 md 그룹: {duplicate_groups}")
    print(f"- 중복 md 삭제: {deleted}")


def get_gdrive_service(non_interactive: bool = False):
    """
    OAuth2 Desktop Credentials로 구글 드라이브 API 서비스 객체를 초기화합니다.
    """
    if not OAUTH_CREDENTIAL_FILE.exists():
        print("❌ 구글 드라이브 API 설정이 필요합니다.\n")
        print("google_oauth2_credentials.json 파일을 생성하려면:")
        print("  1. Google Cloud Console > API 및 서비스 > 사용자 인증정보")
        print("  2. 'OAuth 클라이언트 ID(데스크톱 앱)' 생성")
        print("  3. JSON을 프로젝트 루트에 google_oauth2_credentials.json 으로 저장")
        return None

    try:
        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as refresh_error:
                    error_text = str(refresh_error).lower()
                    if "invalid_scope" in error_text:
                        try:
                            TOKEN_FILE.unlink(missing_ok=True)
                        except Exception:
                            pass

                        if non_interactive:
                            print("❌ 구글 드라이브 인증 실패: invalid_scope")
                            print("기존 토큰 스코프와 현재 스코프가 달라 재인증이 필요합니다.")
                            print("다음 순서로 진행하세요:")
                            print("  1) 기존 토큰 삭제: google_oauth2_token.json")
                            print("  2) 재인증 실행: python tools/gdrive.py --init-auth")
                            print("  3) 이후 /gdrive 재실행")
                            return None

                        creds = None
                    else:
                        raise
            else:
                if non_interactive:
                    print("⏳ OAuth 인증 토큰이 없습니다.")
                    print("터미널에서 1회 인증을 완료해주세요:")
                    print("  python tools/gdrive.py --init-auth")
                    print("인증 완료 후 Telegram에서 /gdrive를 다시 실행하세요.")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CREDENTIAL_FILE), SCOPES)
                creds = flow.run_local_server(
                    port=0,
                    access_type='offline',
                    prompt='consent',
                )

            if not creds or not creds.valid:
                if non_interactive:
                    print("⏳ OAuth 인증 토큰이 유효하지 않습니다.")
                    print("터미널에서 재인증을 완료해주세요:")
                    print("  python tools/gdrive.py --init-auth")
                    print("인증 완료 후 Telegram에서 /gdrive를 다시 실행하세요.")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CREDENTIAL_FILE), SCOPES)
                creds = flow.run_local_server(
                    port=0,
                    access_type='offline',
                    prompt='consent',
                )

            with open(TOKEN_FILE, 'w', encoding='utf-8') as token:
                token.write(creds.to_json())

        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ 구글 드라이브 인증 실패: {e}")
        return None


def list_shared_files(service, max_depth=2, max_items=120):
    """
    OAuth 계정의 '공유 문서함' 파일/폴더를 검색합니다.
    """
    try:
        # 'Shared with me' 검색
        query = "sharedWithMe = true and trashed = false"
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, owners)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        items = results.get('files', [])
        
        if not items:
            return []
        
        print("\n📂 공유된 파일/폴더:")
        for idx, item in enumerate(items):
            if idx >= max_items:
                print(f"... (공유 항목 {max_items}개만 표시)")
                break
            owner = item.get('owners', [{}])[0].get('displayName', 'Unknown')
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                print(f"📁 {item['name']} (소유자: {owner})")
                print(f"   └─ ID: {item['id']}")
                # 공유 폴더 내부 탐색
                list_files(service, item['id'], indent=1, max_depth=max_depth, max_items=max_items)
            else:
                print(f"📄 {item['name']} (소유자: {owner})")
                print(f"   └─ ID: {item['id']}")
        
        return items

    except HttpError as error:
        print(f"❌ 공유 파일 검색 오류: {error}")
        return []


def list_files(service, folder_id='root', indent=0, is_root_call=False, max_depth=2, max_items=120):
    """
    지정한 폴더 내의 파일과 디렉토리를 재귀적으로 탐색합니다.
    """
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        items = results.get('files', [])

        if not items and indent == 0 and is_root_call:
            return False  # root가 비어있음을 알림

        if indent >= max_depth:
            if items:
                prefix = "  " * indent
                print(f"{prefix}... (하위 탐색 생략: depth 제한 {max_depth})")
            return len(items) > 0

        for idx, item in enumerate(items):
            if idx >= max_items:
                prefix = "  " * indent
                print(f"{prefix}... (항목 {max_items}개만 표시)")
                break
            prefix = "  " * indent
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                print(f"{prefix}📁 {item['name']} (ID: {item['id']})")
                list_files(service, item['id'], indent + 1, max_depth=max_depth, max_items=max_items)
            else:
                print(f"{prefix}📄 {item['name']} (ID: {item['id']})")
        
        return len(items) > 0

    except HttpError as error:
        if '403' in str(error):
            print(f'\n❌ 권한 오류: {error}')
            print('\n📋 해결 방법:')
            print('  1. Google Drive에서 공유 폴더 생성')
            print('  2. 폴더를 서비스 계정 이메일과 공유')
            print('  3. 이메일 주소가 위에 표시됩니다.')
        else:
            print(f"❌ API 에러 발생: {error}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Drive 탐색 도구")
    parser.add_argument("--init-auth", action="store_true", help="OAuth 브라우저 인증 1회 수행")
    parser.add_argument("--folder-id", default="root", help="탐색 시작 폴더 ID")
    parser.add_argument("--max-depth", type=int, default=2, help="폴더 재귀 탐색 최대 깊이")
    parser.add_argument("--max-items", type=int, default=120, help="레벨당 최대 표시 항목 수")
    parser.add_argument("--dedupe", action="store_true", help="지정 폴더 내 중복 파일명 정리(최신 1개 유지)")
    parser.add_argument("--enforce-archive-naming", action="store_true", help="[아카이브]/YYYY/MM 경로와 MD/HTML 파일명 규칙 강제 적용")
    parser.add_argument("--dedupe-archive-md", action="store_true", help="[아카이브] 전체에서 동일 md 파일명 중 최신 1개만 유지")
    parser.add_argument("--repair-archive-html-images", action="store_true", help="[아카이브] HTML이 참조하는 이미지(jpg/png 등)를 HTML 폴더로 이동 복구")
    parser.add_argument("--sync-archive-db", action="store_true", help="[아카이브] Google Keep HTML/JSON 이름 정리 후 Drive 링크로 archive DB 동기화")
    args = parser.parse_args()

    print("📡 구글 드라이브 연결 시도 중...")
    service = get_gdrive_service(non_interactive=not args.init_auth)

    if service:
        # 인증 계정 표시
        try:
            profile = service.about().get(fields="user(emailAddress,displayName)").execute()
            user_info = profile.get("user", {})
            email = user_info.get("emailAddress", "unknown")
            name = user_info.get("displayName", "")
            display = f"{name} <{email}>" if name else email
            print(f"✅ 인증 완료 (계정: {display})")
        except Exception:
            print("✅ 인증 완료")
        
        if args.dedupe:
            dedupe_files_by_name(service, folder_id=args.folder_id or 'root')

        if args.enforce_archive_naming:
            enforce_archive_naming(service, archive_root_name="[아카이브]")

        if args.dedupe_archive_md:
            archive_root_id = _find_archive_root_folder_id(service, root_name="[아카이브]")
            if not archive_root_id:
                print("❌ '[아카이브]' 폴더를 찾지 못했습니다.")
            else:
                groups, deleted = _dedupe_archive_md_by_name(service, archive_root_id)
                print(f"✅ 중복 md 정리 완료: 그룹 {groups}, 삭제 {deleted}")

        if args.repair_archive_html_images:
            repair_archive_html_images(service, archive_root_name="[아카이브]")

        if args.sync_archive_db:
            sync_archive_keep_to_db(service, archive_root_name="[아카이브]")

        print("\n--- [ 구글 드라이브 파일 구조 ] ---")
        
        # 1. 공유된 파일 검색
        shared_items = list_shared_files(service, max_depth=max(1, args.max_depth), max_items=max(20, args.max_items))
        
        # 2. root 폴더 검색
        print("\n📂 내 드라이브 (root):")
        has_root_files = list_files(
            service,
            folder_id=args.folder_id or 'root',
            is_root_call=True,
            max_depth=max(1, args.max_depth),
            max_items=max(20, args.max_items),
        )
        
        # 3. 결과 확인
        if not shared_items and not has_root_files:
            print("\n❌ 검색 결과가 없습니다.")
            print('\n⚠️  현재 OAuth 계정에서 접근 가능한 파일/폴더가 없습니다.')
            print('\n📋 설정 확인:')
            print('  1. 인증한 Google 계정의 Drive에서 파일 존재 여부 확인')
            print('  2. 조직 계정이라면 관리자/API 권한 정책 확인')
            print('  3. 토큰 재인증이 필요하면 google_oauth2_token.json 삭제 후 재실행')
        
        print("\n✅ 탐색 완료")