"""Porównanie pred vs gold per przypadek: python eval/diff.py pelnomocnictwo [40-60]"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.pipeline import process_pdf
PDF = {"odwolanie": "odwolanie.pdf", "pelnomocnictwo": "pelnomocnictwo.pdf", "przelew": "potwierdzenie_przelewu.pdf"}
dt = sys.argv[1]; lo, hi = map(int, (sys.argv[2] if len(sys.argv) > 2 else "1-99").split("-"))
d = Path(__file__).resolve().parents[2] / "tasks/uzp/dane"
for c in sorted(d.iterdir()):
    if not lo <= int(c.name[-2:]) <= hi: continue
    _, p, _ = process_pdf(c / PDF[dt]); g = json.loads((c / f"{dt}.json").read_text(encoding="utf-8"))
    if p != g:
        print(f"=== {c.name}\n  pred: {json.dumps(p, ensure_ascii=False)}\n  gold: {json.dumps(g, ensure_ascii=False)}")
