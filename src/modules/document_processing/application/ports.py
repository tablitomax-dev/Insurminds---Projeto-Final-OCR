"""Portas do document_processing como `typing.Protocol` (D-02, sem framework de DI).

As implementações reais vivem em `infrastructure/`; os testes usam fakes
determinísticos que satisfazem estruturalmente estes protocolos.

Erros tipados por porta (D1-P0-1): cada adapter traduz o erro externo
(SDK/daemon) para uma das exceções abaixo. As mensagens são SEMPRE
sanitizadas — só tipo do erro, estágio e IDs; nunca texto de apólice (T-2a).
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from shared_kernel.contracts import ProcessingStatus

from ..domain.processing import ChunkRecord, PageText


class PortError(Exception):
    """Erro base das portas do módulo; mensagem sanitizada (T-2a)."""


class TextExtractionError(PortError):
    """Falha na extração de texto do arquivo (porta `TextExtractor`)."""


class OcrError(PortError):
    """Falha no OCR de uma página (porta `OcrEngine`)."""


class EmbeddingError(PortError):
    """Falha na geração de embeddings (porta `Embedder`)."""


class IndexingError(PortError):
    """Falha no índice vetorial (porta `VectorIndex`)."""


class LayoutError(PortError):
    """Falha na análise de layout de uma página (porta `LayoutEngine`)."""


@dataclass
class ScoredChunk:
    """Resultado de busca: chunk recuperado com score de similaridade."""

    record: ChunkRecord
    score: float


@dataclass
class LayoutRegion:
    """Região normalizada da análise de layout (feature dev1-006, NG-01).

    `kind`: `heading` (título/seção), `table` (TSV — linhas separadas por `\\n`
    e células por `\\t`) ou `text` (trecho corrido). `order` é a ordem de
    leitura da região na página. Saída do adapter, NÃO é contrato externo.
    """

    kind: Literal["heading", "table", "text"]
    text: str
    order: int


class TextExtractor(Protocol):
    """Extrai o texto nativo de cada página do arquivo (ordem do documento)."""

    def extract_pages(self, file_path: str) -> list[PageText]: ...


class OcrEngine(Protocol):
    """Aplica OCR a uma página; devolve (texto, confiança média em [0,1])."""

    def ocr_page(self, file_path: str, page_number: int) -> tuple[str, float | None]: ...


class LayoutEngine(Protocol):
    """Analisa o layout de uma página; devolve regiões em ordem de leitura.

    Erro externo vira `LayoutError` sanitizado (T-2a). O serviço degrada para
    texto puro quando o motor está ausente ou falha (RN-05 da dev1-006).
    """

    def analyze_page(self, file_path: str, page_number: int) -> list[LayoutRegion]: ...


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
        section_name: str | None = None,
        field_code: str | None = None,
    ) -> list[ScoredChunk]:
        """Busca por similaridade com os filtros aplicados NA consulta (F-13).

        - `policy_id`/`document_id`/`section_name`: filtros de metadata do
          payload, aplicados na própria consulta (nunca em pós-filtro).
        - `field_code`: hint determinístico de campo (F-14). O payload do chunk
          (contrato v1.0.0) não persiste `field_code`, então o consumo efetivo
          acontece na composição do texto de busca (`service.compose_search_text`);
          o parâmetro é propagado explicitamente até a porta para permitir filtro
          automático quando o campo entrar no payload — nunca descartado em silêncio.
        """
        ...


class StatusSink(Protocol):
    """Publica o `ProcessingStatus` de cada transição de estágio (RF-06)."""

    def publish(self, status: ProcessingStatus) -> None: ...
