"""Walidacja wartości pól – konfigurowana w YAML (klucz pola `checks:` i reguły krzyżowe `cross_checks:`).

Walidacja jest MIĘKKA: nie zmienia wyniku, tylko ustawia polu status `invalid` z opisem (do sprawdzenia przez
człowieka). Dzięki temu np. fikcyjne numery w danych testowych nie obniżają F1, a prawdziwe błędy OCR/ekstrakcji
są widoczne w interfejsie i w śladzie.

Walidatory wbudowane: nip, regon, pesel, iban (suma kontrolna), krs (10 cyfr), date (poprawna data ISO).
Walidatory z YAML (`validators:` w pliku klasy lub w config/validators.yaml):
    nazwa: {regex: '...', message: 'opis'}            – wartość musi pasować do wzorca
    nazwa: {min: 0, max: 100000, message: 'opis'}     – zakres liczby
    nazwa: {in: [a, b, c], message: 'opis'}           – dozwolone wartości
Reguły krzyżowe (`cross_checks:` w pliku klasy), porównanie dwóch pól (daty ISO / liczby / teksty):
    - {left: OdwolanieKIO.czynnosc_dzien, op: "<=", right: OdwolanieKIO.data, message: 'opis'}
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any


def _digits(v: Any) -> str:
    return re.sub(r"\D", "", str(v))


def _weighted(d: str, weights: list[int], mod: int = 11) -> int:
    return sum(int(a) * w for a, w in zip(d, weights)) % mod


def nip(v: Any) -> bool:
    d = _digits(v)
    return len(d) == 10 and _weighted(d, [6, 5, 7, 2, 3, 4, 5, 6, 7]) % 10 == int(d[9])


def regon(v: Any) -> bool:
    d = _digits(v)
    if len(d) == 9:
        return _weighted(d, [8, 9, 2, 3, 4, 5, 6, 7]) % 10 == int(d[8])
    if len(d) == 14:
        return _weighted(d, [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]) % 10 == int(d[13])
    return False


def pesel(v: Any) -> bool:
    d = _digits(v)
    if len(d) != 11:
        return False
    s = sum(int(a) * w for a, w in zip(d, [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]))
    return (10 - s % 10) % 10 == int(d[10])


def iban(v: Any) -> bool:
    d = _digits(v)
    if len(d) != 26:
        return False
    rearranged = d[2:] + "2521" + d[:2]  # "PL" -> 25 21, przeniesione na koniec z cyframi kontrolnymi
    return int(rearranged) % 97 == 1


def krs(v: Any) -> bool:
    return len(_digits(v)) == 10


def iso_date(v: Any) -> bool:
    try:
        date.fromisoformat(str(v))
        return True
    except ValueError:
        return False


BUILTIN = {
    "nip": (nip, "niepoprawna suma kontrolna NIP"),
    "regon": (regon, "niepoprawna suma kontrolna REGON"),
    "pesel": (pesel, "niepoprawna suma kontrolna PESEL"),
    "iban": (iban, "niepoprawna suma kontrolna numeru rachunku (IBAN)"),
    "krs": (krs, "KRS powinien mieć 10 cyfr"),
    "date": (iso_date, "niepoprawna data"),
}


def check(value: Any, names: str | list[str], custom: dict[str, Any] | None = None) -> list[str]:
    """Zwraca listę komunikatów walidacji (pusta = poprawne). Brak wartości nie jest tu sprawdzany."""
    if value is None:
        return []
    out = []
    for name in [names] if isinstance(names, str) else names:
        if custom and name in custom:
            rule = custom[name]
            ok = True
            if "regex" in rule:
                ok = re.fullmatch(rule["regex"], str(value)) is not None
            if ok and ("min" in rule or "max" in rule):
                try:
                    x = float(value)
                    ok = rule.get("min", x) <= x <= rule.get("max", x)
                except (TypeError, ValueError):
                    ok = False
            if ok and "in" in rule:
                ok = value in rule["in"] or str(value) in map(str, rule["in"])
            if not ok:
                out.append(rule.get("message", f"walidacja {name} nie powiodła się"))
        elif name in BUILTIN:
            fn, msg = BUILTIN[name]
            if not fn(value):
                out.append(msg)
        else:
            raise ValueError(f"nieznany walidator: {name}")
    return out


_OPS = {"<=": lambda a, b: a <= b, "<": lambda a, b: a < b, ">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
        "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


def cross_check(rule: dict[str, Any], left: Any, right: Any) -> str | None:
    """Reguła krzyżowa dla dwóch wartości; None = spełniona albo brak którejś wartości."""
    if left is None or right is None:
        return None
    try:
        a, b = (float(left), float(right)) if all(isinstance(x, (int, float)) for x in (left, right)) else (str(left), str(right))
        return None if _OPS[rule["op"]](a, b) else rule.get("message", f"{rule['left']} {rule['op']} {rule['right']} nie jest spełnione")
    except (KeyError, TypeError, ValueError):
        return None
