"""T-2a (UI): `st.error` nunca carrega texto de apólice nem exceção crua.

A mensagem é tipada (estágio + tipo + IDs) e só ecoa exceções do projeto,
cuja mensagem já é construída/sanitizada no módulo: `ClassifiedError` ecoa
apenas o código estável (nunca `str(exc)`).
"""

from pydantic import BaseModel, ValidationError

from modules.policy_analysis.public_api import ClassifiedError
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


def test_erro_classificado_ecoa_apenas_o_codigo_sanitizado():
    error = ClassifiedError(
        "LLM_SCHEMA_INVALID",
        "EXTRACT: citação do LLM fora do texto (quantidade=1)",
        retriable=True,
    )

    message = sanitize_error_message("EXTRACT", error)

    assert "ClassifiedError" in message
    assert "LLM_SCHEMA_INVALID" in message
    # Só o código é ecoado — nunca `str(exc)` (T-2a).
    assert "citação do LLM fora do texto" not in message


def test_erro_de_contrato_e_mantido():
    error = ContractValidationError("field_code desconhecido: xyz")

    message = sanitize_error_message("REVISAO/corrigir", error)

    assert "ContractValidationError" in message
    assert "field_code desconhecido: xyz" in message
