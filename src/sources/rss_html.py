# src/sources/rss_html.py
from __future__ import annotations
import time
import feedparser
import requests
from dataclasses import dataclass
from typing import List, Optional
import trafilatura

UA = {"User-Agent":"Mozilla/5.0 (compatible; BioWatchdog/0.1)"}

@dataclass
class Item:
    url: str
    title: str
    published_at: Optional[str]
    source: str
    text: str

def fetch_rss(url: str, max_items: int = 20) -> List[Item]:
    feed = feedparser.parse(url)
    out: List[Item] = []
    for e in feed.entries[:max_items]:
        link = getattr(e, "link", None) or getattr(e, "id", None)
        if not link:
            continue
        title = getattr(e, "title", "") or link
        # published_parsed puede no estar
        ts = None
        if getattr(e, "published_parsed", None):
            ts = time.strftime("%Y-%m-%d", e.published_parsed)
        # descargar HTML y limpiar (best-effort)
        try:
            html = requests.get(link, headers=UA, timeout=20).text
            text = trafilatura.extract(html, include_formatting=False, favor_recall=True) or ""
        except Exception:
            text = ""
        out.append(Item(url=link, title=title, published_at=ts, source=url, text=text))
    return out
