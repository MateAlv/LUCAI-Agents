# src/sources/arxiv.py
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote_plus

import feedparser

@dataclass
class Item:
    url: str
    title: str
    published_at: Optional[str]
    source: str
    text: str
    source_tag: str = "arxiv"

ARXIV_API = "http://export.arxiv.org/api/query"

def search_arxiv(query: str, days: int = 7, max_results: int = 20) -> List[Item]:
    # arXiv ordena por submittedDate descendente
    q = quote_plus(query)
    url = f"{ARXIV_API}?search_query={q}&sortBy=submittedDate&sortOrder=descending&start=0&max_results={max_results}"
    feed = feedparser.parse(url)
    cutoff = time.time() - days * 86400
    out: List[Item] = []
    for e in feed.entries:
        link = getattr(e, "link", "") or getattr(e, "id", "")
        title = getattr(e, "title", "") or link
        summ = getattr(e, "summary", "") or ""
        # published_parsed puede faltar
        ts = None
        if getattr(e, "published_parsed", None):
            ts_struct = e.published_parsed
            ts_epoch = time.mktime(ts_struct)
            if ts_epoch < cutoff:
                continue
            ts = time.strftime("%Y-%m-%d", ts_struct)
        out.append(Item(
            url=link, title=title, published_at=ts, source="arxiv", text=summ, source_tag="arxiv"
        ))
    return out
