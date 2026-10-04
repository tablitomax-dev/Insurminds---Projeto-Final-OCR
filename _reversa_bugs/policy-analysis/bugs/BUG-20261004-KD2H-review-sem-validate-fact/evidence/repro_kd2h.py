"""Reprodução do BUG-20261004-KD2H: CORRIGIDO persiste valor que viola regras de campo.

Fluxo real via fachada: extração rebaixa para NEEDS_REVIEW (EC-04) e a decisão humana
CORRIGIDO grava valor que viola `valor_positivo` e `moeda_conhecida` sem nenhuma guarda
(`validate_fact` nunca roda em application/review.py).

Execução (na raiz do projeto):
  $env:PYTHONPATH=".tools/pylibs;src"
  python -B <caminho-deste-arquivo>/repro_kd2h.py

Saída esperada ANTES do fix: "DEFEITO CONFIRMADO ..." (status FOUND, sem rule_violations).
Saída esperada DEPOIS do fix: ContractValidationError sanitizado e nada persistido.
"""

from __future__ import annotations

from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import (
    FixtureExplanationAgent,
    FixtureExtractionAgent,
)
from modules.policy_analysis.public_api import create_policy_analysis
from shared_kernel.contracts import EvidenceRef

POL = "pol_acme"
FIELD = "limite_agregado"

ev = EvidenceRef(
    evidence_id="ev_a1",
    policy_id=POL,
    document_id="doc_pol",
    page_number=1,
    quoted_text="Limite Agregado: R$ 900.000,00 por período de vigência.",
    source_type="NATIVE_TEXT",
)

outputs = {
    POL: [
        {
            "field_code": FIELD,
            # Valor ilegível → EC-04 rebaixa para NEEDS_REVIEW (mesmo caminho do
            # tests/e2e/test_review_cycle.py).
            "status": "FOUND",
            "value": {"amount": "valor ilegível", "currency": "BRL"},
            "confidence": 0.4,
            "evidence_ids": ["ev_a1"],
            "requires_human_review": False,
        }
    ]
}

facade = create_policy_analysis(
    MockEvidenceSource({POL: [ev]}),
    FixtureExtractionAgent(outputs),
    FixtureExplanationAgent(),
    db_path=":memory:",
    output_dir=".tmp/exports-repro-kd2h",
)

raw = facade.extract_field(POL, FIELD)
assert raw.status == "NEEDS_REVIEW", f"esperava NEEDS_REVIEW, veio {raw.status}"

item = facade.list_review_queue(POL)[0]
# Valor corrigido que VIOLA regras do campo: negativo (valor_positivo) e moeda
# desconhecida (moeda_conhecida).
BAD_VALUE = {"amount": "-100.00", "currency": "XYZ"}

try:
    reviewed = facade.record_review_decision(item.fact.fact_id, "CORRIGIDO", "ana", BAD_VALUE)
except Exception as exc:  # noqa: BLE001 - o experimento observa a exceção
    print("EXCECAO:", type(exc).__name__, "| mensagem:", str(exc))
    print("GUARDA ATIVA: CORRIGIDO rejeitou valor que viola regras.")
else:
    violations = (reviewed.value or {}).get("rule_violations")
    print("STATUS_FINAL:", reviewed.status, "| RULE_VIOLATIONS:", violations)
    if reviewed.status == "FOUND" and not violations:
        print(
            "DEFEITO CONFIRMADO: CORRIGIDO persistiu valor que viola regras "
            "(negativo + moeda desconhecida) sem ContractValidationError e sem guarda."
        )
    else:
        print("Resultado intermediário não previsto (verificar semântica).")