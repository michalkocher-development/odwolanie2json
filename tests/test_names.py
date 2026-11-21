import pytest

from app.names import needs_model, to_nominative


@pytest.mark.parametrize("raw, expected", [
    ("Mateusza Szymańskiego", "Mateusz Szymański"),
    ("Jana Nowaka", "Jan Nowak"),
    ("Annę Zielińską", "Anna Zielińska"),
    ("Anny Kowalskiej", "Anna Kowalska"),
    ("Marka Mazura", "Marek Mazur"),
    ("Pawła Wójcika", "Paweł Wójcik"),
    ("Cezarego Walczaka", "Cezary Walczak"),
    ("Jacka Koniecznego", "Jacek Konieczny"),
    ("Katarzynę Nowak", "Katarzyna Nowak"),           # nazwisko żeńskie spółgłoskowe – nieodmienne
    ("Juliana Wojnę", "Julian Wojna"),                # męskie nazwisko na -a
    ("Piotra Nowak-Kowalskiego", "Piotr Nowak-Kowalski"),
])
def test_inflected_to_nominative(raw, expected):
    assert to_nominative(raw) == expected


@pytest.mark.parametrize("name", ["Mateusz Szymański", "Magdalena Wróblewska", "Jan Kula", "Anna Kowalska-Nowak"])
def test_nominative_is_left_untouched(name):
    assert to_nominative(name) == name


def test_unknown_first_name_is_flagged_for_model():
    assert needs_model("Xawery Nowakowi")
    assert not needs_model("Jan Nowak")
