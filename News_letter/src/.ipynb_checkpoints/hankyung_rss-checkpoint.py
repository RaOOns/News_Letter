import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional, Dict
from email.utils import parsedate_to_datetime
from datetime import datetime
import pytz

KST = pytz.timezone("Asia/Seoul")

SECTION_TO_RSS_URL: Dict[str, str] = {
    "한국 경제": "https://www.hankyung.com/feed/economy",
    "세계 경제": "https://www.hankyung.com/feed/international",
    "IT": "https://www.hankyung.com/feed/it",
}

@dataclass
class HKItem:
    section: str
    title: str
    link: str
    published_kst: Optional[datetime]

def _to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    return dt.astimezone(KST)

def _parse_pubdate(pubdate: str) -> Optional[datetime]:
    if not pubdate:
        return None
    try:
        return _to_kst(parsedate_to_datetime(pubdate))
    except Exception:
        return None

def fetch_hankyung_rss(section: str, timeout_sec: int = 10) -> List[HKItem]:
    url = SECTION_TO_RSS_URL.get(section)
    if not url:
        raise ValueError(f"Unknown section: {section}")

    r = requests.get(url, timeout=timeout_sec, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "xml")
    out: List[HKItem] = []
    for it in soup.find_all("item"):
        title = (it.title.get_text(strip=True) if it.title else "").strip()
        link = (it.link.get_text(strip=True) if it.link else "").strip()
        pub = (it.pubDate.get_text(strip=True) if it.pubDate else "").strip()
        out.append(HKItem(section=section, title=title, link=link, published_kst=_parse_pubdate(pub)))
    return out
