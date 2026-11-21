@echo off
REM odwolanie2json – interfejs webowy: http://localhost:8000
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
.venv\Scripts\python.exe -m app.web %*
