"""Fachada pública única do módulo `document_processing` (RF-08, resumo §9.1).

Outros módulos só importam daqui; adapters internos ficam atrás das portas.
Este módulo é importável sem nenhuma dependência externa instalada.
"""

import logging
from typing import Literal

from shared_kernel.contracts import ProcessingStatus, RetrievalQuery, RetrievalResult

from .application.ports import (
    Embedder,
    LayoutEngine,
    OcrEngine,
    StatusSink,
    TextExtractor,
    VectorIndex,
)
from .application.service import DocumentProcessingService


class DocumentProcessingFacade:
    """Ponto de entrada do pipeline documental para o workflow e o Dev 2."""

    def __init__(self, service: DocumentProcessingService) -> None:
        self._service = service

    def process_document(
        self,
        document_id: str,
        policy_id: str,
        file_path: str,
        layout_mode: Literal["scanned", "all"] = "scanned",
    ) -> ProcessingStatus:
        return self._service.process_document(
            document_id, policy_id, file_path, layout_mode=layout_mode
        )

    def retrieve_evidence(self, query: RetrievalQuery) -> RetrievalResult:
        return self._service.retrieve_evidence(query)

    def extract_preview(self, file_path: str, max_pages: int = 2) -> list[str]:
        """Texto das primeiras páginas do arquivo (preview de identificação)."""
        return self._service.extract_preview_pages(file_path, max_pages=max_pages)

    def extract_markdown(self, file_path: str, max_pages: int | None = None) -> list[str]:
        """Markdown estruturado de cada página, em ordem de leitura.

        `max_pages` limita às primeiras páginas (`None` = todas). Compartilha o
        cache de OCR/layout com o preview e o processamento — mesma página não
        roda OCR duas vezes na mesma instância do serviço.
        """
        return [
            page.markdown
            for page in self._service.extract_markdown_pages(file_path, max_pages=max_pages)
        ]


class _LoggingStatusSink:
    """StatusSink padrão: registra cada transição no logger do módulo."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("document_processing")

    def publish(self, status: ProcessingStatus) -> None:
        self._logger.info(
            "%s %s %.2f %s",
            status.document_id,
            status.stage,
            status.progress,
            status.message or "",
        )


def create_document_processing(
    text_extractor: TextExtractor,
    ocr_engine: OcrEngine,
    embedder: Embedder,
    vector_index: VectorIndex,
    status_sink: StatusSink,
    layout_engine: LayoutEngine | None = None,
) -> DocumentProcessingFacade:
    """Monta a fachada com portas injetadas (testes e E2E com fakes).

    `layout_engine` é opcional (dev1-006): sem motor, o pipeline roda sem
    análise de layout e degrada normalmente (RN-05).
    """
    service = DocumentProcessingService(
        text_extractor=text_extractor,
        ocr_engine=ocr_engine,
        embedder=embedder,
        vector_index=vector_index,
        status_sink=status_sink,
        layout_engine=layout_engine,
    )
    return DocumentProcessingFacade(service)


def create_default_document_processing(
    status_sink: StatusSink | None = None,
    gemini_api_key: str | None = None,
    qdrant_url: str = "http://localhost:6333",
    vector_size: int = 768,
) -> DocumentProcessingFacade:
    """Monta a fachada com os adapters reais (imports lazy — exige libs instaladas)."""
    from .infrastructure.extractors import PaddleOcrEngine, PyMuPdfTextExtractor
    from .infrastructure.indexing import GeminiEmbedder, QdrantVectorIndex
    from .infrastructure.layout import PpStructureLayoutEngine

    return create_document_processing(
        text_extractor=PyMuPdfTextExtractor(),
        ocr_engine=PaddleOcrEngine(),
        embedder=GeminiEmbedder(api_key=gemini_api_key, output_dimensionality=vector_size),
        vector_index=QdrantVectorIndex(url=qdrant_url, vector_size=vector_size),
        status_sink=status_sink if status_sink is not None else _LoggingStatusSink(),
        layout_engine=PpStructureLayoutEngine(),
    )
