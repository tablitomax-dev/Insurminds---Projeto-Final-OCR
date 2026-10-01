"""Agentes LLM do policy_analysis (D-03, OQ-02, RF-03, RF-07, RF-09, RNF-03).

Estratégia decidida: agente multi-campo — UMA chamada de LLM por apólice
extrai todos os campos pedidos. A validação de schema acontece fora daqui
(application.extraction); este módulo garante que a resposta é estruturada
e que falhas temporárias seguem retry com backoff (EC-01). `FixtureLLM*
implementações rodam sem rede (testes e demo); `PydanticAIClient` é o
provedor real (Gemini via Pydantic AI).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Protocol

from shared_kernel.contracts import ExtractionRequest

from ..application.errors import ClassifiedError
from ..domain.metrics import KIND_EXPLAIN, KIND_EXTRACT, UsageMetricsCollector
from ..domain.models import FieldComparison
from .pricing import compute_cost_usd

# D2-P2-2: prompts versionados — ao alterar build_extraction_prompt /
# build_explanation_prompt, bumpar a versão correspondente (diff auditável +
# re-execução do golden set). O hash detecta mudança silenciosa do texto.
EXTRACTION_PROMPT_VERSION = "extract-v1"
EXPLANATION_PROMPT_VERSION = "explain-v1"


def prompt_fingerprint(prompt: str) -> str:
    """Hash estável (sha256 curto) do texto do prompt — auditoria de mudança."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


class LLMClient(Protocol):
    """Cliente mínimo de LLM: prompt em texto, resposta JSON em Python."""

    def complete_json(self, prompt: str) -> Any:
        ...


class ExtractionAgent(Protocol):
    def extract(self, requests: list[ExtractionRequest], run_id: str) -> list[dict]:
        ...


class ExplanationAgent(Protocol):
    def explain(self, campo: FieldComparison, run_id: str) -> dict:
        ...


def _with_retries(fn, attempts: int, backoff: float):
    last_exc: Exception | None = None
    for attempt in range(1, max(attempts, 1) + 1):
        try:
            return fn()
        except Exception as exc:  # falha externa do provedor (timeout/429/5xx)
            last_exc = exc
            if attempt < attempts and backoff > 0:
                time.sleep(backoff * (2 ** (attempt - 1)))
    # T-2a: só o tipo da exceção — a mensagem do provedor pode ecoar texto de
    # apólice e nunca deve vazar em métrica, log ou erro.
    raise ClassifiedError(
        "LLM_UNAVAILABLE",
        f"provedor de LLM indisponível após {attempts} tentativas ({type(last_exc).__name__})",
        retriable=True,
    )


def _parse_structured(raw: Any, expected: type) -> Any:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    if not isinstance(raw, expected):
        raise ClassifiedError(
            "LLM_SCHEMA_INVALID", f"resposta do LLM fora do schema: esperado {expected.__name__}", retriable=True
        )
    return raw


def _record_usage(
    collector: UsageMetricsCollector | None,
    client: Any,
    run_id: str,
    kind: str,
    started: float,
) -> None:
    """Métricas da chamada de LLM (features 003/004): só números/IDs (T-2a).

    Extensão aditiva sobre os agentes do Dev 2: quando um `UsageMetricsCollector`
    é injetado, cada chamada vira um `UsageRecord` (tokens, latência, custo USD).
    """
    if collector is None:
        return
    request_tokens = 0
    response_tokens = 0
    registros = getattr(client, "usage", None) or []
    if registros:
        tokens = registros[-1].get("tokens")
        if isinstance(tokens, dict):
            request_tokens = int(tokens.get("request_tokens") or tokens.get("prompt_tokens") or 0)
            response_tokens = int(
                tokens.get("response_tokens") or tokens.get("completion_tokens") or 0
            )
        elif isinstance(tokens, int):
            response_tokens = int(tokens)
    model_name = getattr(client, "_model_name", None) or "llm"
    cost_usd = compute_cost_usd(model_name, request_tokens, response_tokens)
    latency_ms = int((time.monotonic() - started) * 1000)
    collector.record(
        kind=kind,
        model_name=model_name,
        request_tokens=request_tokens,
        response_tokens=response_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        run_id=run_id,
    )
    # Log estruturado durável (004): só números, modelo e IDs — nunca texto
    # de apólice (T-2a).
    logging.getLogger("policy_analysis.usage").info(
        json.dumps(
            {
                "run_id": run_id,
                "kind": kind,
                "model_name": model_name,
                "request_tokens": request_tokens,
                "response_tokens": response_tokens,
                "latency_ms": latency_ms,
                "cost_usd": cost_usd,
            },
            sort_keys=True,
        )
    )


class MultiFieldExtractionAgent:
    """Agente multi-campo: 1 chamada de LLM por apólice (OQ-02)."""

    def __init__(
        self,
        client: LLMClient,
        retries: int = 3,
        backoff: float = 1.0,
        usage_collector: UsageMetricsCollector | None = None,
    ):
        self._client = client
        self._retries = retries
        self._backoff = backoff
        self._usage_collector = usage_collector
        self.usage: list[dict] = []

    def extract(self, requests: list[ExtractionRequest], run_id: str) -> list[dict]:
        prompt = build_extraction_prompt(requests)
        started = time.monotonic()
        raw = _with_retries(lambda: self._client.complete_json(prompt), self._retries, self._backoff)
        _record_usage(self._usage_collector, self._client, run_id, KIND_EXTRACT, started)
        self.usage.append(
            {
                "run_id": run_id,
                "operation": "extract",
                "prompt_chars": len(prompt),
                "prompt_version": EXTRACTION_PROMPT_VERSION,
                "prompt_hash": prompt_fingerprint(prompt),
            }
        )
        if isinstance(raw, dict):
            raw = raw.get("facts", raw)
        raw = _parse_structured(raw, list)
        for item in raw:
            if not isinstance(item, dict):
                raise ClassifiedError("LLM_SCHEMA_INVALID", "item de fato não é objeto", retriable=True)
        return raw


class LLMExplanationAgent:
    """Explicação por LLM; a validação da citação fica no caso de uso."""

    def __init__(
        self,
        client: LLMClient,
        retries: int = 3,
        backoff: float = 1.0,
        usage_collector: UsageMetricsCollector | None = None,
    ):
        self._client = client
        self._retries = retries
        self._backoff = backoff
        self._usage_collector = usage_collector
        self.usage: list[dict] = []

    def explain(self, campo: FieldComparison, run_id: str) -> dict:
        prompt = build_explanation_prompt(campo)
        started = time.monotonic()
        raw = _with_retries(lambda: self._client.complete_json(prompt), self._retries, self._backoff)
        _record_usage(self._usage_collector, self._client, run_id, KIND_EXPLAIN, started)
        self.usage.append(
            {
                "run_id": run_id,
                "operation": "explain",
                "prompt_chars": len(prompt),
                "prompt_version": EXPLANATION_PROMPT_VERSION,
                "prompt_hash": prompt_fingerprint(prompt),
            }
        )
        parsed = _parse_structured(raw, dict)
        return {"text": parsed.get("text"), "evidence_ids": parsed.get("evidence_ids")}


class FixtureExtractionAgent:
    """Saída de LLM pronta, por apólice (fixtures das apólices sintéticas)."""

    def __init__(self, outputs_by_policy: dict[str, list[dict]]):
        self._outputs = outputs_by_policy
        self.calls = 0

    def extract(self, requests: list[ExtractionRequest], run_id: str) -> list[dict]:
        self.calls += 1
        if not requests:
            return []
        return list(self._outputs.get(requests[0].policy_id, []))


class FixtureExplanationAgent:
    """Explicação pronta por campo; sem resposta pronta, cita a evidência dos lados."""

    def __init__(self, responses_by_field: dict[str, dict] | None = None):
        self._responses = responses_by_field or {}

    def explain(self, campo: FieldComparison, run_id: str) -> dict:
        if campo.field_code in self._responses:
            return dict(self._responses[campo.field_code])
        ids = []
        if campo.evidencias_a:
            ids.append(campo.evidencias_a[0])
        if campo.evidencias_b:
            ids.append(campo.evidencias_b[0])
        return {
            "text": f"Comparação de {campo.field_code}: {campo.resultado} (evidências {', '.join(ids)}).",
            "evidence_ids": ids,
        }


class PydanticAIClient:
    """Provedor real (Gemini) via Pydantic AI, com registro de uso (RNF-03)."""

    def __init__(self, model_name: str = "gemini-2.0-flash", api_key: str | None = None):
        self._model_name = model_name
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.usage: list[dict] = []

    def complete_json(self, prompt: str) -> Any:
        try:
            from pydantic_ai import Agent
            try:
                from pydantic_ai.models.google import GeminiModel  # type: ignore[attr-defined]
            except ImportError:  # versões antigas do pydantic-ai
                from pydantic_ai.models.gemini import GeminiModel  # type: ignore[no-redef]
        except ImportError as exc:
            raise ClassifiedError(
                "LLM_CLIENT_UNAVAILABLE", f"pydantic-ai indisponível: {exc}", retriable=False
            ) from exc

        if not self._api_key:
            raise ClassifiedError(
                "LLM_API_KEY_MISSING", "GEMINI_API_KEY não configurada", retriable=False
            )

        model = GeminiModel(self._model_name, api_key=self._api_key)
        try:
            agent = Agent(model, output_type=dict)
        except TypeError:  # versões antigas do pydantic-ai
            agent = Agent(model, result_type=dict)  # type: ignore[call-overload]
        # D2-P0-1: temperature=0 em extração/explicação (determinismo do prompt).
        run_kwargs: dict[str, Any] = {}
        try:
            from pydantic_ai.settings import ModelSettings

            run_kwargs["model_settings"] = ModelSettings(temperature=0.0)
        except Exception:  # SDK sem ModelSettings → segue sem a trava explícita
            pass
        result = agent.run_sync(prompt, **run_kwargs)
        output = getattr(result, "output", None)
        if output is None:
            output = getattr(result, "data", None)
        # RNF-03: tokens/custo por execução registrados via run_id do chamador
        tokens = None
        try:
            usage_attr = getattr(result, "usage", None)
            usage = usage_attr() if callable(usage_attr) else usage_attr
            tokens = getattr(usage, "total_tokens", None) or dict(vars(usage))
        except Exception:
            pass
        self.usage.append({"model": self._model_name, "tokens": tokens, "prompt_chars": len(prompt)})
        return output


def build_extraction_prompt(requests: list[ExtractionRequest]) -> str:
    """Prompt multi-campo: evidências + campos pedidos, saída estruturada."""
    lines = [
        "Você extrai fatos estruturados de apólices de seguro D&O.",
        "Responda SOMENTE com JSON no formato {\"facts\": [...]}, um item por campo pedido.",
        "Cada item: {\"field_code\", \"status\": FOUND|NOT_FOUND|AMBIGUOUS|NEEDS_REVIEW,",
        "\"value\", \"confidence\", \"evidence_ids\", \"requires_human_review\"}.",
        "Use apenas evidence_ids das evidências fornecidas; nunca invente IDs.",
        "",
    ]
    for req in requests:
        lines.append(f"## Campo: {req.field_code} (schema_version={req.schema_version})")
        if not req.evidences:
            lines.append("(sem evidências recuperadas)")
        for ev in req.evidences:
            lines.append(
                f"- [{ev.evidence_id}] pág. {ev.page_number}"
                f"{f' seção {ev.section_name}' if ev.section_name else ''}: \"{ev.quoted_text}\""
            )
        lines.append("")
    return "\n".join(lines)


def build_explanation_prompt(campo: FieldComparison) -> str:
    """Prompt de explicação: diferença + evidências dos dois lados."""
    return "\n".join(
        [
            "Explique a diferença entre duas apólices para um analista de seguro.",
            "Responda SOMENTE com JSON {\"text\": ..., \"evidence_ids\": [...]}.",
            "Toda afirmação deve citar evidence_ids fornecidos, dos dois lados quando houver.",
            f"Campo: {campo.field_code} — resultado: {campo.resultado}",
            f"Lado A: valor={campo.valor_a} evidências={list(campo.evidencias_a)}",
            f"Lado B: valor={campo.valor_b} evidências={list(campo.evidencias_b)}",
        ]
    )
