"""Derivação de `Issue`/`QualityReport` dos sinais existentes (D2-P1-1b, D-01).

Mapa sinal → severidade (data-delta.md desta feature):

- falha de ancoragem/validação pós-LLM (`LlmOutputError`) → `CRÍTICO`
- regra de campo violada (`value["rule_violations"]`) → `ALTO`
- `NEEDS_REVIEW` sem violação / `AMBIGUOUS` → `MÉDIO`
- fato sinalizado pelo LLM sem violação (`requires_human_review`) → `BAIXO`

Nenhum novo detector: só a superfície dos sinais que o pipeline já produz.
`Issue` é aditivo — `requires_human_review` permanece no contrato (RN-01).
"""

from __future__ import annotations

from shared_kernel.contracts import ExtractedFact

from ..domain.quality import SEVERITY_ORDER, Issue, QualityReport, Severity

#: Mesma chave gravada por `application/extraction._demote` (manter em sincronia).
RULE_VIOLATIONS_KEY = "rule_violations"


class QualitySignalLog:
    """Falhas pós-LLM registradas em memória (sinal `CRÍTICO` — D-01/D-03).

    O `ExtractionService` grava aqui quando levanta `LlmOutputError`; o motivo
    guardado é a mensagem já sanitizada (T-2a) — nunca texto de apólice.
    """

    def __init__(self) -> None:
        self._failures: list[tuple[str, str, str]] = []

    def record_extraction_failure(self, policy_id: str, field_code: str, reason: str) -> None:
        self._failures.append((policy_id, field_code, reason))

    def failures(self, policy_id: str | None = None) -> list[tuple[str, str, str]]:
        return [
            failure
            for failure in self._failures
            if policy_id is None or failure[0] == policy_id
        ]


class QualityService:
    """Deriva `Issue`s de uma apólice e agrega `QualityReport` (RF-01)."""

    def __init__(self, repository, signals: QualitySignalLog) -> None:
        # `repository` é duck-typed: basta `get_facts(policy_id)` (o
        # `PolicyAnalysisRepository` do Dev 2 atende; evidências ficam no
        # `EvidenceSource`, não no repo — ver `_first_evidence`).
        self._repository = repository
        self._signals = signals

    def list_issues(self, policy_id: str) -> list[Issue]:
        """Issues derivados dos sinais existentes, ordenados CRÍTICO → BAIXO."""
        issues: list[Issue] = []
        for fact in self._repository.get_facts(policy_id):
            issues.extend(self._issues_for_fact(fact))
        for failure_policy_id, field_code, reason in self._signals.failures(policy_id):
            issues.append(
                Issue(
                    severity=Severity.CRITICO,
                    policy_id=failure_policy_id,
                    field_code=field_code,
                    reason=reason,
                )
            )
        return _sorted(issues)

    def get_quality_report(self, policy_id: str) -> QualityReport:
        """Relatório por documento (RF-01)."""
        return QualityReport(
            scope="document", scope_id=policy_id, issues=self.list_issues(policy_id)
        )

    def get_comparison_quality_report(self, comparison_id: str) -> QualityReport:
        """Relatório por comparação: soma dos issues dos dois lados (RF-01)."""
        comparison = self._repository.get_comparison(comparison_id)
        if comparison is None:
            raise ValueError(f"comparison_id desconhecido: {comparison_id}")
        issues = self.list_issues(comparison.policy_id_a) + self.list_issues(
            comparison.policy_id_b
        )
        return QualityReport(
            scope="comparison", scope_id=comparison_id, issues=_sorted(issues)
        )

    def _issues_for_fact(self, fact: ExtractedFact) -> list[Issue]:
        evidence = self._first_evidence(fact)
        value = fact.value or {}
        violations = value.get(RULE_VIOLATIONS_KEY) or []
        issues = [
            Issue(
                severity=Severity.ALTO,
                policy_id=fact.policy_id,
                field_code=fact.field_code,
                reason=f"regra de campo violada: {reason}",
                evidence_ref=evidence,
            )
            for reason in violations
            if str(reason).strip()
        ]
        if issues:
            return issues
        if fact.status == "NEEDS_REVIEW":
            issues.append(
                Issue(
                    severity=Severity.MEDIO,
                    policy_id=fact.policy_id,
                    field_code=fact.field_code,
                    reason="valor ilegível/incerto (NEEDS_REVIEW)",
                    evidence_ref=evidence,
                )
            )
        elif fact.status == "AMBIGUOUS":
            issues.append(
                Issue(
                    severity=Severity.MEDIO,
                    policy_id=fact.policy_id,
                    field_code=fact.field_code,
                    reason="trechos conflitantes (AMBIGUOUS)",
                    evidence_ref=evidence,
                )
            )
        elif fact.requires_human_review:
            issues.append(
                Issue(
                    severity=Severity.BAIXO,
                    policy_id=fact.policy_id,
                    field_code=fact.field_code,
                    reason="sinalizado pelo LLM para revisão (sem violação de regra)",
                    evidence_ref=evidence,
                )
            )
        return issues

    def _first_evidence(self, fact: ExtractedFact):
        # Repo do Dev 2 (`PolicyAnalysisRepository`) não persiste `EvidenceRef`
        # (evidências vivem no `EvidenceSource`); `evidence_ref` fica `None` aí.
        lookup = getattr(self._repository, "get_evidence", None)
        if lookup is None:
            return None
        for evidence_id in fact.evidence_ids:
            evidence = lookup(evidence_id)
            if evidence is not None:
                return evidence
        return None


def _sorted(issues: list[Issue]) -> list[Issue]:
    return sorted(
        issues, key=lambda issue: (SEVERITY_ORDER.index(issue.severity), issue.field_code)
    )
