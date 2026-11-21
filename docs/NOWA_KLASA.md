# Jak dodać nową klasę dokumentu (bez zmian w kodzie)

Klasa dokumentu to jeden plik `config/doctypes/<nazwa>.yaml`. Silnik (`app/engine.py`) wczytuje wszystkie pliki
z tego katalogu przy starcie. Gotowy, działający przykład: `config/doctypes_examples/kopia_odwolania.yaml`
(potwierdzenie przekazania kopii odwołania) z dokumentami testowymi w `docs/examples/kopia_odwolania/`.

## Krok po kroku

1. **Zbierz 2–3 przykładowe PDF-y** i przygotuj dla nich oczekiwany JSON (jak w `docs/examples/kopia_odwolania/*.json`).
2. **Skopiuj szablon**: `config/doctypes_examples/kopia_odwolania.yaml` → `config/doctypes/<nazwa>.yaml`, zmień `name`.
3. **Klasyfikacja** (`classify`): słowa kluczowe z wagami (`keywords`, regexy), słowa wykluczające (`negative`),
   próg `min_score`, podpowiedź z nazwy pliku (`filename_hints`) i `description` – zdanie opisujące klasę, którego używa
   model decyzyjny, gdy słowa kluczowe nie wystarczą.
4. **Struktura wyniku** (`output`): drzewo YAML odwzorowuje strukturę JSON. Liść = pole (opisany kluczami poniżej),
   słownik = obiekt zagnieżdżony, lista z jednym szablonem = lista obiektów.
5. **Dla każdego pola**: regex (jeśli format jest stały) + normalizator; `llm: "opis"` jako zapas dla pól tekstowych;
   `jev:` dla pól-wyborów; `absent_ok` / `applies_if` dla pól, które mogą być puste.
6. **Sprawdź** na przykładach:
   ```bash
   python -m app --input <katalog_z_przykładami> --output out --trace trace
   ```
   i przejrzyj `trace/` (metoda i cytat dla każdego pola) albo wgraj PDF w interfejsie web.
7. **Dodaj test** (wzór: `tests/test_example_class.py`) i uruchom `pytest`.

## Referencja kluczy pola (liścia)

| klucz | znaczenie | przykład |
|---|---|---|
| `scope` | sekcja (`sections`), `head` (początek dokumentu) lub `all` | `scope: naglowek` |
| `within` | zawężenie tekstu do dopasowania regexu (lista = sklejenie kilku fragmentów) | `within: 'Zarzut\s+nr\s*1[^\n]*'` |
| `regex` | wzorzec lub lista wzorców (pierwsze trafienie wygrywa); `{pattern, nth}` = n-te trafienie | `regex: 'KRS\D{0,25}?(\d{10})'` |
| `group`, `ci` | numer grupy; rozróżnianie wielkości liter (`ci: false`) | `group: 2` |
| `normalize` | normalizator lub lista: `date`, `amount`, `account`, `digits`, `ted`, `nospace`, `company`, `person`, `strip`, `ws`, `int` | `normalize: date` |
| `validate` | regex, który musi spełnić wartość po normalizacji | `validate: '\d{10}'` |
| `rules` | lista `{pattern, value}` – pierwsza pasująca reguła daje wartość | zob. przykład |
| `from` + `enum` | wartość ze słownika `enums` na podstawie innego pola | `{from: sposob_id, enum: sposoby}` |
| `take: item` | tekst bieżącego elementu listy | w szablonie listy |
| `const`, `default`, `default_if_many` | stała; wartość domyślna; domyślna, gdy lista ma >1 element | `default: 0` |
| `candidates` | wszystkie dopasowania luźnego wzorca w zakresie; 1 -> bierzemy, kilka -> wybór modelem decyzyjnym (`question`, `none`); `within_line`, `exclude`, `nominative`, własny `scope` | data z nagłówka |
| `jev` | model decyzyjny: wybór z `enum` (`question`, `other`, `min_prob`, `fallback_scope`); `prefer: jev` = model przed regułami | powód odwołania |
| `select_one` | w liście >1 elementu model wskazuje jeden element (1), reszta 0 (`question`, `label`, `none`) | zamawiający prowadzący |
| `llm` | opis pola dla LLM – wywoływany tylko dla pustych pól; wynik musi być ugruntowany w tekście | `llm: "Tytuł zamówienia"` |
| `llm_grounding` | `exact` (domyślnie) lub `stem` (osoby, odmiana; automatycznie dla `normalize: person`) | |
| `verify` | opis do weryfikacji wartości modelem decyzyjnym (domyślnie wyłączone w `settings.yaml`) | |
| `absent_ok` | brak wartości jest normalny (powód) – status `absent_ok` | `absent_ok: "PESEL rzadko podawany"` |
| `applies_if` | warunek: `{field, equals}` (`../` = poziom wyżej) lub `{list_min: 2}`; inaczej `not_applicable` | |

## Referencja kluczy listy (szablon w liście)

| klucz | znaczenie |
|---|---|
| `_scope` | sekcja, z której powstają elementy |
| `_each` | regex wycinający elementy (np. osoby); bez niego cała sekcja = jeden element |
| `_each_fallback: whole` | gdy `_each` nic nie znajdzie – cała sekcja jako jeden element |
| `_blocks` | podział na bloki nagłówkiem; element rodzica nr i dostaje blok nr i (np. podpisy per członek konsorcjum) |
| `_llm` | opis listy dla LLM – gdy regex nic nie znalazł (lub `_count_check` wykrył więcej elementów) |
| `_count_check` | pytanie tak/nie do modelu decyzyjnego: czy elementów jest więcej niż znalazł regex |
| `_llm_skip` | pola pomijane przez LLM (np. flagi wyliczane przez `select_one`) |

## Sekcje i klasyfikacja (poziom pliku)

```yaml
sections:
  naglowek: {start: '\A', end: '^[ \t]*(?:Odwołując|Zamawiając)', max_chars: 800}
classify:
  description: "Opis klasy dla modelu decyzyjnego"
  keywords: {'kopii\s+odwołania': 3}
  negative: {'^\s*ODWOŁANIE\s*$': 3}
  min_score: 3
enums:
  sposoby: {1: e-mail, 2: ePUAP}
```

Wskazówki: zaczynaj od regexów dla pól o stałym formacie (numery, daty, kwoty) i dodawaj `llm:` jako zapas – pomiary
pokazują, że tak jest dokładniej i taniej niż ekstrakcja całym LLM. Pola, które często bywają puste, oznacz
`absent_ok` i nie dawaj im `llm:` (model mógłby zgadywać).
