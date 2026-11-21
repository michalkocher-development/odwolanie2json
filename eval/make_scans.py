"""Zbiór testowy „skanów”: strony PDF jako obrazy (szarość, lekki obrót, rozmycie, szum) zapisane jako PDF bez
warstwy tekstowej – test OCR i wydajności przy zestawie złożonym ze skanów. Wzorcowe JSON-y kopiowane bez zmian.

python eval/make_scans.py --src ../tasks/uzp/dane ../tasks/adversarial_holdout --per-src 15 --out ../tasks/scans
python eval/evaluate.py --data ../tasks/scans
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageFilter

PDFS = ["odwolanie.pdf", "pelnomocnictwo.pdf", "potwierdzenie_przelewu.pdf"]
GOLD = ["odwolanie.json", "pelnomocnictwo.json", "przelew.json"]


def scan(src: Path, dst: Path, rnd: random.Random, max_pages: int = 4) -> None:
    doc = pdfium.PdfDocument(str(src))
    pages = []
    for i in range(min(max_pages, len(doc))):
        page = doc[i]
        img = page.render(scale=150 / 72).to_pil().convert("L")          # ~150 dpi, skala szarości
        img = img.rotate(rnd.uniform(-0.8, 0.8), expand=False, fillcolor=255)
        img = img.filter(ImageFilter.GaussianBlur(rnd.uniform(0.3, 0.7)))
        noise = Image.effect_noise(img.size, rnd.uniform(6, 12)).convert("L")
        img = Image.blend(img, noise, 0.06)
        pages.append(img)
        page.close()
    doc.close()
    pages[0].save(dst, "PDF", resolution=150, save_all=True, append_images=pages[1:])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, nargs="+", required=True)
    ap.add_argument("--per-src", type=int, default=15)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    k = 0
    for src in a.src:
        cases = sorted(d for d in src.iterdir() if d.is_dir())
        for case in rnd.sample(cases, min(a.per_src, len(cases))):
            k += 1
            out = a.out / f"skan_{k:02d}"
            out.mkdir(parents=True, exist_ok=True)
            for pdf, gold in zip(PDFS, GOLD):
                scan(case / pdf, out / pdf, rnd)
                shutil.copy(case / gold, out / gold)
    print(f"Wygenerowano {k} spraw ze skanami w {a.out}")


if __name__ == "__main__":
    main()
