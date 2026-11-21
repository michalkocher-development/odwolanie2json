@echo off
REM odwolanie2json: przetwarza input\<sprawa>\*.pdf -> output\<sprawa>\*.json (slady ekstrakcji: trace\)
cd /d "%~dp0"
if not exist .env (
    echo UWAGA: brak pliku .env z kluczem OPENROUTER_API_KEY - skopiuj .env.example do .env i wpisz klucz.
)
if not exist .venv (
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
.venv\Scripts\python.exe -m app --input input --output output %*
