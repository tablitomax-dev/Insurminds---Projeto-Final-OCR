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
"""Normalização e regras determinísticas de comparação (RF-06, RNF-01).

Módulo puro: sem LLM, sem I/O. A mesma entrada produz sempre a mesma saída.

Semântica da `direction`: relação do valor de A em relação a B
(`"maior"` significa A > B). Lados ausentes (fato inexistente ou
`status="NOT_FOUND"`) viram `"ausente_*"`; valor sem escalar comparável
(EC-04) vira `"divergente"`.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from shared_kernel.contracts import ExtractedFact

from .catalog import FieldSpec

#: Direção determinística da comparação de um campo.
Direction = Literal[
    "maior",
    "menor",
    "igual",
    "ausente_a",
    "ausente_b",
    "ausente_ambas",
    "divergente",
]

#: Chaves candidatas ao escalar comparável dentro de `value`/`normalized_value`.
_SCALAR_KEYS = (
    "scalar",
    "value",
    "amount",
    "valor",
    "date",
    "data",
    "text",
    "texto",
    "raw_text",
)

_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_PT_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_NON_NUMERIC = re.compile(r"[^\d,.\-]")


@dataclass(frozen=True)
class FieldComparison:
    """Resultado da comparação de um campo entre duas apólices."""

    field_code: str
    direction: Direction
    value_a: dict[str, Any] | None
    value_b: dict[str, Any] | None
    normalized_a: dict[str, Any] | None
    normalized_b: dict[str, Any] | None
    fact_id_a: str | None
    fact_id_b: str | None
    evidence_ids_a: list[str]
    evidence_ids_b: list[str]


@dataclass(frozen=True)
class ComparisonResult:
    """Comparação completa de 2 apólices, identificada por `ComparisonId`."""

    comparison_id: str
    policy_id_a: str
    policy_id_b: str
    rows: list[FieldComparison]


def normalize_value(spec: FieldSpec, value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extrai o escalar comparável em `{"scalar": ...}` (valor ilegível → `None`).

    - `numeric` → `float`
    - `date` → string ISO `YYYY-MM-DD`
    - `text` → `str` em minúsculas (`casefold`) e sem espaços nas bordas
    """
    raw = _raw_scalar(value)
    if raw is None:
        return None
    if spec.value_type == "numeric":
        scalar: Any = _to_float(raw)
    elif spec.value_type == "date":
        scalar = _to_iso_date(raw)
    else:
        scalar = _to_text(raw)
    if scalar is None:
        return None
    return {"scalar": scalar}


def compare_field(
    spec: FieldSpec,
    fact_a: ExtractedFact | None,
    fact_b: ExtractedFact | None,
) -> FieldComparison:
    """Compara um campo entre os fatos das duas apólices (regra pura)."""
    missing_a = _is_missing(fact_a)
    missing_b = _is_missing(fact_b)
    normalized_a = None if missing_a else _comparable(spec, fact_a)
    normalized_b = None if missing_b else _comparable(spec, fact_b)
    if missing_a and missing_b:
        direction: Direction = "ausente_ambas"
    elif missing_a:
        direction = "ausente_a"
    elif missing_b:
        direction = "ausente_b"
    else:
        direction = _direction(spec, normalized_a, normalized_b)
    return FieldComparison(
        field_code=spec.code,
        direction=direction,
        value_a=fact_a.value if fact_a is not None else None,
        value_b=fact_b.value if fact_b is not None else None,
        normalized_a=normalized_a,
        normalized_b=normalized_b,
        fact_id_a=fact_a.fact_id if fact_a is not None else None,
        fact_id_b=fact_b.fact_id if fact_b is not None else None,
        evidence_ids_a=list(fact_a.evidence_ids) if fact_a is not None else [],
        evidence_ids_b=list(fact_b.evidence_ids) if fact_b is not None else [],
    )


def _is_missing(fact: ExtractedFact | None) -> bool:
    """Fato ausente ou `NOT_FOUND` conta como lado ausente (EC-03)."""
    return fact is None or fact.status == "NOT_FOUND"


def _comparable(spec: FieldSpec, fact: ExtractedFact | None) -> dict[str, Any] | None:
    """Normaliza o fato: prefere `normalized_value` e cai para `value`."""
    if fact is None:
        return None
    normalized = normalize_value(spec, fact.normalized_value)
    if normalized is not None:
        return normalized
    return normalize_value(spec, fact.value)


def _direction(
    spec: FieldSpec,
    normalized_a: dict[str, Any] | None,
    normalized_b: dict[str, Any] | None,
) -> Direction:
    scalar_a = normalized_a.get("scalar") if normalized_a is not None else None
    scalar_b = normalized_b.get("scalar") if normalized_b is not None else None
    if scalar_a is None or scalar_b is None:
        # EC-04: pelo menos um lado ficou sem valor comparável.
        return "divergente"
    if spec.value_type == "text":
        return "igual" if scalar_a == scalar_b else "divergente"
    if scalar_a > scalar_b:
        return "maior"
    if scalar_a < scalar_b:
        return "menor"
    return "igual"


def _raw_scalar(value: dict[str, Any] | None) -> Any:
    if not isinstance(value, dict):
        return None
    for key in _SCALAR_KEYS:
        candidate = value.get(key)
        if candidate is not None:
            return candidate
    return None


def _to_float(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        text = _NON_NUMERIC.sub("", raw.strip())
        if "," in text:  # formato pt-br: 1.234.567,89
            text = text.replace(".", "").replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _to_iso_date(raw: Any) -> str | None:
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    if isinstance(raw, str):
        text = raw.strip()
        iso_match = _ISO_DATE.fullmatch(text)
        pt_match = _PT_DATE.fullmatch(text)
        if iso_match:
            year, month, day = (int(part) for part in iso_match.groups())
        elif pt_match:
            day, month, year = (int(part) for part in pt_match.groups())
        else:
            return None
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    return None


def _to_text(raw: Any) -> str | None:
    text = str(raw).strip().casefold()
    return text or None
