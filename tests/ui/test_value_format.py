"""Formatação dos valores A/B do quadro de comparação para o analista."""

from __future__ import annotations

from ui.logic import format_value


def test_dinheiro_brl_no_padrao_com_moeda():
    assert format_value({"amount": "2000000.00", "currency": "BRL"}) == "R$ 2.000.000,00"


def test_dinheiro_com_casas_decimais():
    assert format_value({"amount": "25000.00", "currency": "BRL"}) == "R$ 25.000,00"


def test_dinheiro_usd_com_moeda_identificada():
    assert format_value({"amount": "1000000.00", "currency": "USD"}) == "US$ 1.000.000,00"


def test_data_em_dd_mm_aaaa():
    assert format_value({"date": "2020-01-01"}) == "01-01-2020"


def test_periodo_mostra_as_datas_sem_duracao():
    texto = format_value({"start": "2025-01-01", "end": "2025-12-31", "duration_days": 364})
    assert texto == "01-01-2025 a 31-12-2025"
    assert "364" not in texto


def test_prazo_so_o_numero_com_dias():
    assert format_value({"number": "30"}, unit="dias") == "30 dias"


def test_percentual():
    assert format_value({"number": "5"}, unit="%") == "5%"


def test_texto_puro():
    assert format_value({"text": "mundo"}) == "mundo"


def test_ausente_vira_traco():
    assert format_value(None) == "—"


def test_nenhum_simbolo_de_json_nas_saidas():
    amostras = [
        {"amount": "25000.00", "currency": "BRL"},
        {"date": "2020-01-01"},
        {"start": "2025-01-01", "end": "2025-12-31"},
        {"number": "30"},
        {"text": "fraude, dolo e atos ilícitos"},
    ]
    for valor in amostras:
        texto = format_value(valor)
        assert "{" not in texto
        assert '"' not in texto
        assert "'" not in texto
