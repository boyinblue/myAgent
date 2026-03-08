import os
import re
import yaml
import json
import email.utils
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# 프로젝트 루트의 config.json 로드
_CONFIG_CACHE = None

def _load_config():
    """config.json을 로드합니다 (캐싱)."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    
    # 스크립트 위치에서 프로젝트 루트로 이동
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    config_path = project_root / "config.json"
    
    if not config_path.exists():
        _CONFIG_CACHE = {"platforms": {}}
        return _CONFIG_CACHE
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _CONFIG_CACHE = json.load(f)
    except Exception:
        _CONFIG_CACHE = {"platforms": {}}
    
    return _CONFIG_CACHE

def get_formatted_date(date_str):
    """날짜 문자열을 YYYY-MM-DD 형식으로 변환"""
    try:
        # RFC 2822 형식 (Thu, 06 Mar 2025 ...) 처리
        parsed_date = email.utils.parsedate_to_datetime(date_str)
        return parsed_date.strftime("%Y-%m-%d")
    except Exception:
        # ISO 형식이나 다른 형식일 경우 (YYYY-MM-DD 추출)
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if match:
            return match.group(0)
    return None

def get_platform_info(url):
    """
    URL을 분석하여 platform_type과 media_name을 반환합니다.
    config.json의 platforms 섹션을 기반으로 동적 매칭합니다.
    """
    if not url:
        return "Unknown", "Unknown"
    
    config = _load_config()
    platforms = config.get("platforms", {})
    
    url_lower = url.lower()
    parsed = urlparse(url)
    
    # 1. Naver Blog 처리
    if "blog.naver.com" in url_lower:
        naver_blogs = platforms.get("naver_blog", {}).get("blogs", [])
        for blog in naver_blogs:
            blog_id = blog.get("blog_id", "")
            if blog_id and blog_id.lower() in url_lower:
                return blog.get("platform_type", "NaverBlog"), blog_id
        return "NaverBlog", "Unknown"
    
    # 2. Tistory 처리
    if "tistory.com" in url_lower:
        tistory_blogs = platforms.get("tistory", {}).get("blogs", [])
        for blog in tistory_blogs:
            blog_url = blog.get("blog_url", "")
            if blog_url:
                blog_domain = urlparse(blog_url).netloc.lower()
                if blog_domain in url_lower or blog.get("name", "").lower() in url_lower:
                    return blog.get("platform_type", "Tistory"), blog.get("name", "Unknown")
        return "Tistory", "Unknown"
    
    # 3. GitHub Pages 처리
    if "github.io" in url_lower:
        gh_blogs = platforms.get("github_pages", {}).get("blogs", [])
        for blog in gh_blogs:
            blog_url = blog.get("blog_url", "")
            if blog_url:
                blog_domain = urlparse(blog_url).netloc.lower()
                if blog_domain in url_lower:
                    return blog.get("platform_type", "GitHubPages"), blog.get("name", "Unknown")
        return "GitHubPages", "Unknown"
    
    # 4. YouTube 처리
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        youtube_channels = platforms.get("youtube", {}).get("channels", [])
        for channel in youtube_channels:
            channel_url = channel.get("channel_url", "")
            channel_id = channel.get("channel_id", "")
            if (channel_url and channel_url.lower() in url_lower) or \
               (channel_id and channel_id.lower() in url_lower):
                return channel.get("platform_type", "YouTube"), channel.get("name", "Unknown")
        # YouTube는 채널 정보가 없어도 플랫폼은 확정
        if youtube_channels:
            return "YouTube", youtube_channels[0].get("name", "Unknown")
        return "YouTube", "Unknown"
    
    return "Unknown", "Unknown"

def repair_md_metadata(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 1. YAML Frontmatter 추출
        match = re.search(r'^---\s*\n(.*?)\n---\s*(?:\n|$)', content, re.MULTILINE | re.DOTALL)
        if not match:
            print(f"[!] YAML Frontmatter를 찾을 수 없습니다: {filename}")
            return

        full_match = match.group(0) # --- 포함 전체
        yaml_content = match.group(1)
        
        # 가끔 따옴표 없는 특수문자로 인한 에러 방지용 safe_load
        try:
            metadata = yaml.safe_load(yaml_content)
        except yaml.YAMLError:
            print(f"[!] YAML 파싱 오류: {filename}")
            return
        # 2. 필드 누락 여부 확인
        modified = False
        url = metadata.get('url', '')
        p_type, m_name = get_platform_info(url)

        if 'platform_type' not in metadata or 'media_name' not in metadata:
            if 'platform_type' not in metadata:
                metadata['platform_type'] = p_type

            if 'media_name' not in metadata:
                metadata['media_name'] = m_name

            modified = True

        if metadata['platform_type'] != p_type or metadata['media_name'] != m_name:
            metadata['platform_type'] = p_type
            metadata['media_name'] = m_name
            modified = True

        # 3. 변경 사항이 있으면 파일 업데이트
        if modified:
            # YAML 데이터를 다시 문자열로 변환 (allow_unicode=True 필수)
            new_yaml = yaml.dump(metadata, allow_unicode=True, sort_keys=False).strip()
            new_content = f"---\n{new_yaml}\n---\n" + content[len(full_match):]
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"[+] 필드 추가 완료: {filename} ({metadata['platform_type']})")
    except Exception as e:
        print(f"[ERROR] {filename} 처리 중 오류: {e}")

def delete_duplicate_hyphens(file_path, new_file_path):
    print(f"[!] 중복된 하이픈 제거: {file_path} -> {new_file_path}")
    if os.path.exists(new_file_path):
        os.remove(new_file_path)
    os.rename(file_path, new_file_path)

def fix_quotes_in_comments(line):
    if line.strip().startswith('comments:'):
        # 1. 'comments: "' 와 마지막 '"'를 제외한 내부의 쌍따옴표만 찾음
        # 2. 내부의 쌍따옴표를 홑따옴표(')로 치환
        match = re.match(r'(comments:\s*")(.*)("\s*)', line)
        if match:
            prefix, content, suffix = match.groups()
            fixed_content = content.replace('"', "'")
            return f"{prefix}{fixed_content}{suffix}\n"
    return line

def clean_html_from_comments(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    modified = False
    new_lines = []

    # HTML 태그 매칭 정규식 (예: <img ... />, <div> 등)
    html_tag_pattern = re.compile(r'<[^>]*>')

    for line in lines:
        # "comments: "로 시작하는 라인만 타겟팅
        if line.strip().startswith('comments:'):
            # 태그 제거
            cleaned_line = html_tag_pattern.sub('', line)
            
            if cleaned_line != line:
                new_lines.append(cleaned_line)
                modified = True
                continue

            match = re.match(r'(comments:\s*")(.*)("\s*)', line)
            if match:
                prefix, content, suffix = match.groups()
                fixed_content = content.replace('"', "'")
                new_lines.append(f"{prefix}{fixed_content}{suffix}\n")
                modified = True
                continue
        
        new_lines.append(line)

    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"[+] HTML 제거 완료: {os.path.basename(file_path)}")

def rename_md_files(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 1. YAML Frontmatter 추출
        # --- 와 --- 사이의 내용을 찾음
        match = re.search(r'^---\s*\n(.*?)\n---\s*(?:\n|$)', content, re.MULTILINE | re.DOTALL)
        if not match:
            print(f"[!] YAML Frontmatter를 찾을 수 없습니다: {filename}")
            return
        yaml_content = match.group(1)
        metadata = yaml.safe_load(yaml_content)
        
        created_at = metadata.get('created_at')
        platform_type = metadata.get('platform_type')
        media_name = metadata.get('media_name')
        title = metadata.get('title')

        import archive_manager as ArchiveManager
        archive_mgr = ArchiveManager.ArchiveManager()
        title = archive_mgr._slugify_title(title)

        if not created_at or not platform_type or not media_name or not title:
            print(f"[!] 필수 정보 누락: {filename}")
            return
        # 2. 날짜 변환
        date_prefix = get_formatted_date(created_at)
        if not date_prefix:
            print(f"[!] 날짜 파싱 실패: {created_at} in {filename}")
            return
        # 3. 새 파일명 생성 및 변경
        new_filename = f"{date_prefix}-{platform_type}-{media_name}-{title}.md"
        new_file_path = os.path.join(root, new_filename)
        # 파일명 중복 방지 로직 (이미 같은 이름이 있으면 skip)
        if os.path.exists(new_file_path):
            return
        os.rename(file_path, new_file_path)
        print(f"[+] 변경 완료: {filename} -> {new_filename}")

    except Exception as e:
        print(f"[ERROR] {filename} 처리 중 오류: {e}")

def inspect_md_file(file_path):
    # 중복 하이픈 제거
    new_filename = re.sub(r'-{2,}', '-', filename)
    new_file_path = os.path.join(root, new_filename)
    if file_path != new_file_path:
        delete_duplicate_hyphens(file_path, new_file_path)
        return

    # Comment 항목 HTML 테그 제거
    clean_html_from_comments(file_path)

    # YAML Frontmatter 검사 및 필드 추가
    repair_md_metadata(file_path)

    # 파일명 포맷에 맞게 rename (YYYY-MM-DD-)
    rename_md_files(file_path)

def inspect_index_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            index_data = yaml.safe_load(f)

        for post in index_data.get('posts', []):
            print(f"Raw Data: {post}")

        # 3. 수정된 데이터로 파일 업데이트
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(index_data, f, allow_unicode=True, sort_keys=False)
        print(f"[+] index.json 검사 및 수정 완료")

    except Exception as e:
        print(f"[ERROR] index.json 처리 중 오류: {e}")

if __name__ == "__main__":
    # 현재 스크립트의 절대 경로
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 상위 디렉토리(..)의 archive 폴더 경로 생성
    # normpath를 써주면 'crawlers\..\archive' 같은 경로를 'C:\...\archive'로 깔끔하게 정리해줍니다.
    archive_dir = os.path.normpath(os.path.join(current_dir, "..", "archive"))

    # MD 파일 검사 및 수정
    print(f"[*] 탐색 시작 경로: {archive_dir}")
    for root, dirs, files in os.walk(archive_dir):
        for filename in files:
            if not filename.endswith(".md"):
                continue
            inspect_md_file(os.path.join(root, filename))

    # index.json 파일 검사 및 수정
    index_json_path = os.path.join(archive_dir, "index.json")
    inspect_index_json(index_json_path)
