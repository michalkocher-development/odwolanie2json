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
- Dokument spoza klas (np. ogłoszenie TED) daje plik z pustym obiektem `{}` (ustalenie z organizatorem).
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
    ─► classify (słowa kluczowe z YAML; gdy niepewne – model decyzyjny; dokument spoza klas -> {})
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

## Wyniki

Obecna wersja: dostawca Privatemode (UE), model GLM-5.3-Flash, ekstrakcja tekstu pdfplumber/pypdfium2. Porównanie z dwoma
oczywistymi podejściami: **same regexy** (nasze reguły z YAML, bez modeli) i **samo LLM** (ten sam model dostaje tekst
dokumentu i wzór JSON organizatora z komentarzami i zwraca cały JSON; typ dokumentu podany z góry).

**Dokładność (F1)**

| zbiór | same regexy | **hybryda** | samo LLM |
|---|---|---|---|
| treningowy UZP (60 spraw, 180 PDF) | 0.998 | **0.998** | 0.905 |
| nietypowe układy – zbiór kontrolny (90 PDF) | 0.563 | **0.881** | 0.822 |
| skany bez warstwy tekstowej (90 PDF; regexy z OCR) | 0.600 | **0.907** | – |

**Czas i koszt** (czas na dokument mierzony sekwencyjnie)

| zbiór | hybryda | samo LLM |
|---|---|---|
| treningowy UZP | **0.55 s, €0.07 / 1000 dok.** | 3.03 s, €0.62 / 1000 dok. |
| nietypowe układy | **2.44 s, €0.30 / 1000 dok.** | 2.57 s, €0.36 / 1000 dok. |
| skany | partia 90 skanów w 4.6 min (8 równolegle), €1.30 / 1000 dok. | – |

- Na znanych układach reguły wystarczają – hybryda daje ten sam wynik co same regexy, a model wkracza rzadko
  (91% pól z regexów, LLM w 14 na 180 dokumentów). Na nowych układach i skanach same regexy spadają do ~0.56–0.60,
  hybryda utrzymuje ~0.88–0.91. Względem „samego LLM” hybryda jest dokładniejsza na każdym zbiorze, a na typowych
  dokumentach kilka razy szybsza i tańsza.
- Skany: OCR tylko tylu stron, ile potrzebuje klasa (średnio 1.2 strony na dokument), strony równolegle; 150 skanów ≈ 8 min.
- Zbiory „nietypowe układy” i „skany” generują `eval/adversarial/gen.py` i `eval/make_scans.py` (inne etykiety i układy,
  tabele, odmiana nazwisk, formaty dat/NIP/IBAN, konsorcja, bank po angielsku; skany: obraz strony bez warstwy tekstowej).

Odtworzenie (dane organizatora sklonowane obok projektu, `../tasks/uzp`):
```bash
python eval/evaluate.py --data ../tasks/uzp/dane                     # F1 per pole
python eval/cost_report.py --data ../tasks/uzp/dane --mode hybrid    # + czas, koszt, udział metod (tryby: regex, llm_full)
python eval/summarize.py privatemode                                 # tabela z eval/results/privatemode/
```

## Wydajność

Dokumenty są przetwarzane równolegle (`pipeline.workers`, env `WORKERS`). Ogranicznik zapytań po stronie klienta
(`rate_limit_rpm` w profilu dostawcy) pilnuje limitu dostawcy; odpowiedzi HTTP 429 oznaczają odczekanie, nie utratę danych.
Pojedynczy dokument przez interfejs: ~0.3–1 s (typowy), ~3 s (nietypowy układ: model decyzyjny + LLM), skan ~6 s/stronę (OCR).
Przy profilu `ollama` zapytania idą do najmniej obciążonego hosta z puli `llm.base_url` (`app/ollama.py`).

## Ograniczenia
- Dostrojenie reguł na danych syntetycznych organizatora; nietypowe układy obsługują fallbacki modelowe
  (wyniki na danych adwersaryjnych powyżej). `czynnosc_powod_id` = 12 nie występuje w danych ani we wzorze.
- Bez klucza API działa tylko część regułowa (z ostrzeżeniem przy starcie).
