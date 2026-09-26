"""Ancoragem de citações do LLM no texto real das evidências (RF-01, D2-P0-1).

Regra (A-07, OQ-02 decidido como **substring**): toda citação/excerpt
produzido pelo LLM deve existir literalmente no texto do chunk recuperado
(`EvidenceRef.quoted_text`). Sem ancoragem o output nunca vira fato `FOUND`.

Módulo puro: stdlib apenas, determinístico, sem LLM e sem I/O (A-08).
"""

import re
from typing import Any

#: Chaves de `value`/`normalized_value` que carregam trecho literal (excerpt).
#: Escalares (`scalar`, `amount`, `currency`...) NÃO são citação e ficam fora
#: da ancoragem — valores normalizados (ex.: data ISO) não são substring do
#: texto original.
QUOTE_KEYS = ("raw_text", "excerpt", "quote", "quoted_text", "cited_text", "trecho")

#: Trechos entre aspas em texto livre (explicação do LLM) — candidatos a citação.
_QUOTED_SEGMENT = re.compile(
    r'"([^"\n]+)"|\'([^\'\n]+)\'|«([^»\n]+)»|“([^”\n]+)”|‘([^’\n]+)’'
)


def collect_excerpts(payload: Any) -> list[str]:
    """Coleta os trechos literais de um payload de valor do LLM.

    Percorre o payload recursivamente; só strings sob as chaves de
    `QUOTE_KEYS` são excerpt (listas são achatadas). Excerpts vazios/só
    espaços são descartados — não são citação verificável.
    """
    collected: list[str] = []
    _collect_excerpts(payload, collected)
    return [excerpt for excerpt in collected if excerpt.strip()]


def extract_quoted_segments(text: str) -> list[str]:
    """Trechos entre aspas de um texto livre (explicação) — candidatos a citação."""
    segments = []
    for match in _QUOTED_SEGMENT.finditer(text):
        segment = next(group for group in match.groups() if group is not None)
        segments.append(segment)
    return segments


def unanchored_excerpts(excerpts: list[str], source_texts: list[str]) -> list[str]:
    """Subconjunto de `excerpts` que NÃO é substring literal de nenhum texto-fonte.

    Com múltiplas evidências, TODAS as citações são avaliadas: qualquer uma
    fora do corpus citado é devolvida como não ancorada.
    """
    texts = [text for text in source_texts if isinstance(text, str)]
    return [
        excerpt
        for excerpt in excerpts
        if not any(excerpt.strip() in text for text in texts)
    ]


def _collect_excerpts(payload: Any, out: list[str]) -> None:
    if isinstance(payload, dict):
        for key, item in payload.items():
            if key in QUOTE_KEYS:
                _collect_strings(item, out)
            else:
                _collect_excerpts(item, out)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            _collect_excerpts(item, out)


def _collect_strings(item: Any, out: list[str]) -> None:
    if isinstance(item, str):
        out.append(item)
    elif isinstance(item, (list, tuple)):
        for sub in item:
            _collect_strings(sub, out)
