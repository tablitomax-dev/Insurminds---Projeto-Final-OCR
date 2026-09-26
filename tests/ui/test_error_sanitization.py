"""T-2a (UI): `st.error` nunca carrega texto de apólice nem exceção crua.

A mensagem é tipada (estágio + tipo + IDs) e só ecoa exceções do projeto,
cuja mensagem já é construída/sanitizada no módulo.
"""

from pydantic import BaseModel, ValidationError

from modules.policy_analysis.public_api import LlmOutputError
from shared_kernel.errors import ContractValidationError
from ui.errors import sanitize_error_message

POLICY_TEXT = "Limite agregado R$ 1.000.000"


class _Payload(BaseModel):
    amount: int


def _validation_error() -> ValidationError:
    try:
        _Payload.model_validate({"amount": POLICY_TEXT})
    except ValidationError as exc:
        return exc
    raise AssertionError("esperava ValidationError")


def test_erro_generico_mostra_tipo_e_estagio_sem_texto():
    error = RuntimeError(POLICY_TEXT)

    message = sanitize_error_message("PROCESSAMENTO/doc_a", error)

    assert "PROCESSAMENTO/doc_a" in message
    assert "RuntimeError" in message
    assert POLICY_TEXT not in message


def test_validation_error_nunca_ecoa_o_input():
    message = sanitize_error_message("EXTRACT", _validation_error())

    assert "EXTRACT" in message
    assert "ValidationError" in message
    assert POLICY_TEXT not in message


def test_erro_de_llm_ja_sanitizado_e_mantido():
    error = LlmOutputError("EXTRACT: citação do LLM fora do texto (quantidade=1)")

    message = sanitize_error_message("EXTRACT", error)

    assert "LlmOutputError" in message
    assert "citação do LLM fora do texto" in message


def test_erro_de_contrato_e_mantido():
    error = ContractValidationError("field_code desconhecido: xyz")

    message = sanitize_error_message("REVISAO/corrigir", error)

    assert "ContractValidationError" in message
    assert "field_code desconhecido: xyz" in message
