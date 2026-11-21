# MEMORY – odwolanie2json (zadanie UZP)

- Repo: https://github.com/michalkocher-development/odwolanie2json (private, gałąź main). Lokalnie: `odwolanie2json/`. Stare repo HackNation_2026 = inny projekt.
- Commity/pushe robi użytkownik ręcznie.

- Zadanie: PDF (odwołanie / pełnomocnictwo / przelew) → JSON wg `tasks/uzp/oczekiwane-json`. Ocena: F1 (etap 1 100%), etap 2: 50% F1 + 50% elastyczność (nowe typy przez config).
- Wymogi: Python 3.13+, requirements.txt, start.bat, input/ output/, tylko open source, bez GPU (LLM po API).
- Repo zadania sklonowane: `tasks/uzp/` (60 przykładów treningowych w `dane/`). Teksty: `tasks/txt/`.
- Równoległość: ThreadPool (`pipeline.workers`), PyMuPDF pod blokadą (`_FITZ_LOCK`), pula hostów Ollama w `app/ollama.py` (.211 rtx5090 + .210 rtx4090). Ollama na hostach bez OLLAMA_NUM_PARALLEL → 1 zapytanie naraz/host.
- Stack: PyMuPDF (`get_text(sort=True)`), PyYAML, silnik regex sterowany YAML (`config/doctypes/*.yaml`).
- Środowisko: `.venv` (Python 3.13). SSL proxy: `uv` wisi → używać `pip --use-feature=truststore`.
- Dane: 1–39 proste szablony, 40–60 realistyczne (rozpraszające daty, konsorcja, wielu zamawiających z `prowadzacy_postepowanie`).
- Pułapki: szablon `przyklad odwolanie.pdf` to skan (potrzebny OCR); `negatywny przyklad.pdf` (TED) → pomijany. `czynnosc_powod_id=12` nieznany.
- JEV-9B (Apache 2.0) na vLLM: http://192.168.192.207:8100 (frankencave01, ~/jev-env/start_jev.sh). System 1: `POST /v1/decide` {kind: choice|noul|score, state, question, options} → choice_index, probabilities (~0.2 s). System 2: /v1/chat/completions (ma Thinking Process – dać max_tokens 512+). Klient: `app/jev.py`, adres w `config/settings.yaml` (env JEV_URL, JEV_DISABLE=1).
- JEV lekcje: krótki, celowany kontekst (nagłówek 'Zarzut nr 1 – …' + zdanie 'Zamawiający w dniu…'); pytanie 'Jaką czynność… opisuje ten tekst?' (56/60) >> 'Co zaskarża pierwszy zarzut?' (39/60). Sam JEV dla czynnosc_powod_id: 59/60.
- Windows: Avast ustawia SSLKEYLOGFILE → urllib w Py3.13 crash 'OPENSSL_Uplink'. app/jev.py robi os.environ.pop.
- gemma4:31b (Ollama) jest na wszystkich 4 maszynach; używamy rtx5090 192.168.192.211:11434 (config/settings.yaml `llm`). Klucz `llm: "opis"` w YAML = fallback: 1 wywołanie/dokument dla pustych pól, structured output, kontrola ugruntowania (wartość musi być w tekście). ~1.5 s/dok (rozgrzany), pierwsze wywołanie ~40 s ładowania. Nie włączać llm dla pól często null (data, miejscowosc, bzp/ted, krs, pesel) – ryzyko FP.
- Ablacja `eval/evaluate.py --llm-only --cases 41-60`: same regexy wyłączone → LLM daje F1 1.0 vs 0.575 bez LLM.
- OCR: gemma4 vision (`ocr.engines: [vlm, tesseract]`), ~6 s/stronę, obraz ~1100 px szer. (większe → 500). Zapętla się na zamazaniach → repeat_penalty 1.15, num_predict 2500, znacznik [X]. Skan z szablonu = PRAWDZIWE zanonimizowane odwołanie KIO → test może mieć realne dokumenty o innym układzie.
- NIE: nimble-v3 (CC BY-NC).
- Status (train): F1=0.9995 (regex+JEV+LLM). Ryzyko przeuczenia regexów na syntetycznych szablonach – na nieznanych układach ratuje LLM. Do zrobienia: równoległość dokumentów, UI (wymóg: prototyp z wgrywaniem plików), testy na realnych dokumentach.
