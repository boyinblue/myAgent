# -*- coding: utf-8 -*-
# 간단한 키워드 추출 유틸리티

import re
from collections import Counter
from typing import List

STOPWORDS = set([
    # English stopwords (간단히 일부)
    "the", "and", "for", "with", "that", "this", "from", "your", "you",
    "have", "are", "was", "were", "will", "would", "could", "should",
    "there", "their", "what", "when", "where", "which", "because",
    # Korean common words
    "그리고", "하지만", "그러나", "때문에", "입니다", "합니다", "있습니다",
])


def extract_keywords(text: str, top_n: int = 5) -> List[str]:
    """텍스트에서 상위 N개 키워드를 추출합니다.

    단순히 단어 빈도 기반이며, 길이가 3자 미만이거나 stopword는 제외합니다.
    """
    words = re.findall(r"\w+", text.lower())
    counts = Counter(words)

    # 필터링
    filtered = {
        w: c
        for w, c in counts.items()
        if len(w) >= 3 and w not in STOPWORDS and not w.isdigit()
    }
    most = Counter(filtered).most_common(top_n)
    return [w for w, _ in most]
