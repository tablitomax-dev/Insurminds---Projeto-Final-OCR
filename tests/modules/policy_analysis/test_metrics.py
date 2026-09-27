"""Testes de métricas de uso e tabela de preços (D2-P1-2a — roadmap D-03/D-04)
e da instrumentação do adapter com anti-vazamento (D2-P1-2b/D2-P1-2c)."""

from __future__ import annotations

import logging

import pytest

from fakes.policy_analysis import make_evidence, make_fact
from modules.policy_analysis.application.ports import LlmOutputError
from modules.policy_analysis.domain.metrics import (
    KIND_EXPLAIN,
    KIND_EXTRACT,
    UsageMetricsCollector,
)
from modules.policy_analysis.infrastructure.llm_extractors import PydanticAiFieldExtractor
from modules.policy_analysis.infrastructure.pricing import (
    PRICE_REFERENCE_DATE,
    compute_cost_usd,
)
from shared_kernel.contracts import ExtractionRequest

#: Marcador de texto de apólice — nunca pode vazar em métrica, log ou erro (RF-04).
APOLICE_MARKER = "TEXTO-CONFIDENCIAL-APOLICE-XYZ"


def test_custo_estimado_usa_tabela_usd():
    # 1M de tokens de entrada a $0.10 + 1M de saída a $0.40 = $0.50.
    assert compute_cost_usd("gemini-2.0-flash", 1_000_000, 1_000_000) == 0.5
    # 500k entrada + 0 saída = $0.05.
    assert compute_cost_usd("gemini-2.0-flash", 500_000, 0) == 0.05


def test_custo_estimado_de_modelo_desconhecido_e_none():
    assert compute_cost_usd("modelo-inexistente", 1_000, 1_000) is None


def test_tabela_de_precos_registra_data_de_referencia():
    assert PRICE_REFERENCE_DATE == "2026-09-26"


def test_coletor_agrega_chamadas_por_run_id():
    collector = UsageMetricsCollector()
    run_id = collector.begin_run(KIND_EXTRACT)
    collector.record(
        kind=KIND_EXTRACT,
        model_name="gemini-2.0-flash",
        request_tokens=100,
        response_tokens=20,
        latency_ms=300,
        cost_usd=0.00001,
    )
    collector.record(
        kind=KIND_EXTRACT,
        model_name="gemini-2.0-flash",
        request_tokens=50,
        response_tokens=10,
        latency_ms=200,
        cost_usd=0.000005,
    )
    collector.end_run()

    summary = collector.summarize(run_id, price_reference_date=PRICE_REFERENCE_DATE)
    assert summary is not None
    assert summary.calls == 2
    assert summary.request_tokens == 150
    assert summary.response_tokens == 30
    assert summary.latency_ms == 500
    assert summary.cost_usd == 0.000015
    assert summary.price_reference_date == "2026-09-26"


def test_coletor_sem_metricas_devolve_none():
    collector = UsageMetricsCollector()
    assert collector.summarize() is None
    assert collector.last_run_id() is None


def test_coletor_mostra_o_ultimo_run():
    collector = UsageMetricsCollector()
    first = collector.begin_run(KIND_EXTRACT)
    collector.end_run()
    second = collector.begin_run(KIND_EXPLAIN)
    collector.record(
        kind=KIND_EXPLAIN,
        model_name="gemini-2.0-flash",
        request_tokens=10,
        response_tokens=5,
        latency_ms=100,
        cost_usd=None,
    )
    collector.end_run()
    assert collector.last_run_id() == second
    assert collector.run_ids() == [first, second]


def test_custo_none_na_tabela_nao_estoura_o_agregado():
    collector = UsageMetricsCollector()
    collector.begin_run(KIND_EXPLAIN)
    collector.record(
        kind=KIND_EXPLAIN,
        model_name="modelo-desconhecido",
        request_tokens=10,
        response_tokens=5,
        latency_ms=100,
        cost_usd=None,
    )
    summary = collector.summarize()
    assert summary is not None
    assert summary.cost_usd is None


# --- Instrumentação do adapter (D2-P1-2b) e anti-vazamento (D2-P1-2c) ---


class _FakeUsage:
    request_tokens = 1_000
    response_tokens = 500


class _FakeRun:
    def __init__(self, output: object) -> None:
        self.output = output

    def usage(self) -> _FakeUsage:
        return _FakeUsage()


class _FakeAgent:
    def __init__(self, output: object = None, error: Exception | None = None) -> None:
        self._output = output
        self._error = error

    def run_sync(self, prompt: str) -> _FakeRun:
        if self._error is not None:
            raise self._error
        return _FakeRun(self._output)


def _extractor_with(agent: _FakeAgent) -> tuple[PydanticAiFieldExtractor, UsageMetricsCollector]:
    collector = UsageMetricsCollector()
    extractor = PydanticAiFieldExtractor.__new__(PydanticAiFieldExtractor)
    extractor._model_name = "gemini-2.0-flash"
    extractor._collector = collector
    extractor._agent = agent
    return extractor, collector


def _request() -> ExtractionRequest:
    return ExtractionRequest(
        policy_id="pol_a",
        field_code="franquia",
        evidences=[
            make_evidence(
                "ev_1", "pol_a", quoted_text=f"Apolice declara {APOLICE_MARKER} como limite."
            )
        ],
        schema_version="1.0.0",
    )


def test_instrumentacao_registra_tokens_custo_e_latencia():
    fact = make_fact("pol_a", "franquia", value={"raw_text": "x"})
    extractor, collector = _extractor_with(_FakeAgent(output=fact))

    extractor.extract(_request())

    summary = collector.summarize()
    assert summary is not None
    assert summary.calls == 1
    assert summary.request_tokens == 1_000
    assert summary.response_tokens == 500
    assert summary.latency_ms >= 0
    # 1000/1M × $0.10 + 500/1M × $0.40 = $0.0003
    assert summary.cost_usd == 0.0003


def test_metricas_e_log_nao_contem_texto_de_apolice(caplog):
    """RF-04/D2-P1-2c: métricas e log estruturado são só números, modelo e IDs."""
    fact = make_fact("pol_a", "franquia", value={"raw_text": APOLICE_MARKER})
    extractor, collector = _extractor_with(_FakeAgent(output=fact))

    with caplog.at_level(logging.INFO, logger="policy_analysis.usage"):
        extractor.extract(_request())

    for record in collector.records_for(collector.last_run_id()):
        assert APOLICE_MARKER not in record.model_dump_json()
    usage_logs = [
        record for record in caplog.records if record.name == "policy_analysis.usage"
    ]
    assert usage_logs, "instrumentação deve gravar log estruturado"
    for record in usage_logs:
        assert APOLICE_MARKER not in record.getMessage()


def test_erro_do_llm_nao_vaza_texto_de_apolice():
    extractor, collector = _extractor_with(
        _FakeAgent(error=RuntimeError(f"boom: {APOLICE_MARKER}"))
    )

    with pytest.raises(LlmOutputError) as excinfo:
        extractor.extract(_request())

    assert APOLICE_MARKER not in str(excinfo.value)
    assert collector.last_run_id() is None
