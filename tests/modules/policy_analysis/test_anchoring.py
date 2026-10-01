"""T-guards — Âncora de citação do LLM (D2-P0-1): citação inventada nunca vira FOUND."""

from __future__ import annotations

from modules.policy_analysis.application.extraction import ExtractionService
from modules.policy_analysis.domain.anchoring import (
    collect_excerpts,
    is_anchored,
    unanchored_excerpts,
)
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from shared_kernel.contracts import EvidenceRef


def _ev(eid: str, text: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=eid,
        policy_id="POL-A",
        document_id="DOC-A-1",
        page_number=1,
        quoted_text=text,
        source_type="NATIVE_TEXT",
    )


# --- funções puras ----------------------------------------------------------


def test_collect_excerpts_pega_chaves_de_citacao():
    value = {"raw_text": "Limite agregado de R$ 5.000.000,00", "amount": "5000000.00"}
    assert collect_excerpts(value) == ["Limite agregado de R$ 5.000.000,00"]


def test_collect_excerpts_pega_trechos_entre_aspas_em_texto_livre():
    value = {"text": 'a cláusula diz "cobertura mundial" e mais'}
    assert collect_excerpts(value) == ["cobertura mundial"]


def test_valor_sem_citacao_nao_tem_o_que_ancorar():
    value = {"amount": "5000000.00", "currency": "BRL"}
    assert collect_excerpts(value) == []
    assert is_anchored(value, [], ["EV-1"]) == (True, 0)


def test_citacao_ancorada_e_aceita():
    evs = [_ev("EV-1", "Limite agregado de R$ 5.000.000,00 por período.")]
    value = {"raw_text": "Limite agregado de R$ 5.000.000,00 por período."}
    assert is_anchored(value, evs, ["EV-1"]) == (True, 0)


def test_citacao_inventada_e_rejeitada():
    evs = [_ev("EV-1", "Limite agregado de R$ 5.000.000,00 por período.")]
    value = {"raw_text": "TEXTO INVENTADO PELO MODELO"}
    anchored, bad = is_anchored(value, evs, ["EV-1"])
    assert anchored is False
    assert bad == 1


def test_com_multiplas_evidencias_uma_citacao_invalida_rejeita():
    evs = [
        _ev("EV-1", "Limite agregado de R$ 5.000.000,00."),
        _ev("EV-2", "Franquia de R$ 50.000,00."),
    ]
    value = {"raw_text": "Franquia de R$ 50.000,00."}  # ancorada em EV-2
    assert is_anchored(value, evs, ["EV-1", "EV-2"]) == (True, 0)

    value_ruim = {"raw_text": "TEXTO INVENTADO"}
    assert is_anchored(value_ruim, evs, ["EV-1", "EV-2"])[0] is False


def test_unanchored_excerpts_retorna_os_nao_ancorados():
    anchors = ["Limite agregado de R$ 5.000.000,00."]
    assert unanchored_excerpts(["Limite agregado de R$ 5.000.000,00."], anchors) == []
    assert unanchored_excerpts(["INVENTADO"], anchors) == ["INVENTADO"]


# --- integração: rebaixa FOUND no ExtractionService -------------------------


class StubAgent:
    def __init__(self, raw_list):
        self.raw_list = raw_list

    def extract(self, requests, run_id):
        return self.raw_list


def _service(raw, evidences):
    from modules.policy_analysis.infrastructure.duckdb_repository import (
        PolicyAnalysisRepository,
    )

    return ExtractionService(
        MockEvidenceSource({"POL-A": evidences}),
        StubAgent(raw),
        PolicyAnalysisRepository(":memory:"),
    )


def test_citacao_inventada_rebaixa_found_para_needs_review(evidences_a):
    raw = [
        {
            "field_code": "limite_agregado",
            "status": "FOUND",
            "value": {"amount": "5000000.00", "currency": "BRL", "raw_text": "TEXTO INVENTADO"},
            "confidence": 0.9,
            "evidence_ids": ["EV-A-001"],
            "requires_human_review": False,
        }
    ]
    facts = _service(raw, evidences_a).extract_fields("POL-A", ["limite_agregado"])
    fact = facts[0]
    assert fact.status == "NEEDS_REVIEW"
    assert fact.requires_human_review is True
    assert fact.value["anchor_violations"]


def test_citacao_ancorada_mantem_found(evidences_a):
    raw = [
        {
            "field_code": "limite_agregado",
            "status": "FOUND",
            "value": {
                "amount": "5000000.00",
                "currency": "BRL",
                "raw_text": "Limite agregado de R$ 5.000.000,00 por período de seguro.",
            },
            "confidence": 0.9,
            "evidence_ids": ["EV-A-001"],
            "requires_human_review": False,
        }
    ]
    fact = _service(raw, evidences_a).extract_fields("POL-A", ["limite_agregado"])[0]
    assert fact.status == "FOUND"
    assert fact.requires_human_review is False
