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
        value={"scalar": 150000.0, "raw_text": "Trecho da apólice"},
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
        value={"scalar": 3.0, "raw_text": "Trecho da apólice"},
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
    fact = make_fact(
        "pol_a",
        "franquia",
        value={"scalar": 1.0, "raw_text": "Trecho da apólice"},
        evidence_ids=["ev_1"],
    )
    service, repository, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=fact))

    extracted = service.extract_field("pol_a", "franquia")

    assert service.get_facts("pol_a") == [extracted]
    assert service.get_facts("pol_b") == []


# --- Ancoragem de citação (RF-01, D2-P0-1) ---


def test_llm_inventa_citacao_e_rejeitado():
    evidences = [make_evidence("ev_1", quoted_text="Limite Agregado: R$ 1.000.000,00")]
    fact = make_fact(
        "pol_a",
        "limite_agregado",
        value={"scalar": 1000000.0, "raw_text": "Limite Agregado: R$ 9.999.999,99"},
        evidence_ids=["ev_1"],
    )
    service, repository, _ = _service(evidences, FakeLlmExtractor(result=fact))

    with pytest.raises(LlmOutputError):
        service.extract_field("pol_a", "limite_agregado")

    assert repository.facts == {}


def test_llm_citacao_real_e_aceita():
    evidences = [make_evidence("ev_1", quoted_text="Limite Agregado: R$ 1.000.000,00")]
    fact = make_fact(
        "pol_a",
        "limite_agregado",
        value={"scalar": 1000000.0, "raw_text": "R$ 1.000.000,00"},
        evidence_ids=["ev_1"],
    )
    service, repository, _ = _service(evidences, FakeLlmExtractor(result=fact))

    result = service.extract_field("pol_a", "limite_agregado")

    assert result.status == "FOUND"
    assert repository.get_fact("pol_a", "limite_agregado") == result


def test_multiplas_evidencias_com_uma_citacao_invalida_e_rejeitado():
    evidences = [
        make_evidence("ev_1", quoted_text="Limite Agregado: R$ 1.000.000,00"),
        make_evidence("ev_2", page_number=2, quoted_text="Franquia: R$ 10.000,00"),
    ]
    fact = make_fact(
        "pol_a",
        "limite_agregado",
        value={
            "scalar": 1000000.0,
            "raw_text": "R$ 1.000.000,00",
            "excerpt": "R$ 7.777.777,77",
        },
        evidence_ids=["ev_1", "ev_2"],
    )
    service, repository, _ = _service(evidences, FakeLlmExtractor(result=fact))

    with pytest.raises(LlmOutputError):
        service.extract_field("pol_a", "limite_agregado")

    assert repository.facts == {}


def test_found_sem_trecho_para_ancoragem_e_rejeitado():
    fact = make_fact("pol_a", "limite_agregado", value={"scalar": 150000.0}, evidence_ids=["ev_1"])
    service, repository, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=fact))

    with pytest.raises(LlmOutputError):
        service.extract_field("pol_a", "limite_agregado")

    assert repository.facts == {}


def test_citacao_inventada_em_fato_nao_found_tambem_e_rejeitada():
    fact = make_fact(
        "pol_a",
        "franquia",
        status="AMBIGUOUS",
        value={"raw_text": "trecho que não existe no chunk"},
        evidence_ids=["ev_1"],
        requires_human_review=True,
    )
    service, repository, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=fact))

    with pytest.raises(LlmOutputError):
        service.extract_field("pol_a", "franquia")

    assert repository.facts == {}


# --- Sanitização de erro (T-2a, RF-06) ---

_LEAK = "Limite agregado R$ 1.000.000"


def test_erro_de_schema_nao_ecoa_o_texto_do_input():
    invalid = {
        "fact_id": "fact_1",
        "policy_id": "pol_a",
        "field_code": "limite_agregado",
        "status": "FOUND",
        "value": {"raw_text": _LEAK},
    }
    service, repository, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=invalid))

    with pytest.raises(LlmOutputError) as excinfo:
        service.extract_field("pol_a", "limite_agregado")

    message = str(excinfo.value)
    assert _LEAK not in message
    assert "ValidationError" in message  # tipo do erro
    assert "pol_a" in message and "limite_agregado" in message  # IDs
    assert repository.facts == {}


def test_erro_de_schema_nao_ecoa_chave_inventada():
    invalid = {
        "fact_id": "fact_1",
        "policy_id": "pol_a",
        "field_code": "limite_agregado",
        "status": "FOUND",
        "value": {"scalar": 1.0},
        "confidence": 0.9,
        "evidence_ids": ["ev_1"],
        "requires_human_review": False,
        _LEAK: "extra fora do contrato",
    }
    service, _, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=invalid))

    with pytest.raises(LlmOutputError) as excinfo:
        service.extract_field("pol_a", "limite_agregado")

    assert _LEAK not in str(excinfo.value)


def test_erro_de_evidence_id_nao_ecoa_o_id_inventado():
    fact = make_fact(
        "pol_a",
        "limite_agregado",
        value={"scalar": 1.0, "raw_text": "Trecho da apólice"},
        evidence_ids=[_LEAK],
    )
    service, _, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=fact))

    with pytest.raises(LlmOutputError) as excinfo:
        service.extract_field("pol_a", "limite_agregado")

    assert _LEAK not in str(excinfo.value)
    assert "<id omitido>" in str(excinfo.value)


def test_erro_de_ancoragem_nao_ecoa_a_citacao_inventada():
    evidences = [make_evidence("ev_1", quoted_text="Limite Agregado: R$ 1.000.000,00")]
    fact = make_fact(
        "pol_a",
        "limite_agregado",
        value={"scalar": 1.0, "raw_text": _LEAK},
        evidence_ids=["ev_1"],
    )
    service, _, _ = _service(evidences, FakeLlmExtractor(result=fact))

    with pytest.raises(LlmOutputError) as excinfo:
        service.extract_field("pol_a", "limite_agregado")

    assert _LEAK not in str(excinfo.value)


# --- Regras mínimas por campo (D2-P0-3, RF-03) ---


def test_fato_que_falha_regra_vira_needs_review():
    fact = make_fact(
        "pol_a",
        "franquia",
        value={"scalar": -1000.0, "raw_text": "Trecho da apólice"},
        evidence_ids=["ev_1"],
    )
    service, repository, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=fact))

    result = service.extract_field("pol_a", "franquia")

    assert result.status == "NEEDS_REVIEW"
    assert result.requires_human_review is True
    assert result.value["rule_violations"]
    assert service.get_review_queue("pol_a") == [result]
    assert repository.get_fact("pol_a", "franquia") == result


def test_regra_cruzada_de_vigencia_rebaixa_fato_extraido():
    repository = InMemoryFactRepository()
    repository.upsert_fact(
        make_fact("pol_a", "vigencia_inicio", value={"scalar": "2026-01-01"}, evidence_ids=["ev_ini"])
    )
    fim = make_fact(
        "pol_a",
        "vigencia_fim",
        value={"scalar": "2025-01-01", "raw_text": "Vigência até 01/01/2025"},
        evidence_ids=["ev_1"],
    )
    service = ExtractionService(
        retriever=FakeEvidenceRetriever(
            [make_evidence("ev_1", quoted_text="Vigência até 01/01/2025")]
        ),
        llm_extractor=FakeLlmExtractor(result=fim),
        repository=repository,
    )

    result = service.extract_field("pol_a", "vigencia_fim")

    assert result.status == "NEEDS_REVIEW"
    assert result.value["rule_violations"]
    assert service.get_review_queue("pol_a") == [result]


def test_fato_que_passa_nas_regras_continua_found():
    fact = make_fact(
        "pol_a",
        "limite_agregado",
        value={"scalar": 150000.0, "currency": "BRL", "raw_text": "Trecho da apólice"},
        evidence_ids=["ev_1"],
    )
    service, _, _ = _service([make_evidence("ev_1")], FakeLlmExtractor(result=fact))

    result = service.extract_field("pol_a", "limite_agregado")

    assert result.status == "FOUND"
    assert result.requires_human_review is False
