"""T-guards — Regras mínimas por campo (D2-P0-3): falha nunca vira FOUND."""

from __future__ import annotations

import pytest

from modules.policy_analysis.application.extraction import ExtractionService
from modules.policy_analysis.domain.field_catalog import get_field
from modules.policy_analysis.domain.rules import validate_fact


def _violations(code: str, normalized: dict, others=None):
    return validate_fact(get_field(code), normalized, others)


def test_valor_positivo_rejeita_negativo():
    v = _violations("limite_agregado", {"amount": "-1.00", "currency": "BRL"})
    assert [x.rule for x in v] == ["valor_positivo"]


def test_valor_positivo_rejeita_zero_em_limite():
    v = _violations("limite_agregado", {"amount": "0.00", "currency": "BRL"})
    assert [x.rule for x in v] == ["valor_positivo"]


def test_franquia_zero_e_valida():
    v = _violations("franquia", {"amount": "0.00", "currency": "BRL"})
    assert v == []


def test_valor_positivo_aceita_positivo():
    v = _violations("limite_agregado", {"amount": "5000000.00", "currency": "BRL"})
    assert v == []


def test_prazo_zero_rejeitado():
    v = _violations("prazo_notificacao_sinistro", {"number": "0"})
    assert [x.rule for x in v] == ["valor_positivo"]


def test_moeda_conhecida_rejeita_desconhecida():
    v = _violations("franquia", {"amount": "100.00", "currency": "XYZ"})
    assert [x.rule for x in v] == ["moeda_conhecida"]


def test_moeda_conhecida_aceita_brl_usd():
    assert _violations("franquia", {"amount": "100.00", "currency": "BRL"}) == []
    assert _violations("franquia", {"amount": "100.00", "currency": "USD"}) == []


def test_moeda_consistente_rejeita_moedas_distintas_na_apolice():
    outros = [{"amount": "100.00", "currency": "USD"}]
    v = _violations("limite_agregado", {"amount": "100.00", "currency": "BRL"}, outros)
    assert [x.rule for x in v] == ["moeda_consistente"]


def test_moeda_consistente_aceita_mesma_moeda():
    outros = [{"amount": "100.00", "currency": "BRL"}]
    v = _violations("limite_agregado", {"amount": "100.00", "currency": "BRL"}, outros)
    assert v == []


def test_vigencia_ordem_rejeita_periodo_invertido():
    v = _violations("vigencia", {"start": "2026-01-01", "end": "2025-01-01"})
    assert [x.rule for x in v] == ["vigencia_ordem"]


def test_vigencia_ordem_aceita_periodo_normal():
    v = _violations("vigencia", {"start": "2025-01-01", "end": "2026-01-01"})
    assert v == []


def test_texto_nao_recebe_regras_de_valor():
    v = _violations("extensao_territorial", {"text": "mundial"})
    assert v == []


def test_valor_none_nao_dispara_regra():
    assert validate_fact(get_field("limite_agregado"), None) == []


# --- enum_base_territorial (BUG-20261004-ODCS, D2-P0-3) ----------------------


@pytest.mark.parametrize(
    "text",
    [
        "Mundial", "MUNDIAL", "mundial", "Brasil", "Canadá", "america latina",
        "América do Sul", "América do Norte", "eua", "Estados Unidos", "Europa",
        "Worldwide", "Internacional", "Exterior",
    ],
)
def test_enum_base_territorial_aceita_valores_do_enum(text):
    assert _violations("extensao_territorial", {"text": text}) == []


@pytest.mark.parametrize(
    "text", ["Atlântico Norte", "Global", "mundial exceto brasil", "Estados Unidos e Canadá"]
)
def test_enum_base_territorial_rejeita_fora_do_enum(text):
    v = _violations("extensao_territorial", {"text": text})
    assert [x.rule for x in v] == ["enum_base_territorial"]


def test_enum_base_territorial_motivo_nunca_traz_o_valor():
    v = _violations("extensao_territorial", {"text": "Atlântico Norte"})
    assert "Atlântico" not in v[0].reason


def test_enum_nao_alcanca_texto_livre_de_exclusoes():
    assert _violations("exclusoes_chave", {"text": "Global"}) == []


def test_enum_rebaixa_found_para_needs_review_no_servico(evidences_a):
    raw = [_fact_raw("extensao_territorial", {"text": "Atlântico Norte"}, "EV-A-006")]
    fact = _service(raw, evidences_a).extract_fields("POL-A", ["extensao_territorial"])[0]
    assert fact.status == "NEEDS_REVIEW"
    assert fact.requires_human_review is True
    assert [v["rule"] for v in fact.value["rule_violations"]] == ["enum_base_territorial"]


def test_enum_valido_mantem_found_no_servico(evidences_a):
    raw = [_fact_raw("extensao_territorial", {"text": "Mundial"}, "EV-A-006")]
    fact = _service(raw, evidences_a).extract_fields("POL-A", ["extensao_territorial"])[0]
    assert fact.status == "FOUND"
    assert fact.requires_human_review is False


def test_motivo_da_regra_nunca_traz_o_valor():
    v = _violations("limite_agregado", {"amount": "-99999.00", "currency": "BRL"})
    assert "-99999" not in v[0].reason


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
    from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource

    return ExtractionService(
        MockEvidenceSource({"POL-A": evidences}),
        StubAgent(raw),
        PolicyAnalysisRepository(":memory:"),
    )


def _fact_raw(code, value, evid, status="FOUND"):
    return {
        "field_code": code,
        "status": status,
        "value": value,
        "confidence": 0.9,
        "evidence_ids": [evid],
        "requires_human_review": False,
    }


def test_regra_violada_rebaixa_found_para_needs_review(evidences_a):
    raw = [_fact_raw("limite_agregado", {"amount": "-1.00", "currency": "BRL"}, "EV-A-001")]
    fact = _service(raw, evidences_a).extract_fields("POL-A", ["limite_agregado"])[0]
    assert fact.status == "NEEDS_REVIEW"
    assert fact.requires_human_review is True
    assert [v["rule"] for v in fact.value["rule_violations"]] == ["valor_positivo"]


def test_moeda_inconsistente_rebaixa_campos_monetarios(evidences_a):
    raw = [
        _fact_raw("limite_agregado", {"amount": "5000000.00", "currency": "BRL"}, "EV-A-001"),
        _fact_raw("limite_por_sinistro", {"amount": "1000000.00", "currency": "USD"}, "EV-A-002"),
    ]
    facts = _service(raw, evidences_a).extract_fields(
        "POL-A", ["limite_agregado", "limite_por_sinistro"]
    )
    by_code = {f.field_code: f for f in facts}
    assert by_code["limite_agregado"].status == "NEEDS_REVIEW"
    assert by_code["limite_por_sinistro"].status == "NEEDS_REVIEW"
    rules = [v["rule"] for v in by_code["limite_agregado"].value["rule_violations"]]
    assert "moeda_consistente" in rules


def test_moeda_consistente_nao_rebaixa_quando_igual(evidences_a):
    raw = [
        _fact_raw("limite_agregado", {"amount": "5000000.00", "currency": "BRL"}, "EV-A-001"),
        _fact_raw("limite_por_sinistro", {"amount": "1000000.00", "currency": "BRL"}, "EV-A-002"),
    ]
    facts = _service(raw, evidences_a).extract_fields(
        "POL-A", ["limite_agregado", "limite_por_sinistro"]
    )
    assert all(f.status == "FOUND" for f in facts)
