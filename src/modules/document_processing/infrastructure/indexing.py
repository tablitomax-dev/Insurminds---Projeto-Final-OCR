"""Adapters de indexação: Gemini (embeddings) e Qdrant (índice vetorial).

Imports lazy — `public_api` continua importável sem nenhuma destas libs;
a construção dos adapters falha com `RuntimeError` claro quando falta
dependência ou configuração (RNF-06, EC-04).

Resiliência (D1-P0-1/RF-01):
- Retry com backoff exponencial SÓ no adapter Gemini (429/5xx/timeouts);
  o Qdrant local não repete chamada (idempotência delete+upsert cobre reprocesso).
- Erro externo vira exceção tipada da porta (`EmbeddingError`/`IndexingError`)
  com mensagem sanitizada — só tipo do erro externo, nunca o texto (T-2a).
- Embeddings SEMPRE em lote (no máximo `MAX_EMBEDDING_TEXTS_PER_REQUEST` por
  request); o caminho do SDK legado também usa chamada em lote — sem loop por
  texto (D1-P0-3b/c).
"""

import os
import time
import uuid
from collections.abc import Callable
from typing import Any

from ..application.ports import EmbeddingError, IndexingError, ScoredChunk
from ..domain.processing import ChunkRecord
from shared_kernel.contracts import ChunkMetadata

#: Coleção única de chunks (D-05/OQ-04).
COLLECTION_NAME = "policy_chunks"

#: Dimensão padrão dos vetores (alinhada ao Qdrant e ao modelo de embeddings).
DEFAULT_VECTOR_SIZE = 768

#: Máximo de textos por request de embeddings (limite da API Gemini) (D1-P0-3b).
MAX_EMBEDDING_TEXTS_PER_REQUEST = 100

#: Tentativas máximas por request de embeddings (só erros transitórios).
EMBEDDING_MAX_ATTEMPTS = 3

#: Backoff exponencial entre tentativas: 1s -> 2s (base * fator**(tentativa-1)).
EMBEDDING_BACKOFF_BASE_SECONDS = 1.0
EMBEDDING_BACKOFF_FACTOR = 2.0

#: Timeout de cada chamada à API de embeddings (segundos).
EMBEDDING_TIMEOUT_SECONDS = 30.0

#: Códigos HTTP transitórios elegíveis a retry (timeout, rate limit, 5xx).
TRANSIENT_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})

#: Nomes de exceções transitórias (google-genai, google-api-core e stdlib).
TRANSIENT_ERROR_NAMES = frozenset(
    {
        "timeout",
        "timeouterror",
        "deadlineexceeded",
        "connectionerror",
        "connectionreseterror",
        "brokenpipeerror",
        "toomanyrequests",
        "resourceexhausted",
        "serviceunavailable",
        "unavailable",
        "internalservererror",
        "badgateway",
        "gatewaytimeout",
        "aborted",
        "retryerror",
    }
)

#: Namespace estável para derivar IDs de ponto do Qdrant a partir do chunk_id.
_POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "document_processing.policy_chunks")


def _stable_point_id(chunk_id: str) -> str:
    """Deriva um UUID estável por chunk_id (IDs do Qdrant exigem int/UUID)."""
    return str(uuid.uuid5(_POINT_NAMESPACE, chunk_id))


def _status_code_of(exc: Exception) -> int | None:
    """Extrai o código de status HTTP/gRPC do erro externo, quando existir."""
    status = getattr(exc, "code", None)
    if callable(status):
        try:
            status = status()
        except Exception:  # erro externo imprevisível: segue sem código
            status = None
    if isinstance(status, int):
        return status
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    return None


def is_transient_error(exc: Exception) -> bool:
    """Erro transitório (429/5xx/timeout/conexão) elegível a retry (D1-P0-1)."""
    status = _status_code_of(exc)
    if status is not None and status in TRANSIENT_STATUS_CODES:
        return True
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    return any(
        klass.__name__.lower() in TRANSIENT_ERROR_NAMES for klass in type(exc).__mro__
    )


def _embedding_values(embedding: Any) -> list[float]:
    """Normaliza um embedding da resposta dos SDKs (attr `values`, dict ou lista)."""
    if isinstance(embedding, dict):
        values = embedding.get("values", embedding.get("embedding"))
    else:
        values = getattr(embedding, "values", None)
    if values is None:
        values = embedding
    return list(values)


def _response_embeddings(response: Any) -> list:
    """Extrai a lista de embeddings da resposta (attr `embeddings` ou dict)."""
    embeddings = getattr(response, "embeddings", None)
    if embeddings is None and isinstance(response, dict):
        embeddings = response.get("embeddings")
    if embeddings is None:
        raise EmbeddingError(
            "resposta de embeddings fora do formato esperado (sem 'embeddings')"
        )
    return list(embeddings)


class GeminiEmbedder:
    """Gera embeddings em lote com a API Gemini (provedor único, NG-03).

    Sempre UM request por lote (nunca por texto), com no máximo
    `max_texts_per_request` textos por chamada. Retry com backoff exponencial
    SOMENTE em erros transitórios (429/5xx/timeout), no máximo `max_attempts`
    tentativas e timeout de `timeout_seconds` por chamada (D1-P0-1).
    """

    def __init__(
        self,
        model: str = "gemini-embedding-001",
        api_key: str | None = None,
        output_dimensionality: int = DEFAULT_VECTOR_SIZE,
        max_texts_per_request: int = MAX_EMBEDDING_TEXTS_PER_REQUEST,
        max_attempts: int = EMBEDDING_MAX_ATTEMPTS,
        backoff_base_seconds: float = EMBEDDING_BACKOFF_BASE_SECONDS,
        backoff_factor: float = EMBEDDING_BACKOFF_FACTOR,
        timeout_seconds: float = EMBEDDING_TIMEOUT_SECONDS,
        sleep: Callable[[float], None] | None = None,
        sdk_bundle: tuple[str, object] | None = None,
    ) -> None:
        self._model = model
        self._output_dimensionality = output_dimensionality
        self._max_texts_per_request = max(1, max_texts_per_request)
        self._max_attempts = max(1, max_attempts)
        self._backoff_base_seconds = backoff_base_seconds
        self._backoff_factor = backoff_factor
        self._timeout_seconds = timeout_seconds
        self._sleep = sleep
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "configuração ausente: defina GEMINI_API_KEY para usar este adapter"
            )
        self._kind, self._sdk = sdk_bundle if sdk_bundle is not None else self._load_sdk()
        self._client = None

    @staticmethod
    def _load_sdk() -> tuple[str, object]:
        """Carrega o SDK de embeddings de forma lazy (imports continuam lazy)."""
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
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._max_texts_per_request):
            batch = texts[start : start + self._max_texts_per_request]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        """UM request por lote, com retry só em erro transitório (D1-P0-1)."""
        attempt = 0
        while True:
            attempt += 1
            try:
                return self._request_embeddings(batch)
            except EmbeddingError:
                raise
            except Exception as exc:
                if attempt >= self._max_attempts or not is_transient_error(exc):
                    # Mensagem sanitizada: só tipo do erro externo (T-2a).
                    raise EmbeddingError(
                        f"falha na API de embeddings ({type(exc).__name__})"
                    ) from exc
                self._pause(self._backoff_base_seconds * (self._backoff_factor ** (attempt - 1)))

    def _pause(self, seconds: float) -> None:
        """Sleep injetável: usa o `sleep` recebido ou `time.sleep` (monkeypatchável)."""
        (self._sleep or time.sleep)(seconds)

    def _request_embeddings(self, batch: list[str]) -> list[list[float]]:
        if self._kind == "genai":
            client = self._ensure_client()
            response = client.models.embed_contents(
                model=self._model,
                contents=batch,
                output_dimensionality=self._output_dimensionality,
            )
            return [_embedding_values(embedding) for embedding in _response_embeddings(response)]
        # SDK legado: também em lote — UM `embed_content` por batch (D1-P0-3c).
        self._sdk.configure(api_key=self._api_key)
        response = self._sdk.embed_content(
            model=self._model,
            content=batch,
            output_dimensionality=self._output_dimensionality,
        )
        return [_embedding_values(embedding) for embedding in _response_embeddings(response)]

    def _ensure_client(self) -> object:
        if self._client is None:
            # `HttpOptions.timeout` é em milissegundos no SDK google-genai.
            http_options = self._sdk.types.HttpOptions(
                timeout=int(self._timeout_seconds * 1000)
            )
            self._client = self._sdk.Client(api_key=self._api_key, http_options=http_options)
        return self._client


class QdrantVectorIndex:
    """Índice vetorial Qdrant: coleção única `policy_chunks`, distância cosine (D-05).

    Sem retry (D1-P0-1): Docker local + idempotência delete+upsert cobrem
    reprocessamento. Filtros (`policy_id`/`document_id`/`section_name`) vão no
    `query_filter` da própria consulta — nunca em pós-filtro (F-13).

    `client` é opcional (injeção para testes de integração): um
    `QdrantClient(":memory:")`/`path=...` embutido é o MESMO cliente real, só
    que sem servidor — índice vetorial local, ainda mais offline que o Docker.
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        vector_size: int = DEFAULT_VECTOR_SIZE,
        collection_name: str = COLLECTION_NAME,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client import models as qdrant_models
        except ImportError as exc:
            raise RuntimeError(
                "dependência ausente: qdrant-client — instale para usar este adapter"
            ) from exc
        self._models = qdrant_models
        self._client = client if client is not None else QdrantClient(url=url, api_key=api_key)
        self._vector_size = vector_size
        self._collection_name = collection_name

    def ensure_collection(self) -> None:
        """Health-check + criação da coleção; falha externa vira `IndexingError`."""
        try:
            if self._client.collection_exists(self._collection_name):
                return
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=self._models.VectorParams(
                    size=self._vector_size, distance=self._models.Distance.COSINE
                ),
            )
        except Exception as exc:
            raise IndexingError(
                f"falha ao preparar a coleção {self._collection_name} ({type(exc).__name__})"
            ) from exc

    def delete_document(self, document_id: str) -> None:
        try:
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
        except Exception as exc:
            raise IndexingError(
                f"falha ao limpar o documento {document_id} ({type(exc).__name__})"
            ) from exc

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
        try:
            self._client.upsert(collection_name=self._collection_name, points=points)
        except Exception as exc:
            raise IndexingError(
                f"falha ao indexar {len(points)} chunk(s) ({type(exc).__name__})"
            ) from exc

    def search(
        self,
        vector: list[float],
        top_k: int,
        policy_id: str | None = None,
        document_id: str | None = None,
        section_name: str | None = None,
        field_code: str | None = None,
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
        if section_name is not None:
            conditions.append(
                self._models.FieldCondition(
                    key="section_name", match=self._models.MatchValue(value=section_name)
                )
            )
        query_filter = self._models.Filter(must=conditions) if conditions else None

        # Filtro NA consulta (`query_filter`) — nunca pós-filtro (F-13).
        # `field_code` não está no payload v1.0.0; o consumo acontece no texto
        # de busca (`service.compose_search_text`) e o parâmetro é aceito de
        # forma explícita para virar filtro automático quando o campo entrar no
        # payload (caixa postal) — nunca descartado em silêncio (F-14).
        try:
            response = self._client.query_points(
                collection_name=self._collection_name,
                query=list(vector),
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
                with_vectors=True,
            )
        except Exception as exc:
            raise IndexingError(
                f"falha na busca vetorial ({type(exc).__name__})"
            ) from exc
        return [
            ScoredChunk(
                record=_record_from_payload(point.payload, point.vector),
                score=float(point.score),
            )
            for point in response.points
        ]


def _payload_from_record(record: ChunkRecord) -> dict:
    """Payload do Qdrant conforme `data-delta.md` (IDs + texto + origem).

    `content_fingerprint` (contrato v1.1.0) é opcional: chunks legados ou sem
    texto estável gravam `None` e voltam `None` (retrocompatível).
    """
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
        "content_fingerprint": metadata.content_fingerprint,
        "text": record.text,
    }


def _record_from_payload(payload: dict, vector) -> ChunkRecord:
    """Reconstrói o `ChunkRecord` a partir do payload persistido (RF-05).

    `.get` em `content_fingerprint`: payload gravado antes de v1.1.0 não tem a
    chave e continua válido com `None` (F-14: propagação provada ponta a ponta).
    """
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
        content_fingerprint=payload.get("content_fingerprint"),
    )
    return ChunkRecord(
        metadata=metadata,
        text=payload["text"],
        vector=list(vector) if vector is not None else None,
    )
