# src/sources/pubmed.py
from __future__ import annotations
import requests, datetime as dt
from dataclasses import dataclass
from typing import List

UA = {"User-Agent": "Mozilla/5.0 (compatible; BioWatchdog/0.1)"}
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

@dataclass
class Item:
    url: str
    title: str
    published_at: str | None
    source: str
    text: str
    source_tag: str = "pubmed"
    country: str | None = None

def _esearch(term: str, retmax: int = 20) -> List[str]:
    r = requests.get(f"{EUTILS}/esearch.fcgi",
                     params={"db":"pubmed","term":term,"retmax":retmax,"sort":"date","retmode":"json"},
                     headers=UA, timeout=20)
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])

def _esummary(pmids: List[str]) -> List[dict]:
    if not pmids: return []
    r = requests.get(f"{EUTILS}/esummary.fcgi",
                     params={"db":"pubmed","id":",".join(pmids),"retmode":"json"},
                     headers=UA, timeout=20)
    r.raise_for_status()
    res = r.json().get("result", {})
    return [res[str(p)] for p in pmids if str(p) in res]

def search_pubmed(term: str, retmax: int = 20) -> List[Item]:
    ids = _esearch(term, retmax=retmax)
    out: List[Item] = []
    for rec in _esummary(ids):
        title = rec.get("title") or ""
        # fecha preferida (PubDate o EPubDate)
        pubdate = rec.get("pubdate") or rec.get("epubdate")
        ts = None
        if pubdate:
            # intentamos normalizar YYYY-MM-DD
            try:
                ts = dt.datetime.strptime(pubdate.split(";")[0].split(" ")[0], "%Y").strftime("%Y-%m-%d")
            except Exception:
                ts = None
        pmid = rec.get("uid") or rec.get("articleids", [{}])[0].get("value")
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        journal = rec.get("fulljournalname") or rec.get("source") or "PubMed"
        out.append(Item(
            url=url, title=title, published_at=ts, source=journal, text=""  # texto vacío; luego lo completa trafilatura
        ))
    return out
