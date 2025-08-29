# src/enrich/flags.py
from __future__ import annotations
import re
from urllib.parse import urlparse

PROVINCES = ["Buenos Aires","CABA","Córdoba","Santa Fe","Mendoza","Tucumán","Entre Ríos","Salta","Misiones",
             "Chaco","Corrientes","Santiago del Estero","San Juan","Jujuy","Río Negro","Neuquén","Formosa",
             "Chubut","San Luis","Catamarca","La Rioja","La Pampa","Santa Cruz","Tierra del Fuego"]
AR_TOKENS = ["Argentina","argentino","argentina", "ARG"] + PROVINCES

FIN_PAT = re.compile(
    r"(series\s+[abcde]\b|seed|pre-?seed|ronda|financiaci[oó]n|grant|subsidio|foncyt|anr|\bM&A\b|adquisici[oó]n|inversi[oó]n)"
    r"|(\bUSD\b|\bU\$S\b|\$)\s?\d[\d\.,]*\s?(m|millone?s|bn|k)?",
    re.IGNORECASE
)

def is_argentina(text: str, url: str, country_hint: str|None) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    if host.endswith(".ar"):
        return True
    if country_hint and country_hint.upper() == "AR":
        return True
    t = (text or "")
    for token in AR_TOKENS:
        if token.lower() in t.lower():
            return True
    return False

_FIN_AMT = re.compile(r"\b(\$|usd|u\$s|ars|\bmill(on|ones)\b|\bm\b|\bk\b)\s?\d", re.I)
_FIN_TERMS = [
    r"\b(series [ab]|seed|pre[- ]seed|round|ronda)\b",
    r"\bgrant(s)?\b", r"\bfunding\b", r"\bfinanciamien", r"\binversi(ón|on)\b",
    r"\bfoncyt\b", r"\banr\b", r"\bfonarsec\b", r"\bagencia i\+d\b",
]
def has_funding(text: str, title: str="") -> bool:
    t = (title + " " + text).lower()
    # requiere o bien monto/moneda o bien término de ronda/convocatoria
    return bool(_FIN_AMT.search(t) or any(re.search(p, t, re.I) for p in _FIN_TERMS))