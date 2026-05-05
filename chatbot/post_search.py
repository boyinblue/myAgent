"""
Post search functionality for the chatbot
"""
import sqlite3
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'archive' / 'archive_index.db'


def get_db_connection():
    """DB 연결"""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def search_posts(keyword: str, limit: int = 10) -> str:
    """
    키워드로 포스트 검색
    
    Args:
        keyword: 검색 키워드
        limit: 최대 반환 개수
    
    Returns:
        포스트 리스트 (문자열 형식)
    """
    if not keyword or not keyword.strip():
        return "검색 키워드를 입력해 주세요."
    
    keyword = keyword.strip()
    conn = get_db_connection()
    if not conn:
        return "데이터베이스를 찾을 수 없습니다."
    
    try:
        # 키워드 정규화: 부분 일치 + 대소문자 무시
        search_pattern = f'%{keyword}%'
        
        # SQL 쿼리: 제목과 태그에서 검색
        query = '''
        SELECT id, title, url, platform, media_name, published_date
        FROM posts
        WHERE (title LIKE ? OR keywords LIKE ? OR tags LIKE ?)
        AND title IS NOT NULL
        AND title NOT IN ('', 'untitled', '제목 없음')
        ORDER BY published_date DESC
        LIMIT ?
        '''
        
        cursor = conn.execute(query, (search_pattern, search_pattern, search_pattern, limit))
        rows = cursor.fetchall()
        
        if not rows:
            return f'"{keyword}" 검색 결과가 없습니다.'
        
        # 결과 포맷팅
        result = f'"{keyword}" 검색 결과 ({len(rows)}개):\n\n'
        for i, row in enumerate(rows, 1):
            title = row['title'] or '(제목 없음)'
            platform = row['platform'] or '?'
            date = row['published_date'] or '날짜 미상'
            url = row['url'] or '#'
            
            result += f'{i}. [{platform}] {title}\n'
            result += f'   📅 {date}\n'
            result += f'   🔗 {url}\n'
        
        return result
    
    except Exception as e:
        return f"검색 중 오류 발생: {str(e)}"
    
    finally:
        conn.close()


def search_random_posts(count: int = 3) -> str:
    """
    랜덤 포스트 검색
    
    Args:
        count: 반환할 포스트 개수
    
    Returns:
        포스트 리스트 (문자열 형식)
    """
    conn = get_db_connection()
    if not conn:
        return "데이터베이스를 찾을 수 없습니다."
    
    try:
        query = '''
        SELECT id, title, url, platform, media_name, published_date
        FROM posts
        WHERE title IS NOT NULL
        AND title NOT IN ('', 'untitled', '제목 없음')
        ORDER BY RANDOM()
        LIMIT ?
        '''
        
        cursor = conn.execute(query, (count,))
        rows = cursor.fetchall()
        
        if not rows:
            return '포스트가 없습니다.'
        
        result = f'랜덤 포스트 추천 ({len(rows)}개):\n\n'
        for i, row in enumerate(rows, 1):
            title = row['title'] or '(제목 없음)'
            platform = row['platform'] or '?'
            date = row['published_date'] or '날짜 미상'
            url = row['url'] or '#'
            
            result += f'{i}. [{platform}] {title}\n'
            result += f'   📅 {date}\n'
            result += f'   🔗 {url}\n'
        
        return result
    
    except Exception as e:
        return f"검색 중 오류 발생: {str(e)}"
    
    finally:
        conn.close()
