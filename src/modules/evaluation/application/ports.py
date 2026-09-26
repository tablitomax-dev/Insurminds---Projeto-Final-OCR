"""Portas do módulo `evaluation` (spec evaluation §8/§10).

A avaliação só conversa com o `policy_analysis` pela fachada pública
(`modules.policy_analysis.public_api`); este Protocol é o recorte usado,
para que `application/` continue sem dependência de internals alheios.
"""

from typing import Any, Protocol

from shared_kernel.contracts import EvidenceRef, ExtractedFact


class PolicyAnalysisPort(Protocol):
    """Recorte da `PolicyAnalysisFacade` consumido pela avaliação (RF-02)."""

    def extract_field(self, policy_id: str, field_code: str) -> ExtractedFact: ...

    def get_evidence(self, evidence_id: str) -> EvidenceRef | None: ...

    def normalize_field_value(
        self, field_code: str, value: dict[str, Any] | None
    ) -> dict[str, Any] | None: ...
