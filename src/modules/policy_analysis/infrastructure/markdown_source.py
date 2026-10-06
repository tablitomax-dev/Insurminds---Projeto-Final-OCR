"""Evidências por seções do markdown da apólice (RAG por seções).

Esta é a fonte de evidência "estruturada": em vez de trechos do índice vetorial,
cada SEÇÃO do markdown vira uma `EvidenceRef` cujo `quoted_text` é o corpo da
seção — nada é inventado, só texto vindo do markdown (RN-02). O `split` vive
aqui (e não no `document_processing`) para que este módulo não dependa de
internos do módulo documental (RF-01): só a fachada pública é consultada, de
forma lazy, quando ainda não há markdown cacheado no repositório.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from shared_kernel.contracts import EvidenceRef, SourceType

#: Origem do texto das seções — literal válido de `shared_kernel.contracts.SourceType`.
#: `PP_STRUCTURE` é o reservado do contrato para a fase de estruturação em seções.
SECTION_SOURCE_TYPE: SourceType = "PP_STRUCTURE"

#: Headings markdown de 1 a 4 níveis (`#` a `####`) iniciam uma seção.
_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)

#: Teto de caracteres do corpo citado; o resto vira sufixo `…`.
MAX_QUOTED_CHARS = 4000

#: Teto de seções devolvidas sem `field_code` (ordem de leitura).
MAX_SECTIONS = 20

#: Teto de páginas extraídas por documento quando a fachada é consultada.
MAX_PAGES = 200

#: Termos de ligação do pt-br ignorados na sobreposição léxica.
_STOPWORDS = {
    "aos",
    "ate",
    "com",
    "como",
    "das",
    "de",
    "desde",
    "dos",
    "e",
    "em",
    "entre",
    "era",
    "esta",
    "este",
    "isso",
    "mais",
    "na",
    "nas",
    "no",
    "nos",
    "num",
    "numa",
    "o",
    "os",
    "para",
    "pela",
    "pelas",
    "pelo",
    "pelos",
    "por",
    "qual",
    "que",
    "sem",
    "ser",
    "seu",
    "sua",
    "the",
    "and",
}


@dataclass(frozen=True)
class MarkdownSectionRef:
    """Uma seção do markdown de uma página (título + corpo)."""

    title: str | None
    text: str
    page_number: int
    index: int


def split_markdown_sections(markdown: str, page_number: int) -> list[MarkdownSectionRef]:
    """Quebra o markdown de uma página em seções por headings (`#` a `####`).

    O texto anterior ao primeiro heading vira a seção de abertura (`title=None`);
    seções com corpo vazio são descartadas e o `index` é estável por página.
    """
    matches = list(_HEADING_RE.finditer(markdown))
    if not matches:
        text = markdown.strip()
        return [MarkdownSectionRef(None, text, page_number, 0)] if text else []

    sections: list[MarkdownSectionRef] = []
    preamble = markdown[: matches[0].start()].strip()
    if preamble:
        sections.append(MarkdownSectionRef(None, preamble, page_number, 0))
    for position, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[position + 1].start() if position + 1 < len(matches) else len(markdown)
        body = markdown[body_start:body_end].strip()
        if not body:  # heading sem corpo não vira evidência
            continue
        sections.append(
            MarkdownSectionRef(match.group(1).strip(), body, page_number, len(sections))
        )
    return sections


def _terms(text: str) -> set[str]:
    """Termos normalizados (minúsculas, sem acentos) para sobreposição léxica."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return {
        token
        for token in re.split(r"[^a-z0-9]+", plain)
        if len(token) >= 3 and token not in _STOPWORDS
    }


class MarkdownSectionEvidenceSource:
    """Evidências por seções do markdown, ranqueadas por sobreposição léxica.

    As seções vêm primeiro do cache (`repo.get_markdown_pages`); sem cache, a
    fachada `document_processing` é consultada uma única vez e o resultado fica
    persistido por página no repositório — a extração nunca se repete. Cada
    seção vira uma `EvidenceRef` com `quoted_text` = corpo da seção, truncado
    em `MAX_QUOTED_CHARS` (nada de conteúdo inventado).
    """

    def __init__(
        self,
        repo,
        document_facade=None,
        fingerprint=None,
        top_sections: int = 6,
        file_paths: dict[str, str] | None = None,
    ):
        self._repo = repo
        self._document_facade = document_facade
        self._fingerprint = fingerprint
        self._top_sections = max(top_sections, 1)
        self._file_paths = dict(file_paths or {})
        self._sections_cache: dict[str, list[MarkdownSectionRef]] = {}

    # --- carregamento das seções ---------------------------------------------

    def get_sections(self, policy_id: str) -> list[MarkdownSectionRef]:
        """Seções do documento, com cache em memória por `policy_id`."""
        cached = self._sections_cache.get(policy_id)
        if cached is not None:
            return cached
        pages = self._repo.get_markdown_pages(policy_id)
        if not pages:
            pages = self._extract_and_store(policy_id)
        sections = [
            section
            for page_number, markdown in pages
            for section in split_markdown_sections(markdown, page_number)
        ]
        self._sections_cache[policy_id] = sections
        return sections

    def _extract_and_store(self, policy_id: str) -> list[tuple[int, str]]:
        """Extrai o markdown pela fachada e persiste por página (cache durável).

        O caminho do arquivo vem do mapeamento `file_paths` registrado no
        processamento; sem registro, usa a própria `policy_id` como caminho.
        """
        facade = self._resolve_facade()
        fingerprint = getattr(facade, "fingerprint", None) or self._fingerprint
        file_path = self._file_paths.get(policy_id, policy_id)
        pages = [
            (page_number, markdown)
            for page_number, markdown in enumerate(
                facade.extract_markdown(file_path, MAX_PAGES), start=1
            )
        ]
        for page_number, markdown in pages:
            self._repo.upsert_markdown_page(policy_id, page_number, markdown, fingerprint)
        return pages

    def _resolve_facade(self):
        if self._document_facade is not None:
            return self._document_facade
        # Lazy e exclusivamente pela fachada pública (RF-01) — mesmo padrão do
        # adaptador de evidências, único ponto que fala com `document_processing`.
        from .document_processing_source import DocumentProcessingEvidenceSource

        self._document_facade = DocumentProcessingEvidenceSource()._resolve_facade()
        return self._document_facade

    # --- seleção de evidências ------------------------------------------------

    def get_evidences(self, policy_id: str, field_code: str | None = None) -> list[EvidenceRef]:
        """Seções como evidências: ranqueadas por campo ou em ordem de leitura."""
        sections = self.get_sections(policy_id)
        if field_code is not None:
            from ..domain.field_catalog import get_field

            spec = get_field(field_code)
            query_terms = _terms(f"{spec.label} {spec.description}")
            scores = {section: _overlap_score(section, query_terms) for section in sections}
            ranked = sorted(
                sections,
                key=lambda section: (-scores[section], section.page_number, section.index),
            )
            return [
                self._to_evidence(policy_id, section, scores[section])
                for section in ranked[: self._top_sections]
            ]
        return [self._to_evidence(policy_id, section) for section in sections[:MAX_SECTIONS]]

    def _to_evidence(
        self, policy_id: str, section: MarkdownSectionRef, score: float | None = None
    ) -> EvidenceRef:
        text = section.text
        if len(text) > MAX_QUOTED_CHARS:
            text = text[:MAX_QUOTED_CHARS] + "…"
        return EvidenceRef(
            evidence_id=f"ev_md_{policy_id}:p{section.page_number}:s{section.index}",
            policy_id=policy_id,
            document_id=policy_id,
            page_number=section.page_number,
            section_name=section.title,
            quoted_text=text,
            retrieval_score=score,
            source_type=SECTION_SOURCE_TYPE,
        )


def _overlap_score(section: MarkdownSectionRef, query_terms: set[str]) -> float:
    """Fração dos termos da consulta presentes no título+corpo da seção (0..1)."""
    if not query_terms:
        return 0.0
    section_terms = _terms(f"{section.title or ''} {section.text}")
    return len(query_terms & section_terms) / len(query_terms)
