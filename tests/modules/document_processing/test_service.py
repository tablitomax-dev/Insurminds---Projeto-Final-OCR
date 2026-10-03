"""Testes do serviço de processamento: orquestração, status, idempotência e retrieval (RF-01..RF-09)."""

import logging

import pytest

from fakes.document_processing import (
    FakeEmbedder,
    FakeLayoutEngine,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from modules.document_processing.application.ports import (
    EmbeddingError,
    LayoutError,
    LayoutRegion,
    ScoredChunk,
    TextExtractionError,
)
from modules.document_processing.application.service import DocumentProcessingService
from modules.document_processing.domain.processing import ChunkRecord, PageText, build_chunk_metadata
from modules.document_processing.public_api import _LoggingStatusSink
from shared_kernel.contracts import RetrievalQuery
from shared_kernel.version import CONTRACTS_VERSION

NATIVE_PAGE = "A apólice D&O garante cobertura para atos administrativos e defesa jurídica dos segurados."
MULTI_CHUNK_PAGE = "A apólice D&O cobre limites de responsabilidade e defesa jurídica. " * 30
OCR_TEXT = "texto reconhecido pelo ocr da página escaneada com conteúdo suficiente"

#: Texto de apólice que NUNCA pode aparecer em mensagem de erro/log (T-2a).
POLICY_TEXT = "Limite agregado R$ 1.000.000"


def _write_pdf(tmp_path, name="apolice.pdf", content=b"%PDF-1.4\nconteudo fake\n"):
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def _build_service(pages_by_path=None, max_pdf_bytes=None, layout_engine=None):
    extractor = FakeTextExtractor(pages_by_path=pages_by_path)
    ocr_engine = FakeOcrEngine()
    embedder = FakeEmbedder()
    index = InMemoryVectorIndex()
    sink = RecordingStatusSink()
    kwargs = {}
    if max_pdf_bytes is not None:
        kwargs["max_pdf_bytes"] = max_pdf_bytes
    service = DocumentProcessingService(
        extractor, ocr_engine, embedder, index, sink, layout_engine=layout_engine, **kwargs
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
    assert status.message == "EXTRACT: RuntimeError"  # só o tipo — nunca o texto (T-2a)
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
    assert status.message == "OCR: RuntimeError"  # só o tipo — nunca o texto (T-2a)
    assert index.upsert_calls == 0
    assert [s.stage for s in sink.statuses] == ["RECEIVED", "FAILED"]


def test_embedder_failure_is_classified_as_indexing(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, _ocr, embedder, index, sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE)]}
    )
    embedder.error = EmbeddingError("gemini fora do ar")  # adapter traduz para a porta (D1-P0-1)

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "FAILED"
    assert status.message == "INDEXING: EmbeddingError"  # só o tipo — nunca o texto (T-2a)
    assert index.records == []
    assert index.upsert_calls == 0
    assert [s.stage for s in sink.statuses] == ["RECEIVED", "TEXT_EXTRACTED", "FAILED"]


# ------------------------------------------- T-2a: anti-vazamento de texto


def test_extractor_failure_status_never_contains_policy_text(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, extractor, _ocr, _embedder, _index, sink = _build_service()
    extractor.pages_by_path[file_path] = [PageText(1, NATIVE_PAGE)]
    extractor.error = RuntimeError(POLICY_TEXT)

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "FAILED"
    assert status.message == "EXTRACT: RuntimeError"
    for published in sink.statuses:
        assert POLICY_TEXT not in (published.message or "")


def test_ocr_failure_status_never_contains_policy_text(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, ocr, _embedder, _index, sink = _build_service(
        {file_path: [PageText(1, "curta")]}
    )
    ocr.error = RuntimeError(POLICY_TEXT)

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "FAILED"
    assert status.message == "OCR: RuntimeError"
    for published in sink.statuses:
        assert POLICY_TEXT not in (published.message or "")


def test_embedder_failure_status_never_contains_policy_text(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, _ocr, embedder, _index, sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE)]}
    )
    embedder.error = EmbeddingError(POLICY_TEXT)

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "FAILED"
    assert status.message == "INDEXING: EmbeddingError"
    for published in sink.statuses:
        assert POLICY_TEXT not in (published.message or "")


def test_failure_logs_never_contain_policy_text(tmp_path, caplog):
    file_path = _write_pdf(tmp_path)
    extractor = FakeTextExtractor(pages_by_path={file_path: [PageText(1, NATIVE_PAGE)]})
    extractor.error = TextExtractionError(POLICY_TEXT)
    sink = _LoggingStatusSink()
    service = DocumentProcessingService(
        extractor, FakeOcrEngine(), FakeEmbedder(), InMemoryVectorIndex(), sink
    )

    with caplog.at_level(logging.INFO, logger="document_processing"):
        service.process_document("doc-1", "pol-1", file_path)

    assert POLICY_TEXT not in caplog.text
    assert "TextExtractionError" in caplog.text


# ------------------------------------- D1-P0-3d: health-check da coleção


def test_index_health_check_failure_is_classified_as_indexing_without_crash(tmp_path):
    file_path = _write_pdf(tmp_path)
    service, _extractor, _ocr, embedder, index, sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE)]}
    )
    index.ensure_collection_error = RuntimeError(POLICY_TEXT)

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "FAILED"
    assert status.message == "INDEXING: RuntimeError"
    assert POLICY_TEXT not in (status.message or "")
    # health-check roda antes de gastar embeddings e aborta antes do upsert
    assert embedder.calls == []
    assert index.upsert_calls == 0
    assert [s.stage for s in sink.statuses] == ["RECEIVED", "TEXT_EXTRACTED", "FAILED"]


# --------------------------------- D1-P0-3a: isolamento entre apólices


def test_interleaved_policies_are_isolated_on_retrieval(tmp_path):
    path_a1 = _write_pdf(tmp_path, name="a1.pdf")
    path_b = _write_pdf(tmp_path, name="b.pdf")
    path_a2 = _write_pdf(tmp_path, name="a2.pdf")
    pages = {path: [PageText(1, MULTI_CHUNK_PAGE)] for path in (path_a1, path_b, path_a2)}
    service, _extractor, _ocr, _embedder, index, _sink = _build_service(pages)

    # indexamento intercalado: A, B, A — mesmo índice, chunks vizinhos
    service.process_document("doc-a1", "pol-a", path_a1)
    service.process_document("doc-b1", "pol-b", path_b)
    service.process_document("doc-a2", "pol-a", path_a2)

    unfiltered = service.retrieve_evidence(
        RetrievalQuery(query="defesa jurídica", top_k=20)
    )
    assert {evidence.policy_id for evidence in unfiltered.evidences} == {"pol-a", "pol-b"}

    result_a = service.retrieve_evidence(
        RetrievalQuery(query="defesa jurídica", top_k=20, policy_id="pol-a")
    )
    assert result_a.evidences
    assert {evidence.policy_id for evidence in result_a.evidences} == {"pol-a"}
    assert {evidence.document_id for evidence in result_a.evidences} <= {"doc-a1", "doc-a2"}

    result_b = service.retrieve_evidence(
        RetrievalQuery(query="defesa jurídica", top_k=20, policy_id="pol-b")
    )
    assert result_b.evidences
    assert {evidence.policy_id for evidence in result_b.evidences} == {"pol-b"}
    assert {evidence.document_id for evidence in result_b.evidences} == {"doc-b1"}


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

        def search(
            self,
            vector,
            top_k,
            policy_id=None,
            document_id=None,
            section_name=None,
            field_code=None,
        ):
            return [
                ScoredChunk(record=record, score=2.0),
                ScoredChunk(record=record, score=-1.0),
            ]

    service = DocumentProcessingService(
        FakeTextExtractor(), FakeOcrEngine(), FakeEmbedder(), _StubIndex(), RecordingStatusSink()
    )

    result = service.retrieve_evidence(RetrievalQuery(query="apólice", top_k=5))

    assert [evidence.retrieval_score for evidence in result.evidences] == [1.0, 0.0]


# ------------- dev1-006: estrutura, cláusulas e tabelas (NG-01) — RF-01/RF-04


def test_chunks_herdam_literal_do_marcador_vigente(tmp_path):
    file_path = _write_pdf(tmp_path)
    page_text = "CLÁUSULA 5ª — FRANQUIA\n" + "a franquia aplicável está descrita aqui. " * 20
    service, _extractor, _ocr, _embedder, index, _sink = _build_service(
        {file_path: [PageText(1, page_text)]}
    )

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "INDEXED"
    assert index.records
    assert {record.metadata.section_name for record in index.records} == {
        "CLÁUSULA 5ª — FRANQUIA"
    }


def test_secao_atravessa_paginas_e_chunk_sem_marcador_e_none(tmp_path):
    file_path = _write_pdf(tmp_path)
    pages = [
        PageText(1, "texto introdutório da apólice, sem estrutura. " * 20),
        PageText(2, "CLÁUSULA 5ª — FRANQUIA\n" + "a franquia aplicável está descrita. " * 20),
        PageText(3, "continuação das regras da franquia, sem novo marcador. " * 20),
    ]
    service, _extractor, _ocr, _embedder, index, _sink = _build_service({file_path: pages})

    service.process_document("doc-1", "pol-1", file_path)

    secao_por_pagina = {
        record.metadata.page_number: record.metadata.section_name for record in index.records
    }
    assert secao_por_pagina == {
        1: None,
        2: "CLÁUSULA 5ª — FRANQUIA",
        3: "CLÁUSULA 5ª — FRANQUIA",
    }


def test_retrieval_por_secao_retorna_so_evidencias_da_clausula(tmp_path):
    file_path = _write_pdf(tmp_path)
    pages = [
        PageText(1, "CLÁUSULA 5ª — FRANQUIA\n" + "a franquia aplicável está descrita. " * 20),
        PageText(2, "CLÁUSULA 8ª — EXCLUSÕES\n" + "as exclusões aplicáveis estão descritas. " * 20),
    ]
    service, _extractor, _ocr, _embedder, index, _sink = _build_service({file_path: pages})
    service.process_document("doc-1", "pol-1", file_path)

    result = service.retrieve_evidence(
        RetrievalQuery(query="franquia", top_k=10, section_name="CLÁUSULA 5ª — FRANQUIA")
    )

    assert result.evidences
    assert {evidence.section_name for evidence in result.evidences} == {
        "CLÁUSULA 5ª — FRANQUIA"
    }


# ----------------- dev1-006: layout/tabela (NG-01) — RF-02/RF-03/RF-05


def test_pagina_escaneada_com_layout_vira_pp_structure_com_tabela_serializada(tmp_path):
    file_path = _write_pdf(tmp_path)
    engine = FakeLayoutEngine(
        regions_by_page={
            1: [
                LayoutRegion(kind="heading", text="CLÁUSULA 5ª — FRANQUIA", order=0),
                LayoutRegion(kind="table", text="limite\t1000000\nfranquia\t50000", order=1),
                LayoutRegion(kind="text", text="condições gerais da franquia", order=2),
            ]
        }
    )
    service, _extractor, _ocr, _embedder, index, _sink = _build_service(
        {file_path: [PageText(1, "curta")]}, layout_engine=engine
    )

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "INDEXED"
    assert engine.calls == [(file_path, 1)]
    record = index.records[0]
    assert record.metadata.source_type == "PP_STRUCTURE"
    assert "[TABELA]" in record.text
    assert "limite | 1000000" in record.text
    assert record.metadata.section_name == "CLÁUSULA 5ª — FRANQUIA"


def test_flag_all_estende_layout_as_paginas_nativas(tmp_path):
    file_path = _write_pdf(tmp_path)
    engine = FakeLayoutEngine(
        regions_by_page={1: [LayoutRegion(kind="text", text="texto do layout em ordem", order=0)]}
    )
    service, _extractor, _ocr, _embedder, index, _sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE)]}, layout_engine=engine
    )

    service.process_document("doc-1", "pol-1", file_path, layout_mode="all")

    assert engine.calls == [(file_path, 1)]
    record = index.records[0]
    assert record.metadata.source_type == "PP_STRUCTURE"
    assert record.text == "texto do layout em ordem"


def test_default_scanned_nao_analisa_layout_de_pagina_nativa(tmp_path):
    file_path = _write_pdf(tmp_path)
    engine = FakeLayoutEngine()
    service, _extractor, _ocr, _embedder, index, _sink = _build_service(
        {file_path: [PageText(1, NATIVE_PAGE)]}, layout_engine=engine
    )

    service.process_document("doc-1", "pol-1", file_path)

    assert engine.calls == []
    assert index.records[0].metadata.source_type == "NATIVE_TEXT"


def test_falha_do_motor_de_layout_degrada_sem_failed(tmp_path):
    file_path = _write_pdf(tmp_path)
    engine = FakeLayoutEngine(error=LayoutError("falha na análise de layout (RuntimeError)"))
    service, _extractor, _ocr, _embedder, index, _sink = _build_service(
        {file_path: [PageText(1, "curta")]}, layout_engine=engine
    )
    ocr_engine = _ocr
    ocr_engine.results_by_page[1] = (OCR_TEXT, 0.9)

    status = service.process_document("doc-1", "pol-1", file_path)

    assert status.stage == "INDEXED"  # RN-05: nunca FAILED por causa do motor
    record = index.records[0]
    assert record.metadata.source_type == "PADDLEOCR"  # degradou para o texto do OCR
    assert "texto reconhecido" in record.text


# ------------------------- dev1-006: T-2a — nada de apólice em log (RN-07)


def test_fluxo_novo_nao_vaza_secao_ou_tabela_para_logs(tmp_path, caplog):
    file_path = _write_pdf(tmp_path)
    engine = FakeLayoutEngine(
        regions_by_page={1: [LayoutRegion(kind="table", text="limite\t1000000", order=0)]}
    )
    service, _extractor, _ocr, _embedder, index, _sink = _build_service(
        {file_path: [PageText(1, "CLÁUSULA 5ª — FRANQUIA\n" + "regras da franquia. " * 30)]},
        layout_engine=engine,
    )

    with caplog.at_level(logging.INFO):
        service.process_document("doc-1", "pol-1", file_path, layout_mode="all")

    mensagens = "\n".join(record.getMessage() for record in caplog.records)
    assert "FRANQUIA" not in mensagens  # literal da seção não vai para log
    assert "1000000" not in mensagens  # conteúdo de tabela não vai para log
