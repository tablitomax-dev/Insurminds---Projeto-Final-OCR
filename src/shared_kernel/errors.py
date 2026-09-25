"""Convenções de erro de contrato (spec shared-kernel-contracts, RF-07).

Hierarquia mínima e estável de exceções transversais. Nenhum erro de
infraestrutura (OCR, LLM, banco) mora aqui — cada módulo mapeia suas falhas
para `ProcessingStatus(stage="FAILED")` (EC-08).
"""

from shared_kernel.version import CONTRACTS_VERSION


class ContractError(Exception):
    """Base de todos os erros de contrato compartilhados."""

    def __init__(
        self,
        message: str,
        *,
        contract_version: str = CONTRACTS_VERSION,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.contract_version = contract_version

    def to_dict(self) -> dict[str, str]:
        """Representação estável para logs e respostas da camada de workflow."""
        return {
            "error": type(self).__name__,
            "message": self.message,
            "contract_version": self.contract_version,
        }


class ContractValidationError(ContractError):
    """Payload recebido do outro módulo viola o esquema do contrato.

    Disparada quando Pydantic aceita o dado mas a coerência semântica falha
    (ex.: `ExtractedFact` FOUND sem evidência é barrado antes, no validator).
    """


class ContractNotFound(ContractError):
    """Entidade referenciada pelo contrato não existe (p.ex. chunk/documento)."""


class ContractVersionMismatch(ContractError):
    """`schema_version`/`metadata_version` incompatível com CONTRACTS_VERSION.

    A checagem é de responsabilidade do workflow no startup/uso (EC-07).
    """
