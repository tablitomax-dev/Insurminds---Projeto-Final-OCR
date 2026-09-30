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
    from modules.policy_analysis.domain.models import ComparisonResult, FieldComparison
    from modules.policy_analysis.infrastructure.duckdb_repository import (
        PolicyAnalysisRepository,
    )
    from shared_kernel.contracts import ExtractedFact

    repository = PolicyAnalysisRepository(str(tmp_path / "policy_analysis.duckdb"))
    repository.init_schema()  # schema auto-criado é idempotente

    repository.upsert_policy(
        {
            "policy_id": "pol_a",
            "seguradora": "Acme Seguros",
            "vigencia_inicio": "2026-01-01",
            "vigencia_fim": "2026-12-31",
            "fonte_documentos": "sintética",
        }
    )
    repository.upsert_document(
        {"document_id": "doc_1", "policy_id": "pol_a", "nome_fonte": "apolice_a.pdf"}
    )
    repository.upsert_policy(
        {
            "policy_id": "pol_a",
            "seguradora": "Acme Seguros",
            "vigencia_inicio": "2026-01-01",
            "vigencia_fim": "2026-12-31",
            "fonte_documentos": "sintética",
        }
    )  # idempotente por policy_id
    repository.upsert_document(
        {"document_id": "doc_1", "policy_id": "pol_a", "nome_fonte": "apolice_a.pdf"}
    )  # idempotente por document_id

    fact = ExtractedFact(
        fact_id="FAC-pol_a-limite_agregado",
        policy_id="pol_a",
        field_code="limite_agregado",
        status="FOUND",
        value={"amount": 900_000.0, "currency": "BRL"},
        normalized_value={"amount": "900000.00", "currency": "BRL"},
        confidence=0.9,
        evidence_ids=["ev_1"],
        requires_human_review=True,
    )
    repository.upsert_fact(fact, run_id="run_1", schema_version="1.0")
    repository.upsert_fact(fact, run_id="run_1", schema_version="1.0")  # idempotente

    facts = repository.get_facts("pol_a")
    assert [item.field_code for item in facts] == ["limite_agregado"]
    assert facts[0] == fact
    assert repository.get_facts("pol_a", "franquia") == []

    # fila de revisão com o fato pendente e registro da decisão humana
    items = repository.get_review_items("pol_a")
    assert [item.fact.fact_id for item in items] == ["FAC-pol_a-limite_agregado"]
    assert items[0].revisao_status == "PENDENTE"
    repository.record_review(
        "FAC-pol_a-limite_agregado",
        "CORRIGIDO",
        {"decisao": "CORRIGIDO", "value": None},
        "ana",
        "2026-09-29T12:00:00Z",
        requires_human_review=False,
    )
    reviewed = repository.get_review_item("FAC-pol_a-limite_agregado")
    assert reviewed.revisao_status == "CORRIGIDO"
    assert reviewed.revisao_por == "ana"
    assert repository.get_review_items("pol_a")[0].revisao_status == "CORRIGIDO"

    # comparação idempotente por comparison_id (DELETE+INSERT em transação)
    result = ComparisonResult(
        comparison_id="cmp_1",
        policy_id_a="pol_a",
        policy_id_b="pol_b",
        campos=(
            FieldComparison(
                field_code="limite_agregado",
                resultado="MAIOR",
                valor_a={"amount": "900000.00", "currency": "BRL"},
                valor_b=None,
                direcao="A",
                evidencias_a=("ev_1",),
                evidencias_b=(),
                explicacao="A supera B.",
            ),
        ),
    )
    repository.upsert_comparison(result)
    repository.upsert_comparison(result)  # idempotente
    stored = repository.get_comparison("cmp_1")
    assert stored == result
    assert repository.get_comparison("cmp_inexistente") is None


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
