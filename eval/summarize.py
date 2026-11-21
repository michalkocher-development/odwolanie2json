"""Tabela porównawcza wariantów: python eval/summarize.py [dostawca] -> eval/results/<dostawca>/SUMMARY.md"""

from __future__ import annotations

import json
from pathlib import Path

import sys

RES = Path(__file__).resolve().parent / "results" / (sys.argv[1] if len(sys.argv) > 1 else "privatemode")
CUR = "€" if RES.name == "privatemode" else "$"  # Privatemode: EUR z cennika; OpenRouter: USD z API
NAMES = {
    "regex": "Same regexy/reguły (bez modeli)",
    "hybrid": "**Hybryda (nasz system)**",
    "hybrid_no_llm": "Hybryda bez LLM (regex + model decyzyjny)",
    "hybrid_no_jev": "Hybryda bez modelu decyzyjnego (regex + LLM)",
    "llm": "Samo LLM: tekst (8k znaków) + wzór JSON",
    "llm_full": "Samo LLM: cały tekst + wzór JSON",
    "llm_schema": "Samo LLM: tekst + wymuszony JSON Schema",
    "llm_vision": "Samo LLM wizyjne: obrazy stron + wzór JSON",
}
DATASETS = {"dane": "Treningowy UZP (180 dok.)", "adversarial_holdout": "Adwersaryjny kontrolny (90 dok.)"}


def main() -> None:
    lines = []
    for ds, title in DATASETS.items():
        lines += [f"### {title}", "", "| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |",
                  "|---|---|---|---|---|"]
        for mode, name in NAMES.items():
            f = RES / f"{ds}_{mode}.json"
            if not f.exists():
                continue
            r = json.loads(f.read_text(encoding="utf-8"))
            lines.append(f"| {name} | {r['f1']:.3f} | {r['avg_doc_seconds']:.2f} s | {CUR}{r["cost_per_1000_docs_usd"]:.3f} | "
                         f"{r['model_calls_per_doc']:.2f} |")
        lines.append("")
    md = "\n".join(lines)
    (RES / "SUMMARY.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
