"""Adaptador da fachada `document_processing` do Dev 1 (RF-01, D-02).

Este é o ÚNICO arquivo do módulo que fala com `document_processing`, e fala
exclusivamente com `document_processing.public_api` (nunca com internos).
A importação é adiada para que o módulo funcione antes da entrega do Dev 1.
"""

from __future__ import annotations

from shared_kernel.contracts import EvidenceRef, RetrievalQuery

from ..application.errors import ClassifiedError


class DocumentProcessingEvidenceSource:
    """Evidências reais via `document_processing.public_api.retrieve_evidence`.

    Com `field_code` ausente (pedido de "todas as evidências" da extração),
    o resultado de várias consultas é mesclado — cada consulta traz até
    `top_k` trechos (o contrato `RetrievalQuery` limita `top_k` a 20) e o
    merge dá cobertura ao documento inteiro, sem quebrar o contrato.
    """

    #: Consultas ampliadas para a cobertura total do documento (extração).
    _BREADTH_QUERIES = (
        "limite cobertura franquia deducível",
        "vigência prazo notificação sinistro",
        "exclusões extensão territorial defesa de custos",
        "retroatividade reajuste condições gerais",
    )

    def __init__(self, top_k: int = 20, facade=None):
        self._top_k = min(top_k, 20)  # teto do contrato `RetrievalQuery`
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
        query_texts = [field_code or policy_id]
        if field_code is None:
            query_texts.extend(self._BREADTH_QUERIES)
        merged: dict[str, EvidenceRef] = {}
        for query_text in query_texts:
            query = RetrievalQuery(
                query=query_text,
                policy_id=policy_id,
                field_code=field_code,
                top_k=self._top_k,
            )
            for evidence in facade.retrieve_evidence(query).evidences:
                merged.setdefault(evidence.evidence_id, evidence)
        return list(merged.values())
