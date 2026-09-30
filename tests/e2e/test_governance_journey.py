"""E2E da jornada de governança (RF-01..RF-04) sobre a arquitetura unificada.

Mapa sinal → severidade da arquitetura nova (`application/quality.py`):
- falha de extração (`ClassifiedError`) → `CRÍTICO` (reason = código do erro);
- `NEEDS_REVIEW`/`AMBIGUOUS` sem violação → `MÉDIO`;
- `requires_human_review` sem violação → `BAIXO`.
A fila de revisão agrupa por severidade (`ui.logic`), o `QualityReport` agrega
por documento/comparação e as métricas do run ficam disponíveis via fachada
(estado vazio tratado antes do primeiro run).
"""

from __future__ import annotations

import pytest

from modules.policy_analysis.domain.metrics import KIND_EXPLAIN, KIND_EXTRACT
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import (
    FixtureExplanationAgent,
    FixtureExtractionAgent,
)
from modules.policy_analysis.public_api import (
    ClassifiedError,
    QualitySignalLog,
    Severity,
    UsageMetricsCollector,
    create_policy_analysis,
)
from shared_kernel.contracts import EvidenceRef
from ui.logic import group_by_severity

POL_A, POL_B = "pol_acme", "pol_bravo"
FIELD_LIMIT = "limite_agregado"
FIELD_FRANQUIA = "franquia"
FIELD_PRAZO = "prazo_notificacao_sinistro"

TEXT_A = "Limite Agregado: R$ 900.000,00 por período de vigência."
TEXT_B = "Limite Agregado: R$ 300.000,00 por período de vigência."

#: Saídas roteirizadas do LLM por apólice (formato `FixtureExtractionAgent`).
OUTPUTS = {
    POL_A: [
        # Ilegível/incerto → NEEDS_REVIEW → Issue MÉDIO.
        {
            "field_code": FIELD_LIMIT,
            "status": "NEEDS_REVIEW",
            "value": {"raw_text": "R$ ???"},
            "confidence": 0.3,
            "evidence_ids": ["ev_a1"],
            "requires_human_review": True,
        },
        # FOUND sinalizado pelo LLM sem violação → Issue BAIXO.
        {
            "field_code": FIELD_FRANQUIA,
            "status": "FOUND",
            "value": {"amount": 50_000.0, "currency": "BRL"},
            "confidence": 0.9,
            "evidence_ids": ["ev_a2"],
            "requires_human_review": True,
        },
    ],
    POL_B: [
        # Trechos conflitantes → AMBIGUOUS → Issue MÉDIO.
        {
            "field_code": FIELD_FRANQUIA,
            "status": "AMBIGUOUS",
            "value": {"raw_text": "trechos conflitantes"},
            "confidence": 0.4,
            "evidence_ids": ["ev_b1"],
            "requires_human_review": True,
        },
        # Lado B do limite, sem sinal — alimenta a comparação.
        {
            "field_code": FIELD_LIMIT,
            "status": "FOUND",
            "value": {"amount": 300_000.0, "currency": "BRL"},
            "confidence": 0.9,
            "evidence_ids": ["ev_b1"],
            "requires_human_review": False,
        },
    ],
}


def _evidence(evidence_id: str, policy_id: str, quoted_text: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        policy_id=policy_id,
        document_id=f"doc_{policy_id}",
        page_number=1,
        quoted_text=quoted_text,
        source_type="NATIVE_TEXT",
    )


class _GovernedExtractionAgent(FixtureExtractionAgent):
    """`FixtureExtractionAgent` + métricas por chamada e falha roteirizada.

    O `UsageMetricsCollector` é injetado no agente (mesma costura de
    `MultiFieldExtractionAgent(usage_collector=...)`): cada chamada vira um
    `UsageRecord` no run corrente do coletor.
    """

    def __init__(self, outputs_by_policy, *, usage_collector, failing_key=None):
        super().__init__(outputs_by_policy)
        self._collector = usage_collector
        self._failing_key = failing_key

    def extract(self, requests, run_id):
        keys = {(request.policy_id, request.field_code) for request in requests}
        if self._failing_key is not None and self._failing_key in keys:
            policy_id, field_code = self._failing_key
            raise ClassifiedError(
                "LLM_SCHEMA_INVALID",
                f"saída do LLM fora do contrato em {field_code} policy_id={policy_id}",
                retriable=True,
            )
        self._collector.record(
            kind=KIND_EXTRACT,
            model_name="gemini-2.0-flash",
            request_tokens=1_000,
            response_tokens=500,
            latency_ms=120,
            cost_usd=0.0003,
        )
        return super().extract(requests, run_id)


class _GovernedExplanationAgent(FixtureExplanationAgent):
    """`FixtureExplanationAgent` + métricas por chamada (coletor injetado)."""

    def __init__(self, responses_by_field=None, *, usage_collector):
        super().__init__(responses_by_field)
        self._collector = usage_collector

    def explain(self, campo, run_id):
        self._collector.record(
            kind=KIND_EXPLAIN,
            model_name="gemini-2.0-flash",
            request_tokens=800,
            response_tokens=200,
            latency_ms=90,
            cost_usd=0.0002,
        )
        return super().explain(campo, run_id)


def _stack(tmp_path):
    collector = UsageMetricsCollector()
    signals = QualitySignalLog()
    facade = create_policy_analysis(
        MockEvidenceSource(
            {
                POL_A: [_evidence("ev_a1", POL_A, TEXT_A), _evidence("ev_a2", POL_A, TEXT_A)],
                POL_B: [_evidence("ev_b1", POL_B, TEXT_B)],
            }
        ),
        _GovernedExtractionAgent(
            OUTPUTS, usage_collector=collector, failing_key=(POL_A, FIELD_PRAZO)
        ),
        _GovernedExplanationAgent(usage_collector=collector),
        db_path=":memory:",
        output_dir=str(tmp_path),
        usage_collector=collector,
        quality_signals=signals,
    )
    return facade, collector, signals


def test_jornada_de_governancia_ponta_a_ponta(tmp_path):
    policy, collector, signals = _stack(tmp_path)

    # Estado vazio tratado (RF-03): nenhum run, nenhuma métrica.
    assert policy.get_usage_metrics() is None

    # 1. Extrações: os sinais que o pipeline já produz alimentam os Issues.
    extract_run_id = collector.begin_run(KIND_EXTRACT)
    assert policy.extract_field(POL_A, FIELD_LIMIT).status == "NEEDS_REVIEW"
    assert policy.extract_field(POL_B, FIELD_FRANQUIA).status == "AMBIGUOUS"
    assert policy.extract_field(POL_A, FIELD_FRANQUIA).status == "FOUND"
    collector.end_run()

    # 2. Falha de extração: `ClassifiedError` propaga e vira sinal CRÍTICO
    #    com o código sanitizado (nunca texto de apólice).
    with pytest.raises(ClassifiedError) as excinfo:
        policy.extract_field(POL_A, FIELD_PRAZO)
    assert excinfo.value.code == "LLM_SCHEMA_INVALID"
    assert signals.failures(POL_A) == [(POL_A, FIELD_PRAZO, "LLM_SCHEMA_INVALID")]

    # 3. QualityReport por documento: mapa sinal → severidade novo.
    report = policy.get_quality_report(POL_A)
    assert report.scope == "document"
    assert report.scope_id == POL_A
    assert report.counts_by_severity == {"CRÍTICO": 1, "ALTO": 0, "MÉDIO": 1, "BAIXO": 1}
    by_field = {issue.field_code: issue.severity for issue in report.issues}
    assert by_field[FIELD_PRAZO] is Severity.CRITICO
    assert by_field[FIELD_LIMIT] is Severity.MEDIO
    assert by_field[FIELD_FRANQUIA] is Severity.BAIXO

    report_b = policy.get_quality_report(POL_B)
    assert report_b.counts_by_severity == {"CRÍTICO": 0, "ALTO": 0, "MÉDIO": 1, "BAIXO": 0}

    # 4. Fila de revisão agrupada por severidade (RF-02): CRÍTICO → BAIXO.
    #    O campo com falha não gera fato (a extração falhou), logo não entra
    #    no grupo CRÍTICO — que fica só no Issue.
    queue = policy.list_review_queue()
    assert all(item.revisao_status == "PENDENTE" for item in queue)
    groups = group_by_severity(
        [item.fact for item in queue],
        policy.list_issues(POL_A) + policy.list_issues(POL_B),
    )
    assert [severity for severity, _ in groups] == [Severity.MEDIO, Severity.BAIXO]
    assert {(fact.policy_id, fact.field_code) for fact in groups[0][1]} == {
        (POL_A, FIELD_LIMIT),
        (POL_B, FIELD_FRANQUIA),
    }
    assert [(fact.policy_id, fact.field_code) for fact in groups[1][1]] == [
        (POL_A, FIELD_FRANQUIA)
    ]

    # 5. Métricas por run_id via fachada (RF-03): o coletor injetado nos
    #    agentes agrega as chamadas do run corrente.
    summary = policy.get_usage_metrics(extract_run_id)
    assert summary is not None
    assert summary.run_id == extract_run_id
    assert summary.kind == KIND_EXTRACT
    assert summary.calls == 3
    assert summary.request_tokens == 3_000
    assert summary.response_tokens == 1_500
    assert summary.latency_ms > 0
    assert summary.cost_usd == 0.0009
    assert summary.price_reference_date is not None

    # 6. QualityReport por comparação agrega os dois lados (RF-01).
    policy.extract_field(POL_B, FIELD_LIMIT)
    comparison = policy.compare_policies(POL_A, POL_B)
    comparison_report = policy.get_comparison_quality_report(comparison.comparison_id)
    assert comparison_report.scope == "comparison"
    assert comparison_report.scope_id == comparison.comparison_id
    assert comparison_report.counts_by_severity == {"CRÍTICO": 1, "ALTO": 0, "MÉDIO": 2, "BAIXO": 1}

    # 7. Explicação instrumentada em run próprio: métricas separadas por run_id.
    explain_run_id = collector.begin_run(KIND_EXPLAIN)
    explanation = policy.explain_difference(comparison.comparison_id, FIELD_FRANQUIA)
    collector.end_run()
    assert explanation.evidence_ids

    explain_summary = policy.get_usage_metrics(explain_run_id)
    assert explain_summary is not None
    assert explain_summary.kind == KIND_EXPLAIN
    assert explain_summary.calls == 1
    assert policy.get_usage_metrics(extract_run_id).calls == 3  # run intacto
    assert policy.get_usage_metrics().run_id == explain_run_id  # último run
