"""Generujący LLM (Ollama /api/generate, structured output) – fallback dla pól bez trafienia regex.

Jedno wywołanie na dokument: wszystkie brakujące pola naraz, JSON Schema w `format`.
Model kopiuje fragment dosłownie; wartość jest przyjmowana tylko, gdy występuje w tekście
(kontrola halucynacji), a potem przechodzi przez normalizator pola.
Konfiguracja: config/settings.yaml -> llm.* (env: LLM_URL, LLM_MODEL, LLM_DISABLE=1).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

os.environ.pop("SSLKEYLOGFILE", None)  # patrz app/jev.py

from . import ollama  # noqa: E402

PROMPT = (
    "Jesteś systemem ekstrakcji danych z polskich dokumentów zamówień publicznych ({doctype}).\n"
    "Dla każdego pola zwróć fragment skopiowany DOSŁOWNIE z dokumentu (bez komentarzy). "
    "Jeśli informacji nie ma w dokumencie, zwróć null. Nie zgaduj.\n\nPOLA:\n{fields}\n\nDOKUMENT:\n{text}"
)


def settings() -> dict[str, Any]:
    return ollama.settings()


def enabled() -> bool:
    return bool(settings().get("enabled", True)) and os.environ.get("LLM_DISABLE") != "1"


def _norm(s: str) -> str:
    return re.sub(r"[\s„”\"“]+", " ", s).strip().lower()


def extract(doctype: str, text: str, fields: dict[str, dict[str, Any]]) -> dict[str, tuple[str | None, bool]]:
    """fields: {id: {"desc": str, "context": str|None}} -> {id: (wartość, ugruntowana_w_tekście)}"""
    s = settings()
    lines = []
    for fid, f in fields.items():
        line = f"- {fid}: {f['desc']}"
        if f.get("context"):
            line += f" (dotyczy fragmentu: «{f['context'][:200]}»)"
        lines.append(line)
    schema = {
        "type": "object",
        "properties": {fid: {"type": ["string", "null"]} for fid in fields},
        "required": list(fields),
    }
    body = {
        "prompt": PROMPT.format(doctype=doctype, fields="\n".join(lines), text=text[: s.get("max_chars", 8000)]),
        "format": schema,
        "keep_alive": s.get("keep_alive", "30m"),
        "options": {"temperature": 0, "num_ctx": s.get("num_ctx", 8192)},
    }
    raw = json.loads(ollama.generate(body))
    hay = _norm(text)
    out: dict[str, tuple[str | None, bool]] = {}
    for fid in fields:
        v = raw.get(fid)
        if isinstance(v, str) and v.strip() and not re.fullmatch(r"[\W_]*(\[X\][\W_]*)+", v.strip()):
            out[fid] = (v.strip(), _norm(v) in hay)
        else:
            out[fid] = (None, False)
    return out
