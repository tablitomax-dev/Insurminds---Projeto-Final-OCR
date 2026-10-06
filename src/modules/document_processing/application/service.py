"""Orquestração do processamento documental (RF-01 a RF-09).

`DocumentProcessingService` coordena as portas (extração, OCR, embeddings,
índice e status) sem conhecer as implementações — núcleo testável com fakes.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shared_kernel.contracts import (
    EvidenceRef,
    ProcessingStatus,
    RetrievalQuery,
    RetrievalResult,
    SourceType,
)

from ..domain.chunk_fingerprint import compute_content_fingerprint
from ..domain.processing import (
    ChunkRecord,
    PageText,
    build_chunk_metadata,
    chunk_text,
    classify_page,
    is_illegible,
)
from ..domain.structure import assign_sections, compose_page_text
from .ports import Embedder, LayoutEngine, OcrEngine, StatusSink, TextExtractor, VectorIndex

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

#: Formato determinístico do hint de `field_code` no texto de busca (F-14).
FIELD_CODE_HINT_TEMPLATE = "\n[campo: {field_code}]"


def compose_search_text(query_text: str, field_code: str | None) -> str:
    """Compõe o texto de busca de forma determinística (F-14, D1-P0-2).

    `field_code` não existe no payload do chunk (contrato v1.0.0), então é
    consumido como hint semântico concatenado ao final da consulta, no formato
    fixo `FIELD_CODE_HINT_TEMPLATE` — mesma entrada, mesmo texto de busca.
    """
    if not field_code:
        return query_text
    return query_text + FIELD_CODE_HINT_TEMPLATE.format(field_code=field_code)


@dataclass
class PageMarkdown:
    """Markdown estruturado de uma página, com a origem do conteúdo.

    `source_type` registra de onde veio o markdown: `PP_STRUCTURE` (markdown
    nativo do motor de layout), `NATIVE_TEXT` (texto nativo da página) ou
    `PADDLEOCR` (resultado do OCR).
    """

    page_number: int
    markdown: str
    source_type: SourceType


class DocumentProcessingService:
    """Pipeline: validar → extrair → OCR → chunkar → embeddar → indexar (RF-01..RF-06)."""

    def __init__(
        self,
        text_extractor: TextExtractor,
        ocr_engine: OcrEngine,
        embedder: Embedder,
        vector_index: VectorIndex,
        status_sink: StatusSink,
        layout_engine: LayoutEngine | None = None,
        max_pdf_bytes: int = MAX_PDF_BYTES,
    ) -> None:
        self._text_extractor = text_extractor
        self._ocr_engine = ocr_engine
        self._embedder = embedder
        self._vector_index = vector_index
        self._status_sink = status_sink
        self._layout_engine = layout_engine
        self._max_pdf_bytes = max_pdf_bytes
        # Caches por instância (`file_path` → página → resultado): OCR e
        # markdown por página rodam no máximo uma vez para a mesma página —
        # processamento, preview e markdown compartilham o mesmo resultado.
        self._ocr_cache: dict[str, dict[int, tuple[str, float | None]]] = {}
        self._page_markdown_cache: dict[str, dict[int, PageMarkdown]] = {}

    def process_document(
        self,
        document_id: str,
        policy_id: str,
        file_path: str,
        layout_mode: Literal["scanned", "all"] = "scanned",
    ) -> ProcessingStatus:
        """Processa um PDF de apólice ponta a ponta e publica cada estágio (RF-06).

        `layout_mode` (dev1-006): `"scanned"` analisa o layout só de páginas
        sem texto nativo suficiente; `"all"` estende a todas. Sem motor de
        layout ou em falha, o fluxo degrada para o texto extraído (RN-05).
        """
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
                    text, ocr_confidence = page.text, None
                else:
                    text, ocr_confidence = self._ocr_cached(file_path, page.page_number)
                    ocr_page_numbers.append(page.page_number)
                # Layout (dev1-006): análise estrutural da página; degrada
                # silenciosamente para o texto já extraído (RN-05).
                if self._layout_engine is not None and (
                    layout_mode == "all" or source_type != "NATIVE_TEXT"
                ):
                    composed = self._layout_page_text(file_path, page.page_number)
                    if composed:
                        text, source_type = composed, "PP_STRUCTURE"
                extracted.append((page.page_number, text, source_type, ocr_confidence))
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
        # Seção vigente atravessa páginas: literal do marcador (dev1-006, RN-02).
        current_section: str | None = None
        for page_number, text, source_type, ocr_confidence in extracted:
            if is_illegible(ocr_confidence):
                illegible_pages.append(page_number)
            pieces = chunk_text(text)
            sections, current_section = assign_sections(pieces, current_section)
            for chunk_index, (chunk, section_name) in enumerate(zip(pieces, sections)):
                chunk_id = f"{document_id}:p{page_number}:c{chunk_index}"
                metadata = build_chunk_metadata(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    policy_id=policy_id,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    source_type=source_type,
                    ocr_confidence=ocr_confidence,
                    section_name=section_name,
                )
                # Proveniência (contrato v1.1.0): sha256 do texto do chunk.
                metadata.content_fingerprint = compute_content_fingerprint(chunk)
                records.append(ChunkRecord(metadata=metadata, text=chunk))

        try:
            # Health-check da coleção antes de gastar embeddings (D1-P0-3d).
            self._vector_index.ensure_collection()
            vectors = self._embedder.embed_texts([record.text for record in records])
            for record, vector in zip(records, vectors):
                record.vector = vector
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
        """Recupera evidências ranqueadas (RF-07); lista vazia é resposta válida (EC-07).

        Honra TODOS os campos de `RetrievalQuery` (F-14): `policy_id`,
        `document_id` e `section_name` viram filtros de metadata na consulta e
        `field_code` vira hint determinístico no texto de busca
        (`compose_search_text`) — nada é descartado em silêncio.
        """
        search_text = compose_search_text(query.query, query.field_code)
        vector = self._embedder.embed_texts([search_text])[0]
        scored_chunks = self._vector_index.search(
            vector,
            top_k=query.top_k,
            policy_id=query.policy_id,
            document_id=query.document_id,
            section_name=query.section_name,
            field_code=query.field_code,
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

    def extract_preview_pages(self, file_path: str, max_pages: int = 2) -> list[str]:
        """Preview das primeiras páginas: OCR/visão primeiro + texto nativo.

        O OCR roda sempre (a visão capta logo/cabeçalho que o texto nativo
        perde) e cada bloco é marcado com a origem (`[OCR/visão]`,
        `[texto nativo]`) para o consumidor priorizar a visão. Página ilegível
        vira string vazia — o preview degrada e nunca falha o fluxo (EC-04).
        O OCR sai do cache compartilhado com `extract_markdown_pages`: roda no
        máximo uma vez por página na mesma instância do serviço.
        """
        pages = self._text_extractor.extract_pages(file_path)[:max_pages]
        texts: list[str] = []
        for page in pages:
            ocr_text = ""
            try:
                ocr_text, _ = self._ocr_cached(file_path, page.page_number)
            except Exception:  # noqa: BLE001 — preview degrada, nunca quebra
                ocr_text = ""
            parts: list[str] = []
            if ocr_text.strip():
                parts.append(f"[OCR/visão]\n{ocr_text.strip()}")
            if (page.text or "").strip():
                parts.append(f"[texto nativo]\n{page.text.strip()}")
            texts.append("\n".join(parts))
        return texts

    def extract_markdown_pages(
        self, file_path: str, max_pages: int | None = None
    ) -> list[PageMarkdown]:
        """Markdown estruturado de cada página, em ordem de leitura.

        Por página, a origem é decidida nesta ordem:
        1. markdown nativo do motor de layout (`PP_STRUCTURE`) — quando existe
           `analyze_page_markdown` (duck-typed, fakes antigos continuam válidos)
           e o motor devolve conteúdo;
        2. texto nativo suficiente (`NATIVE_TEXT`, `classify_page`);
        3. OCR (`PADDLEOCR`), com o resultado no cache compartilhado.

        `max_pages` limita às primeiras páginas; `None` devolve todas. Falha de
        layout/OCR degrada para o texto disponível, sem derrubar o fluxo
        (RN-05/EC-04). O cache por instância garante que OCR e markdown por
        página rodam no máximo uma vez — processamento e preview compartilham
        o mesmo resultado.
        """
        pages = self._text_extractor.extract_pages(file_path)
        if max_pages is not None:
            pages = pages[:max_pages]
        results: list[PageMarkdown] = []
        cache = self._page_markdown_cache.setdefault(file_path, {})
        for page in pages:
            cached = cache.get(page.page_number)
            if cached is not None:
                results.append(cached)
                continue
            result = self._page_markdown(file_path, page)
            cache[page.page_number] = result
            results.append(result)
        return results

    def _page_markdown(self, file_path: str, page: PageText) -> PageMarkdown:
        """Resolve o markdown de uma página na ordem layout → nativo → OCR."""
        markdown = self._layout_page_markdown(file_path, page.page_number)
        if markdown:
            return PageMarkdown(
                page_number=page.page_number,
                markdown=markdown,
                source_type="PP_STRUCTURE",
            )
        native = (page.text or "").strip()
        if classify_page(page.text) == "NATIVE_TEXT":
            return PageMarkdown(
                page_number=page.page_number,
                markdown=native,
                source_type="NATIVE_TEXT",
            )
        try:
            ocr_text, _ = self._ocr_cached(file_path, page.page_number)
        except Exception:  # noqa: BLE001 — leitura degrada, nunca quebra (EC-04)
            return PageMarkdown(
                page_number=page.page_number,
                markdown=native,
                source_type="NATIVE_TEXT",
            )
        return PageMarkdown(
            page_number=page.page_number,
            markdown=(ocr_text or "").strip(),
            source_type="PADDLEOCR",
        )

    def _layout_page_markdown(self, file_path: str, page_number: int) -> str | None:
        """Markdown da página pelo motor de layout; `None` = degradação (RN-05).

        Duck-typed: motores sem `analyze_page_markdown` (ex.: fakes antigos)
        continuam válidos e mandam o fluxo para texto nativo/OCR. Nenhum texto
        de apólice sai daqui em log/mensagem (T-2a).
        """
        analyze_page_markdown = getattr(self._layout_engine, "analyze_page_markdown", None)
        if analyze_page_markdown is None:
            return None
        try:
            markdown = analyze_page_markdown(file_path, page_number)
        except Exception:  # RN-05: qualquer falha do motor degrada para texto puro
            return None
        if isinstance(markdown, str) and markdown.strip():
            return markdown.strip()
        return None

    def _ocr_cached(self, file_path: str, page_number: int) -> tuple[str, float | None]:
        """Resultado do OCR da página, cacheado por instância (roda uma vez).

        Processamento, preview e extração de markdown compartilham este cache;
        falhas NÃO são cacheadas — a exceção propaga e a próxima chamada tenta
        de novo (recuperação bem-sucedida é sempre reproduzível).
        """
        cache = self._ocr_cache.setdefault(file_path, {})
        if page_number not in cache:
            cache[page_number] = self._ocr_engine.ocr_page(file_path, page_number)
        return cache[page_number]

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

    def _layout_page_text(self, file_path: str, page_number: int) -> str | None:
        """Analisa o layout da página e compõe o texto estruturado (dev1-006).

        `None` = degradação (RN-05): motor ausente/falho mantém o texto já
        extraído — a falha do motor nunca derruba o processamento. Nenhum
        texto de apólice sai daqui em log/mensagem (T-2a).
        """
        if self._layout_engine is None:
            return None
        try:
            regions = self._layout_engine.analyze_page(file_path, page_number)
        except Exception:  # RN-05: qualquer falha do motor degrada para texto puro
            return None
        composed = compose_page_text(regions)
        return composed or None

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
    """Causa sanitizada da falha: só o tipo da exceção (EC-04/T-2a).

    NUNCA `str(exc)` — a mensagem de exceção pode conter texto de apólice.
    O estágio (`EXTRACT:`/`OCR:`/`INDEXING:`) entra na montagem da mensagem e
    os IDs já vão no próprio `ProcessingStatus`.
    """
    return type(exc).__name__


def _clamp01(value: float) -> float:
    """Normaliza o score de recuperação para o intervalo [0,1] do contrato (RF-07)."""
    return max(0.0, min(1.0, float(value)))
