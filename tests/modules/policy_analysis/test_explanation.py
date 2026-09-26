"""T012 — Explicação rastreável: citação obrigatória dos dois lados (RF-07, RN-02)."""

from __future__ import annotations

import pytest

from modules.policy_analysis.application.errors import ClassifiedError
from modules.policy_analysis.application.explanation import ExplanationService
from modules.policy_analysis.domain.models import ComparisonResult, FieldComparison
from modules.policy_analysis.infrastructure.duckdb_repository import PolicyAnalysisRepository
from modules.policy_analysis.infrastructure.llm_agent import FixtureExplanationAgent


def build_repo_with_comparison() -> PolicyAnalysisRepository:
    repo = PolicyAnalysisRepository(":memory:")
    campo = FieldComparison(
        field_code="franquia",
        resultado="MAIOR",
        valor_a={"amount": "50000.00", "currency": "BRL"},
        valor_b={"amount": "25000.00", "currency": "BRL"},
        direcao="A",
        evidencias_a=["EV-A-003"],
        evidencias_b=["EV-B-003"],
        explicacao=None,
    )
    repo.upsert_comparison(
        ComparisonResult(
            comparison_id="CMP-1",
            policy_id_a="POL-A",
            policy_id_b="POL-B",
            campos=(campo,),
        )
    )
    return repo


def test_explicacao_com_citacao_dos_dois_lados_e_aceita_e_persistida():
    repo = build_repo_with_comparison()
    agent = FixtureExplanationAgent(
        {
            "franquia": {
                "text": "A franquia da apólice A (EV-A-003) é maior que a da apólice B (EV-B-003).",
                "evidence_ids": ["EV-A-003", "EV-B-003"],
            }
        }
    )
    service = ExplanationService(repo, agent)

    explanation = service.explain_difference("CMP-1", "franquia")
    assert explanation.field_code == "franquia"
    assert set(explanation.evidence_ids) == {"EV-A-003", "EV-B-003"}

    stored = repo.get_comparison("CMP-1").campos[0].explicacao
    assert "EV-A-003" in stored


def test_explicacao_sem_citacao_e_rejeitada():
    repo = build_repo_with_comparison()
    agent = FixtureExplanationAgent({"franquia": {"text": "A é maior.", "evidence_ids": []}})
    service = ExplanationService(repo, agent)

    with pytest.raises(ClassifiedError) as exc:
        service.explain_difference("CMP-1", "franquia")
    assert exc.value.code == "EXPLANATION_NOT_CITED"
    assert repo.get_comparison("CMP-1").campos[0].explicacao is None


def test_explicacao_com_citacao_desconhecida_e_rejeitada():
    repo = build_repo_with_comparison()
    agent = FixtureExplanationAgent(
        {"franquia": {"text": "A é maior (EV-Z).", "evidence_ids": ["EV-Z"]}}
    )
    service = ExplanationService(repo, agent)

    with pytest.raises(ClassifiedError) as exc:
        service.explain_difference("CMP-1", "franquia")
    assert exc.value.code == "EXPLANATION_NOT_CITED"


def test_explicacao_com_apenas_um_lado_e_rejeitada():
    repo = build_repo_with_comparison()
    agent = FixtureExplanationAgent(
        {"franquia": {"text": "A é maior (EV-A-003).", "evidence_ids": ["EV-A-003"]}}
    )
    service = ExplanationService(repo, agent)

    with pytest.raises(ClassifiedError) as exc:
        service.explain_difference("CMP-1", "franquia")
    assert exc.value.code == "EXPLANATION_NOT_CITED"


def test_explicacao_de_campo_inexistente_falha_claro():
    repo = build_repo_with_comparison()
    service = ExplanationService(repo, FixtureExplanationAgent({}))

    with pytest.raises(ClassifiedError) as exc:
        service.explain_difference("CMP-1", "campo_qualquer")
    assert exc.value.code == "COMPARISON_FIELD_NOT_FOUND"
