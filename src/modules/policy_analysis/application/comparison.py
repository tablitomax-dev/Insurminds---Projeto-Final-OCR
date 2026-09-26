"""Serviço de comparação, explicação e export (RF-06, RF-07, RF-08).

A comparação em si é 100% determinística (regras puras do domínio); o LLM
participa apenas na explicação das diferenças.
"""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from shared_kernel.contracts import EvidenceRef
from shared_kernel.errors import ContractNotFound

from ..domain.anchoring import extract_quoted_segments, unanchored_excerpts
from ..domain.catalog import FIELD_CATALOG, get_field_spec
from ..domain.comparison import ComparisonResult, FieldComparison, compare_field
from .ports import ExplanationGenerator, FactRepository, LlmOutputError

#: Nome da mensagem usada quando a citação de evidência é inválida (RF-07).
_INVALID_CITATION_MESSAGE = "explicação sem evidência citada válida"


class ComparisonService:
    """Compara 2 apólices campo a campo e explica as diferenças com evidência."""

    def __init__(
        self,
        repository: FactRepository,
        explanation_generator: ExplanationGenerator,
    ) -> None:
        self._repository = repository
        self._explanation_generator = explanation_generator
        self._explanations: dict[tuple[str, str], tuple[str, list[str]]] = {}

    def compare_policies(self, policy_id_a: str, policy_id_b: str) -> ComparisonResult:
        """Compara os 10 campos do catálogo entre as duas apólices (determinístico)."""
        rows = [
            compare_field(
                spec,
                self._repository.get_fact(policy_id_a, spec.code),
                self._repository.get_fact(policy_id_b, spec.code),
            )
            for spec in FIELD_CATALOG.values()
        ]
        result = ComparisonResult(
            comparison_id=f"cmp_{uuid4().hex}",
            policy_id_a=policy_id_a,
            policy_id_b=policy_id_b,
            rows=rows,
        )
        self._repository.save_comparison(result)
        return result

    def explain_difference(self, comparison_id: str, field_code: str) -> tuple[str, list[str]]:
        """Explica a diferença de um campo citando evidências reais (RF-07)."""
        get_field_spec(field_code)
        comparison = self._get_comparison(comparison_id)
        row = next((row for row in comparison.rows if row.field_code == field_code), None)
        if row is None:
            raise ContractNotFound(
                f"campo {field_code} não consta na comparação {comparison_id}"
            )
        fact_a = self._repository.get_fact(comparison.policy_id_a, field_code)
        fact_b = self._repository.get_fact(comparison.policy_id_b, field_code)
        evidences_a = self._load_evidences(row.evidence_ids_a)
        evidences_b = self._load_evidences(row.evidence_ids_b)
        text, cited_ids = self._explanation_generator.explain(
            row.field_code,
            row.direction,
            fact_a,
            fact_b,
            evidences_a,
            evidences_b,
        )
        self._validate_citations(row, cited_ids)
        self._anchor_explanation(text, evidences_a, evidences_b)
        self._explanations[(comparison.comparison_id, field_code)] = (text, list(cited_ids))
        return text, list(cited_ids)

    def export_comparison(self, comparison_id: str, export_dir: str | Path = "exports") -> Path:
        """Exporta o resumo da comparação em Markdown standalone (RF-08)."""
        comparison = self._get_comparison(comparison_id)
        directory = Path(export_dir)
        directory.mkdir(parents=True, exist_ok=True)
        export_path = directory / f"{comparison.comparison_id}.md"
        export_path.write_text(self._render_export(comparison), encoding="utf-8")
        return export_path

    def _get_comparison(self, comparison_id: str) -> ComparisonResult:
        comparison = self._repository.get_comparison(comparison_id)
        if comparison is None:
            raise ContractNotFound(f"comparação não encontrada: {comparison_id}")
        return comparison

    def _load_evidences(self, evidence_ids: list[str]) -> list[EvidenceRef]:
        evidences = [self._repository.get_evidence(evidence_id) for evidence_id in evidence_ids]
        return [evidence for evidence in evidences if evidence is not None]

    @staticmethod
    def _validate_citations(row: FieldComparison, cited_ids: list[str]) -> None:
        """RF-07: citação vazia, inventada ou unilateral (com 2 lados) é rejeitada."""
        cited = set(cited_ids or [])
        real = set(row.evidence_ids_a) | set(row.evidence_ids_b)
        invalid = not cited or not cited <= real
        if row.evidence_ids_a and row.evidence_ids_b:
            invalid = invalid or not cited & set(row.evidence_ids_a)
            invalid = invalid or not cited & set(row.evidence_ids_b)
        if invalid:
            raise LlmOutputError(_INVALID_CITATION_MESSAGE)

    @staticmethod
    def _anchor_explanation(
        text: str,
        evidences_a: list[EvidenceRef],
        evidences_b: list[EvidenceRef],
    ) -> None:
        """Ancoragem da explicação (RF-01, D2-P0-1): citação existe nos textos recuperados.

        Toda citação literal (entre aspas) da explicação deve ser substring de
        alguma evidência recuperada dos dois lados (A e B). Sem ancoragem →
        `LlmOutputError` — a mensagem cita quantidade, nunca o texto (T-2a).
        """
        quotes = extract_quoted_segments(text)
        source_texts = [
            evidence.quoted_text for evidence in [*evidences_a, *evidences_b]
        ]
        missing = unanchored_excerpts(quotes, source_texts)
        if missing:
            raise LlmOutputError(
                f"{_INVALID_CITATION_MESSAGE}: citação fora dos textos recuperados"
                f" (quantidade={len(missing)})"
            )

    def _render_export(self, comparison: ComparisonResult) -> str:
        rows_by_code = {row.field_code: row for row in comparison.rows}
        lines = [
            f"# Comparação de apólices — {comparison.comparison_id}",
            "",
            f"- **comparison_id:** {comparison.comparison_id}",
            f"- **policy_id_a:** {comparison.policy_id_a}",
            f"- **policy_id_b:** {comparison.policy_id_b}",
            f"- **gerado em:** {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Resumo por campo",
            "",
            "| Campo | Valor A | Valor B | Direção | Evidências A | Evidências B | Explicação |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for code, spec in FIELD_CATALOG.items():
            row = rows_by_code.get(code)
            if row is None:
                cells = ("—", "—", "sem dados", "—", "—")
            else:
                cells = (
                    _render_value(row.value_a),
                    _render_value(row.value_b),
                    row.direction,
                    _render_ids(row.evidence_ids_a),
                    _render_ids(row.evidence_ids_b),
                )
            explanation = self._explanations.get((comparison.comparison_id, code))
            explanation_cell = _escape_cell(explanation[0]) if explanation else "explicação não gerada"
            lines.append(f"| `{code}` ({spec.label}) | " + " | ".join(cells) + f" | {explanation_cell} |")
        lines.append("")
        return "\n".join(lines)


def _render_value(value: dict | None) -> str:
    if not value:
        return "—"
    return _escape_cell(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _render_ids(evidence_ids: list[str]) -> str:
    return ", ".join(evidence_ids) if evidence_ids else "—"


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()
