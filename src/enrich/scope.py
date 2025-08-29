from __future__ import annotations
import re

POS = [
    r"\bbiotech\b", r"\bbiotecnolog", r"\bgenom", r"\bcrispr\b", r"\bbioinform",
    r"\bsyn(bio|thetic biology)\b", r"\bensayo(s)? clínic", r"\bdiagnósti", r"\bterapia(s)? génica"
]
NEG = [
    r"\bpaleontolog", r"\bdinosaur", r"\barqueolog", r"\bdeporte\b", r"\bespectáculo\b",
    r"\bpolítica partid", r"\bconcurso cultural\b"
]

def on_scope(text: str, mode: str = "soft") -> bool:
    t = (text or "").lower()
    if any(re.search(n, t) for n in NEG):
        return False
    if mode == "soft":
        return True                # deja pasar salvo NEG
    return any(re.search(p, t) for p in POS)
