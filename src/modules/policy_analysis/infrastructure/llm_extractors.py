"""Adapters LLM (Pydantic AI + Gemini): extração e explicação (D-06).

Regra absoluta: o LLM extrai e explica, jamais compara — a comparação é
determinística em `domain/comparison.py`. Os imports de `pydantic_ai` são
lazy: sem lib ou sem chave de API a instanciação falha com `RuntimeError`.
"""

import os

from pydantic import BaseModel, Field

from shared_kernel.contracts import EvidenceRef, ExtractedFact, ExtractionRequest

from ..application.ports import LlmOutputError

#: Modelo Gemini padrão do vertical slice.
DEFAULT_MODEL = "gemini-2.0-flash"

#: Variável de ambiente com a chave da API Gemini.
API_KEY_ENV = "GEMINI_API_KEY"

#: Temperatura dos agentes (D2-P0-1): 0.0 para saída determinística.
LLM_TEMPERATURE = 0.0

_EXTRACTION_SYSTEM_PROMPT = """\
Você é um analista de apólices D&O. Extraia o campo pedido usando SOMENTE \
as evidências fornecidas — nunca invente informação nem evidence_id.

Regras:
- Cite nos `evidence_ids` apenas os IDs das evidências realmente usadas.
- `status`: FOUND quando o valor é claro; NOT_FOUND quando não aparece; \
AMBIGUOUS quando trechos conflitam; NEEDS_REVIEW quando o valor está ilegível.
- `value`: objeto JSON com o escalar comparável em "scalar" (número para \
valores monetários, data ISO AAAA-MM-DD, texto para o resto) e o trecho \
literal em "raw_text".
- `raw_text` é CÓPIA LITERAL (substring exata) do texto da evidência citada \
— nunca paráfrase nem valor inventado; a extração é verificada por ancoragem.
- `confidence` entre 0 e 1.
- `requires_human_review` = true quando houver dúvida que justifique o \
analista confirmar.
- `fact_id` no formato `fact_<32 caracteres hexadecimais>`.
"""


class _ExplanationOutput(BaseModel):
    """Formato da saída do agente de explicação."""

    texto: str = Field(min_length=1)
    evidence_ids: list[str]


class PydanticAiFieldExtractor:
    """Agente Pydantic AI que extrai um campo produzindo `ExtractedFact` validado."""

    def __init__(self, model_name: str = DEFAULT_MODEL, api_key: str | None = None) -> None:
        try:
            from pydantic_ai import Agent
            from pydantic_ai.models.google import GoogleModel
            from pydantic_ai.providers.google import GoogleProvider
            from pydantic_ai.settings import ModelSettings
        except ImportError as exc:
            raise RuntimeError("dependência ausente: pydantic-ai") from exc
        self._agent = Agent(
            GoogleModel(model_name, provider=GoogleProvider(api_key=_resolve_api_key(api_key))),
            output_type=ExtractedFact,
            system_prompt=_EXTRACTION_SYSTEM_PROMPT,
            model_settings=ModelSettings(temperature=LLM_TEMPERATURE),
        )

    def extract(self, request: ExtractionRequest) -> ExtractedFact:
        """Extrai o campo do request; saída fora do schema nunca vira fato (RF-09)."""
        try:
            run = self._agent.run_sync(_build_extraction_prompt(request))
        except Exception as exc:  # timeout/429/indisponibilidade (EC-01)
            # Só o tipo da exceção: a mensagem pode ecoar texto de apólice (T-2a).
            raise LlmOutputError(
                f"EXTRACT: falha na execução do agente de extração ({type(exc).__name__})"
            ) from exc
        output = getattr(run, "output", None)
        if not isinstance(output, ExtractedFact):
            raise LlmOutputError("EXTRACT: saída do LLM fora do schema ExtractedFact")
        return output


class LlmExplanationGenerator:
    """Agente que explica a diferença entre 2 apólices citando evidências (RF-07)."""

    def __init__(self, model_name: str = DEFAULT_MODEL, api_key: str | None = None) -> None:
        try:
            from pydantic_ai import Agent
            from pydantic_ai.models.google import GoogleModel
            from pydantic_ai.providers.google import GoogleProvider
            from pydantic_ai.settings import ModelSettings
        except ImportError as exc:
            raise RuntimeError("dependência ausente: pydantic-ai") from exc
        self._agent = Agent(
            GoogleModel(model_name, provider=GoogleProvider(api_key=_resolve_api_key(api_key))),
            output_type=_ExplanationOutput,
            system_prompt=(
                "Explique a diferença entre as duas apólices para um analista, "
                "usando SOMENTE as evidências fornecidas e citando nos "
                "`evidence_ids` exatamente os IDs usados (evidências de ambos "
                "os lados quando disponíveis). Se citar trechos literalmente, "
                "use aspas duplas e copie EXATAMENTE o texto das evidências — "
                "a explicação é verificada por ancoragem de citação."
            ),
            model_settings=ModelSettings(temperature=LLM_TEMPERATURE),
        )

    def explain(
        self,
        field_code: str,
        direction: str,
        fact_a: ExtractedFact | None,
        fact_b: ExtractedFact | None,
        evidences_a: list[EvidenceRef],
        evidences_b: list[EvidenceRef],
    ) -> tuple[str, list[str]]:
        """Devolve (texto da explicação, evidence_ids citados)."""
        prompt = _build_explanation_prompt(field_code, direction, fact_a, fact_b, evidences_a, evidences_b)
        try:
            run = self._agent.run_sync(prompt)
        except Exception as exc:
            # Só o tipo da exceção: a mensagem pode ecoar texto de apólice (T-2a).
            raise LlmOutputError(
                f"EXPLAIN: falha na execução do agente de explicação ({type(exc).__name__})"
            ) from exc
        output = getattr(run, "output", None)
        if not isinstance(output, _ExplanationOutput):
            raise LlmOutputError("EXPLAIN: saída do LLM fora do schema de explicação")
        return output.texto.strip(), [str(evidence_id) for evidence_id in output.evidence_ids]


def _resolve_api_key(api_key: str | None) -> str:
    resolved = api_key or os.environ.get(API_KEY_ENV)
    if not resolved:
        raise RuntimeError(f"dependência ausente: chave da API Gemini (variável {API_KEY_ENV})")
    return resolved


def _build_extraction_prompt(request: ExtractionRequest) -> str:
    evidences = "\n".join(
        f"- evidence_id={evidence.evidence_id} (página {evidence.page_number}): "
        f"{evidence.quoted_text}"
        for evidence in request.evidences
    )
    return (
        f"policy_id: {request.policy_id}\n"
        f"field_code: {request.field_code}\n"
        f"schema_version: {request.schema_version}\n\n"
        f"Evidências recuperadas:\n{evidences}"
    )


def _build_explanation_prompt(
    field_code: str,
    direction: str,
    fact_a: ExtractedFact | None,
    fact_b: ExtractedFact | None,
    evidences_a: list[EvidenceRef],
    evidences_b: list[EvidenceRef],
) -> str:
    def _evidence_block(evidences: list[EvidenceRef]) -> str:
        return "\n".join(
            f"- evidence_id={evidence.evidence_id} (página {evidence.page_number}): "
            f"{evidence.quoted_text}"
            for evidence in evidences
        ) or "(sem evidências)"

    return (
        f"field_code: {field_code}\n"
        f"direção da comparação (A em relação a B): {direction}\n"
        f"valor de A: {fact_a.value if fact_a else '(ausente)'}\n"
        f"valor de B: {fact_b.value if fact_b else '(ausente)'}\n\n"
        f"Evidências de A:\n{_evidence_block(evidences_a)}\n\n"
        f"Evidências de B:\n{_evidence_block(evidences_b)}"
    )
