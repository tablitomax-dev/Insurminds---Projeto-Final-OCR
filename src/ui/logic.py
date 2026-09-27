"""Lógica pura dos componentes de UI (D2-P1-1d/D2-P1-2e).

Sem `streamlit`: funções determinísticas e testáveis que os componentes
apenas apresentam. Consome tipos re-exportados pela fachada pública
(F-15 — nada de `domain`/`infrastructure` alheio).
"""

from __future__ import annotations

from modules.policy_analysis.public_api import (
    SEVERITY_ORDER,
    ExtractedFact,
    Issue,
    Severity,
    UsageSummary,
)


def group_by_severity(
    facts: list[ExtractedFact], issues: list[Issue]
) -> list[tuple[Severity, list[ExtractedFact]]]:
    """Agrupa a fila de revisão por severidade do `Issue` derivado (RF-02).

    Ordem `CRÍTICO` → `BAIXO`; fato sem `Issue` associado cai em `BAIXO`
    (sem sinal de qualidade). Grupos vazios não aparecem.
    """
    severity_by_key: dict[tuple[str, str], Severity] = {}
    for issue in issues:
        key = (issue.policy_id, issue.field_code)
        current = severity_by_key.get(key)
        if current is None or SEVERITY_ORDER.index(issue.severity) < SEVERITY_ORDER.index(
            current
        ):
            severity_by_key[key] = issue.severity
    groups: list[tuple[Severity, list[ExtractedFact]]] = []
    for severity in SEVERITY_ORDER:
        bucket = [
            fact
            for fact in facts
            if severity_by_key.get((fact.policy_id, fact.field_code), Severity.BAIXO)
            is severity
        ]
        if bucket:
            groups.append((severity, bucket))
    return groups


def format_usage_summary(summary: UsageSummary | None) -> dict[str, str] | None:
    """Formata o resumo de métricas para o painel — números, IDs e datas (T-2a)."""
    if summary is None:
        return None
    cost = (
        "n/d (modelo fora da tabela de preços)"
        if summary.cost_usd is None
        else f"US$ {summary.cost_usd:.6f}"
    )
    return {
        "run_id": summary.run_id,
        "chamadas de LLM": str(summary.calls),
        "tokens de entrada": str(summary.request_tokens),
        "tokens de saída": str(summary.response_tokens),
        "latência total": f"{summary.latency_ms} ms",
        "custo estimado": cost,
        "tabela de preços (ref.)": summary.price_reference_date or "n/d",
    }
