"""Regras mínimas por campo do catálogo (D2-P0-3, A-08/A-14).

Validações pós-extração, puras e determinísticas: fato que passa no LLM mas
falha na regra vira `NEEDS_REVIEW` (nunca `FOUND`) e cai na fila de revisão.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .field_catalog import FieldDefinition, FieldType
from .value_types import parse_date, parse_decimal


def validate_field_rules(field: FieldDefinition, normalized_value: dict | None) -> list[str]:
    """Retorna as violações de regra do campo (lista vazia = regras ok)."""
    if not normalized_value:
        return [f"{field.code}: valor normalizado ausente"]

    violations: list[str] = []
    code = field.code

    if field.field_type is FieldType.MONEY:
        amount = parse_decimal(normalized_value.get("amount"))
        if code == "franquia":
            if amount < 0:
                violations.append(f"{code}: franquia negativa ({amount})")
        elif amount <= 0:
            violations.append(f"{code}: valor monetário deve ser > 0 (recebido {amount})")

    elif field.field_type is FieldType.NUMBER:
        number = parse_decimal(normalized_value.get("number"))
        if code == "indice_reajuste":
            if number < 0:
                violations.append(f"{code}: índice de reajuste negativo ({number})")
        elif number <= 0:
            violations.append(f"{code}: valor numérico deve ser > 0 (recebido {number})")

    elif field.field_type is FieldType.PERIOD:
        start = parse_date(normalized_value.get("start"))
        end = parse_date(normalized_value.get("end"))
        if end <= start:
            violations.append(f"{code}: período sem duração ({start} a {end})")

    elif field.field_type is FieldType.DATE:
        when = parse_date(normalized_value.get("date"))
        if code == "retroatividade" and when > date.today():
            violations.append(f"{code}: retroatividade não pode ser data futura ({when})")

    elif field.field_type is FieldType.TEXT:
        if not str(normalized_value.get("text", "")).strip():
            violations.append(f"{code}: texto vazio")

    return violations
