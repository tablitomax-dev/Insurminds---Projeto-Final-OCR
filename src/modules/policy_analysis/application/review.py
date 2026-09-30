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
from ..domain.value_types import normalize_value


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

    def record_decision(
        self,
        fact_id: str,
        decision: str,
        decided_by: str,
        value: dict | None = None,
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
            new_value = value
            new_normalized = normalize_value(get_field(item.fact.field_code), value)

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
"""Serviço do loop de revisão humana (RF-02, Must do PRD §9, D2-P0-2).

Ações **Confirmar / Corrigir valor / Registrar divergência** por campo/fato.
Toda decisão é persistida com revisor, timestamp, valor original, valor
corrigido (quando houver) e `EvidenceRef` do fato — rastreável na comparação.

Sanitização (T-2a): mensagens citam regra/campo/ID, nunca o valor extraído.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from shared_kernel.contracts import ExtractedFact
from shared_kernel.errors import ContractNotFound, ContractValidationError

from ..domain.catalog import FieldSpec, get_field_spec
from ..domain.review import ReviewAction, ReviewDecision, apply_review
from ..domain.rules import validate_fact
from .ports import FactRepository

#: Aviso usado quando a correção humana não pode ser ligada a evidência.
_EVIDENCE_REQUIRED_MESSAGE = (
    "CORRECT: correção sem EvidenceRef — informe evidence_ids para ligar a correção à evidência"
)


class HumanReviewService:
    """Orquestra a decisão humana sobre fatos sinalizados e a persiste."""

    def __init__(self, repository: FactRepository) -> None:
        self._repository = repository

    def confirm(
        self,
        policy_id: str,
        field_code: str,
        reviewer: str,
        note: str | None = None,
    ) -> tuple[ExtractedFact, ReviewDecision]:
        """Confirma o valor cru do fato (revisor leu a evidência e aceita)."""
        return self._decide(policy_id, field_code, "confirm", reviewer, None, None, note)

    def correct(
        self,
        policy_id: str,
        field_code: str,
        reviewer: str,
        corrected_value: dict[str, Any],
        evidence_ids: list[str] | None = None,
        note: str | None = None,
    ) -> tuple[ExtractedFact, ReviewDecision]:
        """Corrige o valor do fato; o corrigido substitui o cru na comparação."""
        return self._decide(
            policy_id, field_code, "correct", reviewer, corrected_value, evidence_ids, note
        )

    def register_divergence(
        self,
        policy_id: str,
        field_code: str,
        reviewer: str,
        note: str | None = None,
    ) -> tuple[ExtractedFact, ReviewDecision]:
        """Registra divergência sem alterar o fato (segue pendente de correção)."""
        return self._decide(policy_id, field_code, "divergence", reviewer, None, None, note)

    def list_decisions(
        self, policy_id: str | None = None, field_code: str | None = None
    ) -> list[ReviewDecision]:
        """Decisões registradas (auditoria: quem decidiu, quando e o quê)."""
        return self._repository.list_reviews(policy_id, field_code)

    def _decide(
        self,
        policy_id: str,
        field_code: str,
        action: ReviewAction,
        reviewer: str,
        corrected_value: dict[str, Any] | None,
        evidence_ids: list[str] | None,
        note: str | None,
    ) -> tuple[ExtractedFact, ReviewDecision]:
        spec = get_field_spec(field_code)
        who = _safe_reviewer(reviewer)
        fact = self._repository.get_fact(policy_id, field_code)
        if fact is None:
            raise ContractNotFound(f"fato inexistente para revisão: {policy_id}/{field_code}")
        decision = ReviewDecision(
            review_id=f"rev_{uuid4().hex}",
            policy_id=fact.policy_id,
            field_code=fact.field_code,
            fact_id=fact.fact_id,
            action=action,
            reviewer=who,
            reviewed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            original_value=dict(fact.value) if fact.value else None,
            corrected_value=dict(corrected_value) if corrected_value else None,
            evidence_ids=list(evidence_ids) if evidence_ids is not None else list(fact.evidence_ids),
            note=note,
        )
        _ensure_evidence_link(decision, self._repository)
        reviewed = apply_review(fact, decision)
        if action == "correct":
            _ensure_correction_within_rules(spec, reviewed, self._repository)
        self._repository.save_review(decision)
        self._repository.upsert_fact(reviewed)
        return reviewed, decision


def _safe_reviewer(reviewer: str) -> str:
    """Identificador de revisor vazio é rejeitado (quem decidiu é obrigatório)."""
    name = (reviewer or "").strip()
    if not name:
        raise ContractValidationError("revisão sem identificação do revisor")
    return name


def _ensure_evidence_link(
    decision: ReviewDecision, repository: FactRepository
) -> None:
    """Toda decisão fica ligada a um `EvidenceRef` persistido do fato.

    Correção exige evidência sempre (o valor corrigido precisa de lastro);
    `confirm`/`divergence` de um fato sem evidência (`NOT_FOUND`) ficam sem
    link — não existe `EvidenceRef` para uma ausência (EC-05).
    """
    if decision.action == "correct" and not decision.evidence_ids:
        raise ContractValidationError(_EVIDENCE_REQUIRED_MESSAGE)
    if not decision.evidence_ids:
        return
    if any(
        repository.get_evidence(evidence_id) is None for evidence_id in decision.evidence_ids
    ):
        raise ContractValidationError(
            "REVIEW: decisão sem EvidenceRef persistido para o evidence_id informado"
        )


def _ensure_correction_within_rules(
    spec: FieldSpec, reviewed: ExtractedFact, repository: FactRepository
) -> None:
    """Correção humana passa pelas regras do campo (guarda contra erro de digitação).

    `confirm` não recebe regras: o revisor é a autoridade final sobre o valor
    documentado (é exatamente para isso que a fila existe). Mensagem cita só
    regras/campos — nunca o valor (T-2a).
    """
    others = {
        other.field_code: other
        for other in repository.get_facts(reviewed.policy_id)
        if other.field_code != reviewed.field_code
    }
    violations = validate_fact(spec, reviewed, others)
    if violations:
        rules = ", ".join(sorted({violation.rule for violation in violations}))
        raise ContractValidationError(
            "CORRECT: valor corrigido fora das regras do campo"
            f" (field_code={spec.code} regras=[{rules}])"
        )
