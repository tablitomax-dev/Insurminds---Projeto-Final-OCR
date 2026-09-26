"""T006 — Catálogo fechado de campos (RF-02, RN-05)."""

from __future__ import annotations

import pytest

from modules.policy_analysis.domain.field_catalog import (
    CATALOG,
    UnknownFieldCodeError,
    all_codes,
    get_field,
    is_known,
)

EXPECTED_CODES = {
    "limite_agregado",
    "limite_por_sinistro",
    "franquia",
    "vigencia",
    "prazo_notificacao_sinistro",
    "extensao_territorial",
    "exclusoes_chave",
    "limite_defesa_custos",
    "retroatividade",
    "indice_reajuste",
}


def test_catalogo_tem_os_10_campos_do_vertical_slice():
    assert set(all_codes()) == EXPECTED_CODES
    assert len(CATALOG) == 10


def test_cada_campo_tem_semantica_e_tipo():
    for code in all_codes():
        field = get_field(code)
        assert field.label
        assert field.description
        assert field.field_type is not None


def test_field_code_fora_do_catalogo_e_rejeitado():
    with pytest.raises(UnknownFieldCodeError):
        get_field("limite_inexistente")
    assert not is_known("limite_inexistente")
    assert is_known("franquia")


def test_ordem_canonica_estavel():
    assert all_codes()[0] == "limite_agregado"
    assert all_codes()[-1] == "indice_reajuste"
