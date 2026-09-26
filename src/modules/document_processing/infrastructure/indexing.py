"""Adapters de indexação: Gemini (embeddings) e Qdrant (índice vetorial).

Imports lazy — `public_api` continua importável sem nenhuma destas libs;
a construção dos adapters falha com `RuntimeError` claro quando falta
dependência ou configuração (RNF-06, EC-04).
"""

import os
import uuid

from ..application.ports import ScoredChunk
from ..domain.processing import ChunkRecord
from shared_kernel.contracts import ChunkMetadata

#: Coleção única de chunks (D-05/OQ-04).
COLLECTION_NAME = "policy_chunks"

#: Dimensão padrão dos vetores (alinhada ao Qdrant e ao modelo de embeddings).
DEFAULT_VECTOR_SIZE = 768

#: Namespace estável para derivar IDs de ponto do Qdrant a partir do chunk_id.
_POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "document_processing.policy_chunks")


def _stable_point_id(chunk_id: str) -> str:
    """Deriva um UUID estável por chunk_id (IDs do Qdrant exigem int/UUID)."""
    return str(uuid.uuid5(_POINT_NAMESPACE, chunk_id))


class GeminiEmbedder:
    """Gera embeddings com a API Gemini (provedor único, NG-03)."""

    def __init__(
        self,
        model: str = "gemini-embedding-001",
        api_key: str | None = None,
        output_dimensionality: int = DEFAULT_VECTOR_SIZE,
    ) -> None:
        self._model = model
        self._output_dimensionality = output_dimensionality
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "configuração ausente: defina GEMINI_API_KEY para usar este adapter"
            )
        self._kind, self._sdk = self._load_sdk()
        self._client = None

    @staticmethod
    def _load_sdk() -> tuple[str, object]:
        try:
            from google import genai  # google-genai (SDK novo)
        except ImportError:
            genai = None
        if genai is not None:
            return "genai", genai
        try:
            import google.generativeai as generativeai  # google-generativeai (SDK legado)
        except ImportError as exc:
            raise RuntimeError(
                "dependência ausente: google-genai — instale para usar este adapter"
            ) from exc
        return "generativeai", generativeai

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._kind == "genai":
            if self._client is None:
                self._client = self._sdk.Client(api_key=self._api_key)
            response = self._client.models.embed_contents(
                model=self._model,
                contents=texts,
                output_dimensionality=self._output_dimensionality,
            )
            return [list(embedding.values) for embedding in response.embeddings]

        self._sdk.configure(api_key=self._api_key)
        return [
            list(
                self._sdk.embed_content(
                    model=self._model,
                    content=text,
                    output_dimensionality=self._output_dimensionality,
                )["embedding"]
            )
            for text in texts
        ]


class QdrantVectorIndex:
    """Índice vetorial Qdrant: coleção única `policy_chunks`, distância cosine (D-05)."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        vector_size: int = DEFAULT_VECTOR_SIZE,
        collection_name: str = COLLECTION_NAME,
        api_key: str | None = None,
    ) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client import models as qdrant_models
        except ImportError as exc:
            raise RuntimeError(
                "dependência ausente: qdrant-client — instale para usar este adapter"
            ) from exc
        self._models = qdrant_models
        self._client = QdrantClient(url=url, api_key=api_key)
        self._vector_size = vector_size
        self._collection_name = collection_name

    def ensure_collection(self) -> None:
        if self._client.collection_exists(self._collection_name):
            return
        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=self._models.VectorParams(
                size=self._vector_size, distance=self._models.Distance.COSINE
            ),
        )

    def delete_document(self, document_id: str) -> None:
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=self._models.Filter(
                must=[
                    self._models.FieldCondition(
                        key="document_id",
                        match=self._models.MatchValue(value=document_id),
                    )
                ]
            ),
        )

    def upsert_chunks(self, records: list[ChunkRecord]) -> None:
        if not records:
            return
        points = []
        for record in records:
            if record.vector is None:
                raise ValueError(f"chunk {record.metadata.chunk_id} sem vetor para indexar")
            points.append(
                self._models.PointStruct(
                    id=_stable_point_id(record.metadata.chunk_id),
                    vector=list(record.vector),
                    payload=_payload_from_record(record),
                )
            )
        self._client.upsert(collection_name=self._collection_name, points=points)

    def search(
        self,
        vector: list[float],
        top_k: int,
        policy_id: str | None = None,
        document_id: str | None = None,
    ) -> list[ScoredChunk]:
        conditions = []
        if policy_id is not None:
            conditions.append(
                self._models.FieldCondition(
                    key="policy_id", match=self._models.MatchValue(value=policy_id)
                )
            )
        if document_id is not None:
            conditions.append(
                self._models.FieldCondition(
                    key="document_id", match=self._models.MatchValue(value=document_id)
                )
            )
        query_filter = self._models.Filter(must=conditions) if conditions else None

        response = self._client.query_points(
            collection_name=self._collection_name,
            query=list(vector),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=True,
        )
        return [
            ScoredChunk(
                record=_record_from_payload(point.payload, point.vector),
                score=float(point.score),
            )
            for point in response.points
        ]


def _payload_from_record(record: ChunkRecord) -> dict:
    """Payload do Qdrant conforme `data-delta.md` (IDs + texto + origem)."""
    metadata = record.metadata
    return {
        "chunk_id": metadata.chunk_id,
        "document_id": metadata.document_id,
        "policy_id": metadata.policy_id,
        "page": metadata.page_number,
        "chunk_index": metadata.chunk_index,
        "section_name": metadata.section_name,
        "metadata_version": metadata.metadata_version,
        "source_type": metadata.source_type,
        "ocr_confidence": metadata.ocr_confidence,
        "text": record.text,
    }


def _record_from_payload(payload: dict, vector) -> ChunkRecord:
    """Reconstrói o `ChunkRecord` a partir do payload persistido (RF-05)."""
    metadata = ChunkMetadata(
        chunk_id=payload["chunk_id"],
        document_id=payload["document_id"],
        policy_id=payload["policy_id"],
        page_number=payload["page"],
        chunk_index=payload["chunk_index"],
        source_type=payload["source_type"],
        ocr_confidence=payload["ocr_confidence"],
        section_name=payload["section_name"],
        metadata_version=payload["metadata_version"],
    )
    return ChunkRecord(
        metadata=metadata,
        text=payload["text"],
        vector=list(vector) if vector is not None else None,
    )
