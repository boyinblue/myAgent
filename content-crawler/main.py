# -*- coding: utf-8 -*-
# 파일 인코딩: UTF-8
"""콘텐츠 크롤러 메인 실행 스크립트

여러 플랫폼에서 콘텐츠를 수집하고 아카이브에 저장합니다.
지원: 네이버 블로그, Tistory, GitHub Pages, YouTube
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone
from typing import List, Dict

# 환경 변수 로드
from utils.secrets import load_environment
load_environment()

# 로컬 모듈 import
from crawlers.naver_blog import NaverBlogCrawler
from crawlers.tistory_blog import TistoryBlogCrawler
from crawlers.github_pages import GitHubPagesCrawler
from crawlers.youtube import YouTubeCrawler
from archive_manager import ArchiveManager
from event_date_extractor import EventDateExtractor
from utils.telegram_notifier import TelegramNotifier
from utils.error_collector import ErrorCollector
from scheduler import DailyDigestScheduler

# 버전 정보 (아카이브 업데이트를 추적하기 위해)
CRAWLER_VERSION = "2.2"

def load_config(config_file="config.json"):
    """설정 파일을 로드합니다."""
    if not os.path.exists(config_file):
        print(f"[!] 설정 파일을 찾을 수 없습니다: {config_file}")
        return None

    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_metadata(posts, output_file):
    """포스트 메타데이터를 JSON으로 저장합니다."""
    data = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_posts": len(posts),
        "posts": posts,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[+] 메타데이터 저장: {output_file} ({len(posts)}개)")


def archive_posts(posts, archive_mgr, platform_type="", media_name="", raw_dir: str = None):
    """포스트를 아카이브에 저장합니다.

    HTML이 제공된 포스트에서는 본문에서 이미지를 찾아 메타데이터(주소, 설명, 크기, SHA256)를 추출하고
    Frontmatter에 `images` 필드로 추가합니다.

    raw_dir가 지정되면 각 포스트의 원본 HTML/Raw 데이터를 해당 디렉토리에 저장합니다 (로컬 전용).
    """
    extractor = EventDateExtractor()
    archived_count = 0

    for post in posts:
        try:
            title = post.get("title", "제목 없음")
            link = post.get("link", "")
            content = post.get("content", "")
            published = post.get("published", "")
            tags = post.get("tags") or []
            summary = post.get("summary") or ""
            comments = post.get("comments") or ""

            if link.startswith("https://blog.naver.com") and "?" in link:
                link = link.split("?")[0]

            # 중복 확인
            if archive_mgr.is_archived(link):
                print(f"[i] 이미 아카이브됨, 건너뜁니다: {link}")
                post["new"] = False
                continue

            # 발견된 링크를 아카이브에 저장
            print(f"[*] 아카이브 저장 중: {title} ({link})")

            # 이벤트 날짜 추출
            extracted_dates = extractor.extract(content) if content else []

            # 키워드 추출
            from utils.keyword_extractor import extract_keywords
            keywords = extract_keywords(content or "", top_n=5)

            # 이미지 메타 추출 함수
            def extract_images(html_str):
                images = []
                try:
                    from bs4 import BeautifulSoup
                    import hashlib
                    import requests

                    soup = BeautifulSoup(html_str or "", "html.parser")
                    for img in soup.find_all("img", src=True):
                        url = img["src"]
                        desc = img.get("alt", "")
                        size = None
                        sha = None
                        try:
                            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                            data = r.content
                            size = len(data)
                            sha = hashlib.sha256(data).hexdigest()
                        except Exception:
                            pass
                        images.append({
                            "url": url,
                            "description": desc,
                            "blog": media_name,
                            "size": size,
                            "sha256": sha,
                        })
                except Exception:
                    pass
                return images

            # ollama를 이용한 요약 시도
            summary_text = ""
            if content:
                try:
                    summary_text = archive_mgr.summarize_with_ollama(content) or ""
                    if summary_text:
                        print(f"[+] Ollama 요약 생성 완료")
                except Exception as e:
                    print(f"[!] 요약 생성 실패: {e}")

            # 이미지 리스트 생성
            html_for_images = post.get("html") or content or ""
            images = extract_images(html_for_images)

            # raw_html 준비 (있으면 html 저장)
            raw_html = post.get("html") or ""

            # 마크다운 생성 및 저장 (create_markdown_file 사용)
            archive_mgr.create_markdown_file(
                title=title,
                url=link,
                platform_type=platform_type,
                media_name=media_name,
                content=content or "(본문 없음)",
                created_at=published,
                event_dates=extracted_dates,
                tags=tags,
                comments=summary_text or comments,
                keywords=keywords,
                crawler_version=CRAWLER_VERSION,
                images=images,
                raw_html=raw_html,
                raw_dir=raw_dir,
            )
            archived_count += 1
            post["new"] = True

        except Exception as e:
            print(f"[!] 아카이브 실패 ({title}): {e}")

    print(f"[+] {archived_count}개 포스트를 아카이브에 저장했습니다")
    archive_mgr.update_index(media_name, platform="mixed")


def crawl_naver_blog(config: Dict, args, archive_mgr=None):
    """네이버 블로그 크롤링

    config 플랫폼 섹션에서 blogs 리스트를 읽어 여러 블로그를 순회합니다.
    또한 CLI의 --naver-blog 옵션을 통해 수동 블로그 ID를 추가로 크롤할 수 있습니다.
    """
    naver_config = config.get("platforms", {}).get("naver_blog", {})
    if not naver_config.get("enabled"):
        return []

    # 기본 블로그 목록
    blogs = []
    if isinstance(naver_config.get("blogs"), list):
        blogs = naver_config.get("blogs")
    else:
        # 이전 구조 호환성
        blogs = [{
            "platform_type": naver_config.get("platform_type", "NaverBlog"),
            "blog_id": naver_config.get("blog_id", "boyinblue"),
            "rss_url": naver_config.get("rss_url"),
            "request_interval_seconds": naver_config.get("request_interval_seconds", 1.0),
        }]

    # CLI에 추가된 블로그 ID 처리
    if args.naver_blog:
        for bid in args.naver_blog:
            blogs.append({"blog_id": bid, "rss_url": None, "request_interval_seconds": 1.0})

    all_posts = []

    for info in blogs:
        platform_type = info.get("platform_type", "NaverBlog")
        blog_id = info.get("blog_id")
        request_interval = info.get("request_interval_seconds", 1.0)
        rss_url = info.get("rss_url")

        print(f"\n[*] 네이버 블로그 크롤링 시작 (블로그: {blog_id})")
        print(f"[*] 요청 간격: {request_interval}초")

        crawler = NaverBlogCrawler(blog_id, rss_url=rss_url, request_interval=request_interval)
        posts = crawler.crawl(max_posts=args.max_posts)

        if posts:
            archive_posts(posts, archive_mgr, platform_type, blog_id)
            all_posts.extend(posts)

    return all_posts


def crawl_tistory_blogs(config: Dict, args, archive_mgr=None):
    """티스토리 블로그 크롤링"""
    tistory_config = config.get("platforms", {}).get("tistory", {})
    if not tistory_config.get("enabled"):
        return []

    blogs = tistory_config.get("blogs", [])
    all_posts: List[Dict] = []

    for blog_info in blogs:
        blog_url = blog_info.get("blog_url")
        platform_type = blog_info.get("platform_type", "Tistory")
        blog_name = blog_info.get("name", "unknown")
        request_interval = blog_info.get("request_interval_seconds", 1.0)

        if not blog_url:
            continue

        print(f"\n[*] 티스토리 블로그 크롤링 시작 ({blog_name}: {blog_url})")
        print(f"[*] 요청 간격: {request_interval}초")

        crawler = TistoryBlogCrawler(blog_url, request_interval=request_interval)
        posts = crawler.crawl(max_posts=args.max_posts, archive_mgr=archive_mgr)

        if posts:
            archive_root = config.get("archive_root", "./archive")
            raw_dir = config.get("raw_directory")
            archive_posts(posts, archive_mgr, platform_type, blog_name, raw_dir=raw_dir)
            all_posts.extend(posts)

    return all_posts


def crawl_github_pages(config: Dict, args, archive_mgr=None):
    """GitHub Pages 크롤링"""
    gp_config = config.get("platforms", {}).get("github_pages", {})
    if not gp_config.get("enabled"):
        return []

    blogs = gp_config.get("blogs", [])
    all_posts: List[Dict] = []

    for blog_info in blogs:
        blog_url = blog_info.get("blog_url")
        platform_type = blog_info.get("platform_type", "GitHubPages")
        blog_name = blog_info.get("name", "unknown")
        request_interval = blog_info.get("request_interval_seconds", 1.0)

        if not blog_url:
            continue

        print(f"\n[*] GitHub Pages 크롤링 시작 ({blog_name}: {blog_url})")
        print(f"[*] 요청 간격: {request_interval}초")

        crawler = GitHubPagesCrawler(blog_url, request_interval=request_interval, archive_mgr=archive_mgr)
        posts = crawler.crawl(max_posts=args.max_posts)

        if posts:
            archive_root = config.get("archive_root", "./archive")
            raw_dir = config.get("raw_directory")
            archive_posts(posts, archive_mgr, platform_type, blog_name, raw_dir=raw_dir)
            all_posts.extend(posts)

    return all_posts


def crawl_youtube(config: Dict, args, archive_mgr=None):
    """YouTube 채널 크롤링"""
    yt_config = config.get("platforms", {}).get("youtube", {})
    if not yt_config.get("enabled"):
        return []

    channels = yt_config.get("channels", [])
    all_videos: List[Dict] = []

    for channel_info in channels:
        channel_url = channel_info.get("channel_url")
        platform_type = channel_info.get("platform_type", "YouTube")
        channel_id = channel_info.get("channel_id")
        channel_name = channel_info.get("name", "unknown")
        request_interval = channel_info.get("request_interval_seconds", 1.0)

        if not channel_url:
            continue

        print(f"\n[*] YouTube 채널 크롤링 시작 ({channel_name}: {channel_url}, ID: {channel_id})")
        print(f"[*] 요청 간격: {request_interval}초")

        crawler = YouTubeCrawler(channel_url=channel_url, channel_id=channel_id, request_interval=request_interval)
        videos = crawler.crawl(max_videos=args.max_posts)

        if videos:
            archive_root = config.get("archive_root", "./archive")
            raw_dir = config.get("raw_directory")
            archive_posts(videos, archive_mgr, platform_type, channel_name, raw_dir=raw_dir)
            all_videos.extend(videos)

    return all_videos


def get_number_of_new_archived(posts: List[Dict]) -> int:
    """새로 아카이브된 포스트 수를 계산합니다."""
    return sum(1 for post in posts if post.get("new"))


def test_telegram_config():
    """텔레그램 설정을 테스트합니다."""
    from utils.secrets import get_telegram_token, get_telegram_chat_id
    
    print("\n[*] 텔레그램 설정 확인 중...")
    token = get_telegram_token()
    chat_id = get_telegram_chat_id()
    
    print(f"  TELEGRAM_BOT_TOKEN: {'✓ 설정됨' if token and token != 'your_telegram_bot_token_here' else '✗ 설정 필요'}")
    print(f"  TELEGRAM_CHAT_ID: {'✓ 설정됨' if chat_id else '✗ 설정 필요'}")
    
    if not token or token == 'your_telegram_bot_token_here':
        print("\n[i] 텔레그램 봇 토큰을 설정하려면:")
        print("  1. Telegram에서 @BotFather와 대화")
        print("  2. /newbot 명령어로 새 봇 생성")
        print("  3. 얻은 토큰을 .env 파일의 TELEGRAM_BOT_TOKEN에 입력")
        return False
    
    if not chat_id:
        print("\n[i] 텔레그램 채팅 ID를 설정하려면 .env 파일의 TELEGRAM_CHAT_ID를 입력하세요.")
        return False
    
    # 실제 테스트
    print("\n[*] 텔레그램 메시지 발송 테스트...")
    notifier = TelegramNotifier()
    
    if not notifier.is_configured():
        print("[!] 텔레그램이 설정되지 않았습니다.")
        return False

    success = notifier.send_message("🔔 <b>테스트 메시지</b>\n\n콘텐츠 크롤러 텔레그램 설정이 정상작동합니다!")
    if success:
        print("[+] 텔레그램 설정 성공!")
    else:
        print("[!] 텔레그램 발송 실패 - 토큰이나 채팅 ID를 확인하세요")

    return success


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="콘텐츠 크롤러 v2.2 - 다중 플랫폼 지원")
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="아카이브에 저장하지 않고 메타데이터만 저장",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=None,
        help="최대 크롤링 포스트 수 (테스트용)",
    )
    parser.add_argument(
        "--use-sitemap",
        action="store_true",
        help="티스토리 블로그의 sitemap.xml에 있는 링크를 추가로 수집합니다.",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="스케줄러 모드로 실행 (일일 다이제스트)",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="텔레그램 설정을 테스트합니다",
    )
    parser.add_argument(
        "--no-error-report",
        action="store_true",
        help="에러가 발생해도 텔레그램으로 보고하지 않습니다",
    )
    parser.add_argument(
        "--naver-blog",
        action="append",
        help="추가로 수동 크롤링할 네이버 블로그 ID를 지정 (여러 개 반복 가능)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print(f"콘텐츠 크롤러 v{CRAWLER_VERSION}")
    print("=" * 60)
    print()

    # 텔레그램 테스트 모드
    if args.test_telegram:
        test_telegram_config()
        return

    # 설정 로드
    config = load_config("config.json")
    if not config:
        return
    
    archive_root = config.get("archive_root", "./archive")
    raw_dir = config.get("raw_directory", ".raw")
    archive_mgr = ArchiveManager(archive_root)  # 아카이브 매니저 인스턴스 생성

    # 스케줄러 모드
    if args.schedule:
        notifier = TelegramNotifier()
        scheduler_config = config.get("scheduler", {})
        scheduler = DailyDigestScheduler(scheduler_config, notifier)
        scheduler.start()
        return

    # 크롤링 모드
    print("[*] 크롤링 시작...")
    all_posts: List[Dict] = []
    youtube_videos: List[Dict] = []
    tistory_posts: List[Dict] = []
    naver_posts: List[Dict] = []
    github_posts: List[Dict] = []
    
    # 에러 수집 시작
    error_collector = ErrorCollector()
    
    with error_collector:
        # 각 플랫폼별 크롤링
        if not args.no_archive:
            youtube_videos = crawl_youtube(config, args, archive_mgr)
            all_posts.extend(youtube_videos)

            naver_posts = crawl_naver_blog(config, args, archive_mgr)
            all_posts.extend(naver_posts)

            tistory_posts = crawl_tistory_blogs(config, args, archive_mgr)
            all_posts.extend(tistory_posts)

            github_posts = crawl_github_pages(config, args, archive_mgr)
            all_posts.extend(github_posts)

    new_archived_count_youtube = get_number_of_new_archived(youtube_videos)
    new_archived_count_naver = get_number_of_new_archived(naver_posts)
    new_archived_count_tistory = get_number_of_new_archived(tistory_posts)
    new_archived_count_github = get_number_of_new_archived(github_posts)
    new_archived_total = new_archived_count_youtube + new_archived_count_naver + new_archived_count_tistory + new_archived_count_github

    print("\n" + "=" * 60)
    print(f"[+] 모든 작업 완료! (총 {len(all_posts)}개 발견 / {new_archived_total}개 추가)")
    print(f"  - YouTube 영상: {len(youtube_videos)}개 발견 / {new_archived_count_youtube}개 추가")
    print(f"  - 네이버 블로그 포스트: {len(naver_posts)}개 발견 / {new_archived_count_naver}개 추가")
    print(f"  - 티스토리 블로그 포스트: {len(tistory_posts)}개 발견 / {new_archived_count_tistory}개 추가")
    print(f"  - GitHub Pages 포스트: {len(github_posts)}개 발견 / {new_archived_count_github}개 추가")

    if error_collector.has_errors():
        print(f"[!] 에러 {len(error_collector.errors)}개 발생")
    print("=" * 60)
    
    # 에러가 있으면 텔레그램으로 전송 (옵션으로 비활성화 가능)
    if error_collector.has_errors() and not args.no_error_report:
        notifier = TelegramNotifier()
        if notifier.is_configured():
            notifier.send_errors(error_collector.errors)
        else:
            print("[!] 텔레그램이 설정되지 않아 에러를 전송할 수 없습니다.")
    elif error_collector.has_errors() and args.no_error_report:
        print("[i] 에러 리포팅이 비활성화되어 있으므로 텔레그램으로 전송하지 않습니다.")


if __name__ == "__main__":
    main()
