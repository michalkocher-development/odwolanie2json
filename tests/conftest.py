"""Wspólne ustawienia testów: bez sieci i bez kosztów – modele (LLM, decyzje) wyłączone."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_DISABLE", "1")
    monkeypatch.setenv("JEV_DISABLE", "1")
