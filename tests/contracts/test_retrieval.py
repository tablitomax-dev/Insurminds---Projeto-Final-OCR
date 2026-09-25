"""RF-03: RetrievalQuery/RetrievalResult fiéis ao resumo §8.3."""

import pytest
from pydantic import ValidationError

from shared_kernel.contracts import RetrievalQuery, RetrievalResult


def test_valid_query_fixture(load):
    query = RetrievalQuery(**load("retrieval_query.json"))
    assert query.field_code == "limite_agregado"
    assert query.top_k == 5


def test_top_k_default_is_five():
    query = RetrievalQuery(query="limite agregado")
    assert query.top_k == 5
    assert query.policy_id is None


@pytest.mark.parametrize("top_k", [0, 21, -1])
def test_top_k_out_of_range_rejected(top_k):
    with pytest.raises(ValidationError):
        RetrievalQuery(query="consulta", top_k=top_k)


def test_empty_query_rejected(load):
    data = load("invalid/retrieval_query_invalid_top_k.json")
    data.pop("top_k")
    data["query"] = ""
    with pytest.raises(ValidationError):
        RetrievalQuery(**data)


def test_valid_result_fixture(load):
    result = RetrievalResult(**load("retrieval_result.json"))
    assert len(result.evidences) == 2
    assert result.evidences[0].source_type == "NATIVE_TEXT"
    assert result.evidences[1].chunk_id == "chunk-0023"


def test_empty_evidences_is_valid_empty_hit():
    # fluxo alternativo A: nada encontrado NÃO é erro do contrato
    result = RetrievalResult(
        query=RetrievalQuery(query="campo inexistente"),
        evidences=[],
        retrieval_run_id="run-0001",
    )
    assert result.evidences == []


def test_result_requires_retrieval_run_id(load):
    data = load("retrieval_result.json")
    data.pop("retrieval_run_id")
    with pytest.raises(ValidationError):
        RetrievalResult(**data)
