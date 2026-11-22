"""Szkielet klasy z przykładowego JSON-a (app/new_class.py) i dodawanie klasy przez API interfejsu (bez sieci)."""

import pytest
import yaml

from app import engine, new_class, pipeline, web

EXAMPLE = {"data": "2026-10-14", "kwota": 7500.0, "sygnatura": "KIO 1/26",
           "strony": [{"nazwa": "Gmina X", "nip": "5262239325"}]}


def test_skeleton_structure():
    spec = new_class.skeleton("demo_klasa", EXAMPLE, "Demo", ["kopii odwołania"])
    out = spec["output"]
    assert out["data"] == {"llm": "Data", "normalize": "date", "checks": ["date"]}
    assert out["kwota"]["normalize"] == "amount"
    assert out["strony"][0]["_llm"] and out["strony"][0]["nazwa"]["llm"]
    assert spec["classify"]["keywords"] == {r"kopii\s+odwołania": 3}
    result, _ = engine.extract("dokument", yaml.safe_load(new_class.to_yaml(spec)))  # YAML działa w silniku
    assert set(result) == set(EXAMPLE)


def test_add_class_via_api(monkeypatch):
    monkeypatch.setattr(pipeline, "EXTRA_DOCTYPES", {})
    y = new_class.to_yaml(new_class.skeleton("demo_klasa", EXAMPLE))
    assert web.add_class(y)["name"] == "demo_klasa"
    assert "demo_klasa" in pipeline.load_doctypes()
    for bad in ["name: X\noutput: {a: {llm: x}}", "name: zla\noutput:\n  a: {regex: '('}", "name: odwolanie\noutput: {a: {llm: x}}"]:
        with pytest.raises(ValueError):
            web.add_class(bad)
