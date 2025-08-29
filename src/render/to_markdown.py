# src/render/to_markdown.py
from __future__ import annotations
from typing import Dict, List

def render_md_by_sections(items_by_sec):
    lines = []
    lines.append("# Bio Watchdog — Newsletter\n")
    for sec in ("tech","finance","academic"):
        items = items_by_sec.get(sec, [])
        if not items: 
            continue
        title = {"tech":"Tecnología (biotech)", "finance":"Finanzas (rondas/grants)", "academic":"Académico/Clinical"}[sec]
        lines.append(f"## {title} — {len(items)} items\n")
        for it in items:
            flags = []
            if it.get("is_ar"): flags.append("AR")
            if it.get("is_fin"): flags.append("FIN")
            if it.get("is_watch"): flags.append("WATCH")
            badge = f" [{'|'.join(flags)}]" if flags else ""
            date = it.get("published_at") or ""
            lines.append(f"### {it.get('title','(sin título)')}{badge}")
            lines.append(f"*{date}* — {it.get('url','')}")
            if it.get("summary"): lines.append(it["summary"])
            lines.append("")
    return "\n".join(lines)
