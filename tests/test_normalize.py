import pytest

from app import normalize as n


@pytest.mark.parametrize("raw, expected", [
    ("19 października 2026 r.", "2026-10-19"),
    ("05.03.2026", "2026-03-05"),
    ("2026-07-04", "2026-07-04"),
    ("04-07-2026", "2026-07-04"),
    ("4/7/2026", "2026-07-04"),
    ("32.01.2026", None),
    ("bez daty", None),
])
def test_date(raw, expected):
    assert n.date(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("15 000,00 zł", 15000.0),
    ("PLN 1.234,56", 1234.56),
    ("17.00 PLN", 17.0),
    ("34,00", 34.0),
])
def test_amount(raw, expected):
    assert n.amount(raw) == expected


def test_account_strips_country_code_and_spaces():
    assert n.account("PL61 1090 1014 0000 0712 1981 2874") == "61109010140000071219812874"


@pytest.mark.parametrize("raw, expected", [
    ("2026/S 187-999584", "999584-2026"),
    ("641651-2025", "641651-2025"),
])
def test_ted(raw, expected):
    assert n.ted(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("października 2026 r. PEŁNOMOCNICTWO Valtrix Systemy sp. z o.o.", "Valtrix Systemy sp. z o.o."),
    ("Bastion Dystrybucja sp. z o.o., ul. Długa 114, 18-365 Lublin", "Bastion Dystrybucja sp. z o.o."),
    ("Gmina Olsztyn (Zamawiający prowadzący postępowanie)", "Gmina Olsztyn"),
    ("FAMBUD", "FAMBUD"),
])
def test_company(raw, expected):
    assert n.company(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("r. pr. Mateusza Szymańskiego", "Mateusz Szymański"),
    ("radcę prawnego Tomasza Lewandowskiego", "Tomasz Lewandowski"),
    ("Panią Katarzynę Nowak", "Katarzyna Nowak"),
    ("adw. Cezary Kaczmark", "Cezary Kaczmark"),
])
def test_person_strips_titles_and_returns_nominative(raw, expected):
    assert n.person(raw) == expected


def test_apply_chain_stops_on_none():
    assert n.apply("brak", ["date", "strip"]) is None
    assert n.apply(" 9999 284 065 ", "digits") == "9999284065"


def test_ocr_redaction_marker_removed():
    assert n.apply("[X] Spółka z o.o.", "company") == "Spółka z o.o."
    assert n.apply("[X] [X]", "company") is None
