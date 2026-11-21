"""Nowa klasa dokumentu dodana wyłącznie plikiem YAML (config/doctypes_examples/kopia_odwolania.yaml)."""

import json
from pathlib import Path

import pytest
import yaml

from app import engine
from app.pdf_text import pdf_to_texts

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load((ROOT / "config/doctypes_examples/kopia_odwolania.yaml").read_text(encoding="utf-8"))
SAMPLES = sorted((ROOT / "docs/examples/kopia_odwolania").glob("*.pdf"))


@pytest.mark.parametrize("pdf", SAMPLES, ids=lambda p: p.name)
def test_yaml_only_class_extracts_samples(pdf):
    text, _, flow = pdf_to_texts(pdf)
    result, _ = engine.extract(text, SPEC, alt_text=flow)
    gold = json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
    assert {k: result[k] for k in gold} == gold
