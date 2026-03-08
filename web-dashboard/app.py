# -*- coding: utf-8 -*-
"""웹 대시보드 메인 애플리케이션"""

import os
import sys
import sqlite3
from datetime import datetime
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

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(32).hex())

def validate_token(token):
    """토큰 유효성 검증"""
    if token not in ngrok_manager.active_tokens:
        return False
    
    token_info = ngrok_manager.active_tokens[token]
    
    # 만료 확인
    if datetime.now() > token_info['expires_at']:
        del ngrok_manager.active_tokens[token]
        return False
    
    # 사용 여부 확인 (일회용)
    if token_info['used']:
        return False
    
    # 토큰 사용 처리
    token_info['used'] = True
    return True

def get_db_connection():
    """아카이브 DB 연결"""
    db_path = project_root / 'content-crawler' / 'archive_index.db'
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """접속 토큰 검증"""
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
    if not session.get('authenticated'):
        return redirect(url_for('index'))
    
    return render_template('dashboard.html')

@app.route('/api/stats')
def api_stats():
    """통계 데이터 API"""
    if not session.get('authenticated'):
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
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    search = request.args.get('search', '').strip()
    platform = request.args.get('platform', '').strip()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database not found'}), 500
    
    try:
        # 기본 쿼리
        where_clauses = []
        params = []
        
        if search:
            where_clauses.append('(title LIKE ? OR summary LIKE ?)')
            params.extend([f'%{search}%', f'%{search}%'])
        
        if platform:
            where_clauses.append('platform = ?')
            params.append(platform)
        
        where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
        
        # 전체 개수
        count_sql = f'SELECT COUNT(*) as count FROM posts WHERE {where_sql}'
        total = conn.execute(count_sql, params).fetchone()['count']
        
        # 페이징된 결과
        offset = (page - 1) * per_page
        posts_sql = f'''
            SELECT id, title, url, platform, media_name, published_date, created_at, summary
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

@app.route('/api/trigger-crawl', methods=['POST'])
def api_trigger_crawl():
    """크롤링 트리거 (GitHub Actions 워크플로 디스패치)"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    # GitHub Actions workflow_dispatch 트리거
    import requests
    
    github_token = os.getenv('GITHUB_TOKEN')
    repo = os.getenv('GITHUB_REPOSITORY', 'boyinblue/myAgent')
    workflow = 'run_crowler.yml'
    
    if not github_token:
        return jsonify({'error': 'GitHub token not configured'}), 500
    
    url = f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches'
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    data = {'ref': 'main'}
    
    try:
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        return jsonify({'success': True, 'message': '크롤링이 시작되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 개발 환경에서는 직접 실행
    app.run(host='0.0.0.0', port=5000, debug=True)
