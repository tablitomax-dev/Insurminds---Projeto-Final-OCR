"""Domínio puro de estrutura documental (feature dev1-006 — NG-01).

Detecção de marcadores de seção e serialização de tabelas. Puro: apenas
stdlib (RNF-06) — nenhuma dependência externa aqui.

Semântica (clarify 2026-10-01 + RN-02/RN-03):
- Família FECHADA de marcadores: Cláusula, Artigo, Seção e Epígrafe, ancorada
  no início de linha — nada de heurística ampla de linhas em destaque.
- O `section_name` gravado é o LITERAL do documento, sem normalização; nomes
  nunca são inventados sem fonte no próprio documento.
- Tabela serializada entra como texto do chunk com o marcador `[TABELA]` — o
  corte de chunks não muda (RN-06).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

#: Família fechada de marcadores estruturais (clarify 2026-10-01).
#: `MULTILINE`: o `^` ancora em cada início de linha, não só da string.
SECTION_MARKER_PATTERN = re.compile(
    r"^[ \t]*(cl[áa]usula|artigo|se[çc][ãa]o|ep[íi]grafe)\b[^\n]*",
    re.IGNORECASE | re.MULTILINE,
)

#: Prefixo que marca uma tabela serializada dentro do texto do chunk (RN-03).
TABLE_MARKER = "[TABELA]"


@dataclass(frozen=True)
class SectionMarker:
    """Marcador de seção detectado; `name` é o literal do documento (RN-02)."""

    name: str
    char_offset: int


def detect_section_markers(text: str) -> list[SectionMarker]:
    """Marcadores de seção do texto, em ordem; literal preservado (RN-02)."""
    markers: list[SectionMarker] = []
    for match in SECTION_MARKER_PATTERN.finditer(text):
        markers.append(
            SectionMarker(name=match.group(0).strip(), char_offset=match.start())
        )
    return markers


def assign_sections(
    pieces: list[str], initial: str | None = None
) -> tuple[list[str | None], str | None]:
    """Atribui a seção vigente a cada peça e devolve o estado final.

    Regra determinística (decisão dev1-006):
    - a peça herda a seção vigente no início dela;
    - um marcador no início da peça (após espaço em branco) já vale para a
      própria peça;
    - marcadores internos passam a valer para as peças seguintes.

    A seção vigente atravessa peças e páginas — `initial` é o estado vindo da
    página anterior (literal ou `None` antes do primeiro marcador).
    """
    current = initial
    sections: list[str | None] = []
    for piece in pieces:
        markers = detect_section_markers(piece)
        section = current
        if markers and piece[: markers[0].char_offset].strip() == "":
            section = markers[0].name
        sections.append(section)
        if markers:
            current = markers[-1].name
    return sections, current


def serialize_table(regions: Iterable[object]) -> str:
    """Serializa as regiões de tabela em texto com o marcador `[TABELA]` (RN-03).

    Aceita objetos com atributos `kind`, `text` e `order` (ex.: `LayoutRegion`)
    por duck-typing — o domínio não importa aplicação/infraestrutura. Regiões
    que não sejam `table` são ignoradas; tabela cujo corpo renderiza vazio não
    vira marcador órfão (devolve string vazia).
    """
    tables = sorted(
        (region for region in regions if getattr(region, "kind", None) == "table"),
        key=lambda region: getattr(region, "order", 0),
    )
    rendered: list[str] = []
    for table in tables:
        body = _render_tsv(getattr(table, "text", ""))
        if body:
            rendered.append(f"{TABLE_MARKER}\n{body}")
    return "\n".join(rendered)


def compose_page_text(regions: Iterable[object]) -> str:
    """Compõe o texto da página em ordem de leitura, tabelas serializadas.

    Regiões `heading`/`text` entram como o próprio texto (literal); regiões
    `table` passam por `serialize_table`. Ordem: atributo `order`.
    """
    parts: list[str] = []
    for region in sorted(regions, key=lambda r: getattr(r, "order", 0)):
        if getattr(region, "kind", None) == "table":
            rendered = serialize_table([region])
        else:
            rendered = getattr(region, "text", "").strip()
        if rendered:
            parts.append(rendered)
    return "\n".join(parts)


def _render_tsv(table_tsv: str) -> str:
    """Renderiza TSV (linhas `\\n`, células `\\t`) como linhas `a | b | c`."""
    lines: list[str] = []
    for row in table_tsv.splitlines():
        cells = [cell.strip() for cell in row.split("\t")]
        if not any(cells):
            continue
        lines.append(" | ".join(cells))
    return "\n".join(lines)


# ------------------------------- Seções de markdown estruturado (caminho markdown)

#: Heading ATX de markdown: 1 a 4 `#` seguidos de espaço e título não vazio.
#: `#####` ou mais `#`, e linha sem título, NÃO separam seção (determinístico).
ATX_HEADING_PATTERN = re.compile(r"^(#{1,4})[ \t]+(\S.*)$", re.MULTILINE)


@dataclass(frozen=True)
class MarkdownSection:
    """Seção de uma página em markdown, na ordem de leitura.

    `title` é o literal do heading ATX sem os `#`; texto anterior ao primeiro
    heading vira seção com `title=None`. `body` é o texto entre o heading e o
    próximo (sem o próprio heading). `index` é 0-based na ordem de leitura.
    """

    title: str | None
    body: str
    page_number: int
    index: int


def split_markdown_sections(markdown: str, page_number: int) -> list[MarkdownSection]:
    """Quebra o markdown de uma página em seções por headings ATX (níveis 1–4).

    Regras determinísticas (mesma entrada, mesma saída):
    - texto antes do primeiro heading vira seção com `title=None`;
    - heading define o título da seção seguinte, excluído do corpo;
    - seções com corpo vazio são descartadas (inclusive o preâmbulo);
    - a lista devolvida segue a ordem de leitura, com `index` sequencial.
    """
    blocks: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for line in markdown.splitlines():
        match = ATX_HEADING_PATTERN.match(line)
        if match is None:
            current_lines.append(line)
            continue
        blocks.append((current_title, current_lines))
        current_title = match.group(2).strip()
        current_lines = []
    blocks.append((current_title, current_lines))

    sections: list[MarkdownSection] = []
    for title, lines in blocks:
        body = "\n".join(lines).strip()
        if not body:
            continue
        sections.append(
            MarkdownSection(
                title=title,
                body=body,
                page_number=page_number,
                index=len(sections),
            )
        )
    return sections
