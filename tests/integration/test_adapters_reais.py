"""Testes de integração dos adapters reais (T018) — marcados `integration`.

Rodam apenas quando a dependência está instalada; caso contrário são
pulados graciosamente (D-10 do roadmap).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def test_duckdb_repository_idempotente(tmp_path):
    pytest.importorskip("duckdb", reason="duckdb não instalado")
    from fakes.policy_analysis import make_evidence, make_fact
    from modules.policy_analysis.infrastructure.duckdb_repository import DuckDbFactRepository

    repository = DuckDbFactRepository(str(tmp_path / "facts.duckdb"))
    fact = make_fact("pol_a", "limite_agregado", value={"amount": 1.0}, evidence_ids=["ev_1"])
    repository.save_evidence(make_evidence("ev_1", policy_id="pol_a"))
    repository.upsert_fact(fact)
    repository.upsert_fact(fact)  # idempotente por (policy_id, field_code)

    facts = repository.get_facts("pol_a")
    assert [item.field_code for item in facts] == ["limite_agregado"]
    assert repository.get_evidence("ev_1") is not None
    assert repository.get_fact("pol_a", "limite_agregado") is not None
    assert repository.get_fact("pol_a", "franquia") is None


def test_pymupdf_extrai_texto_por_pagina(tmp_path):
    fitz = pytest.importorskip("fitz", reason="PyMuPDF não instalado")
    from modules.document_processing.infrastructure.extractors import PyMuPdfTextExtractor

    pdf_path = tmp_path / "amostra.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Limite Agregado: R$ 1.000.000,00")
    document.save(str(pdf_path))
    document.close()

    pages = PyMuPdfTextExtractor().extract_pages(str(pdf_path))
    assert pages[0].page_number == 1
    assert "Limite Agregado" in pages[0].text


@pytest.mark.skipif(
    os.environ.get("INTEGRATION_QDRANT_URL") is None,
    reason="defina INTEGRATION_QDRANT_URL para testar o Qdrant real",
)
def test_qdrant_roundtrip_basico():
    pytest.importorskip("qdrant_client", reason="qdrant-client não instalado")
    from modules.document_processing.domain.processing import ChunkRecord, build_chunk_metadata
    from modules.document_processing.infrastructure.indexing import QdrantVectorIndex

    alvo = os.environ["INTEGRATION_QDRANT_URL"]
    if alvo == ":memory:":
        # Modo embutido do qdrant-client: cliente real, sem servidor (offline).
        from qdrant_client import QdrantClient

        index = QdrantVectorIndex(vector_size=8, client=QdrantClient(":memory:"))
    else:
        index = QdrantVectorIndex(url=alvo, vector_size=8)
    metadata = build_chunk_metadata(
        chunk_id="doc_it:p1:c0",
        document_id="doc_it",
        policy_id="pol_it",
        page_number=1,
        chunk_index=0,
        source_type="NATIVE_TEXT",
        ocr_confidence=None,
    )
    record = ChunkRecord(metadata=metadata, text="texto de integração", vector=[0.1] * 8)
    index.ensure_collection()
    index.delete_document("doc_it")
    index.upsert_chunks([record])
    results = index.search([0.1] * 8, top_k=3, policy_id="pol_it")
    assert results and results[0].record.metadata.chunk_id == "doc_it:p1:c0"
    index.delete_document("doc_it")


@pytest.mark.skipif(
    os.environ.get("GEMINI_API_KEY") is None and os.environ.get("GOOGLE_API_KEY") is None,
    reason="defina GEMINI_API_KEY para testar embeddings reais",
)
def test_gemini_embedder_gera_vetores():
    from modules.document_processing.infrastructure.indexing import GeminiEmbedder

    embedder = GeminiEmbedder(output_dimensionality=8)
    vectors = embedder.embed_texts(["limite agregado da apólice"])
    assert len(vectors) == 1 and len(vectors[0]) == 8
