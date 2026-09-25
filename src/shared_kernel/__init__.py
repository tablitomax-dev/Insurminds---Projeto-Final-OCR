"""shared_kernel — contratos compartilhados entre módulos (zona crítica).

Pacote pequeno e estável: identificadores, contratos Pydantic, erros e
versionamento. Sem serviços, sem regra de negócio, sem dependência além de
stdlib + pydantic (regra de importação do resumo executivo §7, RF-10).

Qualquer módulo pode importar `shared_kernel.contracts` e
`shared_kernel.identifiers`. Qualquer mudança MAJOR exige revisão dos dois
desenvolvedores.
"""

from shared_kernel.contracts import (
    ChunkMetadata,
    EvidenceRef,
    ExtractionRequest,
    ExtractedFact,
    FactStatus,
    ProcessingStage,
    ProcessingStatus,
    RetrievalQuery,
    RetrievalResult,
    SourceType,
)
from shared_kernel.errors import (
    ContractError,
    ContractNotFound,
    ContractValidationError,
    ContractVersionMismatch,
)
from shared_kernel.identifiers import (
    ChunkId,
    ComparisonId,
    DocumentId,
    FactId,
    PageId,
    PolicyId,
    RunId,
)
from shared_kernel.version import CONTRACTS_VERSION

__all__ = [
    "CONTRACTS_VERSION",
    # identifiers
    "ChunkId",
    "ComparisonId",
    "DocumentId",
    "FactId",
    "PageId",
    "PolicyId",
    "RunId",
    # contracts
    "ChunkMetadata",
    "EvidenceRef",
    "ExtractionRequest",
    "ExtractedFact",
    "FactStatus",
    "ProcessingStage",
    "ProcessingStatus",
    "RetrievalQuery",
    "RetrievalResult",
    "SourceType",
    # errors
    "ContractError",
    "ContractNotFound",
    "ContractValidationError",
    "ContractVersionMismatch",
]
