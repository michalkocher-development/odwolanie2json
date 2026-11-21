"""Imię i nazwisko w mianowniku ("Mateusza Szymańskiego" -> "Mateusz Szymański").

Regexy wycinają osoby w formie z tekstu (np. po "przez", "Pana", "radcę prawnego"), a wzorzec oczekuje mianownika.
Podejście: słownik imion w mianowniku z płcią -> rozpoznanie imienia i płci -> reguły końcówek nazwisk zależne od płci.
Gdy imię jest spoza słownika, a forma wygląda na odmienioną, `needs_model()` zwraca True (engine może poprosić LLM).
"""

from __future__ import annotations

import re

MALE = """Adam Adrian Albert Aleksander Andrzej Antoni Arkadiusz Artur Bartłomiej Bartosz Bogdan Bogusław Bolesław
Borys Cezary Czesław Damian Daniel Dariusz Dawid Dominik Edward Emil Eryk Filip Franciszek Fryderyk Gabriel
Grzegorz Gustaw Henryk Hubert Ignacy Igor Ireneusz Jacek Jakub Jan Janusz Jarosław Jerzy Józef Julian Juliusz
Kacper Kamil Karol Kazimierz Konrad Krystian Krzysztof Leon Leszek Lucjan Łukasz Maciej Maksymilian Marcel Marcin
Marek Marian Mariusz Mateusz Michał Mieczysław Mikołaj Miłosz Nikodem Norbert Oliwer Oskar Patryk Paweł Piotr
Przemysław Radosław Rafał Remigiusz Robert Roman Ryszard Sebastian Seweryn Sławomir Stanisław Stefan Szymon
Tadeusz Tomasz Tymon Tymoteusz Wacław Waldemar Wiesław Wiktor Witold Władysław Włodzimierz Wojciech Zbigniew
Zdzisław Zenon Zygmunt Szczepan Bernard Dionizy Leopold Wincenty Igor Olaf Antoni Bronisław Ludwik Eugeniusz Kajetan Tobiasz Aleks Alan Fabian Ksawery""".split()
FEMALE = """Ada Agata Agnieszka Aleksandra Alicja Amelia Anna Antonina Barbara Beata Bogumiła Bożena Celina Danuta
Dominika Dorota Edyta Elżbieta Emilia Ewa Ewelina Felicja Gabriela Genowefa Grażyna Halina Hanna Helena Irena
Iwona Izabela Jadwiga Janina Joanna Jolanta Józefa Julia Justyna Kamila Karolina Katarzyna Kinga Klaudia Kornelia
Krystyna Laura Lena Lidia Liliana Magdalena Maja Małgorzata Maria Marianna Marta Marzena Milena Monika Natalia
Nikola Olga Oliwia Patrycja Paula Paulina Renata Róża Sabina Sandra Stanisława Sylwia Teresa Urszula Wanda
Weronika Wiesława Wiktoria Zofia Zuzanna Żaneta Anita Adrianna Bogna Daria Diana Ilona Jagoda Lucyna Mirosława
Roksana Wioletta Iga Ewelina Jowita Michalina Ludwika Aurelia Grażyna Elwira Regina Bernadeta Celina Emilia Gertruda""".split()
NOM_MALE, NOM_FEMALE = set(MALE), set(FEMALE)


def _male_forms(nom: str) -> set[str]:
    """Formy zależne imienia męskiego (dopełniacz/biernik -a, celownik -owi, narzędnik -em) – z ruchomym e."""
    stems = {nom}
    if re.search(r"e[kłl]$", nom):  # Marek->Mark-, Paweł->Pawł-, Jacek->Jack-
        stems.add(nom[:-2] + nom[-1])
    if nom.endswith("y"):  # Cezary, Ignacy -> Cezarego, Ignacego
        return {nom[:-1] + "ego", nom[:-1] + "emu", nom + "m"}
    return {s + suf for s in stems for suf in ("a", "owi", "em", "u")}


def _female_forms(nom: str) -> set[str]:
    """Formy zależne imienia żeńskiego na -a: biernik -ę, narzędnik -ą, dopełniacz -y/-i, celownik -ie/-i."""
    if not nom.endswith("a"):
        return set()
    stem = nom[:-1]
    forms = {stem + "ę", stem + "ą", stem + "y", stem + "i", stem + "ie"}
    if stem.endswith("i"):  # Maria -> Marii, Julia -> Julii
        forms.add(stem + "i")
    return forms


FIRST: dict[str, tuple[str, str]] = {}  # forma -> (mianownik, płeć "m"/"f")
for _n in MALE:
    FIRST[_n.lower()] = (_n, "m")
    for _f in _male_forms(_n):
        FIRST.setdefault(_f.lower(), (_n, "m"))
for _n in FEMALE:
    FIRST[_n.lower()] = (_n, "f")
    for _f in _female_forms(_n):
        FIRST.setdefault(_f.lower(), (_n, "f"))

_INFLECTED = re.compile(r"(?:ego|emu|iej|ej|ą|ę|owi|em)$", re.IGNORECASE)


def _surname_nom(s: str, gender: str) -> str:
    low = s.lower()
    if gender == "m":
        for a, b in (("skiego", "ski"), ("ckiego", "cki"), ("dzkiego", "dzki"), ("skiemu", "ski"), ("ckiemu", "cki"),
                     ("skim", "ski"), ("ckim", "cki")):
            if low.endswith(a):
                return s[: -len(a)] + b
        if low.endswith(("iego", "ego")):  # przymiotnikowe: Koniecznego -> Konieczny, Bożego -> Boży
            return s[:-3] + ("" if low.endswith("iego") else "y") if not low.endswith("iego") else s[:-4] + "i"
        if low.endswith(("owi", "em")) and len(s) > 4:  # Nowakowi, Nowakiem -> Nowak
            return s[:-3] if low.endswith("owi") else (s[:-3] if low.endswith("iem") else s[:-2])
        if low.endswith("ę") and len(s) > 3:  # męskie nazwiska na -a w bierniku: Wojnę -> Wojna, Kulę -> Kula
            return s[:-1] + "a"
        if low.endswith("a") and len(s) > 3 and not low.endswith(("ska", "cka", "dzka")):  # Nowaka -> Nowak, Mazura -> Mazur
            return s[:-1]
        return s
    # kobiety: przymiotnikowe -skiej/-ską -> -ska; nazwiska spółgłoskowe (Nowak) są nieodmienne
    for a, b in (("skiej", "ska"), ("ską", "ska"), ("ckiej", "cka"), ("cką", "cka"), ("dzkiej", "dzka"), ("dzką", "dzka")):
        if low.endswith(a):
            return s[: -len(a)] + b
    if low.endswith("iej"):
        return s[:-3] + "a"
    if low.endswith(("ej", "ą")):  # Nowickiej (już wyżej), Ostrej -> Ostra, Wesołą -> Wesoła
        return s[:-2] + "a" if low.endswith("ej") else s[:-1] + "a"
    if low.endswith("ę") and len(s) > 3:  # Kowalę -> Kowala (rzadkie nazwiska na -a)
        return s[:-1] + "a"
    return s


def to_nominative(name: str) -> str:
    """Sprowadź "Imię Nazwisko" do mianownika, jeśli imię jest w słowniku. Inaczej zwróć bez zmian."""
    parts = name.split()
    if len(parts) < 2:
        return name
    first = FIRST.get(parts[0].lower())
    if not first:
        return name
    nom, gender = first
    if parts[0] == nom and not any(_INFLECTED.search(p) for p in parts[1:]) and not (
            gender == "m" and parts[0] != nom):
        # imię w mianowniku -> zakładamy mianownik całości (chroni nazwiska typu "Kula", "Wojna")
        return name
    surnames = [_surname_nom(p, gender) if not p.isupper() else p for p in parts[1:]]
    # nazwisko dwuczłonowe z łącznikiem: Nowak-Kowalskiego -> Nowak-Kowalski
    surnames = ["-".join(_surname_nom(x, gender) for x in s.split("-")) if "-" in s else s for s in surnames]
    return " ".join([nom, *surnames])


def needs_model(name: str) -> bool:
    """Imię spoza słownika, a któreś słowo ma końcówkę przypadku zależnego -> warto zapytać model o mianownik."""
    parts = name.split()
    return len(parts) >= 2 and parts[0].lower() not in FIRST and any(_INFLECTED.search(p) for p in parts)
