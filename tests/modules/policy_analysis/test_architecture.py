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
