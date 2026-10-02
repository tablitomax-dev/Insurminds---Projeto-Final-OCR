"""Testes do domínio puro: chunking, classificação de página e metadados (RF-02..RF-04)."""

from modules.document_processing.domain.processing import (
    CHUNK_MAX_CHARS,
    CHUNK_OVERLAP,
    MIN_NATIVE_TEXT_CHARS,
    OCR_ILLEGIBLE_CONFIDENCE,
    build_chunk_metadata,
    chunk_text,
    classify_page,
    is_illegible,
)
from shared_kernel.version import CONTRACTS_VERSION

# --- dev1-006: section_name no metadado (OQ-03 resolvida) -------------------


def test_build_chunk_metadata_section_name_recebe_literal():
    metadata = build_chunk_metadata(
        chunk_id="doc-1:p1:c0",
        document_id="doc-1",
        policy_id="pol-1",
        page_number=1,
        chunk_index=0,
        source_type="NATIVE_TEXT",
        ocr_confidence=None,
        section_name="Cláusula 5ª — FRANQUIA",
    )

    assert metadata.section_name == "Cláusula 5ª — FRANQUIA"


def test_build_chunk_metadata_default_section_name_none():
    metadata = build_chunk_metadata(
        chunk_id="doc-1:p1:c0",
        document_id="doc-1",
        policy_id="pol-1",
        page_number=1,
        chunk_index=0,
        source_type="NATIVE_TEXT",
        ocr_confidence=None,
    )

    assert metadata.section_name is None


def test_chunk_text_splits_long_text_with_overlap():
    chunks = chunk_text("a" * 900)

    assert len(chunks) == 2
    assert len(chunks[0]) == CHUNK_MAX_CHARS
    assert len(chunks[1]) == 900 - (CHUNK_MAX_CHARS - CHUNK_OVERLAP)
    assert chunks[1][:CHUNK_OVERLAP] == chunks[0][-CHUNK_OVERLAP:]


def test_chunk_text_short_text_yields_single_chunk():
    assert chunk_text("x" * 100) == ["x" * 100]
    assert chunk_text("a" * CHUNK_MAX_CHARS) == ["a" * CHUNK_MAX_CHARS]


def test_chunk_text_never_returns_empty_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []
    for size in (1, 39, 799, 800, 801, 1500, 2201):
        chunks = chunk_text("b" * size)
        assert chunks
        assert all(chunk for chunk in chunks)


def test_chunk_text_respects_custom_limits():
    chunks = chunk_text("c" * 25, max_chars=10, overlap=2)

    assert [len(chunk) for chunk in chunks] == [10, 10, 9]
    assert chunks[1][:2] == chunks[0][-2:]


def test_classify_page_threshold():
    assert classify_page("x" * (MIN_NATIVE_TEXT_CHARS - 1)) == "PADDLEOCR"
    assert classify_page("x" * MIN_NATIVE_TEXT_CHARS) == "NATIVE_TEXT"
    assert classify_page("  " + "x" * (MIN_NATIVE_TEXT_CHARS - 1) + "  ") == "PADDLEOCR"


def test_is_illegible_threshold():
    assert is_illegible(OCR_ILLEGIBLE_CONFIDENCE - 0.01) is True
    assert is_illegible(OCR_ILLEGIBLE_CONFIDENCE) is False
    assert is_illegible(0.9) is False
    assert is_illegible(None) is False


def test_build_chunk_metadata_matches_contract():
    metadata = build_chunk_metadata(
        chunk_id="doc-1:p1:c0",
        document_id="doc-1",
        policy_id="pol-1",
        page_number=1,
        chunk_index=0,
        source_type="PADDLEOCR",
        ocr_confidence=0.87,
    )

    assert metadata.chunk_id == "doc-1:p1:c0"
    assert metadata.document_id == "doc-1"
    assert metadata.policy_id == "pol-1"
    assert metadata.page_number == 1
    assert metadata.chunk_index == 0
    assert metadata.source_type == "PADDLEOCR"
    assert metadata.ocr_confidence == 0.87
    assert metadata.section_name is None
    assert metadata.metadata_version == CONTRACTS_VERSION


def test_build_chunk_metadata_native_page_has_no_ocr_confidence():
    metadata = build_chunk_metadata(
        chunk_id="doc-1:p2:c1",
        document_id="doc-1",
        policy_id="pol-1",
        page_number=2,
        chunk_index=1,
        source_type="NATIVE_TEXT",
        ocr_confidence=None,
    )

    assert metadata.source_type == "NATIVE_TEXT"
    assert metadata.ocr_confidence is None
    assert metadata.metadata_version == CONTRACTS_VERSION
