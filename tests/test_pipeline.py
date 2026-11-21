"""Cały pipeline na publicznej przykładowej sprawie organizatora (część regułowa, bez modeli)."""

import json

from conftest import FIXTURES

from app.pipeline import process_pdf, process_tree

CASE = FIXTURES / "sprawa"


def _gold(name):
    return json.loads((CASE / name).read_text(encoding="utf-8"))


def test_classification():
    assert process_pdf(CASE / "odwolanie.pdf")[0] == "odwolanie"
    assert process_pdf(CASE / "pelnomocnictwo.pdf")[0] == "pelnomocnictwo"
    assert process_pdf(CASE / "potwierdzenie_przelewu.pdf")[0] == "przelew"


def test_unknown_document_is_skipped():
    doctype, result, _ = process_pdf(CASE / "ogloszenie_ted.pdf")
    assert doctype is None and result is None


def test_extraction_matches_reference():
    assert process_pdf(CASE / "odwolanie.pdf")[1] == _gold("odwolanie.json")
    assert process_pdf(CASE / "pelnomocnictwo.pdf")[1] == _gold("pelnomocnictwo.json")
    assert process_pdf(CASE / "potwierdzenie_przelewu.pdf")[1] == _gold("przelew.json")


def test_output_tree_mirrors_input(tmp_path):
    inp, out = tmp_path / "input" / "case1", tmp_path / "output"
    inp.mkdir(parents=True)
    for f in ("odwolanie.pdf", "ogloszenie_ted.pdf"):
        (inp / f).write_bytes((CASE / f).read_bytes())
    n = process_tree(tmp_path / "input", out, None)
    assert n == 1
    assert (out / "case1" / "odwolanie.json").exists()          # ta sama nazwa co PDF
    assert not (out / "case1" / "ogloszenie_ted.json").exists()  # dokument spoza klas pominięty
