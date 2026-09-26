"""E2E do ciclo de revisão humana (RF-02, Must do PRD §9).

Ciclo completo via fachada: fato `NEEDS_REVIEW` → **corrigido** → decisão
**registrada** (revisor, timestamp, valor original/corrigido, `EvidenceRef`) →
**comparação usa o valor revisado**. Mais o caminho de **Registrar divergência**
(fato segue pendente, decisão fica registrada).
"""

from datetime import datetime

from fakes.policy_analysis import (
    FakeEvidenceRetriever,
    FakeExplanationGenerator,
    InMemoryFactRepository,
    ScriptedLlmExtractor,
    make_evidence,
)
from modules.policy_analysis.public_api import create_policy_analysis

POL_A, POL_B = "pol_acme", "pol_bravo"
FIELD = "limite_agregado"

TEXT_A = "Limite Agregado: R$ 900.000,00 por período de vigência."
TEXT_B = "Limite Agregado: R$ 300.000,00 por período de vigência."

#: Âncoras literais dos chunks recuperados (ancoragem D2-P0-1, OQ-02 substring).
ANCHOR_A, ANCHOR_B = "R$ 900.000,00", "R$ 300.000,00"

OUTPUTS = {
    # Valor cru NEGATIVO → regra `valor_positivo` rebaixa para NEEDS_REVIEW.
    (POL_A, FIELD): {
        "status": "FOUND",
        "value": {"amount": -900000.0, "currency": "BRL", "raw_text": ANCHOR_A},
        "anchor": ANCHOR_A,
    },
    (POL_B, FIELD): {
        "status": "FOUND",
        "value": {"amount": 300000.0, "currency": "BRL", "raw_text": ANCHOR_B},
        "anchor": ANCHOR_B,
    },
    (POL_A, "franquia"): {
        "status": "AMBIGUOUS",
        "value": {"raw_text": ANCHOR_A},
        "anchor": ANCHOR_A,
        "confidence": 0.4,
        "requires_human_review": True,
    },
}

CORRECTED_VALUE = {"amount": 900000.0, "currency": "BRL", "raw_text": ANCHOR_A}


def _stack():
    """Fachada com fakes determinísticos (sem custo de LLM real)."""
    repository = InMemoryFactRepository()
    retriever = FakeEvidenceRetriever(
        evidences_by_policy={
            POL_A: [make_evidence("ev_a1", policy_id=POL_A, quoted_text=TEXT_A)],
            POL_B: [make_evidence("ev_b1", policy_id=POL_B, quoted_text=TEXT_B)],
        }
    )
    facade = create_policy_analysis(
        retriever=retriever,
        llm_extractor=ScriptedLlmExtractor(OUTPUTS),
        repository=repository,
        explanation_generator=FakeExplanationGenerator(),
    )
    return facade, repository


def test_ciclo_completo_needs_review_corrigido_registrado_e_comparado():
    policy, repository = _stack()

    # 1. Extração: regra por campo rebaixa o fato para NEEDS_REVIEW (RF-03).
    raw = policy.extract_field(POL_A, FIELD)
    assert raw.status == "NEEDS_REVIEW"
    assert raw.requires_human_review is True
    assert any("valor_positivo" in reason for reason in raw.value["rule_violations"])
    policy.extract_field(POL_B, FIELD)

    # 2. Fila de revisão antes de qualquer decisão (RF-04).
    assert [fact.field_code for fact in policy.get_review_queue(POL_A)] == [FIELD]

    # 3. Sem decisão humana, a comparação usa o valor cru (decisão registrada).
    before = policy.compare_policies(POL_A, POL_B)
    assert _direction(before, FIELD) == "menor"

    # 4. Corrigir valor: decisão gravada com revisor/timestamp/originais.
    reviewed, decision = policy.correct_fact(
        POL_A, FIELD, "ana", CORRECTED_VALUE, note="sinal trocado pelo OCR"
    )
    assert reviewed.status == "FOUND"
    assert reviewed.value == CORRECTED_VALUE
    assert reviewed.normalized_value == {"scalar": 900000.0}
    assert reviewed.requires_human_review is False
    assert reviewed.fact_id == raw.fact_id

    assert decision.action == "correct"
    assert decision.reviewer == "ana"
    assert decision.note == "sinal trocado pelo OCR"
    assert decision.original_value == raw.value
    assert decision.corrected_value == CORRECTED_VALUE
    assert decision.evidence_ids == raw.evidence_ids == ["ev_a1"]
    assert datetime.fromisoformat(decision.reviewed_at).tzinfo is not None

    # 5. Registrado e rastreável: decisão persistida, fato atualizado, fila zerada.
    persisted = policy.list_review_decisions(POL_A, FIELD)
    assert [item.review_id for item in persisted] == [decision.review_id]
    assert repository.get_fact(POL_A, FIELD) == reviewed
    assert policy.get_review_queue(POL_A) == []

    # 6. A comparação passa a usar o valor revisado (900k > 300k).
    after = policy.compare_policies(POL_A, POL_B)
    row = _row(after, FIELD)
    assert row.direction == "maior"
    assert row.value_a == CORRECTED_VALUE
    assert row.normalized_a == {"scalar": 900000.0}


def test_registrar_divergencia_fica_registrado_e_fato_segue_pendente():
    policy, _ = _stack()

    ambiguous = policy.extract_field(POL_A, "franquia")
    assert ambiguous.status == "AMBIGUOUS"

    reviewed, decision = policy.register_divergence(
        POL_A, "franquia", "bruno", "não confere com o doc físico"
    )

    assert reviewed == ambiguous
    assert decision.action == "divergence"
    assert decision.original_value == ambiguous.value
    assert decision.corrected_value is None
    assert decision.evidence_ids == ambiguous.evidence_ids
    assert [item.review_id for item in policy.list_review_decisions(POL_A, "franquia")] == [
        decision.review_id
    ]
    assert [fact.field_code for fact in policy.get_review_queue(POL_A)] == ["franquia"]


def _row(comparison, field_code):
    return next(row for row in comparison.rows if row.field_code == field_code)


def _direction(comparison, field_code):
    return _row(comparison, field_code).direction
