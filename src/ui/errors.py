"""Mensagens de erro sanitizadas para a UI (T-2a/T-2b) — módulo puro.

`st.error` mostra estágio + tipo do erro (+ detalhe seguro); nunca stack,
nunca `ValidationError` crua e nunca texto de apólice (RF-06).
"""

from __future__ import annotations

from modules.policy_analysis.public_api import ClassifiedError
from shared_kernel.errors import ContractError

#: Exceções cuja mensagem já é construída pelo código do projeto, com IDs e
#: nomes de campo filtrados (T-2a) — só elas podem ecoar `str(exc)`.
_SAFE_MESSAGE_TYPES: tuple[type[BaseException], ...] = (ContractError,)

#: Detalhe usado quando a mensagem da exceção não é confiável.
_OMITTED_DETAIL = "detalhe omitido (mensagem não sanitizada)"


def sanitize_error_message(stage: str, error: BaseException) -> str:
    """Mensagem tipada para a UI: estágio + tipo (+ detalhe seguro).

    `ClassifiedError` ecoa só o `.code` sanitizado (nunca `str(exc)`); exceções
    de `_SAFE_MESSAGE_TYPES` ecoam a mensagem do projeto; qualquer outra
    (`ValidationError`, erros de LLM/infra) vira só o tipo: `str(exc)`,
    `ValidationError` e stack podem conter texto de apólice.
    """
    kind = type(error).__name__
    if isinstance(error, ClassifiedError):
        detail = f"código {error.code}"
    elif isinstance(error, _SAFE_MESSAGE_TYPES):
        detail = str(error)
    else:
        detail = _OMITTED_DETAIL
    return f"{stage}: {kind} — {detail}"
