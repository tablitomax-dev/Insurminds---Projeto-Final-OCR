"""Testes dos modelos puros de qualidade (D2-P1-1a — roadmap D-01/D-02)
e da derivação de `Issue` dos sinais existentes (D2-P1-1b) sobre a arquitetura
unificada: fachada `create_policy_analysis` com fakes do mundo novo."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fakes.policy_analysis import (
    FailingExtractionAgent,
    FixtureExplanationAgent,
    FixtureExtractionAgent,
    InMemoryFactRepository,
    MockEvidenceSource,
    make_evidence,
    make_fact,
)
from modules.policy_analysis.application.errors import ClassifiedError
from modules.policy_analysis.application.quality import QualityService, QualitySignalLog
from modules.policy_analysis.domain.models import ComparisonResult
from modules.policy_analysis.domain.quality import (
    SEVERITY_ORDER,
    Issue,
    QualityReport,
    Severity,
)
from modules.policy_analysis.public_api import create_policy_analysis


def test_enum_de_severidade_tem_os_quatro_niveis_pt_br():
    assert [severity.value for severity in Severity] == ["CRÍTICO", "ALTO", "MÉDIO", "BAIXO"]


def test_ordem_de_agrupamento_vai_de_critico_a_baixo():
    assert SEVERITY_ORDER == (
        Severity.CRITICO,
        Severity.ALTO,
        Severity.MEDIO,
        Severity.BAIXO,
    )


@pytest.mark.parametrize("severity", list(Severity))
def test_issue_aceita_cada_valor_de_severidade(severity: Severity):
    issue = Issue(
        severity=severity,
        policy_id="pol_acme",
        field_code="limite_agregado",
        reason="sinal de teste",
    )
    assert issue.severity is severity
    assert issue.evidence_ref is None


def test_issue_exige_reason_nao_vazia():
    with pytest.raises(ValidationError):
        Issue(
            severity=Severity.ALTO,
            policy_id="pol_acme",
            field_code="limite_agregado",
            reason="",
        )


def test_quality_report_conta_por_severidade():
    report = QualityReport(
        scope="document",
        scope_id="pol_acme",
        issues=[
            Issue(severity=Severity.ALTO, policy_id="pol_acme", field_code="a", reason="r1"),
            Issue(severity=Severity.ALTO, policy_id="pol_acme", field_code="b", reason="r2"),
            Issue(severity=Severity.MEDIO, policy_id="pol_acme", field_code="c", reason="r3"),
        ],
    )
    assert report.counts_by_severity == {
        "CRÍTICO": 0,
        "ALTO": 2,
        "MÉDIO": 1,
        "BAIXO": 0,
    }


def test_quality_report_vazio_tem_contagem_zerada():
    report = QualityReport(scope="comparison", scope_id="cmp_1", issues=[])
    assert report.counts_by_severity == {
        "CRÍTICO": 0,
        "ALTO": 0,
        "MÉDIO": 0,
        "BAIXO": 0,
    }


# --- Derivação dos sinais existentes (D2-P1-1b, mapa do data-delta.md) ---


def _facade(extraction_agent, *, signals: QualitySignalLog | None = None, evidences=None):
    """Fachada do mundo novo com fakes; `pol_a` tem uma evidência por padrão."""
    return create_policy_analysis(
        MockEvidenceSource(
            {"pol_a": evidences or [make_evidence("ev_pol_a_franquia", "pol_a")]}
        ),
        extraction_agent,
        FixtureExplanationAgent(),
        quality_signals=signals,
    )


def _raw(field_code: str, status: str, **overrides) -> dict:
    """Saída bruta de agente para `pol_a`, com evidência real citada."""
    raw = {
        "field_code": field_code,
        "status": status,
        "value": None,
        "confidence": 0.5,
        "evidence_ids": ["ev_pol_a_franquia"],
        "requires_human_review": False,
    }
    raw.update(overrides)
    return raw


def test_falha_de_extracao_gera_issue_critico():
    """`ClassifiedError` da extração vira sinal CRÍTICO — com o código sanitizado."""
    signals = QualitySignalLog()
    facade = _facade(
        FailingExtractionAgent(
            ClassifiedError("LLM_SCHEMA_INVALID", "saída do LLM fora do schema", retriable=True)
        ),
        signals=signals,
    )

    with pytest.raises(ClassifiedError):
        facade.extract_field("pol_a", "franquia")

    issues = facade.list_issues("pol_a")
    assert [issue.severity for issue in issues] == [Severity.CRITICO]
    assert issues[0].field_code == "franquia"
    assert issues[0].reason == "LLM_SCHEMA_INVALID"
    assert signals.failures("pol_a") == [("pol_a", "franquia", "LLM_SCHEMA_INVALID")]


def test_needs_review_sem_violacao_gera_issue_medio():
    facade = _facade(
        FixtureExtractionAgent(
            {
                "pol_a": [
                    _raw("franquia", "NEEDS_REVIEW", confidence=0.3, requires_human_review=True)
                ]
            }
        )
    )

    facade.extract_field("pol_a", "franquia")

    issues = facade.list_issues("pol_a")
    assert [issue.severity for issue in issues] == [Severity.MEDIO]
    assert "NEEDS_REVIEW" in issues[0].reason


def test_ambiguous_gera_issue_medio():
    facade = _facade(
        FixtureExtractionAgent(
            {"pol_a": [_raw("franquia", "AMBIGUOUS", requires_human_review=True)]}
        )
    )

    facade.extract_field("pol_a", "franquia")

    issues = facade.list_issues("pol_a")
    assert [issue.severity for issue in issues] == [Severity.MEDIO]
    assert "AMBIGUOUS" in issues[0].reason


def test_sinal_do_llm_sem_violacao_gera_issue_baixo():
    facade = _facade(
        FixtureExtractionAgent(
            {
                "pol_a": [
                    _raw(
                        "franquia",
                        "FOUND",
                        value={"amount": "1000.00", "currency": "BRL"},
                        requires_human_review=True,
                    )
                ]
            }
        )
    )

    facade.extract_field("pol_a", "franquia")

    issues = facade.list_issues("pol_a")
    assert [issue.severity for issue in issues] == [Severity.BAIXO]
    assert "revisão" in issues[0].reason


def test_regra_violada_gera_issue_alto_com_evidencia():
    """Ramo ALTO (`value["rule_violations"]`): fato criado diretamente no repo."""
    fact = make_fact(
        "pol_a",
        "franquia",
        status="NEEDS_REVIEW",
        value={"scalar": -1, "rule_violations": ["valor_positivo: valor deve ser > 0"]},
        requires_human_review=True,
    )
    repository = InMemoryFactRepository()
    repository.save_evidence(make_evidence("ev_pol_a_franquia", "pol_a"))
    repository.upsert_fact(fact)
    service = QualityService(repository, QualitySignalLog())

    issues = service.list_issues("pol_a")

    assert len(issues) == 1
    assert issues[0].severity is Severity.ALTO
    assert issues[0].reason.startswith("regra de campo violada: valor_positivo")
    assert issues[0].evidence_ref is not None


def test_issues_ficam_ordenados_de_critico_a_baixo():
    signals = QualitySignalLog()
    facade = _facade(
        FixtureExtractionAgent(
            {
                "pol_a": [
                    _raw(
                        "franquia",
                        "FOUND",
                        value={
                            "amount": "1.00",
                            "currency": "BRL",
                            "rule_violations": ["valor_positivo: negativo"],
                        },
                    ),
                    _raw("vigencia", "NEEDS_REVIEW", requires_human_review=True),
                ]
            }
        ),
        signals=signals,
    )
    facade.extract_fields("pol_a", ["franquia", "vigencia"])
    signals.record_extraction_failure("pol_a", "retroatividade", "LLM_SCHEMA_INVALID")

    issues = facade.list_issues("pol_a")

    severities = [issue.severity for issue in issues]
    assert severities == sorted(
        severities, key=lambda severity: SEVERITY_ORDER.index(severity)
    )
    assert severities[0] is Severity.CRITICO
    assert severities == [Severity.CRITICO, Severity.ALTO, Severity.MEDIO]


def test_relatorio_por_comparacao_agrega_os_dois_lados():
    facade = create_policy_analysis(
        MockEvidenceSource(
            {
                "pol_a": [make_evidence("ev_pol_a_franquia", "pol_a")],
                "pol_b": [make_evidence("ev_pol_b_franquia", "pol_b")],
            }
        ),
        FixtureExtractionAgent(
            {
                "pol_a": [
                    _raw(
                        "franquia",
                        "FOUND",
                        value={
                            "amount": "1.00",
                            "currency": "BRL",
                            "rule_violations": ["valor_positivo: negativo"],
                        },
                    )
                ],
                "pol_b": [
                    _raw(
                        "franquia",
                        "AMBIGUOUS",
                        requires_human_review=True,
                        evidence_ids=["ev_pol_b_franquia"],
                    )
                ],
            }
        ),
        FixtureExplanationAgent(),
    )
    facade.extract_field("pol_a", "franquia")
    facade.extract_field("pol_b", "franquia")
    comparison = facade.compare_policies("pol_a", "pol_b")

    report = facade.get_comparison_quality_report(comparison.comparison_id)

    assert report.scope == "comparison"
    assert report.scope_id == comparison.comparison_id
    assert report.counts_by_severity["ALTO"] == 1
    assert report.counts_by_severity["MÉDIO"] == 1


def test_relatorio_de_comparacao_desconhecida_falha():
    facade = _facade(FixtureExtractionAgent({"pol_a": []}))
    with pytest.raises(ValueError):
        facade.get_comparison_quality_report("cmp_inexistente")


def test_comparacao_desconhecida_no_repo_em_memoria_falha():
    service = QualityService(InMemoryFactRepository(), QualitySignalLog())
    with pytest.raises(ValueError):
        service.get_comparison_quality_report("cmp_inexistente")


def test_regra_violada_no_repo_em_memoria_fica_acima_de_needs_review():
    """`rule_violations` tem prioridade sobre o status de revisão do fato."""
    repository = InMemoryFactRepository()
    repository.upsert_fact(
        make_fact(
            "pol_a",
            "franquia",
            status="NEEDS_REVIEW",
            value={"rule_violations": ["valor_positivo: negativo"]},
            requires_human_review=True,
        )
    )
    repository.save_comparison(
        ComparisonResult(comparison_id="cmp_1", policy_id_a="pol_a", policy_id_b="pol_b", campos=())
    )
    repository.upsert_fact(make_fact("pol_b", "franquia", status="AMBIGUOUS", value=None))
    service = QualityService(repository, QualitySignalLog())

    report = service.get_comparison_quality_report("cmp_1")

    assert report.counts_by_severity["ALTO"] == 1
    assert report.counts_by_severity["MÉDIO"] == 1
