"""Comparação determinística campo a campo (RN-01, RN-04, RN-06, OQ-03).

Função pura: sem LLM, sem I/O, sem aleatoriedade. Mesma entrada → mesma
saída (RNF-01). A comparação nunca é erro: campo ausente vira diferença por
omissão; fato pendente de revisão fica AGUARDANDO_REVISAO (fluxo B, EC-02).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from shared_kernel.contracts import ExtractedFact

from .field_catalog import FieldDefinition, FieldType
from .models import FieldComparison
from .value_types import (
    date_key,
    money_key,
    number_key,
    period_key,
    text_key,
)

RESULT_MAIOR = "MAIOR"
RESULT_MENOR = "MENOR"
RESULT_IGUAL = "IGUAL"
RESULT_DIVERGENTE = "DIVERGENTE"
RESULT_AUSENTE_A = "AUSENTE_A"
RESULT_AUSENTE_B = "AUSENTE_B"
RESULT_AUSENTES_AMBOS = "AUSENTES_AMBOS"
RESULT_AGUARDANDO_REVISAO = "AGUARDANDO_REVISAO"

_COMPARISON_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


def comparison_id(policy_id_a: str, policy_id_b: str) -> str:
    """`ComparisonId` determinístico do par (idempotência, EC-06/D-09)."""
    return str(uuid.uuid5(_COMPARISON_NAMESPACE, f"insurminds:comparison:{policy_id_a}|{policy_id_b}"))


def _is_absent(fact: ExtractedFact | None) -> bool:
    return fact is None or fact.status == "NOT_FOUND"


def _is_pending(fact: ExtractedFact | None) -> bool:
    return fact is not None and (
        fact.requires_human_review or fact.status in ("AMBIGUOUS", "NEEDS_REVIEW")
    )


def _money_in_brl(fact: ExtractedFact, currency_rates: dict[str, Decimal] | None) -> Decimal:
    normalized = fact.normalized_value or {}
    currency = str(normalized.get("currency", "BRL")).upper()
    if currency != "BRL":
        rates = currency_rates or {}
        if currency not in rates:
            raise ValueError(f"sem taxa de câmbio para {currency}; informe currency_rates[{currency!r}]")
        return money_key(normalized, rates[currency])
    return money_key(normalized, Decimal("1"))


def compare_facts(
    field: FieldDefinition,
    fact_a: ExtractedFact | None,
    fact_b: ExtractedFact | None,
    currency_rates: dict[str, Decimal] | None = None,
) -> FieldComparison:
    """Compara dois fatos do mesmo campo por regra determinística por tipo."""
    valor_a = fact_a.normalized_value if fact_a else None
    valor_b = fact_b.normalized_value if fact_b else None
    evidencias_a = tuple(fact_a.evidence_ids) if fact_a else ()
    evidencias_b = tuple(fact_b.evidence_ids) if fact_b else ()

    if _is_pending(fact_a) or _is_pending(fact_b):
        return FieldComparison(
            field.code, RESULT_AGUARDANDO_REVISAO, valor_a, valor_b, "n/a", evidencias_a, evidencias_b
        )

    ausente_a = _is_absent(fact_a)
    ausente_b = _is_absent(fact_b)
    if ausente_a and ausente_b:
        return FieldComparison(
            field.code, RESULT_AUSENTES_AMBOS, valor_a, valor_b, "n/a", evidencias_a, evidencias_b
        )
    if ausente_a:
        return FieldComparison(
            field.code, RESULT_AUSENTE_A, valor_a, valor_b, "n/a", evidencias_a, evidencias_b
        )
    if ausente_b:
        return FieldComparison(
            field.code, RESULT_AUSENTE_B, valor_a, valor_b, "n/a", evidencias_a, evidencias_b
        )

    resultado = _compare_by_type(field, fact_a, fact_b, currency_rates)
    direcao = {"MAIOR": "A", "MENOR": "B", "IGUAL": "igual"}.get(resultado, "n/a")
    return FieldComparison(
        field.code, resultado, valor_a, valor_b, direcao, evidencias_a, evidencias_b
    )


def _compare_by_type(
    field: FieldDefinition,
    fact_a: ExtractedFact,
    fact_b: ExtractedFact,
    currency_rates: dict[str, Decimal] | None,
) -> str:
    a = fact_a.normalized_value or {}
    b = fact_b.normalized_value or {}

    if field.field_type is FieldType.MONEY:
        return _cmp(_money_in_brl(fact_a, currency_rates), _money_in_brl(fact_b, currency_rates))
    if field.field_type is FieldType.NUMBER:
        return _cmp(number_key(a), number_key(b))
    if field.field_type is FieldType.DATE:
        return _cmp(date_key(a), date_key(b))
    if field.field_type is FieldType.PERIOD:
        start_a, end_a = period_key(a)
        start_b, end_b = period_key(b)
        if (start_a, end_a) == (start_b, end_b):
            return RESULT_IGUAL
        if (end_a - start_a).days != (end_b - start_b).days:
            return _cmp((end_a - start_a).days, (end_b - start_b).days)
        return RESULT_DIVERGENTE
    # TEXT: igualdade após normalização; semântica fica com o analista (OQ-03)
    return RESULT_IGUAL if text_key(a) == text_key(b) else RESULT_DIVERGENTE


def _cmp(a, b) -> str:
    if a > b:
        return RESULT_MAIOR
    if a < b:
        return RESULT_MENOR
    return RESULT_IGUAL
