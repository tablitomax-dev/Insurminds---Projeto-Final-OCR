"""Execução da avaliação sobre o conjunto de referência (RF-02..RF-04).

A extração roda no fluxo real do vertical slice, exclusivamente pela fachada
pública do `policy_analysis` (RNF-03). O relatório é determinístico em
`run_id` + entradas + totais (RNF-01); `generated_at` é só carimbo de
execução (auditoria, RNF-04).
"""

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from ..domain.matching import classify_entry, evidence_matches
from ..domain.models import (
    SYNTHETIC_CAVEAT,
    EvaluationEntry,
    EvaluationReport,
    EvaluationTotals,
    ExpectedFact,
    ReferenceCase,
    ReferenceSet,
)
from .ports import PolicyAnalysisPort


class EvaluationService:
    """Executa o conjunto de referência e escreve o relatório por campo."""

    def __init__(self, policy: PolicyAnalysisPort) -> None:
        self._policy = policy

    def run(self, reference_set: ReferenceSet, report_dir: str | Path) -> EvaluationReport:
        """1 execução → relatório dos casos, com divergências sinalizadas."""
        entries = [
            self._evaluate(case, expected)
            for case in reference_set.cases
            for expected in case.expected_facts
        ]
        report = EvaluationReport(
            run_id=_run_id(reference_set),
            reference_version=reference_set.reference_version,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            oq_02=reference_set.oq_02,
            caveat=SYNTHETIC_CAVEAT,
            entries=entries,
            totals=_totals(entries),
        )
        directory = Path(report_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"evaluation_{report.run_id}.json").write_text(
            report.model_dump_json(indent=2), encoding="utf-8"
        )
        return report

    def _evaluate(self, case: ReferenceCase, expected: ExpectedFact) -> EvaluationEntry:
        """Extrai o campo via fachada e compara com o esperado (determinístico)."""
        try:
            fact = self._policy.extract_field(case.policy_id, expected.field_code)
        except Exception as exc:  # EC-02: falha externa nunca é erro de extração
            return EvaluationEntry(
                case_id=case.case_id,
                policy_id=case.policy_id,
                field_code=expected.field_code,
                expected_status=expected.status,
                extracted_status=None,
                result="nao_avaliado",
                detail=f"não avaliado: falha externa ({type(exc).__name__})",
            )

        expected_scalar = self._policy.normalize_field_value(
            expected.field_code, expected.expected_value
        )
        extracted_scalar = fact.normalized_value or self._policy.normalize_field_value(
            expected.field_code, fact.value
        )
        # A evidência citada pelo fato (nova superfície: lista por apólice/campo).
        cited_ids = set(fact.evidence_ids)
        source_texts = [
            evidence.quoted_text
            for evidence in self._policy.get_evidences(case.policy_id, expected.field_code)
            if evidence.evidence_id in cited_ids
        ]
        result, detail = classify_entry(
            expected.status, fact.status, expected_scalar, extracted_scalar
        )
        return EvaluationEntry(
            case_id=case.case_id,
            policy_id=case.policy_id,
            field_code=expected.field_code,
            expected_status=expected.status,
            extracted_status=fact.status,
            expected_scalar=expected_scalar,
            extracted_scalar=extracted_scalar,
            result=result,
            evidence_ok=evidence_matches(expected.evidence_quote, source_texts),
            evidence_ids=list(fact.evidence_ids),
            detail=detail,
        )


def _run_id(reference_set: ReferenceSet) -> str:
    """`run_id` determinístico: mesma referência → mesmo id (RNF-01)."""
    digest = sha256(reference_set.model_dump_json().encode("utf-8")).hexdigest()
    return f"eval_{digest[:12]}"


def _totals(entries: list[EvaluationEntry]) -> EvaluationTotals:
    counts = {name: 0 for name in ("correto", "divergente", "ausente", "inconclusivo", "nao_avaliado")}
    for entry in entries:
        counts[entry.result] += 1
    return EvaluationTotals(
        total_cases=len(entries),
        correct=counts["correto"],
        divergent=counts["divergente"],
        absent=counts["ausente"],
        inconclusive=counts["inconclusivo"],
        not_evaluated=counts["nao_avaliado"],
        evidence_correct=sum(1 for entry in entries if entry.evidence_ok),
    )
