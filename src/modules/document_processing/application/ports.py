"""Portas do document_processing como `typing.Protocol` (D-02, sem framework de DI).

As implementações reais vivem em `infrastructure/`; os testes usam fakes
determinísticos que satisfazem estruturalmente estes protocolos.
"""

from dataclasses import dataclass
from typing import Protocol

from shared_kernel.contracts import ProcessingStatus

from ..domain.processing import ChunkRecord, PageText


@dataclass
class ScoredChunk:
    """Resultado de busca: chunk recuperado com score de similaridade."""

    record: ChunkRecord
    score: float


class TextExtractor(Protocol):
    """Extrai o texto nativo de cada página do arquivo (ordem do documento)."""

    def extract_pages(self, file_path: str) -> list[PageText]: ...


class OcrEngine(Protocol):
    """Aplica OCR a uma página; devolve (texto, confiança média em [0,1])."""

    def ocr_page(self, file_path: str, page_number: int) -> tuple[str, float | None]: ...


class Embedder(Protocol):
    """Gera um vetor por texto de entrada, na mesma ordem."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class VectorIndex(Protocol):
    """Índice vetorial dos chunks (coleção única `policy_chunks`, D-05)."""

    def ensure_collection(self) -> None: ...

    def delete_document(self, document_id: str) -> None: ...

    def upsert_chunks(self, records: list[ChunkRecord]) -> None: ...

    def search(
        self,
        vector: list[float],
        top_k: int,
        policy_id: str | None = None,
        document_id: str | None = None,
    ) -> list[ScoredChunk]: ...


class StatusSink(Protocol):
    """Publica o `ProcessingStatus` de cada transição de estágio (RF-06)."""

    def publish(self, status: ProcessingStatus) -> None: ...
