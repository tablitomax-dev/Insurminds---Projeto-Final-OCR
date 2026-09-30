"""policy_analysis — núcleo de análise de apólices (Dev 2).

Camadas: `domain`, `application`, `infrastructure`; entrada única por
`public_api.PolicyAnalysisFacade` (spec `_reversa_sdd/sdd/policy-analysis.md#8`).
"""
"""Módulo de análise de apólices (spec policy-analysis).

Superfície pública única: `PolicyAnalysisFacade` e as fábricas de wiring.
A comparação é 100% determinística — LLM extrai e explica, jamais compara.
"""

from modules.policy_analysis.public_api import (
    PolicyAnalysisFacade,
    create_default_policy_analysis,
    create_document_processing_retriever,
    create_policy_analysis,
)

__all__ = [
    "PolicyAnalysisFacade",
    "create_default_policy_analysis",
    "create_document_processing_retriever",
    "create_policy_analysis",
]
