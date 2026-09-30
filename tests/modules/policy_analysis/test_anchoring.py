"""T-D2P01 — Ancoragem de citação (D2-P0-1, A-07): citação inventada nunca vira FOUND."""

from __future__ import annotations

from modules.policy_analysis.application.anchoring import is_anchored
from modules.policy_analysis.application.extraction import ExtractionService
from modules.policy_analysis.infrastructure.duckdb_repository import PolicyAnalysisRepository
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource


class StubAgent:
    def __init__(self, raw_list):
        self.raw_list = raw_list

    def extract(self, requests, run_id):
        return self.raw_list


def raw_with_text(raw_text: str) -> dict:
    return {
        "field_code": "limite_agregado",
        "status": "FOUND",
        "value": {"amount": "5000000.00", "currency": "BRL", "raw_text": raw_text},
        "confidence": 0.9,
        "evidence_ids": ["EV-A-001"],
        "requires_human_review": False,
    }


def test_citacao_real_e_ancorada(evidences_a):
    quote = "Limite agregado de R$ 5.000.000,00 por período de seguro."
    assert is_anchored(quote, evidences_a) is True
    # normalização pt-br: caixa/acentos/espaços não quebram a ancoragem
    assert is_anchored("  limite agregado de r$ 5.000.000,00   por periodo de seguro. ", evidences_a) is True


def test_citacao_inventada_nao_e_ancorada(evidences_a):
    assert is_anchored("Limite agregado de R$ 99.999.999,00 cobertura total.", evidences_a) is False
    assert is_anchored("", evidences_a) is False


def test_citacao_inventada_nunca_vira_found(evidences_a):
    repo = PolicyAnalysisRepository(":memory:")
    service = ExtractionService(
        MockEvidenceSource({"POL-A": evidences_a}),
        StubAgent([raw_with_text("Limite agregado de R$ 99.999.999,00 cobertura total.")]),
        repo,
    )
    fact = service.extract_field("POL-A", "limite_agregado")
    assert fact.status == "NEEDS_REVIEW"  # nunca FOUND
    assert fact.requires_human_review is True


def test_citacao_ancorada_vira_found(evidences_a):
    repo = PolicyAnalysisRepository(":memory:")
    service = ExtractionService(
        MockEvidenceSource({"POL-A": evidences_a}),
        StubAgent([raw_with_text("Limite agregado de R$ 5.000.000,00 por período de seguro.")]),
        repo,
    )
    fact = service.extract_field("POL-A", "limite_agregado")
    assert fact.status == "FOUND"
    assert fact.requires_human_review is False
