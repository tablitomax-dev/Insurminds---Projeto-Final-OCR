"""T011 — Fila de revisão humana (RF-04, RN-03)."""

from __future__ import annotations

import pytest

from modules.policy_analysis.application.extraction import ExtractionService
from modules.policy_analysis.application.review import ReviewService
from modules.policy_analysis.infrastructure.duckdb_repository import PolicyAnalysisRepository
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import (
    FixtureExplanationAgent,
    FixtureExtractionAgent,
)

ALL_CODES = [
    "limite_agregado",
    "limite_por_sinistro",
    "franquia",
    "vigencia",
    "prazo_notificacao_sinistro",
    "extensao_territorial",
    "exclusoes_chave",
    "limite_defesa_custos",
    "retroatividade",
    "indice_reajuste",
]


def build(fixture_a, evidences_a):
    repo = PolicyAnalysisRepository(":memory:")
    extraction = ExtractionService(
        MockEvidenceSource({"POL-A": evidences_a}),
        FixtureExtractionAgent({"POL-A": fixture_a["llm_output"]}),
        repo,
    )
    return repo, extraction, ReviewService(repo)


def test_fato_ambiguo_entra_na_fila_com_evidencia_anexa(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)

    pending = review.list_pending("POL-A")
    assert len(pending) == 1
    item = pending[0]
    assert item.fact.field_code == "indice_reajuste"
    assert item.fact.status == "AMBIGUOUS"
    assert item.fact.evidence_ids == ["EV-A-010", "EV-A-011"]  # evidência visível
    assert item.revisao_status == "PENDENTE"


def test_decisao_confirmado_registra_quem_decidiu(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)

    updated = review.record_decision(
        "FAC-POL-A-indice_reajuste",
        decision="CONFIRMADO",
        decided_by="analista@insurminds",
    )
    assert updated.status == "FOUND"
    assert updated.requires_human_review is False
    assert review.list_pending("POL-A") == []


def test_decisao_corrigido_substitui_valor_e_normaliza(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)

    updated = review.record_decision(
        "FAC-POL-A-indice_reajuste",
        decision="CORRIGIDO",
        decided_by="analista@insurminds",
        value={"number": "5", "unit": "%"},
    )
    assert updated.value == {"number": "5", "unit": "%"}
    assert updated.normalized_value == {"number": "5"}
    assert updated.status == "FOUND"
    assert updated.requires_human_review is False


def test_corrigido_sem_valor_e_invalido(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)

    with pytest.raises(ValueError):
        review.record_decision(
            "FAC-POL-A-indice_reajuste",
            decision="CORRIGIDO",
            decided_by="analista@insurminds",
        )


def test_registrar_divergencia_fica_auditada_sem_pendencia(fixture_a, evidences_a):
    """D2-P0-2: terceira ação do loop de revisão — 'Registrar divergência'."""
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)

    updated = review.record_decision(
        "FAC-POL-A-indice_reajuste",
        decision="DIVERGENTE",
        decided_by="analista@insurminds",
        reason="cláusula 10.2 (4%) contradiz cláusula 10.3 (5%)",
    )
    assert updated.status == "NEEDS_REVIEW"  # valor não comparável
    assert updated.requires_human_review is False  # pendência tratada

    item = repo.get_review_item("FAC-POL-A-indice_reajuste")
    assert item.revisao_status == "DIVERGENTE"
    assert item.revisao_decisao["reason"].startswith("cláusula 10.2")
    assert item.revisao_por == "analista@insurminds"
    assert review.list_pending("POL-A") == []


def test_divergencia_sem_motivo_e_invalida(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)

    with pytest.raises(ValueError):
        review.record_decision(
            "FAC-POL-A-indice_reajuste",
            decision="DIVERGENTE",
            decided_by="analista@insurminds",
        )


def test_comparacao_usa_divergencia_registrada(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path):
    from modules.policy_analysis.public_api import PolicyAnalysisFacade

    facade = PolicyAnalysisFacade(
        MockEvidenceSource({"POL-A": evidences_a, "POL-B": evidences_b}),
        FixtureExtractionAgent({"POL-A": fixture_a["llm_output"], "POL-B": fixture_b["llm_output"]}),
        FixtureExplanationAgent({}),
        db_path=":memory:",
        output_dir=str(tmp_path),
    )
    facade.extract_fields("POL-A", ALL_CODES)
    facade.extract_fields("POL-B", ALL_CODES)

    assert facade.compare_policies("POL-A", "POL-B").campo("indice_reajuste").resultado == "AGUARDANDO_REVISAO"

    facade.record_review_decision(
        "FAC-POL-A-indice_reajuste",
        decision="DIVERGENTE",
        decided_by="analista@insurminds",
        reason="trechos contraditórios na apólice A",
    )
    assert facade.compare_policies("POL-A", "POL-B").campo("indice_reajuste").resultado == "DIVERGENTE"
