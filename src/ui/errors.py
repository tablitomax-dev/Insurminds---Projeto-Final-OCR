"""Mensagens de erro sanitizadas para a UI (T-2a/T-2b) — módulo puro.

`st.error` mostra estágio + tipo do erro (+ detalhe seguro); nunca stack,
nunca `ValidationError` crua e nunca texto de apólice (RF-06).
"""

from __future__ import annotations

from modules.policy_analysis.public_api import LlmOutputError
from shared_kernel.errors import ContractError

#: Exceções cuja mensagem já é construída pelo código do projeto, com IDs e
#: nomes de campo filtrados (T-2a) — só elas podem ecoar `str(exc)`.
_SAFE_MESSAGE_TYPES: tuple[type[BaseException], ...] = (ContractError, LlmOutputError)

#: Detalhe usado quando a mensagem da exceção não é confiável.
_OMITTED_DETAIL = "detalhe omitido (mensagem não sanitizada)"


def sanitize_error_message(stage: str, error: BaseException) -> str:
    """Mensagem tipada para a UI: estágio + tipo (+ detalhe seguro).

    Qualquer exceção fora de `_SAFE_MESSAGE_TYPES` vira só o tipo: `str(exc)`,
    `ValidationError` e stack podem conter texto de apólice.
    """
    kind = type(error).__name__
    detail = str(error) if isinstance(error, _SAFE_MESSAGE_TYPES) else _OMITTED_DETAIL
    return f"{stage}: {kind} — {detail}"
