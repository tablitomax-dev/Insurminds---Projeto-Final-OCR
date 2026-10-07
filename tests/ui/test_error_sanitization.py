"""Diagnóstico: a UI mostra a mensagem completa do erro (sem trava, 2026-10-05).

Decisão do humano: o projeto não tem dados sensíveis — o "detalhe omitido" foi
removido e `str(error)` aparece na tela para agilizar o diagnóstico. Erros
classificados ainda ganham uma dica amigável por código, sem esconder o detalhe.
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


def test_dica_amigavel_por_codigo_de_llm_indisponivel():
    error = ClassifiedError(
        "LLM_UNAVAILABLE",
        "provedor de LLM indisponível após 3 tentativas (RuntimeError)",
        retriable=True,
    )

    message = sanitize_error_message("EXTRACAO/Allianz", error)

    assert "Os provedores de IA não responderam após várias tentativas." in message
    assert "provedor de LLM indisponível após 3 tentativas" in message  # detalhe real
    assert "(código LLM_UNAVAILABLE)" in message
    # formato: estágio: tipo — dica detalhe (código X); a dica vem antes do detalhe
    assert message.index("Os provedores de IA") < message.index("provedor de LLM indisponível")


def test_dica_amigavel_por_codigo_de_timeout_de_llm():
    error = ClassifiedError("LLM_TIMEOUT", "provedor LLM não respondeu em 30s", retriable=True)

    message = sanitize_error_message("AGENTE", error)

    assert "O provedor de IA demorou para responder e a tentativa foi interrompida." in message
    assert "provedor LLM não respondeu em 30s" in message
    assert "(código LLM_TIMEOUT)" in message


def test_outras_codificacoes_tambem_recebem_dica_curta():
    error = ClassifiedError("COMPARISON_NOT_FOUND", "comparação não encontrada: cmp_1")

    message = sanitize_error_message("EXPORTACAO", error)

    assert "gere uma nova comparação" in message
    assert "comparação não encontrada: cmp_1" in message
    assert "(código COMPARISON_NOT_FOUND)" in message


def test_codigo_sem_dica_especifica_usa_dica_generica():
    error = ClassifiedError("CODIGO_INEDITO", "detalhe qualquer", retriable=True)

    message = sanitize_error_message("REVISAO", error)

    assert "Tente novamente" in message
    assert "detalhe qualquer" in message
    assert "(código CODIGO_INEDITO)" in message


def test_dica_do_codigo_de_credito_do_provedor_estourado():
    error = ClassifiedError(
        "LLM_QUOTA_EXCEEDED",
        "HTTP 403 — Key limit exceeded (total limit)",
        retriable=False,
    )

    message = sanitize_error_message("CONSULTA", error)

    assert "A chave do provedor de IA estourou o limite de crédito" in message
    assert "openrouter.ai" in message
    assert "HTTP 403 — Key limit exceeded (total limit)" in message  # detalhe real
    assert "(código LLM_QUOTA_EXCEEDED)" in message


def test_dica_do_codigo_de_chave_recusada_pelo_provedor():
    error = ClassifiedError("LLM_AUTH_FAILED", "HTTP 401 — Unauthorized", retriable=False)

    message = sanitize_error_message("CONSULTA", error)

    assert "A chave do provedor de IA foi recusada" in message
    assert "OPENROUTER_API_KEY" in message
    assert "HTTP 401 — Unauthorized" in message  # detalhe real
    assert "(código LLM_AUTH_FAILED)" in message
