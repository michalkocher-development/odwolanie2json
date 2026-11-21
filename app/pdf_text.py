"""Wydobycie tekstu z PDF (wyłącznie biblioteki o licencjach permisywnych).

1. Warstwa tekstowa: pdfplumber / pdfminer.six (MIT), tryb układu (`layout=True`) – linie i odstępy między kolumnami
   zachowane jak na stronie (etykieta i wartość w jednej linii). Drugi wariant – kolejność strumienia PDF (pypdfium2) –
   trafia do LLM i do kontroli ugruntowania: tabele komórka po komórce, bez przeplatania kolumn.
2. Skan (brak tekstu) -> OCR modelem wizyjnym przez API (config/settings.yaml `ocr`): strony renderowane przez
   pypdfium2 (BSD-3 / Apache-2.0), pierwsze `ocr.max_pages` stron (kluczowe dane są na pierwszych stronach).
"""

from __future__ import annotations

import io
import logging
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import pdfplumber
import pypdfium2 as pdfium
import yaml

from . import backend
from .pipeline_paths import CONFIG

os.environ.pop("SSLKEYLOGFILE", None)  # niektóre antywirusy ustawiają go na urządzenie -> crash OpenSSL w urllib
log = logging.getLogger(__name__)
_PDFIUM_LOCK = threading.Lock()  # PDFium nie jest bezpieczny wątkowo; sieć (OCR) idzie poza blokadą
MIN_CHARS_PER_PAGE = 40
# ligatury z PDF (np. "Identyﬁkator") psują wyszukiwanie słów
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})
VLM_PROMPT = (
    "Przepisz dokładnie cały tekst z tego skanu dokumentu (po polsku), zachowując podział na linie "
    "i kolejność czytania. Zamazane/zaczernione fragmenty oznacz jednym znacznikiem [X]. "
    "Nie tłumacz, nie poprawiaj, nie dodawaj komentarzy. Zwróć tylko tekst."
)


@lru_cache
def settings() -> dict[str, Any]:
    f = CONFIG / "settings.yaml"
    s = yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}
    return s.get("ocr", {})


def _clean(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)       # spacje na końcach linii
    text = re.sub(r"\n{3,}", "\n\n", text)       # najwyżej jedna pusta linia odstępu
    return text.translate(LIGATURES)


def pdf_to_text(path: Path, max_pages: int | None = None) -> tuple[str, str]:
    """Zwraca (tekst, metoda). Metoda: 'text', 'ocr:vlm' albo 'empty'."""
    text, method, _ = pdf_to_texts(path, max_pages)
    return text, method


def pdf_to_texts(path: Path, max_pages: int | None = None) -> tuple[str, str, str | None]:
    """(tekst w układzie wizualnym, metoda, tekst w kolejności strumienia PDF albo None)."""
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        text = "\f".join(_clean(p.extract_text(layout=True) or "") for p in pages)
        n_pages = len(pages)
        if len(text.strip()) >= MIN_CHARS_PER_PAGE * max(1, n_pages) / 2:
            return text, "text", stream_text(path, n_pages)
    s = settings()
    if "vlm" in s.get("engines", ["vlm"]):
        try:
            out = _vlm(render_pages(path, s.get("max_pages", 3)))
            if out.strip():
                return out, "ocr:vlm", None
        except Exception as e:
            log.warning("OCR nieudany dla %s: %s", path.name, e)
    log.warning("Brak warstwy tekstowej i OCR niedostępny: %s", path)
    return text, "empty", None


def stream_text(path: Path, n_pages: int) -> str | None:
    """Tekst w kolejności strumienia PDF (pypdfium2) – tabele komórka po komórce, bez przeplatania kolumn."""
    try:
        with _PDFIUM_LOCK:
            doc = pdfium.PdfDocument(str(path))
            try:
                parts = []
                for i in range(min(n_pages, len(doc))):
                    page = doc[i]
                    tp = page.get_textpage()
                    parts.append(tp.get_text_range())
                    tp.close()
                    page.close()
            finally:
                doc.close()
    except Exception as e:  # wariant pomocniczy – brak nie blokuje ekstrakcji
        log.warning("Tekst strumieniowy niedostępny dla %s: %s", path.name, e)
        return None
    text = "\f".join(parts).replace("\r\n", "\n").replace("\r", "\n").replace("￾", "-\n")  # U+FFFE = dzielenie wyrazu
    return _clean(text)


def render_pages(path: Path, max_pages: int) -> list[bytes]:
    """Pierwsze strony jako PNG (~`ocr.image_width` px szerokości) – pypdfium2."""
    width = settings().get("image_width", 1100)  # ~1100 px wystarcza dla A4; większe obrazy spowalniają
    out = []
    with _PDFIUM_LOCK:
        doc = pdfium.PdfDocument(str(path))
        try:
            for i in range(min(max_pages, len(doc))):
                page = doc[i]
                img = page.render(scale=width / page.get_width()).to_pil()
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                out.append(buf.getvalue())
                page.close()
        finally:
            doc.close()
    return out


def _vlm(images: list[bytes]) -> str:
    timeout = settings().get("timeout", 300)
    return "\f".join(backend.vision_text(VLM_PROMPT, png, timeout) for png in images)
