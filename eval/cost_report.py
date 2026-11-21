"""Pomiar: hybryda (regex + model decyzyjny + LLM jako fallback) vs samo LLM (cały JSON jednym wywołaniem).

python eval/cost_report.py --data ../tasks/uzp/dane --mode hybrid
tryby: regex | hybrid | hybrid_no_llm | hybrid_no_jev | llm | llm_full | llm_schema | llm_vision
Wynik: F1, czas (łączny i na dokument), liczba wywołań modeli, tokeny, koszt (z OpenRouter), udział metod
wypełnienia pól. Zapis: eval/results/<zbiór>_<tryb>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from app import backend  # noqa: E402
from app.pdf_text import pdf_to_texts  # noqa: E402
from app.pipeline import process_pdf, workers  # noqa: E402
from evaluate import GOLD_FILES, PDF_FILES, f1, score  # noqa: E402

TEMPLATES = ROOT.parent / "tasks/uzp/oczekiwane-json"
METHOD_GROUP = {"regex": "regex/reguły", "rule": "regex/reguły", "item": "regex/reguły", "candidate": "regex/reguły",
                "enum": "konfiguracja", "const": "konfiguracja", "default": "konfiguracja", "default_if_many": "konfiguracja",
                "llm": "LLM"}
BASELINE_PROMPT = (
    "Jesteś systemem ekstrakcji danych z polskich dokumentów zamówień publicznych. Dokument to: {doctype}.\n"
    "Zwróć WYŁĄCZNIE obiekt JSON o dokładnie takiej strukturze jak wzór poniżej (komentarze // opisują reguły "
    "wypełniania pól; nie umieszczaj ich w odpowiedzi). Brakujące informacje = null.\n\nWZÓR:\n{template}\n\n"
    "DOKUMENT:\n{text}"
)


def run_hybrid(pdf: Path) -> tuple[str | None, Any, dict[str, Any]]:
    return process_pdf(pdf)


def _schema_from(example: Any) -> dict[str, Any]:
    """JSON Schema (strict) ze struktury przykładowego JSON-a referencyjnego danego typu."""
    if isinstance(example, dict):
        return {"type": "object", "properties": {k: _schema_from(v) for k, v in example.items()},
                "required": list(example), "additionalProperties": False}
    if isinstance(example, list):
        return {"type": "array", "items": _schema_from(example[0]) if example else {"type": ["string", "null"]}}
    return {"type": ["string", "number", "null"]}


_SCHEMAS: dict[str, dict[str, Any]] = {}


def run_llm(pdf: Path, dtype: str, variant: str, data_dir: Path) -> tuple[str | None, Any, dict[str, Any]]:
    """Punkty odniesienia „wszystko w LLM” (typ dokumentu podany z góry – przewaga baseline'u):
    llm        – tekst (pierwsze 8000 znaków) + wzór JSON z komentarzami, tryb json_object
    llm_full   – cały tekst dokumentu bez przycinania
    llm_schema – jak llm, ale wymuszony JSON Schema (structured output) zbudowany ze struktury wzorca
    llm_vision – obrazy pierwszych 3 stron (model wizyjny) zamiast tekstu
    """
    from app import pdf_text

    tpl = (TEMPLATES / f"{dtype}.json").read_text(encoding="utf-8")
    if variant == "llm_vision":
        import base64

        pngs = pdf_text.render_pages(pdf, 3)
        prompt = BASELINE_PROMPT.format(doctype=dtype, template=tpl, text="(obrazy stron poniżej)")
        content: Any = [{"type": "text", "text": prompt}] + [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(p).decode()}} for p in pngs]
        method = "vision"
    else:
        text, method, _ = pdf_to_texts(pdf)
        content = BASELINE_PROMPT.format(doctype=dtype, template=tpl, text=text if variant == "llm_full" else text[:8000])
    if variant == "llm_schema":
        if dtype not in _SCHEMAS:
            ex = next(json.loads((c / GOLD_FILES[dtype]).read_text(encoding="utf-8")) for c in sorted(data_dir.iterdir()) if c.is_dir())
            _SCHEMAS[dtype] = _schema_from(ex)
        fmt = {"response_format": {"type": "json_schema", "json_schema": {"name": dtype, "strict": True, "schema": _SCHEMAS[dtype]}}}
    else:
        fmt = {"response_format": {"type": "json_object"}}
    try:
        out = backend._chat([{"role": "user", "content": content}], fmt, 3000, kind="llm")
        return dtype, backend._parse_json(backend._content(out)), {"text_method": method}
    except Exception as e:
        return dtype, None, {"text_method": method, "error": str(e)}


MODES = {  # tryb -> zmienne środowiskowe wyłączające komponenty pipeline'u
    "regex": {"LLM_DISABLE": "1", "JEV_DISABLE": "1"},
    "hybrid": {},
    "hybrid_no_llm": {"LLM_DISABLE": "1"},
    "hybrid_no_jev": {"JEV_DISABLE": "1"},
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--mode", choices=[*MODES, "llm", "llm_full", "llm_schema", "llm_vision"], default="hybrid")
    a = ap.parse_args()
    import os

    os.environ.update(MODES.get(a.mode, {}))
    if backend.provider() != "openrouter":
        print("Uwaga: koszt liczony tylko dla provider=openrouter")
    jobs = [(c, d, g) for c in sorted(p for p in a.data.iterdir() if p.is_dir()) for d, g in GOLD_FILES.items()]
    backend.usage_snapshot(reset=True)
    lat: list[float] = []

    def one(job: tuple[Path, str, str]) -> tuple[str | None, Any, dict[str, Any]]:
        c, d, _ = job
        t0 = time.time()
        res = run_hybrid(c / PDF_FILES[d]) if a.mode in MODES else run_llm(c / PDF_FILES[d], d, a.mode, a.data)
        lat.append(time.time() - t0)
        return res

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, workers())) as ex:
        results = list(ex.map(one, jobs))
    wall = time.time() - t0
    usage = backend.usage_snapshot()

    total: Counter[str] = Counter()
    filled: Counter[str] = Counter()
    docs_llm = docs_dec = docs_cls_model = 0
    for (c, d, g), (got, pred, info) in zip(jobs, results):
        gold = json.loads((c / g).read_text(encoding="utf-8"))
        for _, cnt in score(pred if got == d else None, gold).items():
            total += cnt
        if a.mode in MODES:
            last: dict[str, dict[str, Any]] = {}
            for t in info.get("trace", []):
                if t.get("field") and t["field"] != "*":
                    last[t["field"]] = t
            for t in last.values():
                if t.get("value") is None:
                    continue
                m = str(t.get("method", ""))
                filled["model decyzyjny" if m.startswith("decision") else METHOD_GROUP.get(m, m)] += 1
            methods = {str(t.get("method", "")) for t in info.get("trace", [])}
            docs_llm += any(m in ("llm", "llm_pending") for m in methods)
            docs_dec += any(m.startswith("decision") for m in methods)
            docs_cls_model += str(info.get("class_method", "")).startswith("decision")
    n = len(jobs)
    p, r, f = f1(total)
    report = {
        "dataset": a.data.name, "mode": a.mode, "provider": backend.provider(), "documents": n, "f1": round(f, 4), "precision": round(p, 4), "recall": round(r, 4),
        "wall_seconds": round(wall, 1), "avg_doc_seconds": round(sum(lat) / n, 2), "workers": workers(),
        "usage": {k: {kk: round(vv, 6) for kk, vv in v.items()} for k, v in usage.items()},
        "cost_total_usd": round(sum(v["cost"] for v in usage.values()), 6),
        "cost_per_1000_docs_usd": round(sum(v["cost"] for v in usage.values()) / n * 1000, 4),
        "model_calls_per_doc": round(sum(v["calls"] for v in usage.values()) / n, 2),
    }
    if a.mode in MODES:
        tot = sum(filled.values()) or 1
        report["filled_fields_by_method"] = {k: f"{v} ({v / tot:.1%})" for k, v in filled.most_common()}
        report["docs_with_llm_call"] = f"{docs_llm}/{n}"
        report["docs_with_decision_call"] = f"{docs_dec}/{n}"
        report["docs_classified_by_model"] = f"{docs_cls_model}/{n}"
    out = ROOT / "eval/results" / backend.provider() / f"{a.data.name}_{a.mode}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
