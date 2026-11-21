"""Wydobycie tekstu z PDF.

1. Warstwa tekstowa przez PyMuPDF (`get_text(sort=True)` – zachowuje układ linii).
2. Skan (brak tekstu) -> OCR wg config/settings.yaml `ocr.engines` (kolejno, pierwszy udany):
   - "vlm": model wizyjny przez Ollama (domyślnie gemma4 – ten sam serwer co llm), przepisuje stronę,
   - "tesseract": Tesseract wbudowany w PyMuPDF (wymaga lokalnej instalacji + danych 'pol').
   OCR obejmuje pierwsze `ocr.max_pages` stron (kluczowe dane są na pierwszych stronach).
"""

from __future__ import annotations

import base64
import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import pymupdf as fitz
import yaml

from . import ollama
from .pipeline_paths import CONFIG

os.environ.pop("SSLKEYLOGFILE", None)  # patrz app/jev.py
log = logging.getLogger(__name__)
_FITZ_LOCK = threading.Lock()  # PyMuPDF nie jest bezpieczny wątkowo; sieć (OCR) idzie poza blokadą
MIN_CHARS_PER_PAGE = 40
VLM_PROMPT = (
    "Przepisz dokładnie cały tekst z tego skanu dokumentu (po polsku), zachowując podział na linie "
    "i kolejność czytania. Zamazane/zaczernione fragmenty oznacz jednym znacznikiem [X]. "
    "Nie tłumacz, nie poprawiaj, nie dodawaj komentarzy. Zwróć tylko tekst."
)


@lru_cache
def settings() -> dict[str, Any]:
    f = CONFIG / "settings.yaml"
    s = yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}
    return s.get("ocr", {})  # serwery/model: wspólna pula z sekcji llm (app/ollama.py); ocr.model nadpisuje model


def pdf_to_text(path: Path, max_pages: int | None = None) -> tuple[str, str]:
    """Zwraca (tekst, metoda). Metoda: 'text', 'ocr:vlm', 'ocr:tesseract' albo 'empty'."""
    s = settings()
    with _FITZ_LOCK, fitz.open(path) as doc:
        pages = list(doc)[:max_pages] if max_pages else list(doc)
        text = "\f".join(p.get_text("text", sort=True) for p in pages)
        if len(text.strip()) >= MIN_CHARS_PER_PAGE * max(1, len(pages)) / 2:
            return text, "text"
        ocr_pages = pages[: s.get("max_pages", 3)]
        engines = s.get("engines", ["vlm", "tesseract"])
        images = [_render(p) for p in ocr_pages] if "vlm" in engines else []
    for engine in engines:
        try:
            if engine == "vlm":
                out = _vlm(images)
            else:
                with _FITZ_LOCK, fitz.open(path) as doc:
                    out = _tesseract(list(doc)[: s.get("max_pages", 3)])
            if out.strip():
                return out, f"ocr:{engine}"
        except Exception as e:
            log.warning("OCR %s nieudany dla %s: %s", engine, path.name, e)
    log.warning("Brak warstwy tekstowej i OCR niedostępny: %s", path)
    return text, "empty"


def _render(p: fitz.Page) -> bytes:
    zoom = settings().get("image_width", 1100) / p.rect.width  # ~1100 px szerokości wystarcza dla A4
    return p.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("png")


def _vlm(images: list[bytes]) -> str:
    s = settings()
    out = []
    for png in images:
        body = {
            "prompt": VLM_PROMPT,
            "images": [base64.b64encode(png).decode()],
            "keep_alive": "30m",
            # repeat_penalty + limit: model potrafi zapętlić się na zamazanych fragmentach
            "options": {"temperature": 0, "num_ctx": 8192, "repeat_penalty": 1.15, "num_predict": 2500},
        }
        if s.get("model"):
            body["model"] = s["model"]
        out.append(ollama.generate(body, timeout=s.get("timeout", 300)))
    return "\f".join(out)


def _tesseract(pages: list[fitz.Page]) -> str:
    out = []
    for p in pages:
        tp = p.get_textpage_ocr(language="pol", dpi=300, full=True)
        out.append(p.get_text("text", textpage=tp, sort=True))
    return "\f".join(out)
