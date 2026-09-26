"""Fachada pública do policy_analysis (spec §8, RF-01..RF-08).

ÚNICA entrada do módulo para o resto do sistema (workflow/app/Streamlit):
`extract_field`, `get_facts`, `compare_policies`, `explain_difference`,
`export_comparison` — mais as operações de revisão humana (RF-04).
"""

from __future__ import annotations

from shared_kernel.contracts import ExtractedFact

from .application.comparison_service import ComparisonService
from .application.explanation import ExplanationService
from .application.export import ExportService
from .application.extraction import ExtractionService
from .application.review import ReviewService
from .domain.models import ComparisonResult, Explanation, ReviewItem
from .infrastructure.duckdb_repository import PolicyAnalysisRepository


class PolicyAnalysisFacade:
    """API pública do módulo de análise de apólices."""

    def __init__(
        self,
        evidence_source,
        extraction_agent,
        explanation_agent,
        db_path: str = ":memory:",
        output_dir: str = "output",
        currency_rates: dict | None = None,
    ):
        self._repo = PolicyAnalysisRepository(db_path)
        self._extraction = ExtractionService(evidence_source, extraction_agent, self._repo)
        self._review = ReviewService(self._repo)
        self._comparison = ComparisonService(self._repo, currency_rates)
        self._explanation = ExplanationService(self._repo, explanation_agent)
        self._export = ExportService(self._repo, output_dir)

    # --- extração (RF-02, RF-03) ----------------------------------------------

    def extract_field(self, policy_id: str, field_code: str) -> ExtractedFact:
        return self._extraction.extract_field(policy_id, field_code)

    def extract_fields(self, policy_id: str, field_codes: list[str]) -> list[ExtractedFact]:
        return self._extraction.extract_fields(policy_id, field_codes)

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        return self._extraction.get_facts(policy_id)

    # --- revisão humana (RF-04) ----------------------------------------------

    def list_review_queue(self, policy_id: str | None = None) -> list[ReviewItem]:
        return self._review.list_pending(policy_id)

    def record_review_decision(
        self, fact_id: str, decision: str, decided_by: str, value: dict | None = None
    ) -> ExtractedFact:
        return self._review.record_decision(fact_id, decision, decided_by, value)

    # --- comparação determinística (RF-06) ------------------------------------

    def compare_policies(self, policy_id_a: str, policy_id_b: str) -> ComparisonResult:
        return self._comparison.compare_policies(policy_id_a, policy_id_b)

    # --- explicação rastreável (RF-07) ----------------------------------------

    def explain_difference(self, comparison_id: str, field_code: str) -> Explanation:
        return self._explanation.explain_difference(comparison_id, field_code)

    # --- export standalone (RF-08) --------------------------------------------

    def export_comparison(self, comparison_id: str) -> str:
        return self._export.export_comparison(comparison_id)
