"""Domínio puro do processamento documental (RF-02 a RF-04).

Contém as constantes de política (D-03/D-04), a classificação de página,
o chunker sequencial com sobreposição e a montagem de `ChunkMetadata`.
Nenhuma dependência externa aqui (RNF-06) — apenas stdlib + pydantic + shared_kernel.
"""

from dataclasses import dataclass

from shared_kernel.contracts import ChunkMetadata, SourceType
from shared_kernel.version import CONTRACTS_VERSION

#: Caracteres não-brancos mínimos para considerar texto nativo suficiente (D-04).
MIN_NATIVE_TEXT_CHARS = 40

#: Confiança de OCR abaixo deste limiar torna a página ilegível (D-04).
OCR_ILLEGIBLE_CONFIDENCE = 0.5

#: Tamanho máximo de um chunk em caracteres (D-03).
CHUNK_MAX_CHARS = 800

#: Sobreposição entre chunks consecutivos em caracteres (D-03).
CHUNK_OVERLAP = 100


@dataclass
class PageText:
    """Texto extraído de uma página; `page_number` começa em 1."""

    page_number: int
    text: str


@dataclass
class ChunkRecord:
    """Chunk pronto para indexação: metadados + texto (+ vetor quando gerado)."""

    metadata: ChunkMetadata
    text: str
    vector: list[float] | None = None


def classify_page(text: str) -> SourceType:
    """Classifica a página pelo texto nativo (RF-02/RF-03).

    Texto nativo suficiente vira `NATIVE_TEXT`; caso contrário a página
    precisa de OCR e recebe `PADDLEOCR`.
    """
    if len(text.strip()) >= MIN_NATIVE_TEXT_CHARS:
        return "NATIVE_TEXT"
    return "PADDLEOCR"


def is_illegible(ocr_confidence: float | None) -> bool:
    """Uma página só é ilegível se teve OCR e a confiança ficou abaixo do limiar."""
    return ocr_confidence is not None and ocr_confidence < OCR_ILLEGIBLE_CONFIDENCE


def chunk_text(
    text: str,
    max_chars: int = CHUNK_MAX_CHARS,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Divide o texto em fatias sequenciais com sobreposição (D-03).

    O último chunk fecha com o restante do texto (sem sobra órfã); fatias
    vazias nunca entram na lista. Texto menor que `max_chars` vira 1 chunk.
    """
    if max_chars <= 0:
        raise ValueError("max_chars deve ser positivo")
    if not 0 <= overlap < max_chars:
        raise ValueError("overlap deve estar no intervalo [0, max_chars)")

    stripped = text.strip()
    if not stripped:
        return []

    chunks: list[str] = []
    step = max_chars - overlap
    start = 0
    while True:
        piece = stripped[start : start + max_chars].strip()
        if piece:
            chunks.append(piece)
        if start + max_chars >= len(stripped):
            break
        start += step
    return chunks


def build_chunk_metadata(
    chunk_id: str,
    document_id: str,
    policy_id: str,
    page_number: int,
    chunk_index: int,
    source_type: SourceType,
    ocr_confidence: float | None,
    section_name: str | None = None,
) -> ChunkMetadata:
    """Monta `ChunkMetadata` versionada (RF-04).

    `section_name` recebe o literal da seção vigente (OQ-03 resolvida pela
    feature dev1-006); o default `None` preserva o comportamento anterior.
    """
    return ChunkMetadata(
        chunk_id=chunk_id,
        document_id=document_id,
        policy_id=policy_id,
        page_number=page_number,
        chunk_index=chunk_index,
        source_type=source_type,
        ocr_confidence=ocr_confidence,
        section_name=section_name,
        metadata_version=CONTRACTS_VERSION,
    )
