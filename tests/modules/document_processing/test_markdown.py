"""Markdown estruturado: seções ATX e extração por página com cache compartilhado.

Caminho novo de saída: o motor de layout (PP-StructureV3) também devolve
markdown nativo por página — extraído UMA vez, com cache por instância do
serviço, eliminando o OCR duplicado entre preview e processamento.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from fakes.document_processing import (
    FakeEmbedder,
    FakeLayoutEngine,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from modules.document_processing.application.ports import LayoutError
from modules.document_processing.application.service import DocumentProcessingService
from modules.document_processing.domain.processing import PageText
from modules.document_processing.domain.structure import (
    MarkdownSection,
    split_markdown_sections,
)
from modules.document_processing.public_api import create_document_processing

#: Página com texto nativo suficiente (>= 40 caracteres não-brancos).
NATIVE_PAGE = "A apólice D&O garante cobertura para atos administrativos e defesa jurídica dos segurados."

#: Página "escaneada": texto nativo curto, classificada para OCR.
SCANNED_PAGE = "logo da seguradora"


class FakeMarkdownLayoutEngine(FakeLayoutEngine):
    """Fake de motor de layout com markdown nativo por página (duck-typed)."""

    def __init__(
        self,
        markdown_by_page: dict[int, str] | None = None,
        markdown_error: Exception | None = None,
        regions_by_page: dict[int, list] | None = None,
    ) -> None:
        super().__init__(regions_by_page=regions_by_page)
        self.markdown_by_page = dict(markdown_by_page or {})
        self.markdown_error = markdown_error
        self.markdown_calls: list[tuple[str, int]] = []

    def analyze_page_markdown(self, file_path: str, page_number: int) -> str | None:
        self.markdown_calls.append((file_path, page_number))
        if self.markdown_error is not None:
            raise self.markdown_error
        return self.markdown_by_page.get(page_number)


def _service(pages, ocr=None, layout_engine=None):
    extractor = FakeTextExtractor(default_pages=list(pages))
    ocr_engine = ocr or FakeOcrEngine()
    service = DocumentProcessingService(
        extractor,
        ocr_engine,
        FakeEmbedder(),
        InMemoryVectorIndex(),
        RecordingStatusSink(),
        layout_engine=layout_engine,
    )
    return service, ocr_engine


# ------------------------------- split_markdown_sections


def test_pre_amulo_sem_titulo_antes_do_primeiro_heading():
    sections = split_markdown_sections(
        "texto livre inicial\n\n# Título\ncorpo da seção", page_number=3
    )

    assert [(section.title, section.body) for section in sections] == [
        (None, "texto livre inicial"),
        ("Título", "corpo da seção"),
    ]
    assert all(section.page_number == 3 for section in sections)


def test_multiplos_headings_em_ordem_de_leitura_com_index_sequencial():
    markdown = (
        "# Capítulo\n"
        "texto do capítulo\n"
        "## Seção\n"
        "texto da seção\n"
        "### Subseção\n"
        "texto da sub"
    )

    sections = split_markdown_sections(markdown, page_number=1)

    assert [(s.index, s.title, s.body) for s in sections] == [
        (0, "Capítulo", "texto do capítulo"),
        (1, "Seção", "texto da seção"),
        (2, "Subseção", "texto da sub"),
    ]


def test_corpos_vazios_sao_descartados_mesmo_com_titulo():
    markdown = "# A\n\n# B\ncorpo B\n\n# C\n\n"

    sections = split_markdown_sections(markdown, page_number=2)

    assert [(s.title, s.body) for s in sections] == [("B", "corpo B")]


def test_sem_heading_vira_so_o_pre_ambulo_e_vazio_devolve_lista_vazia():
    sections = split_markdown_sections("texto corrido sem heading", page_number=1)

    assert [(s.title, s.body) for s in sections] == [(None, "texto corrido sem heading")]
    assert split_markdown_sections("   \n\n", page_number=1) == []


def test_secoes_sao_imutaveis():
    section = MarkdownSection(title="Título", body="corpo", page_number=1, index=0)

    with pytest.raises(FrozenInstanceError):
        section.title = "outro"  # type: ignore[misc]


# ------------------------------- extract_markdown_pages


def test_extract_markdown_pages_usa_markdown_do_engine_quando_disponivel():
    engine = FakeMarkdownLayoutEngine(markdown_by_page={1: "# Título\n\ncorpo do markdown"})
    service, ocr = _service([PageText(1, SCANNED_PAGE)], layout_engine=engine)

    pages = service.extract_markdown_pages("apolice.pdf")

    assert [(p.page_number, p.markdown, p.source_type) for p in pages] == [
        (1, "# Título\n\ncorpo do markdown", "PP_STRUCTURE")
    ]
    # Markdown do engine substitui até o OCR: nada de OCR duplicado.
    assert ocr.calls == []
    assert engine.markdown_calls == [("apolice.pdf", 1)]


def test_sem_engine_cai_para_texto_nativo():
    service, ocr = _service([PageText(1, NATIVE_PAGE)])

    pages = service.extract_markdown_pages("apolice.pdf")

    assert [(p.markdown, p.source_type) for p in pages] == [(NATIVE_PAGE, "NATIVE_TEXT")]
    assert ocr.calls == []


def test_sem_engine_cai_para_ocr_quando_nativo_insuficiente():
    ocr = FakeOcrEngine(results_by_page={1: ("texto do ocr da página", 0.9)})
    service, _ocr = _service([PageText(1, SCANNED_PAGE)], ocr=ocr)

    pages = service.extract_markdown_pages("apolice.pdf")

    assert [(p.markdown, p.source_type) for p in pages] == [
        ("texto do ocr da página", "PADDLEOCR")
    ]
    assert ocr.calls == [("apolice.pdf", 1)]


def test_engine_falha_ou_devolve_none_degrada_para_o_texto_disponivel():
    engine_falho = FakeMarkdownLayoutEngine(markdown_error=LayoutError("falha (RuntimeError)"))
    service_falha, _ = _service([PageText(1, NATIVE_PAGE)], layout_engine=engine_falho)
    engine_vazio = FakeMarkdownLayoutEngine(markdown_by_page={})
    service_vazio, ocr_vazio = _service(
        [PageText(1, SCANNED_PAGE)], ocr=FakeOcrEngine(), layout_engine=engine_vazio
    )

    pages_falha = service_falha.extract_markdown_pages("apolice.pdf")
    pages_vazio = service_vazio.extract_markdown_pages("apolice.pdf")

    # Falha do motor nunca derruba o fluxo (RN-05): cai para nativo/OCR.
    assert [(p.markdown, p.source_type) for p in pages_falha] == [(NATIVE_PAGE, "NATIVE_TEXT")]
    assert [(p.markdown, p.source_type) for p in pages_vazio] == [
        ("texto ocr extraído da página", "PADDLEOCR")
    ]
    assert ocr_vazio.calls == [("apolice.pdf", 1)]


def test_engine_so_com_analyze_page_tambem_e_valido_pelo_duck_typing():
    # FakeLayoutEngine "antigo": só tem `analyze_page`, sem `analyze_page_markdown`.
    engine = FakeLayoutEngine()
    service, ocr = _service([PageText(1, SCANNED_PAGE)], ocr=FakeOcrEngine(), layout_engine=engine)

    pages = service.extract_markdown_pages("apolice.pdf")

    assert [(p.markdown, p.source_type) for p in pages] == [
        ("texto ocr extraído da página", "PADDLEOCR")
    ]
    assert ocr.calls == [("apolice.pdf", 1)]


# ------------------------------- cache compartilhado (OCR roda uma vez)


def test_cache_ocr_roda_uma_vez_entre_markdown_e_preview():
    ocr = FakeOcrEngine(
        results_by_page={1: ("PORTO SEGURO", 0.9), 2: ("condições gerais", 0.8)}
    )
    service, _ = _service(
        [PageText(1, SCANNED_PAGE), PageText(2, "sumário da apólice")], ocr=ocr
    )

    markdowns = service.extract_markdown_pages("apolice.pdf")
    preview = service.extract_preview_pages("apolice.pdf", max_pages=2)

    # O OCR roda UMA vez por página: preview reaproveita o cache do markdown.
    assert ocr.calls == [("apolice.pdf", 1), ("apolice.pdf", 2)]
    assert [p.markdown for p in markdowns] == ["PORTO SEGURO", "condições gerais"]
    # O formato do preview é preservado (blocos [OCR/visão] e [texto nativo]).
    assert preview == [
        "[OCR/visão]\nPORTO SEGURO\n[texto nativo]\nlogo da seguradora",
        "[OCR/visão]\ncondições gerais\n[texto nativo]\nsumário da apólice",
    ]


def test_cache_de_markdown_evita_novo_olhar_do_engine():
    engine = FakeMarkdownLayoutEngine(markdown_by_page={1: "markdown estável"})
    service, _ = _service([PageText(1, SCANNED_PAGE)], layout_engine=engine)

    primeira = service.extract_markdown_pages("apolice.pdf")
    segunda = service.extract_markdown_pages("apolice.pdf")

    assert [p.markdown for p in primeira] == [p.markdown for p in segunda] == ["markdown estável"]
    assert engine.markdown_calls == [("apolice.pdf", 1)]


# ------------------------------- max_pages e fachada


def test_max_pages_limita_a_saida():
    service, ocr = _service(
        [PageText(1, SCANNED_PAGE), PageText(2, "sumário"), PageText(3, "página três")]
    )

    pages = service.extract_markdown_pages("apolice.pdf", max_pages=2)

    assert [p.page_number for p in pages] == [1, 2]
    assert ocr.calls == [("apolice.pdf", 1), ("apolice.pdf", 2)]
    assert len(service.extract_markdown_pages("apolice.pdf")) == 3


def test_fachada_extract_markdown_devolve_markdown_por_pagina():
    ocr = FakeOcrEngine(results_by_page={1: ("texto do ocr", 0.9)})
    facade = create_document_processing(
        text_extractor=FakeTextExtractor(default_pages=[PageText(1, SCANNED_PAGE)]),
        ocr_engine=ocr,
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        status_sink=RecordingStatusSink(),
    )

    assert facade.extract_markdown("apolice.pdf") == ["texto do ocr"]