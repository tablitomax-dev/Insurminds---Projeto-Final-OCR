"""Teste de contrato por parâmetro de `RetrievalQuery` (F-14, D1-P0-2).

Para CADA campo de `RetrievalQuery` um teste prova que o campo chega à porta
`VectorIndex.search` (spy gravando a chamada) e é consumido — o teste falha se
qualquer filtro voltar a ser descartado em silêncio.
"""

from fakes.document_processing import (
    FakeEmbedder,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from modules.document_processing.application.service import (
    FIELD_CODE_HINT_TEMPLATE,
    DocumentProcessingService,
    compose_search_text,
)
from modules.document_processing.domain.processing import ChunkRecord, build_chunk_metadata
from shared_kernel.contracts import RetrievalQuery

TEXT_COBERTURA = "Cobertura para atos administrativos dos segurados da apólice D&O."
TEXT_FRANQUIA = "Franquia de R$ 10.000,00 por sinistro a cargo do segurado."


def _record(chunk_id, policy_id, document_id, text, section_name=None):
    metadata = build_chunk_metadata(
        chunk_id=chunk_id,
        document_id=document_id,
        policy_id=policy_id,
        page_number=1,
        chunk_index=0,
        source_type="NATIVE_TEXT",
        ocr_confidence=None,
    )
    if section_name is not None:
        metadata = metadata.model_copy(update={"section_name": section_name})
    return ChunkRecord(metadata=metadata, text=text)


def _stack(records):
    """Serviço com índice em memória populado + spies (embedder e busca)."""
    embedder = FakeEmbedder()
    index = InMemoryVectorIndex()
    for record in records:
        record.vector = embedder.embed_texts([record.text])[0]
    index.upsert_chunks(records)
    embedder.calls.clear()
    service = DocumentProcessingService(
        FakeTextExtractor(), FakeOcrEngine(), embedder, index, RecordingStatusSink()
    )
    return service, embedder, index


# ---------------------------------------------------------- campo: query


def test_query_reaches_search_as_the_embedded_vector():
    service, embedder, index = _stack([_record("doc-1:p1:c0", "pol-1", "doc-1", TEXT_COBERTURA)])

    service.retrieve_evidence(RetrievalQuery(query="cobertura administrativa", top_k=3))

    # o texto da consulta é o que vai para a porta de embeddings e o vetor
    # resultante é o que chega à porta `VectorIndex.search`
    assert embedder.calls == [["cobertura administrativa"]]
    assert index.search_calls[0]["vector"] == embedder.embed_texts(["cobertura administrativa"])[0]


def test_different_query_yields_different_vector_at_the_port():
    service, _embedder, index = _stack([_record("doc-1:p1:c0", "pol-1", "doc-1", TEXT_COBERTURA)])

    service.retrieve_evidence(RetrievalQuery(query="cobertura", top_k=3))
    service.retrieve_evidence(RetrievalQuery(query="franquia", top_k=3))

    assert index.search_calls[0]["vector"] != index.search_calls[1]["vector"]


# ---------------------------------------------------------- campo: top_k


def test_top_k_reaches_search_and_limits_results():
    records = [_record(f"doc-1:p1:c{i}", "pol-1", "doc-1", TEXT_COBERTURA) for i in range(5)]
    service, _embedder, index = _stack(records)

    result = service.retrieve_evidence(RetrievalQuery(query="cobertura", top_k=2))

    assert index.search_calls[0]["top_k"] == 2
    assert len(result.evidences) == 2  # consumido: limita de fato o resultado


# ------------------------------------------------------ campo: policy_id


def test_policy_id_reaches_search_and_filters_results():
    records = [
        _record("doc-a:p1:c0", "pol-a", "doc-a", TEXT_COBERTURA),
        _record("doc-b:p1:c0", "pol-b", "doc-b", TEXT_FRANQUIA),
    ]
    service, _embedder, index = _stack(records)

    result = service.retrieve_evidence(
        RetrievalQuery(query="cobertura", top_k=5, policy_id="pol-a")
    )

    assert index.search_calls[0]["policy_id"] == "pol-a"
    assert {evidence.policy_id for evidence in result.evidences} == {"pol-a"}


# ---------------------------------------------------- campo: document_id


def test_document_id_reaches_search_and_filters_results():
    records = [
        _record("doc-a:p1:c0", "pol-1", "doc-a", TEXT_COBERTURA),
        _record("doc-b:p1:c0", "pol-1", "doc-b", TEXT_FRANQUIA),
    ]
    service, _embedder, index = _stack(records)

    result = service.retrieve_evidence(
        RetrievalQuery(query="cobertura", top_k=5, document_id="doc-b")
    )

    assert index.search_calls[0]["document_id"] == "doc-b"
    assert {evidence.document_id for evidence in result.evidences} == {"doc-b"}


# ---------------------------------------------------- campo: section_name


def test_section_name_reaches_search_and_filters_results():
    records = [
        _record("doc-1:p1:c0", "pol-1", "doc-1", TEXT_COBERTURA, section_name="Coberturas"),
        _record("doc-1:p1:c1", "pol-1", "doc-1", TEXT_FRANQUIA, section_name="Franquias"),
    ]
    service, _embedder, index = _stack(records)

    result = service.retrieve_evidence(
        RetrievalQuery(query="cobertura", top_k=5, section_name="Franquias")
    )

    # chega à porta e é consumido como filtro de metadata na consulta
    assert index.search_calls[0]["section_name"] == "Franquias"
    assert [evidence.chunk_id for evidence in result.evidences] == ["doc-1:p1:c1"]


# ------------------------------------------------------ campo: field_code


def test_field_code_reaches_search_and_shapes_query_text():
    service, embedder, index = _stack([_record("doc-1:p1:c0", "pol-1", "doc-1", TEXT_COBERTURA)])

    service.retrieve_evidence(
        RetrievalQuery(query="limite máximo", top_k=3, field_code="limite_agregado")
    )

    # chega explícito à porta (nunca descartado em silêncio)...
    assert index.search_calls[0]["field_code"] == "limite_agregado"
    # ...e é consumido como hint determinístico no texto de busca (D1-P0-2)
    assert embedder.calls == [["limite máximo" + FIELD_CODE_HINT_TEMPLATE.format(
        field_code="limite_agregado"
    )]]


def test_field_code_changes_the_vector_that_reaches_the_port():
    service, _embedder, index = _stack([_record("doc-1:p1:c0", "pol-1", "doc-1", TEXT_COBERTURA)])

    service.retrieve_evidence(RetrievalQuery(query="limite", top_k=3, field_code="limite_agregado"))
    service.retrieve_evidence(RetrievalQuery(query="limite", top_k=3, field_code="franquia"))

    # consumo com efeito na busca: field_code diferente => vetor de busca diferente
    assert index.search_calls[0]["vector"] != index.search_calls[1]["vector"]


def test_compose_search_text_is_deterministic():
    hint = FIELD_CODE_HINT_TEMPLATE.format(field_code="limite_agregado")

    assert compose_search_text("consulta", "limite_agregado") == "consulta" + hint
    assert compose_search_text("consulta", "limite_agregado") == compose_search_text(
        "consulta", "limite_agregado"
    )
    assert compose_search_text("consulta", None) == "consulta"
    assert compose_search_text("consulta", "") == "consulta"


# --------------------------------------------- todos os campos de uma vez


def test_every_retrieval_query_field_reaches_the_port():
    fields = {
        "query": "limite máximo indenizável",
        "policy_id": "pol-1",
        "document_id": "doc-1",
        "section_name": "Coberturas",
        "field_code": "limite_agregado",
        "top_k": 7,
    }
    service, embedder, index = _stack([_record("doc-1:p1:c0", "pol-1", "doc-1", TEXT_COBERTURA)])

    service.retrieve_evidence(RetrievalQuery(**fields))

    call = index.search_calls[0]
    assert call["policy_id"] == fields["policy_id"]
    assert call["document_id"] == fields["document_id"]
    assert call["section_name"] == fields["section_name"]
    assert call["field_code"] == fields["field_code"]
    assert call["top_k"] == fields["top_k"]
    assert fields["query"] in embedder.calls[0][0]
    assert fields["field_code"] in embedder.calls[0][0]
