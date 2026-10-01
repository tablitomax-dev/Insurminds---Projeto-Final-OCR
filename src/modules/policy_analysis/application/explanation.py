"""Explicação rastreável de diferenças (RF-07, RN-02).

O LLM explica, mas a explicação só é aceita se citar `evidence_ids` reais dos
dois lados comparados — citação desconhecida ou unilateral é rejeitada como
`ClassifiedError` reexecutável. A explicação aceita fica persistida na linha
da comparação.
"""

from __future__ import annotations

import uuid
from typing import cast

from ..domain.models import Explanation, FieldComparison
from .errors import ClassifiedError


def fallback_explanation(campo: FieldComparison) -> tuple[str, list[str]]:
    """Explicação determinística quando o LLM falha (D2-P2-1).

    Saída fixa no formato do resultado da comparação (MAIOR/MENOR/IGUAL/…)
    citando as evidências dos dois lados — a UI nunca quebra por falta de
    explicação. Determinística: mesma entrada, mesmo texto.
    """
    ids = list(dict.fromkeys([*campo.evidencias_a, *campo.evidencias_b]))
    partes = [f"Comparação de {campo.field_code}: {campo.resultado}."]
    if campo.direcao:
        partes.append(f"Direção: {campo.direcao}.")
    partes.append(f"Evidências citadas: {', '.join(ids) if ids else 'nenhuma'}.")
    return " ".join(partes), ids


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
        try:
            raw = self._agent.explain(campo, run_id)  # falha do provedor → ClassifiedError
        except ClassifiedError:
            # D2-P2-1: provedor do LLM indisponível → fallback determinístico; a
            # UI nunca quebra por falta de explicação. A validação de citação
            # (RN-02) continua valendo quando o LLM responde.
            text, evidence_ids = fallback_explanation(campo)
        else:
            text, evidence_ids = self._validated(campo, raw)

        self._repo.update_explanation(comparison_id, field_code, text)
        return Explanation(
            comparison_id=comparison_id,
            field_code=field_code,
            text=text,
            evidence_ids=tuple(evidence_ids),
        )

    def _validated(self, campo: FieldComparison, raw: dict) -> tuple[str, list[str]]:
        """Valida a explicação do LLM (RN-02: cita evidência real dos dois lados)."""
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
                f"explicação de {campo.field_code} sem evidência citada dos dois lados",
                retriable=True,
            )
        return cast(str, text), cast(list[str], evidence_ids)
