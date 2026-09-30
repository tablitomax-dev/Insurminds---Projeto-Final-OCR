"""Decisões do loop de revisão humana (RF-02, Must do PRD §9, D2-P0-2).

Ações do analista por campo/fato: **Confirmar**, **Corrigir valor** e
**Registrar divergência**. Toda decisão guarda revisor, timestamp, valor
original, valor corrigido (quando houver) e os `EvidenceRef` do fato.

Módulo puro: stdlib + `shared_kernel` apenas, determinístico (A-08).

Semântica do valor revisado na comparação (decisão registrada em
`actions.md` da feature):
- `confirm`  → o valor cru já revisado vira o valor efetivo (`FOUND`);
- `correct`  → o valor corrigido substitui o cru antes de `compare_policies`
  (o valor original fica registrado na decisão, para auditoria);
- `divergence` → nada muda no fato (segue na fila, pendente de correção);
  a divergência fica registrada com revisor/timestamp/evidência.
"""

from dataclasses import dataclass
from typing import Any, Literal

from shared_kernel.contracts import ExtractedFact

from .catalog import get_field_spec
from .comparison import normalize_value

#: Ação do analista no loop de revisão humana.
ReviewAction = Literal["confirm", "correct", "divergence"]

#: Ações que encerram a pendência do fato (valor efetivo decidido pelo revisor).
CLOSING_ACTIONS: frozenset[str] = frozenset({"confirm", "correct"})


@dataclass(frozen=True)
class ReviewDecision:
    """Decisão humana sobre um fato, ligada aos `EvidenceRef` (auditoria)."""

    review_id: str
    policy_id: str
    field_code: str
    fact_id: str
    action: ReviewAction
    reviewer: str
    reviewed_at: str
    original_value: dict[str, Any] | None
    corrected_value: dict[str, Any] | None
    evidence_ids: list[str]
    note: str | None = None


def apply_review(fact: ExtractedFact, decision: ReviewDecision) -> ExtractedFact:
    """Aplica a decisão humana ao fato (regra pura, determinística).

    - `confirm`: o valor cru é aceito como está — `FOUND` (ou `NOT_FOUND`
      mantido quando o revisor confirma a ausência) e o fato sai da fila;
    - `correct`: o valor corrigido substitui o cru, o normalizado é recalculado
      e o fato sai da fila como `FOUND`;
    - `divergence`: o fato permanece como está (segue na fila de revisão).

    O `fact_id` é preservado: a decisão referencia o fato revisado.
    """
    if decision.fact_id != fact.fact_id:
        raise ValueError("decisão de revisão pertence a outro fact_id")
    if decision.action == "divergence":
        return fact
    if decision.action == "confirm":
        if fact.status == "NOT_FOUND":
            return fact.model_copy(update={"requires_human_review": False})
        return fact.model_copy(update={"status": "FOUND", "requires_human_review": False})
    return _apply_correction(fact, decision)


def _apply_correction(fact: ExtractedFact, decision: ReviewDecision) -> ExtractedFact:
    """Valor corrigido vira o valor efetivo do fato (com normalização nova)."""
    corrected = dict(decision.corrected_value or {})
    spec = get_field_spec(decision.field_code)
    return fact.model_copy(
        update={
            "status": "FOUND",
            "value": corrected,
            "normalized_value": normalize_value(spec, corrected),
            "evidence_ids": list(decision.evidence_ids),
            "requires_human_review": False,
        }
    )
