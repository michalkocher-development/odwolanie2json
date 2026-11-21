# Architektura odwolanie2json

## Cel i zasada działania

Sprawa odwoławcza (kilka PDF-ów: odwołanie, pełnomocnictwo, potwierdzenie przelewu) → jeden JSON na dokument,
zgodny z kanonicznym modelem UZP. Zasada projektowa: **tanie i deterministyczne metody najpierw, model tylko tam,
gdzie reguły nie wystarczają** – i każda wartość z cytatem źródłowym.

```
PDF
 │  app/pdf_text.py      tekst z układem (pdfplumber, MIT) + wariant „strumień” – kolejność strumienia PDF, tabele
 ▼                       komórka po komórce (pypdfium2, BSD/Apache); skan -> OCR modelem wizyjnym (render pypdfium2)
klasyfikacja             app/pipeline.py: słowa kluczowe z YAML (classify) -> gdy niepewne: model decyzyjny
 │                       (opcje = classify.description każdej klasy + „inny dokument” -> plik z `{}`)
 ▼
silnik ekstrakcji        app/engine.py: interpreter config/doctypes/<klasa>.yaml
 │   1. sekcje (kotwice), regexy, reguły, słowniki, normalizatory (app/normalize.py, app/names.py)
 │   2. kandydaci + wybór modelem decyzyjnym (candidates), liczność list (_count_check), wybór elementu (select_one)
 │   3. model decyzyjny dla pól-wyborów (jev:, prefer: jev)
 │   4. LLM dla pustych pól (llm:) i list (_llm:) – jedno wywołanie na dokument, structured output,
 │      kontrola ugruntowania (wartość musi wystąpić w tekście; dla osób – rdzenie słów, mianownik)
 ▼
walidacja                app/validate.py: walidatory z YAML (checks, cross_checks) – miękkie, status `invalid`
 ▼
statusy pól              app/status.py: found / invalid / absent_ok / not_applicable / missing
 ▼
JSON + ślad              output/<sprawa>/<plik>.json ; trace/<sprawa>/<plik>.json (metoda, cytat, strona, pewność)
```

## Moduły

| moduł | odpowiedzialność |
|---|---|
| `app/__main__.py` | CLI: `input/<sprawa>/*.pdf` → `output/<sprawa>/*.json`, ślady w `trace/` |
| `app/web.py`, `web/` | interfejs web (biblioteka standardowa `http.server` + HTML/CSS/JS), `POST /api/process` |
| `app/pipeline.py` | wczytanie klas z YAML, klasyfikacja, przetwarzanie równoległe (wątki), zapis wyników |
| `app/pdf_text.py` | tekst z PDF (dwa warianty kolejności), OCR skanów modelem wizyjnym, normalizacja ligatur |
| `app/engine.py` | interpreter konfiguracji klasy dokumentu (składnia kluczy: docstring + `docs/NOWA_KLASA.md`) |
| `app/normalize.py` | normalizatory wartości: daty, kwoty, rachunki, NIP/KRS, TED/BZP, nazwy firm, osoby |
| `app/names.py` | imię i nazwisko w mianowniku (słownik imion z płcią + reguły końcówek nazwisk) |
| `app/validate.py` | walidatory wbudowane (sumy kontrolne NIP/REGON/PESEL/IBAN) i z YAML, reguły krzyżowe |
| `app/status.py` | status każdego pola (found / invalid / absent_ok / not_applicable / missing) |
| `app/backend.py` | jedyny punkt dostępu do modeli: profile dostawców, LLM (JSON Schema), OCR, decyzje, ogranicznik zapytań, licznik kosztu |
| `app/llm.py` | prompt ekstrakcji, kontrola ugruntowania |
| `app/ollama.py`, `app/jev.py` | alternatywny backend: własne serwery (Ollama, JEV-9B) |
| `config/settings.yaml` | dostawca i modele, limity, OCR, wątki |
| `config/doctypes/*.yaml` | **klasy dokumentów** – jeden plik = jedna klasa |

## Modele i dostawcy

Wszystkie wywołania modeli przechodzą przez `app/backend.py`; dostawca to profil w `config/settings.yaml`.
Domyślny profil `privatemode` (Privatemode, Edgeless Systems GmbH, przetwarzanie w UE) z jednym otwartym modelem
**GLM-5.3-Flash (MIT)** w trzech rolach:

| rola | technika |
|---|---|
| ekstrakcja pól (LLM) | `chat/completions` + JSON Schema (structured output), temperatura 0 |
| OCR skanów | ten sam model, wejście obrazem strony |
| model decyzyjny | „System One” na LLM: asystent zaczyna od `answer=`, dozwolone tylko tokeny numerów opcji (`allowed_token_ids`), prawdopodobieństwa z `logprobs`, kalibracja temperaturą (technika z `edgelesssys/privatemode-decisions`, MIT) |

Inne profile: `openrouter` (porównawczo; gemma-4-31b + clef-flash przez `/systemone`), `ollama` (własne serwery).
Ogranicznik zapytań po stronie klienta (`rate_limit_rpm`) i obsługa HTTP 429 – brak utraty danych przy limitach.

## Dlaczego hybryda

Pomiary (`eval/`, wyniki w README): na dokumentach UZP 91% pól wypełniają regexy/reguły, LLM jest wołany w 13 na 180
dokumentów; na nietypowych układach rośnie udział modeli. Hybryda jest dokładniejsza niż „cały dokument do LLM”
(UZP: 0.998 vs 0.905 F1; zbiór kontrolny: 0.881 vs 0.822), szybsza (UZP: 0.55 s vs 3.03 s na dokument)
i kilkukrotnie tańsza.

## Przejrzystość

Każde pole w śladzie (`trace/`, API, interfejs): wartość, metoda (`regex`, `rule`, `candidate`, `decision:*`, `llm`,
`enum`, `default`), dokładny cytat, numer strony, kontekst przed i po, użyty wzorzec / pytanie do modelu
z prawdopodobieństwem, status pola. Wartości z LLM są przyjmowane tylko, gdy są ugruntowane w tekście.

## Rozszerzalność

Nowa klasa dokumentu = nowy plik YAML (`docs/NOWA_KLASA.md`, przykład: `config/doctypes_examples/kopia_odwolania.yaml`).
Reguły rozpoznawania (`classify`), ekstrakcji, normalizacji (`normalizers`), walidacji (`validators`, `checks`,
`cross_checks`) i mapowania (`output`, `enums`) – wyłącznie w YAML. Nowy dostawca modeli = profil
w `config/settings.yaml` (API zgodne z OpenAI).

## Testy i ewaluacja

- `pytest` (`tests/`): normalizatory, mianownik, silnik na klasie zdefiniowanej w YAML, statusy, decyzje (podstawiony
  serwer), cały pipeline na przykładowej sprawie – bez sieci i kosztów.
- `eval/evaluate.py` – F1 per pole; `eval/adversarial/gen.py` – generator spraw o nietypowych układach;
  `eval/cost_report.py` + `eval/summarize.py` – koszt, czas, udział metod, porównanie z wariantami „samo LLM”.
