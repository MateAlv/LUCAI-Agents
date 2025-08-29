# src/critic/auto_critic.py
from __future__ import annotations
import re
from urllib.parse import urlparse
from typing import Dict, List, Tuple

PAYWALL_PATTERNS = [
    r"sign up to read", r"subscribe to read", r"this content is for subscribers",
    r"regístrate para leer", r"suscribite", r"suscripción requerida"
]
SOCIAL_HOSTS = {"twitter.com","x.com","facebook.com","linkedin.com","instagram.com","youtube.com","wa.me"}

def _host(u: str) -> str:
    try:
        return (urlparse(u).hostname or "").lower().lstrip("www.")
    except Exception:
        return ""

def _is_social(u: str) -> bool:
    h = _host(u)
    return any(h.endswith(s) for s in SOCIAL_HOSTS)

def _looks_paywall(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t) for p in PAYWALL_PATTERNS)

def _is_anmat_category(u: str, text: str) -> bool:
    # Evitar páginas de categoría de ANMAT (Medicamentos/Alimentos/etc.) sin detalle
    parsed = urlparse(u)
    if "argentina.gob.ar" not in (parsed.hostname or ""):
        return False
    path = (parsed.path or "").strip("/").split("/")
    # ej: /anmat/alertas/medicamentos  (3 segmentos) => suele ser índice
    return len(path) <= 3 and "alertas" in path

def _norm_title(t: str) -> str:
    t = (t or "").lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def run(items: List[Dict], cfg: Dict) -> Tuple[List[Dict], List[Dict]]:
    ccfg = cfg.get("critic", {}) or {}
    min_score = float(ccfg.get("min_score_drop", 0.35))
    drop_paywall_mode = ccfg.get("drop_paywall", True)  # True|False|"demote"
    paywall_penalty = float(ccfg.get("paywall_penalty", 0.1))
    drop_social = bool(ccfg.get("drop_social", True))
    drop_short_if_not_whitelisted = bool(ccfg.get("drop_short_if_not_whitelisted", True))

    qcfg = cfg.get("quality", {}) or {}
    min_chars = int(qcfg.get("min_text_chars", 0) or 0)
    allow_short = set((qcfg.get("allow_short_sources") or []))

    kept, dropped = [], []
    seen_titles = set()

    for it in items:
        url = it.get("url","")
        title = it.get("title","") or url
        text  = it.get("text","") or ""
        tag   = (it.get("source_tag") or it.get("source") or "").lower()
        score = float(it.get("score", 0.0))

        # 1) Duplicados (título normalizado)
        nt = _norm_title(title)
        if nt and nt in seen_titles:
            it["drop_reason"] = "duplicate_title"; dropped.append(it); continue
        seen_titles.add(nt)

        # 2) Social directo
        if drop_social and _is_social(url):
            it["drop_reason"] = "social_link"; dropped.append(it); continue

        # 3) Paywall: solo aplica si el texto útil es corto (< 800)
        looks_pw = _looks_paywall(text) or _looks_paywall(it.get("summary",""))
        if looks_pw and len(text) < 800:
            if drop_paywall_mode is True:
                it["drop_reason"] = "paywall_teaser"; dropped.append(it); continue
            elif str(drop_paywall_mode).lower() == "demote":
                score = max(0.0, score - paywall_penalty)
                it["score"] = score
                it["paywall_flag"] = True  # por si querés mostrarlo en el render

        # 4) Largo mínimo (salvo whitelist de fuentes cortas)
        if drop_short_if_not_whitelisted and min_chars > 0 and tag not in allow_short:
            if len(text) < min_chars:
                it["drop_reason"] = "too_short"; dropped.append(it); continue

        # 5) Umbral de score
        if score < min_score:
            it["drop_reason"] = "low_score"; dropped.append(it); continue

        kept.append(it)

    return kept, dropped
