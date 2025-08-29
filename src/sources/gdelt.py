# src/sources/gdelt.py
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
from typing import List, Optional
import requests
import logging

UA = {"User-Agent":"Mozilla/5.0 (compatible; BioWatchdog/0.1)"}
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

@dataclass
class Item:
    url: str
    title: str
    published_at: Optional[str]
    source: str
    text: str
    country: Optional[str]

def search_gdelt(query: str, days: int = 7, country: Optional[str] = None, maxrecords: int = 30) -> List[Item]:
    # Usamos timespan + sort; si querés, podés alternar con startdatetime
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "JSON",
        "timespan": f"{days}d",
        "sort": "DateDesc",
        "maxrecords": str(maxrecords),
    }
    if country:
        params["sourcecountry"] = country  # e.g. "AR"

    try:
        r = requests.get(GDELT_DOC_API, params=params, headers=UA, timeout=30)
        ct = (r.headers.get("Content-Type") or "").lower()
        if not r.ok or "json" not in ct:
            logging.warning("GDELT devolvió estado=%s content-type=%s. Devuelvo [].",
                            r.status_code, ct)
            # Opcional: logging.debug("GDELT body: %s", r.text[:500])
            return []
        data = r.json()
    except Exception as e:
        logging.exception("Fallo consultando GDELT: %s", e)
        return []

    arts = data.get("articles", []) or []
    out: List[Item] = []
    for a in arts:
        out.append(Item(
            url=a.get("url",""),
            title=a.get("title",""),
            published_at=(a.get("seendate","") or "")[:10] or None,
            source="gdelt",
            text="",  # extraeremos luego si hace falta
            country=a.get("sourcecountry")
        ))
    return out
