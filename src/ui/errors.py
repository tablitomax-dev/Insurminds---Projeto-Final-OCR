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


def sanitize_error_message(stage: str, error: BaseException) -> str:
    """Mensagem de erro para a UI: estágio + tipo + detalhe completo.

    Sem trava de sanitização (decisão de 2026-10-05): `str(error)` vai para a
    tela; `ClassifiedError` ainda exibe o código estável junto da mensagem.
    """
    kind = _KIND_LABELS.get(type(error).__name__, type(error).__name__)
    detail = str(error).strip() or "sem detalhe"
    if isinstance(error, ClassifiedError):
        detail = f"{detail} (código {error.code})"
    return f"{stage}: {kind} — {detail}"
