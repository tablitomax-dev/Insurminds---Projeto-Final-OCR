"""Fakes das portas do `document_processing` (D-10: testes sem libs externas)."""

import hashlib
import math

from modules.document_processing.application.ports import ScoredChunk
from modules.document_processing.domain.processing import ChunkRecord, PageText
from shared_kernel.contracts import ProcessingStatus


class FakeTextExtractor:
    """TextExtractor fake: páginas configuráveis por caminho de arquivo."""

    def __init__(
        self,
        pages_by_path: dict[str, list[PageText]] | None = None,
        default_pages: list[PageText] | None = None,
    ) -> None:
        self.pages_by_path = dict(pages_by_path or {})
        self.default_pages = list(default_pages or [])
        self.error: Exception | None = None
        self.calls: list[str] = []

    def extract_pages(self, file_path: str) -> list[PageText]:
        self.calls.append(file_path)
        if self.error is not None:
            raise self.error
        return list(self.pages_by_path.get(file_path, self.default_pages))


class FakeOcrEngine:
    """OcrEngine fake: resultado configurável por página, com falha opcional."""

    def __init__(
        self,
        results_by_page: dict[int, tuple[str, float | None]] | None = None,
        default_result: tuple[str, float | None] = ("texto ocr extraído da página", 0.9),
    ) -> None:
        self.results_by_page = dict(results_by_page or {})
        self.default_result = default_result
        self.error: Exception | None = None
        self.calls: list[tuple[str, int]] = []

    def ocr_page(self, file_path: str, page_number: int) -> tuple[str, float | None]:
        self.calls.append((file_path, page_number))
        if self.error is not None:
            raise self.error
        return self.results_by_page.get(page_number, self.default_result)


class FakeLayoutEngine:
    """LayoutEngine fake: regiões determinísticas por página, falha injetável."""

    def __init__(
        self,
        regions_by_page: dict[int, list] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.regions_by_page = dict(regions_by_page or {})
        self.error = error
        self.calls: list[tuple[str, int]] = []

    def analyze_page(self, file_path: str, page_number: int) -> list:
        self.calls.append((file_path, page_number))
        if self.error is not None:
            raise self.error
        return list(self.regions_by_page.get(page_number, []))


class FakeEmbedder:
    """Embedder fake: vetor determinístico derivado do texto (hashing por token)."""

    def __init__(self, dimensions: int = 32) -> None:
        self.dimensions = dimensions
        self.error: Exception | None = None
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.error is not None:
            raise self.error
        return [self._vector_for(text) for text in texts]

    def _vector_for(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector


class InMemoryVectorIndex:
    """VectorIndex fake: busca real por similaridade de cosseno em memória.

    Também age como spy: grava cada chamada de `search` (parâmetros recebidos)
    para o teste de contrato por parâmetro de `RetrievalQuery` (D1-P0-2).
    """

    def __init__(self) -> None:
        self._chunks: dict[str, ChunkRecord] = {}
        self.delete_calls: list[str] = []
        self.ensure_collection_calls = 0
        self.upsert_calls = 0
        self.search_calls: list[dict] = []
        self.ensure_collection_error: Exception | None = None

    def ensure_collection(self) -> None:
        self.ensure_collection_calls += 1
        if self.ensure_collection_error is not None:
            raise self.ensure_collection_error

    def delete_document(self, document_id: str) -> None:
        self.delete_calls.append(document_id)
        self._chunks = {
            chunk_id: record
            for chunk_id, record in self._chunks.items()
            if record.metadata.document_id != document_id
        }

    def upsert_chunks(self, records: list[ChunkRecord]) -> None:
        self.upsert_calls += 1
        for record in records:
            self._chunks[record.metadata.chunk_id] = record

    def search(
        self,
        vector: list[float],
        top_k: int,
        policy_id: str | None = None,
        document_id: str | None = None,
        section_name: str | None = None,
        field_code: str | None = None,
    ) -> list[ScoredChunk]:
        self.search_calls.append(
            {
                "vector": list(vector),
                "top_k": top_k,
                "policy_id": policy_id,
                "document_id": document_id,
                "section_name": section_name,
                "field_code": field_code,
            }
        )
        results = []
        for record in self._chunks.values():
            if policy_id is not None and record.metadata.policy_id != policy_id:
                continue
            if document_id is not None and record.metadata.document_id != document_id:
                continue
            if section_name is not None and record.metadata.section_name != section_name:
                continue
            score = _cosine_similarity(vector, record.vector or [])
            results.append(ScoredChunk(record=record, score=score))
        results.sort(key=lambda scored: scored.score, reverse=True)
        return results[:top_k]

    @property
    def records(self) -> list[ChunkRecord]:
        return list(self._chunks.values())


class RecordingStatusSink:
    """StatusSink fake: guarda todos os statuses publicados, em ordem."""

    def __init__(self) -> None:
        self.statuses: list[ProcessingStatus] = []

    def publish(self, status: ProcessingStatus) -> None:
        self.statuses.append(status)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if not norm_left or not norm_right:
        return 0.0
    return dot / (norm_left * norm_right)
