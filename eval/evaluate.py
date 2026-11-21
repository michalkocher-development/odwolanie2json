"""Ewaluacja F1 na zbiorze treningowym (dane/przyklad_XX/*.pdf + *.json).

Uruchomienie:  python eval/evaluate.py --data ../tasks/uzp/dane [--errors pole] [--only odwolanie]

Metryka (przybliżenie oficjalnej): spłaszczamy JSON do par (ścieżka, wartość),
listy porównujemy jako multizbiory (bez kolejności).
TP = przewidziana != null i równa wzorcowi; FP = przewidziana != null i błędna;
FN = wzorzec != null i nie trafiony. Para null/null nie liczy się.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

from app.pipeline import process_pdf, workers  # noqa: E402

GOLD_FILES = {"odwolanie": "odwolanie.json", "pelnomocnictwo": "pelnomocnictwo.json", "przelew": "przelew.json"}
PDF_FILES = {"odwolanie": "odwolanie.pdf", "pelnomocnictwo": "pelnomocnictwo.pdf", "przelew": "potwierdzenie_przelewu.pdf"}


def flatten(obj: Any, path: str = "") -> list[tuple[str, Any]]:
    if isinstance(obj, dict):
        return [p for k, v in obj.items() for p in flatten(v, f"{path}.{k}" if path else k)]
    if isinstance(obj, list):
        return [p for v in obj for p in flatten(v, f"{path}[]")]
    return [(path, obj)]


def canon(v: Any) -> Any:
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    return str(v).strip()


def score(pred: Any, gold: Any) -> dict[str, Counter[str]]:
    """Zwraca liczniki tp/fp/fn per ścieżka."""
    res: dict[str, Counter[str]] = defaultdict(Counter)
    p_by, g_by = defaultdict(Counter), defaultdict(Counter)
    for k, v in flatten(pred or {}):
        if v is not None:
            p_by[k][canon(v)] += 1
    for k, v in flatten(gold):
        if v is not None:
            g_by[k][canon(v)] += 1
        res[k]  # zarejestruj pole
    for k in set(p_by) | set(g_by):
        tp = sum((p_by[k] & g_by[k]).values())
        res[k]["tp"] += tp
        res[k]["fp"] += sum(p_by[k].values()) - tp
        res[k]["fn"] += sum(g_by[k].values()) - tp
    return res


def f1(c: Counter[str]) -> tuple[float, float, float]:
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 1.0
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[2] / "tasks/uzp/dane")
    ap.add_argument("--only", choices=list(GOLD_FILES))
    ap.add_argument("--errors", help="pokaż błędy dla ścieżek zawierających ten tekst")
    ap.add_argument("--cases", help="np. 40-60")
    ap.add_argument("--llm-only", action="store_true", help="ablacja: usuń regex z pól z kluczem llm (test fallbacku)")
    a = ap.parse_args()
    if a.llm_only:
        from app.pipeline import load_doctypes

        def strip(node: Any) -> None:
            if isinstance(node, dict):
                if "llm" in node:
                    node.pop("regex", None)
                for v in node.values():
                    strip(v)
            elif isinstance(node, list):
                for v in node:
                    strip(v)

        for spec in load_doctypes().values():
            strip(spec["output"])

    cases = sorted(d for d in a.data.iterdir() if d.is_dir())
    if a.cases:
        lo, hi = map(int, a.cases.split("-"))
        cases = [d for d in cases if lo <= int(d.name.split("_")[-1]) <= hi]
    per_field: dict[str, Counter[str]] = defaultdict(Counter)
    per_type: dict[str, Counter[str]] = defaultdict(Counter)
    cls_ok = cls_n = 0
    t0 = time.time()
    jobs = [(c, d, g) for c in cases for d, g in GOLD_FILES.items() if not a.only or d == a.only]
    with ThreadPoolExecutor(max_workers=max(1, workers())) as ex:
        preds = list(ex.map(lambda j: process_pdf(j[0] / PDF_FILES[j[1]]), jobs))
    for (case, dtype, gname), (got_type, pred, _info) in zip(jobs, preds):
        if True:  # noqa: SIM108 (zachowane wcięcie bloku)
            gold = json.loads((case / gname).read_text(encoding="utf-8"))
            cls_n += 1
            cls_ok += got_type == dtype
            for k, c in score(pred if got_type == dtype else None, gold).items():
                per_field[f"{dtype}:{k}"] += c
                per_type[dtype] += c
            if a.errors:
                pf, gf = dict(flatten(pred or {})), flatten(gold)
                for k, gv in gf:
                    if a.errors in k:
                        pv = pf.get(k)
                        if canon(pv) != canon(gv):
                            print(f"  {case.name} {k}: pred={pv!r} gold={gv!r}")
    total = sum(per_type.values(), Counter())
    print(f"\nKlasyfikacja: {cls_ok}/{cls_n}   czas: {time.time() - t0:.1f}s")
    print(f"{'pole':55} {'P':>6} {'R':>6} {'F1':>6}  tp/fp/fn")
    for k, c in sorted(per_field.items(), key=lambda kv: f1(kv[1])[2]):
        p, r, f = f1(c)
        print(f"{k:55} {p:6.3f} {r:6.3f} {f:6.3f}  {c['tp']}/{c['fp']}/{c['fn']}")
    for t, c in per_type.items():
        print(f"== {t:20} F1={f1(c)[2]:.4f}")
    print(f"== RAZEM (micro)        F1={f1(total)[2]:.4f}")


if __name__ == "__main__":
    main()
