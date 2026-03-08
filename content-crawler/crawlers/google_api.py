import requests
from typing import Dict, List, Optional


def google_search(search_term: str, api_key: str, cse_id: str, **kwargs) -> Optional[Dict]:
    """Google Custom Search API를 사용하여 검색 결과를 가져옵니다."""
    service_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": search_term,
        "key": api_key,
        "cx": cse_id,
    }
    params.update(kwargs)

    try:
        response = requests.get(service_url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[!] Google Search API 오류: {e}")
        return None


def search_naver_blog_posts(
    blog_id: str,
    api_key: str,
    cse_id: str,
    max_results: int = 100,
) -> List[Dict]:
    """Google 검색으로 특정 네이버 블로그 포스트 URL을 수집합니다."""
    if not blog_id or not api_key or not cse_id:
        return []

    query = f'site:blog.naver.com/{blog_id}'
    collected: List[Dict] = []
    start = 1

    while len(collected) < max_results and start <= 91:
        payload = google_search(
            query,
            api_key,
            cse_id,
            num=min(10, max_results - len(collected)),
            start=start,
        )
        if not payload:
            break

        items = payload.get("items", [])
        if not items:
            break

        for item in items:
            link = (item.get("link") or "").strip()
            if f"blog.naver.com/{blog_id}" not in link:
                continue

            collected.append(
                {
                    "title": item.get("title", "제목 없음"),
                    "published": "",
                    "link": link,
                    "summary": item.get("snippet", ""),
                }
            )

        start += 10

    return collected