"""Erros classificados do policy_analysis (RF-09, EC-01).

Falhas nunca são silenciosas: viram erro classificado (reexecutável) ou
sinalização de revisão. `retriable=True` indica que uma nova `run_id` pode
tentar de novo (ex.: falha temporária do provedor de LLM).
"""

from __future__ import annotations


class PolicyAnalysisError(Exception):
    """Erro base do módulo."""

    code = "POLICY_ANALYSIS_ERROR"
    retriable = False


class ClassifiedError(PolicyAnalysisError):
    """Erro com código estável e se é reexecutável (rastro de auditoria)."""

    def __init__(self, code: str, message: str, retriable: bool = False):
        super().__init__(message)
        self.code = code
        self.retriable = retriable
        self.message = message

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "retriable": self.retriable}


def to_processing_status(document_id: str, exc: PolicyAnalysisError):
    """Mapeia falha classificada para `ProcessingStatus(stage="FAILED")` (EC-05).

    A falha nunca é silenciosa: o workflow enxerga a causa classificada e o
    fato de ser reexecutável.
    """
    from shared_kernel.contracts import ProcessingStatus

    code = getattr(exc, "code", "POLICY_ANALYSIS_ERROR")
    retriable = getattr(exc, "retriable", False)
    message = f"{code}: {exc} (reexecutável={retriable})"
    return ProcessingStatus(document_id=document_id, stage="FAILED", progress=0.0, message=message)
