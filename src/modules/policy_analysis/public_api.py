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
from .application.review import HumanReviewService
from .domain.catalog import FIELD_CATALOG, get_field_spec
from .domain.comparison import ComparisonResult, normalize_value
from .domain.review import ReviewDecision


class PolicyAnalysisFacade:
    """Fachada consumida pelo workflow/UI — não expõe internals do módulo."""

    def __init__(
        self,
        extraction: ExtractionService,
        comparison: ComparisonService,
        review: HumanReviewService,
    ) -> None:
        self._extraction = extraction
        self._comparison = comparison
        self._review = review

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


def create_policy_analysis(
    retriever: EvidenceRetriever,
    llm_extractor: LlmExtractor,
    repository: FactRepository,
    explanation_generator: ExplanationGenerator,
) -> PolicyAnalysisFacade:
    """Wiring injetável da fachada (testes e composição manual)."""
    return PolicyAnalysisFacade(
        extraction=ExtractionService(
            retriever=retriever,
            llm_extractor=llm_extractor,
            repository=repository,
        ),
        comparison=ComparisonService(
            repository=repository,
            explanation_generator=explanation_generator,
        ),
        review=HumanReviewService(repository=repository),
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
    return create_policy_analysis(
        retriever=retriever,
        llm_extractor=PydanticAiFieldExtractor(model_name=model, api_key=api_key),
        repository=DuckDbFactRepository(db_path),
        explanation_generator=LlmExplanationGenerator(model_name=model, api_key=api_key),
    )


__all__ = [
    "ComparisonResult",
    "EvidenceRef",
    "ExtractedFact",
    "LlmOutputError",
    "PolicyAnalysisFacade",
    "ReviewDecision",
    "create_default_policy_analysis",
    "create_document_processing_retriever",
    "create_policy_analysis",
]
