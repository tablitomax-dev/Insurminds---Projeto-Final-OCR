"""Teste de arquitetura: núcleo puro, fachada pública e imports lazy (RNF-06, RF-08)."""

import importlib
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[3] / "src" / "modules" / "document_processing"

FORBIDDEN_IMPORTS = [
    "fitz",
    "pymupdf",
    "paddleocr",
    "qdrant_client",
    "duckdb",
    "llama_index",
    "streamlit",
    "pydantic_ai",
    "google",
    "numpy",
]


def test_core_layers_have_no_external_imports():
    # RNF-06: domain/ e application/ só usam stdlib + pydantic + shared_kernel
    for layer in ("domain", "application"):
        for source_file in (MODULE_ROOT / layer).glob("*.py"):
            text = source_file.read_text(encoding="utf-8")
            for module in FORBIDDEN_IMPORTS:
                assert f"import {module}" not in text, f"{source_file.name} importa {module}"
                assert f"from {module}" not in text, f"{source_file.name} importa {module}"


def test_public_api_is_importable_without_external_libs():
    public_api = importlib.import_module("modules.document_processing.public_api")

    assert hasattr(public_api, "DocumentProcessingFacade")
    assert hasattr(public_api, "create_document_processing")
    assert hasattr(public_api, "create_default_document_processing")
    # Os adapters só são importados quando a fachada padrão é montada.
    assert "modules.document_processing.infrastructure.extractors" not in sys.modules
    assert "modules.document_processing.infrastructure.indexing" not in sys.modules
