# google_search.py
import requests
import json

def google_search(search_term, api_key, cse_id, **kwargs):
    """
    Google Custom Search API를 사용하여 검색 결과를 가져옵니다.
    """
    service_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': search_term,
        'key': api_key,
        'cx': cse_id,
    }
    params.update(kwargs)
    
    try:
        response = requests.get(service_url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

def display_results(results):
    """
    검색 결과 중 제목, 링크, 요약 내용을 출력합니다.
    """
    if not results or 'items' not in results:
        print("검색 결과가 없습니다.")
        return

    for i, item in enumerate(results['items'], 1):
        print(f"{i}. {item['title']}")
        print(f"   Link: {item['link']}")
        print(f"   Snippet: {item['snippet']}\n")

if __name__ == "__main__":
    # 할당받은 API 키와 CX ID를 입력하세요.
    # .env 파일에서 불러오도록 수정하여 사용하는 것을 권장합니다.
    API_KEY = "YOUR_GOOGLE_API_KEY"
    CSE_ID = "YOUR_CUSTOM_SEARCH_ENGINE_ID"
    
    query = "안양 마라톤 코스 추천"
    
    print(f"🔍 '{query}' 검색 중...\n")
    search_results = google_search(query, API_KEY, CSE_ID)
    
    display_results(search_results)