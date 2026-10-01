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


# --- DIVERGENTE (3ª ação — Must do PRD §9) + histórico de decisões -----------


def test_decisao_divergente_registra_sem_resolver_fato(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)

    updated = review.record_decision(
        "FAC-POL-A-indice_reajuste",
        decision="DIVERGENTE",
        decided_by="analista@insurminds",
    )
    # não resolve o fato: não vira FOUND e continua sinalizado
    assert updated.status == "AMBIGUOUS"
    assert updated.requires_human_review is True
    # sai apenas da fila de pendentes
    assert review.list_pending("POL-A") == []


def test_historico_lista_decisoes_registradas(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)
    assert review.list_decisions("POL-A") == []

    review.record_decision(
        "FAC-POL-A-indice_reajuste",
        decision="DIVERGENTE",
        decided_by="analista@insurminds",
    )
    decisions = review.list_decisions("POL-A")
    assert len(decisions) == 1
    assert decisions[0].revisao_status == "DIVERGENTE"
    assert decisions[0].revisao_por == "analista@insurminds"
    assert decisions[0].revisao_em is not None


def test_tres_acoes_disponiveis_e_decisao_invalida_rejeitada(fixture_a, evidences_a):
    repo, extraction, review = build(fixture_a, evidences_a)
    extraction.extract_fields("POL-A", ALL_CODES)

    for decision in ("CONFIRMADO", "CORRIGIDO", "DIVERGENTE"):
        assert decision in ("CONFIRMADO", "CORRIGIDO", "DIVERGENTE")
    with pytest.raises(ValueError):
        review.record_decision(
            "FAC-POL-A-indice_reajuste",
            decision="DECISAO_INVALIDA",
            decided_by="analista@insurminds",
        )
