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

from . import engine
from .pdf_text import pdf_to_text

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


def process_pdf(pdf: Path) -> tuple[str | None, Any, dict[str, Any]]:
    text, method = pdf_to_text(pdf)
    doctype, scores = classify(text, pdf.name)
    info: dict[str, Any] = {"file": pdf.name, "text_method": method, "class_scores": scores, "doctype": doctype}
    if doctype is None:
        return None, None, info
    result, trace = engine.extract(text, load_doctypes()[doctype])
    info["trace"] = trace
    return doctype, result, info


def workers() -> int:
    """Liczba dokumentów przetwarzanych równolegle (config/settings.yaml: pipeline.workers, env WORKERS)."""
    f = CONFIG / "settings.yaml"
    s = yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}
    return int(os.environ.get("WORKERS", (s.get("pipeline") or {}).get("workers", 8)))


def _safe_process(pdf: Path) -> tuple[str | None, Any, dict[str, Any]] | None:
    try:
        return process_pdf(pdf)
    except Exception:
        log.exception("Błąd przetwarzania %s", pdf)
        return None


def process_tree(inp: Path, out: Path, trace_dir: Path | None = None) -> int:
    """Przetwarza wszystkie PDF-y z drzewa `inp` równolegle (wątki: czas to głównie I/O sieciowe do modeli)."""
    pdfs = sorted(inp.rglob("*.pdf"))
    n = 0
    with ThreadPoolExecutor(max_workers=max(1, workers())) as ex:
        results = ex.map(_safe_process, pdfs)  # zachowuje kolejność
        for pdf, res in zip(pdfs, results):
            if res is None:
                continue
            n += _write(pdf, inp, out, trace_dir, *res)
    return n


def _write(
    pdf: Path, inp: Path, out: Path, trace_dir: Path | None, doctype: str | None, result: Any, info: dict[str, Any]
) -> int:
    rel = pdf.relative_to(inp).with_suffix(".json")
    if trace_dir:
        t = trace_dir / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    if doctype is None:
        log.info("Pominięto (nie rozpoznano typu): %s", rel)
        return 0
    dst = out / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("%s -> %s (%s)", pdf.relative_to(inp), rel, doctype)
    return 1
