# src/rank/score.py
from __future__ import annotations
import math, time
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse

import numpy as np

# Embeddings (opcional, con fallback a keywords)
try:
    from sentence_transformers import SentenceTransformer
    _EMB_MODEL: Optional[SentenceTransformer] = SentenceTransformer("all-MiniLM-L6-v2")
except Exception:
    _EMB_MODEL = None

def _domain(host: str) -> str:
    try:
        return (host or "").lower().lstrip("www.")
    except Exception:
        return host or ""

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    num = float((a * b).sum())
    den = float(np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)
    return num / den

def _emb(texts: List[str]) -> np.ndarray:
    assert _EMB_MODEL is not None
    vecs = _EMB_MODEL.encode(texts, normalize_embeddings=True)
    return np.array(vecs, dtype="float32")

def _kw_score(text: str, keywords: List[str]) -> float:
    t = (text or "").lower()
    hits = sum(1 for k in keywords if k.lower() in t)
    return min(1.0, hits / max(3, len(keywords) / 2))

def _days_from(date_str: Optional[str]) -> float:
    if not date_str:
        return 999.0
    try:
        # formatos YYYY-MM-DD
        parts = [int(p) for p in date_str.split("-")]
        y, m, d = parts[0], parts[1], parts[2]
        ts_item = time.mktime((y, m, d, 0, 0, 0, 0, 0, -1))
        return max(0.0, (time.time() - ts_item) / 86400.0)
    except Exception:
        return 999.0

def _recency_score(days: float, half_life: float) -> float:
    # e^(-ln(2)*days/half_life)
    return math.exp(-math.log(2) * (days / max(0.1, half_life)))

def compute_scores(cfg: Dict, items: List[Dict]) -> Tuple[List[Dict], Optional[np.ndarray]]:
    """Anota cada item con 'score' y devuelve (items, embeddings opcionales)."""
    rk = cfg.get("ranking", {}) or {}
    half = float(rk.get("recency_half_life_days", 7))
    dweights = {k.lower(): float(v) for k, v in (rk.get("domain_weights", {}) or {}).items()}
    boosts = rk.get("boosts", {}) or {}
    use_emb = bool(rk.get("use_embeddings", True))

    # Query/topic vector
    topics = []
    for sec in ("tech", "finance", "academic"):
        topics += cfg.get("topics", {}).get(sec, []) or []
    topics = [t for t in topics if t]
    watch = [w.lower() for w in (cfg.get("watchlists", {}).get("companies", []) or [])]

    # Preparar embeddings si están
    text_blobs = [ (it.get("title","") + " " + (it.get("text","")[:800])) for it in items ]
    emb_items: Optional[np.ndarray] = None
    emb_query: Optional[np.ndarray] = None
    if use_emb and _EMB_MODEL is not None:
        try:
            emb_items = _emb(text_blobs)
            emb_query = _emb(["; ".join(topics)])[0:1]  # (1,dim)
        except Exception:
            emb_items, emb_query = None, None

    # Scoring
    for idx, it in enumerate(items):
        # recency
        days = _days_from(it.get("published_at"))
        s_rec = _recency_score(days, half)

        # dominio
        host = _domain(urlparse(it.get("url","")).hostname or "")
        s_dom = dweights.get(host, 1.0)

        # similitud temática
        if emb_items is not None and emb_query is not None:
            s_topic = float(_cosine(emb_items[idx], emb_query[0]))
        else:
            s_topic = _kw_score(text_blobs[idx], topics)

        # boosts por flags
        s_boost = 0.0
        if it.get("is_ar"):  s_boost += float(boosts.get("argentina", 0.0))
        if it.get("is_fin"): s_boost += float(boosts.get("funding", 0.0))

        # watchlist
        it["is_watch"] = False
        title_low = (it.get("title","") + " " + it.get("text","")).lower()
        if any(w in title_low for w in watch):
            it["is_watch"] = True
            s_boost += float(boosts.get("watchlist", 0.0))

        # mezcla final
        # pesos base: 0.6 tópico, 0.25 recency, 0.15 dominio + boosts
        score = 0.6 * s_topic + 0.25 * s_rec + 0.15 * (s_dom / 1.5) + s_boost
        it["score"] = float(score)

    return items, emb_items

def mmr_select(items: List[Dict], emb_items: Optional[np.ndarray], k: int, lam: float = 0.5) -> List[Dict]:
    """Maximal Marginal Relevance: diversidad simple. Si no hay embeddings, devuelve top-k por score."""
    if k <= 0: return []
    items_sorted = sorted(items, key=lambda x: x.get("score", 0.0), reverse=True)
    if emb_items is None or len(items_sorted) <= k:
        return items_sorted[:k]

    # Tomar embeddings en el mismo orden
    idx_map = {id(it): i for i, it in enumerate(items)}
    emb = emb_items

    selected: List[Dict] = []
    cand = items_sorted.copy()
    # seed: mejor score
    selected.append(cand.pop(0))
    while cand and len(selected) < k:
        best, best_val = None, -1e9
        for it in cand:
            i = idx_map[id(it)]
            rel = it.get("score", 0.0)
            # disimilitud: 1 - max cosine con seleccionados
            max_sim = 0.0
            for sj in selected:
                j = idx_map[id(sj)]
                sim = float((emb[i] * emb[j]).sum())  # ya normalizado
                if sim > max_sim: max_sim = sim
            val = lam * rel - (1 - lam) * max_sim
            if val > best_val:
                best, best_val = it, val
        selected.append(best)
        cand.remove(best)
    return selected
