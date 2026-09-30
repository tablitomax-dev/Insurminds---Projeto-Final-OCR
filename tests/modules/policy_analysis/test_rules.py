"""T-D2P03 — Regras mínimas por campo (D2-P0-3)."""

from __future__ import annotations

from datetime import date

from modules.policy_analysis.domain.field_catalog import get_field
from modules.policy_analysis.domain.rules import validate_field_rules

FUTURE = date.today().replace(year=date.today().year + 1).isoformat()


def test_valores_monetarios_positivos_passam():
    for code in ("limite_agregado", "limite_por_sinistro", "limite_defesa_custos"):
        field = get_field(code)
        assert validate_field_rules(field, {"amount": "1000.00", "currency": "BRL"}) == []


def test_limite_monetario_zero_ou_negativo_falha():
    field = get_field("limite_agregado")
    assert validate_field_rules(field, {"amount": "0.00", "currency": "BRL"})
    assert validate_field_rules(field, {"amount": "-1.00", "currency": "BRL"})


def test_franquia_zero_e_valida_mas_negativa_falha():
    field = get_field("franquia")
    assert validate_field_rules(field, {"amount": "0.00", "currency": "BRL"}) == []
    assert validate_field_rules(field, {"amount": "-10.00", "currency": "BRL"})


def test_prazo_de_notificacao_deve_ser_positivo():
    field = get_field("prazo_notificacao_sinistro")
    assert validate_field_rules(field, {"number": "30"}) == []
    assert validate_field_rules(field, {"number": "0"})
    assert validate_field_rules(field, {"number": "-5"})


def test_indice_de_reajuste_nao_pode_ser_negativo():
    field = get_field("indice_reajuste")
    assert validate_field_rules(field, {"number": "0"}) == []
    assert validate_field_rules(field, {"number": "-1"})


def test_vigencia_precisa_ter_duracao():
    field = get_field("vigencia")
    assert validate_field_rules(field, {"start": "2025-01-01", "end": "2026-01-01", "duration_days": 365}) == []
    assert validate_field_rules(field, {"start": "2026-01-01", "end": "2026-01-01", "duration_days": 0})


def test_retroatividade_nao_pode_ser_futura():
    field = get_field("retroatividade")
    assert validate_field_rules(field, {"date": "2015-01-01"}) == []
    assert validate_field_rules(field, {"date": FUTURE})


def test_texto_vazio_falha():
    field = get_field("extensao_territorial")
    assert validate_field_rules(field, {"text": "mundial"}) == []
    assert validate_field_rules(field, {"text": "   "})


def test_valor_ausente_falha():
    field = get_field("limite_agregado")
    assert validate_field_rules(field, None)
