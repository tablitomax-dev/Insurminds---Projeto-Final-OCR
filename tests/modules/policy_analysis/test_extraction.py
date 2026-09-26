"""RF-02/RF-03/RF-04/RF-09: ExtractionService com fakes (sem libs externas)."""

import pytest

from fakes.policy_analysis import (
    FakeEvidenceRetriever,
    FakeLlmExtractor,
    InMemoryFactRepository,
    make_evidence,
    make_fact,
)
from modules.policy_analysis.application.extraction import ExtractionService
from modules.policy_analysis.application.ports import LlmOutputError
from shared_kernel.errors import ContractValidationError
from shared_kernel.version import CONTRACTS_VERSION


def _service(evidences, extractor):
    repository = InMemoryFactRepository()
    retriever = FakeEvidenceRetriever(evidences)
    service = ExtractionService(
        retriever=retriever,
        llm_extractor=extractor,
        repository=repository,
    )
    return service, repository, retriever


def test_sem_evidencias_retorna_not_found_sem_evidencia():
    service, repository, retriever = _service([], FakeLlmExtractor())
    fact = service.extract_field("pol_a", "franquia")

    assert fact.status == "NOT_FOUND"
    assert fact.value is None
    assert fact.normalized_value is None
    assert fact.confidence == 0.0
    assert fact.evidence_ids == []
    assert fact.requires_human_review is False
    assert repository.get_fact("pol_a", "franquia") == fact
    assert retriever.queries[0].top_k == 5


def test_found_valido_persiste_com_normalized_value():
    evidences = [make_evidence("ev_1"), make_evidence("ev_2", page_number=2)]
    fact = make_fact(
        "pol_a",
        "limite_agregado",
        value={"scalar": 150000.0},
        evidence_ids=["ev_1"],
    )
    extractor = FakeLlmExtractor(result=fact)
    service, repository, retriever = _service(evidences, extractor)

    result = service.extract_field("pol_a", "limite_agregado")

    assert result.normalized_value == {"scalar": 150000.0}
    assert repository.get_fact("pol_a", "limite_agregado") == result
    assert repository.get_evidence("ev_1") is not None
    assert repository.get_evidence("ev_2") is not None

    query = retriever.queries[0]
    assert query.field_code == "limite_agregado"
    assert query.policy_id == "pol_a"
    assert query.top_k == 5

    request = extractor.requests[0]
    assert request.schema_version == CONTRACTS_VERSION
    assert [evidence.evidence_id for evidence in request.evidences] == ["ev_1", "ev_2"]


def test_normalized_value_ja_preenchido_nao_e_sobrescrito():
    fact = make_fact(
        "pol_a",
        "limite_agregado",
        value={"scalar": 3.0},
        normalized_value={"scalar": 7.0},
        evidence_ids=["ev_1"],
    )
    service, repository, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=fact))

    result = service.extract_field("pol_a", "limite_agregado")

    assert result.normalized_value == {"scalar": 7.0}


def test_llm_inventa_evidence_id_nada_persistido():
    fact = make_fact("pol_a", "limite_agregado", value={"scalar": 1.0}, evidence_ids=["ev_fantasma"])
    service, repository, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=fact))

    with pytest.raises(LlmOutputError):
        service.extract_field("pol_a", "limite_agregado")

    assert repository.facts == {}
    assert repository.get_fact("pol_a", "limite_agregado") is None


@pytest.mark.parametrize(
    "invalid_output",
    [
        {"status": "ILEGIVEL", "evidence_ids": ["ev_1"]},
        "resposta fora do schema",
        {"fact_id": "f", "policy_id": "pol_a", "field_code": "limite_agregado", "status": "FOUND"},
    ],
)
def test_saida_fora_do_schema_gera_llm_output_error(invalid_output):
    service, repository, _ = _service(
        [make_evidence("ev_1")],
        FakeLlmExtractor(result=invalid_output),
    )

    with pytest.raises(LlmOutputError):
        service.extract_field("pol_a", "limite_agregado")

    assert repository.facts == {}


def test_field_code_fora_do_catalogo_e_rejeitado():
    service, repository, retriever = _service([make_evidence("ev_1")], FakeLlmExtractor())

    with pytest.raises(ContractValidationError):
        service.extract_field("pol_a", "campo_inventado")

    assert retriever.queries == []
    assert repository.facts == {}


def test_fatos_sinalizados_entram_na_fila_de_revisao():
    ambiguous = make_fact(
        "pol_a",
        "franquia",
        status="AMBIGUOUS",
        value={"scalar": 1000.0},
        evidence_ids=["ev_1"],
        requires_human_review=True,
    )
    review_flag = make_fact(
        "pol_a",
        "nome_segurado",
        value={"scalar": "ACME"},
        evidence_ids=["ev_2"],
        requires_human_review=True,
    )
    extractor = FakeLlmExtractor(result=ambiguous)
    service, repository, _ = _service([make_evidence("ev_1")], extractor)
    service.extract_field("pol_a", "franquia")
    repository.upsert_fact(review_flag)
    repository.upsert_fact(
        make_fact("pol_b", "franquia", value={"scalar": 2.0}, evidence_ids=["ev_3"])
    )

    queue = service.get_review_queue()

    assert [fact.fact_id for fact in queue] == ["fact_pol_a_franquia", "fact_pol_a_nome_segurado"]
    assert service.get_review_queue("pol_b") == []


def test_get_facts_devolve_fatos_da_apolice():
    fact = make_fact("pol_a", "franquia", value={"scalar": 1.0}, evidence_ids=["ev_1"])
    service, repository, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=fact))

    extracted = service.extract_field("pol_a", "franquia")

    assert service.get_facts("pol_a") == [extracted]
    assert service.get_facts("pol_b") == []
