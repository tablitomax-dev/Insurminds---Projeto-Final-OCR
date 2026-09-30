"""Demo do vertical slice ponta a ponta (RF-10 + spec §6.2).

Extração dos 10 campos de 2 apólices → revisão sinalizada → comparação
determinística → explicação citando evidência → export PDF standalone.

Uso:
    python -m modules.policy_analysis.demo

Modo padrão: evidências e saída de LLM das fixtures (100% offline).
Com GEMINI_API_KEY: usa o provedor real (Pydantic AI) para extração/explicação.
Com EVIDENCE_SOURCE=document_processing: evidências reais da fachada do Dev 1.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from modules.policy_analysis.infrastructure.document_processing_source import (
    DocumentProcessingEvidenceSource,
)
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import (
    FixtureExplanationAgent,
    FixtureExtractionAgent,
    LLMExplanationAgent,
    MultiFieldExtractionAgent,
    PydanticAIClient,
)
from modules.policy_analysis.public_api import PolicyAnalysisFacade

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "tests" / "modules" / "policy_analysis" / "fixtures"
ALL_CODES = [
    "limite_agregado",
    "limite_por_sinistro",
    "franquia",
    "vigencia",
    "prazo_notificacao_sinistro",
    "extensao_territorial",
    "exclusoes_chave",
    "limite_defesa_custos",
    "retroatividade",
    "indice_reajuste",
]


def _load_fixtures() -> dict[str, dict]:
    return {
        name: json.loads((FIXTURES_DIR / f"apolice_{name}.json").read_text(encoding="utf-8"))
        for name in ("a", "b")
    }


def main() -> None:
    fixtures = _load_fixtures()
    policy_a = fixtures["a"]["policy"]["policy_id"]
    policy_b = fixtures["b"]["policy"]["policy_id"]

    if os.environ.get("EVIDENCE_SOURCE") == "document_processing":
        evidence_source = DocumentProcessingEvidenceSource()
    else:
        evidence_source = MockEvidenceSource(  # type: ignore[assignment]
            {
                policy_a: MockEvidenceSource.from_fixture_files(FIXTURES_DIR / "apolice_a.json")
                .get_evidences(policy_a),
                policy_b: MockEvidenceSource.from_fixture_files(FIXTURES_DIR / "apolice_b.json")
                .get_evidences(policy_b),
            }
        )

    if os.environ.get("GEMINI_API_KEY"):
        client = PydanticAIClient()
        extraction_agent = MultiFieldExtractionAgent(client)
        explanation_agent = LLMExplanationAgent(client)
    else:
        extraction_agent = FixtureExtractionAgent(  # type: ignore[assignment]
            {
                policy_a: fixtures["a"]["llm_output"],
                policy_b: fixtures["b"]["llm_output"],
            }
        )
        explanation_agent = FixtureExplanationAgent({})  # type: ignore[assignment]

    (REPO_ROOT / "output").mkdir(parents=True, exist_ok=True)
    facade = PolicyAnalysisFacade(
        evidence_source,
        extraction_agent,
        explanation_agent,
        db_path=str(REPO_ROOT / "output" / "demo.duckdb"),
        output_dir=str(REPO_ROOT / "exports"),
    )

    print(f"== Extração ({policy_a}) ==")
    facade.extract_fields(policy_a, ALL_CODES)
    print(f"== Extração ({policy_b}) ==")
    facade.extract_fields(policy_b, ALL_CODES)

    print("\n== Fila de revisão humana ==")
    for item in facade.list_review_queue():
        print(f"- {item.fact.field_code}: {item.fact.status} evidências={item.fact.evidence_ids}")

    print("\n== Comparação determinística ==")
    result = facade.compare_policies(policy_a, policy_b)
    print(f"ComparisonId: {result.comparison_id}")
    for campo in result.campos:
        print(f"- {campo.field_code}: {campo.resultado} (direção: {campo.direcao})")

    print("\n== Explicações ==")
    for campo in result.campos:
        if campo.resultado not in ("IGUAL", "AUSENTES_AMBOS"):
            explanation = facade.explain_difference(result.comparison_id, campo.field_code)
            print(f"- {campo.field_code}: {explanation.text}")

    path = facade.export_comparison(result.comparison_id)
    print(f"\n== Export ==\nMarkdown standalone: {path}")


if __name__ == "__main__":
    main()
