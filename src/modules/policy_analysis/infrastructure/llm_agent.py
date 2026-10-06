"""Agentes LLM do policy_analysis (D-03, OQ-02, RF-03, RF-07, RF-09, RNF-03).

Estratégia decidida: agente multi-campo — UMA chamada de LLM por apólice
extrai todos os campos pedidos. A validação de schema acontece fora daqui
(application.extraction); este módulo garante que a resposta é estruturada
e que falhas temporárias seguem retry com backoff (EC-01). `FixtureLLM*
implementações rodam sem rede (testes e demo); `PydanticAIClient` é o
provedor real (Gemini via Pydantic AI, ou OpenRouter para modelos
namespaced como `xiaomi/mimo-v2.6-pro` — rota por `/` no id do modelo).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Protocol

from shared_kernel.contracts import EvidenceRef, ExtractionRequest

from ..application.errors import ClassifiedError
from ..domain.metrics import (
    KIND_EXPLAIN,
    KIND_EXTRA,
    KIND_EXTRACT,
    KIND_IDENTIFY,
    KIND_QUESTION,
    KIND_REVIEW,
    UsageMetricsCollector,
)
from ..domain.models import FieldComparison
from .pricing import compute_cost_usd

# D2-P2-2: prompts versionados — ao alterar build_extraction_prompt /
# build_explanation_prompt, bumpar a versão correspondente (diff auditável +
# re-execução do golden set). O hash detecta mudança silenciosa do texto.
EXTRACTION_PROMPT_VERSION = "extract-v1"
EXPLANATION_PROMPT_VERSION = "explain-v1"
INSURER_PROMPT_VERSION = "insurer-v2"
QUESTION_PROMPT_VERSION = "question-v1"
REVIEW_PROMPT_VERSION = "review-v1"
EXTRA_FINDINGS_PROMPT_VERSION = "extras-v1"

#: Teto de espera da resposta do provedor LLM (validação real 2026-10-06).
#: Sem teto, conexão presa no provedor bloqueia o fluxo para sempre.
LLM_TIMEOUT_SECONDS = 300.0


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


def _run_agent_blocking(agent: Any, prompt: str, run_kwargs: dict, timeout: float | None = None) -> Any:
    """Executa `agent.run_sync` numa thread própria (loop asyncio novo).

    Sob o Streamlit 1.65 (servidor uvicorn/asyncio) o script roda dentro de um
    loop ativo e o `run_sync` estoura `RuntimeError: This event loop is already
    running` — a thread nova não tem loop e funciona em qualquer contexto.

    `timeout` (validação real 2026-10-06): teto de espera da resposta. Sem ele,
    uma conexão presa no provedor bloqueia o fluxo para sempre — o `join` com
    teto degrada para `LLM_TIMEOUT` reexecutável (EC-04).
    """
    import threading

    box: dict[str, Any] = {}

    def _runner() -> None:
        try:
            box["result"] = agent.run_sync(prompt, **run_kwargs)
        except BaseException as exc:  # noqa: BLE001 — repassado ao chamador
            box["error"] = exc

    worker = threading.Thread(target=_runner, name="llm-run-sync", daemon=True)
    worker.start()
    worker.join(timeout if timeout is not None else None)
    if worker.is_alive():
        raise ClassifiedError(
            "LLM_TIMEOUT",
            f"provedor LLM não respondeu em {timeout:.0f}s",
            retriable=True,
        )
    if "error" in box:
        raise box["error"]
    return box["result"]


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


def _clean_optional_str(value: Any) -> str | None:
    """String limpa ou None — `null`/vazio do LLM vira None (nunca inventa)."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() in {"null", "none", "n/a", "na"}:
        return None
    return text


class InsurerNameAgent:
    """Identifica a seguradora (nome + ano) nas páginas iniciais da apólice."""

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

    def identify(self, policy_id: str, page_texts: list[str], run_id: str) -> dict:
        prompt = build_insurer_prompt(page_texts)
        started = time.monotonic()
        raw = _with_retries(lambda: self._client.complete_json(prompt), self._retries, self._backoff)
        _record_usage(self._usage_collector, self._client, run_id, KIND_IDENTIFY, started)
        self.usage.append(
            {
                "run_id": run_id,
                "operation": "identify_insurer",
                "prompt_chars": len(prompt),
                "prompt_version": INSURER_PROMPT_VERSION,
                "prompt_hash": prompt_fingerprint(prompt),
            }
        )
        parsed = _parse_structured(raw, dict)
        return {
            "name": _clean_optional_str(parsed.get("name")),
            "year": _clean_optional_str(parsed.get("year")),
        }


class LLMQuestionAgent:
    """Responde ao analista citando evidências (RAG: busca + geração)."""

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

    def answer(self, question: str, evidences: list[EvidenceRef], run_id: str) -> dict:
        prompt = build_question_prompt(question, evidences)
        started = time.monotonic()
        raw = _with_retries(lambda: self._client.complete_json(prompt), self._retries, self._backoff)
        _record_usage(self._usage_collector, self._client, run_id, KIND_QUESTION, started)
        self.usage.append(
            {
                "run_id": run_id,
                "operation": "question",
                "prompt_chars": len(prompt),
                "prompt_version": QUESTION_PROMPT_VERSION,
                "prompt_hash": prompt_fingerprint(prompt),
            }
        )
        parsed = _parse_structured(raw, dict)
        return {"text": parsed.get("text"), "evidence_ids": parsed.get("evidence_ids") or []}


class LLMReviewAgent:
    """Interpreta a indicação de divergências e devolve correções estruturadas."""

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

    def corrections(self, message: str, facts: list[dict], run_id: str) -> list[dict]:
        prompt = build_review_prompt(message, facts)
        started = time.monotonic()
        raw = _with_retries(lambda: self._client.complete_json(prompt), self._retries, self._backoff)
        _record_usage(self._usage_collector, self._client, run_id, KIND_REVIEW, started)
        self.usage.append(
            {
                "run_id": run_id,
                "operation": "review",
                "prompt_chars": len(prompt),
                "prompt_version": REVIEW_PROMPT_VERSION,
                "prompt_hash": prompt_fingerprint(prompt),
            }
        )
        parsed = _parse_structured(raw, dict)
        raw_list = parsed.get("corrections", [])
        if isinstance(raw_list, dict):
            raw_list = [raw_list]
        if not isinstance(raw_list, list):
            raise ClassifiedError("LLM_SCHEMA_INVALID", "corrections não é lista", retriable=True)
        for item in raw_list:
            if not isinstance(item, dict):
                raise ClassifiedError("LLM_SCHEMA_INVALID", "correção não é objeto", retriable=True)
        return raw_list


def validate_extra_findings(findings: Any, known_ids: set[str]) -> list[dict]:
    """Valida achados extras: só `evidence_ids` fornecidos, nunca inventados (RN-02).

    Achado sem `label`/`value` ou com `evidence_ids` vazio, malformado ou fora
    do conjunto fornecido é descartado — o LLM não cria rastro de evidência.
    """
    valid: list[dict] = []
    for item in findings or []:
        if not isinstance(item, dict):
            continue
        label = _clean_optional_str(item.get("label"))
        value = item.get("value")
        if label is None or value is None:
            continue
        evidence_ids = item.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            continue
        if not all(isinstance(evidence_id, str) for evidence_id in evidence_ids):
            continue
        if not set(evidence_ids) <= known_ids:
            continue
        valid.append(
            {
                "label": label,
                "value": value,
                "detail": _clean_optional_str(item.get("detail")),
                "evidence_ids": list(dict.fromkeys(evidence_ids)),
            }
        )
    return valid


class LLMExtraFindingsAgent:
    """Achados relevantes fora do catálogo fechado (SUSEP, sublimites, prazos...)."""

    def __init__(
        self,
        client: LLMClient,
        usage_collector: UsageMetricsCollector | None = None,
        retries: int = 2,
        backoff: float = 0.5,
    ):
        self._client = client
        self._usage_collector = usage_collector
        self._retries = retries
        self._backoff = backoff
        self.usage: list[dict] = []

    def extract(self, policy_id: str, evidences: list[EvidenceRef], run_id: str) -> list[dict]:
        prompt = build_extra_findings_prompt(evidences)
        started = time.monotonic()
        raw = _with_retries(lambda: self._client.complete_json(prompt), self._retries, self._backoff)
        _record_usage(self._usage_collector, self._client, run_id, KIND_EXTRA, started)
        self.usage.append(
            {
                "run_id": run_id,
                "operation": "extra_findings",
                "prompt_chars": len(prompt),
                "prompt_version": EXTRA_FINDINGS_PROMPT_VERSION,
                "prompt_hash": prompt_fingerprint(prompt),
            }
        )
        parsed = _parse_structured(raw, dict)
        findings = parsed.get("findings", [])
        if isinstance(findings, dict):
            findings = [findings]
        if not isinstance(findings, list):
            raise ClassifiedError("LLM_SCHEMA_INVALID", "findings não é lista", retriable=True)
        for item in findings:
            if not isinstance(item, dict):
                raise ClassifiedError("LLM_SCHEMA_INVALID", "achado não é objeto", retriable=True)
        # RN-02: id de evidência inventado nunca vira achado.
        return validate_extra_findings(findings, {ev.evidence_id for ev in evidences})


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


class FixtureInsurerNameAgent:
    """Seguradora pronta por apólice (fixtures das apólices sintéticas)."""

    def __init__(self, info_by_policy: dict[str, dict]):
        self._info = info_by_policy

    def identify(self, policy_id: str, page_texts: list[str], run_id: str) -> dict:
        info = self._info.get(policy_id) or {}
        return {"name": info.get("name"), "year": info.get("year")}


class FixtureExtraFindingsAgent:
    """Achados extras prontos por apólice (fixtures/demo sem custo de LLM)."""

    def __init__(self, findings_by_policy: dict[str, list[dict]]):
        self._by_policy = findings_by_policy

    def extract(self, policy_id: str, evidences: list[EvidenceRef], run_id: str) -> list[dict]:
        return self._by_policy.get(policy_id, [])


def _build_gemini_model(model_name: str, api_key: str) -> Any:
    """Monta o modelo Gemini conforme a API do pydantic-ai instalado.

    pydantic-ai >= 2 expõe `GoogleModel` + `GoogleProvider`; nas versões antigas,
    `GeminiModel(model, api_key=...)` (em `models.google` ou `models.gemini`).
    """
    try:
        from pydantic_ai.models.google import GoogleModel  # type: ignore[attr-defined]
        from pydantic_ai.providers.google import GoogleProvider

        return GoogleModel(model_name, provider=GoogleProvider(api_key=api_key))
    except ImportError:
        pass
    try:
        from pydantic_ai.models.google import GeminiModel  # type: ignore[attr-defined]
    except ImportError:  # versões antigas do pydantic-ai
        from pydantic_ai.models.gemini import GeminiModel  # type: ignore[no-redef]
    return GeminiModel(model_name, api_key=api_key)


#: Endpoint da API compatível com OpenAI do OpenRouter.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _provider_for(model_name: str) -> str:
    """Rota de provedor pelo id do modelo: ids namespaced (`org/modelo`) → OpenRouter.

    Ids do Gemini nunca contêm `/`; `xiaomi/mimo-v2.6-pro` e similares sempre vão
    para o OpenRouter. Determinístico, sem dependência de env.
    """
    return "openrouter" if "/" in model_name else "gemini"


def _api_key_env_for(model_name: str) -> str:
    """Variável de ambiente da chave conforme o provedor do modelo."""
    return "OPENROUTER_API_KEY" if _provider_for(model_name) == "openrouter" else "GEMINI_API_KEY"


def _build_openrouter_model(model_name: str, api_key: str) -> Any:
    """Monta o modelo via OpenRouter (API compatível com OpenAI)."""
    from pydantic_ai.models import openai as openai_models
    from pydantic_ai.providers.openai import OpenAIProvider

    # `OpenAIModel` (antigo) ou `OpenAIChatModel` (nome novo do pydantic-ai).
    model_cls = getattr(openai_models, "OpenAIModel", None) or openai_models.OpenAIChatModel
    return model_cls(
        model_name,
        provider=OpenAIProvider(base_url=OPENROUTER_BASE_URL, api_key=api_key),
    )


class PydanticAIClient:
    """Provedor real (Gemini ou OpenRouter) via Pydantic AI, com registro de uso (RNF-03)."""

    def __init__(self, model_name: str | None = None, api_key: str | None = None):
        self._model_name = model_name or os.environ.get("LLM_MODEL") or "gemini-3.8-flash"
        key_env = _api_key_env_for(self._model_name)
        self._api_key = api_key or os.environ.get(key_env)
        self.usage: list[dict] = []

    def complete_json(self, prompt: str) -> Any:
        key_env = _api_key_env_for(self._model_name)
        if not self._api_key:
            raise ClassifiedError(
                "LLM_API_KEY_MISSING", f"{key_env} não configurada", retriable=False
            )

        try:
            from pydantic_ai import Agent

            if _provider_for(self._model_name) == "openrouter":
                model = _build_openrouter_model(self._model_name, self._api_key)
            else:
                model = _build_gemini_model(self._model_name, self._api_key)
        except ImportError as exc:
            raise ClassifiedError(
                "LLM_CLIENT_UNAVAILABLE", f"pydantic-ai indisponível: {exc}", retriable=False
            ) from exc
        try:
            agent = Agent(model, output_type=dict)
        except TypeError:  # versões antigas do pydantic-ai
            agent = Agent(model, result_type=dict)  # type: ignore[call-overload]
        # D2-P0-1: temperature=0 em extração/explicação (determinismo do prompt).
        # Timeout (validação real 2026-10-06): teto no SDK e na thread — sem ele,
        # conexão presa no provedor bloqueia o fluxo para sempre.
        run_kwargs: dict[str, Any] = {}
        try:
            from pydantic_ai.settings import ModelSettings

            run_kwargs["model_settings"] = ModelSettings(
                temperature=0.0, timeout=LLM_TIMEOUT_SECONDS
            )
        except Exception:  # SDK sem ModelSettings → segue sem a trava explícita
            pass
        result = _run_agent_blocking(agent, prompt, run_kwargs, timeout=LLM_TIMEOUT_SECONDS)
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


def build_insurer_prompt(page_texts: list[str]) -> str:
    """Prompt de escalação da seguradora: páginas iniciais (OCR/visão + nativo).

    Chega aqui só quando a leitura direta (`detect_insurer`) não confiou —
    a LLM confirma/interpreta o caso estranho, preferindo a visão (OCR).
    """
    lines = [
        "Identifique a seguradora (empresa provedora) desta apólice de seguro.",
        "O nome da empresa costuma estar na primeira ou, no máximo, na segunda",
        "página (cabeçalho/logo). Os blocos [OCR/visão] vêm da leitura visual —",
        "prefira-os para o nome da empresa; use [texto nativo] para confirmar.",
        "Se as fontes divergirem ou os dados parecerem estranhos, confirme antes",
        "de responder; sem certeza, devolva null — nunca invente.",
        "Responda SOMENTE com JSON {\"name\": ..., \"year\": ...}.",
        "\"name\" é o nome real da empresa seguradora (ex.: \"Porto Seguro\");",
        "\"year\" é o ano de referência da apólice (vigência/emissão, 4 dígitos).",
        "",
    ]
    for index, text in enumerate(page_texts, start=1):
        lines.append(f"## Página {index}")
        lines.append(text.strip() or "(sem texto)")
        lines.append("")
    return "\n".join(lines)


def build_question_prompt(question: str, evidences: list[EvidenceRef]) -> str:
    """Prompt do Agente Inteligente: pergunta + evidências recuperadas (RAG)."""
    lines = [
        "Você é o Agente Inteligente de análise de apólices de seguro D&O.",
        "Responda à pergunta do analista SOMENTE com base nas evidências fornecidas.",
        "Responda SOMENTE com JSON {\"text\": ..., \"evidence_ids\": [...]}.",
        "Toda afirmação deve citar evidence_ids fornecidos; se as evidências não",
        "sustentarem a resposta, diga que não encontrou base nas apólices.",
        "Nunca invente valores, números ou evidence_ids.",
        "",
        f"## Pergunta do analista\n{question.strip()}",
        "",
        "## Evidências das apólices",
    ]
    for ev in evidences:
        section = f" seção {ev.section_name}" if ev.section_name else ""
        lines.append(
            f"- [{ev.evidence_id}] pág. {ev.page_number}{section}: \"{ev.quoted_text}\""
        )
    return "\n".join(lines)


def build_review_prompt(message: str, facts: list[dict]) -> str:
    """Prompt de revisão: indicação do analista + fatos extraídos candidatos."""
    lines = [
        "O analista de seguro indicou divergências numa comparação de apólices D&O.",
        "Com base na indicação, decida quais fatos extraídos estão errados e como corrigi-los.",
        "Responda SOMENTE com JSON {\"corrections\": [...]}; cada item:",
        "{\"fact_id\", \"decision\": CORRIGIDO|DIVERGENTE|CONFIRMADO, \"value\": ...}.",
        "Use SOMENTE fact_id da lista fornecida, sem inventar IDs.",
        "CORRIGIDO exige \"value\" (o valor correto, no formato do campo — dinheiro",
        "como número simples, ex.: 2000000.00, sem símbolo de moeda);",
        "DIVERGENTE registra a divergência sem mudar o valor; CONFIRMADO confirma",
        "o valor atual. Se a indicação não apontar fatos específicos, devolva",
        "{\"corrections\": []} — nunca invente correções.",
        "",
        f"## Indicação do analista\n{message.strip()}",
        "",
        "## Fatos extraídos",
    ]
    for fact in facts:
        lines.append(
            f"- fact_id={fact.get('fact_id')} · {fact.get('policy_id')} · "
            f"{fact.get('field_code')} · status={fact.get('status')} · "
            f"valor={fact.get('value')} · evidências={fact.get('evidence_ids')}"
        )
    return "\n".join(lines)


def build_extra_findings_prompt(evidences: list[EvidenceRef]) -> str:
    """Prompt dos campos extras: achados relevantes fora do catálogo fechado.

    As seções do markdown entram como evidências; a resposta só pode citar os
    `evidence_ids` fornecidos e nunca inventar achado (RN-02).
    """
    lines = [
        "Você analisa seções de uma apólice de seguro D&O à procura de achados relevantes",
        "NÃO cobertos pelo catálogo padrão de campos (ex.: número SUSEP, produto,",
        "público-alvo, sublimites, prazos especiais de notificação).",
        "Responda SOMENTE com JSON {\"findings\": [...]}; cada item:",
        "{\"label\" (rótulo curto em pt-br), \"value\" (valor literal simples; dinheiro",
        "como número simples ex. 2000000.00), \"detail\" (1 frase), \"evidence_ids\",",
        "\"page_hint\" (página aproximada do achado)}.",
        "Os \"evidence_ids\" devem ser SOMENTE os ids fornecidos — nunca invente IDs.",
        "Sem achados relevantes, responda {\"findings\": []} — nunca invente achados.",
        "",
        "## Seções da apólice",
    ]
    for ev in evidences:
        section = f" seção {ev.section_name}" if ev.section_name else ""
        lines.append(
            f"- [{ev.evidence_id}] pág. {ev.page_number}{section}: \"{ev.quoted_text}\""
        )
    return "\n".join(lines)
