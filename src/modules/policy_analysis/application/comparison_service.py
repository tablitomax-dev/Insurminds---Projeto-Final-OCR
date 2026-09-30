"""Comparação determinística entre 2 apólices (RF-06, RN-01, RN-06).

Campo a campo, por regras puras do domínio — sem LLM. `ComparisonId` é
determinístico (hash do par): reexecutar o mesmo par devolve o mesmo resultado
sem duplicar registros (EC-06). Explicações já geradas são preservadas na
re-comparação.
"""

from __future__ import annotations

from dataclasses import replace

from ..domain.comparison import compare_facts
from ..domain.comparison import comparison_id as make_comparison_id
from ..domain.field_catalog import all_codes, get_field
from ..domain.models import ComparisonResult


class ComparisonService:
    """Casos de uso de comparação."""

    def __init__(self, repo, currency_rates: dict | None = None):
        self._repo = repo
        self._currency_rates = currency_rates

    def compare_policies(self, policy_id_a: str, policy_id_b: str) -> ComparisonResult:
        cid = make_comparison_id(policy_id_a, policy_id_b)
        facts_a = {f.field_code: f for f in self._repo.get_facts(policy_id_a)}
        facts_b = {f.field_code: f for f in self._repo.get_facts(policy_id_b)}

        previous = self._repo.get_comparison(cid)
        explicacoes = (
            {c.field_code: c.explicacao for c in previous.campos} if previous else {}
        )

        campos = tuple(
            replace(
                compare_facts(
                    get_field(code),
                    facts_a.get(code),
                    facts_b.get(code),
                    self._currency_rates,
                ),
                explicacao=explicacoes.get(code),
            )
            for code in all_codes()
        )
        result = ComparisonResult(
            comparison_id=cid,
            policy_id_a=policy_id_a,
            policy_id_b=policy_id_b,
            campos=campos,
        )
        self._repo.upsert_comparison(result)
        return result

    def get_comparison(self, comparison_id: str) -> ComparisonResult:
        result = self._repo.get_comparison(comparison_id)
        if result is None:
            from .errors import ClassifiedError

            raise ClassifiedError(
                "COMPARISON_NOT_FOUND", f"comparação não encontrada: {comparison_id}", retriable=False
            )
        return result
