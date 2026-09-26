"""Módulo de avaliação (spec evaluation): golden set e relatório por campo.

Superfície pública única: `EvaluationFacade` e as fábricas de wiring.
"""

from modules.evaluation.public_api import (
    EvaluationFacade,
    create_evaluation,
    load_reference_set,
)

__all__ = [
    "EvaluationFacade",
    "create_evaluation",
    "load_reference_set",
]
