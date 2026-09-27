"""Modelos puros de qualidade da análise (D2-P1-1, roadmap D-01/D-02).

`Issue`/`QualityReport` são **aditivos**: `requires_human_review` permanece
no contrato (RN-01) e nada aqui substitui o modelo de extração. Os modelos
são derivados de sinais que o pipeline já detecta — nenhum novo detector.
Escala de severidade decidida no clarify de 2026-09-26 (4 níveis pt-br).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from shared_kernel.contracts import EvidenceRef


class Severity(str, Enum):
    """Escala de severidade de `Issue` (RN-02): falha dura → ruído informativo."""

    CRITICO = "CRÍTICO"
    ALTO = "ALTO"
    MEDIO = "MÉDIO"
    BAIXO = "BAIXO"


#: Ordem de agrupamento da fila de revisão (RF-02): CRÍTICO → BAIXO.
SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.CRITICO,
    Severity.ALTO,
    Severity.MEDIO,
    Severity.BAIXO,
)


class Issue(BaseModel):
    """Problema de qualidade derivado de um sinal já existente (RF-01)."""

    severity: Severity
    policy_id: str = Field(min_length=1)
    field_code: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_ref: EvidenceRef | None = None


class QualityReport(BaseModel):
    """Agregado de `Issue`s por documento ou por comparação (RF-01)."""

    scope: str = Field(min_length=1)  # "document" | "comparison"
    scope_id: str = Field(min_length=1)
    issues: list[Issue] = Field(default_factory=list)

    def count(self, severity: Severity) -> int:
        return sum(1 for issue in self.issues if issue.severity is severity)

    @property
    def counts_by_severity(self) -> dict[str, int]:
        return {severity.value: self.count(severity) for severity in SEVERITY_ORDER}
