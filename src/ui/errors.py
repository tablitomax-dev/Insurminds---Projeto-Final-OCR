"""Mensagens de erro da UI — detalhe completo para diagnóstico.

Decisão do humano (2026-10-05): o projeto não tem dados sensíveis — a trava
de sanitização (T-2a) foi removida e a mensagem real da exceção é exibida
na tela para agilizar o diagnóstico.
"""

from __future__ import annotations

from modules.policy_analysis.public_api import ClassifiedError

#: Tipo da exceção → leitura humana do analista (pt-br).
_KIND_LABELS: dict[str, str] = {
    "ClassifiedError": "Erro classificado",
    "ContractError": "Erro de contrato",
    "ContractValidationError": "Erro de regra de contrato",
    "NormalizationError": "Erro de normalização",
    "ValidationError": "Erro de validação",
    "ValueError": "Valor inválido",
    "RuntimeError": "Erro de execução",
    "ImportError": "Erro de dependência ausente",
    "FileNotFoundError": "Arquivo não encontrado",
    "TimeoutError": "Tempo esgotado",
}

#: Código do `ClassifiedError` → dica curta e amigável para o analista (pt-br).
_CODE_HINTS: dict[str, str] = {
    "LLM_UNAVAILABLE": (
        "Os provedores de IA não responderam após várias tentativas. Tente novamente em instantes."
    ),
    "LLM_TIMEOUT": "O provedor de IA demorou para responder e a tentativa foi interrompida.",
    "LLM_SCHEMA_INVALID": (
        "O provedor de IA respondeu fora do formato esperado — tentar novamente costuma resolver."
    ),
    "LLM_API_KEY_MISSING": "Falta configurar a chave da API de IA no ambiente.",
    "LLM_QUOTA_EXCEEDED": (
        "A chave do provedor de IA estourou o limite de crédito — recarregue em openrouter.ai e tente novamente."
    ),
    "LLM_AUTH_FAILED": (
        "A chave do provedor de IA foi recusada — verifique a variável de ambiente OPENROUTER_API_KEY."
    ),
    "LLM_CLIENT_UNAVAILABLE": "A biblioteca de integração com a IA não está disponível neste ambiente.",
    "EVIDENCE_UNKNOWN": "A evidência citada não pertence ao pedido de extração.",
    "COMPARISON_NOT_FOUND": "A comparação indicada não existe mais — gere uma nova comparação.",
    "COMPARISON_FIELD_NOT_FOUND": "O campo indicado não faz parte da comparação atual.",
    "EXPLANATION_NOT_CITED": "A explicação não citou evidências dos dois lados — tente novamente.",
    "SECTIONS_UNAVAILABLE": "As seções do markdown não estão disponíveis — processe as apólices antes.",
    "DOCUMENT_PROCESSING_UNAVAILABLE": "O processamento de documentos está indisponível neste ambiente.",
}

#: Dica usada quando o código classificado não tem leitura específica.
_DEFAULT_CODE_HINT = "Tente novamente; se persistir, use o detalhe e o código acima no diagnóstico."


def sanitize_error_message(stage: str, error: BaseException) -> str:
    """Mensagem de erro para a UI: estágio + tipo + dica + detalhe completo.

    Sem trava de sanitização (decisão de 2026-10-05): `str(error)` vai para a
    tela; `ClassifiedError` ganha uma dica amigável por código, mantendo o
    detalhe real da exceção e o código estável na mensagem.
    """
    kind = _KIND_LABELS.get(type(error).__name__, type(error).__name__)
    detail = str(error).strip() or "sem detalhe"
    if isinstance(error, ClassifiedError):
        hint = _CODE_HINTS.get(error.code, _DEFAULT_CODE_HINT)
        return f"{stage}: {kind} — {hint} {detail} (código {error.code})"
    return f"{stage}: {kind} — {detail}"
