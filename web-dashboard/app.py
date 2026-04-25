# -*- coding: utf-8 -*-
"""웹 대시보드 메인 애플리케이션"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# content-crawler/utils에 접근하기 위해 경로 추가
content_crawler = project_root / 'content-crawler'
if str(content_crawler) not in sys.path:
    sys.path.insert(0, str(content_crawler))

from utils.secrets import load_environment
load_environment()

# ngrok_manager의 토큰 관리 함수 import
import ngrok_manager
import json

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(32).hex())

# 토큰 저장 파일
_TOKENS_FILE = Path(__file__).parent / '.access_tokens.json'

def is_local_mode() -> bool:
    return (os.getenv('DASHBOARD_LOCAL_MODE', '0').strip() == '1')


def is_authenticated() -> bool:
    return is_local_mode() or bool(session.get('authenticated'))

def validate_token(token):
    """토큰 유효성 검증 (파일 기반, 제한 횟수 사용)"""
    try:
        # 파일에서 토큰 읽기
        if not _TOKENS_FILE.exists():
            return False
        
        with open(_TOKENS_FILE, 'r') as f:
            all_tokens = json.load(f)
        
        if token not in all_tokens:
            return False
        
        token_info = all_tokens[token]
        
        # 만료 확인
        expires_at = datetime.fromisoformat(token_info['expires_at'])
        if datetime.now() > expires_at:
            # 만료된 토큰 제거
            del all_tokens[token]
            with open(_TOKENS_FILE, 'w') as f:
                json.dump(all_tokens, f)
            return False
        
        used_count = int(token_info.get('used_count', 0))
        max_uses = int(token_info.get('max_uses', 1))

        # 구버전 토큰(used 플래그만 존재) 하위 호환
        if 'used_count' not in token_info and 'used' in token_info:
            used_count = 1 if bool(token_info.get('used')) else 0
            max_uses = 1

        if used_count >= max_uses:
            return False
        
        # 토큰 사용 처리
        token_info['used_count'] = used_count + 1
        token_info['max_uses'] = max_uses
        token_info['used'] = token_info['used_count'] >= token_info['max_uses']
        all_tokens[token] = token_info
        with open(_TOKENS_FILE, 'w') as f:
            json.dump(all_tokens, f)
        
        return True
    except Exception as e:
        print(f"[!] 토큰 검증 실패: {e}")
        return False

def get_db_connection():
    """아카이브 DB 연결"""
    db_path = project_root / 'archive' / 'archive_index.db'
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# DATE_EXPR: published_date이 없거나 'None' 문자열이면 created_at 사용
DATE_EXPR = "date(COALESCE(NULLIF(published_date, ''), NULLIF(published_date, 'None'), created_at))"


def _build_posts_select_sql(conn):
    """posts 테이블에서 사용 가능한 컬럼으로 SELECT 구문 생성"""
    rows = conn.execute("PRAGMA table_info(posts)").fetchall()
    columns = {row['name'] for row in rows}

    base_columns = [
        'id',
        'title',
        'url',
        'platform',
        'media_name',
        'published_date',
        'created_at',
        'keywords',
        'tags',
    ]

    select_parts = [f'"{col}"' for col in base_columns if col in columns]

    image_candidates = [
        'representative_image',
        'thumbnail_url',
        'thumbnail',
        'image_url',
        'image',
        'og_image',
    ]
    image_col = next((col for col in image_candidates if col in columns), None)
    if image_col:
        select_parts.append(f'"{image_col}" AS representative_image')
    else:
        select_parts.append("'' AS representative_image")

    # 요약 필드가 있으면 사용하고, 없으면 빈 문자열로 내려준다.
    if 'summary' in columns:
        select_parts.append('"summary"')
    else:
        select_parts.append("'' AS summary")

    return ', '.join(select_parts)


def _build_search_platform_where(search, platform):
    where_clauses = []
    params = []

    if search:
        where_clauses.append('(title LIKE ? OR keywords LIKE ? OR tags LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    if platform:
        where_clauses.append('platform = ?')
        params.append(platform)

    return where_clauses, params


def _build_calendar_day_map(rows):
    """날짜별 count / titles(최대 3개)로 재구성"""
    days = {}
    for row in rows:
        day = row['day']
        if not day:
            continue

        if day not in days:
            days[day] = {'count': 0, 'titles': []}

        days[day]['count'] += 1

        if len(days[day]['titles']) < 3:
            days[day]['titles'].append({
                'title': row['title'] or '(제목 없음)',
                'url': row['url'] or '',
            })

    return days


def _to_post_preview(row):
    return {
        'id': row.get('id'),
        'title': row.get('title') or '(제목 없음)',
        'url': row.get('url') or '',
        'platform': row.get('platform') or '',
        'media_name': row.get('media_name') or '',
        'published_date': row.get('published_date') or '',
        'created_at': row.get('created_at') or '',
        'representative_image': row.get('representative_image') or '',
    }

@app.route('/')
def index():
    """접속 토큰 검증"""
    if is_local_mode():
        session['authenticated'] = True
        return redirect(url_for('dashboard'))

    token = request.args.get('token')
    
    if not token:
        return "⛔ 접속 토큰이 필요합니다. 텔레그램 봇에서 URL을 요청하세요.", 403
    
    if not validate_token(token):
        return "⛔ 유효하지 않거나 만료된 토큰입니다.", 403
    
    # 세션에 인증 상태 저장
    session['authenticated'] = True
    session['token'] = token
    
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    """메인 대시보드"""
    if not is_authenticated():
        return redirect(url_for('index'))
    
    return render_template('dashboard.html')

@app.route('/api/stats')
def api_stats():
    """통계 데이터 API"""
    if not is_authenticated():
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database not found'}), 500
    
    try:
        # 전체 통계
        total = conn.execute('SELECT COUNT(*) as count FROM posts').fetchone()['count']
        
        # 플랫폼별 통계
        platform_stats = conn.execute('''
            SELECT platform, COUNT(*) as count 
            FROM posts 
            GROUP BY platform 
            ORDER BY count DESC
        ''').fetchall()
        
        # 최근 30일 추가된 포스트 수
        recent = conn.execute('''
            SELECT COUNT(*) as count 
            FROM posts 
            WHERE created_at >= datetime('now', '-30 days')
        ''').fetchone()['count']
        
        return jsonify({
            'total_posts': total,
            'recent_posts': recent,
            'platform_stats': [dict(row) for row in platform_stats]
        })
    finally:
        conn.close()

@app.route('/api/posts')
def api_posts():
    """포스트 목록 API"""
    if not is_authenticated():
        return jsonify({'error': 'Unauthorized'}), 403
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    search = request.args.get('search', '').strip()
    platform = request.args.get('platform', '').strip()
    published_on = request.args.get('published_on', '').strip()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database not found'}), 500
    
    try:
        select_sql = _build_posts_select_sql(conn)

        # 기본 쿼리
        where_clauses, params = _build_search_platform_where(search, platform)
        # 제목이 없거나 'untitled'인 글은 제외 (완전하지 않은 데이터)
        where_clauses.append("title IS NOT NULL AND title NOT IN ('', 'untitled', '제목 없음')")

        if published_on:
            where_clauses.append(f"{DATE_EXPR} = date(?)")
            params.append(published_on)
        
        where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
        
        # 전체 개수
        count_sql = f'SELECT COUNT(*) as count FROM posts WHERE {where_sql}'
        total = conn.execute(count_sql, params).fetchone()['count']
        
        # 페이징된 결과
        offset = (page - 1) * per_page
        posts_sql = f'''
            SELECT {select_sql}
            FROM posts 
            WHERE {where_sql}
            ORDER BY published_date DESC, created_at DESC
            LIMIT ? OFFSET ?
        '''
        params.extend([per_page, offset])
        posts = conn.execute(posts_sql, params).fetchall()
        
        return jsonify({
            'total': total,
            'page': page,
            'per_page': per_page,
            'posts': [dict(row) for row in posts]
        })
    finally:
        conn.close()


@app.route('/api/calendar')
def api_calendar():
    """월별 캘린더 집계 API (날짜별 count + 상위 3개 제목)"""
    if not is_authenticated():
        return jsonify({'error': 'Unauthorized'}), 403

    now = datetime.now()
    year = int(request.args.get('year', now.year))
    month = int(request.args.get('month', now.month))
    search = request.args.get('search', '').strip()
    platform = request.args.get('platform', '').strip()

    if month < 1 or month > 12:
        return jsonify({'error': 'Invalid month'}), 400

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    month_start = f'{year:04d}-{month:02d}-01'
    next_month_start = f'{next_year:04d}-{next_month:02d}-01'

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database not found'}), 500

    try:
        where_clauses, params = _build_search_platform_where(search, platform)
        where_clauses.insert(0, f"{DATE_EXPR} >= date(?)")
        where_clauses.insert(1, f"{DATE_EXPR} < date(?)")
        # 제목이 없거나 'untitled'인 글은 제외 (완전하지 않은 데이터)
        where_clauses.append("title IS NOT NULL AND title NOT IN ('', 'untitled', '제목 없음')")
        params = [month_start, next_month_start] + params
        where_sql = ' AND '.join(where_clauses)

        rows = conn.execute(
            f'''
            SELECT
                {DATE_EXPR} AS day,
                title,
                url
            FROM posts
            WHERE {where_sql}
            ORDER BY day ASC, datetime(COALESCE(NULLIF(published_date, ''), created_at)) DESC
            ''',
            params,
        ).fetchall()

        days = _build_calendar_day_map(rows)

        return jsonify({
            'year': year,
            'month': month,
            'days': days,
        })
    finally:
        conn.close()


@app.route('/api/calendar/week')
def api_calendar_week():
    """주간 캘린더 API (7일)"""
    if not is_authenticated():
        return jsonify({'error': 'Unauthorized'}), 403

    search = request.args.get('search', '').strip()
    platform = request.args.get('platform', '').strip()
    reference_date_str = request.args.get('date', '').strip()

    if reference_date_str:
        try:
            ref_date = datetime.strptime(reference_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    else:
        ref_date = datetime.now().date()

    week_start = ref_date - timedelta(days=ref_date.weekday())
    week_end = week_start + timedelta(days=6)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database not found'}), 500

    try:
        where_clauses, params = _build_search_platform_where(search, platform)
        where_clauses.insert(0, f"{DATE_EXPR} >= date(?)")
        where_clauses.insert(1, f"{DATE_EXPR} <= date(?)")
        # 제목이 없거나 'untitled'인 글은 제외 (완전하지 않은 데이터)
        where_clauses.append("title IS NOT NULL AND title NOT IN ('', 'untitled', '제목 없음')")
        params = [week_start.isoformat(), week_end.isoformat()] + params
        where_sql = ' AND '.join(where_clauses)

        rows = conn.execute(
            f'''
            SELECT
                {DATE_EXPR} AS day,
                title,
                url
            FROM posts
            WHERE {where_sql}
            ORDER BY day ASC, datetime(COALESCE(NULLIF(published_date, ''), created_at)) DESC
            ''',
            params,
        ).fetchall()

        day_map = _build_calendar_day_map(rows)
        ordered_days = []
        for offset in range(7):
            current = week_start + timedelta(days=offset)
            key = current.isoformat()
            info = day_map.get(key, {'count': 0, 'titles': []})
            ordered_days.append({
                'date': key,
                'count': info['count'],
                'titles': info['titles'],
            })

        return jsonify({
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'days': ordered_days,
        })
    finally:
        conn.close()


@app.route('/api/discover')
def api_discover():
    """달력 하단 추천 목록 API (몇 년 전 오늘 + 랜덤)"""
    if not is_authenticated():
        return jsonify({'error': 'Unauthorized'}), 403

    search = request.args.get('search', '').strip()
    platform = request.args.get('platform', '').strip()

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database not found'}), 500

    try:
        select_sql = _build_posts_select_sql(conn)
        today = datetime.now().date()
        md = today.strftime('%m-%d')
        current_year = today.strftime('%Y')

        where_clauses, base_params = _build_search_platform_where(search, platform)

        history_where = [
            "strftime('%m-%d', " + DATE_EXPR + ") = ?",
            "strftime('%Y', " + DATE_EXPR + ") < ?",
            "title IS NOT NULL AND title NOT IN ('', 'untitled', '제목 없음')",
        ] + where_clauses
        history_params = [md, current_year] + base_params

        random_where = ["title IS NOT NULL AND title NOT IN ('', 'untitled', '제목 없음')"]
        if where_clauses:
            random_where.extend(where_clauses)
        else:
            random_where.append('1=1')
        random_params = base_params[:]

        history_rows = conn.execute(
            f'''
            SELECT {select_sql}
            FROM posts
            WHERE {' AND '.join(history_where)}
            ORDER BY {DATE_EXPR} DESC
            LIMIT 3
            ''',
            history_params,
        ).fetchall()

        random_rows = conn.execute(
            f'''
            SELECT {select_sql}
            FROM posts
            WHERE {' AND '.join(random_where)}
            ORDER BY RANDOM()
            LIMIT 3
            ''',
            random_params,
        ).fetchall()

        return jsonify({
            'today_history': [_to_post_preview(dict(row)) for row in history_rows],
            'random_posts': [_to_post_preview(dict(row)) for row in random_rows],
        })
    finally:
        conn.close()

@app.route('/api/trigger-crawl', methods=['POST'])
def api_trigger_crawl():
    """크롤링 트리거 (GitHub Actions 워크플로 디스패치)"""
    if not is_authenticated():
        return jsonify({'error': 'Unauthorized'}), 403
    
    import requests
    
    github_token = os.getenv('GITHUB_TOKEN')
    repo = os.getenv('GITHUB_REPOSITORY', 'boyinblue/myAgent')
    workflow = 'run_crowler.yml'
    
    if not github_token:
        return jsonify({'error': 'GitHub token not configured'}), 500
    
    # 요청 본문에서 선택적 URL 파라미터 추출
    body = request.get_json(silent=True) or {}
    target_url = body.get('url', '').strip()
    
    api_url = f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches'
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    data = {
        'ref': 'main',
        'inputs': {'url': target_url},  # 빈 문자열이면 전체 크롤링
    }
    
    try:
        resp = requests.post(api_url, headers=headers, json=data)
        resp.raise_for_status()
        msg = f'단건 URL 크롤링이 시작되었습니다: {target_url}' if target_url else '전체 크롤링이 시작되었습니다.'
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        return jsonify({'error': str(e), 'detail': getattr(e, 'response', None) and e.response.text}), 500


@app.route('/api/crawl-status')
def api_crawl_status():
    """현재 크롤링 워크플로 실행 상태 조회"""
    if not is_authenticated():
        return jsonify({'error': 'Unauthorized'}), 403

    import requests

    github_token = os.getenv('GITHUB_TOKEN')
    repo = os.getenv('GITHUB_REPOSITORY', 'boyinblue/myAgent')
    workflow = 'run_crowler.yml'

    if not github_token:
        return jsonify({'configured': False, 'running': False, 'message': 'GitHub token not configured'})

    api_url = f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?per_page=1'
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        resp.raise_for_status()
        runs = resp.json().get('workflow_runs', [])

        if not runs:
            return jsonify({'configured': True, 'running': False, 'message': '실행 이력이 없습니다.'})

        run = runs[0]
        status = run.get('status', '')
        conclusion = run.get('conclusion')
        running = status in ('queued', 'in_progress', 'waiting', 'pending', 'requested')

        return jsonify({
            'configured': True,
            'running': running,
            'status': status,
            'conclusion': conclusion,
            'workflow_name': run.get('name', workflow),
            'html_url': run.get('html_url', ''),
            'created_at': run.get('created_at', ''),
            'updated_at': run.get('updated_at', ''),
            'message': '크롤링이 실행 중입니다.' if running else '현재 실행 중인 크롤링이 없습니다.',
        })
    except Exception as e:
        return jsonify({'configured': True, 'running': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # 개발 환경에서는 직접 실행
    app.run(host='0.0.0.0', port=5000, debug=True)
