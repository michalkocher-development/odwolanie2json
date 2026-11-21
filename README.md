# odwolanie2json

Konwersja dokumentów sprawy odwoławczej KIO (odwołanie, pełnomocnictwo, potwierdzenie przelewu) z PDF do JSON
zgodnego z kanonicznym modelem UZP – hybryda reguł konfigurowanych w YAML, otwartego modelu decyzyjnego i LLM,
z cytatem źródłowym dla każdej wartości.

Dokumentacja: [architektura](docs/ARCHITEKTURA.md) · [jak dodać nową klasę dokumentu](docs/NOWA_KLASA.md)
(przykład klasy dodanej samym YAML-em: `config/doctypes_examples/kopia_odwolania.yaml`).

## Uruchomienie

Wymagania: Python 3.13+, klucz API dostawcy modeli w pliku `.env` (wzór: `.env.example`; domyślnie `PRIVATEMODE_API_KEY`).

```bat
start.bat
```
albo
```bash
pip install -r requirements.txt
python -m app --input input --output output [--trace trace] [-v]
```

Docker Compose:
```bash
docker compose up -d web       # interfejs web: http://localhost:8000
docker compose run --rm cli    # tryb wsadowy: ./input/<sprawa>/*.pdf -> ./output/<sprawa>/*.json
```

Testy (bez sieci i kosztów): `pip install -r requirements-dev.txt && pytest`

- `input/caseN/*.pdf` → `output/caseN/<ta sama nazwa>.json`
- Dokumenty nierozpoznane (np. ogłoszenie TED) są pomijane.
- `trace/` zawiera dla każdego pola: wartość, metodę (regex/reguła/enum), wzorzec i fragment źródłowy (transparentność).

## Interfejs webowy

```bat
start_web.bat            REM albo: python -m app.web --port 8000
```

Otwórz http://localhost:8000, upuść PDF-y (kilka naraz, także skany). Każda sekcja JSON jest osobnym panelem;
kliknięcie pola pokazuje **dokładny cytat** z dokumentu (strona, podświetlony fragment w kontekście), metodę
(regex / reguła / model decyzyjny z pewnością / LLM zweryfikowany w tekście) i użyty wzorzec. Przyciski: podgląd i pobranie JSON.
Serwer bez dodatkowych zależności (`http.server`); API: `POST /api/process` (treść = PDF, nagłówek `X-Filename`), `GET /api/health`.

## Architektura

```
PDF ─► pdf_text (pdfplumber, MIT; skan → OCR modelem wizyjnym, render pypdfium2)
    ─► classify (słowa kluczowe z YAML; gdy niepewne – model decyzyjny; nierozpoznane pomijane)
    ─► engine (YAML): regex / reguły / sekcje ─► model decyzyjny (wybory, kandydaci) ─► LLM (puste pola i listy)
    ─► JSON + trace (metoda, cytat, strona, prawdopodobieństwo, status pola)
```
Szczegóły: [docs/ARCHITEKTURA.md](docs/ARCHITEKTURA.md). Biblioteki: PyYAML (MIT), pdfplumber / pdfminer.six (MIT),
pypdfium2 (BSD-3 / Apache-2.0), Pillow (MIT-CMU) – wyłącznie licencje permisywne.

Modele (po API, bez GPU lokalnie) – dostawca w `config/settings.yaml` (`provider`, `decisions.provider`):

| rola | **`privatemode` (domyślny, wersja dla jury – UE)** | `openrouter` (porównawczo, poza UE) | `ollama` / `jev_local` (nasze serwery) |
|---|---|---|---|
| decyzje (klucz `jev:` w YAML) | **GLM-5.3-Flash** (MIT) – technika System One na logprobs | cloudflare/clef-flash (Apache 2.0, `/systemone`) | JEV-9B (Apache 2.0, vLLM `/v1/decide`) |
| ekstrakcja (klucz `llm:`) + OCR skanów | **GLM-5.3-Flash** (MIT, obrazy) | gemma-4-31b-it (Apache 2.0) | gemma4:31b (Ollama, pula hostów) |

Zgodność z regulaminem: wyłącznie otwarte modele z możliwością instalacji lokalnej (licencje MIT / Apache 2.0 sprawdzone na
Hugging Face), API u usługodawcy i na serwerach w UE – Privatemode (Edgeless Systems GmbH, Niemcy; przetwarzanie wyłącznie
w UE, bez przechowywania promptów). Endpoint bez lokalnego proxy: `https://proxyless-api.privatemode.ai/v1`.
Limit dostawcy (plan Standard) 100 zapytań/min – klient ma własny ogranicznik (`rate_limit_rpm` w profilu) i czeka zamiast
dostawać HTTP 429.

Konfiguracja klucza: skopiuj `.env.example` do `.env` i wpisz `PRIVATEMODE_API_KEY` (plik `.env` jest w `.gitignore`).
Bez klucza działa część regułowa (z ostrzeżeniem przy starcie).
Zmienne: `PROVIDER`, `DECISION_PROVIDER`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `DECISION_MODEL`, `JEV_URL`, `LLM_URL`,
`LLM_DISABLE=1`, `JEV_DISABLE=1`, `WORKERS`.

- `config/doctypes/*.yaml` – **jedna klasa dokumentu = jeden plik**: klasyfikacja, sekcje (kotwice), struktura wyjściowego JSON, regexy, reguły, słowniki, normalizatory. Nowy typ dokumentu = nowy plik YAML, bez zmian w kodzie.
- `app/engine.py` – interpreter konfiguracji (opis składni w docstringu).
- `app/normalize.py` – normalizatory: `date`, `amount`, `account`, `ted`, `person`, `digits`, `nospace`, `ws`, `strip`, `int`.
- `eval/evaluate.py` – F1 per pole na zbiorze treningowym.

## Ewaluacja

Dane treningowe organizatora nie są w repo – sklonuj je obok projektu:

```bash
git clone https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026 ../tasks/uzp   # domyślna ścieżka --data
```


```bash
python eval/evaluate.py --data ../tasks/uzp/dane            # pełny raport
python eval/evaluate.py --only przelew --errors kwota       # błędy wybranego pola
python eval/evaluate.py --cases 40-60                       # podzbiór przykładów
```

## Wyniki (zbiór treningowy, 60 spraw / 180 PDF)

| konfiguracja | F1 |
|---|---|
| regex + JEV + LLM | 0.9995 |
| ablacja: pola z `llm:` bez regexów, tylko LLM (sprawy 41–60) | 1.000 |
| ta sama ablacja z wyłączonym LLM | 0.575 |
| `czynnosc_powod_id` bez reguł: clef-flash (OpenRouter) | 60/60 |
| `czynnosc_powod_id` bez reguł: JEV-9B (lokalnie) | 59/60 |

```bash
python eval/evaluate.py --llm-only --cases 41-60   # test fallbacku LLM
python eval/bench_powod.py                         # benchmark JEV dla czynnosc_powod_id
python eval/diff.py pelnomocnictwo 40-60            # pełne porównanie pred/gold
```

### Test odporności: dane adwersaryjne

`eval/adversarial/gen.py` generuje sprawy celowo inne niż dane UZP (inne etykiety i układy, tabele, odmiana nazwisk,
formaty dat/NIP/IBAN/kwot, bank po angielsku, konsorcja, rozpraszające daty, brakujące pola):

```bash
python eval/adversarial/gen.py --out ../tasks/adversarial --n 30 --seed 7          # zbiór do analizy błędów
python eval/adversarial/gen.py --out ../tasks/adversarial_holdout --n 30 --seed 2026 # zbiór kontrolny
python eval/evaluate.py --data ../tasks/adversarial_holdout
```

| zbiór | same regexy | pełny pipeline |
|---|---|---|
| treningowy UZP (60 spraw) | 0.9995 | **1.000** |
| adwersaryjny seed 7 (analiza błędów) | 0.376 | **0.897** |
| adwersaryjny seed 2026 (kontrolny, niewidziany) | 0.535 | **0.885** |

Mechanizmy odporności: wybór spośród kandydatów (`candidates`: data/miejscowość z nagłówka), sprawdzanie liczby elementów listy i wybór lidera modelem decyzyjnym (`_count_check`, `select_one`), klasyfikacja modelem decyzyjnym, gdy słowa kluczowe nie wystarczą (`classify.description`);
fallback LLM dla pól (`llm:`) i list (`_llm:`); ugruntowanie wartości w tekście (dla osób – z uwzględnieniem odmiany);
dwa warianty kolejności tekstu (układ wizualny + strumień PDF – tabele); normalizacja ligatur.

### Wyniki dla dostawcy domyślnego (UE): Privatemode, GLM-5.3-Flash

Regulamin: otwarte modele z możliwością instalacji lokalnej + API u usługodawcy i na serwerze w UE. Domyślny dostawca:
Privatemode (Edgeless Systems GmbH, DE; przetwarzanie wyłącznie w UE), model GLM-5.3-Flash (MIT) – ekstrakcja, OCR i decyzje
(technika System One na logprobs). Pomiary: `python eval/summarize.py privatemode` (wyniki `eval/results/privatemode/`).
Czas na dokument zawiera kolejkowanie przez ogranicznik zapytań (limit dostawcy 40 zapytań/min); pojedyncze zapytanie 0.5–1 s.

#### Treningowy UZP (180 dok.)

| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |
|---|---|---|---|---|
| Same regexy/reguły (bez modeli) | 1.000 | 0.29 s | €0.000 | 0.00 |
| **Hybryda (nasz system)** | 0.999 | 14.80 s | €0.071 | 1.30 |
| Hybryda bez LLM (regex + model decyzyjny) | 0.999 | 13.50 s | €0.040 | 1.23 |
| Hybryda bez modelu decyzyjnego (regex + LLM) | 1.000 | 2.96 s | €0.031 | 0.07 |
| Samo LLM: cały tekst + wzór JSON | 0.893 | 11.84 s | €0.619 | 1.00 |

#### Adwersaryjny kontrolny (90 dok.)

| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |
|---|---|---|---|---|
| Same regexy/reguły (bez modeli) | 0.572 | 0.10 s | €0.000 | 0.00 |
| **Hybryda (nasz system)** | 0.885 | 28.80 s | €0.300 | 2.51 |
| Hybryda bez LLM (regex + model decyzyjny) | 0.646 | 26.90 s | €0.070 | 1.93 |
| Hybryda bez modelu decyzyjnego (regex + LLM) | 0.806 | 6.47 s | €0.203 | 0.83 |
| Samo LLM: cały tekst + wzór JSON | 0.836 | 16.68 s | €0.354 | 1.00 |

Adwersaryjny (seed 7): hybryda 0.906. Dla porównania (OpenRouter, poza UE: gemma-4-31b + clef-flash): kontrolny 0.897, adwersaryjny 0.913.

### Koszt i szybkość: hybryda vs „wszystko w LLM” vs ablacja komponentów (OpenRouter, poza UE – porównawczo)

`python eval/cost_report.py --data <zbiór> --mode <tryb>` (tryby: regex, hybrid, hybrid_no_llm, hybrid_no_jev, llm,
llm_full, llm_schema, llm_vision), tabela: `python eval/summarize.py` (wyniki w `eval/results/`).
Warianty „samo LLM” (gemma-4-31b) dostają typ dokumentu z góry i wzór JSON organizatora z komentarzami.

### Treningowy UZP (180 dok.)

| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |
|---|---|---|---|---|
| Same regexy/reguły (bez modeli) | 1.000 | 0.25 s | $0.000 | 0.00 |
| **Hybryda (nasz system)** | 1.000 | 0.50 s | $0.022 | 0.72 |
| Hybryda bez LLM (regex + model decyzyjny) | 1.000 | 0.44 s | $0.006 | 0.65 |
| Hybryda bez modelu decyzyjnego (regex + LLM) | 1.000 | 0.27 s | $0.014 | 0.07 |
| Samo LLM: tekst (8k znaków) + wzór JSON | 0.885 | 2.74 s | $0.275 | 1.00 |
| Samo LLM: cały tekst + wzór JSON | 0.888 | 3.96 s | $0.347 | 1.00 |
| Samo LLM: tekst + wymuszony JSON Schema | 0.891 | 3.05 s | $0.271 | 1.00 |
| Samo LLM wizyjne: obrazy stron + wzór JSON | 0.712 | 5.66 s | $0.234 | 1.00 |

### Adwersaryjny kontrolny (90 dok.)

| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |
|---|---|---|---|---|
| Same regexy/reguły (bez modeli) | 0.535 | 0.08 s | $0.000 | 0.00 |
| **Hybryda (nasz system)** | 0.884 | 1.82 s | $0.134 | 1.81 |
| Hybryda bez LLM (regex + model decyzyjny) | 0.633 | 0.38 s | $0.010 | 0.76 |
| Hybryda bez modelu decyzyjnego (regex + LLM) | 0.800 | 1.10 s | $0.103 | 0.83 |
| Samo LLM: tekst (8k znaków) + wzór JSON | 0.827 | 2.43 s | $0.217 | 1.00 |
| Samo LLM: cały tekst + wzór JSON | 0.831 | 2.48 s | $0.208 | 1.00 |
| Samo LLM: tekst + wymuszony JSON Schema | 0.826 | 2.61 s | $0.207 | 1.00 |
| Samo LLM wizyjne: obrazy stron + wzór JSON | 0.714 | 3.40 s | $0.193 | 1.00 |

Udział metod wypełnienia pól (hybryda): dane UZP – 91% regex/reguły, 6% konfiguracja, 3% model decyzyjny, 0.1% LLM;
dane adwersaryjne – 51% regex/reguły, 38% LLM, 7% konfiguracja, 4% model decyzyjny.
Wnioski: hybryda jest dokładniejsza od każdego wariantu „samo LLM” i wielokrotnie tańsza/szybsza na typowych dokumentach;
oba komponenty modelowe są potrzebne (bez LLM 0.63, bez modelu decyzyjnego 0.80, razem 0.88 na zbiorze kontrolnym).

## Wydajność

Dokumenty są przetwarzane równolegle (`pipeline.workers`, env `WORKERS`). Ogranicznik zapytań po stronie klienta
(`rate_limit_rpm` w profilu dostawcy) pilnuje limitu dostawcy; odpowiedzi HTTP 429 oznaczają odczekanie, nie utratę danych.
Pojedynczy dokument przez interfejs: ~0.3–1 s (typowy), ~3 s (nietypowy układ: model decyzyjny + LLM), skan ~6 s/stronę (OCR).
Przy profilu `ollama` zapytania idą do najmniej obciążonego hosta z puli `llm.base_url` (`app/ollama.py`).

## Ograniczenia
- Dostrojenie reguł na danych syntetycznych organizatora; nietypowe układy obsługują fallbacki modelowe
  (wyniki na danych adwersaryjnych powyżej). `czynnosc_powod_id` = 12 nie występuje w danych ani we wzorze.
- Bez klucza API działa tylko część regułowa (z ostrzeżeniem przy starcie).
