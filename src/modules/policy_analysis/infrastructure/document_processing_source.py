"""Adaptador da fachada `document_processing` do Dev 1 (RF-01, D-02).

Este é o ÚNICO arquivo do módulo que fala com `document_processing`, e fala
exclusivamente com `document_processing.public_api` (nunca com internos).
A importação é adiada para que o módulo funcione antes da entrega do Dev 1.
"""

from __future__ import annotations

from shared_kernel.contracts import EvidenceRef, RetrievalQuery

from ..application.errors import ClassifiedError


class DocumentProcessingEvidenceSource:
    """Evidências reais via `document_processing.public_api.retrieve_evidence`."""

    def __init__(self, top_k: int = 5, facade=None):
        self._top_k = top_k
        self._facade = facade  # injetado em teste; em produção resolve pela fachada pública

    def _resolve_facade(self):
        if self._facade is not None:
            return self._facade
        try:
            from document_processing import public_api  # somente a fachada (RF-01)
        except ImportError as exc:
            raise ClassifiedError(
                "DOCUMENT_PROCESSING_UNAVAILABLE",
                f"fachada document_processing indisponível: {exc}",
                retriable=True,
            ) from exc
        self._facade = public_api
        return public_api

    def get_evidences(self, policy_id: str, field_code: str | None = None) -> list[EvidenceRef]:
        facade = self._resolve_facade()
        query = RetrievalQuery(
            query=field_code or policy_id,
            policy_id=policy_id,
            field_code=field_code,
            top_k=self._top_k,
        )
        result = facade.retrieve_evidence(query)
        return list(result.evidences)
