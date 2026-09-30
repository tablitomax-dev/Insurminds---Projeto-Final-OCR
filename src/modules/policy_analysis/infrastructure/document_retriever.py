"""Adaptador de evidências sobre a fachada pública do `document_processing`.

RF-01 da spec policy-analysis: o módulo de análise obtém evidências
exclusivamente via `document_processing.public_api` — nunca importa
internos do módulo documental.
"""

from __future__ import annotations

from shared_kernel.contracts import RetrievalQuery, RetrievalResult


class DocumentProcessingRetriever:
    """Porta `EvidenceRetriever` implementada sobre a fachada documental."""

    def __init__(self, document_processing_facade: object) -> None:
        self._facade = document_processing_facade

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        retrieve_evidence = getattr(self._facade, "retrieve_evidence", None)
        if retrieve_evidence is None:
            raise TypeError(
                "fachada inválida: esperado DocumentProcessingFacade com retrieve_evidence"
            )
        return retrieve_evidence(query)
