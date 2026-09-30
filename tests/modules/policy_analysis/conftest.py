"""Fixtures compartilhadas dos testes do policy_analysis (apólices sintéticas)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared_kernel.contracts import EvidenceRef

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def fixture_a() -> dict:
    return load_fixture("apolice_a.json")


@pytest.fixture
def fixture_b() -> dict:
    return load_fixture("apolice_b.json")


@pytest.fixture
def evidences_a(fixture_a: dict) -> list[EvidenceRef]:
    return [EvidenceRef.model_validate(e) for e in fixture_a["evidences"]]


@pytest.fixture
def evidences_b(fixture_b: dict) -> list[EvidenceRef]:
    return [EvidenceRef.model_validate(e) for e in fixture_b["evidences"]]
