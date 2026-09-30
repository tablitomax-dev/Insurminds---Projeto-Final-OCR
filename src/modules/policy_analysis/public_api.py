"""Fachada pública do policy_analysis (spec §8, RF-01..RF-08).

ÚNICA entrada do módulo para o resto do sistema (workflow/app/Streamlit):
`extract_field`, `get_facts`, `compare_policies`, `explain_difference`,
`export_comparison` — mais as operações de revisão humana (RF-04).
"""

from __future__ import annotations

from shared_kernel.contracts import ExtractedFact

from .application.comparison_service import ComparisonService
from .application.explanation import ExplanationService
from .application.export import ExportService
from .application.extraction import ExtractionService
from .application.review import ReviewService
from .domain.models import ComparisonResult, Explanation, ReviewItem
from .infrastructure.duckdb_repository import PolicyAnalysisRepository


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
    ):
        self._repo = PolicyAnalysisRepository(db_path)
        self._extraction = ExtractionService(evidence_source, extraction_agent, self._repo)
        self._review = ReviewService(self._repo)
        self._comparison = ComparisonService(self._repo, currency_rates)
        self._explanation = ExplanationService(self._repo, explanation_agent)
        self._export = ExportService(self._repo, output_dir)

    # --- extração (RF-02, RF-03) ----------------------------------------------

    def extract_field(self, policy_id: str, field_code: str) -> ExtractedFact:
        return self._extraction.extract_field(policy_id, field_code)

    def extract_fields(self, policy_id: str, field_codes: list[str]) -> list[ExtractedFact]:
        return self._extraction.extract_fields(policy_id, field_codes)

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        return self._extraction.get_facts(policy_id)

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
"""Fachada pública única do módulo policy_analysis (spec policy-analysis §8).

Importável sem nenhuma lib externa: os adapters reais só entram no wiring
lazy de `create_default_policy_analysis`. A UI e os demais módulos consomem
exclusivamente esta superfície (F-15) — nada de `domain`/`infrastructure`
alheio.
"""

from pathlib import Path
from typing import Any

from shared_kernel.contracts import EvidenceRef, ExtractedFact

from .application.comparison import ComparisonService
from .application.extraction import ExtractionService
from .application.ports import (
    EvidenceRetriever,
    ExplanationGenerator,
    FactRepository,
    LlmExtractor,
    LlmOutputError,
)
from .application.quality import QualityService, QualitySignalLog
from .application.review import HumanReviewService
from .domain.catalog import FIELD_CATALOG, get_field_spec
from .domain.comparison import ComparisonResult, normalize_value
from .domain.metrics import UsageMetricsCollector, UsageSummary
from .domain.quality import SEVERITY_ORDER, Issue, QualityReport, Severity
from .domain.review import ReviewDecision
from .infrastructure.pricing import PRICE_REFERENCE_DATE


class PolicyAnalysisFacade:
    """Fachada consumida pelo workflow/UI — não expõe internals do módulo."""

    def __init__(
        self,
        extraction: ExtractionService,
        comparison: ComparisonService,
        review: HumanReviewService,
        quality: QualityService,
        usage: UsageMetricsCollector,
    ) -> None:
        self._extraction = extraction
        self._comparison = comparison
        self._review = review
        self._quality = quality
        self._usage = usage

    def extract_field(self, policy_id: str, field_code: str) -> ExtractedFact:
        """Extrai um campo de uma apólice com evidência (RF-03)."""
        return self._extraction.extract_field(policy_id, field_code)

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        """Fatos já extraídos de uma apólice."""
        return self._extraction.get_facts(policy_id)

    def get_review_queue(self, policy_id: str | None = None) -> list[ExtractedFact]:
        """Fila de revisão humana (RF-04)."""
        return self._extraction.get_review_queue(policy_id)

    def compare_policies(self, policy_id_a: str, policy_id_b: str) -> ComparisonResult:
        """Comparação determinística campo a campo entre 2 apólices (RF-06).

        O valor efetivo de cada campo é o valor revisado quando existe decisão
        humana (confirmado ou corrigido); sem decisão, o valor cru é usado.
        """
        return self._comparison.compare_policies(policy_id_a, policy_id_b)

    def explain_difference(self, comparison_id: str, field_code: str) -> tuple[str, list[str]]:
        """Explicação da diferença de um campo com evidência citada (RF-07)."""
        return self._comparison.explain_difference(comparison_id, field_code)

    def export_comparison(self, comparison_id: str, export_dir: str | Path = "exports") -> Path:
        """Exporta o resumo da comparação em Markdown standalone (RF-08)."""
        return self._comparison.export_comparison(comparison_id, export_dir)

    def list_fields(self) -> list[dict[str, str]]:
        """Campos do catálogo (code/label/semantic/value_type) para a UI (F-15)."""
        return [
            {
                "code": spec.code,
                "label": spec.label,
                "semantic": spec.semantic,
                "value_type": spec.value_type,
            }
            for spec in FIELD_CATALOG.values()
        ]

    def normalize_field_value(self, field_code: str, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """Normaliza um valor para o escalar comparável — regra única (RNF-01)."""
        return normalize_value(get_field_spec(field_code), value)

    def get_evidence(self, evidence_id: str) -> EvidenceRef | None:
        """`EvidenceRef` persistido de um fato (rastreabilidade da revisão)."""
        return self._extraction.get_evidence(evidence_id)

    def confirm_fact(
        self, policy_id: str, field_code: str, reviewer: str, note: str | None = None
    ) -> tuple[ExtractedFact, ReviewDecision]:
        """Revisão humana: **Confirmar** o valor cru do campo (Must PRD §9)."""
        return self._review.confirm(policy_id, field_code, reviewer, note)

    def correct_fact(
        self,
        policy_id: str,
        field_code: str,
        reviewer: str,
        corrected_value: dict[str, Any],
        evidence_ids: list[str] | None = None,
        note: str | None = None,
    ) -> tuple[ExtractedFact, ReviewDecision]:
        """Revisão humana: **Corrigir valor** — o corrigido alimenta a comparação."""
        return self._review.correct(
            policy_id, field_code, reviewer, corrected_value, evidence_ids, note
        )

    def register_divergence(
        self, policy_id: str, field_code: str, reviewer: str, note: str | None = None
    ) -> tuple[ExtractedFact, ReviewDecision]:
        """Revisão humana: **Registrar divergência** (fato segue pendente)."""
        return self._review.register_divergence(policy_id, field_code, reviewer, note)

    def list_review_decisions(
        self, policy_id: str | None = None, field_code: str | None = None
    ) -> list[ReviewDecision]:
        """Decisões de revisão registradas (quem, quando, valor original/corrigido)."""
        return self._review.list_decisions(policy_id, field_code)

    def list_issues(self, policy_id: str) -> list[Issue]:
        """Issues de qualidade derivados dos sinais existentes (RF-01)."""
        return self._quality.list_issues(policy_id)

    def get_quality_report(self, policy_id: str) -> QualityReport:
        """Relatório de qualidade por documento (RF-01)."""
        return self._quality.get_quality_report(policy_id)

    def get_comparison_quality_report(self, comparison_id: str) -> QualityReport:
        """Relatório de qualidade por comparação (RF-01)."""
        return self._quality.get_comparison_quality_report(comparison_id)

    def get_usage_metrics(self, run_id: str | None = None) -> UsageSummary | None:
        """Métricas do último run (ou do `run_id`) — tokens/custo USD/latência (RF-03)."""
        return self._usage.summarize(run_id, price_reference_date=PRICE_REFERENCE_DATE)


def create_policy_analysis(
    retriever: EvidenceRetriever,
    llm_extractor: LlmExtractor,
    repository: FactRepository,
    explanation_generator: ExplanationGenerator,
    usage_collector: UsageMetricsCollector | None = None,
    quality_signals: QualitySignalLog | None = None,
) -> PolicyAnalysisFacade:
    """Wiring injetável da fachada (testes e composição manual)."""
    collector = usage_collector if usage_collector is not None else UsageMetricsCollector()
    signals = quality_signals if quality_signals is not None else QualitySignalLog()
    return PolicyAnalysisFacade(
        extraction=ExtractionService(
            retriever=retriever,
            llm_extractor=llm_extractor,
            repository=repository,
            quality_signals=signals,
        ),
        comparison=ComparisonService(
            repository=repository,
            explanation_generator=explanation_generator,
        ),
        review=HumanReviewService(repository=repository),
        quality=QualityService(repository=repository, signals=signals),
        usage=collector,
    )


def create_document_processing_retriever(document_processing_facade: object) -> EvidenceRetriever:
    """Monta o `EvidenceRetriever` sobre a fachada do `document_processing` (F-15).

    Quem consome `policy_analysis` não precisa importar `infrastructure`:
    basta passar a `DocumentProcessingFacade` recebida de
    `modules.document_processing.public_api`.
    """
    from .infrastructure.document_retriever import DocumentProcessingRetriever

    return DocumentProcessingRetriever(document_processing_facade)


def create_default_policy_analysis(
    retriever: EvidenceRetriever,
    db_path: str = "data/facts.duckdb",
    model_name: str | None = None,
    api_key: str | None = None,
) -> PolicyAnalysisFacade:
    """Wiring lazy dos adapters reais (DuckDB + Pydantic AI/Gemini).

    O `retriever` é injetado: use `create_document_processing_retriever` com a
    fachada do módulo documental (RF-01 — sem internals alheios).
    """
    from .infrastructure.duckdb_repository import DuckDbFactRepository
    from .infrastructure.llm_extractors import (
        DEFAULT_MODEL,
        LlmExplanationGenerator,
        PydanticAiFieldExtractor,
    )

    model = model_name or DEFAULT_MODEL
    collector = UsageMetricsCollector()
    return create_policy_analysis(
        retriever=retriever,
        llm_extractor=PydanticAiFieldExtractor(
            model_name=model, api_key=api_key, collector=collector
        ),
        repository=DuckDbFactRepository(db_path),
        explanation_generator=LlmExplanationGenerator(
            model_name=model, api_key=api_key, collector=collector
        ),
        usage_collector=collector,
    )


__all__ = [
    "ComparisonResult",
    "EvidenceRef",
    "ExtractedFact",
    "Issue",
    "LlmOutputError",
    "PolicyAnalysisFacade",
    "QualityReport",
    "ReviewDecision",
    "SEVERITY_ORDER",
    "Severity",
    "UsageSummary",
    "create_default_policy_analysis",
    "create_document_processing_retriever",
    "create_policy_analysis",
]
