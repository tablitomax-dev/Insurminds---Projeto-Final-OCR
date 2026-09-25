"""RF-04 + EC-05: ExtractionRequest/ExtractedFact fiéis ao resumo §8.4,
com coerência de evidência por status (só NOT_FOUND dispensa evidência).
"""

import pytest
from pydantic import ValidationError

from shared_kernel.contracts import ExtractedFact, ExtractionRequest


def _base_fact(**overrides) -> dict:
    data = {
        "fact_id": "fact-0001",
        "policy_id": "policy-0001",
        "field_code": "limite_agregado",
        "status": "FOUND",
        "value": {"amount": 5000000.0, "currency": "USD"},
        "normalized_value": None,
        "confidence": 0.95,
        "evidence_ids": ["ev-0001"],
        "requires_human_review": False,
    }
    data.update(overrides)
    return data


def test_extraction_request_fixture(load):
    request = ExtractionRequest(**load("extraction_request.json"))
    assert request.field_code == "limite_agregado"
    assert request.schema_version == "1.0.0"
    assert len(request.evidences) == 1


def test_fact_found_fixture(load):
    fact = ExtractedFact(**load("extracted_fact_found.json"))
    assert fact.status == "FOUND"
    assert fact.value["amount"] == 5000000.0
    assert fact.evidence_ids == ["ev-native-0001"]


def test_fact_not_found_fixture_allows_empty_evidence_ids(load):
    fact = ExtractedFact(**load("extracted_fact_not_found.json"))
    assert fact.status == "NOT_FOUND"
    assert fact.value is None
    assert fact.normalized_value is None
    assert fact.evidence_ids == []


def test_found_without_evidence_rejected(load):
    # EC-05: FOUND exige evidência (resumo §2.5) — fixture inválida dedicada
    with pytest.raises(ValidationError):
        ExtractedFact(**load("invalid/extracted_fact_invalid_evidence_rule.json"))


@pytest.mark.parametrize("status", ["AMBIGUOUS", "NEEDS_REVIEW"])
def test_non_found_status_requires_evidence_ids(status):
    with pytest.raises(ValidationError):
        ExtractedFact(**_base_fact(status=status, evidence_ids=[]))


def test_unknown_status_rejected(load):
    with pytest.raises(ValidationError):
        ExtractedFact(**load("invalid/extracted_fact_invalid_status.json"))


def test_negative_confidence_rejected(load):
    with pytest.raises(ValidationError):
        ExtractedFact(**load("invalid/extracted_fact_invalid_confidence.json"))


def test_confidence_bounds_accepted():
    assert ExtractedFact(**_base_fact(confidence=0.0, value=None)).confidence == 0.0
    assert ExtractedFact(**_base_fact(confidence=1.0)).confidence == 1.0


def test_requires_human_review_flag():
    fact = ExtractedFact(**_base_fact(requires_human_review=True))
    assert fact.requires_human_review is True
