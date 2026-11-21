"""CLI: python -m app [--input input] [--output output] [--trace trace]"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .pipeline import ROOT, process_tree


def main() -> None:
    p = argparse.ArgumentParser(description="Odwołania KIO: PDF -> JSON")
    p.add_argument("--input", type=Path, default=ROOT / "input")
    p.add_argument("--output", type=Path, default=ROOT / "output")
    p.add_argument("--trace", type=Path, default=ROOT / "trace", help="ślady ekstrakcji (transparentność)")
    p.add_argument("--no-trace", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    n = process_tree(a.input, a.output, None if a.no_trace else a.trace)
    print(f"Zapisano {n} plików JSON w {a.output}")


if __name__ == "__main__":
    main()
