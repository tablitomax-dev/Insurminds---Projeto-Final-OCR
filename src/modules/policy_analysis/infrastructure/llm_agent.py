"""Agentes LLM do policy_analysis (D-03, OQ-02, RF-03, RF-07, RF-09, RNF-03).

Estratégia decidida: agente multi-campo — UMA chamada de LLM por apólice
extrai todos os campos pedidos. A validação de schema acontece fora daqui
(application.extraction); este módulo garante que a resposta é estruturada
e que falhas temporárias seguem retry com backoff (EC-01). `FixtureLLM*
implementações rodam sem rede (testes e demo); `PydanticAIClient` é o
provedor real (Gemini via Pydantic AI).
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Protocol

from shared_kernel.contracts import ExtractionRequest

from ..application.errors import ClassifiedError
from ..domain.models import FieldComparison


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
    raise ClassifiedError(
        "LLM_UNAVAILABLE", f"provedor de LLM indisponível após {attempts} tentativas: {last_exc}", retriable=True
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


class MultiFieldExtractionAgent:
    """Agente multi-campo: 1 chamada de LLM por apólice (OQ-02)."""

    def __init__(self, client: LLMClient, retries: int = 3, backoff: float = 1.0):
        self._client = client
        self._retries = retries
        self._backoff = backoff
        self.usage: list[dict] = []

    def extract(self, requests: list[ExtractionRequest], run_id: str) -> list[dict]:
        prompt = build_extraction_prompt(requests)
        raw = _with_retries(lambda: self._client.complete_json(prompt), self._retries, self._backoff)
        self.usage.append({"run_id": run_id, "operation": "extract", "prompt_chars": len(prompt)})
        if isinstance(raw, dict):
            raw = raw.get("facts", raw)
        raw = _parse_structured(raw, list)
        for item in raw:
            if not isinstance(item, dict):
                raise ClassifiedError("LLM_SCHEMA_INVALID", "item de fato não é objeto", retriable=True)
        return raw


class LLMExplanationAgent:
    """Explicação por LLM; a validação da citação fica no caso de uso."""

    def __init__(self, client: LLMClient, retries: int = 3, backoff: float = 1.0):
        self._client = client
        self._retries = retries
        self._backoff = backoff
        self.usage: list[dict] = []

    def explain(self, campo: FieldComparison, run_id: str) -> dict:
        prompt = build_explanation_prompt(campo)
        raw = _with_retries(lambda: self._client.complete_json(prompt), self._retries, self._backoff)
        self.usage.append({"run_id": run_id, "operation": "explain", "prompt_chars": len(prompt)})
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
                from pydantic_ai.models.google import GeminiModel
            except ImportError:  # versões antigas do pydantic-ai
                from pydantic_ai.models.gemini import GeminiModel
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
            agent = Agent(model, result_type=dict)
        result = agent.run_sync(prompt)
        output = getattr(result, "output", None)
        if output is None:
            output = getattr(result, "data", None)
        # RNF-03: tokens/custo por execução registrados via run_id do chamador
        tokens = None
        try:
            usage = result.usage()
            tokens = getattr(usage, "total_tokens", None) or dict(usage)
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
