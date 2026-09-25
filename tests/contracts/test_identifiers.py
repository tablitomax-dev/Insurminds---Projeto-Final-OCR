"""RF-01: os 7 identificadores compartilhados são str-based (resumo §8.1),
sem geração centralizada (NG-02).
"""

import pytest

from shared_kernel.identifiers import (
    ChunkId,
    ComparisonId,
    DocumentId,
    FactId,
    PageId,
    PolicyId,
    RunId,
)

ALL_IDENTIFIERS = [
    PolicyId,
    DocumentId,
    PageId,
    ChunkId,
    FactId,
    ComparisonId,
    RunId,
]


@pytest.mark.parametrize("identifier_cls", ALL_IDENTIFIERS)
def test_identifier_is_string_based(identifier_cls):
    value = identifier_cls("id-0001")
    assert isinstance(value, str)
    assert str(value) == "id-0001"


def test_identifiers_are_independent_namespaces():
    # NewType distingue os IDs apenas em type-checking estático; em runtime
    # todos continuam str (sem wrapper, sem custo — decisão RF-01/NG-02)
    assert PolicyId is not DocumentId
    assert type(PolicyId("a")) is str
    assert type(DocumentId("a")) is str
