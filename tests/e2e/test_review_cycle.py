"""E2E do ciclo de revisão humana (RF-04, Must do PRD §9) no formato novo.

Ciclo completo via fachada: fato `NEEDS_REVIEW` → **corrigido** → decisão
**registrada** (revisor, timestamp, valor) → **comparação usa o valor revisado**.
Mais o caminho de **confirmar** o fato ambíguo (valor original preservado,
fato sai da fila). A fachada expõe o loop como `list_review_queue()` →
`ReviewItem(.fact, revisao_status, ...)` e
`record_review_decision(fact_id, "CONFIRMADO"|"CORRIGIDO", decided_by, value)`.
"""

from __future__ import annotations

from datetime import datetime

from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import (
    FixtureExplanationAgent,
    FixtureExtractionAgent,
)
from modules.policy_analysis.public_api import (
    PolicyAnalysisRepository,
    create_policy_analysis,
)
from shared_kernel.contracts import EvidenceRef

POL_A, POL_B = "pol_acme", "pol_bravo"
FIELD = "limite_agregado"
FIELD_FRANQUIA = "franquia"

TEXT_A = "Limite Agregado: R$ 900.000,00 por período de vigência."
TEXT_B = "Limite Agregado: R$ 300.000,00 por período de vigência."

#: Saídas roteirizadas do LLM por apólice (formato `FixtureExtractionAgent`).
OUTPUTS = {
    POL_A: [
        # Valor ilegível → EC-04 rebaixa para NEEDS_REVIEW com revisão humana.
        {
            "field_code": FIELD,
            "status": "FOUND",
            "value": {"amount": "valor ilegível", "currency": "BRL"},
            "confidence": 0.4,
            "evidence_ids": ["ev_a1"],
            "requires_human_review": False,
        },
        # Trechos conflitantes → AMBIGUOUS → decisão CONFIRMADO.
        {
            "field_code": FIELD_FRANQUIA,
            "status": "AMBIGUOUS",
            "value": {"raw_text": "trechos conflitantes"},
            "confidence": 0.4,
            "evidence_ids": ["ev_a1"],
            "requires_human_review": True,
        },
    ],
    POL_B: [
        {
            "field_code": FIELD,
            "status": "FOUND",
            "value": {"amount": 300_000.0, "currency": "BRL"},
            "confidence": 0.9,
            "evidence_ids": ["ev_b1"],
            "requires_human_review": False,
        },
    ],
}

CORRECTED_VALUE = {"amount": 900_000.0, "currency": "BRL"}


def _evidence(evidence_id: str, policy_id: str, quoted_text: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        policy_id=policy_id,
        document_id=f"doc_{policy_id}",
        page_number=1,
        quoted_text=quoted_text,
        source_type="NATIVE_TEXT",
    )


def _stack(tmp_path):
    """Fachada com fakes determinísticos + leitor do registro durável."""
    db_path = str(tmp_path / "pa.duckdb")
    facade = create_policy_analysis(
        MockEvidenceSource(
            {
                POL_A: [_evidence("ev_a1", POL_A, TEXT_A)],
                POL_B: [_evidence("ev_b1", POL_B, TEXT_B)],
            }
        ),
        FixtureExtractionAgent(OUTPUTS),
        FixtureExplanationAgent(),
        db_path=db_path,
        output_dir=str(tmp_path / "exports"),
    )
    return facade, PolicyAnalysisRepository(db_path)


def test_ciclo_completo_needs_review_corrigido_registrado_e_comparado(tmp_path):
    policy, reader = _stack(tmp_path)

    # 1. Extração: valor ilegível é rebaixado para NEEDS_REVIEW (RF-03, EC-04).
    raw = policy.extract_field(POL_A, FIELD)
    assert raw.status == "NEEDS_REVIEW"
    assert raw.requires_human_review is True
    policy.extract_field(POL_B, FIELD)

    # 2. Fila de revisão antes de qualquer decisão (RF-04): ReviewItem com a
    #    evidência anexa e nenhuma decisão registrada ainda.
    queue = policy.list_review_queue(POL_A)
    assert [item.fact.field_code for item in queue] == [FIELD]
    item = queue[0]
    assert item.fact.fact_id == f"FAC-{POL_A}-{FIELD}"
    assert item.fact.evidence_ids == ["ev_a1"]
    assert item.revisao_status == "PENDENTE"
    assert item.revisao_decisao is None
    assert item.revisao_por is None
    assert item.revisao_em is None

    # 3. Sem decisão humana, o campo aguarda na comparação (fluxo B, EC-02).
    before = policy.compare_policies(POL_A, POL_B)
    assert before.campo(FIELD).resultado == "AGUARDANDO_REVISAO"
    assert before.campo(FIELD).direcao == "n/a"

    # 4. Corrigir valor: decisão gravada, fato atualizado e normalizado.
    reviewed = policy.record_review_decision(
        item.fact.fact_id, "CORRIGIDO", "ana", CORRECTED_VALUE
    )
    assert reviewed.fact_id == raw.fact_id
    assert reviewed.status == "FOUND"
    assert reviewed.value == CORRECTED_VALUE
    assert reviewed.normalized_value == {"amount": "900000.00", "currency": "BRL"}
    assert reviewed.requires_human_review is False

    # 5. Registrado e rastreável: fila zerada e decisão persistida
    #    (quem decidiu, quando e com qual valor).
    assert policy.list_review_queue(POL_A) == []
    persisted = reader.get_review_item(item.fact.fact_id)
    assert persisted is not None
    assert persisted.revisao_status == "CORRIGIDO"
    assert persisted.revisao_por == "ana"
    assert persisted.revisao_decisao == {"decisao": "CORRIGIDO", "value": CORRECTED_VALUE}
    assert datetime.fromisoformat(persisted.revisao_em).tzinfo is not None

    # 6. A comparação passa a usar o valor revisado (900k > 300k).
    after = policy.compare_policies(POL_A, POL_B)
    campo = after.campo(FIELD)
    assert campo.resultado == "MAIOR"
    assert campo.direcao == "A"
    assert campo.valor_a == {"amount": "900000.00", "currency": "BRL"}


def test_confirmacao_mantem_o_valor_e_registra_a_decisao(tmp_path):
    policy, reader = _stack(tmp_path)

    ambiguous = policy.extract_field(POL_A, FIELD_FRANQUIA)
    assert ambiguous.status == "AMBIGUOUS"
    assert ambiguous.requires_human_review is True

    confirmed = policy.record_review_decision(
        ambiguous.fact_id, "CONFIRMADO", "bruno"
    )

    # Valor original preservado; o fato sai da fila de revisão.
    assert confirmed.fact_id == ambiguous.fact_id
    assert confirmed.value == ambiguous.value
    assert confirmed.normalized_value == ambiguous.normalized_value
    assert confirmed.requires_human_review is False
    assert policy.list_review_queue(POL_A) == []

    persisted = reader.get_review_item(ambiguous.fact_id)
    assert persisted is not None
    assert persisted.revisao_status == "CONFIRMADO"
    assert persisted.revisao_por == "bruno"
    assert persisted.revisao_decisao == {"decisao": "CONFIRMADO", "value": None}
    assert datetime.fromisoformat(persisted.revisao_em).tzinfo is not None
