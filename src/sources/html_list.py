# src/sources/html_list.py
from __future__ import annotations

try:
    import truststore
    truststore.inject_into_ssl()   # usa la trust store nativa de Windows
except Exception:
    pass

try:
    import certifi_win32
except Exception:
    pass


from dataclasses import dataclass
from typing import List, Optional, Iterable
from urllib.parse import urljoin, urlparse
import logging, re

import requests
from bs4 import BeautifulSoup
import trafilatura

UA = {"User-Agent":"Mozilla/5.0 (compatible; BioWatchdog/0.2)"}

DATE_RE = re.compile(
    r"\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+\d{4}\b",
    re.IGNORECASE
)

SOCIAL_HOSTS = {"twitter.com","facebook.com","linkedin.com","instagram.com","youtube.com","wa.me"}

@dataclass
class Item:
    url: str
    title: str
    published_at: Optional[str]
    source: str
    text: str

def _norm_host(u: str) -> str:
    try:
        return urlparse(u).hostname or ""
    except Exception:
        return ""

def _is_social(u: str) -> bool:
    h = _norm_host(u).lower()
    return any(h.endswith(s) for s in SOCIAL_HOSTS)

def _dedupe_keep_first(urls: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for u in urls:
        k = u.strip()
        if not k or k in seen: continue
        seen.add(k); out.append(k)
    return out

def _find_by_selectors(soup: BeautifulSoup, selectors: List[str]) -> List[str]:
    urls = []
    for sel in selectors:
        for a in soup.select(sel):
            href = a.get("href") or ""
            if not href: continue
            urls.append(href)
    return urls

def _fallback_links(page_url: str, soup: BeautifulSoup, limit: int) -> List[str]:
    """Plan B: tomar anchors con fecha o texto largo y evitar sociales/categorías."""
    base_host = _norm_host(page_url).lower()
    cand = []
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        if not href: continue
        full = urljoin(page_url, href)
        if _is_social(full): 
            continue
        # Mantener en el mismo dominio (evita navegación general)
        if _norm_host(full).lower() != base_host:
            continue
        txt = (a.get_text(" ", strip=True) or "")
        # Heurísticas: que el texto tenga pinta de título o contenga una fecha española
        if len(txt) >= 30 or DATE_RE.search(txt):
            cand.append(full)
    # Quitar anchors ancla (#), archivos, duplicados, y cortar
    cand = [u for u in cand if not urlparse(u).fragment]
    cand = _dedupe_keep_first(cand)
    return cand[:limit]

def fetch_list(page_url: str,
               link_selector: str | List[str],
               limit: int = 10,
               base_url: Optional[str] = None,
               verify_ssl: bool = True,
               verify_cert_path: Optional[str] = None,
               min_text_chars: int = 300) -> List[Item]:
    """
    Raspa una página índice y retorna hasta 'limit' artículos:
      - Usa uno o varios selectores CSS (string o lista).
      - Si no encuentra resultados, intenta un fallback por fecha/título largo.
      - Descarta destinos con poco texto (evita categorías y "ver más").
    """
    def _verify():
        return verify_cert_path if verify_cert_path else verify_ssl

    try:
        html = requests.get(page_url, headers=UA, timeout=25, verify=_verify()).text
    except Exception as e:
        logging.warning("Error cargando %s: %s. Devuelvo [].", page_url, e)
        return []

    soup = BeautifulSoup(html, "html.parser")
    selectors = link_selector if isinstance(link_selector, list) else [link_selector]

    urls = _find_by_selectors(soup, selectors)
    if not urls:
        logging.info("No hubo matches con selectores en %s. Uso fallback heurístico.", page_url)
        urls = _fallback_links(page_url, soup, limit)

    # Normalizar y recortar
    urls = [urljoin(base_url or page_url, u) for u in urls]
    urls = _dedupe_keep_first(urls)[:limit]

    out: List[Item] = []
    for u in urls:
        if _is_social(u): 
            continue
        try:
            art_html = requests.get(u, headers=UA, timeout=25, verify=_verify()).text
            text = trafilatura.extract(art_html, include_formatting=False, favor_recall=True) or ""
        except Exception as e:
            logging.warning("Error bajando %s: %s. Skipping.", u, e)
            continue

        # Filtro de calidad para evitar categorías/listados
        if len(text) < min_text_chars:
            continue

        # Título razonable
        title = ""
        try:
            s2 = BeautifulSoup(art_html, "html.parser")
            h = s2.find(["h1","h2"])
            if h: title = h.get_text(" ", strip=True)[:180]
        except Exception:
            pass
        if not title:
            # fallback: usa el texto del link original si existe
            title = u

        out.append(Item(url=u, title=title, published_at=None, source=page_url, text=text))

    return out
