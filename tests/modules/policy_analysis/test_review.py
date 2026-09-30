"""RF-02/D2-P0-2: loop de revisão humana — Confirmar / Corrigir / Registrar.

Cobertura: valor revisado alimenta a comparação, decisão persistida com
revisor/timestamp/valor original/valor corrigido ligada ao `EvidenceRef`,
guardas de correção e mensagens sem texto de apólice (T-2a).
"""

from datetime import datetime

import pytest

from fakes.policy_analysis import (
    FakeEvidenceRetriever,
    FakeExplanationGenerator,
    FakeLlmExtractor,
    InMemoryFactRepository,
    make_evidence,
    make_fact,
)
from modules.policy_analysis.application.review import HumanReviewService
from modules.policy_analysis.public_api import create_policy_analysis
from shared_kernel.errors import ContractNotFound, ContractValidationError

FIELD = "limite_agregado"
EVIDENCE_ID = "ev_pol_a_limite_agregado"
POLICY = "pol_a"


def _service(**fact_kwargs):
    """Serviço com um fato persistido e o `EvidenceRef` correspondente."""
    repository = InMemoryFactRepository()
    fact = make_fact(POLICY, FIELD, **fact_kwargs)
    repository.upsert_fact(fact)
    if fact.evidence_ids:
        for evidence_id in fact.evidence_ids:
            repository.save_evidence(make_evidence(evidence_id, policy_id=POLICY))
    return HumanReviewService(repository=repository), repository, fact


def _flagged(**overrides):
    defaults = {
        "status": "NEEDS_REVIEW",
        "value": {"amount": -5.0, "currency": "BRL", "raw_text": "Trecho da apólice"},
        "requires_human_review": True,
    }
    defaults.update(overrides)
    return defaults


def test_confirm_registra_decisao_e_tira_fato_da_fila():
    service, repository, fact = _service(**_flagged())

    reviewed, decision = service.confirm(POLICY, FIELD, "ana", "conferido no PDF")

    assert reviewed.status == "FOUND"
    assert reviewed.requires_human_review is False
    assert reviewed.value == fact.value  # valor cru aceito como está
    assert repository.get_fact(POLICY, FIELD) == reviewed
    assert repository.list_review_queue(POLICY) == []

    assert decision.action == "confirm"
    assert decision.reviewer == "ana"
    assert decision.note == "conferido no PDF"
    assert decision.fact_id == fact.fact_id
    assert decision.original_value == fact.value
    assert decision.corrected_value is None
    assert decision.evidence_ids == fact.evidence_ids
    assert datetime.fromisoformat(decision.reviewed_at).tzinfo is not None


def test_correct_substitui_valor_e_registra_original():
    service, repository, fact = _service(**_flagged())
    corrected_value = {"amount": 150000.0, "currency": "BRL", "raw_text": "Trecho da apólice"}

    reviewed, decision = service.correct(POLICY, FIELD, "ana", corrected_value, note="OCR invertido")

    assert reviewed.status == "FOUND"
    assert reviewed.value == corrected_value
    assert reviewed.normalized_value == {"scalar": 150000.0}
    assert reviewed.fact_id == fact.fact_id  # decisão segue ligada ao fato
    assert reviewed.requires_human_review is False
    assert repository.get_fact(POLICY, FIELD) == reviewed
    assert repository.list_review_queue(POLICY) == []

    assert decision.action == "correct"
    assert decision.original_value == fact.value
    assert decision.corrected_value == corrected_value
    assert decision.evidence_ids == fact.evidence_ids
    assert decision.evidence_ids == [EVIDENCE_ID]


def test_divergencia_registra_e_mantem_fato_pendente():
    service, repository, fact = _service(
        status="AMBIGUOUS",
        value={"raw_text": "Trecho da apólice"},
        requires_human_review=True,
    )

    reviewed, decision = service.register_divergence(POLICY, FIELD, "ana", "divergente do doc físico")

    assert reviewed == fact  # nada muda no fato
    assert repository.list_review_queue(POLICY) == [fact]
    assert decision.action == "divergence"
    assert decision.original_value == fact.value
    assert decision.corrected_value is None
    assert decision.note == "divergente do doc físico"
    assert decision.evidence_ids == fact.evidence_ids


def test_confirm_not_found_mantem_ausencia():
    service, repository, fact = _service(status="NOT_FOUND", value=None, evidence_ids=[])

    reviewed, decision = service.confirm(POLICY, FIELD, "ana")

    assert reviewed.status == "NOT_FOUND"
    assert reviewed.requires_human_review is False
    assert decision.evidence_ids == []
    assert decision.original_value is None


def test_correcao_de_not_found_exige_evidencia():
    service, repository, fact = _service(status="NOT_FOUND", value=None, evidence_ids=[])

    with pytest.raises(ContractValidationError) as excinfo:
        service.correct(POLICY, FIELD, "ana", {"amount": 10.0})

    assert "EvidenceRef" in str(excinfo.value)
    assert repository.list_reviews() == []
    assert repository.get_fact(POLICY, FIELD) == fact


def test_correcao_de_not_found_com_evidencia_vira_found():
    service, repository, _ = _service(status="NOT_FOUND", value=None, evidence_ids=[])
    repository.save_evidence(make_evidence(EVIDENCE_ID, policy_id=POLICY))

    reviewed, decision = service.correct(
        POLICY,
        FIELD,
        "ana",
        {"amount": 10.0, "raw_text": "Trecho da apólice"},
        evidence_ids=[EVIDENCE_ID],
    )

    assert reviewed.status == "FOUND"
    assert reviewed.evidence_ids == [EVIDENCE_ID]
    assert decision.evidence_ids == [EVIDENCE_ID]


def test_decisao_com_evidencia_inexistente_eh_rejeitada():
    service, repository, fact = _service(**_flagged())

    with pytest.raises(ContractValidationError):
        service.correct(
            POLICY, FIELD, "ana", {"amount": 10.0}, evidence_ids=["ev_inventada"]
        )

    assert repository.list_reviews() == []
    assert repository.get_fact(POLICY, FIELD) == fact


def test_revisor_em_branco_eh_rejeitado():
    service, _, _ = _service(**_flagged())

    with pytest.raises(ContractValidationError):
        service.confirm(POLICY, FIELD, "   ")


def test_fato_inexistente_eh_rejeitado():
    service, _, _ = _service(**_flagged())

    with pytest.raises(ContractNotFound):
        service.confirm("pol_desconhecida", FIELD, "ana")


def test_correcao_fora_das_regras_eh_rejeitada_sem_persistir():
    service, repository, fact = _service(**_flagged())

    with pytest.raises(ContractValidationError) as excinfo:
        service.correct(
            POLICY,
            FIELD,
            "ana",
            {"amount": -1.0, "raw_text": "Limite agregado R$ 1.000.000"},
        )

    message = str(excinfo.value)
    assert "valor_positivo" in message
    assert "R$ 1.000.000" not in message  # T-2a: valor nunca vaza em mensagem
    assert repository.list_reviews() == []
    assert repository.get_fact(POLICY, FIELD) == fact


def test_fachada_expoe_campos_decisoes_e_evidencias():
    repository = InMemoryFactRepository()
    fact = make_fact(POLICY, FIELD, **_flagged())
    repository.upsert_fact(fact)
    repository.save_evidence(make_evidence(EVIDENCE_ID, policy_id=POLICY))
    facade = create_policy_analysis(
        retriever=FakeEvidenceRetriever([]),
        llm_extractor=FakeLlmExtractor(),
        repository=repository,
        explanation_generator=FakeExplanationGenerator(),
    )

    fields = facade.list_fields()
    assert len(fields) == 10
    assert fields[0]["code"] == FIELD
    assert fields[0]["label"] == "Limite agregado"
    assert facade.normalize_field_value(FIELD, {"amount": "1.234,50"}) == {"scalar": 1234.5}
    assert facade.get_evidence(EVIDENCE_ID) is not None

    reviewed, decision = facade.correct_fact(POLICY, FIELD, "ana", {"amount": 10.0})
    assert reviewed.normalized_value == {"scalar": 10.0}
    assert [item.review_id for item in facade.list_review_decisions(POLICY, FIELD)] == [
        decision.review_id
    ]
