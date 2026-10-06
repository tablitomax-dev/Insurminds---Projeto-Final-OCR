"""Diagnóstico: a UI mostra a mensagem completa do erro (sem trava, 2026-10-05).

Decisão do humano: o projeto não tem dados sensíveis — o "detalhe omitido" foi
removido e `str(error)` aparece na tela para agilizar o diagnóstico.
"""

from pydantic import BaseModel, ValidationError

from modules.policy_analysis.public_api import ClassifiedError
from shared_kernel.errors import ContractValidationError
from ui.errors import sanitize_error_message

DETAIL = "Limite agregado R$ 1.000.000"


class _Payload(BaseModel):
    amount: int


def _validation_error() -> ValidationError:
    try:
        _Payload.model_validate({"amount": DETAIL})
    except ValidationError as exc:
        return exc
    raise AssertionError("esperava ValidationError")


def test_erro_generico_mostra_o_detalhe_completo():
    message = sanitize_error_message("PROCESSAMENTO/doc_a", RuntimeError(DETAIL))

    assert "PROCESSAMENTO/doc_a" in message
    assert "Erro de execução" in message
    assert DETAIL in message


def test_validation_error_mostra_o_detalhe():
    message = sanitize_error_message("EXTRACT", _validation_error())

    assert "EXTRACT" in message
    assert "Erro de validação" in message
    assert "amount" in message  # o campo com problema aparece no diagnóstico


def test_erro_classificado_mostra_mensagem_e_codigo():
    error = ClassifiedError(
        "LLM_SCHEMA_INVALID",
        "saída do LLM fora do schema",
        retriable=True,
    )

    message = sanitize_error_message("EXTRACT", error)

    assert "Erro classificado" in message
    assert "LLM_SCHEMA_INVALID" in message
    assert "saída do LLM fora do schema" in message


def test_erro_de_contrato_e_mantido():
    error = ContractValidationError("field_code desconhecido: xyz")

    message = sanitize_error_message("REVISAO/corrigir", error)

    assert "Erro de regra de contrato" in message
    assert "field_code desconhecido: xyz" in message
