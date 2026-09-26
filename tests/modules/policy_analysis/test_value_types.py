"""T007 — Value objects e normalização por tipo (D-05, OQ-03)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from modules.policy_analysis.domain.value_types import (
    Money,
    NormalizationError,
    Period,
    date_key,
    money_key,
    normalize_date_value,
    normalize_money_value,
    normalize_number_value,
    normalize_period_value,
    normalize_text,
    normalize_text_value,
    number_key,
    parse_date,
    parse_decimal,
    period_key,
    text_key,
)


def test_normalize_text_remove_acentos_caixa_e_espacos():
    assert normalize_text("  São   Paulo ") == "sao paulo"


def test_parse_decimal_aceita_formatos_br_e_us():
    assert parse_decimal("1.000,50") == Decimal("1000.50")
    assert parse_decimal("1000.50") == Decimal("1000.50")
    assert parse_decimal("R$ 5.000.000,00") == Decimal("5000000.00")
    assert parse_decimal(60) == Decimal("60")


def test_parse_decimal_invalido_levanta_erro():
    with pytest.raises(NormalizationError):
        parse_decimal("abc")
    with pytest.raises(NormalizationError):
        parse_decimal(True)


def test_parse_date_aceita_formatos_comuns():
    assert parse_date("2025-01-01") == date(2025, 1, 1)
    assert parse_date("01/06/2018") == date(2018, 6, 1)
    with pytest.raises(NormalizationError):
        parse_date("32/13/2025")


def test_money_converte_para_brl_com_taxa():
    assert Money(Decimal("100.00"), "USD").to_brl(Decimal("5")) == Decimal("500.00")
    assert Money(Decimal("100.00"), "BRL").to_brl(Decimal("5")) == Decimal("100.00")
    with pytest.raises(NormalizationError):
        Money(Decimal("100.00"), "USD").to_brl(Decimal("0"))


def test_period_duracao_e_ordem():
    period = Period(date(2025, 1, 1), date(2026, 1, 1))
    assert period.duration_days == 365
    with pytest.raises(NormalizationError):
        Period(date(2026, 1, 1), date(2025, 1, 1))


def test_normalizacao_por_tipo_gera_chave_comparavel():
    assert normalize_money_value({"amount": "5.000.000,00", "currency": "brl"}) == {
        "amount": "5000000.00",
        "currency": "BRL",
    }
    assert money_key({"amount": "5000000.00", "currency": "BRL"}) == Decimal("5000000.00")

    assert normalize_period_value({"start": "2025-01-01", "end": "2026-01-01"})["duration_days"] == 365
    assert period_key({"start": "2025-01-01", "end": "2026-01-01"}) == (date(2025, 1, 1), date(2026, 1, 1))

    assert normalize_date_value({"date": "01/01/2015"}) == {"date": "2015-01-01"}
    assert date_key({"date": "2015-01-01"}) == date(2015, 1, 1)

    assert normalize_number_value({"number": "60", "unit": "dias"}) == {"number": "60"}
    assert number_key({"number": "60"}) == Decimal("60")

    assert normalize_text_value({"text": "Mundial"}) == {"text": "mundial"}
    assert text_key({"text": "Mundial"}) == "mundial"


def test_normalizacao_de_texto_vazio_falha():
    with pytest.raises(NormalizationError):
        normalize_text_value({"text": "   "})
