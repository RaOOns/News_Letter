import requests
from readability import Document
from bs4 import BeautifulSoup

def fetch_article_text(url: str, timeout_sec: int = 10) -> str:
    r = requests.get(url, timeout=timeout_sec, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()

    doc = Document(r.text)
    html = doc.summary()
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    return text.strip()
