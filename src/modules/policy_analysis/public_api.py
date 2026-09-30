"""Fachada pública do policy_analysis (spec §8, RF-01..RF-08).

ÚNICA entrada do módulo para o resto do sistema (workflow/app/Streamlit):
`extract_field`, `get_facts`, `compare_policies`, `explain_difference`,
`export_comparison` — mais as operações de revisão humana (RF-04).

Extensões de governança/observabilidade (features 003/004 do ciclo anterior,
**reimplementadas sobre esta arquitetura** por decisão do humano em 2026-09-29 —
a arquitetura do Dev 2 prevalece e as costuras são aditivas): `list_issues`,
`get_quality_report`, `get_comparison_quality_report`, `get_usage_metrics`.
"""

from __future__ import annotations

from shared_kernel.contracts import EvidenceRef, ExtractedFact

from .application.comparison_service import ComparisonService
from .application.errors import ClassifiedError
from .application.explanation import ExplanationService
from .application.export import ExportService
from .application.extraction import ExtractionService
from .application.quality import QualityService, QualitySignalLog
from .application.review import ReviewService
from .domain.metrics import UsageMetricsCollector, UsageSummary
from .domain.models import ComparisonResult, Explanation, ReviewItem
from .domain.quality import SEVERITY_ORDER, Issue, QualityReport, Severity
from .infrastructure.duckdb_repository import PolicyAnalysisRepository
from .infrastructure.pricing import PRICE_REFERENCE_DATE


class PolicyAnalysisFacade:
    """API pública do módulo de análise de apólices."""

    def __init__(
        self,
        evidence_source,
        extraction_agent,
        explanation_agent,
        db_path: str = ":memory:",
        output_dir: str = "output",
        currency_rates: dict | None = None,
        usage_collector: UsageMetricsCollector | None = None,
        quality_signals: QualitySignalLog | None = None,
    ):
        self._repo = PolicyAnalysisRepository(db_path)
        self._evidence_source = evidence_source
        self._extraction = ExtractionService(evidence_source, extraction_agent, self._repo)
        self._review = ReviewService(self._repo)
        self._comparison = ComparisonService(self._repo, currency_rates)
        self._explanation = ExplanationService(self._repo, explanation_agent)
        self._export = ExportService(self._repo, output_dir)
        self._usage = usage_collector if usage_collector is not None else UsageMetricsCollector()
        self._signals = quality_signals if quality_signals is not None else QualitySignalLog()
        self._quality = QualityService(self._repo, self._signals)

    # --- extração (RF-02, RF-03) ----------------------------------------------

    def extract_field(self, policy_id: str, field_code: str) -> ExtractedFact:
        return self.extract_fields(policy_id, [field_code])[0]

    def extract_fields(self, policy_id: str, field_codes: list[str]) -> list[ExtractedFact]:
        try:
            return self._extraction.extract_fields(policy_id, field_codes)
        except Exception as exc:
            # Sinal CRÍTICO de governança (004) antes de propagar: só o código
            # classificado do erro (sanitizado — T-2a), nunca texto de apólice.
            code = str(getattr(exc, "code", None) or type(exc).__name__)
            for field_code in field_codes:
                self._signals.record_extraction_failure(policy_id, field_code, code)
            raise

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        return self._extraction.get_facts(policy_id)

    # --- catálogo e evidências (consumidores: UI/evaluation) ------------------

    def list_fields(self) -> list[dict[str, str]]:
        from .domain.field_catalog import all_codes, get_field

        fields = []
        for code in all_codes():
            definition = get_field(code)
            fields.append(
                {
                    "code": definition.code,
                    "label": definition.label,
                    "description": definition.description,
                }
            )
        return fields

    def normalize_field_value(self, field_code: str, value: dict | None) -> dict | None:
        from .domain.field_catalog import get_field
        from .domain.value_types import normalize_value

        if value is None:
            return None
        return normalize_value(get_field(field_code), value)

    def get_evidences(self, policy_id: str, field_code: str | None = None) -> list[EvidenceRef]:
        return list(self._evidence_source.get_evidences(policy_id, field_code))

    # --- revisão humana (RF-04) ----------------------------------------------

    def list_review_queue(self, policy_id: str | None = None) -> list[ReviewItem]:
        return self._review.list_pending(policy_id)

    def record_review_decision(
        self, fact_id: str, decision: str, decided_by: str, value: dict | None = None
    ) -> ExtractedFact:
        return self._review.record_decision(fact_id, decision, decided_by, value)

    # --- comparação determinística (RF-06) ------------------------------------

    def compare_policies(self, policy_id_a: str, policy_id_b: str) -> ComparisonResult:
        return self._comparison.compare_policies(policy_id_a, policy_id_b)

    # --- explicação rastreável (RF-07) ----------------------------------------

    def explain_difference(self, comparison_id: str, field_code: str) -> Explanation:
        return self._explanation.explain_difference(comparison_id, field_code)

    # --- export standalone (RF-08) --------------------------------------------

    def export_comparison(self, comparison_id: str) -> str:
        return self._export.export_comparison(comparison_id)

    # --- governança da qualidade (extensão 004) -------------------------------

    def list_issues(self, policy_id: str) -> list[Issue]:
        return self._quality.list_issues(policy_id)

    def get_quality_report(self, policy_id: str) -> QualityReport:
        return self._quality.get_quality_report(policy_id)

    def get_comparison_quality_report(self, comparison_id: str) -> QualityReport:
        return self._quality.get_comparison_quality_report(comparison_id)

    # --- métricas de uso do LLM (extensão 004) --------------------------------

    def get_usage_metrics(self, run_id: str | None = None) -> UsageSummary | None:
        return self._usage.summarize(run_id, price_reference_date=PRICE_REFERENCE_DATE)


def create_policy_analysis(
    evidence_source,
    extraction_agent,
    explanation_agent,
    *,
    db_path: str = ":memory:",
    output_dir: str = "output",
    currency_rates: dict | None = None,
    usage_collector: UsageMetricsCollector | None = None,
    quality_signals: QualitySignalLog | None = None,
) -> PolicyAnalysisFacade:
    """Monta a fachada com as portas injetadas (testes e E2E com fakes)."""
    return PolicyAnalysisFacade(
        evidence_source,
        extraction_agent,
        explanation_agent,
        db_path=db_path,
        output_dir=output_dir,
        currency_rates=currency_rates,
        usage_collector=usage_collector,
        quality_signals=quality_signals,
    )


def create_document_processing_evidence_source(document_processing_facade=None):
    """Evidências reais via fachada `document_processing` (único elo com o Dev 1)."""
    from .infrastructure.document_processing_source import DocumentProcessingEvidenceSource

    return DocumentProcessingEvidenceSource(facade=document_processing_facade)


def create_default_policy_analysis(
    document_processing_facade=None,
    db_path: str = "exports/policy_analysis.duckdb",
    output_dir: str = "exports",
    model_name: str = "gemini-2.0-flash",
    api_key: str | None = None,
    usage_collector: UsageMetricsCollector | None = None,
    quality_signals: QualitySignalLog | None = None,
) -> PolicyAnalysisFacade:
    """Monta a fachada com os adapters reais (imports lazy — exige libs instaladas)."""
    from .infrastructure.llm_agent import (
        LLMExplanationAgent,
        MultiFieldExtractionAgent,
        PydanticAIClient,
    )

    collector = usage_collector if usage_collector is not None else UsageMetricsCollector()
    client = PydanticAIClient(model_name=model_name, api_key=api_key)
    return PolicyAnalysisFacade(
        create_document_processing_evidence_source(document_processing_facade),
        MultiFieldExtractionAgent(client, usage_collector=collector),
        LLMExplanationAgent(client, usage_collector=collector),
        db_path=db_path,
        output_dir=output_dir,
        usage_collector=collector,
        quality_signals=quality_signals,
    )


__all__ = [
    "ClassifiedError",
    "ComparisonResult",
    "Explanation",
    "Issue",
    "PolicyAnalysisFacade",
    "PolicyAnalysisRepository",
    "QualityReport",
    "QualityService",
    "QualitySignalLog",
    "ReviewItem",
    "SEVERITY_ORDER",
    "Severity",
    "UsageMetricsCollector",
    "UsageSummary",
    "create_default_policy_analysis",
    "create_document_processing_evidence_source",
    "create_policy_analysis",
]
