"""Fachada pública única do módulo policy_analysis (spec policy-analysis §8).

Importável sem nenhuma lib externa: os adapters reais só entram no wiring
lazy de `create_default_policy_analysis`.
"""

from pathlib import Path

from shared_kernel.contracts import ExtractedFact

from .application.comparison import ComparisonService
from .application.extraction import ExtractionService
from .application.ports import (
    EvidenceRetriever,
    ExplanationGenerator,
    FactRepository,
    LlmExtractor,
)
from .domain.comparison import ComparisonResult


class PolicyAnalysisFacade:
    """Fachada consumida pelo workflow/UI — não expõe internals do módulo."""

    def __init__(self, extraction: ExtractionService, comparison: ComparisonService) -> None:
        self._extraction = extraction
        self._comparison = comparison

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
        """Comparação determinística campo a campo entre 2 apólices (RF-06)."""
        return self._comparison.compare_policies(policy_id_a, policy_id_b)

    def explain_difference(self, comparison_id: str, field_code: str) -> tuple[str, list[str]]:
        """Explicação da diferença de um campo com evidência citada (RF-07)."""
        return self._comparison.explain_difference(comparison_id, field_code)

    def export_comparison(self, comparison_id: str, export_dir: str | Path = "exports") -> Path:
        """Exporta o resumo da comparação em Markdown standalone (RF-08)."""
        return self._comparison.export_comparison(comparison_id, export_dir)


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
    )


def create_default_policy_analysis(
    retriever: EvidenceRetriever,
    db_path: str = "data/facts.duckdb",
    model_name: str | None = None,
    api_key: str | None = None,
) -> PolicyAnalysisFacade:
    """Wiring lazy dos adapters reais (DuckDB + Pydantic AI/Gemini).

    O `retriever` é injetado: deve embrulhar `document_processing.public_api`
    (`retrieve_evidence`) — o módulo nunca importa internals do módulo
    documental (RF-01).
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
