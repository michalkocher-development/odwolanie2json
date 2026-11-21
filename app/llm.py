"""Generujący LLM (structured output; dostawca wg app/backend.py) – fallback dla pól bez trafienia regex.

Jedno wywołanie na dokument: wszystkie brakujące pola naraz, JSON Schema w `format`.
Model kopiuje fragment dosłownie; wartość jest przyjmowana tylko, gdy występuje w tekście
(kontrola halucynacji), a potem przechodzi przez normalizator pola.
Konfiguracja: config/settings.yaml -> llm.* (env: LLM_URL, LLM_MODEL, LLM_DISABLE=1).
"""

from __future__ import annotations

import os
import re
from typing import Any

os.environ.pop("SSLKEYLOGFILE", None)  # patrz app/jev.py

from . import backend, ollama  # noqa: E402

PROMPT = (
    "Jesteś systemem ekstrakcji danych z polskich dokumentów zamówień publicznych ({doctype}).\n"
    "Dla każdego pola zwróć fragment skopiowany DOSŁOWNIE z dokumentu (bez komentarzy). "
    "Wyjątek: imiona i nazwiska osób podawaj w mianowniku, bez tytułów (np. 'Pana Jana Nowaka' -> 'Jan Nowak'). "
    "Jeśli informacji nie ma w dokumencie, zwróć null (dla listy: pustą listę). Nie zgaduj.\n\n"
    "POLA:\n{fields}\n\nDOKUMENT:\n{text}"
)


def settings() -> dict[str, Any]:
    return ollama.settings()


def enabled() -> bool:
    return bool(settings().get("enabled", True)) and os.environ.get("LLM_DISABLE") != "1"


def _norm(s: str) -> str:
    return re.sub(r"[\s„”\"“]+", " ", s).strip().lower()


def grounded(value: str, text: str, mode: str = "exact") -> bool:
    """Czy wartość jest oparta na tekście dokumentu (kontrola halucynacji).

    exact – fragment występuje dosłownie (z dokładnością do białych znaków i cudzysłowów);
    stem  – dla imion i nazwisk w mianowniku: rdzeń każdego słowa występuje jako początek słowa w tekście
            ("Anna Zielińska" ugruntowana w "adwokata Annę Zielińską").
    """
    hay = _norm(text)
    if _norm(value) in hay:
        return True
    if mode != "stem":
        return False
    words = re.findall(r"[^\W\d_][\w-]*", value.lower())
    return bool(words) and all(re.search(r"(?<!\w)" + re.escape(w[: max(3, len(w) - 2)]), hay) for w in words)


def _clean(v: Any) -> str | None:
    if isinstance(v, str) and v.strip() and not re.fullmatch(r"[\W_]*(\[X\][\W_]*)+", v.strip()):
        return v.strip()
    return None


def extract(doctype: str, text: str, fields: dict[str, dict[str, Any]], ground: list[str] | None = None) -> dict[str, Any]:
    """Jedno wywołanie LLM dla wielu pól.

    fields: {id: {"desc", "context"?, "grounding"?: exact|stem}}                 -> (wartość, ugruntowana)
            {id: {"desc", "context"?, "items": {klucz: {"desc", "grounding"?}}}} -> [{klucz: (wartość, ugruntowana)}]
    """
    s = settings()
    lines, props = [], {}
    for fid, f in fields.items():
        ctx = f" (dotyczy fragmentu: «{f['context'][:200]}»)" if f.get("context") else ""
        if "items" in f:
            sub = "; ".join(f"{k}: {d['desc']}" for k, d in f["items"].items())
            lines.append(f"- {fid}: LISTA – {f['desc']}{ctx}. Każdy element ma pola: {sub}")
            props[fid] = {"type": "array", "items": {
                "type": "object", "properties": {k: {"type": ["string", "null"]} for k in f["items"]},
                "required": list(f["items"]), "additionalProperties": False}}
        else:
            lines.append(f"- {fid}: {f['desc']}{ctx}")
            props[fid] = {"type": ["string", "null"]}
    schema = {"type": "object", "properties": props, "required": list(fields)}
    prompt = PROMPT.format(doctype=doctype, fields="\n".join(lines), text=text[: s.get("max_chars", 8000)])
    raw = backend.generate_json(prompt, schema)
    corpus = "\n".join([text, *(ground or [])])  # ugruntowanie w każdym wariancie tekstu
    out: dict[str, Any] = {}
    for fid, f in fields.items():
        if "items" in f:
            rows = raw.get(fid) if isinstance(raw.get(fid), list) else []
            out[fid] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                vals = {k: _clean(row.get(k)) for k in f["items"]}
                out[fid].append({k: (v, v is not None and grounded(v, corpus, f["items"][k].get("grounding", "exact")))
                                 for k, v in vals.items()})
        else:
            v = _clean(raw.get(fid))
            out[fid] = (v, v is not None and grounded(v, corpus, f.get("grounding", "exact")))
    return out
