"""Klient modelu decyzyjnego JEV (System 1) – POST {base_url}/v1/decide.

Payload: {"kind": "choice"|"noul"|"score", "state": str, "question": str, "options": [...]}
Odpowiedź: {"choice", "choice_index", "options", "probabilities", ...}
Konfiguracja: config/settings.yaml -> jev.base_url / jev.timeout (nadpisanie: env JEV_URL).
"""

from __future__ import annotations

import json
import os
import urllib.request
from functools import lru_cache
from typing import Any

import yaml

# Antywirus (Avast) ustawia SSLKEYLOGFILE na urządzenie, co wywraca OpenSSL w urllib.
os.environ.pop("SSLKEYLOGFILE", None)

from .pipeline_paths import CONFIG  # noqa: E402


@lru_cache
def settings() -> dict[str, Any]:
    f = CONFIG / "settings.yaml"
    s = yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}
    jev = s.get("jev", {})
    jev["base_url"] = os.environ.get("JEV_URL", jev.get("base_url", "http://localhost:8100"))
    return jev


def enabled() -> bool:
    return bool(settings().get("enabled", True)) and os.environ.get("JEV_DISABLE") != "1"


def decide(kind: str, state: str, question: str, options: list[str] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"kind": kind, "state": state, "question": question}
    if options:
        body["options"] = options
    req = urllib.request.Request(
        settings()["base_url"].rstrip("/") + "/v1/decide",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=settings().get("timeout", 60)) as r:
        return json.load(r)


def choice(state: str, question: str, options: list[str]) -> tuple[int, float, list[float]]:
    """Zwraca (indeks wybranej opcji, jej prawdopodobieństwo, wszystkie prawdopodobieństwa)."""
    r = decide("choice", state, question, options)
    p = r["probabilities"]
    return r["choice_index"], p[r["choice_index"]], p


def noul(state: str, question: str) -> float:
    """Prawdopodobieństwo odpowiedzi 'tak'."""
    r = decide("noul", state, question)
    return dict(zip(r["options"], r["probabilities"]))["true"]
