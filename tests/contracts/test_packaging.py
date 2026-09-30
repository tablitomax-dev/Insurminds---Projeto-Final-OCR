"""RF-08 + RF-10: versionamento do contrato e pureza do pacote.

RF-10 é verificado estaticamente aqui (varredura dos fontes) para que a
regra valha em CI, sem depender do Grep manual de alguém.
"""

import re
from pathlib import Path

import shared_kernel

SRC_DIR = Path(__file__).parents[2] / "src" / "shared_kernel"

FORBIDDEN_IMPORTS = [
    "qdrant_client",
    "duckdb",
    "llama_index",
    "streamlit",
    "paddleocr",
    "fitz",
    "pydantic_ai",
]

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def test_contracts_version_is_semver():
    assert SEMVER_PATTERN.match(shared_kernel.CONTRACTS_VERSION)
    # Versão vigente do contrato: 1.1.0 (MINOR por `content_fingerprint`
    # opcional — caixa postal `contract-delta-chunkmetadata.md`, feature 005).
    assert shared_kernel.CONTRACTS_VERSION == "1.1.0"


def test_package_exposes_contracts_surface():
    expected = {
        "CONTRACTS_VERSION",
        # identifiers
        "ChunkId", "ComparisonId", "DocumentId", "FactId", "PageId", "PolicyId", "RunId",
        # contracts
        "ChunkMetadata", "EvidenceRef", "ExtractionRequest", "ExtractedFact",
        "FactStatus", "ProcessingStage", "ProcessingStatus",
        "RetrievalQuery", "RetrievalResult", "SourceType",
        # errors
        "ContractError", "ContractNotFound", "ContractValidationError",
        "ContractVersionMismatch",
    }
    assert set(shared_kernel.__all__) == expected


def test_package_has_no_forbidden_imports():
    # RF-10: shared_kernel importa apenas stdlib + pydantic
    for source_file in SRC_DIR.glob("*.py"):
        text = source_file.read_text(encoding="utf-8")
        for module in FORBIDDEN_IMPORTS:
            assert f"import {module}" not in text
            assert f"from {module}" not in text
