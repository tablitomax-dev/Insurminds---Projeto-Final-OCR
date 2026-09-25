"""RF-06: ChunkMetadata — proposta da spec (OQ-01), contrato versionado."""

import pytest
from pydantic import ValidationError

from shared_kernel.contracts import ChunkMetadata


def _base_metadata(**overrides) -> dict:
    data = {
        "chunk_id": "chunk-0001",
        "document_id": "doc-0001",
        "policy_id": "policy-0001",
        "page_number": 7,
        "chunk_index": 23,
        "source_type": "NATIVE_TEXT",
        "ocr_confidence": None,
        "section_name": None,
        "metadata_version": "1.0.0",
    }
    data.update(overrides)
    return data


def test_valid_fixture(load):
    chunk = ChunkMetadata(**load("chunk_metadata.json"))
    assert chunk.chunk_index == 23
    assert chunk.metadata_version == "1.0.0"
    assert chunk.ocr_confidence == 0.93


def test_chunk_index_zero_is_valid():
    chunk = ChunkMetadata(**_base_metadata(chunk_index=0))
    assert chunk.chunk_index == 0


def test_negative_chunk_index_rejected():
    with pytest.raises(ValidationError):
        ChunkMetadata(**_base_metadata(chunk_index=-1))


def test_invalid_page_rejected(load):
    with pytest.raises(ValidationError):
        ChunkMetadata(**load("invalid/chunk_metadata_invalid_page.json"))


def test_metadata_version_required():
    data = _base_metadata()
    data.pop("metadata_version")
    with pytest.raises(ValidationError):
        ChunkMetadata(**data)


def test_unknown_field_rejected():
    # zona de integração 2: nomenclatura divergente deve falhar aqui
    with pytest.raises(ValidationError):
        ChunkMetadata(**_base_metadata(doc_id="doc-0001"))
