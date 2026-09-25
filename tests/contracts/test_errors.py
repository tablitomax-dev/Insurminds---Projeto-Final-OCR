"""RF-07: convenções de erro de contrato (hierarquia mínima e to_dict estável)."""

import pytest

from shared_kernel.errors import (
    ContractError,
    ContractNotFound,
    ContractValidationError,
    ContractVersionMismatch,
)
from shared_kernel.version import CONTRACTS_VERSION

SUBCLASSES = [ContractValidationError, ContractNotFound, ContractVersionMismatch]

EXPECTED_KEYS = {"error", "message", "contract_version"}


@pytest.mark.parametrize("error_cls", SUBCLASSES)
def test_subclasses_capture_as_base(error_cls):
    error = error_cls("falha de exemplo")
    assert isinstance(error, ContractError)
    assert error.message == "falha de exemplo"
    assert error.contract_version == CONTRACTS_VERSION


def test_to_dict_shape_is_stable():
    payload = ContractValidationError("campo 'page_number' inválido").to_dict()
    assert set(payload.keys()) == EXPECTED_KEYS
    assert payload == {
        "error": "ContractValidationError",
        "message": "campo 'page_number' inválido",
        "contract_version": CONTRACTS_VERSION,
    }


def test_version_mismatch_carries_expected_version():
    error = ContractVersionMismatch(
        "schema_version 2.0.0 > CONTRACTS_VERSION 1.0.0",
        contract_version="1.0.0",
    )
    assert error.to_dict()["contract_version"] == "1.0.0"


def test_base_error_is_raisable_and_catchable():
    with pytest.raises(ContractError):
        raise ContractNotFound("documento doc-0001 não encontrado")
