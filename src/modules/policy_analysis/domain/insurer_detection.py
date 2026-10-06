"""Detecção determinística da seguradora nas páginas iniciais (OCR-primeiro).

Leitura direta — sem custo de LLM — do nome da empresa provedora e do ano de
referência, preferindo os blocos de OCR/visão (logo/cabeçalho). O que vier
estranho, divergente ou ausente devolve `None`: o chamador escala para a LLM
e, em seguida, para o analista. EC-04: incerteza nunca vira palpite.

O nome da seguradora fica ao lado do logotipo (topo da página 1); linhas de
título do documento ("Condições Gerais…", "Apólice…") parecem nome, mas nunca
são — são rejeitadas mesmo contendo "seguro".
"""

from __future__ import annotations

import re

#: Linha que marca a origem do texto no preview (`[OCR/visão]`, `[texto nativo]`).
_TAG_LINE = re.compile(r"\[[^\]]+\]")

#: Linhas de título/documento: parecem nome, mas são o documento — nunca empresa.
_TITLE_MARKERS = (
    "condições gerais",
    "condicoes gerais",
    "condições especiais",
    "condicoes especiais",
    "cláusulas",
    "clausulas",
    "apólice",
    "apolice",
    "proposta",
    "certificado",
    "endosso",
    "responsabilidade",
    "cobertura",
    "franquia",
    "anexo",
    "sumário",
    "sumario",
    "índice",
    "indice",
    "gerais de seguro",
)

#: Sinais fortes de razão social de seguradora (marca, não o produto).
_STRONG_HINTS = (
    "seguros",
    "companhia",
    "insurance",
    "assurance",
    "s.a",
    "s/a",
    "ltda",
    "corp",
    "grupo",
)

#: Linhas do topo da página 1 = região do logotipo (nome ao lado da marca).
_HEADER_LINES = 5

#: `vigência ... 2025` / `emissão ...` / `apólice ...` → ano de referência.
_YEAR_CONTEXT = re.compile(
    r"(?:vig[eê]ncia|emiss[aã]o|compet[eê]ncia|ap[oó]lice)[^0-9]{0,40}(\d{4})",
    re.IGNORECASE,
)
_DATE = re.compile(r"\b\d{2}/\d{2}/(\d{4})\b")

_YEAR_MIN, _YEAR_MAX = 1990, 2100


def _clean_line(line: str) -> str:
    text = re.sub(r"^\W+", "", line.strip())
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:|\t")


def _company_from_line(line: str, *, in_header: bool) -> str | None:
    """Nome de seguradora plausível na linha, ou `None` (sem palpite)."""
    text = _clean_line(line)
    if not (3 <= len(text) <= 60):
        return None
    words = text.split()
    if not (1 <= len(words) <= 8):
        return None
    if any(ch.isdigit() for ch in text):
        return None
    letters = sum(ch.isalpha() for ch in text)
    if letters < 3 or letters / max(len(text), 1) < 0.55:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in _TITLE_MARKERS):
        return None  # título do documento, não empresa
    if any(hint in lowered for hint in _STRONG_HINTS):
        return text
    if in_header and text[:1].isupper():
        return text  # região do logotipo: linha curta em maiúsculas é marca
    return None


def _year_from_line(line: str) -> str | None:
    match = _YEAR_CONTEXT.search(line)
    if match:
        return match.group(1)
    for value in _DATE.findall(line):
        if _YEAR_MIN <= int(value) <= _YEAR_MAX:
            return value
    return None


def detect_insurer(page_texts: list[str]) -> dict | None:
    """Nome/ano da seguradora pela leitura direta das páginas 1–2.

    Confia apenas em resultado único e plausível; candidatos divergentes,
    ausentes ou estranhos → `None` (caso para a LLM confirmar). Um candidato
    contido em outro (`Porto Seguro` × `Porto Seguro S.A.`) é o mesmo de sempre
    — vale o mais completo.
    """
    candidates: list[str] = []
    year: str | None = None
    for page_index, text in enumerate(page_texts):
        content_line = 0
        for raw_line in str(text or "").splitlines():
            if _TAG_LINE.fullmatch(raw_line.strip()):
                continue
            content_line += 1
            in_header = page_index == 0 and content_line <= _HEADER_LINES
            if year is None:
                year = _year_from_line(raw_line)
            name = _company_from_line(raw_line, in_header=in_header)
            if name and name not in candidates:
                candidates.append(name)

    collapsed: list[str] = []
    for name in sorted(candidates, key=len, reverse=True):
        if any(name.lower() in base.lower() for base in collapsed):
            continue
        collapsed.append(name)
    if len(collapsed) != 1:
        return None
    return {"name": collapsed[0], "year": year}
