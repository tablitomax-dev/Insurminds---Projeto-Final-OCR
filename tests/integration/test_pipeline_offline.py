"""Integração opt-in do pipeline documental sobre as fixtures (D1-P1-2b).

Roda com `python -B -m pytest -q -p no:cacheprovider -m integration`, **sem
internet** — a rede de embeddings é a única externa e é substituída por fake.

Declaração explícita de real vs fake (RN-03):
- **REAL:** extração de texto (PyMuPDF), OCR (PaddleOCR, só no "escaneado"),
  domínio (classificação de página, chunking, metadados, fingerprint) e índice
  vetorial Qdrant (servidor local via Docker **ou** modo embutido `:memory:`
  do próprio `qdrant-client` — cliente real, sem servidor; ambos offline).
- **FAKE:** apenas o `Embedder` (`FakeEmbedder`, vetor determinístico por
  hashing de token). Nada mais é falso.

Roda com `INTEGRATION_QDRANT_URL=:memory:` (sem Docker) ou com a URL de um
Qdrant local. Pulado graciosamente quando falta dependência (padrão D-10):
`fitz`, `paddleocr` e `qdrant-client` são extras de integração
(`requirements.txt`).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fakes.document_processing import FakeEmbedder, RecordingStatusSink
from modules.document_processing.domain.chunk_fingerprint import compute_content_fingerprint
from shared_kernel.contracts import RetrievalQuery

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
DIGITAL = FIXTURES / "aplice_digital.pdf"
ESCANEADO = FIXTURES / "aplice_escaneada.pdf"

#: Mesma dimensionalidade do `FakeEmbedder` (só o Embedder é fake — RN-03).
VECTOR_SIZE = 32


def _pipeline():
    """Pipeline REAL contra o Qdrant local; fake apenas do `Embedder`.

    Imports lazy (padrão de `test_adapters_reais.py`): os adapters não podem
    ficar em `sys.modules` — o teste de arquitetura vigia a importabilidade da
    fachada sem dependências externas.
    """
    pytest.importorskip("fitz", reason="PyMuPDF não instalado (extras de integração)")
    pytest.importorskip("paddleocr", reason="PaddleOCR não instalado (extras de integração)")
    pytest.importorskip("qdrant_client", reason="qdrant-client não instalado (extras de integração)")
    from qdrant_client import QdrantClient

    from modules.document_processing.application.service import DocumentProcessingService
    from modules.document_processing.infrastructure.extractors import (
        PaddleOcrEngine,
        PyMuPdfTextExtractor,
    )
    from modules.document_processing.infrastructure.indexing import QdrantVectorIndex

    alvo = os.environ["INTEGRATION_QDRANT_URL"]
    if alvo == ":memory:":
        # Índice REAL em modo embutido do qdrant-client: sem servidor/Docker.
        index = QdrantVectorIndex(vector_size=VECTOR_SIZE, client=QdrantClient(":memory:"))
    else:
        index = QdrantVectorIndex(url=alvo, vector_size=VECTOR_SIZE)
    service = DocumentProcessingService(
        text_extractor=PyMuPdfTextExtractor(),  # REAL
        ocr_engine=PaddleOcrEngine(),  # REAL
        embedder=FakeEmbedder(dimensions=VECTOR_SIZE),  # FAKE (única externa)
        vector_index=index,  # REAL (Qdrant local)
        status_sink=RecordingStatusSink(),
    )
    return service, index


def _records_do_documento(index, policy_id: str):
    """Recupera pelo caminho real de busca os chunks indexados do documento."""
    vector = FakeEmbedder(dimensions=VECTOR_SIZE).embed_texts(["apólice D&O"])[0]
    return [scored.record for scored in index.search(vector, top_k=20, policy_id=policy_id)]


def _skip_se_limitacao_conhecida_do_paddle():
    """Pula SÓ na limitação do PaddlePaddle no Windows/CPU (executor PIR/oneDNN:
    `NotImplementedError` interno de runtime); qualquer outra causa de OCR falha
    como falha real do pipeline."""
    from modules.document_processing.application.ports import OcrError
    from modules.document_processing.infrastructure.extractors import PaddleOcrEngine

    try:
        PaddleOcrEngine(lang="pt").ocr_page(str(ESCANEADO), 1)
    except OcrError as exc:
        if isinstance(exc.__cause__, NotImplementedError):
            pytest.skip(
                "PaddlePaddle neste ambiente falha no executor PIR/oneDNN "
                "(Windows/CPU, NotImplementedError interno de runtime) — "
                "rodar o caso do 'escaneado' em Linux/CI"
            )
        raise


@pytest.mark.skipif(
    os.environ.get("INTEGRATION_QDRANT_URL") is None,
    reason="defina INTEGRATION_QDRANT_URL para o Qdrant local (Docker)",
)
def test_digital_pipeline_real_indexa_chunk_com_fingerprint_confere():
    service, index = _pipeline()

    status = service.process_document("doc_fp_digital", "pol_fp_digital", str(DIGITAL))

    assert status.stage == "INDEXED"
    # caminho real de recuperação de evidências (jornada ponta a ponta)
    result = service.retrieve_evidence(
        RetrievalQuery(query="Limite Agregado", policy_id="pol_fp_digital", top_k=5)
    )
    assert result.evidences
    records = _records_do_documento(index, "pol_fp_digital")
    assert records
    for record in records:
        assert record.metadata.source_type == "NATIVE_TEXT"  # sem caminho de OCR
        # RF-02: fingerprint recuperado confere com o sha256 do texto recuperado
        assert record.metadata.content_fingerprint == compute_content_fingerprint(record.text)


@pytest.mark.skipif(
    os.environ.get("INTEGRATION_QDRANT_URL") is None,
    reason="defina INTEGRATION_QDRANT_URL para o Qdrant local (Docker)",
)
def test_escaneado_pipeline_real_passa_pelo_caminho_de_ocr():
    service, index = _pipeline()

    status = service.process_document("doc_fp_escaneado", "pol_fp_escaneado", str(ESCANEADO))

    if status.stage == "FAILED" and "OCR:" in (status.message or ""):
        _skip_se_limitacao_conhecida_do_paddle()
    # fixture sem camada de texto: o pipeline a trata pelo caminho de OCR
    assert status.stage in ("INDEXED", "REVIEW_REQUIRED")
    records = _records_do_documento(index, "pol_fp_escaneado")
    assert records
    for record in records:
        assert record.metadata.source_type == "PADDLEOCR"
        assert record.metadata.content_fingerprint == compute_content_fingerprint(record.text)
