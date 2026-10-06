"""Testes da formatação do painel de métricas (D2-P1-2e, RF-03/RF-04)."""

from __future__ import annotations

from modules.policy_analysis.public_api import UsageSummary
from ui.logic import format_usage_summary


def _summary(cost_usd: float | None = 0.0003) -> UsageSummary:
    return UsageSummary(
        run_id="run_abc",
        kind="EXTRACT",
        calls=2,
        request_tokens=1500,
        response_tokens=400,
        latency_ms=800,
        cost_usd=cost_usd,
        price_reference_date="2026-09-26",
    )


def test_sem_metricas_devolve_none():
    assert format_usage_summary(None) is None


def test_formata_valores_para_o_painel():
    formatted = format_usage_summary(_summary())

    assert formatted is not None
    assert formatted["ID da execução"] == "run_abc"
    assert formatted["chamadas de LLM"] == "2"
    assert formatted["tokens de entrada"] == "1500"
    assert formatted["tokens de saída"] == "400"
    assert formatted["latência total"] == "800 ms"
    assert formatted["custo estimado"] == "US$ 0.000300"
    assert formatted["tabela de preços (ref.)"] == "2026-09-26"


def test_custo_desconhecido_e_explicito_no_painel():
    formatted = format_usage_summary(_summary(cost_usd=None))

    assert formatted is not None
    assert "n/d" in formatted["custo estimado"]


def test_formatacao_nao_contem_texto_de_apolice():
    """RF-04: o painel só mostra números, IDs e datas (T-2a)."""
    formatted = format_usage_summary(_summary())
    assert formatted is not None
    for value in formatted.values():
        assert "apolice" not in value.lower()
