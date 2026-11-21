"""Walidacja, normalizatory i reguły krzyżowe definiowane w YAML (bez zmian w kodzie)."""

import yaml

from app import engine, normalize, validate
from app.status import field_status

SPEC = yaml.safe_load(r"""
name: walidacja_demo
normalizers:
  sygnatura: [{use: strip}, {upper: true}, {replace: ['\s+', '']}]
validators:
  sygn_format: {regex: 'KIO/\d+/\d{2}', message: "sygnatura w formacie KIO/nr/rr"}
cross_checks:
  - {left: wplyw, op: "<=", right: rozprawa, message: "rozprawa przed wpływem odwołania"}
output:
  sygnatura: {regex: 'sygn\.\s*(.+)', normalize: sygnatura, checks: [sygn_format]}
  nip: {regex: 'NIP\s*(\d{10})', checks: [nip]}
  wplyw: {regex: 'wpływ:\s*(\S+)', normalize: date, checks: [date]}
  rozprawa: {regex: 'rozprawa:\s*(\S+)', normalize: date}
""")


def _run(text):
    result, trace = engine.extract(text, SPEC)
    warnings = {t["field"]: t["warnings"] for t in trace if t.get("warnings")}
    return result, field_status(SPEC["output"], result, warnings)


def test_yaml_normalizer_and_valid_values():
    result, st = _run("sygn. kio/123/26\nNIP 5262239325\nwpływ: 2026-05-01\nrozprawa: 2026-05-20")
    assert result["sygnatura"] == "KIO/123/26"
    assert all(s["status"] == "found" for s in st.values())


def test_invalid_values_are_kept_but_flagged():
    result, st = _run("sygn. XYZ\nNIP 5262239326\nwpływ: 2026-05-20\nrozprawa: 2026-05-01")
    assert result["nip"] == "5262239326"                        # walidacja miękka – wartość zostaje
    assert st["nip"] == {"status": "invalid", "note": "niepoprawna suma kontrolna NIP"}
    assert st["sygnatura"]["note"] == "sygnatura w formacie KIO/nr/rr"
    assert st["wplyw"]["note"] == "rozprawa przed wpływem odwołania"  # reguła krzyżowa


def test_builtin_checksums():
    assert validate.nip("5262239325") and not validate.nip("5262239326")
    assert validate.iban("61109010140000071219812874")
    assert validate.pesel("44051401359") and not validate.pesel("44051401358")


def test_step_normalizer_map_and_template():
    custom = {"kanal": [{"map": {"poczta elektroniczna": "e-mail"}}], "pl": [{"template": "PL{value}"}]}
    assert normalize.apply("Poczta elektroniczna", "kanal", custom) == "e-mail"
    assert normalize.apply("61109010140000071219812874", "pl", custom) == "PL61109010140000071219812874"
