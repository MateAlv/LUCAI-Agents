# src/summarize/summary.py
from __future__ import annotations
import requests, textwrap

def summarize(text: str, title: str = "", model: str = "llama3:8b", max_chars: int = 1000) -> str:
    if not text:
        return "- (sin contenido extraíble)"
    chunk = text[: max_chars]
    prompt = f"Resumí en 3 bullets informativos, sin marketing, con hechos/fechas/montos si aparecen.\nTítulo: {title}\n\nTexto:\n{chunk}"
    try:
        r = requests.post("http://localhost:11434/api/generate",
                          json={"model": model, "prompt": prompt, "stream": False}, timeout=25)
        if r.ok and r.json().get("response"):
            return textwrap.dedent(r.json()["response"]).strip()
    except Exception:
        pass
    # Fallback extractivo muy simple
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    bullets = []
    for ln in lines[:3]:
        bullets.append(f"- {ln[:220]}")
    return "\n".join(bullets) if bullets else "- (sin resumen)"
