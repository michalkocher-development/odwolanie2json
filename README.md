# odwolanie2json

Konwersja dokumentów sprawy odwoławczej KIO (odwołanie, pełnomocnictwo, potwierdzenie przelewu) z PDF do JSON.

## Uruchomienie

```bat
start.bat
```
albo
```bash
pip install -r requirements.txt
python -m app --input input --output output [--trace trace] [-v]
```

- `input/caseN/*.pdf` → `output/caseN/<ta sama nazwa>.json`
- Dokumenty nierozpoznane (np. ogłoszenie TED) są pomijane.
- `trace/` zawiera dla każdego pola: wartość, metodę (regex/reguła/enum), wzorzec i fragment źródłowy (transparentność).

## Architektura

```
PDF ─► pdf_text (PyMuPDF; skan → OCR: gemma4 vision / Tesseract)
    ─► classify (słowa kluczowe z YAML; nierozpoznane pomijane)
    ─► engine (YAML): regex / reguły / sekcje  ─► JEV /v1/decide (pola-wybory)  ─► gemma4 (puste pola tekstowe)
    ─► JSON + trace (metoda, wzorzec, fragment źródłowy, prawdopodobieństwo)
```

Modele (open source, po API, bez GPU lokalnie) – adresy w `config/settings.yaml`:
- **JEV-9B** (Apache 2.0, vLLM) – decyzje: `czynnosc_powod_id` (klucz `jev:` w YAML).
- **gemma4:31b** (Ollama) – fallback generujący (klucz `llm:` z opisem pola) + OCR skanów.
- Zmienne: `JEV_URL`, `JEV_DISABLE=1`, `LLM_URL`, `LLM_MODEL`, `LLM_DISABLE=1`.

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

```bash
python eval/evaluate.py --llm-only --cases 41-60   # test fallbacku LLM
python eval/bench_powod.py                         # benchmark JEV dla czynnosc_powod_id
python eval/diff.py pelnomocnictwo 40-60            # pełne porównanie pred/gold
```

## Wydajność

Dokumenty są przetwarzane równolegle (`pipeline.workers`, env `WORKERS`). Zapytania do Ollamy idą do najmniej obciążonego hosta z puli `llm.base_url` (`app/ollama.py`); host bez odpowiedzi jest pomijany przez `cooldown` s. Ablacja LLM (60 dok.): 201 s sekwencyjnie → 119 s (8 wątków, 2 hosty).

## TODO
- UI do wgrywania plików (wymóg formalny: prototyp).
- Testy na realnych (nie syntetycznych) dokumentach.
