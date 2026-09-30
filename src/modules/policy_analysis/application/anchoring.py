"""Ancoragem de citação do LLM (D2-P0-1, A-07).

Toda citação/excerpt produzido pelo LLM deve existir de fato no texto das
evidências recebidas (`EvidenceRef.quoted_text`). Sem ancoragem, o fato NUNCA
é `FOUND` — vira `NEEDS_REVIEW` para o analista. A comparação usa a
normalização pt-br testada (caixa/acentos/espaços).
"""

from __future__ import annotations

from shared_kernel.contracts import EvidenceRef

from ..domain.value_types import NormalizationError, normalize_text


def is_anchored(quote: str, evidences: list[EvidenceRef]) -> bool:
    """A citação (normalizada) aparece no texto de alguma evidência?"""
    try:
        needle = normalize_text(str(quote))
    except NormalizationError:
        return False
    for ev in evidences:
        try:
            haystack = normalize_text(ev.quoted_text)
        except NormalizationError:
            continue
        if needle in haystack:
            return True
    return False
