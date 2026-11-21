"""Klasyfikacja dokumentu + ekstrakcja + zapis JSON."""

from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from . import engine, status
from .pdf_text import pdf_to_texts

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"


@lru_cache
def load_doctypes() -> dict[str, dict[str, Any]]:
    """Każdy plik config/doctypes/*.yaml to jedna klasa dokumentu."""
    types = {}
    for f in sorted((CONFIG / "doctypes").glob("*.yaml")):
        spec = yaml.safe_load(f.read_text(encoding="utf-8"))
        types[spec["name"]] = spec
    return types


def classify(text: str, filename: str) -> tuple[str | None, dict[str, float]]:
    """Punktacja słów kluczowych z sekcji `classify` w YAML. None = dokument nieznany."""
    scores: dict[str, float] = {}
    head = text[:5000]
    for name, spec in load_doctypes().items():
        c = spec.get("classify", {})
        s = 0.0
        for pat, w in (c.get("keywords") or {}).items():
            if re.search(pat, head, re.IGNORECASE | re.MULTILINE):
                s += w
        for pat, w in (c.get("negative") or {}).items():
            if re.search(pat, head, re.IGNORECASE | re.MULTILINE):
                s -= w
        if any(h in filename.lower() for h in c.get("filename_hints", [])):
            s += c.get("filename_weight", 1)
        scores[name] = s
    best = max(scores, key=lambda k: scores[k])
    min_score = load_doctypes()[best].get("classify", {}).get("min_score", 3)
    return (best if scores[best] >= min_score else None), scores


CLASSIFY_QUESTION = "Jakiego rodzaju jest ten dokument?"
OTHER = "Inny dokument (żaden z powyższych, np. ogłoszenie o zamówieniu, umowa, faktura)"


def classify_model(text: str) -> tuple[str | None, dict[str, Any]]:
    """Klasyfikacja modelem decyzyjnym, gdy słowa kluczowe nie wystarczą. Opcje = `classify.description` z YAML."""
    from . import backend, jev

    types = {n: s["classify"]["description"] for n, s in load_doctypes().items() if s.get("classify", {}).get("description")}
    if not types or not jev.enabled():
        return None, {}
    names, options = list(types), list(types.values()) + [OTHER]
    try:
        idx, prob = backend.choose(re.sub(r"\s+", " ", text[:2500]), CLASSIFY_QUESTION, options)
    except Exception as e:
        log.warning("Klasyfikacja modelem nieudana: %s", e)
        return None, {"error": str(e)}
    info = {"answer": options[idx], "prob": prob}
    if idx >= len(names) or (prob is not None and prob < 0.5):
        return None, info
    return names[idx], info


def _settings() -> dict[str, Any]:
    f = CONFIG / "settings.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}


def process_pdf(pdf: Path) -> tuple[str | None, Any, dict[str, Any]]:
    """Jeden dokument w budżecie czasu (`pipeline.doc_time_budget_s`): po jego przekroczeniu wywołania modeli
    są pomijane, a wynik powstaje z tego, co już ustalono (reguły, wcześniejsze odpowiedzi modeli)."""
    from . import backend

    budget = float((_settings().get("pipeline") or {}).get("doc_time_budget_s", 0) or 0)
    token = backend.set_deadline(budget)
    try:
        return _process_pdf(pdf)
    finally:
        backend.reset_deadline(token)


def _process_pdf(pdf: Path) -> tuple[str | None, Any, dict[str, Any]]:
    from . import pdf_text

    text, method, flow = pdf_to_texts(pdf)
    doctype, scores = classify(text, pdf.name)
    if method.startswith("ocr") and doctype is None and text.strip():
        doctype, _ = classify_model(text)
    if method.startswith("ocr") and doctype:
        # skan: OCR objął pierwszą stronę – dociągamy tyle stron, ile potrzebuje klasa (classify.ocr_pages)
        need = int(load_doctypes()[doctype].get("classify", {}).get("ocr_pages")
                   or pdf_text.settings().get("max_pages", 3))
        done = text.count("\f") + 1
        if need > done:
            more = pdf_text.ocr_range(pdf, done, need)
            if more:
                text = "\f".join([text, *more])
    info: dict[str, Any] = {"file": pdf.name, "text_method": method, "class_scores": scores, "doctype": doctype,
                            "class_method": "keywords" if doctype else None}
    if doctype is None and text.strip():
        doctype, minfo = classify_model(text)
        info.update(doctype=doctype, class_method="decision" if doctype else "decision:none", class_decision=minfo)
    if doctype is None:
        return None, None, info
    spec = load_doctypes()[doctype]
    result, trace = engine.extract(text, spec, alt_text=flow)
    info["trace"] = trace
    info["status"] = status.field_status(spec["output"], result)  # found / absent_ok / not_applicable / missing
    return doctype, result, info


def workers() -> int:
    """Liczba dokumentów przetwarzanych równolegle (config/settings.yaml: pipeline.workers, env WORKERS)."""
    f = CONFIG / "settings.yaml"
    s = yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}
    return int(os.environ.get("WORKERS", (s.get("pipeline") or {}).get("workers", 8)))


def _safe_process(pdf: Path) -> tuple[str | None, Any, dict[str, Any]]:
    """Nigdy nie przerywa partii: błąd dokumentu (np. uszkodzony PDF) -> wynik pusty `{}` + opis błędu w śladzie."""
    try:
        return process_pdf(pdf)
    except Exception as e:
        log.exception("Błąd przetwarzania %s", pdf)
        return None, None, {"file": pdf.name, "error": f"{type(e).__name__}: {e}"}


def process_tree(inp: Path, out: Path, trace_dir: Path | None = None, progress: bool = False) -> int:
    """Przetwarza wszystkie PDF-y z drzewa `inp` równolegle (wątki: czas to głównie I/O sieciowe do modeli).
    Każdy PDF dostaje plik wynikowy (także dokument spoza klas lub błąd -> `{}`)."""
    import sys
    import time
    from concurrent.futures import as_completed

    pdfs = sorted(inp.rglob("*.pdf"))
    n, t0 = 0, time.time()
    with ThreadPoolExecutor(max_workers=max(1, workers())) as ex:
        futures = {ex.submit(_safe_process, pdf): pdf for pdf in pdfs}
        for i, fut in enumerate(as_completed(futures), 1):
            pdf = futures[fut]
            n += _write(pdf, inp, out, trace_dir, *fut.result())
            if progress:
                el = time.time() - t0
                eta = el / i * (len(pdfs) - i)
                print(f"[{i}/{len(pdfs)}] {pdf.relative_to(inp)}  ({el:.0f} s, pozostało ~{eta:.0f} s)",
                      file=sys.stderr, flush=True)
    return n


def _write(
    pdf: Path, inp: Path, out: Path, trace_dir: Path | None, doctype: str | None, result: Any, info: dict[str, Any]
) -> int:
    rel = pdf.relative_to(inp).with_suffix(".json")
    if trace_dir:
        t = trace_dir / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    dst = out / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if doctype is None:
        # dokument spoza klas: plik z pustym obiektem {} (ustalenie z organizatorem)
        dst.write_text("{}", encoding="utf-8")
        log.info("Dokument spoza klas -> {}: %s", rel)
        return 1
    dst.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("%s -> %s (%s)", pdf.relative_to(inp), rel, doctype)
    return 1
