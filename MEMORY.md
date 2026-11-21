# MEMORY – odwolanie2json (zadanie UZP „Odwołania2json”, HackNation 2026)

Krótkie, kluczowe fakty dla zespołu i agentów. Szczegóły: `README.md`, `docs/ARCHITEKTURA.md`, `docs/NOWA_KLASA.md`.

## Zadanie i wymagania
- PDF-y sprawy (odwołanie / pełnomocnictwo / potwierdzenie przelewu) → JSON per dokument wg wzorów organizatora
  (repo `Urzad-Zamowien-Publicznych/hacknation-2026`, katalog `oczekiwane-json`). Dokumenty spoza klas są pomijane.
- Ocena: etap 1 – F1 na nieujawnionym zbiorze **realnych** spraw (≥10); finał – F1 + rozszerzalność + architektura.
- Wymogi: Python 3.13+, `requirements.txt`, CLI/`start.bat`, `input/` → `output/` (te same nazwy), tylko komponenty
  open source (otwarte modele z możliwością instalacji lokalnej), uruchomienie bez GPU (LLM po API), API u usługodawcy
  i na serwerach w UE. Zwycięzca przekazuje kod, instrukcję, Docker Compose, dokumentację architektury i dodawania klas.
- `czynnosc_powod_id` = 12 – nieznany (brak w danych i we wzorze), nie obsługujemy.

## Architektura (skrót)
- Tekst: pdfplumber (MIT) w trybie układu + wariant „strumień” dla LLM i ugruntowania; OCR skanów modelem wizyjnym
  (render pypdfium2, BSD/Apache). PyMuPDF (AGPL) usunięty z aplikacji – zostaje tylko w generatorze danych (dev).
- Silnik: `config/doctypes/*.yaml` – jedna klasa = jeden plik; regexy/reguły/normalizatory najpierw, potem model
  decyzyjny (`jev:`, `candidates`, `_count_check`, `select_one`), na końcu LLM dla pustych pól/list (`llm:`, `_llm:`)
  z kontrolą ugruntowania (osoby: rdzenie + mianownik, `app/names.py`). Statusy pól: `app/status.py`.
- Dostawca: `provider: privatemode` (GLM-5.3-Flash, MIT; ekstrakcja + OCR + decyzje techniką logprobs: prefill
  `answer=`, `allowed_token_ids`, kalibracja). Endpoint bez proxy: https://proxyless-api.privatemode.ai/v1, klucz
  `PRIVATEMODE_API_KEY` w `.env`. Plan Standard: 100 zapytań/min → `rate_limit_rpm: 95` + obsługa 429.
- Alternatywy: `openrouter` (porównawczo, poza UE), `ollama`/`jev_local` (własne serwery, adresy przez env).

## Wyniki (eval/results/<dostawca>/)
- Obecna wersja (Privatemode, pdfplumber+pypdfium2, pomiar sekwencyjny): UZP 0.998 (samo LLM 0.905), kontrolny 0.881
  (samo LLM 0.822), adwersaryjny 0.900, skany 0.907; same regexy: 0.998 / 0.563 / skany 0.600;
  czas/dok. UZP 0.55 s vs 3.03 s (samo LLM), kontrolny 2.44 s vs 2.57 s; 90 skanów w 4.6 min.
- Dokument spoza klas -> plik `{}` (DC). Skany: OCR etapami (classify.ocr_pages), budżet czasu pipeline.doc_time_budget_s.
- Docker: obraz zbudowany i sprawdzony – `docker compose up -d web` (API OK) i `docker compose run --rm cli` (wyniki zgodne ze wzorcem).
- Na danych UZP 91% pól z regexów, LLM w 13/180 dok.; koszt ~€0.07–0.30 / 1000 dok.
- Zmierzone i odrzucone: weryfikacja pól modelem (`verify`) – +0.005 F1 przy 3× koszcie (wyłączona).

## Wskazówki techniczne
- Testy: `pytest` (bez sieci; modele wyłączone przez `LLM_DISABLE=1`, `JEV_DISABLE=1`).
- Ewaluacja: `python eval/evaluate.py --data <katalog>`; generator nietypowych spraw: `eval/adversarial/gen.py`.
- Windows: niektóre antywirusy ustawiają `SSLKEYLOGFILE` na urządzenie (crash OpenSSL) – kod usuwa tę zmienną.
- Edycje plików z `\n`, `\f`, `\b` w stringach przez skrypty potrafią wstawić znaki sterujące – używać narzędzia Edit.
- Commity i pushe robi użytkownik ręcznie.
