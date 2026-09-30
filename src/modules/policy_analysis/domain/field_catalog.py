"""Catálogo fechado de `field_code` do vertical slice (RF-02, decisão OQ-01).

É a ÚNICA fonte de `field_code` do módulo: requisição com campo fora do
catálogo é rejeitada na fronteira (RN-05/EC-07). Cada campo carrega o tipo de
valor, que dirige a normalização (domain.value_types) e a regra de comparação
determinística (domain.comparison).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FieldType(str, Enum):
    MONEY = "money"
    NUMBER = "number"
    PERIOD = "period"
    DATE = "date"
    TEXT = "text"


class UnknownFieldCodeError(ValueError):
    """`field_code` fora do catálogo fechado (RN-05)."""


@dataclass(frozen=True)
class FieldDefinition:
    code: str
    label: str
    description: str
    field_type: FieldType
    unit: str | None = None


_FIELDS: tuple[FieldDefinition, ...] = (
    FieldDefinition(
        "limite_agregado",
        "Limite agregado",
        "Teto total pago pela seguradora no período de seguro.",
        FieldType.MONEY,
    ),
    FieldDefinition(
        "limite_por_sinistro",
        "Limite por sinistro",
        "Teto pago por evento/sinistro individual.",
        FieldType.MONEY,
    ),
    FieldDefinition(
        "franquia",
        "Franquia/deducível",
        "Valor a cargo do segurado por sinistro antes da cobertura.",
        FieldType.MONEY,
    ),
    FieldDefinition(
        "vigencia",
        "Vigência",
        "Período de cobertura (início e fim) da apólice.",
        FieldType.PERIOD,
    ),
    FieldDefinition(
        "prazo_notificacao_sinistro",
        "Prazo de notificação de sinistro",
        "Dias após o conhecimento do evento para notificar a seguradora.",
        FieldType.NUMBER,
        unit="dias",
    ),
    FieldDefinition(
        "extensao_territorial",
        "Extensão territorial",
        "Abrangência geográfica da cobertura.",
        FieldType.TEXT,
    ),
    FieldDefinition(
        "exclusoes_chave",
        "Exclusões-chave",
        "Principais exclusões de cobertura listadas na apólice.",
        FieldType.TEXT,
    ),
    FieldDefinition(
        "limite_defesa_custos",
        "Limite de defesa de custos",
        "Teto para custos de defesa judicial/administrativa.",
        FieldType.MONEY,
    ),
    FieldDefinition(
        "retroatividade",
        "Retroatividade (claims-made)",
        "Data a partir da qual fatos geradores são cobertos.",
        FieldType.DATE,
    ),
    FieldDefinition(
        "indice_reajuste",
        "Índice de reajuste/correção",
        "Percentual de reajuste anual aplicado aos limites.",
        FieldType.NUMBER,
        unit="%",
    ),
)

CATALOG: dict[str, FieldDefinition] = {field.code: field for field in _FIELDS}


def get_field(code: str) -> FieldDefinition:
    """Retorna a definição do campo ou levanta `UnknownFieldCodeError` (RN-05)."""
    try:
        return CATALOG[code]
    except KeyError as exc:
        raise UnknownFieldCodeError(
            f"field_code fora do catálogo: {code!r}; válidos: {sorted(CATALOG)}"
        ) from exc


def is_known(code: str) -> bool:
    return code in CATALOG


def all_codes() -> list[str]:
    """Todos os `field_code` na ordem canônica do catálogo."""
    return [field.code for field in _FIELDS]
