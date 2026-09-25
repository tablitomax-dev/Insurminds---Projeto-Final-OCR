"""Fixtures compartilhadas dos testes de contrato (tests/contracts)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "data"


@pytest.fixture
def load():
    """Carrega um arquivo JSON de fixture a partir de `fixtures/data/`."""

    def _load(*parts: str) -> dict:
        path = FIXTURES_DIR.joinpath(*parts)
        return json.loads(path.read_text(encoding="utf-8"))

    return _load
