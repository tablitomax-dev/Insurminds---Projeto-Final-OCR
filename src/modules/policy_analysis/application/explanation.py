"""Explicação rastreável de diferenças (RF-07, RN-02).

O LLM explica, mas a explicação só é aceita se citar `evidence_ids` reais dos
dois lados comparados — citação desconhecida ou unilateral é rejeitada como
`ClassifiedError` reexecutável. A explicação aceita fica persistida na linha
da comparação.
"""

from __future__ import annotations

import uuid

from ..domain.models import Explanation
from .errors import ClassifiedError


class ExplanationService:
    """Casos de uso de explicação por diferença."""

    def __init__(self, repo, agent):
        self._repo = repo
        self._agent = agent

    def explain_difference(self, comparison_id: str, field_code: str) -> Explanation:
        result = self._repo.get_comparison(comparison_id)
        if result is None:
            raise ClassifiedError(
                "COMPARISON_NOT_FOUND", f"comparação não encontrada: {comparison_id}", retriable=False
            )
        campo = result.campo(field_code)
        if campo is None:
            raise ClassifiedError(
                "COMPARISON_FIELD_NOT_FOUND",
                f"campo {field_code!r} não faz parte da comparação {comparison_id}",
                retriable=False,
            )

        run_id = str(uuid.uuid4())
        raw = self._agent.explain(campo, run_id)  # falha do provedor → ClassifiedError

        text = raw.get("text")
        evidence_ids = raw.get("evidence_ids") or []
        allowed = set(campo.evidencias_a) | set(campo.evidencias_b)

        valid = (
            isinstance(text, str)
            and bool(text.strip())
            and isinstance(evidence_ids, list)
            and bool(evidence_ids)
            and set(evidence_ids) <= allowed
        )
        if campo.evidencias_a:
            valid = valid and bool(set(evidence_ids) & set(campo.evidencias_a))
        if campo.evidencias_b:
            valid = valid and bool(set(evidence_ids) & set(campo.evidencias_b))

        if not valid:
            raise ClassifiedError(
                "EXPLANATION_NOT_CITED",
                f"explicação de {field_code} sem evidência citada dos dois lados",
                retriable=True,
            )

        self._repo.update_explanation(comparison_id, field_code, text)
        return Explanation(
            comparison_id=comparison_id,
            field_code=field_code,
            text=text,
            evidence_ids=tuple(evidence_ids),
        )
