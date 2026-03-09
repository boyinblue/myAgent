#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug parse_url update process"""

from crawlers.naver_blog import NaverBlogCrawler
from archive_manager import ArchiveManager
import os
from pathlib import Path

# 아카이브 루트 결정 (프로젝트 루트)
script_dir = Path(__file__).resolve().parent
archive_root = script_dir.parent / 'archive'

# 아카이브 매니저 생성
am = ArchiveManager(archive_root=str(archive_root))

# 테스트 URL
test_url = 'https://blog.naver.com/boyinblue/221222400123'

print("[*] 테스트 시작")
print(f"[*] 입력 URL: {test_url}")

# 1. DB 상태 확인 BEFORE
am.cur.execute('SELECT title FROM achieves WHERE url LIKE ?', ('%221222400123%',))
records = am.cur.fetchall()
print(f"\n[1] DB 검색 결과 (221222400123 포함):")
for rec in records:
    print(f"    title: {rec[0]}")

# 2. parse_url 호출
print(f"\n[2] parse_url 호출:")
crawler = NaverBlogCrawler('boyinblue', archive_mgr=am)
result = crawler.parse_url(test_url)

print(f"\n[3] 반환 결과:")
print(f"    title: {result['title'] if result else 'None'}")
print(f"    resolved_url: {result.get('resolved_url') if result else 'None'}")

# 3. DB 상태 확인 AFTER
print(f"\n[4] DB 검색 결과 (업데이트 후):")
am.cur.execute('SELECT title FROM achieves WHERE url LIKE ?', ('%221222400123%',))
records = am.cur.fetchall()
for rec in records:
    print(f"    title: {rec[0]}")
