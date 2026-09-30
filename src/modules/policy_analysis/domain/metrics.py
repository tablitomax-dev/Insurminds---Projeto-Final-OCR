"""Modelos puros de métricas de uso do LLM (D2-P1-2, roadmap D-03).

`UsageMetrics` é **local por `run_id`** (RN-03): tokens, custo estimado e
latência por chamada de extração/explicação. Sem `ModelGateway` nesta rodada
(gatelo registrado) e sem texto de apólice em métrica/log (T-2a) — os
campos são só números, modelo e identificadores.
"""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, Field

#: Tipos de chamada instrumentada.
KIND_EXTRACT = "EXTRACT"
KIND_EXPLAIN = "EXPLAIN"


class UsageRecord(BaseModel):
    """Uma chamada de LLM medida (RF-03)."""

    run_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)  # KIND_EXTRACT | KIND_EXPLAIN
    model_name: str = Field(min_length=1)
    request_tokens: int = Field(ge=0)
    response_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    cost_usd: float | None = Field(default=None, ge=0)


class UsageSummary(BaseModel):
    """Agregado de um run (RF-03): soma por `run_id`."""

    run_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    calls: int = Field(ge=0)
    request_tokens: int = Field(ge=0)
    response_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    price_reference_date: str | None = None


class UsageMetricsCollector:
    """Coletor em memória por processo (decisão D-03 — log estruturado é o
    registro durável; o painel da UI lê o último run daqui)."""

    def __init__(self) -> None:
        self._records: dict[str, list[UsageRecord]] = {}
        self._order: list[str] = []
        self._current_run_id: str | None = None
        self._current_kind: str | None = None

    def begin_run(self, kind: str) -> str:
        """Abre um run e passa a ser o run corrente (agrega chamadas)."""
        run_id = f"run_{uuid4().hex[:12]}"
        self._records[run_id] = []
        self._order.append(run_id)
        self._current_run_id = run_id
        self._current_kind = kind
        return run_id

    def end_run(self) -> None:
        self._current_run_id = None
        self._current_kind = None

    def record(
        self,
        *,
        kind: str,
        model_name: str,
        request_tokens: int,
        response_tokens: int,
        latency_ms: int,
        cost_usd: float | None,
        run_id: str | None = None,
    ) -> UsageRecord:
        """Registra uma chamada — no run corrente quando `run_id` é omitido.

        `run_id` externo (gerado por quem chama, ex. o `ExtractionService` do
        Dev 2) é aceito e cria o run em memória — sem isso, `record` quebraria
        com `KeyError` na primeira chamada instrumentada.
        """
        target = run_id or self._current_run_id or self.begin_run(kind)
        if target not in self._records:
            self._records[target] = []
            self._order.append(target)
        record = UsageRecord(
            run_id=target,
            kind=kind,
            model_name=model_name,
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )
        self._records[target].append(record)
        return record

    def records_for(self, run_id: str) -> list[UsageRecord]:
        return list(self._records.get(run_id, []))

    def run_ids(self) -> list[str]:
        return list(self._order)

    def last_run_id(self) -> str | None:
        return self._order[-1] if self._order else None

    def summarize(
        self, run_id: str | None = None, price_reference_date: str | None = None
    ) -> UsageSummary | None:
        """Agregado do run indicado (ou do último). `None` se não há métricas."""
        target = run_id or self.last_run_id()
        if target is None:
            return None
        records = self._records.get(target, [])
        if not records:
            return None
        costs = [record.cost_usd for record in records if record.cost_usd is not None]
        return UsageSummary(
            run_id=target,
            kind=records[0].kind,
            calls=len(records),
            request_tokens=sum(record.request_tokens for record in records),
            response_tokens=sum(record.response_tokens for record in records),
            latency_ms=sum(record.latency_ms for record in records),
            cost_usd=round(sum(costs), 6) if costs else None,
            price_reference_date=price_reference_date,
        )
