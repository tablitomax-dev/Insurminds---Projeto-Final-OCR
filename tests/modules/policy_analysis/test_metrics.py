"""Testes de métricas de uso e tabela de preços (D2-P1-2a — roadmap D-03/D-04)
e da instrumentação dos agentes LLM com anti-vazamento (D2-P1-2b/D2-P1-2c)."""

from __future__ import annotations

import pytest

from fakes.policy_analysis import make_evidence
from modules.policy_analysis.application.errors import ClassifiedError
from modules.policy_analysis.domain.metrics import (
    KIND_EXPLAIN,
    KIND_EXTRACT,
    UsageMetricsCollector,
)
from modules.policy_analysis.domain.models import FieldComparison
from modules.policy_analysis.infrastructure.llm_agent import (
    LLMExplanationAgent,
    MultiFieldExtractionAgent,
)
from modules.policy_analysis.infrastructure.pricing import (
    PRICE_REFERENCE_DATE,
    compute_cost_usd,
)
from shared_kernel.contracts import ExtractionRequest

#: Marcador de texto de apólice — nunca pode vazar em métrica ou erro (RF-04).
APOLICE_MARKER = "TEXTO-CONFIDENCIAL-APOLICE-XYZ"


def test_custo_estimado_usa_tabela_usd():
    # 1M de tokens de entrada a $0.10 + 1M de saída a $0.40 = $0.50.
    assert compute_cost_usd("gemini-2.0-flash", 1_000_000, 1_000_000) == 0.5
    # 500k entrada + 0 saída = $0.05.
    assert compute_cost_usd("gemini-2.0-flash", 500_000, 0) == 0.05


def test_custo_estimado_de_modelo_desconhecido_e_none():
    assert compute_cost_usd("modelo-inexistente", 1_000, 1_000) is None


def test_custo_estimado_usa_tabela_do_mimo_openrouter():
    # 1M de tokens de entrada a $0.43 + 1M de saída a $0.87 = $1.30.
    assert compute_cost_usd("xiaomi/mimo-v2.6-pro", 1_000_000, 1_000_000) == 1.3
    # 500k entrada + 100k saída = $0.215 + $0.087 = $0.302.
    assert compute_cost_usd("xiaomi/mimo-v2.6-pro", 500_000, 100_000) == 0.302


def test_tabela_de_precos_registra_data_de_referencia():
    assert PRICE_REFERENCE_DATE == "2026-10-04"


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
    assert summary.price_reference_date == PRICE_REFERENCE_DATE


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


# --- Instrumentação dos agentes (D2-P1-2b) e anti-vazamento (D2-P1-2c) ---


class StubLlmClient:
    """Cliente LLM fake: resposta pronta + uso no formato do provedor real.

    `usage[-1]["tokens"]` é o registro lido por `_record_usage` nos agentes.
    """

    def __init__(
        self,
        response=None,
        *,
        error: Exception | None = None,
        tokens: dict | None = None,
        model_name: str = "gemini-2.0-flash",
    ) -> None:
        self._model_name = model_name
        self.response = response
        self.error = error
        self.tokens = (
            tokens if tokens is not None else {"request_tokens": 1_000, "response_tokens": 500}
        )
        self.usage: list[dict] = []
        self.calls = 0

    def complete_json(self, prompt: str):
        self.calls += 1
        if self.error is not None:
            raise self.error
        self.usage.append(
            {"model": self._model_name, "tokens": self.tokens, "prompt_chars": len(prompt)}
        )
        return self.response


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


def _campo() -> FieldComparison:
    return FieldComparison(
        field_code="franquia",
        resultado="MAIOR",
        valor_a={"amount": "1000.00", "currency": "BRL"},
        valor_b={"amount": "500.00", "currency": "BRL"},
        direcao="A",
        evidencias_a=("ev_1",),
        evidencias_b=("ev_2",),
    )


def test_extracao_registra_usage_record_com_tokens_custo_e_latencia():
    collector = UsageMetricsCollector()
    run_id = collector.begin_run(KIND_EXTRACT)
    agent = MultiFieldExtractionAgent(
        StubLlmClient(
            response=[
                {
                    "field_code": "franquia",
                    "status": "FOUND",
                    "value": {"amount": "1000.00", "currency": "BRL"},
                    "confidence": 0.9,
                    "evidence_ids": ["ev_1"],
                    "requires_human_review": False,
                }
            ]
        ),
        usage_collector=collector,
    )

    agent.extract([_request()], run_id)

    records = collector.records_for(run_id)
    assert len(records) == 1
    record = records[0]
    assert record.run_id == run_id
    assert record.kind == KIND_EXTRACT
    assert record.model_name == "gemini-2.0-flash"
    assert record.request_tokens == 1_000
    assert record.response_tokens == 500
    assert record.latency_ms >= 0
    # 1000/1M × $0.10 + 500/1M × $0.40 = $0.0003
    assert record.cost_usd == 0.0003


def test_explicacao_registra_usage_record():
    collector = UsageMetricsCollector()
    run_id = collector.begin_run(KIND_EXPLAIN)
    agent = LLMExplanationAgent(
        StubLlmClient(response={"text": "A apólice A tem franquia maior.", "evidence_ids": ["ev_1"]}),
        usage_collector=collector,
    )

    agent.explain(_campo(), run_id)

    records = collector.records_for(run_id)
    assert len(records) == 1
    assert records[0].kind == KIND_EXPLAIN
    assert records[0].run_id == run_id
    assert records[0].request_tokens == 1_000
    assert records[0].response_tokens == 500
    assert records[0].cost_usd == 0.0003


def test_summarize_agrega_chamadas_por_run_id():
    collector = UsageMetricsCollector()
    run_id = collector.begin_run(KIND_EXTRACT)
    agent = MultiFieldExtractionAgent(StubLlmClient(response=[]), usage_collector=collector)

    agent.extract([], run_id)
    agent.extract([], run_id)

    summary = collector.summarize(run_id, price_reference_date=PRICE_REFERENCE_DATE)
    assert summary is not None
    assert summary.run_id == run_id
    assert summary.kind == KIND_EXTRACT
    assert summary.calls == 2
    assert summary.request_tokens == 2_000
    assert summary.response_tokens == 1_000
    assert summary.latency_ms >= 0
    assert summary.cost_usd == 0.0006
    assert summary.price_reference_date == PRICE_REFERENCE_DATE


def test_metricas_nao_contem_texto_de_apolice():
    """RF-04/D2-P1-2c: métricas são só números, modelo e IDs (T-2a)."""
    collector = UsageMetricsCollector()
    run_id = collector.begin_run(KIND_EXTRACT)
    agent = MultiFieldExtractionAgent(StubLlmClient(response=[]), usage_collector=collector)

    agent.extract([_request()], run_id)

    records = collector.records_for(run_id)
    assert records, "instrumentação deve gravar UsageRecord"
    for record in records:
        assert APOLICE_MARKER not in record.model_dump_json()
    assert APOLICE_MARKER not in collector.summarize(run_id).model_dump_json()


def test_erro_do_llm_nao_vaza_texto_de_apolice():
    collector = UsageMetricsCollector()
    agent = MultiFieldExtractionAgent(
        StubLlmClient(error=RuntimeError(f"boom: {APOLICE_MARKER}")),
        retries=1,
        backoff=0,
        usage_collector=collector,
    )

    with pytest.raises(ClassifiedError) as excinfo:
        agent.extract([_request()], "run_falho")

    assert APOLICE_MARKER not in str(excinfo.value)
    assert collector.last_run_id() is None
