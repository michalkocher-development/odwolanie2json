"""Wspólny klient Ollama (/api/generate) z pulą hostów.

`llm.base_url` w config/settings.yaml może być adresem albo listą adresów (env LLM_URL: po przecinku).
Każde zapytanie trafia do hosta z najmniejszą liczbą trwających zapytań – równoległe dokumenty
rozkładają się na kilka maszyn. Host, który nie odpowiada, jest pomijany przez `cooldown` sekund.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any

import yaml

os.environ.pop("SSLKEYLOGFILE", None)  # niektóre antywirusy ustawiają go na urządzenie -> crash OpenSSL w urllib

from .pipeline_paths import CONFIG  # noqa: E402

log = logging.getLogger(__name__)
_lock = threading.Lock()
_inflight: dict[str, int] = {}
_down_until: dict[str, float] = {}


@lru_cache
def settings() -> dict[str, Any]:
    f = CONFIG / "settings.yaml"
    s = (yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}).get("llm", {})
    urls = os.environ.get("LLM_URL") or s.get("base_url", "http://localhost:11434")
    s["base_urls"] = [u.strip().rstrip("/") for u in (urls.split(",") if isinstance(urls, str) else urls)]
    s["model"] = os.environ.get("LLM_MODEL", s.get("model", "gemma4:31b"))
    return s


def _acquire() -> str:
    now = time.time()
    with _lock:
        hosts = [h for h in settings()["base_urls"] if _down_until.get(h, 0) <= now] or settings()["base_urls"]
        host = min(hosts, key=lambda h: _inflight.get(h, 0))
        _inflight[host] = _inflight.get(host, 0) + 1
        return host


def _release(host: str, failed: bool) -> None:
    with _lock:
        _inflight[host] -= 1
        if failed:
            _down_until[host] = time.time() + settings().get("cooldown", 60)


def generate(body: dict[str, Any], timeout: float | None = None, retries: int = 3) -> str:
    """POST /api/generate (stream=False), zwraca pole `response`. Ponawia na innym hoście przy błędzie."""
    body = {"model": settings()["model"], "stream": False, "think": False, **body}
    data = json.dumps(body).encode()
    last: Exception | None = None
    for attempt in range(retries):
        host = _acquire()
        failed = False
        try:
            req = urllib.request.Request(host + "/api/generate", data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout or settings().get("timeout", 300)) as r:
                return json.load(r)["response"]
        except urllib.error.HTTPError as e:  # np. 500 "token repeat limit reached" – ponów
            last = e
            log.warning("Ollama %s próba %d: HTTP %s %s", host, attempt + 1, e.code, e.read().decode(errors="replace")[:200])
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:  # host niedostępny
            last, failed = e, True
            log.warning("Ollama %s niedostępna: %s", host, e)
        finally:
            _release(host, failed)
    raise RuntimeError(f"Ollama: wszystkie próby nieudane: {last}")
