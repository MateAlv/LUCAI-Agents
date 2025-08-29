# src/categorize.py
from __future__ import annotations
from typing import Dict, List

def classify(item: Dict, cfg: Dict) -> str:
    title = (item.get("title") or "").lower()
    text  = (item.get("text")  or "").lower()

    finance_kw = [k.lower() for k in cfg.get("topics", {}).get("finance", [])]
    academic_kw = [k.lower() for k in cfg.get("topics", {}).get("academic", [])]

    if item.get("is_fin"):
        return "finance"
    if any(k in title or k in text for k in academic_kw):
        return "academic"
    return "tech"
