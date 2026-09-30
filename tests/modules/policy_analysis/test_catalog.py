"""RF-02 + EC-07: catálogo fechado dos 10 field_code do vertical slice."""

import pytest

from modules.policy_analysis.domain.catalog import FIELD_CATALOG, get_field_spec
from shared_kernel.errors import ContractValidationError

EXPECTED_CODES = [
    "limite_agregado",
    "limite_por_sinistro",
    "franquia",
    "vigencia_inicio",
    "vigencia_fim",
    "base_territorial",
    "retroatividade",
    "prazo_notificacao",
    "exclusoes_chave",
    "nome_segurado",
]

EXPECTED_VALUE_TYPES = {
    "limite_agregado": "numeric",
    "limite_por_sinistro": "numeric",
    "franquia": "numeric",
    "vigencia_inicio": "date",
    "vigencia_fim": "date",
    "base_territorial": "text",
    "retroatividade": "date",
    "prazo_notificacao": "text",
    "exclusoes_chave": "text",
    "nome_segurado": "text",
}


def test_catalogo_tem_exatamente_os_dez_codigos():
    assert list(FIELD_CATALOG) == EXPECTED_CODES


def test_get_field_spec_resolve_todos_os_codigos():
    for code in EXPECTED_CODES:
        spec = get_field_spec(code)
        assert spec.code == code
        assert spec.label.strip()
        assert spec.semantic.strip()
        assert spec.value_type == EXPECTED_VALUE_TYPES[code]


def test_field_code_desconhecido_e_rejeitado():
    with pytest.raises(ContractValidationError):
        get_field_spec("campo_inventado")
