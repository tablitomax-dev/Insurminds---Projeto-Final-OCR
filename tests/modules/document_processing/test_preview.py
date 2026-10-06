"""Preview de páginas: OCR/visão sempre primeiro, com marcador de origem."""

from __future__ import annotations

from fakes.document_processing import (
    FakeEmbedder,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from modules.document_processing.domain.processing import PageText
from modules.document_processing.public_api import create_document_processing


def _facade(text_extractor, ocr_engine):
    return create_document_processing(
        text_extractor=text_extractor,
        ocr_engine=ocr_engine,
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        status_sink=RecordingStatusSink(),
    )


def test_preview_roda_ocr_mesmo_com_texto_nativo():
    facade = _facade(
        FakeTextExtractor(default_pages=[PageText(1, "texto nativo da página")]),
        FakeOcrEngine(results_by_page={1: ("PORTO SEGURO", 0.9)}),
    )
    pages = facade.extract_preview("qualquer.pdf", max_pages=2)
    assert pages == [
        "[OCR/visão]\nPORTO SEGURO\n[texto nativo]\ntexto nativo da página"
    ]


def test_preview_degrada_quando_o_ocr_falha():
    ocr = FakeOcrEngine(default_result=("", None))
    ocr.error = RuntimeError("ocr fora do ar")
    facade = _facade(FakeTextExtractor(default_pages=[PageText(1, "só nativo")]), ocr)
    pages = facade.extract_preview("qualquer.pdf", max_pages=2)
    assert pages == ["[texto nativo]\nsó nativo"]


def test_preview_limita_a_quantidade_de_paginas():
    facade = _facade(
        FakeTextExtractor(
            default_pages=[PageText(1, "p1"), PageText(2, "p2"), PageText(3, "p3")]
        ),
        FakeOcrEngine(default_result=("", None)),
    )
    pages = facade.extract_preview("qualquer.pdf", max_pages=2)
    assert len(pages) == 2
