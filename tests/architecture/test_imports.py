"""Testes de arquitetura cross-module (RF-10 do requirements, RNF-05/06).

Regras:
- Módulos só conversam via `public_api` do módulo alvo.
- `document_processing` não conhece `policy_analysis`.
- `src/ui` consome apenas fachadas públicas (F-15) — nunca `domain`/
  `infrastructure` de módulo algum.
- `src/composition_root` é o único ponto de wiring e também só consome
  fachadas públicas (D2-P1-4 — regra arquitetural cobre TODO o alvo, F-15).
- `evaluation` consome apenas a fachada pública do `policy_analysis`.
- Dependências externas ficam em `infrastructure/` e `src/ui/`.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
MODULES_DIR = SRC_DIR / "modules"
UI_DIR = SRC_DIR / "ui"
COMPOSITION_DIR = SRC_DIR / "composition_root"

EXTERNAL_LIBS = (
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
)

_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_\.]*)", re.MULTILINE
)


def _imports_of(path: Path) -> list[str]:
    return _IMPORT_RE.findall(path.read_text(encoding="utf-8"))


def _module_sources(module: str, *parts: str) -> list[Path]:
    base = MODULES_DIR / module
    for part in parts:
        base = base / part
    return sorted(base.rglob("*.py"))


def test_policy_analysis_soh_usa_fachada_do_document_processing():
    """RF-01 policy-analysis: internals do módulo documental são proibidos."""
    offenders = []
    for path in _module_sources("policy_analysis"):
        for imported in _imports_of(path):
            if not imported.startswith("modules.document_processing"):
                continue
            if imported != "modules.document_processing.public_api":
                offenders.append(f"{path.name}: {imported}")
    assert not offenders, f"imports cross-module fora da fachada: {offenders}"


def test_document_processing_nao_conhece_policy_analysis():
    offenders = []
    for path in _module_sources("document_processing"):
        for imported in _imports_of(path):
            if imported.startswith("modules.policy_analysis"):
                offenders.append(f"{path.name}: {imported}")
    assert not offenders, f"document_processing não pode importar policy_analysis: {offenders}"


def test_ui_soh_usa_fachadas_publicas():
    """F-15/RF-02: `src/ui` jamais importa `domain`/`infrastructure` de módulos."""
    offenders = []
    for path in sorted(UI_DIR.rglob("*.py")):
        for imported in _imports_of(path):
            parts = imported.split(".")
            if parts[0] == "modules" and (len(parts) < 3 or parts[2] != "public_api"):
                offenders.append(f"{path.name}: {imported}")
            if ".infrastructure" in imported or ".domain" in imported:
                offenders.append(f"{path.name}: {imported}")
    assert not offenders, f"UI importa internals de módulo: {offenders}"


def test_composition_root_soh_usa_fachadas_publicas():
    """D2-P1-4/RF-07: o wiring único também só consome fachadas públicas."""
    offenders = []
    for path in sorted(COMPOSITION_DIR.rglob("*.py")):
        for imported in _imports_of(path):
            parts = imported.split(".")
            if parts[0] == "modules" and (len(parts) < 3 or parts[2] != "public_api"):
                offenders.append(f"{path.name}: {imported}")
            if ".infrastructure" in imported or ".domain" in imported:
                offenders.append(f"{path.name}: {imported}")
    assert not offenders, f"composition_root importa internals de módulo: {offenders}"


def test_evaluation_soh_usa_fachada_do_policy_analysis():
    """RNF-03: `evaluation` não importa internals do `policy_analysis`."""
    offenders = []
    for path in _module_sources("evaluation"):
        for imported in _imports_of(path):
            if not imported.startswith("modules.policy_analysis"):
                continue
            if imported != "modules.policy_analysis.public_api":
                offenders.append(f"{path.name}: {imported}")
    assert not offenders, f"evaluation importa internals de policy_analysis: {offenders}"


def test_sem_dependencias_externas_fora_de_infrastructure():
    """Núcleo (domain/application/public_api) é stdlib + pydantic + shared_kernel."""
    offenders = []
    for module in ("document_processing", "policy_analysis", "evaluation"):
        for layer in ("domain", "application"):
            for path in _module_sources(module, layer):
                for imported in _imports_of(path):
                    root = imported.split(".")[0]
                    if root in EXTERNAL_LIBS:
                        offenders.append(f"{path}: {imported}")
        for path in (MODULES_DIR / module).glob("public_api.py"):
            for imported in _imports_of(path):
                root = imported.split(".")[0]
                if root in EXTERNAL_LIBS:
                    offenders.append(f"{path}: {imported}")
    assert not offenders, f"dependência externa no núcleo: {offenders}"
