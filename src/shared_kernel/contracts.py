"""Contratos compartilhados entre módulos (resumo executivo §8.2–8.5).

Dev 1 produz `EvidenceRef` (document_processing). Dev 2 consome `EvidenceRef`
e produz `ExtractedFact` (policy_analysis). `ProcessingStatus` coordena o
workflow; `ChunkMetadata` é a zona de integração dos metadados de chunks.

Regras do pacote:
- Apenas stdlib + pydantic (RF-10).
- Todos os modelos são fechos: campos desconhecidos são rejeitados
  (`extra="forbid"`) — payload fora do contrato falha na fronteira (RNF-01).
- Toda mudança MAJOR exige revisão dos dois desenvolvedores.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Origem do texto que gerou a evidência (PP_STRUCTURE reservado para a fase posterior).
SourceType = Literal["NATIVE_TEXT", "PADDLEOCR", "PP_STRUCTURE"]

#: Status de um fato extraído.
FactStatus = Literal["FOUND", "NOT_FOUND", "AMBIGUOUS", "NEEDS_REVIEW"]

#: Estágios do workflow de processamento de documento (resumo §8.5).
ProcessingStage = Literal[
    "RECEIVED",
    "TEXT_EXTRACTED",
    "OCR_COMPLETED",
    "INDEXED",
    "FACTS_EXTRACTED",
    "REVIEW_REQUIRED",
    "COMPLETED",
    "FAILED",
]

_FORBID = ConfigDict(extra="forbid")


class EvidenceRef(BaseModel):
    """Referência de evidência: aponta um fato para sua origem no documento.

    Todo fato extraído deve apontar para evidência (resumo §2.5). Campos que
    o pipeline ainda não fornece ficam `None` (ex.: `clause_number`).
    """

    model_config = _FORBID

    evidence_id: str
    policy_id: str
    document_id: str
    page_number: int = Field(ge=1)
    chunk_id: str | None = None
    section_name: str | None = None
    clause_number: str | None = None
    quoted_text: str = Field(min_length=1)
    retrieval_score: float | None = Field(default=None, ge=0, le=1)
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    source_type: SourceType


class ChunkMetadata(BaseModel):
    """Metadados de chunk indexado (zona de integração 2, contrato versionado).

    Proposta da spec shared-kernel-contracts (RF-06) — OQ-01 a validar com o
    Dev 2 (p.ex. `char_offset`, `token_count` podem entrar como opcional em
    MINOR).
    """

    model_config = _FORBID

    chunk_id: str
    document_id: str
    policy_id: str
    page_number: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    source_type: SourceType
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    section_name: str | None = None
    metadata_version: str = Field(min_length=1)


class RetrievalQuery(BaseModel):
    """Consulta de evidências pelo módulo de análise (resumo §8.3)."""

    model_config = _FORBID

    query: str = Field(min_length=1)
    policy_id: str | None = None
    document_id: str | None = None
    section_name: str | None = None
    field_code: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalResult(BaseModel):
    """Resposta do retrieval: evidências ranqueadas para a consulta.

    `evidences=[]` é válido — significa "nada encontrado", e o consumidor
    registra `ExtractedFact(status="NOT_FOUND")` (fluxo alternativo A).
    """

    model_config = _FORBID

    query: RetrievalQuery
    evidences: list[EvidenceRef]
    retrieval_run_id: str = Field(min_length=1)


class ExtractionRequest(BaseModel):
    """Pedido de extração de um campo, com as evidências recuperadas (§8.4)."""

    model_config = _FORBID

    policy_id: str
    field_code: str
    evidences: list[EvidenceRef]
    schema_version: str = Field(min_length=1)


class ExtractedFact(BaseModel):
    """Fato extraído com rastro de evidência (resumo §8.4 e §2.5).

    Coerência por status (EC-05, RF-04): `evidence_ids` só pode ser vazio
    quando `status="NOT_FOUND"`.
    """

    model_config = _FORBID

    fact_id: str
    policy_id: str
    field_code: str
    status: FactStatus
    value: dict[str, Any] | None
    normalized_value: dict[str, Any] | None
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str]
    requires_human_review: bool

    @model_validator(mode="after")
    def _evidence_must_exist_outside_not_found(self) -> "ExtractedFact":
        if self.status != "NOT_FOUND" and not self.evidence_ids:
            raise ValueError(
                f"evidence_ids must be non-empty when status={self.status!r} "
                "(evidência obrigatória, resumo §2.5; só NOT_FOUND dispensa evidência)"
            )
        return self


class ProcessingStatus(BaseModel):
    """Estado do processamento de um documento, consumido pela UI (§8.5)."""

    model_config = _FORBID

    document_id: str
    stage: ProcessingStage
    progress: float = Field(ge=0, le=1)
    message: str | None = None
