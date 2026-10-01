"""Fila de revisão humana (RF-04, RN-03).

Fatos `AMBIGUOUS`/`NEEDS_REVIEW` (ou `requires_human_review`) ficam na fila
com a evidência anexa; a decisão do analista é registrada (quem/decidiu) e vira
fato novo (CORRIGIDO) ou confirmação (CONFIRMADO). A comparação só usa valores
definitivos (fluxo B, EC-02).
"""

from __future__ import annotations

from datetime import datetime, timezone

from shared_kernel.contracts import ExtractedFact

from ..domain.field_catalog import get_field
from ..domain.models import ReviewItem
from ..domain.value_types import normalize_value, raw_value_from_text


class ReviewService:
    """Casos de uso da fila de revisão."""

    def __init__(self, repo):
        self._repo = repo

    def list_pending(self, policy_id: str | None = None) -> list[ReviewItem]:
        return [
            item
            for item in self._repo.get_review_items(policy_id)
            if item.revisao_status == "PENDENTE"
        ]

    def list_decisions(self, policy_id: str | None = None) -> list[ReviewItem]:
        """Histórico de revisões decididas por humano (RF-04).

        Fatos que não precisavam de revisão nascem `CONFIRMADO` sem revisor;
        o sinal de decisão humana é `revisao_por` preenchido.
        """
        return [
            item
            for item in self._repo.get_review_items(policy_id)
            if item.revisao_por is not None
        ]

    def record_decision(
        self,
        fact_id: str,
        decision: str,
        decided_by: str,
        value: dict | str | None = None,
    ) -> ExtractedFact:
        if decision not in ("CONFIRMADO", "CORRIGIDO"):
            raise ValueError(f"decisão inválida: {decision!r}")
        item = self._repo.get_review_item(fact_id)
        if item is None:
            raise ValueError(f"fato não encontrado: {fact_id!r}")

        new_value = None
        new_normalized = None
        if decision == "CORRIGIDO":
            if value is None:
                raise ValueError("decisão CORRIGIDO exige value")
            field = get_field(item.fact.field_code)
            if isinstance(value, str):
                value = raw_value_from_text(field, value, original=item.fact.value)
            new_value = value
            new_normalized = normalize_value(field, value)

        self._repo.record_review(
            fact_id,
            decision,
            {"decisao": decision, "value": value},
            decided_by,
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            new_value=new_value,
            new_normalized_value=new_normalized,
            new_status="FOUND",
            requires_human_review=False,
        )
        return self._repo.get_review_item(fact_id).fact
