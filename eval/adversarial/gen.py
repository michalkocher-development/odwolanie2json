"""Generator adwersaryjnych spraw testowych (PDF + JSON referencyjny), celowo innych niż dane treningowe UZP.

Cel: sprawdzić, czy pipeline działa, gdy regexy nie trafiają (inne etykiety i układy, odmiana nazwisk,
formaty dat/NIP/IBAN/kwot, tabele, angielski bank, konsorcja, rozpraszające daty, brakujące pola).
Struktura wyjścia jak w danych UZP: <out>/przyklad_NN/{odwolanie,pelnomocnictwo,potwierdzenie_przelewu}.pdf + *.json

Użycie: python eval/adversarial/gen.py --out ../tasks/adversarial --n 30 --seed 7
Ewaluacja: python eval/evaluate.py --data ../tasks/adversarial
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

R = random.Random()

# ------------------------------------------------------------------ słowniki (mianownik, dopełniacz/biernik)
MALE_FIRST = [("Jan", "Jana"), ("Piotr", "Piotra"), ("Tomasz", "Tomasza"), ("Marek", "Marka"), ("Krzysztof", "Krzysztofa"),
              ("Paweł", "Pawła"), ("Michał", "Michała"), ("Andrzej", "Andrzeja"), ("Grzegorz", "Grzegorza")]
MALE_LAST = [("Nowak", "Nowaka"), ("Kowalski", "Kowalskiego"), ("Wiśniewski", "Wiśniewskiego"), ("Zieliński", "Zielińskiego"),
             ("Lewandowski", "Lewandowskiego"), ("Kamiński", "Kamińskiego"), ("Dąbrowski", "Dąbrowskiego"), ("Mazur", "Mazura"),
             ("Wójcik", "Wójcika"), ("Krawczyk", "Krawczyka")]
FEMALE_FIRST = [("Anna", "Annę"), ("Maria", "Marię"), ("Katarzyna", "Katarzynę"), ("Małgorzata", "Małgorzatę"),
                ("Agnieszka", "Agnieszkę"), ("Ewa", "Ewę"), ("Joanna", "Joannę"), ("Monika", "Monikę")]
FEMALE_LAST = [("Nowak", "Nowak"), ("Kowalska", "Kowalską"), ("Wiśniewska", "Wiśniewską"), ("Zielińska", "Zielińską"),
               ("Mazur", "Mazur"), ("Kamińska", "Kamińską"), ("Wójcik", "Wójcik"), ("Krawczyk", "Krawczyk")]
CITIES = [("Warszawa", "Warszawie"), ("Kraków", "Krakowie"), ("Gdańsk", "Gdańsku"), ("Wrocław", "Wrocławiu"),
          ("Poznań", "Poznaniu"), ("Łódź", "Łodzi"), ("Lublin", "Lublinie"), ("Katowice", "Katowicach"),
          ("Szczecin", "Szczecinie"), ("Rzeszów", "Rzeszowie"), ("Olsztyn", "Olsztynie"), ("Opole", "Opolu")]
STREETS = ["Lipowa", "Polna", "Leśna", "Słoneczna", "Kościuszki", "Mickiewicza", "Długa", "Ogrodowa", "Kolejowa", "Wiejska"]
CO_A = ["Arkona", "Bastion", "Cedrus", "Delta-Tech", "Ekoform", "Faber", "Granit", "Horyzont", "Iskra", "Jantar", "Kontur",
        "Lumen", "Merkury", "Nordis", "Orion", "Prima", "Quadra", "Rubin", "Sigma", "Tytan", "Unimax", "Vector", "Zenit"]
CO_B = ["Budownictwo", "Systemy IT", "Med", "Logistyka", "Energia", "Serwis", "Infrastruktura", "Technologie", "Usługi Komunalne",
        "Ochrona", "Instalacje", "Dystrybucja"]
FORMS = ["sp. z o.o.", "S.A.", "sp. k.", "sp. j.", "spółka z ograniczoną odpowiedzialnością", "spółka akcyjna", "sp. z o.o. sp. k."]
PUBLIC = ["Gmina {c}", "Szpital Wojewódzki w {l}", "Zarząd Dróg Miejskich w {l}", "Uniwersytet Medyczny w {l}",
          "Miejskie Przedsiębiorstwo Wodociągów w {l} sp. z o.o.", "Powiatowy Zarząd Dróg w {l}", "Teatr Miejski w {l}"]
TITLES = ["Dostawa sprzętu komputerowego dla szkół", "Przebudowa drogi gminnej nr 1203W wraz z odwodnieniem",
          "Świadczenie usług ochrony fizycznej obiektów", "Dostawa energii elektrycznej na lata 2027–2028",
          "Budowa hali sportowej przy Szkole Podstawowej nr 4", "Odbiór i zagospodarowanie odpadów komunalnych",
          "Dostawa leków onkologicznych w podziale na 8 części", "Modernizacja oczyszczalni ścieków – etap II",
          "Usługa sprzątania pomieszczeń biurowych", "Zakup ambulansów sanitarnych typu C"]
MONTHS_GEN = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
              "października", "listopada", "grudnia"]
BANKS = ["Bank Zachodni", "Mazowiecki Bank Spółdzielczy", "Nordbank Polska", "Credit Polonia"]
POWODY = {
    1: ("Decyzja o odrzuceniu oferty", ["odrzucenia oferty Odwołującego", "odrzucenia złożonej przez Odwołującego oferty"],
        ["odrzucił ofertę Odwołującego", "poinformował o odrzuceniu oferty Odwołującego"]),
    2: ("Ogłoszenie wyboru oferty", ["wyboru oferty najkorzystniejszej", "dokonania wyboru oferty wykonawcy {inny}"],
        ["dokonał wyboru oferty najkorzystniejszej", "zawiadomił o wyborze oferty wykonawcy {inny}"]),
    3: ("Decyzja o wykluczeniu wykonawcy", ["wykluczenia Odwołującego z postępowania"],
        ["wykluczył Odwołującego z postępowania"]),
    4: ("Publikacja specyfikacji warunków zamówienia (SWZ)", ["postanowień specyfikacji warunków zamówienia", "treści SWZ w zakresie warunków udziału"],
        ["opublikował specyfikację warunków zamówienia", "udostępnił na platformie SWZ"]),
    5: ("Modyfikacja treści SWZ", ["modyfikacji treści SWZ", "zmiany specyfikacji warunków zamówienia"],
        ["zmodyfikował treść SWZ", "opublikował zmianę specyfikacji warunków zamówienia"]),
    6: ("Odpowiedzi i wyjaśnienia do SWZ", ["udzielonych wyjaśnień treści SWZ", "odpowiedzi na pytania wykonawców do SWZ"],
        ["udzielił odpowiedzi na pytania wykonawców dotyczące SWZ", "opublikował wyjaśnienia treści SWZ"]),
    7: ("Zaniechanie odrzucenia oferty", ["zaniechania odrzucenia oferty wykonawcy {inny}"],
        ["nie odrzucił oferty wykonawcy {inny}, mimo jej niezgodności z warunkami zamówienia"]),
    8: ("Zaniechanie wykluczenia wykonawcy", ["zaniechania wykluczenia wykonawcy {inny}"],
        ["nie wykluczył z postępowania wykonawcy {inny}"]),
    9: ("Decyzja o unieważnieniu postępowania", ["unieważnienia postępowania", "unieważnienia przetargu"],
        ["unieważnił postępowanie", "podjął decyzję o unieważnieniu przetargu"]),
    10: ("Zaniechanie unieważnienia postępowania", ["zaniechania unieważnienia postępowania obarczonego wadą"],
         ["kontynuował postępowanie zamiast je unieważnić, mimo wady niemożliwej do usunięcia"]),
    11: ("Opis przedmiotu zamówienia (OPZ)", ["opisu przedmiotu zamówienia", "wymagań technicznych zawartych w OPZ"],
         ["udostępnił opis przedmiotu zamówienia", "opublikował załącznik nr 1 – OPZ"]),
}


def digits(n: int) -> str:
    return "".join(R.choice("0123456789") for _ in range(n))


def date_rand() -> tuple[int, int, int]:
    return 2026, R.randint(1, 12), R.randint(1, 28)


def iso(d: tuple[int, int, int]) -> str:
    return f"{d[0]:04d}-{d[1]:02d}-{d[2]:02d}"


def fmt_date(d: tuple[int, int, int], style: int | None = None) -> str:
    y, m, dd = d
    style = R.randint(0, 4) if style is None else style
    return [f"{dd} {MONTHS_GEN[m - 1]} {y} r.", f"{dd:02d}.{m:02d}.{y} r.", f"{y}-{m:02d}-{dd:02d}",
            f"{dd:02d}/{m:02d}/{y}", f"{dd} {MONTHS_GEN[m - 1]} {y}"][style]


@dataclass
class Person:
    nom: str
    acc: str  # forma po "Pana/Panią", "przez"
    male: bool


def person() -> Person:
    if R.random() < 0.5:
        (f, fa), (l, la) = R.choice(MALE_FIRST), R.choice(MALE_LAST)
        return Person(f"{f} {l}", f"{fa} {la}", True)
    (f, fa), (l, la) = R.choice(FEMALE_FIRST), R.choice(FEMALE_LAST)
    return Person(f"{f} {l}", f"{fa} {la}", False)


def company() -> dict[str, Any]:
    city = R.choice(CITIES)
    return {"nazwa": f"{R.choice(CO_A)} {R.choice(CO_B)} {R.choice(FORMS)}", "krs": "0000" + digits(6), "nip": digits(10),
            "regon": digits(9), "city": city, "addr": f"ul. {R.choice(STREETS)} {R.randint(1, 120)}, {digits(2)}-{digits(3)} {city[0]}"}


def authority() -> dict[str, Any]:
    city = R.choice(CITIES)
    name = R.choice(PUBLIC).format(c=city[0], l=city[1])
    return {"nazwa": name, "krs": ("0000" + digits(6)) if "sp. z o.o." in name else None, "nip": digits(10),
            "regon": digits(9), "city": city, "addr": f"ul. {R.choice(STREETS)} {R.randint(1, 60)}, {digits(2)}-{digits(3)} {city[0]}"}


def nip_fmt(n: str) -> str:
    return R.choice([n, f"{n[:3]}-{n[3:6]}-{n[6:8]}-{n[8:]}", f"{n[:3]}-{n[3:5]}-{n[5:7]}-{n[7:]}", f"PL{n}", f"{n[:3]} {n[3:6]} {n[6:8]} {n[8:]}"])


def ids_line(e: dict[str, Any]) -> str:
    parts = []
    if e.get("krs"):
        parts.append(R.choice([f"KRS {e['krs']}", f"nr KRS: {e['krs']}", f"wpisana do rejestru przedsiębiorców KRS pod nr {e['krs']}"]))
    parts.append(R.choice(["NIP ", "NIP: ", "nr NIP "]) + nip_fmt(e["nip"]))
    parts.append(R.choice(["REGON ", "REGON: ", "nr REGON "]) + e["regon"])
    R.shuffle(parts)
    return ", ".join(parts)


def iban() -> str:
    return digits(26)


def iban_fmt(a: str) -> str:
    g = " ".join([a[:2]] + [a[i:i + 4] for i in range(2, 26, 4)])
    return R.choice([f"PL{a}", f"PL{g}", a, g, f"PL {g}"])


def amount_fmt(x: float) -> str:
    whole, gr = f"{x:.2f}".split(".")
    w_sp = f"{int(whole):,}".replace(",", " ")
    w_dot = f"{int(whole):,}".replace(",", ".")
    return R.choice([f"{w_sp},{gr} PLN", f"PLN {w_dot},{gr}", f"{whole}.{gr} zł", f"{w_sp},{gr} zł", f"{whole},{gr} PLN"])


# ------------------------------------------------------------------ PDF
CSS = "* {font-family: sans-serif; font-size: 10.5pt; line-height: 1.35;} td {padding: 2px 6px; vertical-align: top;} h2 {font-size: 14pt;}"


def save_pdf(html: str, path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()  # A4; insert_htmlbox w razie potrzeby zmniejsza skalę, by zmieścić treść
    page.insert_htmlbox(pymupdf.Rect(50, 50, 545, 792), html, css=CSS)
    doc.save(path)
    doc.close()


# ------------------------------------------------------------------ odwołanie
def gen_odwolanie(case: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    odw, zam, pel = case["odwolujacy"], case["zamawiajacy"], case["pelnomocnik"]
    city_nom, city_loc = R.choice(CITIES)
    hdr_date = date_rand()
    header_style = R.randint(0, 4)
    if header_style == 4:  # brak miejscowości i daty w nagłówku
        header, g_data, g_city = "", None, None
    else:
        header = [f"{city_nom}, {fmt_date(hdr_date, 0)}", f"{city_nom}, dn. {fmt_date(hdr_date, 1)}",
                  f"{city_nom} {fmt_date(hdr_date, 3)}", f"Sporządzono w {city_loc}, dnia {fmt_date(hdr_date, 4)}"][header_style]
        g_data, g_city = iso(hdr_date), city_nom

    # strony
    def party_odw() -> str:
        if case["konsorcjum"]:
            lider, partner = odw, case["partner"]
            body = (f"Konsorcjum w składzie: <b>{partner['nazwa']}</b> ({ids_line(partner)}) oraz "
                    f"<b>{lider['nazwa']}</b> – Lider Konsorcjum ({ids_line(lider)}), {lider['addr']}")
        else:
            body = f"<b>{odw['nazwa']}</b>, {odw['addr']}<br>{ids_line(odw)}"
        if pel:
            p = pel["osoba"]
            tit = R.choice(["adw.", "radca prawny", "r.pr.", "mec.", ""])
            rep = R.choice([
                f"Pełnomocnik: {tit} {p.nom}, {pel['kancelaria']}, {pel['addr']}, e-mail: {pel['mail']}",
                f"reprezentowany przez {'radcę prawnego' if tit in ('radca prawny', 'r.pr.') else 'adwokata'} {p.acc} "
                f"({pel['kancelaria']}); adres e-mail do doręczeń: {pel['mail']}",
                f"działający przez pełnomocnika – {p.nom} ({pel['kancelaria']}, {pel['mail']})",
            ])
            body += "<br>" + rep
        label = R.choice(["Odwołujący:", "ODWOŁUJĄCY", "Wykonawca wnoszący odwołanie:", "Strona odwołująca –", "Odwołujący"])
        return f"<p><b>{label}</b><br>{body}</p>"

    def party_zam() -> str:
        out = []
        multi = len(zam) > 1
        for i, z in enumerate(zam):
            lab = ""
            if multi:
                lab = " (Zamawiający prowadzący postępowanie)" if i == 0 else " (Zamawiający wspólnie udzielający zamówienia)"
            out.append(f"<b>{z['nazwa']}</b>{lab}, {z['addr']}<br>{ids_line(z)}")
        label = R.choice(["Zamawiający:", "ZAMAWIAJĄCY", "Instytucja zamawiająca:", "Zamawiający (strona przeciwna):"])
        return f"<p><b>{label}</b><br>" + "<br>".join(out) + "</p>"

    parties = [party_odw(), party_zam()]
    if R.random() < 0.5:
        parties.reverse()
    if R.random() < 0.3:  # układ tabelaryczny
        parties = [f"<table border='1' style='border-collapse:collapse'><tr><td>{parties[0]}</td><td>{parties[1]}</td></tr></table>"]

    # zamówienie
    zp = case["zamowienie"]
    title_q = R.choice([f"„{zp['tytul']}”", f"«{zp['tytul']}»", f"\"{zp['tytul']}\"", zp["tytul"]])
    ref = R.choice(["znak sprawy:", "Numer referencyjny:", "sygn.", "nr postępowania", "Znak postępowania –"]) + f" {zp['numer']}"
    nums = [ref]
    if zp["bzp_raw"]:
        nums.append(R.choice(["ogłoszenie w BZP nr ", "Biuletyn Zamówień Publicznych: ", "nr ogłoszenia (BZP): "]) + zp["bzp_raw"])
    if zp["ted_raw"]:
        nums.append(R.choice(["ogłoszenie w Dz. Urz. UE ", "nr ogłoszenia TED: ", "publikacja w Dzienniku Urzędowym UE nr "]) + zp["ted_raw"])
    R.shuffle(nums)
    zp_block = R.choice([
        f"<p>w postępowaniu o udzielenie zamówienia publicznego pod nazwą {title_q} ({'; '.join(nums)})</p>",
        f"<p><b>Przedmiot zamówienia:</b> {title_q}<br>" + "<br>".join(nums) + "</p>",
        f"<p>Sprawa: postępowanie prowadzone w trybie podstawowym na: {title_q}. {'. '.join(nums)}.</p>",
    ])

    # czynność i zarzuty (+ rozpraszacz)
    pid = case["powod_id"]
    opis, nouns, verbs = POWODY[pid]
    inny = case["inny"]
    act_date = case["czynnosc_dzien"]
    noun = R.choice(nouns).format(inny=inny)
    verb = R.choice(verbs).format(inny=inny)
    dis_id = R.choice([k for k in POWODY if k != pid])
    dis_noun = R.choice(POWODY[dis_id][1]).format(inny=inny)
    dis_date = date_rand()
    sentence = R.choice([
        f"W dniu {fmt_date(act_date)} Zamawiający {verb}.",
        f"Dnia {fmt_date(act_date)} Odwołujący powziął wiadomość o czynności Zamawiającego polegającej na {noun.replace('odrzucenia', 'odrzuceniu').replace('wyboru', 'wyborze')}.",
        f"Informację o czynności ({noun}) Zamawiający przekazał wykonawcom {fmt_date(act_date)}.",
    ])
    distract = f"Wcześniej, {fmt_date(dis_date)}, Zamawiający wezwał wykonawców do przedłużenia terminu związania ofertą."
    z1 = R.choice([f"Zarzut nr 1 – naruszenie art. {R.randint(16, 255)} ustawy Pzp poprzez dokonanie {noun}",
                   f"I. ZARZUT PIERWSZY: zaskarżam czynność {noun}",
                   f"1) naruszenie art. {R.randint(16, 255)} Pzp przez czynność {noun}"])
    z2 = R.choice([f"Zarzut nr 2 – naruszenie art. 16 Pzp w związku z {dis_noun}", f"II. ZARZUT DRUGI: {dis_noun}",
                   f"2) naruszenie art. 16 Pzp w zw. z {dis_noun}"])
    zarzuty = f"<p>{sentence} {distract}</p><p>Odwołujący zarzuca Zamawiającemu:</p><p>{z1};<br>{z2}.</p>"
    filler = ("<p>Uzasadnienie. " + " ".join(["Odwołujący wskazuje, że czynność Zamawiającego narusza zasadę uczciwej konkurencji "
                                              "oraz równego traktowania wykonawców, co ma istotny wpływ na wynik postępowania."] * 4) + "</p>")
    html = (f"<p style='text-align:right'>{header}</p>"
            "<p style='text-align:right'>Krajowa Izba Odwoławcza<br>ul. Postępu 17a, 02-676 Warszawa</p>"
            + "".join(parties) + "<h2 style='text-align:center'>ODWOŁANIE</h2>" + zp_block + zarzuty + filler)

    gold = {
        "OdwolanieKIO": {"data": g_data, "czynnosc_dzien": iso(act_date), "czynnosc_powod_id": pid, "czynnosc_opis": opis,
                         "miejscowosc": g_city},
        "Odwolujacy": [{"krs": odw["krs"], "nazwa": odw["nazwa"], "nip": odw["nip"], "regon": odw["regon"],
                        "przez-pelnomocnika": 1 if pel else 0,
                        "pelnomocnik": {"imie_nazwisko": pel["osoba"].nom if pel else None,
                                        "nazwa": pel["kancelaria"] if pel else None, "mail": pel["mail"] if pel else None}}],
        "Zamawiajacy": [{"krs": z["krs"], "nazwa": z["nazwa"], "nip": z["nip"], "regon": z["regon"],
                         "prowadzacy_postepowanie": (1 if i == 0 else 0) if len(zam) > 1 else None} for i, z in enumerate(zam)],
        "ZamowieniePubliczne": {"numer_bzp": zp["bzp"], "numer_postepowania": zp["numer"], "numer_ted": zp["ted"], "tytul": zp["tytul"]},
    }
    return html, gold


# ------------------------------------------------------------------ pełnomocnictwo
def gen_pelnomocnictwo(case: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    city_nom, _ = R.choice(CITIES)
    d = case["data_pelnomocnictwa"]
    mocodawcy = [case["odwolujacy"]] + ([case["partner"]] if case["konsorcjum"] else [])
    pels = case["pelnomocnicy"]
    fiz = case["mocodawca_fizyczny"]
    blocks, gold_m = [], []
    for m in mocodawcy:
        signers = [person() for _ in range(R.randint(1, 2))]
        m["_signers"] = signers
        if fiz and m is case["odwolujacy"] and not case["konsorcjum"]:
            p = fiz
            blocks.append(R.choice([
                f"Ja, {p.nom}, prowadzący działalność gospodarczą pod firmą {m['nazwa']} ({ids_line({**m, 'krs': None})})",
                f"{p.nom}, przedsiębiorca wpisany do CEIDG, działający pod firmą {m['nazwa']}, NIP {nip_fmt(m['nip'])}",
            ]))
            m["_signers"] = [p]
            gold_m.append({"data": {"imie_nazwisko": p.nom, "krs": None, "nazwa": m["nazwa"], "nip": m["nip"], "typ": "osoba_fizyczna"},
                           "podpisujacy": [{"imie_nazwisko": p.nom}]})
            continue
        blocks.append(R.choice([
            f"{m['nazwa']} z siedzibą w {m['city'][1]} ({ids_line(m)})",
            f"spółka {m['nazwa']}, {m['addr']}, {ids_line(m)}",
            f"Ja, niżej {'podpisany' if signers[0].male else 'podpisana'} {signers[0].nom}, działając w imieniu {m['nazwa']} ({ids_line(m)})",
        ]))
        gold_m.append({"data": {"imie_nazwisko": None, "krs": m["krs"], "nazwa": m["nazwa"], "nip": m["nip"], "typ": "osoba_prawna"},
                       "podpisujacy": [{"imie_nazwisko": s.nom} for s in signers]})

    def pel_txt(p: Person, pesel: str | None) -> str:
        pz = f", PESEL {pesel}" if pesel else ""
        return R.choice([f"{'Pana' if p.male else 'Panią'} {p.acc}{pz}",
                         f"{R.choice(['adw.', 'r. pr.', 'radcę prawnego', 'aplikanta adwokackiego'])} {p.acc if R.random() < 0.5 else p.nom}{pz}",
                         f"{p.nom}{pz} (nr wpisu {R.choice(['WA', 'KR', 'GD'])}-{digits(4)})"])

    pel_list = ", ".join(pel_txt(p, pesel) for p, pesel in pels)
    mocod = " oraz ".join(blocks)
    grant = R.choice([f"{mocod} niniejszym {'udzielają' if len(blocks) > 1 else 'udziela'} pełnomocnictwa: {pel_list}",
                      f"{mocod} ustanawia{'ją' if len(blocks) > 1 else ''} pełnomocnikiem {pel_list}",
                      f"Mocodawca: {mocod}.<br>Pełnomocnik/pełnomocnicy: {pel_list}."])
    scope = (f"<p>do reprezentowania w postępowaniu odwoławczym przed Krajową Izbą Odwoławczą dotyczącym zamówienia "
             f"„{case['zamowienie']['tytul']}” (znak: {case['zamowienie']['numer']}), w tym do wniesienia odwołania, "
             f"udziału w rozprawach i składania oświadczeń.</p>")
    sig_rows = []
    for m in mocodawcy:
        for s in m["_signers"]:
            role = R.choice(["Prezes Zarządu", "Członek Zarządu", "Prokurent", "Wspólnik", "Właściciel"])
            sig_rows.append(R.choice([f"<tr><td>{s.nom}</td><td>{role}</td><td>……………</td></tr>",
                                      f"<tr><td>{role} – {s.nom}</td><td>(podpis elektroniczny)</td></tr>"]))
    sig = ("<p>Za Mocodawcę:</p><table>" + "".join(sig_rows) + "</table>") if not fiz or case["konsorcjum"] else \
        f"<p>Podpis Mocodawcy:</p><p>{fiz.nom}</p>"
    html = (f"<p style='text-align:right'>{city_nom}, {fmt_date(d)}</p><h2 style='text-align:center'>"
            f"{R.choice(['PEŁNOMOCNICTWO', 'Pełnomocnictwo procesowe', 'P E Ł N O M O C N I C T W O'])}</h2>"
            f"<p>{grant}</p>{scope}{sig}")
    gold = {"mocodawca": gold_m, "pelnomocnicy": [{"imie_nazwisko": p.nom, "pesel": pesel} for p, pesel in pels]}
    return html, gold


# ------------------------------------------------------------------ przelew
def gen_przelew(case: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    payer, rec = case["odwolujacy"], case["zamawiajacy"][0]
    z, na = iban(), iban()
    amt = R.choice([34.0, 17.0, 100.0, 7500.0, 10000.0, 15000.0, 20000.0, 1234.56])
    d = date_rand()
    ref = None if R.random() < 0.15 else R.choice(["TRX", "PMT", "ELX", ""]) + digits(R.randint(10, 14))
    tytul = R.choice([f"Wpis od odwołania – {case['zamowienie']['numer']}",
                      f"opłata skarbowa od pełnomocnictwa {case['zamowienie']['numer']}",
                      f"WPIS KIO {case['zamowienie']['tytul'][:40].upper()}"])
    bank = R.choice(BANKS)
    style = R.randint(0, 3)
    if style == 0:  # bank po angielsku
        rows = [("Ordering party", payer["nazwa"]), ("Debit account", iban_fmt(z)), ("Beneficiary", rec["nazwa"]),
                ("Beneficiary account", iban_fmt(na)), ("Amount", amount_fmt(amt)), ("Execution date", fmt_date(d, R.choice([2, 3]))),
                ("Payment details", tytul)] + ([("Reference no.", ref)] if ref else [])
        html = f"<h2>{bank} – Transfer confirmation</h2><table border='1' style='border-collapse:collapse'>" + \
            "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in rows) + "</table><p>Status: COMPLETED</p>"
    elif style == 1:  # list z banku (proza)
        html = (f"<p>{bank}</p><h2>Zaświadczenie o wykonaniu dyspozycji</h2><p>Niniejszym potwierdzamy, że dnia {fmt_date(d)} "
                f"z rachunku {iban_fmt(z)} należącego do {payer['nazwa']} obciążono kwotą {amount_fmt(amt)} na rzecz "
                f"{rec['nazwa']} – rachunek beneficjenta {iban_fmt(na)}. Tytułem: „{tytul}”."
                + (f" Identyfikator dyspozycji: {ref}." if ref else "") + "</p>")
    elif style == 2:  # wyciąg jednolinijkowy
        html = (f"<h2>Historia rachunku – {bank}</h2><table border='1' style='border-collapse:collapse'>"
                "<tr><td>Data księgowania</td><td>Opis</td><td>Kontrahent / rachunek</td><td>Kwota</td></tr>"
                f"<tr><td>{fmt_date(d, R.choice([1, 2, 3]))}</td><td>{tytul}" + (f" ref. {ref}" if ref else "") +
                f"</td><td>{rec['nazwa']}<br>{iban_fmt(na)}</td><td>-{amount_fmt(amt)}</td></tr></table>"
                f"<p>Rachunek: {iban_fmt(z)} ({payer['nazwa']})</p>")
    else:  # klasyczny, ale nowe etykiety
        html = (f"<h2>Potwierdzenie transakcji</h2><p>Nadawca: {payer['nazwa']}<br>Konto nadawcy: {iban_fmt(z)}<br>"
                f"Odbiorca: {rec['nazwa']}<br>Konto odbiorcy: {iban_fmt(na)}<br>Wartość transakcji: {amount_fmt(amt)}<br>"
                f"Data waluty: {fmt_date(d)}<br>Opis płatności: {tytul}<br>" + (f"Nr dyspozycji: {ref}" if ref else "") + "</p>")
    gold = {"przelew_bankowy": {"data_operacji": iso(d), "kwota": amt, "na_rachunek": na, "numer_transakcji": ref,
                                "tytul": tytul, "z_rachunku": z}}
    return html, gold


# ------------------------------------------------------------------ sprawa
def gen_case() -> dict[str, Any]:
    konsorcjum = R.random() < 0.2
    zam = [authority()] + ([authority()] if R.random() < 0.2 else [])
    pel = None if R.random() < 0.15 else {
        "osoba": person(), "mail": f"{R.choice(['biuro', 'kancelaria', 'kontakt', 'zp'])}@{R.choice(CO_A).lower()}-legal.example",
        "kancelaria": R.choice(["Kancelaria Adwokacka ", "Kancelaria Radcy Prawnego ", "Legal Partners "]) + R.choice(CO_A)
        + R.choice([" sp. k.", " sp.p.", ""]),
        "addr": f"ul. {R.choice(STREETS)} {R.randint(1, 50)}, {R.choice(CITIES)[0]}"}
    ted_n, bzp_n = digits(6), digits(8)
    bzp_style = R.random()
    bzp_raw = None if bzp_style < 0.2 else R.choice([f"2026/BZP {bzp_n}", f"2026/BZP{bzp_n}", f"2026/BZP {bzp_n}/01"])
    bzp = None if bzp_raw is None else bzp_raw.replace(" ", "")
    ted_raw = None if R.random() < 0.4 else R.choice([f"2026/S {R.randint(1, 250):03d}-{ted_n}", f"{ted_n}-2026"])
    numer = R.choice([f"ZP.271.{R.randint(1, 99)}.2026", f"DZP/{R.randint(1, 300)}/2026", f"SZW-{digits(3)}/26", f"IR.272.{R.randint(1, 30)}.2026.AK"])
    odw = company()
    fiz = person() if (R.random() < 0.15 and not konsorcjum) else None
    if fiz:
        odw["nazwa"] = f"{R.choice(CO_A).upper()} {fiz.nom}"
        odw["krs"] = None
    return {
        "odwolujacy": odw, "partner": company() if konsorcjum else None, "konsorcjum": konsorcjum, "zamawiajacy": zam,
        "pelnomocnik": pel, "powod_id": R.randint(1, 11), "czynnosc_dzien": date_rand(),
        "inny": f"{R.choice(CO_A)} {R.choice(CO_B)} {R.choice(FORMS)}",
        "zamowienie": {"tytul": R.choice(TITLES), "numer": numer, "bzp_raw": bzp_raw, "bzp": bzp, "ted_raw": ted_raw,
                       "ted": None if ted_raw is None else f"{ted_n}-2026"},
        "data_pelnomocnictwa": date_rand(),
        "pelnomocnicy": [((pel["osoba"] if (pel and i == 0) else person()), digits(11) if R.random() < 0.25 else None)
                         for i in range(R.randint(1, 2))],
        "mocodawca_fizyczny": fiz,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[3] / "tasks/adversarial")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    R.seed(a.seed)
    for i in range(1, a.n + 1):
        case = gen_case()
        d = a.out / f"przyklad_{i:02d}"
        d.mkdir(parents=True, exist_ok=True)
        for name, fn, pdf in [("odwolanie", gen_odwolanie, "odwolanie.pdf"), ("pelnomocnictwo", gen_pelnomocnictwo, "pelnomocnictwo.pdf"),
                              ("przelew", gen_przelew, "potwierdzenie_przelewu.pdf")]:
            html, gold = fn(case)
            save_pdf(html, d / pdf)
            (d / f"{name}.json").write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wygenerowano {a.n} spraw w {a.out}")


if __name__ == "__main__":
    main()
