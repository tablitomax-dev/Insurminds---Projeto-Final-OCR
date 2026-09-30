"""Fachada pública única do módulo `evaluation` (spec evaluation §8).

Superfície mínima (RF-05): `run_evaluation(reference_set) -> report`. O
módulo consome o `policy_analysis` exclusivamente pela fachada pública
(RNF-03) e valida os artefatos por Pydantic (RF-06).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from modules.policy_analysis.public_api import PolicyAnalysisFacade
from shared_kernel.errors import ContractValidationError

from .application.ports import PolicyAnalysisPort
from .application.runner import EvaluationService
from .domain.models import (
    OQ_02_DECISION,
    SYNTHETIC_CAVEAT,
    EvaluationReport,
    ReferenceSet,
)

#: Golden set sintético embutido no módulo (2 apólices × 10 campos = 20 casos).
GOLDEN_SET_PATH = Path(__file__).resolve().parent / "fixtures" / "golden_set.json"

#: Caminho fixo dos relatórios (mesma política de `exports/` — T-2b).
DEFAULT_REPORT_DIR = Path("exports") / "evaluation"


class EvaluationFacade:
    """Fachada consumida pelo workflow — não expõe internals do módulo."""

    def __init__(
        self,
        service: EvaluationService,
        report_dir: str | Path = DEFAULT_REPORT_DIR,
    ) -> None:
        self._service = service
        self._report_dir = report_dir

    def run_evaluation(self, reference_set: ReferenceSet | str | Path) -> EvaluationReport:
        """Executa a avaliação e escreve o relatório por campo (RF-04)."""
        return self._service.run(as_reference_set(reference_set), self._report_dir)


def create_evaluation(
    policy_analysis: PolicyAnalysisFacade | PolicyAnalysisPort,
    report_dir: str | Path = DEFAULT_REPORT_DIR,
) -> EvaluationFacade:
    """Monta a fachada de avaliação sobre a fachada do `policy_analysis`."""
    return EvaluationFacade(EvaluationService(policy_analysis), report_dir)


def load_reference_set(path: str | Path) -> ReferenceSet:
    """Carrega e valida o conjunto de referência na fronteira (EC-01/EC-04).

    Fora do contrato → `ContractValidationError` classificado, sem ecoar o
    payload (T-2a: tipo do erro, nunca o conteúdo).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        return ReferenceSet.model_validate(data)
    except ValidationError as exc:
        raise ContractValidationError(
            f"REFERENCE: conjunto de referência fora do contrato (tipo={type(exc).__name__})"
        ) from exc


def as_reference_set(reference_set: ReferenceSet | str | Path) -> ReferenceSet:
    """Aceita o conjunto pronto ou o caminho do JSON versionado."""
    if isinstance(reference_set, ReferenceSet):
        return reference_set
    return load_reference_set(reference_set)


__all__ = [
    "DEFAULT_REPORT_DIR",
    "GOLDEN_SET_PATH",
    "OQ_02_DECISION",
    "SYNTHETIC_CAVEAT",
    "EvaluationFacade",
    "EvaluationReport",
    "ReferenceSet",
    "as_reference_set",
    "create_evaluation",
    "load_reference_set",
]
