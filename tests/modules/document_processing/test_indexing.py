"""Testes dos adapters de indexação com SDKs/daemon falsos (D1-P0-1, D1-P0-3).

- Gemini: retry com backoff SÓ em transitórios, timeout por chamada, lote de
  até 100 textos por request e caminho em lote também no SDK legado.
- Qdrant: `query_filter` na consulta (com `QdrantClient` mockado), SEM retry,
  erro externo traduzido para `IndexingError`.
"""

import importlib
import sys
import types
from dataclasses import dataclass, field

import pytest

from modules.document_processing.application.ports import EmbeddingError, IndexingError
from modules.document_processing.domain.chunk_fingerprint import compute_content_fingerprint
from modules.document_processing.domain.processing import ChunkRecord, build_chunk_metadata

#: Texto de apólice que NUNCA pode aparecer em mensagem de erro (T-2a).
POLICY_TEXT = "Limite agregado R$ 1.000.000"


class ServiceUnavailable(Exception):
    """Erro externo transitório (503) simulado dos SDKs Google/Qdrant."""

    code = 503


class InvalidArgument(Exception):
    """Erro externo definitivo simulado dos SDKs (não é transitório)."""

    code = 400


@pytest.fixture()
def indexing():
    """Importa `infrastructure.indexing` sem deixá-lo em `sys.modules` depois.

    O teste de arquitetura exige que o módulo de adapters não seja importado
    pelo núcleo; o teardown preserva essa garantia independente da ordem.
    """
    module = importlib.import_module("modules.document_processing.infrastructure.indexing")
    yield module
    sys.modules.pop("modules.document_processing.infrastructure.indexing", None)


# --------------------------------------------------- fakes do SDK Gemini


class _FakeHttpOptions:
    def __init__(self, timeout=None):
        self.timeout = timeout


class _FakeEmbedding:
    def __init__(self, values):
        self.values = values


def _response_for(texts):
    """Resposta determinística: vetor derivado do tamanho do texto."""
    return types.SimpleNamespace(embeddings=[_FakeEmbedding([float(len(text))]) for text in texts])


class _FakeGenaiSdk:
    """Subconjunto do SDK `google-genai` usado pelo `GeminiEmbedder`."""

    def __init__(self, failures=()):
        self.types = types.SimpleNamespace(HttpOptions=_FakeHttpOptions)
        self.failures = list(failures)
        self.calls = []
        self.client_init_calls = []

    def Client(self, **kwargs):
        self.client_init_calls.append(kwargs)
        sdk = self

        class _Models:
            def embed_contents(self, **kwargs):
                sdk.calls.append(kwargs)
                if sdk.failures:
                    raise sdk.failures.pop(0)
                return _response_for(kwargs["contents"])

        return types.SimpleNamespace(models=_Models())


class _FakeLegacySdk:
    """Subconjunto do SDK `google-generativeai` (caminho legado do adapter)."""

    def __init__(self, failures=()):
        self.failures = list(failures)
        self.configure_calls = []
        self.calls = []

    def configure(self, **kwargs):
        self.configure_calls.append(kwargs)

    def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.failures:
            raise self.failures.pop(0)
        return {"embeddings": [{"values": [float(len(text))]} for text in kwargs["content"]]}


def _make_embedder(indexing, sdk, kind, sleeps, **kwargs):
    return indexing.GeminiEmbedder(
        api_key="chave-fake",
        output_dimensionality=8,
        sdk_bundle=(kind, sdk),
        sleep=sleeps.append,
        **kwargs,
    )


# ------------------------------- D1-P0-1: retry/backoff só no Gemini (RF-01)


def test_gemini_fails_twice_and_succeeds_on_third_with_backoff(indexing):
    sdk = _FakeGenaiSdk(failures=[ServiceUnavailable("503"), ServiceUnavailable("503")])
    sleeps = []
    embedder = _make_embedder(indexing, sdk, "genai", sleeps)

    vectors = embedder.embed_texts(["a", "bb"])

    assert vectors == [[1.0], [2.0]]
    assert len(sdk.calls) == 3  # 2 falhas + 1 sucesso
    assert sleeps == [1.0, 2.0]  # backoff exponencial 1s -> 2s (sem atrasar o teste)


def test_gemini_gives_up_after_max_attempts_on_transient_error(indexing):
    sdk = _FakeGenaiSdk(failures=[ServiceUnavailable("503")] * 3)
    sleeps = []
    embedder = _make_embedder(indexing, sdk, "genai", sleeps)

    with pytest.raises(EmbeddingError):
        embedder.embed_texts(["a"])

    assert len(sdk.calls) == 3  # EMBEDDING_MAX_ATTEMPTS
    assert sleeps == [1.0, 2.0]


def test_gemini_does_not_retry_non_transient_error(indexing):
    sdk = _FakeGenaiSdk(failures=[InvalidArgument("400")])
    sleeps = []
    embedder = _make_embedder(indexing, sdk, "genai", sleeps)

    with pytest.raises(EmbeddingError):
        embedder.embed_texts(["a"])

    assert len(sdk.calls) == 1  # erro definitivo NÃO é repetido
    assert sleeps == []


def test_gemini_external_error_becomes_typed_port_error_without_leaking_text(indexing):
    sdk = _FakeGenaiSdk(failures=[InvalidArgument(f"requisição inválida: {POLICY_TEXT}")])
    embedder = _make_embedder(indexing, sdk, "genai", [])

    with pytest.raises(EmbeddingError) as excinfo:
        embedder.embed_texts(["a"])

    message = str(excinfo.value)
    assert POLICY_TEXT not in message  # nunca o texto da exceção (T-2a)
    assert "InvalidArgument" in message  # só o tipo do erro externo


def test_gemini_timeout_is_transient_and_http_options_get_30s(indexing):
    sdk = _FakeGenaiSdk(failures=[TimeoutError("deadline")])
    sleeps = []
    embedder = _make_embedder(indexing, sdk, "genai", sleeps)

    assert embedder.embed_texts(["a"]) == [[1.0]]
    assert len(sdk.calls) == 2
    assert sleeps == [1.0]
    # timeout por chamada: 30s em milissegundos (unidade do `HttpOptions`)
    assert sdk.client_init_calls[0]["http_options"].timeout == 30_000


@pytest.mark.parametrize(
    ("error", "transient"),
    [
        (ServiceUnavailable("503"), True),
        (TimeoutError("deadline"), True),
        (ConnectionError("reset"), True),
        (type("TooManyRequests", (Exception,), {"code": 429})("429"), True),
        (InvalidArgument("400"), False),
        (ValueError("formato"), False),
    ],
)
def test_is_transient_error_classification(indexing, error, transient):
    assert indexing.is_transient_error(error) is transient


def test_embed_texts_empty_returns_empty_without_requests(indexing):
    sdk = _FakeGenaiSdk()
    embedder = _make_embedder(indexing, sdk, "genai", [])

    assert embedder.embed_texts([]) == []
    assert sdk.calls == []


# -------------------------- D1-P0-3b/c: lote de até 100, sem loop por texto


def test_gemini_splits_large_batch_into_requests_of_at_most_100_texts(indexing):
    sdk = _FakeGenaiSdk()
    embedder = _make_embedder(indexing, sdk, "genai", [])
    texts = [f"texto-{index}" for index in range(250)]

    vectors = embedder.embed_texts(texts)

    assert [len(call["contents"]) for call in sdk.calls] == [100, 100, 50]
    assert [call["contents"] for call in sdk.calls] == [texts[:100], texts[100:200], texts[200:]]
    assert len(vectors) == 250
    assert [vector[0] for vector in vectors] == [float(len(text)) for text in texts]


def test_gemini_makes_one_request_per_batch_not_per_text(indexing):
    sdk = _FakeGenaiSdk()
    embedder = _make_embedder(indexing, sdk, "genai", [])

    embedder.embed_texts(["um", "dois", "tres"])

    assert len(sdk.calls) == 1
    assert sdk.calls[0]["contents"] == ["um", "dois", "tres"]


def test_legacy_sdk_also_uses_single_batch_request(indexing):
    """Caminho legado sem loop por texto: UM `embed_content` por lote (D1-P0-3c)."""
    sdk = _FakeLegacySdk()
    embedder = _make_embedder(indexing, sdk, "generativeai", [])

    vectors = embedder.embed_texts(["um", "dois", "tres"])

    assert len(sdk.calls) == 1
    assert sdk.calls[0]["content"] == ["um", "dois", "tres"]
    assert len(vectors) == 3


# --------------------------------------- fakes do cliente Qdrant (mockado)


@dataclass
class _MatchValue:
    value: object


@dataclass
class _FieldCondition:
    key: str
    match: object


@dataclass
class _Filter:
    must: list = field(default_factory=list)


@dataclass
class _VectorParams:
    size: int
    distance: object


@dataclass
class _PointStruct:
    id: str
    vector: list
    payload: dict


class _Distance:
    COSINE = "Cosine"


@pytest.fixture()
def qdrant(monkeypatch, indexing):
    """`QdrantVectorIndex` com `QdrantClient` mockado (sem Docker)."""
    state = types.SimpleNamespace(
        exists=True,
        error=None,
        query_calls=[],
        upsert_calls=[],
        delete_calls=[],
        created_collections=[],
    )

    class _QdrantClient:
        def __init__(self, **kwargs):
            state.init_kwargs = kwargs

        def collection_exists(self, name):
            if state.error is not None:
                raise state.error
            return state.exists

        def create_collection(self, **kwargs):
            if state.error is not None:
                raise state.error
            state.created_collections.append(kwargs)

        def delete(self, **kwargs):
            if state.error is not None:
                raise state.error
            state.delete_calls.append(kwargs)

        def upsert(self, **kwargs):
            if state.error is not None:
                raise state.error
            state.upsert_calls.append(kwargs)

        def query_points(self, **kwargs):
            state.query_calls.append(kwargs)
            if state.error is not None:
                raise state.error
            return types.SimpleNamespace(points=[])

    fake_module = types.ModuleType("qdrant_client")
    fake_module.QdrantClient = _QdrantClient
    fake_module.models = types.SimpleNamespace(
        FieldCondition=_FieldCondition,
        MatchValue=_MatchValue,
        Filter=_Filter,
        VectorParams=_VectorParams,
        PointStruct=_PointStruct,
        Distance=_Distance,
    )
    monkeypatch.setitem(sys.modules, "qdrant_client", fake_module)
    vector_index = indexing.QdrantVectorIndex(url="http://fake:6333", vector_size=2)
    return types.SimpleNamespace(index=vector_index, state=state)


# --------------------------- D1-P0-3a: query_filter chega em query_points


def test_qdrant_query_filter_with_all_metadata_reaches_query_points(qdrant):
    qdrant.index.search(
        [0.1, 0.2],
        top_k=3,
        policy_id="pol-1",
        document_id="doc-1",
        section_name="Coberturas",
        field_code="limite_agregado",
    )

    call = qdrant.state.query_calls[0]
    query_filter = call["query_filter"]
    matches = {condition.key: condition.match.value for condition in query_filter.must}
    # filtros de metadata NA consulta (nunca em pós-filtro)
    assert matches == {
        "policy_id": "pol-1",
        "document_id": "doc-1",
        "section_name": "Coberturas",
    }
    assert call["query"] == [0.1, 0.2]
    assert call["limit"] == 3


def test_qdrant_search_without_filters_passes_none_query_filter(qdrant):
    qdrant.index.search([0.1, 0.2], top_k=5)

    assert qdrant.state.query_calls[0]["query_filter"] is None


# ------------------------------- D1-P0-1: sem retry no Qdrant + erro tipado


def test_qdrant_does_not_retry_on_transient_error(qdrant):
    qdrant.state.error = ServiceUnavailable("503")

    with pytest.raises(IndexingError):
        qdrant.index.search([0.1, 0.2], top_k=3)

    assert len(qdrant.state.query_calls) == 1  # retry no Qdrant: cortado


def test_qdrant_external_error_becomes_indexing_error_without_leaking_text(qdrant):
    qdrant.state.error = ServiceUnavailable(f"daemon respondeu: {POLICY_TEXT}")

    with pytest.raises(IndexingError) as excinfo:
        qdrant.index.search([0.1, 0.2], top_k=3)

    message = str(excinfo.value)
    assert POLICY_TEXT not in message  # nunca o texto da exceção (T-2a)
    assert "ServiceUnavailable" in message


def test_qdrant_ensure_collection_failure_is_indexing_error(qdrant):
    qdrant.state.error = ServiceUnavailable("503")

    with pytest.raises(IndexingError):
        qdrant.index.ensure_collection()

    assert qdrant.state.created_collections == []


# ----------------- D1-P1-1d: round-trip do content_fingerprint (v1.1.0)


def _record_com_fingerprint(text="Limite agregado da apólice"):
    """Chunk como o pipeline monta: fingerprint = sha256 do texto do chunk."""
    metadata = build_chunk_metadata(
        chunk_id="doc_fp:p1:c0",
        document_id="doc_fp",
        policy_id="pol_fp",
        page_number=1,
        chunk_index=0,
        source_type="NATIVE_TEXT",
        ocr_confidence=None,
    )
    metadata.content_fingerprint = compute_content_fingerprint(text)
    return ChunkRecord(metadata=metadata, text=text, vector=[0.1, 0.2])


def test_round_trip_gravar_recuperar_confere_sha256_do_texto(qdrant, indexing):
    record = _record_com_fingerprint()

    qdrant.index.upsert_chunks([record])
    point = qdrant.state.upsert_calls[0]["points"][0]
    assert point.payload["content_fingerprint"] == record.metadata.content_fingerprint

    restored = indexing._record_from_payload(point.payload, point.vector)
    # RF-02: o resumo recuperado confere com o sha256 do texto recuperado
    assert restored.metadata.content_fingerprint == compute_content_fingerprint(restored.text)
    assert restored.text == record.text


def test_payload_legado_sem_content_fingerprint_volta_none(indexing):
    record = _record_com_fingerprint()
    payload = indexing._payload_from_record(record)
    payload.pop("content_fingerprint")  # chunk gravado antes de v1.1.0

    restored = indexing._record_from_payload(payload, record.vector)

    assert restored.metadata.content_fingerprint is None  # retrocompatível
    assert restored.text == record.text
