"""Higiene da suíte de integração: os adapters do `document_processing` são
importados lazy dentro dos testes — este fixture os remove de `sys.modules`
ao fim de cada teste para que o teste de arquitetura (que garante a
importabilidade da fachada sem libs externas) não veja contaminação.
Mesmo padrão da fixture `indexing` de `tests/modules/document_processing/`.
"""

import sys

import pytest

_INFRA_MODULES = (
    "modules.document_processing.infrastructure.extractors",
    "modules.document_processing.infrastructure.indexing",
)


@pytest.fixture(autouse=True)
def _limpa_modulos_de_infra():
    yield
    for name in _INFRA_MODULES:
        sys.modules.pop(name, None)
