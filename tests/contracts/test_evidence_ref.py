"""RF-02: EvidenceRef fiel ao resumo §8.2 — constraints, literais e fail-fast."""

import pytest
from pydantic import ValidationError

from shared_kernel.contracts import EvidenceRef


def _base_evidence(**overrides) -> dict:
    data = {
        "evidence_id": "ev-0001",
        "policy_id": "policy-0001",
        "document_id": "doc-0001",
        "page_number": 7,
        "quoted_text": "Texto citado da página.",
        "source_type": "NATIVE_TEXT",
    }
    data.update(overrides)
    return data


def test_valid_fixture_native(load):
    data = load("evidence_ref_native.json")
    evidence = EvidenceRef(**data)
    assert evidence.page_number == 7
    assert evidence.section_name == "Objeto do Seguro"
    assert evidence.retrieval_score is None  # opcional, default None
    assert evidence.ocr_confidence is None


def test_valid_fixture_ocr_roundtrip(load):
    data = load("evidence_ref_ocr.json")
    evidence = EvidenceRef.model_validate(data)
    # serialização → leitura redonda estável (contrato é o dado em trânsito)
    again = EvidenceRef.model_validate(evidence.model_dump())
    assert again == evidence


@pytest.mark.parametrize("source_type", ["NATIVE_TEXT", "PADDLEOCR", "PP_STRUCTURE"])
def test_all_source_types_accepted(source_type):
    evidence = EvidenceRef(**_base_evidence(source_type=source_type))
    assert evidence.source_type == source_type


def test_invalid_page_number_rejected(load):
    with pytest.raises(ValidationError):
        EvidenceRef(**load("invalid/evidence_ref_invalid_page.json"))


def test_invalid_retrieval_score_rejected(load):
    with pytest.raises(ValidationError):
        EvidenceRef(**load("invalid/evidence_ref_invalid_score.json"))


def test_invalid_quoted_text_rejected(load):
    with pytest.raises(ValidationError):
        EvidenceRef(**load("invalid/evidence_ref_invalid_quoted_text.json"))


def test_page_number_zero_in_dict_rejected():
    with pytest.raises(ValidationError):
        EvidenceRef(**_base_evidence(page_number=0))


def test_unknown_field_rejected():
    # extra="forbid": payload fora do contrato falha na fronteira (RNF-01)
    with pytest.raises(ValidationError):
        EvidenceRef(**_base_evidence(page_hint="12"))


def test_score_boundary_values_accepted():
    lower = EvidenceRef(**_base_evidence(retrieval_score=0.0))
    upper = EvidenceRef(**_base_evidence(retrieval_score=1.0))
    assert lower.retrieval_score == 0.0
    assert upper.retrieval_score == 1.0
