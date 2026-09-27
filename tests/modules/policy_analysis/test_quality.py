"""Testes dos modelos puros de qualidade (D2-P1-1a — roadmap D-01/D-02)
e da derivação de `Issue` dos sinais existentes (D2-P1-1b)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fakes.policy_analysis import (
    FakeEvidenceRetriever,
    FakeLlmExtractor,
    InMemoryFactRepository,
    make_evidence,
    make_fact,
)
from modules.policy_analysis.application.extraction import ExtractionService
from modules.policy_analysis.application.ports import LlmOutputError
from modules.policy_analysis.application.quality import QualityService, QualitySignalLog
from modules.policy_analysis.domain.comparison import ComparisonResult
from modules.policy_analysis.domain.quality import (
    SEVERITY_ORDER,
    Issue,
    QualityReport,
    Severity,
)


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
        field_code="limite_total",
        reason="sinal de teste",
    )
    assert issue.severity is severity
    assert issue.evidence_ref is None


def test_issue_exige_reason_nao_vazia():
    with pytest.raises(ValidationError):
        Issue(
            severity=Severity.ALTO,
            policy_id="pol_acme",
            field_code="limite_total",
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


def _service_with(fact) -> tuple[QualityService, QualitySignalLog, InMemoryFactRepository]:
    repository = InMemoryFactRepository()
    repository.save_evidence(make_evidence(f"ev_{fact.policy_id}_{fact.field_code}", fact.policy_id))
    repository.upsert_fact(fact)
    signals = QualitySignalLog()
    return QualityService(repository, signals), signals, repository


def test_regra_violada_gera_issue_alto_com_evidencia():
    fact = make_fact(
        "pol_a",
        "franquia",
        status="NEEDS_REVIEW",
        value={"scalar": -1, "rule_violations": ["valor_positivo: valor deve ser > 0"]},
        requires_human_review=True,
    )
    service, _, _ = _service_with(fact)

    issues = service.list_issues("pol_a")

    assert len(issues) == 1
    assert issues[0].severity is Severity.ALTO
    assert issues[0].reason.startswith("regra de campo violada: valor_positivo")
    assert issues[0].evidence_ref is not None


def test_needs_review_sem_violacao_gera_issue_medio():
    fact = make_fact("pol_a", "franquia", status="NEEDS_REVIEW", value=None, requires_human_review=True)
    service, _, _ = _service_with(fact)

    issues = service.list_issues("pol_a")

    assert [issue.severity for issue in issues] == [Severity.MEDIO]
    assert "NEEDS_REVIEW" in issues[0].reason


def test_ambiguous_gera_issue_medio():
    fact = make_fact("pol_a", "franquia", status="AMBIGUOUS", value=None, requires_human_review=True)
    service, _, _ = _service_with(fact)

    issues = service.list_issues("pol_a")

    assert [issue.severity for issue in issues] == [Severity.MEDIO]
    assert "AMBIGUOUS" in issues[0].reason


def test_falha_pos_llm_gera_issue_critico():
    fact = make_fact("pol_a", "franquia", status="FOUND", value={"raw_text": "x"})
    service, signals, _ = _service_with(fact)
    signals.record_extraction_failure(
        "pol_a", "limite_total", "EXTRACT: citação do LLM fora do texto da evidência"
    )

    issues = service.list_issues("pol_a")

    criticos = [issue for issue in issues if issue.severity is Severity.CRITICO]
    assert len(criticos) == 1
    assert criticos[0].field_code == "limite_total"


def test_issues_ficam_ordenados_de_critico_a_baixo():
    fact = make_fact(
        "pol_a",
        "franquia",
        status="NEEDS_REVIEW",
        value={"rule_violations": ["valor_positivo: negativo"]},
        requires_human_review=True,
    )
    service, signals, _ = _service_with(fact)
    signals.record_extraction_failure("pol_a", "limite_total", "EXTRACT: falha")

    issues = service.list_issues("pol_a")

    severities = [issue.severity for issue in issues]
    assert severities == sorted(
        severities, key=lambda severity: SEVERITY_ORDER.index(severity)
    )
    assert severities[0] is Severity.CRITICO


def test_relatorio_por_comparacao_agrega_os_dois_lados():
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
    repository.upsert_fact(make_fact("pol_b", "franquia", status="AMBIGUOUS", value=None))
    repository.save_comparison(
        ComparisonResult(comparison_id="cmp_1", policy_id_a="pol_a", policy_id_b="pol_b", rows=[])
    )
    service = QualityService(repository, QualitySignalLog())

    report = service.get_comparison_quality_report("cmp_1")

    assert report.scope == "comparison"
    assert report.scope_id == "cmp_1"
    assert report.counts_by_severity["ALTO"] == 1
    assert report.counts_by_severity["MÉDIO"] == 1


def test_relatorio_de_comparacao_desconhecida_falha():
    service = QualityService(InMemoryFactRepository(), QualitySignalLog())
    with pytest.raises(ValueError):
        service.get_comparison_quality_report("cmp_inexistente")


def test_extracao_com_falha_registra_sinal_critico():
    """O `LlmOutputError` da extração vira sinal CRÍTICO — e o erro segue subindo."""
    repository = InMemoryFactRepository()
    signals = QualitySignalLog()
    service = ExtractionService(
        retriever=FakeEvidenceRetriever([make_evidence("ev_1", "pol_a")]),
        llm_extractor=FakeLlmExtractor(error=LlmOutputError("EXTRACT: saída fora do schema")),
        repository=repository,
        quality_signals=signals,
    )

    with pytest.raises(LlmOutputError):
        service.extract_field("pol_a", "franquia")

    assert signals.failures("pol_a") == [
        ("pol_a", "franquia", "EXTRACT: saída fora do schema")
    ]
