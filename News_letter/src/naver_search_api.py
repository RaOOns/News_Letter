import re
import requests
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse

NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"

def _strip_html_tags(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&quot;", '"').replace("&amp;", "&")
    return s.strip()

def _host(url: str) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower().replace("www.", "")

def parse_naver_pubdate_to_kst(pub_date: str) -> Optional[datetime]:
    if not pub_date:
        return None
    try:
        return parsedate_to_datetime(pub_date)  # pubDate에 +0900 포함
    except Exception:
        return None

@dataclass
class NaverNewsItem:
    title: str
    link: str
    originallink: str
    description: str
    pubdate_kst: Optional[datetime]

    @property
    def original_host(self) -> str:
        return _host(self.originallink or self.link)

    @property
    def is_original_hankyung(self) -> bool:
        return "hankyung.com" in self.original_host

class NaverNewsSearchAPI:
    def __init__(self, client_id: str, client_secret: str, timeout_sec: int = 10):
        if not client_id or not client_secret:
            raise ValueError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET is missing.")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout_sec = timeout_sec

    def search_news(self, query: str, display: int, sort: str) -> List[NaverNewsItem]:
        # display는 문서상 최대 100 :contentReference[oaicite:3]{index=3}
        display = max(1, min(int(display), 100))

        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        params = {
            "query": query,
            "display": display,
            "start": 1,
            "sort": sort,  # sim / date
        }

    def search_sim_then_date(self, query: str, display: int = 30) -> Tuple[List[NaverNewsItem], str]:
        # 1) sim 우선
        items = self.search_news(query=query, display=display, sort="sim")
        return items, "sim"

    def search_date(self, query: str, display: int = 30) -> List[NaverNewsItem]:
        return self.search_news(query=query, display=display, sort="date")

    def search_sim_then_date(self, query: str, display: int = 100) -> Tuple[List[NaverNewsItem], str]:
        """
        run.py 호환용:
        - sim으로 먼저 호출
        - 여기서는 '필터링 부족' 판단을 run.py가 하므로, 여기서는 sim 결과만 반환
        - 반드시 (List, used_sort) 반환
        """
        items = self.search_news(query=query, display=display, sort="sim")
        return (items or []), "sim"

    def search_date(self, query: str, display: int = 100) -> List[NaverNewsItem]:
        """
        run.py fallback용:
        - date 정렬 결과 반환
        - 반드시 List 반환
        """
        items = self.search_news(query=query, display=display, sort="date")
        return items or []

def is_naver_news_link(item: NaverNewsItem) -> bool:
    # link가 네이버뉴스 URL이 아니면 제외하는 기준 (필요시 더 넓혀도 됨)
    lk = (item.link or "")
    return ("n.news.naver.com" in lk) or ("news.naver.com" in lk) or ("openapi.naver.com/l" in lk)