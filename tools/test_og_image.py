import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'}
url = 'https://m.blog.naver.com/sadneye/221318133492'
print(f'테스트 URL: {url}')
try:
    r = requests.get(url, headers=headers, timeout=10)
    print(f'상태: {r.status_code}')
    soup = BeautifulSoup(r.text, 'html.parser')
    og_img = soup.find('meta', attrs={'property': 'og:image'})
    if og_img:
        img_url = og_img.get('content')
        print(f'og:image 찾음: {repr(img_url[:100])}')
    else:
        print('og:image를 찾을 수 없음')
        # HTML head 확인
        head = soup.find('head')
        if head:
            metas = head.find_all('meta')
            print(f'meta 태그: {len(metas)}개')
            for m in metas[:10]:
                prop = m.get('property', m.get('name', '?'))
                cont = m.get('content', '')[:60]
                print(f'  {prop}: {cont}...')
except Exception as e:
    print(f'오류: {e}')
