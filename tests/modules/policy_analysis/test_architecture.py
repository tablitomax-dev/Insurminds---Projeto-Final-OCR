"""T014 — Teste de arquitetura: fachada única e isolamento de camadas (RF-01, RNF-05)."""

from __future__ import annotations

import re
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[3] / "src" / "modules" / "policy_analysis"

IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+([a-zA-Z_][\w.]*)", re.MULTILINE
)

FORBIDDEN_EVERYWHERE = {"paddleocr", "pymupdf", "fitz", "qdrant_client", "llamaindex"}


def module_files() -> list[Path]:
    return sorted(MODULE_ROOT.rglob("*.py"))


def imports_of(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {match.group(1) for match in IMPORT_RE.finditer(text)}


def test_nenhum_import_de_internos_do_modulo_documental():
    """RF-01: policy_analysis só fala com document_processing pela fachada pública."""
    for path in module_files():
        for name in imports_of(path):
            assert not name.startswith("document_processing.") or name == "document_processing.public_api", (
                f"{path.name} importa interno do módulo documental: {name}"
            )
            if name.startswith("document_processing"):
                assert path.name == "document_processing_source.py", (
                    f"{path.name} importa document_processing fora do adaptador de evidência"
                )


def test_domain_e_application_nao_citam_infraestrutura():
    """RNF-05: camadas puras não mencionam banco, OCR, fila ou UI."""
    for layer in ("domain", "application"):
        for path in (MODULE_ROOT / layer).rglob("*.py"):
            for name in imports_of(path):
                root = name.split(".")[0]
                assert root not in FORBIDDEN_EVERYWHERE, f"{path.name} importa {name}"
                assert root not in {"duckdb", "fpdf", "pydantic_ai"}, f"{layer} importa {name}"
                assert not name.startswith("document_processing"), f"{layer} importa {name}"
"""Arquitetura: núcleo puro e fachada sem libs externas (RNF-05, RF-01)."""

import importlib
import re
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[3] / "src" / "modules" / "policy_analysis"

IMPORT_PATTERN = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.MULTILINE)

#: Único pacote externo liberado no núcleo (mais o shared_kernel do projeto).
ALLOWED_ROOTS = {"pydantic", "shared_kernel", "__future__"}


def _import_roots(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {match.group(1).split(".")[0] for match in IMPORT_PATTERN.finditer(text)}


def _assert_pure(paths: list[Path]) -> None:
    for path in paths:
        for root in _import_roots(path):
            if root in sys.stdlib_module_names or root in ALLOWED_ROOTS:
                continue
            raise AssertionError(f"import proibido em {path}: {root}")


def _layer_sources(*layers: str) -> list[Path]:
    return [source for layer in layers for source in (MODULE_DIR / layer).glob("*.py")]


def test_domain_e_application_sem_dependencias_externas():
    _assert_pure(_layer_sources("domain", "application"))


def test_public_api_sem_dependencias_externas():
    _assert_pure([MODULE_DIR / "public_api.py"])


def test_public_api_importavel_sem_libs_externas():
    module = importlib.import_module("modules.policy_analysis.public_api")
    assert hasattr(module, "PolicyAnalysisFacade")
    assert hasattr(module, "create_policy_analysis")
    assert hasattr(module, "create_default_policy_analysis")


def test_comparacao_nao_importa_llm():
    # LLM extrai e explica, jamais compara: o domínio de comparação é puro.
    for source in _layer_sources("domain") + [MODULE_DIR / "application" / "comparison.py"]:
        text = source.read_text(encoding="utf-8")
        assert "pydantic_ai" not in text
        assert "llm_extractors" not in text
