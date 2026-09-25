"""RF-05: ProcessingStatus fiel ao resumo §8.5 (8 estágios fechados)."""

import pytest
from pydantic import ValidationError

from shared_kernel.contracts import ProcessingStatus

ALL_STAGES = [
    "RECEIVED",
    "TEXT_EXTRACTED",
    "OCR_COMPLETED",
    "INDEXED",
    "FACTS_EXTRACTED",
    "REVIEW_REQUIRED",
    "COMPLETED",
    "FAILED",
]


def test_valid_fixture(load):
    status = ProcessingStatus(**load("processing_status_indexed.json"))
    assert status.stage == "INDEXED"
    assert status.progress == 0.6
    assert status.message is not None


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_all_8_stages_accepted(stage):
    status = ProcessingStatus(document_id="doc-0001", stage=stage, progress=0.1)
    assert status.stage == stage


def test_message_defaults_to_none():
    status = ProcessingStatus(document_id="doc-0001", stage="RECEIVED", progress=0.0)
    assert status.message is None


def test_unknown_stage_rejected(load):
    with pytest.raises(ValidationError):
        ProcessingStatus(**load("invalid/processing_status_invalid_stage.json"))


@pytest.mark.parametrize("progress", [-0.01, 1.1])
def test_progress_out_of_range_rejected(progress):
    with pytest.raises(ValidationError):
        ProcessingStatus(document_id="doc-0001", stage="RECEIVED", progress=progress)


def test_failed_stage_accepts_message_alternative_flow_b():
    # fluxo alternativo B: falha com mensagem, sem estado novo ad-hoc
    status = ProcessingStatus(
        document_id="doc-0002",
        stage="FAILED",
        progress=0.3,
        message="OCR failed: documento ilegível abaixo da confiança mínima",
    )
    assert status.stage == "FAILED"
    assert status.progress < 1.0
