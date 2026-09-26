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
