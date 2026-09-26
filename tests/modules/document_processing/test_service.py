"""Testes do serviço de processamento: orquestração, status, idempotência e retrieval (RF-01..RF-09)."""

import pytest

from fakes.document_processing import (
    FakeEmbedder,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from modules.document_processing.application.ports import ScoredChunk
from modules.document_processing.application.service import DocumentProcessingService
from modules.document_processing.domain.processing import ChunkRecord, PageText, build_chunk_metadata
from shared_kernel.contracts import RetrievalQuery
from shared_kernel.version import CONTRACTS_VERSION

NATIVE_PAGE = "A apólice D&O garante cobertura para atos administrativos e defesa jurídica dos segurados."
MULTI_CHUNK_PAGE = "A apólice D&O cobre limites de responsabilidade e defesa jurídica. " * 30
OCR_TEXT = "texto reconhecido pelo ocr da página escaneada com conteúdo suficiente"


def _write_pdf(tmp_path, name="apolice.pdf", content=b"%PDF-1.4\nconteudo fake\n"):
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def _build_service(pages_by_path=None, max_pdf_bytes=None):
    extractor = FakeTextExtractor(pages_by_path=pages_by_path)
    ocr_engine = FakeOcrEngine()
    embedder = FakeEmbedder()
    index = InMemoryVectorIndex()
    sink = RecordingStatusSink()
    kwargs = {}
    if max_pdf_bytes is not None:
        kwargs["max_pdf_bytes"] = max_pdf_bytes
    service = DocumentProcessingService(
        extractor, ocr_engine, embedder, index, sink, **kwargs
    )
    return service, extractor, ocr_engine, embedder, index, sink


# ---------------------------------------------------------------- happy path


def test_happy_path_native_pages_publishes_stages_and_indexes_chunks(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, ocr, _embedder, index, sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE), PageText(2, NATIVE_PAGE)]}
    )

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "INDEXED"
    assert status.progress == 1.0
    assert [s.stage for s in sink.statuses] == ["RECEIVED", "TEXT_EXTRACTED", "INDEXED"]
    assert ocr.calls == []
    assert index.delete_calls == ["doc-1"]

    records = index.records
    assert records
    for record in records:
        metadata = record.metadata
        assert metadata.document_id == "doc-1"
        assert metadata.policy_id == "pol-1"
        assert metadata.chunk_id == f"doc-1:p{metadata.page_number}:c{metadata.chunk_index}"
        assert metadata.page_number in (1, 2)
        assert metadata.source_type == "NATIVE_TEXT"
        assert metadata.ocr_confidence is None
        assert metadata.metadata_version == CONTRACTS_VERSION
        assert record.text


def test_pages_without_native_text_go_to_ocr(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, ocr, _embedder, index, sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE), PageText(2, "curta")]}
    )
    ocr.results_by_page[2] = (OCR_TEXT, 0.87)

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "INDEXED"
    assert [s.stage for s in sink.statuses] == [
        "RECEIVED",
        "TEXT_EXTRACTED",
        "OCR_COMPLETED",
        "INDEXED",
    ]
    assert ocr.calls == [(file_path, 2)]

    by_page = {record.metadata.page_number: record.metadata for record in index.records}
    assert by_page[1].source_type == "NATIVE_TEXT"
    assert by_page[1].ocr_confidence is None
    assert by_page[2].source_type == "PADDLEOCR"
    assert by_page[2].ocr_confidence == 0.87


# ------------------------------------------------------- arquivo inválido


@pytest.mark.parametrize("case", ["missing", "wrong_extension", "bad_header"])
def test_invalid_file_fails_with_extract_and_indexes_nothing(tmp_path, case):
    if case == "missing":
        file_path = str(tmp_path / "inexistente.pdf")
    elif case == "wrong_extension":
        file_path = _write_pdf(tmp_path, name="apolice.txt")
    else:
        file_path = _write_pdf(
            tmp_path, name="corrompido.pdf", content=b"conteudo sem cabecalho pdf"
        )

    service, extractor, _ocr, _embedder, index, sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE)]}
    )

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "FAILED"
    assert status.progress == 0.0
    assert status.message == "EXTRACT: arquivo inválido"
    assert extractor.calls == []
    assert index.records == []
    assert index.upsert_calls == 0
    assert index.delete_calls == []
    assert [s.stage for s in sink.statuses] == ["FAILED"]


def test_file_over_size_limit_fails_with_extract(tmp_path):
    file_path = _write_pdf(tmp_path, content=b"%PDF-1.4\n" + b"x" * 100)
    service, _extractor, _ocr, _embedder, index, sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE)]}, max_pdf_bytes=16
    )

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "FAILED"
    assert status.message == "EXTRACT: arquivo inválido"
    assert index.upsert_calls == 0
    assert [s.stage for s in sink.statuses] == ["FAILED"]


# ------------------------------------------------------- páginas ilegíveis


def test_illegible_page_signals_review_without_blocking_indexing(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, ocr, _embedder, index, sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE), PageText(2, "curta")]}
    )
    ocr.results_by_page[2] = (OCR_TEXT, 0.2)

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "REVIEW_REQUIRED"
    assert status.progress == 1.0
    assert status.message.startswith("REVIEW: páginas ilegíveis:")
    assert "2" in status.message
    assert [s.stage for s in sink.statuses] == [
        "RECEIVED",
        "TEXT_EXTRACTED",
        "OCR_COMPLETED",
        "INDEXED",
        "REVIEW_REQUIRED",
    ]
    assert index.records


# ------------------------------------------------------------- falhas (EC-04)


def test_extraction_failure_is_classified_as_extract(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, extractor, _ocr, _embedder, index, sink = _build_service()
    extractor.pages_by_path[file_path] = [PageText(1, NATIVE_PAGE)]
    extractor.error = RuntimeError("pdf trancado")

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "FAILED"
    assert status.message == "EXTRACT: pdf trancado"
    assert index.upsert_calls == 0
    assert [s.stage for s in sink.statuses] == ["RECEIVED", "FAILED"]


def test_ocr_failure_is_classified_as_ocr(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, ocr, _embedder, index, sink = _build_service(
        {file_path: [PageText(1, "curta")]}
    )
    ocr.error = RuntimeError("paddle estourou")

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "FAILED"
    assert status.message == "OCR: paddle estourou"
    assert index.upsert_calls == 0
    assert [s.stage for s in sink.statuses] == ["RECEIVED", "FAILED"]


def test_embedder_failure_is_classified_as_indexing(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, _ocr, embedder, index, sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE)]}
    )
    embedder.error = RuntimeError("gemini fora do ar")

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "FAILED"
    assert status.message == "INDEXING: gemini fora do ar"
    assert index.records == []
    assert index.upsert_calls == 0
    assert [s.stage for s in sink.statuses] == ["RECEIVED", "TEXT_EXTRACTED", "FAILED"]


# --------------------------------------------------------------- idempotência


def test_reprocessing_same_document_does_not_duplicate_chunks(tmp_path):
    file_path = _write_pdf(tmp_path)
    pages = {file_path: [PageText(1, MULTI_CHUNK_PAGE), PageText(2, NATIVE_PAGE)]}
    service, _extractor, _ocr, _embedder, index, _sink = _build_service(pages)

    service.process_document("doc-1", "pol-1", file_path)
    first_count = len(index.records)
    first_ids = {record.metadata.chunk_id for record in index.records}

    service.process_document("doc-1", "pol-1", file_path)

    assert index.delete_calls == ["doc-1", "doc-1"]
    assert len(index.records) == first_count
    assert {record.metadata.chunk_id for record in index.records} == first_ids


# ------------------------------------------------------------------ retrieval


def test_retrieve_evidence_respects_top_k_and_returns_valid_evidence(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, _ocr, _embedder, index, _sink = _build_service(
        {file_path: [PageText(1, MULTI_CHUNK_PAGE)]}
    )
    service.process_document("doc-1", "pol-1", file_path)
    assert len(index.records) > 2

    query = RetrievalQuery(query="defesa jurídica limites", top_k=2)
    result = service.retrieve_evidence(query)

    assert result.query == query
    assert result.retrieval_run_id
    assert len(result.evidences) == 2
    for evidence in result.evidences:
        assert evidence.evidence_id == f"ev_{evidence.chunk_id}"
        assert evidence.document_id == "doc-1"
        assert evidence.policy_id == "pol-1"
        assert evidence.page_number >= 1
        assert evidence.quoted_text.strip()
        assert evidence.source_type in ("NATIVE_TEXT", "PADDLEOCR")
        assert 0.0 <= evidence.retrieval_score <= 1.0


def test_retrieve_evidence_filters_by_policy_id(tmp_path):
    first_path = _write_pdf(tmp_path, name="apolice_a.pdf")
    second_path = _write_pdf(tmp_path, name="apolice_b.pdf")
    service, _extractor, _ocr, _embedder, _index, _sink = _build_service(
        {
            first_path: [PageText(1, NATIVE_PAGE)],
            second_path: [PageText(1, MULTI_CHUNK_PAGE)],
        }
    )
    service.process_document("doc-a", "pol-a", first_path)
    service.process_document("doc-b", "pol-b", second_path)

    result = service.retrieve_evidence(
        RetrievalQuery(query="defesa jurídica", top_k=5, policy_id="pol-b")
    )

    assert result.evidences
    assert {evidence.policy_id for evidence in result.evidences} == {"pol-b"}
    assert {evidence.document_id for evidence in result.evidences} == {"doc-b"}


def test_retrieve_evidence_run_id_is_unique_per_query(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, _ocr, _embedder, _index, _sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE)]}
    )
    service.process_document("doc-1", "pol-1", file_path)
    query = RetrievalQuery(query="cobertura", top_k=3)

    first = service.retrieve_evidence(query)
    second = service.retrieve_evidence(query)

    assert first.retrieval_run_id != second.retrieval_run_id


def test_retrieve_evidence_returns_empty_list_when_nothing_found(tmp_path):
    service, _extractor, _ocr, _embedder, _index, _sink = _build_service()

    result = service.retrieve_evidence(RetrievalQuery(query="cobertura", top_k=5))

    assert result.evidences == []
    assert result.retrieval_run_id


def test_retrieve_evidence_clamps_score_to_contract_range():
    record = ChunkRecord(
        metadata=build_chunk_metadata(
            chunk_id="doc-1:p1:c0",
            document_id="doc-1",
            policy_id="pol-1",
            page_number=1,
            chunk_index=0,
            source_type="NATIVE_TEXT",
            ocr_confidence=None,
        ),
        text="trecho da apólice",
    )

    class _StubIndex:
        def ensure_collection(self):
            pass

        def delete_document(self, document_id):
            pass

        def upsert_chunks(self, records):
            pass

        def search(self, vector, top_k, policy_id=None, document_id=None):
            return [
                ScoredChunk(record=record, score=2.0),
                ScoredChunk(record=record, score=-1.0),
            ]

    service = DocumentProcessingService(
        FakeTextExtractor(), FakeOcrEngine(), FakeEmbedder(), _StubIndex(), RecordingStatusSink()
    )

    result = service.retrieve_evidence(RetrievalQuery(query="apólice", top_k=5))

    assert [evidence.retrieval_score for evidence in result.evidences] == [1.0, 0.0]
