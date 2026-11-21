"""CLI: python -m app [--input input] [--output output] [--trace trace]"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .pipeline import ROOT, process_tree


def warn_missing_key() -> None:
    """Czytelne ostrzeżenie zamiast błędów 401 w logach, gdy brak klucza API."""
    from . import backend

    if backend.is_api() and not backend._oai()["api_key"]:
        key = backend._oai().get("api_key_env", "OPENROUTER_API_KEY")
        print(f"UWAGA: brak klucza {key} (plik .env, wzór: .env.example).\n"
              "       Działa tylko część regułowa – bez klasyfikacji modelem, modelu decyzyjnego, LLM i OCR skanów.")


def main() -> None:
    p = argparse.ArgumentParser(description="Odwołania KIO: PDF -> JSON")
    p.add_argument("--input", type=Path, default=ROOT / "input")
    p.add_argument("--output", type=Path, default=ROOT / "output")
    p.add_argument("--trace", type=Path, default=ROOT / "trace", help="ślady ekstrakcji (transparentność)")
    p.add_argument("--no-trace", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    warn_missing_key()
    if not a.input.is_dir():
        raise SystemExit(f"Brak folderu wejściowego: {a.input} (oczekiwana struktura: input/<sprawa>/*.pdf)")
    n = process_tree(a.input, a.output, None if a.no_trace else a.trace, progress=True)
    print(f"Zapisano {n} plików JSON w {a.output}")


if __name__ == "__main__":
    main()
