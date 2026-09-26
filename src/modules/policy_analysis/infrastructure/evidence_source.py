"""Porta de evidências do policy_analysis (RF-10, D-02).

`EvidenceSource` abstrai a origem das evidências: `MockEvidenceSource` (fixtures
sintéticas, Fase 1) e `DocumentProcessingEvidenceSource` (fachada do Dev 1,
Fase 2). Trocar a origem não muda contrato nenhum do domínio.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from shared_kernel.contracts import EvidenceRef


class EvidenceSource(Protocol):
    """Origem de evidências por apólice (retrieval real ou mockado)."""

    def get_evidences(self, policy_id: str, field_code: str | None = None) -> list[EvidenceRef]:
        ...


class MockEvidenceSource:
    """Evidências fixas em memória (fixtures das apólices sintéticas)."""

    def __init__(self, evidences_by_policy: dict[str, list[EvidenceRef]]):
        self._by_policy = evidences_by_policy

    @classmethod
    def from_fixture_files(cls, *paths: str | Path) -> "MockEvidenceSource":
        """Carrega fixtures JSON no formato das apólices sintéticas."""
        by_policy: dict[str, list[EvidenceRef]] = {}
        for path in paths:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            policy_id = data["policy"]["policy_id"]
            by_policy[policy_id] = [EvidenceRef.model_validate(e) for e in data["evidences"]]
        return cls(by_policy)

    def get_evidences(self, policy_id: str, field_code: str | None = None) -> list[EvidenceRef]:
        return list(self._by_policy.get(policy_id, []))
