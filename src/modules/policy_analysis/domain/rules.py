"""Regras mínimas por campo do catálogo (D2-P0-3, determinístico — A-08).

Validações pós-extração, pós-normalização, que rebaixam o fato para
`NEEDS_REVIEW` quando falham (nunca `FOUND`). Regras puras: não persistem,
não chamam LLM, não dependem de estado — só leem o valor normalizado.

Regras implementadas sobre o catálogo vigente (`field_catalog`):
- `valor_positivo` — campos monetários/numéricos com escalar > 0 (a `franquia`
  aceita 0, pois "sem franquia" é válido).
- `moeda_conhecida` — moeda monetária declarada em um conjunto ISO usual D&O.
- `moeda_consistente` — campos monetários da mesma apólice com a mesma moeda
  (regra cruzada: recebe os demais valores monetários da apólice).
- `vigencia_ordem` — `vigencia.inicio <= vigencia.fim` (regra cruzada; cobre
  valores montados fora da normalização).
- `enum_base_territorial` — `extensao_territorial` ∈ vocabulário fechado de
  abrangências usuais D&O (fora do enum → sinal de revisão ao humano).

Motivos citam apenas regra/campo — nunca o valor (T-2a).
"""

from __future__ import annotations

from dataclasses import dataclass

from .field_catalog import FieldDefinition, FieldType
from .value_types import NormalizationError, normalize_text

#: Moedas usuais em apólices D&O (ISO 4217).
KNOWN_CURRENCIES: frozenset[str] = frozenset(
    {"BRL", "USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD"}
)

#: Campos cujo escalar deve ser estrictamente positivo (limites/prazos/índice).
_POSITIVE_CODES: frozenset[str] = frozenset(
    {
        "limite_agregado",
        "limite_por_sinistro",
        "limite_defesa_custos",
        "prazo_notificacao_sinistro",
        "indice_reajuste",
    }
)

#: Vocabulário fechado da base/extensão territorial (D2-P0-3, `enum_base_territorial`).
#: Formas canônicas já normalizadas (minúsculas, sem acentos — `normalize_text`).
KNOWN_TERRITORY_BASES: frozenset[str] = frozenset(
    {
        "brasil",
        "eua",
        "estados unidos",
        "canada",
        "europa",
        "america latina",
        "america do sul",
        "america do norte",
        "mundo",
        "mundial",
        "worldwide",
        "internacional",
        "exterior",
    }
)

#: Chaves de escalar numérico/monetário no valor normalizado.
_AMOUNT_KEYS = ("amount", "number")


@dataclass(frozen=True)
class RuleViolation:
    """Violação de regra de campo; motivo sanitizado (só regra/campo, T-2a)."""

    rule: str
    field_code: str
    reason: str

    def to_dict(self) -> dict:
        return {"rule": self.rule, "field_code": self.field_code, "reason": self.reason}


def _scalar(raw: dict, key: str) -> str | None:
    value = raw.get(key)
    return str(value) if value is not None else None


def _as_decimal(raw: str | None):
    from decimal import Decimal, InvalidOperation

    if raw is None:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _rule_valor_positivo(field: FieldDefinition, normalized: dict) -> list[RuleViolation]:
    if field.field_type not in (FieldType.MONEY, FieldType.NUMBER):
        return []
    key = "amount" if field.field_type is FieldType.MONEY else "number"
    number = _as_decimal(_scalar(normalized, key))
    if number is None:
        return []  # sem escalar legível → sem regra (normalização cuida)
    if number < 0:
        return [
            RuleViolation("valor_positivo", field.code, "valor negativo é inválido")
        ]
    if field.code in _POSITIVE_CODES and number == 0:
        return [
            RuleViolation("valor_positivo", field.code, "campo exige valor estritamente positivo")
        ]
    return []


def _rule_moeda_conhecida(field: FieldDefinition, normalized: dict) -> list[RuleViolation]:
    if field.field_type is not FieldType.MONEY:
        return []
    currency = str(normalized.get("currency", "")).upper()
    if currency and currency not in KNOWN_CURRENCIES:
        return [RuleViolation("moeda_conhecida", field.code, "moeda fora do conjunto conhecido")]
    return []


def _rule_moeda_consistente(
    field: FieldDefinition, normalized: dict, others: list[dict] | None
) -> list[RuleViolation]:
    """Moedas monetárias da mesma apólice devem coincidir (regra cruzada).

    Intenção (§8.2): apólice com moedas mistas é rara, mas legal — em vez de
    validar/inventar câmbio aqui, rebaixamos todos os monetários para
    `NEEDS_REVIEW`, sinalizando ao humano para decidir. É sinal, não erro.
    """
    if field.field_type is not FieldType.MONEY:
        return []
    currency = str(normalized.get("currency", "")).upper()
    if not currency:
        return []
    for other in others or []:
        other_currency = str(other.get("currency", "")).upper()
        if other_currency and other_currency != currency:
            return [
                RuleViolation(
                    "moeda_consistente",
                    field.code,
                    "campos monetários da mesma apólice com moedas distintas",
                )
            ]
    return []


def _rule_vigencia_ordem(field: FieldDefinition, normalized: dict) -> list[RuleViolation]:
    if field.field_type is not FieldType.PERIOD:
        return []
    start = str(normalized.get("start", ""))
    end = str(normalized.get("end", ""))
    if start and end and start > end:
        return [RuleViolation("vigencia_ordem", field.code, "início posterior ao fim")]
    return []


def _rule_enum_base_territorial(
    field: FieldDefinition, normalized: dict
) -> list[RuleViolation]:
    """`extensao_territorial` ∈ vocabulário fechado de abrangências D&O.

    Fora do enum → `NEEDS_REVIEW` (sinal ao humano, não erro): texto livre
    fora do vocabulário pode ser legítimo (ex.: "Mundo exceto EUA"), mas o
    determinismo da comparação agradece o enum fechado (A-08) — o analista
    decide na revisão.
    """
    if field.code != "extensao_territorial":
        return []
    raw = normalized.get("text")
    if not raw:
        return []
    try:
        text = normalize_text(str(raw))
    except NormalizationError:
        return []
    if text in KNOWN_TERRITORY_BASES:
        return []
    return [
        RuleViolation(
            "enum_base_territorial",
            field.code,
            "valor fora do enum de abrangência territorial",
        )
    ]


def validate_fact(
    field: FieldDefinition,
    normalized: dict | None,
    other_money_values: list[dict] | None = None,
) -> list[RuleViolation]:
    """Avalia as regras do campo sobre o valor normalizado.

    `other_money_values` são os `normalized_value` monetários já extraídos da
    mesma apólice (para a regra cruzada `moeda_consistente`). Valor `None` ou
    sem escalar legível não dispara regra (a normalização já tratou EC-04).
    """
    if normalized is None:
        return []
    violations: list[RuleViolation] = []
    violations += _rule_valor_positivo(field, normalized)
    violations += _rule_moeda_conhecida(field, normalized)
    violations += _rule_moeda_consistente(field, normalized, other_money_values)
    violations += _rule_vigencia_ordem(field, normalized)
    violations += _rule_enum_base_territorial(field, normalized)
    return violations
