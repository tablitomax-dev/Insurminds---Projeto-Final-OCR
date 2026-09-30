"""Testes do agrupamento da fila de revisão por severidade (D2-P1-1d, RF-02)."""

from __future__ import annotations

from modules.policy_analysis.public_api import SEVERITY_ORDER, Issue, Severity
from shared_kernel.contracts import ExtractedFact
from ui.logic import group_by_severity


def _fact(
    policy_id: str, field_code: str, *, status: str, requires_human_review: bool
) -> ExtractedFact:
    return ExtractedFact(
        fact_id=f"FAC-{policy_id}-{field_code}",
        policy_id=policy_id,
        field_code=field_code,
        status=status,
        value=None,
        normalized_value=None,
        confidence=0.5,
        evidence_ids=["ev_1"],
        requires_human_review=requires_human_review,
    )


def _issue(policy_id: str, field_code: str, severity: Severity) -> Issue:
    return Issue(
        severity=severity, policy_id=policy_id, field_code=field_code, reason="sinal"
    )


def test_agrupamento_vai_de_critico_a_baixo():
    facts = [
        _fact("pol_a", "franquia", status="NEEDS_REVIEW", requires_human_review=True),
        _fact("pol_a", "nome_segurado", status="AMBIGUOUS", requires_human_review=True),
    ]
    issues = [
        _issue("pol_a", "franquia", Severity.MEDIO),
        _issue("pol_a", "nome_segurado", Severity.CRITICO),
    ]

    groups = group_by_severity(facts, issues)

    assert [severity for severity, _ in groups] == [Severity.CRITICO, Severity.MEDIO]
    assert [fact.field_code for _, bucket in groups for fact in bucket] == [
        "nome_segurado",
        "franquia",
    ]


def test_fato_sem_issue_cai_em_baixo():
    fact = _fact("pol_a", "franquia", status="FOUND", requires_human_review=True)
    groups = group_by_severity([fact], [])

    assert [severity for severity, _ in groups] == [Severity.BAIXO]


def test_grupos_vazios_nao_aparecem():
    fact = _fact("pol_a", "franquia", status="FOUND", requires_human_review=True)
    issues = [_issue("pol_a", "franquia", Severity.ALTO)]

    groups = group_by_severity([fact], issues)

    assert [severity for severity, _ in groups] == [Severity.ALTO]


def test_severidade_mais_grave_vence_quando_ha_varios_issues():
    fact = _fact("pol_a", "franquia", status="NEEDS_REVIEW", requires_human_review=True)
    issues = [
        _issue("pol_a", "franquia", Severity.BAIXO),
        _issue("pol_a", "franquia", Severity.ALTO),
    ]

    groups = group_by_severity([fact], issues)

    assert [severity for severity, _ in groups] == [Severity.ALTO]


def test_ordem_de_severidade_usada_pelo_agrupamento_e_a_do_contrato():
    assert SEVERITY_ORDER[0] is Severity.CRITICO
    assert SEVERITY_ORDER[-1] is Severity.BAIXO
