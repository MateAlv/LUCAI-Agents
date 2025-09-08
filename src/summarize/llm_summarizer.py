# src/summarize/llm_summarizer.py
from __future__ import annotations
from openai import OpenAI
import textwrap

def _chunk(text: str, chunk_chars: int = 2000):
    text = text.strip()
    for i in range(0, len(text), chunk_chars):
        yield text[i:i+chunk_chars]

def _client(cfg):
    return OpenAI(base_url=cfg.get("base_url"), api_key=cfg.get("api_key", "none"))

SYS_ES = "Sos un analista biotech. Resumí con precisión factual. Sin opiniones."
USR_TMPL_ES = """Resumí el siguiente texto en {bullets} bullets concisos (máx 1 línea c/u), en español rioplatense.
Incluí empresas, montos, fase clínica o institución si aparecen. Sin emojis ni links.

TÍTULO: {title}

TEXTO:
{body}
"""

def summarize_llm(text: str, title: str, cfg: dict) -> str:
    if not text:
        return ""
    bullets = int(cfg.get("bullets", 4))
    max_tokens = int(cfg.get("max_tokens", 256))
    temp = float(cfg.get("temperature", 0.2))
    chunk_chars = int(cfg.get("chunk_chars", 2000))
    model = cfg.get("model", "local")
    lang = cfg.get("lang", "es")

    sys_msg = SYS_ES if lang.startswith("es") else "You are a precise biotech analyst. Summarize factually."
    usr_tmpl = USR_TMPL_ES if lang.startswith("es") else (
        "Summarize the text into {bullets} concise one-line bullets in English. Include companies, amounts, clinical phase or institutions if present. No emojis or links.\n\nTITLE: {title}\n\nTEXT:\n{body}\n"
    )

    cli = _client(cfg)
    chunks = list(_chunk(text, chunk_chars))

    # Map step: sumarizar cada chunk (si hay varios)
    chunk_summaries = []
    for body in chunks:
        prompt = usr_tmpl.format(bullets=bullets, title=title or "", body=body)
        resp = cli.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":sys_msg},{"role":"user","content":prompt}],
            temperature=temp,
            max_tokens=max_tokens,
        )
        chunk_summaries.append(resp.choices[0].message.content.strip())

    # Reduce step: combinar a un único resumen
    if len(chunk_summaries) == 1:
        return chunk_summaries[0]
    combined = "\n".join(chunk_summaries)
    reduce_prompt = (usr_tmpl if lang.startswith("es") else usr_tmpl).format(
        bullets=bullets, title=title or "", body=combined
    )
    resp = cli.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":sys_msg},{"role":"user","content":reduce_prompt}],
        temperature=temp, max_tokens=max_tokens
    )
    return resp.choices[0].message.content.strip()
