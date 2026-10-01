"""T011 — Fila de revisão humana (RF-04, RN-03)."""

from __future__ import annotations

import pytest

from modules.policy_analysis.application.extraction import ExtractionService
from modules.policy_analysis.application.review import ReviewService
from modules.policy_analysis.infrastructure.duckdb_repository import PolicyAnalysisRepository
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import FixtureExtractionAgent

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


def test_corrigido_com_texto_digitado_coercao_por_tipo_do_campo(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)

    money = review.record_decision(
        "FAC-POL-A-franquia",
        decision="CORRIGIDO",
        decided_by="analista@insurminds",
        value="R$ 60.000,00",
    )
    assert money.value == {"amount": "R$ 60.000,00", "currency": "BRL"}
    assert money.normalized_value == {"amount": "60000.00", "currency": "BRL"}

    period = review.record_decision(
        "FAC-POL-A-vigencia",
        decision="CORRIGIDO",
        decided_by="analista@insurminds",
        value="01/01/2025 a 01/06/2026",
    )
    assert period.value == {"start": "01/01/2025", "end": "01/06/2026"}
    assert period.normalized_value["duration_days"] == 516


def test_corrigido_com_texto_invalido_para_o_tipo_e_rejeitado(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)

    with pytest.raises(ValueError):
        review.record_decision(
            "FAC-POL-A-vigencia",
            decision="CORRIGIDO",
            decided_by="analista@insurminds",
            value="01/01/2025",
        )


def test_historico_so_lista_decisoes_humanas(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)
    review.record_decision(
        "FAC-POL-A-indice_reajuste",
        decision="CONFIRMADO",
        decided_by="analista@insurminds",
    )

    decisions = review.list_decisions("POL-A")
    assert [item.fact.field_code for item in decisions] == ["indice_reajuste"]
    assert decisions[0].revisao_status == "CONFIRMADO"
    assert decisions[0].revisao_por == "analista@insurminds"
    assert decisions[0].revisao_em is not None
    assert review.list_pending("POL-A") == []
