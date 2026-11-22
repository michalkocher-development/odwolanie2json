"""Szkielet nowej klasy dokumentu z przykładowego JSON-a (poziom 1: same opisy pól dla LLM, bez regexów).

    python -m app.new_class <nazwa> <przyklad.json> [--opis "..."] [--slowa "kopii odwołania, art. 514"] [--zapisz]

Wynik: YAML gotowy do `config/doctypes/<nazwa>.yaml` – rozpoznawanie (słowa kluczowe + opis dla modelu decyzyjnego)
i pole `llm:` dla każdego klucza JSON (daty -> `normalize: date` + `checks: [date]`, liczby -> `amount`/`int`,
listy obiektów -> lista wypełniana przez LLM). Dalsze kroki (słowniki, regexy, walidatory): docs/NOWA_KLASA.md.
Używane też przez interfejs web (przycisk „Dodaj klasę”).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

NAME_RE = re.compile(r"[a-z][a-z0-9_]{1,40}")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
NEVER = "(?!)"  # `_each`, które nic nie dopasowuje -> elementy listy wypełnia LLM (`_llm`)


def label(key: str) -> str:
    """`data_przekazania` / `numerBZP` -> „Data przekazania” / „Numer BZP”."""
    s = re.sub(r"(?<=[a-ząćęłńóśźż])(?=[A-ZĄĆĘŁŃÓŚŹŻ])", " ", key).replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:1].upper() + s[1:]


def leaf(key: str, value: Any, context: str = "") -> dict[str, Any]:
    desc = label(key) + (f" ({context})" if context else "")
    out: dict[str, Any] = {"llm": desc}
    if isinstance(value, str) and DATE_RE.fullmatch(value):
        out.update(normalize="date", checks=["date"])
    elif isinstance(value, bool):
        out["llm"] = desc + " – tak/nie"
    elif isinstance(value, float):
        out["normalize"] = "amount"
    elif isinstance(value, int):
        out["normalize"] = "int"
    return out


def node(key: str, value: Any, context: str = "") -> Any:
    if isinstance(value, dict):
        ctx = label(key) if key else ""
        return {k: node(k, v, ctx) for k, v in value.items()}
    if isinstance(value, list) and value and isinstance(value[0], dict):
        tmpl: dict[str, Any] = {"_each": NEVER, "_llm": f"{label(key)} – wszystkie elementy wymienione w dokumencie"}
        for k, v in value[0].items():  # zagnieżdżone listy w elemencie listy -> pojedyncze pole tekstowe
            tmpl[k] = leaf(k, v, label(key)) if not isinstance(v, dict) else node(k, v, label(key))
        return [tmpl]
    return leaf(key, value, context)


def skeleton(name: str, example: Any, description: str = "", keywords: list[str] | None = None) -> dict[str, Any]:
    if not NAME_RE.fullmatch(name):
        raise ValueError("Nazwa klasy: małe litery, cyfry i _, zaczyna się literą (np. kopia_odwolania)")
    if not isinstance(example, dict) or not example:
        raise ValueError("Przykładowy JSON musi być niepustym obiektem")
    words = [w.strip() for w in (keywords or []) if w.strip()]
    classify: dict[str, Any] = {"description": description.strip() or label(name)}
    if words:
        classify["keywords"] = {r"\s+".join(map(re.escape, w.split())): 3 for w in words}
        classify["min_score"] = 3
    else:
        classify["min_score"] = 99  # bez słów kluczowych rozpoznaje tylko model decyzyjny (po `description`)
    return {"name": name, "classify": classify, "output": node("", example)}


def to_yaml(spec: dict[str, Any]) -> str:
    head = (f"# Klasa dokumentu „{spec['classify']['description']}” – szkielet wygenerowany z przykładowego JSON-a.\n"
            "# Poziom 1: opisy pól dla LLM (wartości przyjmowane tylko, gdy występują w tekście).\n"
            "# Dalej: słowniki (jev/enum, rules), regexy dla stałych formatów, walidatory – docs/NOWA_KLASA.md\n")
    return head + yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120)


def main() -> None:
    ap = argparse.ArgumentParser(description="Szkielet klasy dokumentu z przykładowego JSON-a")
    ap.add_argument("name")
    ap.add_argument("example", type=Path)
    ap.add_argument("--opis", default="", help="opis klasy dla modelu decyzyjnego")
    ap.add_argument("--slowa", default="", help="słowa kluczowe rozpoznawania, po przecinku")
    ap.add_argument("--zapisz", action="store_true", help="zapisz do config/doctypes/<nazwa>.yaml")
    a = ap.parse_args()
    spec = skeleton(a.name, json.loads(a.example.read_text(encoding="utf-8")), a.opis, a.slowa.split(","))
    text = to_yaml(spec)
    if a.zapisz:
        from .pipeline import CONFIG

        f = CONFIG / "doctypes" / f"{a.name}.yaml"
        if f.exists():
            sys.exit(f"{f} już istnieje")
        f.write_text(text, encoding="utf-8")
        print(f"Zapisano {f}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()
