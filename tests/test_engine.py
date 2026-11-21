"""Silnik konfiguracji: klasa dokumentu zdefiniowana wyłącznie w YAML (bez zmian w kodzie)."""

import yaml

from app import engine
from app.status import field_status

SPEC = yaml.safe_load(r"""
name: demo
sections:
  strony:
    start: '^Strony:'
    end: '^Treść'
enums:
  rodzaje: {1: Wezwanie, 2: Odpowiedź}
output:
  naglowek:
    data: {regex: 'dnia\s+(\d{1,2}\s+\w+\s+\d{4})', normalize: date}
    rodzaj_id:
      rules:
        - {pattern: 'wzywa', value: 1}
        - {pattern: 'odpowiada', value: 2}
    rodzaj: {from: rodzaj_id, enum: rodzaje}
    sygnatura: {regex: 'sygn\.\s*(\S+)', absent_ok: "nie każde pismo ma sygnaturę"}
  osoby:
    - _scope: strony
      _each: '(?m)^-\s*(.+)$'
      imie_nazwisko: {take: item, normalize: person}
""")

TEXT = """Warszawa, dnia 5 marca 2026 r.
Strony:
- r. pr. Jana Nowaka
- Anna Kowalska
Treść: Zamawiający wzywa wykonawcę do złożenia wyjaśnień."""


def test_yaml_only_document_class():
    result, trace = engine.extract(TEXT, SPEC)
    assert result == {
        "naglowek": {"data": "2026-03-05", "rodzaj_id": 1, "rodzaj": "Wezwanie", "sygnatura": None},
        "osoby": [{"imie_nazwisko": "Jan Nowak"}, {"imie_nazwisko": "Anna Kowalska"}],
    }
    # transparentność: każde znalezione pole ma metodę i cytat ze strony
    data = next(t for t in trace if t["field"] == "naglowek.data")
    assert data["method"] == "regex" and data["quote"] == "5 marca 2026" and data["page"] == 1


def test_field_status():
    result, _ = engine.extract(TEXT, SPEC)
    st = field_status(SPEC["output"], result)
    assert st["naglowek.data"]["status"] == "found"
    assert st["naglowek.sygnatura"] == {"status": "absent_ok", "note": "nie każde pismo ma sygnaturę"}


def test_candidates_single_match_without_model():
    spec = {"name": "c", "output": {"kwota": {"regex": "NIEMA(\\d+)", "candidates": {
        "regex": "(\\d+,\\d{2}) zł", "question": "?"}, "normalize": "amount"}}}
    result, trace = engine.extract("Do zapłaty 120,50 zł.", spec)
    assert result == {"kwota": 120.5}
    assert trace[-1]["method"] == "candidate"
