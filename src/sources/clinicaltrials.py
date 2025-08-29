# src/sources/clinicaltrials.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import time
import requests
import dateparser

@dataclass
class Item:
    url: str
    title: str
    published_at: Optional[str]
    source: str
    text: str
    source_tag: str = "clinicaltrials"
    country: Optional[str] = None

UA = {"User-Agent":"Mozilla/5.0 (compatible; BioWatchdog/0.2)"}
CT_API = "https://clinicaltrials.gov/api/query/study_fields"

# Campos comunes y livianos
FIELDS = [
    "NCTId","BriefTitle","OverallStatus","StartDate","LastUpdatePostDate",
    "Phase","Condition","LocationCountry","LeadSponsorName","StudyType"
]

def _to_iso(d: str|None) -> Optional[str]:
    if not d: return None
    dt = dateparser.parse(d)
    if not dt: return None
    return dt.strftime("%Y-%m-%d")

def search_clinicaltrials_arg(days: int = 30, max_records: int = 50) -> List[Item]:
    """
    Usa la API 'study_fields' y filtra LocationCountry=Argentina.
    Luego corta por LastUpdatePostDate/StartDate según 'days'.
    """
    # Expresión: estudios con sitios en Argentina
    expr = "AREA[LocationCountry] Argentina"
    params = {
        "expr": expr,
        "fields": ",".join(FIELDS),
        "min_rnk": "1",
        "max_rnk": str(max_records),
        "fmt": "json",
    }
    try:
        r = requests.get(CT_API, params=params, headers=UA, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    studies = (data.get("StudyFieldsResponse", {}) or {}).get("StudyFields", []) or []
    cutoff = time.time() - days * 86400

    out: List[Item] = []
    for s in studies:
        # Campos vienen como listas
        def pick(name: str) -> str:
            v = s.get(name) or []
            return (v[0] if v else "").strip()

        nct = pick("NCTId")
        if not nct:
            continue

        title = pick("BriefTitle") or nct
        status = pick("OverallStatus")
        phase = pick("Phase")
        cond  = pick("Condition")
        sponsor = pick("LeadSponsorName")
        start = pick("StartDate")
        upd   = pick("LastUpdatePostDate")
        locs  = ", ".join(s.get("LocationCountry") or [])

        # fecha: preferimos la última actualización
        iso = _to_iso(upd) or _to_iso(start)
        ts_ok = True
        if iso:
            try:
                import datetime as dt
                dt_item = dt.datetime.strptime(iso, "%Y-%m-%d")
                ts_ok = (time.time() - dt_item.timestamp()) <= days * 86400
            except Exception:
                ts_ok = True

        if not ts_ok:
            continue

        # Texto “sintético” para alimentar el resumen (sin PDF/HTML)
        blob = []
        if status:  blob.append(f"Estado: {status}.")
        if phase:   blob.append(f"Fase: {phase}.")
        if cond:    blob.append(f"Condición: {cond}.")
        if sponsor: blob.append(f"Patrocinador: {sponsor}.")
        if locs:    blob.append(f"Países: {locs}.")
        text = " ".join(blob) or title

        url = f"https://clinicaltrials.gov/study/{nct}"
        out.append(Item(
            url=url, title=title, published_at=iso, source="clinicaltrials",
            text=text, source_tag="clinicaltrials", country="AR"
        ))
    return out
