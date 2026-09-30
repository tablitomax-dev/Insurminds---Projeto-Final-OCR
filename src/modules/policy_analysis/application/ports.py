"""Portas (typing.Protocol) do módulo policy_analysis (D-02).

Os adapters reais vivem em `infrastructure/`; os testes usam fakes.
`LlmOutputError` classifica saída inválida de LLM como falha reexecutável
(RF-09) — nunca vira fato.
"""

from typing import Protocol

from shared_kernel.contracts import (
    EvidenceRef,
    ExtractedFact,
    ExtractionRequest,
    RetrievalQuery,
    RetrievalResult,
)

from ..domain.comparison import ComparisonResult
from ..domain.review import ReviewDecision


class LlmOutputError(Exception):
    """Saída do LLM fora do contrato — falha classificada e reexecutável (RF-09)."""


class EvidenceRetriever(Protocol):
    """Porta de recuperação de evidências (RF-01: via `document_processing`)."""

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...


class LlmExtractor(Protocol):
    """Porta de extração de um campo por LLM (deve devolver `ExtractedFact`)."""

    def extract(self, request: ExtractionRequest) -> ExtractedFact: ...


class ExplanationGenerator(Protocol):
    """Porta de explicação de diferença por LLM (devolve texto + IDs citados)."""

    def explain(
        self,
        field_code: str,
        direction: str,
        fact_a: ExtractedFact | None,
        fact_b: ExtractedFact | None,
        evidences_a: list[EvidenceRef],
        evidences_b: list[EvidenceRef],
    ) -> tuple[str, list[str]]: ...


class FactRepository(Protocol):
    """Porta de persistência de fatos, evidências e comparações (RF-05)."""

    def upsert_fact(self, fact: ExtractedFact) -> None: ...

    def get_facts(self, policy_id: str) -> list[ExtractedFact]: ...

    def get_fact(self, policy_id: str, field_code: str) -> ExtractedFact | None: ...

    def list_review_queue(self, policy_id: str | None = None) -> list[ExtractedFact]: ...

    def save_evidence(self, evidence: EvidenceRef) -> None: ...

    def get_evidence(self, evidence_id: str) -> EvidenceRef | None: ...

    def save_comparison(self, result: ComparisonResult) -> None: ...

    def get_comparison(self, comparison_id: str) -> ComparisonResult | None: ...

    def save_review(self, decision: ReviewDecision) -> None: ...

    def list_reviews(
        self, policy_id: str | None = None, field_code: str | None = None
    ) -> list[ReviewDecision]: ...
