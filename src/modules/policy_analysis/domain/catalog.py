"""Catálogo dos 10 campos críticos do vertical slice (RF-02).

O catálogo é a única fonte de `field_code` do módulo: campo fora dele é
rejeitado na fronteira com `ContractValidationError` (EC-07).
"""

from dataclasses import dataclass
from typing import Literal

from shared_kernel.errors import ContractValidationError

#: Tipo do valor comparável de um campo (regra de comparação deriva daqui).
ValueType = Literal["numeric", "date", "text"]


@dataclass(frozen=True)
class FieldSpec:
    """Especificação de um campo do catálogo.

    `semantic` descreve em pt-br o que o campo significa e é o texto usado
    tanto no retrieval quanto no prompt do agente de extração.
    """

    code: str
    label: str
    semantic: str
    value_type: ValueType


#: Catálogo fechado do vertical slice (OQ-01), em ordem estável de exibição.
FIELD_CATALOG: dict[str, FieldSpec] = {
    "limite_agregado": FieldSpec(
        code="limite_agregado",
        label="Limite agregado",
        semantic=(
            "Limite máximo total que a seguradora indeniza no período de "
            "vigência da apólice (teto agregado, em moeda da apólice)."
        ),
        value_type="numeric",
    ),
    "limite_por_sinistro": FieldSpec(
        code="limite_por_sinistro",
        label="Limite por sinistro",
        semantic="Limite máximo indenizável por sinistro individual coberto pela apólice.",
        value_type="numeric",
    ),
    "franquia": FieldSpec(
        code="franquia",
        label="Franquia",
        semantic="Franquia (dedutível) que fica a cargo do segurado em cada sinistro.",
        value_type="numeric",
    ),
    "vigencia_inicio": FieldSpec(
        code="vigencia_inicio",
        label="Início da vigência",
        semantic="Data de início da vigência da apólice.",
        value_type="date",
    ),
    "vigencia_fim": FieldSpec(
        code="vigencia_fim",
        label="Fim da vigência",
        semantic="Data de término da vigência da apólice.",
        value_type="date",
    ),
    "base_territorial": FieldSpec(
        code="base_territorial",
        label="Base territorial",
        semantic="Base territorial de cobertura (regiões ou países em que a apólice responde).",
        value_type="text",
    ),
    "retroatividade": FieldSpec(
        code="retroatividade",
        label="Retroatividade",
        semantic=(
            "Data de retroatividade da cobertura (claims-made): sinistros "
            "conhecidos antes desta data não são cobertos."
        ),
        value_type="date",
    ),
    "prazo_notificacao": FieldSpec(
        code="prazo_notificacao",
        label="Prazo de notificação",
        semantic="Prazo para notificação do sinistro à seguradora (ex.: 30 dias após o conhecimento).",
        value_type="text",
    ),
    "exclusoes_chave": FieldSpec(
        code="exclusoes_chave",
        label="Exclusões-chave",
        semantic="Principais exclusões de cobertura da apólice (riscos expressamente excluídos).",
        value_type="text",
    ),
    "nome_segurado": FieldSpec(
        code="nome_segurado",
        label="Nome do segurado",
        semantic="Nome do segurado (pessoa ou empresa) titular da apólice.",
        value_type="text",
    ),
}


def get_field_spec(field_code: str) -> FieldSpec:
    """Resolve o `field_code` no catálogo (RF-02).

    Fora do catálogo → `ContractValidationError` (EC-07).
    """
    spec = FIELD_CATALOG.get(field_code)
    if spec is None:
        raise ContractValidationError(f"field_code desconhecido: {field_code}")
    return spec
