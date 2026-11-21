"""Normalizatory wartości. Nazwy używane w YAML: `normalize: date` itd."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

MONTHS = {
    "stycznia": 1, "styczeń": 1, "lutego": 2, "luty": 2, "marca": 3, "marzec": 3,
    "kwietnia": 4, "kwiecień": 4, "maja": 5, "maj": 5, "czerwca": 6, "czerwiec": 6,
    "lipca": 7, "lipiec": 7, "sierpnia": 8, "sierpień": 8, "września": 9, "wrzesień": 9,
    "października": 10, "październik": 10, "listopada": 11, "listopad": 11,
    "grudnia": 12, "grudzień": 12,
}

TITLES = re.compile(
    r"^(?:(?:r\.\s?pr\.|radc[ay]\s+prawn[ya]|adw\.|adwokat|apl\.\s?(?:adw|radc)\.?|"
    r"mec\.|dr|hab\.|prof\.|pan[iy]?|mgr)\s+)+",
    re.IGNORECASE,
)


def ws(v: str) -> str:
    """Zwija białe znaki (w tym łamania linii) do pojedynczych spacji."""
    return re.sub(r"\s+", " ", v).strip()


def date(v: str) -> str | None:
    v = ws(v).lower()
    if m := re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", v):
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
    elif m := re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", v):
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
    elif m := re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", v):
        mo = MONTHS.get(m[2], 0)
        d, y = int(m[1]), int(m[3])
    else:
        return None
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def digits(v: str) -> str | None:
    d = re.sub(r"\D", "", v)
    return d or None


def account(v: str) -> str | None:
    d = re.sub(r"\D", "", v.upper().replace("PL", ""))
    return d if len(d) == 26 else (d or None)


def amount(v: str) -> float | None:
    v = re.sub(r"[^\d,.]", "", v.replace(" ", ""))
    if "," in v:  # format polski: 15.000,00 / 15 000,00
        v = v.replace(".", "").replace(",", ".")
    try:
        return round(float(v), 2)
    except ValueError:
        return None


def nospace(v: str) -> str:
    return re.sub(r"\s+", "", v)


def ted(v: str) -> str | None:
    v = nospace(v)
    if m := re.search(r"(\d{4})/S\d{1,3}-(\d{6})", v):
        return f"{m[2]}-{m[1]}"
    if m := re.search(r"(\d{6})-(\d{4})", v):
        return f"{m[1]}-{m[2]}"
    return None


def person(v: str) -> str:
    """Imię i nazwisko bez tytułów zawodowych."""
    return TITLES.sub("", ws(v)).strip(" ,;.")


_COMPANY_JUNK = re.compile(
    r"^(?:(?:P\s?E\s?Ł\s?N\s?O\s?M\s?O\s?C\s?N\s?I\s?C\s?T\s?W\s?O|Pełnomocnictwo|PROCESOWE|MOCODAWCA|PEŁNOMOCNIK|"
    r"Mocodawca|dnia|r\.|roku|\d[\d.\-/]*|" + "|".join(MONTHS) + r"|[A-ZŁŚŻ])[\s,:]+)+",
)


def company(v: str) -> str:
    """Nazwa podmiotu bez śmieci z nagłówka (tytuł dokumentu, data) przed właściwą nazwą."""
    return _COMPANY_JUNK.sub("", ws(v)).strip(" ,;:")


def strip_punct(v: str) -> str | None:
    v = ws(v.replace("[X]", "")).strip(" ,;:")  # [X] = fragment zamazany (OCR anonimizowanych skanów)
    return v or None


def to_int(v: Any) -> int | None:
    try:
        return int(re.sub(r"\D", "", str(v)))
    except ValueError:
        return None


NORMALIZERS: dict[str, Callable[[Any], Any]] = {
    "ws": ws,
    "date": date,
    "digits": digits,
    "account": account,
    "amount": amount,
    "nospace": nospace,
    "ted": ted,
    "person": person,
    "strip": strip_punct,
    "company": company,
    "int": to_int,
}


def apply(value: Any, names: str | list[str] | None) -> Any:
    if value is None or names is None:
        return value
    for name in [names] if isinstance(names, str) else names:
        value = NORMALIZERS[name](value)
        if value is None:
            return None
    return value
