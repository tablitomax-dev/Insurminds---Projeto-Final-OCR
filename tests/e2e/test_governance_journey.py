"""E2E da jornada de governança (RF-01..RF-04, feature 004).

Jornada do analista com os novos sinais: extração com falha de regra →
`Issue` ALTO; extração incerta → MÉDIO; fato sinalizado → BAIXO; falha
pós-LLM → CRÍTICO. A fila de revisão agrupa por severidade, o
`QualityReport` agrega por documento/comparação e as métricas do run ficam
disponíveis via fachada (estado vazio tratado antes do primeiro run).
"""

from __future__ import annotations

import pytest

from fakes.policy_analysis import (
    FakeEvidenceRetriever,
    FakeExplanationGenerator,
    InMemoryFactRepository,
    ScriptedLlmExtractor,
    make_evidence,
)
from modules.policy_analysis.application.ports import LlmOutputError
from modules.policy_analysis.application.quality import QualitySignalLog
from modules.policy_analysis.domain.metrics import (
    KIND_EXTRACT,
    UsageMetricsCollector,
)
from modules.policy_analysis.public_api import Severity, create_policy_analysis
from ui.logic import group_by_severity

POL_A, POL_B = "pol_acme", "pol_bravo"
FIELD_LIMIT = "limite_agregado"
FIELD_FRANQUIA = "franquia"
FIELD_NOME = "nome_segurado"

TEXT_A = "Limite Agregado: R$ 900.000,00 por período de vigência."
ANCHOR_A = "R$ 900.000,00"

OUTPUTS = {
    # Valor NEGATIVO → regra `valor_positivo` → NEEDS_REVIEW → Issue ALTO.
    (POL_A, FIELD_LIMIT): {
        "status": "FOUND",
        "value": {"amount": -900000.0, "currency": "BRL", "raw_text": ANCHOR_A},
        "anchor": ANCHOR_A,
    },
    # AMBIGUOUS → Issue MÉDIO.
    (POL_B, FIELD_FRANQUIA): {
        "status": "AMBIGUOUS",
        "value": {"raw_text": ANCHOR_A},
        "anchor": ANCHOR_A,
        "confidence": 0.4,
        "requires_human_review": True,
    },
    # FOUND sinalizado sem violação → Issue BAIXO.
    (POL_A, FIELD_FRANQUIA): {
        "status": "FOUND",
        "value": {"amount": 50000.0, "currency": "BRL", "raw_text": ANCHOR_A},
        "anchor": ANCHOR_A,
        "requires_human_review": True,
    },
    # Lado B do limite, sem sinal — alimenta a comparação.
    (POL_B, FIELD_LIMIT): {
        "status": "FOUND",
        "value": {"amount": 300000.0, "currency": "BRL", "raw_text": ANCHOR_A},
        "anchor": ANCHOR_A,
    },
}


class _ScriptedWithFailure(ScriptedLlmExtractor):
    """Scripted + falha pós-LLM em um campo designado (sinal CRÍTICO)."""

    def __init__(self, outputs: dict, failing_key: tuple[str, str]) -> None:
        super().__init__(outputs)
        self._failing_key = failing_key

    def extract(self, request):  # type: ignore[override]
        if (request.policy_id, request.field_code) == self._failing_key:
            self.requests.append(request)
            raise LlmOutputError(
                "EXTRACT: citação do LLM fora do texto da evidência citada"
                " (quantidade=1 campos=value policy_id=pol_acme field_code=nome_segurado)"
            )
        return super().extract(request)


def _stack():
    repository = InMemoryFactRepository()
    collector = UsageMetricsCollector()
    signals = QualitySignalLog()
    facade = create_policy_analysis(
        retriever=FakeEvidenceRetriever(
            evidences_by_policy={
                POL_A: [make_evidence("ev_a1", policy_id=POL_A, quoted_text=TEXT_A)],
                POL_B: [make_evidence("ev_b1", policy_id=POL_B, quoted_text=TEXT_A)],
            }
        ),
        llm_extractor=_ScriptedWithFailure(OUTPUTS, failing_key=(POL_A, FIELD_NOME)),
        repository=repository,
        explanation_generator=FakeExplanationGenerator(),
        usage_collector=collector,
        quality_signals=signals,
    )
    return facade, collector


def test_jornada_de_governancia_ponta_a_ponta():
    policy, collector = _stack()

    # Estado vazio tratado (RF-03): nenhum run, nenhuma métrica.
    assert policy.get_usage_metrics() is None

    # 1. Extrações: regras e sinais já existentes alimentam os Issues.
    assert policy.extract_field(POL_A, FIELD_LIMIT).status == "NEEDS_REVIEW"
    assert policy.extract_field(POL_B, FIELD_FRANQUIA).status == "AMBIGUOUS"
    assert policy.extract_field(POL_A, FIELD_FRANQUIA).status == "FOUND"
    with pytest.raises(LlmOutputError):
        policy.extract_field(POL_A, FIELD_NOME)

    # 2. QualityReport por documento: mapa sinal → severidade completo.
    report = policy.get_quality_report(POL_A)
    assert report.counts_by_severity == {"CRÍTICO": 1, "ALTO": 1, "MÉDIO": 0, "BAIXO": 1}
    by_field = {issue.field_code: issue.severity for issue in report.issues}
    assert by_field[FIELD_NOME] is Severity.CRITICO
    assert by_field[FIELD_LIMIT] is Severity.ALTO
    assert by_field[FIELD_FRANQUIA] is Severity.BAIXO

    # 3. Fila de revisão agrupada por severidade (RF-02): CRÍTICO → BAIXO.
    queue = policy.get_review_queue()
    groups = group_by_severity(queue, policy.list_issues(POL_A) + policy.list_issues(POL_B))
    assert [severity for severity, _ in groups] == [
        Severity.ALTO,
        Severity.MEDIO,
        Severity.BAIXO,
    ]

    # 4. Métricas do run via fachada (RF-03) — a instrumentação real do adapter
    #    é provada em test_metrics.py; aqui o agregado por run_id é o contrato.
    run_id = collector.begin_run(KIND_EXTRACT)
    collector.record(
        kind=KIND_EXTRACT,
        model_name="gemini-2.0-flash",
        request_tokens=1_000,
        response_tokens=500,
        latency_ms=300,
        cost_usd=0.0003,
    )
    collector.end_run()
    summary = policy.get_usage_metrics()
    assert summary is not None
    assert summary.run_id == run_id
    assert summary.calls == 1
    assert summary.cost_usd == 0.0003

    # 5. QualityReport por comparação agrega os dois lados (RF-01).
    policy.extract_field(POL_B, FIELD_LIMIT)
    comparison = policy.compare_policies(POL_A, POL_B)
    comparison_report = policy.get_comparison_quality_report(comparison.comparison_id)
    assert comparison_report.scope == "comparison"
    assert comparison_report.counts_by_severity["ALTO"] >= 1
