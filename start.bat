@echo off
REM Odwolania2json: przetwarza input\caseN\*.pdf -> output\caseN\*.json
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
.venv\Scripts\python.exe -m app --input input --output output %*
