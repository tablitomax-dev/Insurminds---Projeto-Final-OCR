"""Âncora de citação do LLM (D2-P0-1, OQ-02 = substring literal).

Guarda pós-LLM: toda citação/trecho literal que o LLM coloque no `value` de um
fato deve existir de fato no texto (`EvidenceRef.quoted_text`) das evidências
citadas naquele fato. Citação que não ancora é invenção do modelo e nunca vira
`FOUND` — rebaixa o fato para `NEEDS_REVIEW` com motivo registrado.

Decisão de design (adaptação ao formato de valor estruturado do Dev 2): o
`value` normalmente carrega escalares (`amount`/`text`/`start`/...), não texto
literai. A ancoragem só se aplica às chaves de citação quando presentes
(`raw_text`, `excerpt`, `quote`, `quoted_text`, `cited_text`, `trecho`) e aos
trechos entre aspas de campos de texto livre. Um fato sem nenhuma citação não
tem o que ancorar — a validação do valor fica com `rules`/normalização.

Comparação é substring **literal** após trim de bordas (OQ-02), sem semelhança
difusa. Mensagem de motivo traz apenas quantidade, nunca o texto (T-2a).
"""

from __future__ import annotations

import re

#: Chaves sob as quais o LLM pode devolver um trecho literal citado.
CITATION_KEYS: tuple[str, ...] = (
    "raw_text",
    "excerpt",
    "quote",
    "quoted_text",
    "cited_text",
    "trecho",
)

_QUOTED_SEGMENT = re.compile(r"[\"“”']([^\"“”']+)[\"“”']")


def collect_excerpts(value: dict | None) -> list[str]:
    """Coleta trechos literais citados no `value` (chaves de citação + aspas).

    Escalares puros (`amount`, `number`, datas) não são citação. Em campos de
    texto livre, trechos entre aspas também contam como citação literal.
    """
    if not isinstance(value, dict):
        return []
    excerpts: list[str] = []
    for key in CITATION_KEYS:
        part = value.get(key)
        if isinstance(part, str) and part.strip():
            excerpts.append(part.strip())
    # trechos entre aspas em chaves de texto livre
    for key in ("text", "value_text", "raw_text"):
        part = value.get(key)
        if isinstance(part, str):
            for match in _QUOTED_SEGMENT.findall(part):
                if match.strip():
                    excerpts.append(match.strip())
    return excerpts


def anchor_texts_for(evidences, evidence_ids) -> list[str]:
    """Textos âncora (`quoted_text`) das evidências citadas no fato."""
    wanted = set(evidence_ids or [])
    return [
        ev.quoted_text
        for ev in evidences
        if getattr(ev, "evidence_id", None) in wanted and getattr(ev, "quoted_text", None)
    ]


def unanchored_excerpts(excerpts: list[str], anchor_texts: list[str]) -> list[str]:
    """Excerpts que NÃO aparecem literalmente em nenhum texto âncora.

    Com múltiplas evidências, a âncora é a união dos textos: um excerpt basta
    existir em um deles. Uma citação inválida já é suficiente para rejeitar.
    """
    if not excerpts:
        return []
    anchors = [a for a in anchor_texts if a]
    bad: list[str] = []
    for excerpt in excerpts:
        needle = excerpt.strip()
        if not needle:
            continue
        if not any(needle in anchor for anchor in anchors):
            bad.append(excerpt)
    return bad


def is_anchored(value: dict | None, evidences, evidence_ids) -> tuple[bool, int]:
    """Retorna (ancorado, nº de citações não ancoradas) para o valor do fato.

    `True` quando não há citação inventada. Um fato sem citação retorna
    `(True, 0)` — não há o que ancorar.
    """
    excerpts = collect_excerpts(value)
    if not excerpts:
        return True, 0
    anchors = anchor_texts_for(evidences, evidence_ids)
    bad = unanchored_excerpts(excerpts, anchors)
    return (not bad), len(bad)
