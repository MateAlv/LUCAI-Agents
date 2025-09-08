# src/run.py
from __future__ import annotations

# --- SSL helpers (Windows) ---
try:
    import truststore
    truststore.inject_into_ssl()   # usa la trust store nativa de Windows
except Exception:
    pass

try:
    import certifi_win32  # usa el store de certificados de Windows
except Exception:
    pass

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

import argparse
import sys
import datetime as dt
from pathlib import Path
from typing import List, Dict

import requests
import trafilatura
import yaml

from sources.rss_html import fetch_rss
from sources.html_list import fetch_list as fetch_html_list
from sources.gdelt import search_gdelt
from sources.arxiv import search_arxiv
from sources.clinicaltrials import search_clinicaltrials_arg
from sources.pubmed import search_pubmed

from enrich.flags import is_argentina, has_funding
from enrich.scope import on_scope
from summarize.summary import summarize_extractive
from categorize import classify
from render.to_markdown import render_md_by_sections

from rank.score import compute_scores, mmr_select
from critic.auto_critic import run as critic_run

# LLM summarizer (opcional, via llama.cpp server)
try:
    from summarize.llm_summarizer import summarize_llm
except Exception:
    summarize_llm = None

UA = {"User-Agent": "Mozilla/5.0 (compatible; BioWatchdog/0.1)"}


def fetch_html_text(url: str) -> str:
    """Descarga HTML y extrae texto limpio (best-effort)."""
    try:
        html = requests.get(url, headers=UA, timeout=20).text
        return trafilatura.extract(html, include_formatting=False, favor_recall=True) or ""
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser(description="Bio Watchdog - Ingestion + Render")
    ap.add_argument("--config", default="config/cliente.yaml", help="Ruta al YAML de configuración")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, "r", encoding="utf-8"))
    freshness_days = int(cfg.get("freshness_days", 7))
    max_items = int(cfg.get("max_items", 20))

    items: List[Dict] = []

    # 1) RSS
    for rss in (cfg.get("sources", {}).get("rss", []) or []):
        for it in fetch_rss(rss, max_items=max_items // 2 or 10):
            items.append(
                {
                    "url": it.url,
                    "title": it.title,
                    "published_at": it.published_at,
                    "source": it.source,
                    "text": it.text,
                    "source_tag": "rss",
                }
            )

    # 1.b) HTML pages (listas sin RSS)
    for page in (cfg.get("sources", {}).get("html_pages", []) or []):
        page_url = page.get("page_url")
        link_selector = page.get("link_selector")
        limit = page.get("limit", 6)
        verify_ssl = page.get("verify_ssl", True)
        verify_cert_path = page.get("verify_cert_path")
        min_text_chars = page.get("min_text_chars", 300)

        for it in fetch_html_list(page_url,
                                  link_selector,
                                  limit=limit,
                                  verify_ssl=verify_ssl,
                                  verify_cert_path=verify_cert_path,
                                  min_text_chars=min_text_chars):
            items.append({
                "url": it.url,
                "title": it.title,
                "published_at": it.published_at,
                "source": it.source,
                "text": it.text,
                "source_tag": "html",
            })

    # 2) PubMed
    pubmed_cfg = (cfg.get("sources", {}).get("apis", {}).get("pubmed") or {})
    if pubmed_cfg.get("enabled"):
        term = pubmed_cfg.get("query") or "biotechnology OR synthetic biology OR CRISPR OR bioinformatics"
        retmax = int(pubmed_cfg.get("retmax", 20))
        for it in search_pubmed(term, retmax=retmax):
            items.append({
                "url": it.url,
                "title": it.title,
                "published_at": it.published_at,
                "source": it.source,
                "text": it.text,
                "source_tag": it.source_tag
            })

    # 2.b) arXiv
    if cfg.get("sources", {}).get("apis", {}).get("arxiv"):
        arxiv_q = 'cat:q-bio OR CRISPR OR "synthetic biology"'
        for it in search_arxiv(arxiv_q, days=freshness_days, max_results=max_items//2 or 10):
            items.append({
                "url": it.url,
                "title": it.title,
                "published_at": it.published_at,
                "source": it.source,          # "arxiv"
                "text": it.text,
                "source_tag": it.source_tag,  # "arxiv"
            })

    # 2.c) ClinicalTrials.gov (Argentina)
    if cfg.get("sources", {}).get("apis", {}).get("clinicaltrials"):
        for it in search_clinicaltrials_arg(days=freshness_days, max_records=max_items):
            items.append({
                "url": it.url,
                "title": it.title,
                "published_at": it.published_at,
                "source": it.source,             # "clinicaltrials"
                "text": it.text,
                "country_hint": it.country,      # "AR"
                "source_tag": it.source_tag,     # "clinicaltrials"
            })

    # 3) Dedupe por URL
    seen = set()
    deduped: List[Dict] = []
    for it in items:
        key = (it.get("url") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    items = deduped

    # 4) Completar texto faltante para los primeros N (para no demorar)
    for it in items[: max_items]:
        if not it.get("text"):
            it["text"] = fetch_html_text(it["url"])

    # 4.b) Filtro de calidad global con whitelist de fuentes cortas
    qcfg = cfg.get("quality", {}) or {}
    min_chars_global = int(qcfg.get("min_text_chars", 0) or 0)
    allow_short = set((qcfg.get("allow_short_sources") or []))
    if min_chars_global > 0:
        before = len(items)
        kept = []
        for it in items:
            tag = it.get("source_tag") or it.get("source") or ""
            if len(it.get("text","")) >= min_chars_global or tag in allow_short:
                kept.append(it)
        items = kept
        print(f"Filtro calidad: {before} -> {len(items)} ítems (>= {min_chars_global} chars o tag en {list(allow_short)})")

    # 5) Flags AR/FIN + resumen (LLM si está habilitado)
    llmcfg = cfg.get("llm_summary", {}) or {}
    print("llm_summary cfg:", cfg.get("llm_summary", {}))
    use_llm = bool(llmcfg.get("enabled")) and summarize_llm is not None
    min_llm_chars = int(llmcfg.get("min_chars", 400))
    print("Resumen LLM:", "ON" if use_llm else "OFF (extractivo)")

    for it in items:
        blob = (it.get("text") or "") + " " + (it.get("title") or "")
        it["is_ar"] = is_argentina(blob, it.get("url", ""), it.get("country_hint"))
        it["is_fin"] = has_funding(it.get("text",""), it.get("title",""))
        try:
            text = it.get("text","")
            if use_llm and len(text) >= min_llm_chars:
                it["summary"] = summarize_llm(text, it.get("title",""), llmcfg)
            else:
                it["summary"] = summarize_extractive(text, title=it.get("title",""))
        except Exception as e:
            logging.warning(f"LLM summary falló ({e}), uso extractivo.")
            it["summary"] = summarize_extractive(it.get("text",""), title=it.get("title",""))

    # 5.b) Filtro de scope (biotech)
    before = len(items)
    items = [it for it in items if on_scope((it.get("title","")+" "+it.get("text","")), mode="soft")]
    print(f"Filtro scope biotech: {before} -> {len(items)} ítems")

    # 6) Scoring inicial
    items, emb_items = compute_scores(cfg, items)

    # 6.a) Crítico (poda/demote)
    before = len(items)
    items, dropped = critic_run(items, cfg)
    print(f"Crítico: {before} -> {len(items)} kept (dropped {len(dropped)})")
    from collections import Counter
    print("Motivos drop:", Counter([d.get("drop_reason") for d in dropped]))

    # 6.b) Re-scoring post-crítico
    items, emb_items = compute_scores(cfg, items)
    print("Embeddings:", "ON" if emb_items is not None else "OFF (fallback keywords)")

    # 6.c) Clasificación por sección
    by_sec = {"tech": [], "finance": [], "academic": []}
    for it in items:
        sec = classify(it, cfg)
        by_sec.setdefault(sec, []).append(it)

    # 6.d) MMR / top-K por sección
    import numpy as np
    max_k = int(cfg.get("max_items_per_section", cfg.get("max_items", 20)))

    emb_map = None
    if emb_items is not None:
        emb_map = {id(it): emb_items[idx] for idx, it in enumerate(items)}

    final_by_sec = {}
    for sec, sec_items in by_sec.items():
        # ordenar por score desc
        sec_sorted = sorted(sec_items, key=lambda x: x.get("score", 0.0), reverse=True)

        if emb_map is not None and len(sec_sorted) > 0:
            # construir matriz en el mismo orden que sec_sorted
            emb_sec = []
            ok = True
            for it in sec_sorted:
                v = emb_map.get(id(it))
                if v is None:
                    ok = False
                    break
                emb_sec.append(v)
            if ok and emb_sec:
                emb_sec = np.stack(emb_sec).astype("float32")
                sec_final = mmr_select(sec_sorted, emb_sec, k=max_k, lam=0.5)
            else:
                sec_final = sec_sorted[:max_k]
        else:
            sec_final = sec_sorted[:max_k]

        final_by_sec[sec] = sec_final

    # 7) Render a Markdown
    outdir = Path("output")
    outdir.mkdir(exist_ok=True)
    outname = outdir / f"newsletter_{dt.datetime.now().strftime('%Y%m%d')}.md"
    md = render_md_by_sections(final_by_sec)
    outname.write_text(md, encoding="utf-8")
    print(f"OK -> {outname}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
