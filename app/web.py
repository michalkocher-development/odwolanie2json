"""Interfejs webowy: python -m app.web [--host 0.0.0.0] [--port 8000]

GET  /                 -> web/index.html (+ /static/*)
POST /api/process      -> treść żądania = plik PDF, nagłówek X-Filename = nazwa pliku
                          odpowiedź: {file, doctype, text_method, class_scores, result, fields{ścieżka: ślad + status}}
                          fields[ścieżka].status: found | absent_ok | not_applicable | missing (+ note: wyjaśnienie)
GET  /api/health       -> {"ok": true, "provider": ..., "decision_provider": ...}
GET  /api/classes      -> [{name, description, source: file|ui}]
POST /api/class/preview -> {name, description, keywords, example} -> {yaml}: szkielet klasy z przykładowego JSON-a
POST /api/class        -> {yaml}: dodaje klasę (tylko w pamięci tego procesu; trwale = plik w config/doctypes/)
Bez zewnętrznych zależności (http.server z biblioteki standardowej).
"""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

from . import backend, engine, new_class, pipeline
from .pipeline import ROOT, process_pdf

log = logging.getLogger(__name__)
WEB = ROOT / "web"
MAX_BYTES = 40 * 1024 * 1024
MAX_CLASS_BYTES = 100 * 1024
MAX_UI_CLASSES = 20


def list_classes() -> list[dict[str, Any]]:
    return [{"name": n, "description": (s.get("classify") or {}).get("description") or n,
             "source": "ui" if n in pipeline.EXTRA_DOCTYPES else "file"} for n, s in pipeline.load_doctypes().items()]


def add_class(text: str) -> dict[str, Any]:
    """Klasa z YAML (interfejs „Dodaj klasę”): sprawdzenie struktury i próbny przebieg silnika, potem rejestracja."""
    try:
        spec = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"Niepoprawny YAML: {e}") from e
    if not isinstance(spec, dict) or not isinstance(spec.get("output"), dict) or not spec["output"]:
        raise ValueError("YAML musi zawierać `name` i niepustą sekcję `output`")
    name = str(spec.get("name", ""))
    if not new_class.NAME_RE.fullmatch(name):
        raise ValueError("Nazwa klasy: małe litery, cyfry i _, zaczyna się literą")
    if name in pipeline._file_doctypes():
        raise ValueError(f"Klasa „{name}” jest już zdefiniowana w config/doctypes – wybierz inną nazwę")
    if name not in pipeline.EXTRA_DOCTYPES and len(pipeline.EXTRA_DOCTYPES) >= MAX_UI_CLASSES:
        raise ValueError("Osiągnięto limit klas dodanych w interfejsie")
    spec.setdefault("classify", {})
    token = backend.set_deadline(1e-6)  # próbny przebieg bez modeli (budżet czasu wyczerpany od razu):
    try:                                 # błędne regexy / klucze wychodzą teraz, a nie przy dokumencie
        engine.extract("dokument testowy", spec)
    except Exception as e:
        raise ValueError(f"Błąd w definicji klasy: {e}") from e
    finally:
        backend.reset_deadline(token)
    pipeline.EXTRA_DOCTYPES[name] = spec
    return {"name": name, "description": spec["classify"].get("description") or name}


def run_document(data: bytes, filename: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / (Path(filename).name or "dokument.pdf")
        pdf.write_bytes(data)
        doctype, result, info = process_pdf(pdf)
    fields: dict[str, Any] = {}
    for t in info.get("trace", []):  # ostatni wpis wygrywa (np. llm_pending -> llm)
        if t.get("field") and t["field"] != "*":
            fields[t["field"]] = {k: v for k, v in t.items() if k != "field"}
    for path, st in (info.get("status") or {}).items():  # status pola: found / absent_ok / not_applicable / missing
        fields.setdefault(path, {}).update(st)
    return {
        "file": filename,
        "doctype": doctype,
        "text_method": info.get("text_method"),
        "class_scores": info.get("class_scores"),
        "result": result,
        "fields": fields,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "odwolanie2json"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: Any) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/classes":
            return self._json(200, list_classes())
        if path == "/api/health":
            return self._json(200, {"ok": True, "provider": backend.provider(), "decision_provider": backend.decision_provider()})
        rel = "index.html" if path in ("/", "") else path.removeprefix("/static/").lstrip("/")
        f = (WEB / rel).resolve()
        if WEB.resolve() not in f.parents or not f.is_file():  # tylko pliki z katalogu web/
            return self._send(404, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self._send(200, f.read_bytes(), ctype)

    def _class_api(self, path: str) -> None:
        size = int(self.headers.get("Content-Length") or 0)
        if not 0 < size <= MAX_CLASS_BYTES:
            return self._json(413, {"error": "Pusta albo zbyt duża definicja"})
        try:
            body = json.loads(self.rfile.read(size))
            if path == "/api/class/preview":
                example = body.get("example")
                if isinstance(example, str):
                    example = json.loads(example)
                kw = body.get("keywords") or ""
                spec = new_class.skeleton(str(body.get("name", "")).strip(), example, str(body.get("description", "")),
                                          kw.split(",") if isinstance(kw, str) else list(kw))
                return self._json(200, {"yaml": new_class.to_yaml(spec)})
            return self._json(200, add_class(str(body.get("yaml", ""))))
        except json.JSONDecodeError as e:
            return self._json(400, {"error": f"Niepoprawny JSON: {e}"})
        except ValueError as e:
            return self._json(400, {"error": str(e)})

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path in ("/api/class", "/api/class/preview"):
            return self._class_api(path)
        if path != "/api/process":
            return self._json(404, {"error": "Nieznany endpoint"})
        size = int(self.headers.get("Content-Length") or 0)
        if not 0 < size <= MAX_BYTES:
            return self._json(413, {"error": f"Plik pusty albo większy niż {MAX_BYTES // 2**20} MB"})
        data = self.rfile.read(size)
        name = urllib.parse.unquote(self.headers.get("X-Filename") or "dokument.pdf")
        if not data.startswith(b"%PDF"):
            return self._json(415, {"error": "To nie jest plik PDF"})
        try:
            self._json(200, run_document(data, name))
        except Exception as e:  # komunikat dla użytkownika, szczegóły w logu
            log.exception("Błąd przetwarzania %s", name)
            self._json(500, {"error": f"Błąd przetwarzania: {e}"})

    def log_message(self, fmt: str, *args: Any) -> None:
        log.info("%s %s", self.address_string(), fmt % args)


def main() -> None:
    ap = argparse.ArgumentParser(description="odwolanie2json – interfejs webowy")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"odwolanie2json: http://localhost:{a.port}  (provider: {backend.provider()}, decyzje: {backend.decision_provider()})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
