"""Orquestração do processamento documental (RF-01 a RF-09).

`DocumentProcessingService` coordena as portas (extração, OCR, embeddings,
índice e status) sem conhecer as implementações — núcleo testável com fakes.
"""

import uuid
from pathlib import Path

from shared_kernel.contracts import EvidenceRef, ProcessingStatus, RetrievalQuery, RetrievalResult

from ..domain.processing import (
    ChunkRecord,
    build_chunk_metadata,
    chunk_text,
    classify_page,
    is_illegible,
)
from .ports import Embedder, OcrEngine, StatusSink, TextExtractor, VectorIndex

#: Tamanho máximo aceito do PDF em bytes (RF-01, default 50MB).
MAX_PDF_BYTES = 50 * 1024 * 1024

#: Assinatura mágica de todo PDF válido (RF-01).
PDF_HEADER = b"%PDF-"

#: Progresso publicado após a extração de texto (RF-06).
PROGRESS_TEXT_EXTRACTED = 0.3

#: Progresso publicado após o OCR (RF-06).
PROGRESS_OCR_COMPLETED = 0.5

#: Progresso publicado quando o documento termina indexado (RF-06).
PROGRESS_DONE = 1.0


class DocumentProcessingService:
    """Pipeline: validar → extrair → OCR → chunkar → embeddar → indexar (RF-01..RF-06)."""

    def __init__(
        self,
        text_extractor: TextExtractor,
        ocr_engine: OcrEngine,
        embedder: Embedder,
        vector_index: VectorIndex,
        status_sink: StatusSink,
        max_pdf_bytes: int = MAX_PDF_BYTES,
    ) -> None:
        self._text_extractor = text_extractor
        self._ocr_engine = ocr_engine
        self._embedder = embedder
        self._vector_index = vector_index
        self._status_sink = status_sink
        self._max_pdf_bytes = max_pdf_bytes

    def process_document(
        self, document_id: str, policy_id: str, file_path: str
    ) -> ProcessingStatus:
        """Processa um PDF de apólice ponta a ponta e publica cada estágio (RF-06)."""
        if self._validate_pdf(file_path) is not None:
            return self._publish_failed(document_id, "EXTRACT", "arquivo inválido")

        self._publish(
            ProcessingStatus(document_id=document_id, stage="RECEIVED", progress=0.0)
        )

        try:
            pages = self._text_extractor.extract_pages(file_path)
        except Exception as exc:  # falha de extração classificada (EC-04)
            return self._publish_failed(document_id, "EXTRACT", _cause(exc))

        extracted: list[tuple[int, str, str, float | None]] = []
        ocr_page_numbers: list[int] = []
        try:
            for page in pages:
                source_type = classify_page(page.text)
                if source_type == "NATIVE_TEXT":
                    extracted.append((page.page_number, page.text, "NATIVE_TEXT", None))
                    continue
                text, ocr_confidence = self._ocr_engine.ocr_page(
                    file_path, page.page_number
                )
                extracted.append(
                    (page.page_number, text, "PADDLEOCR", ocr_confidence)
                )
                ocr_page_numbers.append(page.page_number)
        except Exception as exc:  # falha de OCR classificada (EC-04)
            return self._publish_failed(document_id, "OCR", _cause(exc))

        self._publish(
            ProcessingStatus(
                document_id=document_id, stage="TEXT_EXTRACTED", progress=PROGRESS_TEXT_EXTRACTED
            )
        )
        if ocr_page_numbers:
            self._publish(
                ProcessingStatus(
                    document_id=document_id,
                    stage="OCR_COMPLETED",
                    progress=PROGRESS_OCR_COMPLETED,
                )
            )

        records: list[ChunkRecord] = []
        illegible_pages: list[int] = []
        for page_number, text, source_type, ocr_confidence in extracted:
            if is_illegible(ocr_confidence):
                illegible_pages.append(page_number)
            for chunk_index, chunk in enumerate(chunk_text(text)):
                chunk_id = f"{document_id}:p{page_number}:c{chunk_index}"
                metadata = build_chunk_metadata(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    policy_id=policy_id,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    source_type=source_type,
                    ocr_confidence=ocr_confidence,
                )
                records.append(ChunkRecord(metadata=metadata, text=chunk))

        try:
            vectors = self._embedder.embed_texts([record.text for record in records])
            for record, vector in zip(records, vectors):
                record.vector = vector
            self._vector_index.ensure_collection()
            # Idempotência (RF-09/EC-03/D-07): limpa o estado anterior antes do upsert.
            self._vector_index.delete_document(document_id)
            self._vector_index.upsert_chunks(records)
        except Exception as exc:  # falha de embedding/indexação (EC-04)
            return self._publish_failed(document_id, "INDEXING", _cause(exc))

        indexed_status = ProcessingStatus(
            document_id=document_id, stage="INDEXED", progress=PROGRESS_DONE
        )
        self._publish(indexed_status)

        if illegible_pages:
            pages_listing = ", ".join(str(page) for page in sorted(illegible_pages))
            review_status = ProcessingStatus(
                document_id=document_id,
                stage="REVIEW_REQUIRED",
                progress=PROGRESS_DONE,
                message=f"REVIEW: páginas ilegíveis: {pages_listing}",
            )
            self._publish(review_status)
            return review_status
        return indexed_status

    def retrieve_evidence(self, query: RetrievalQuery) -> RetrievalResult:
        """Recupera evidências ranqueadas (RF-07); lista vazia é resposta válida (EC-07)."""
        vector = self._embedder.embed_texts([query.query])[0]
        scored_chunks = self._vector_index.search(
            vector,
            top_k=query.top_k,
            policy_id=query.policy_id,
            document_id=query.document_id,
        )

        evidences: list[EvidenceRef] = []
        for scored_chunk in scored_chunks[: query.top_k]:
            record = scored_chunk.record
            if not record.text.strip():
                continue
            metadata = record.metadata
            evidences.append(
                EvidenceRef(
                    evidence_id=f"ev_{metadata.chunk_id}",
                    policy_id=metadata.policy_id,
                    document_id=metadata.document_id,
                    page_number=metadata.page_number,
                    chunk_id=metadata.chunk_id,
                    section_name=metadata.section_name,
                    quoted_text=record.text,
                    retrieval_score=_clamp01(scored_chunk.score),
                    ocr_confidence=metadata.ocr_confidence,
                    source_type=metadata.source_type,
                )
            )
        return RetrievalResult(
            query=query,
            evidences=evidences,
            retrieval_run_id=uuid.uuid4().hex,
        )

    def _validate_pdf(self, file_path: str) -> str | None:
        """Valida existência, extensão, tamanho e cabeçalho (RF-01); None = válido."""
        path = Path(file_path)
        if not path.is_file():
            return "arquivo inválido"
        if path.suffix.lower() != ".pdf":
            return "arquivo inválido"
        if path.stat().st_size > self._max_pdf_bytes:
            return "arquivo inválido"
        with path.open("rb") as handle:
            if not handle.read(len(PDF_HEADER)).startswith(PDF_HEADER):
                return "arquivo inválido"
        return None

    def _publish(self, status: ProcessingStatus) -> None:
        self._status_sink.publish(status)

    def _publish_failed(self, document_id: str, stage: str, cause: str) -> ProcessingStatus:
        status = ProcessingStatus(
            document_id=document_id,
            stage="FAILED",
            progress=0.0,
            message=f"{stage}: {cause}",
        )
        self._publish(status)
        return status


def _cause(exc: Exception) -> str:
    """Mensagem da causa da falha; nunca deixa o motivo em branco (EC-04)."""
    return str(exc) or type(exc).__name__


def _clamp01(value: float) -> float:
    """Normaliza o score de recuperação para o intervalo [0,1] do contrato (RF-07)."""
    return max(0.0, min(1.0, float(value)))
