import os
import re
import yaml
import email.utils
from datetime import datetime

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
    """URL을 분석하여 platform_type과 media_name을 반환"""

    p_type = "Unknown"
    m_name = "Unknown"
    
    if "blog.naver.com" in url:
        p_type = "NaverBlog"
        if "boyinblue" in url:
            m_name = "boyinblue"
        elif "parksejin03" in url:
            m_name = "parksejin03"
        elif "pgi100" in url:
            m_name = "pgi100"
        elif "sadneye" in url:
            m_name = "sadneye"
    elif "tistory.com" in url:
        p_type = "Tistory"
        if "frankler" in url:
            m_name = "frankler"
        elif "worldclassproduct" in url:
            m_name = "worldclassproduct"
    elif "github.io" in url:
        p_type = "GitHubPages"
        if "boyinblue" in url:
            m_name = "boyinblue"
        elif "esregnet0409" in url:
            m_name = "esregnet0409"
    elif "youtube.com" in url or "youtu.be" in url:
        p_type = "YouTube"
        m_name = "saejinpark4614"

    return p_type, m_name

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

if __name__ == "__main__":
    # 1. 현재 스크립트의 절대 경로
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 2. 상위 디렉토리(..)의 archive 폴더 경로 생성
    # normpath를 써주면 'crawlers\..\archive' 같은 경로를 'C:\...\archive'로 깔끔하게 정리해줍니다.
    archive_dir = os.path.normpath(os.path.join(current_dir, "..", "archive"))

    print(f"[*] 탐색 시작 경로: {archive_dir}")
    for root, dirs, files in os.walk(archive_dir):
        for filename in files:
            if not filename.endswith(".md"):
                continue
            inspect_md_file(os.path.join(root, filename))
