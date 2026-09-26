"""T029 — E2E dos cenários Gherkin do requirements.md (feature 001)."""

from __future__ import annotations

import pytest

from modules.policy_analysis.application.errors import ClassifiedError
from modules.policy_analysis.domain.field_catalog import UnknownFieldCodeError
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import (
    FixtureExplanationAgent,
    FixtureExtractionAgent,
)
from modules.policy_analysis.public_api import PolicyAnalysisFacade

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

EXPECTED = {
    "limite_agregado": "MAIOR",
    "limite_por_sinistro": "IGUAL",
    "franquia": "MAIOR",
    "vigencia": "MENOR",
    "prazo_notificacao_sinistro": "MAIOR",
    "extensao_territorial": "DIVERGENTE",
    "exclusoes_chave": "DIVERGENTE",
    "limite_defesa_custos": "AUSENTE_B",
    "retroatividade": "MENOR",
    "indice_reajuste": "AGUARDANDO_REVISAO",
}


class BadAgent:
    """Agente que devolve saída fora do contrato (cenário negativo)."""

    def extract(self, requests, run_id):
        return [{"field_code": "franquia", "status": "FOUND", "value": {}, "confidence": 42}]


def build_facade(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path, agent=None, explainer=None):
    source = MockEvidenceSource({"POL-A": evidences_a, "POL-B": evidences_b})
    extraction_agent = agent or FixtureExtractionAgent(
        {"POL-A": fixture_a["llm_output"], "POL-B": fixture_b["llm_output"]}
    )
    explanation_agent = explainer or FixtureExplanationAgent({})
    return PolicyAnalysisFacade(
        source,
        extraction_agent,
        explanation_agent,
        db_path=":memory:",
        output_dir=str(tmp_path),
    )


def test_cenario_extração_comparacao_e_export(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path):
    facade = build_facade(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path)

    facade.extract_fields("POL-A", ALL_CODES)
    facade.extract_fields("POL-B", ALL_CODES)
    result = facade.compare_policies("POL-A", "POL-B")

    assert {c.field_code: c.resultado for c in result.campos} == EXPECTED

    for campo in result.campos:
        if campo.resultado not in ("IGUAL", "AUSENTES_AMBOS", "AGUARDANDO_REVISAO"):
            explanation = facade.explain_difference(result.comparison_id, campo.field_code)
            assert set(explanation.evidence_ids) <= (
                set(campo.evidencias_a) | set(campo.evidencias_b)
            )

    path = facade.export_comparison(result.comparison_id)
    assert open(path, "rb").read().startswith(b"%PDF")


def test_cenario_revisao_humana_de_fato_ambiguo(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path):
    facade = build_facade(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path)
    facade.extract_fields("POL-A", ALL_CODES)
    facade.extract_fields("POL-B", ALL_CODES)

    pending = facade.list_review_queue("POL-A")
    assert [item.fact.field_code for item in pending] == ["indice_reajuste"]
    assert pending[0].fact.evidence_ids == ["EV-A-010", "EV-A-011"]  # evidência anexa

    # a comparação daquele campo aguarda a decisão
    result = facade.compare_policies("POL-A", "POL-B")
    assert result.campo("indice_reajuste").resultado == "AGUARDANDO_REVISAO"

    # decisão registrada → comparação resolve o campo
    facade.record_review_decision(
        "FAC-POL-A-indice_reajuste",
        decision="CORRIGIDO",
        decided_by="analista@insurminds",
        value={"number": "5", "unit": "%"},
    )
    result = facade.compare_policies("POL-A", "POL-B")
    assert result.campo("indice_reajuste").resultado == "MAIOR"


def test_cenario_field_code_fora_do_catalogo_e_rejeitado(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path):
    facade = build_facade(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path)

    with pytest.raises(UnknownFieldCodeError):
        facade.extract_field("POL-A", "campo_desconhecido")


def test_cenario_campo_ausente_nao_e_erro(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path):
    facade = build_facade(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path)
    facade.extract_fields("POL-A", ALL_CODES)
    facade.extract_fields("POL-B", ALL_CODES)

    fact_b = {f.field_code: f for f in facade.get_facts("POL-B")}["limite_defesa_custos"]
    assert fact_b.status == "NOT_FOUND"  # nunca exceção

    result = facade.compare_policies("POL-A", "POL-B")
    assert result.campo("limite_defesa_custos").resultado == "AUSENTE_B"


def test_cenario_saida_llm_invalida_nao_vira_fato(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path):
    facade = build_facade(
        fixture_a, fixture_b, evidences_a, evidences_b, tmp_path, agent=BadAgent()
    )

    with pytest.raises(ClassifiedError):
        facade.extract_field("POL-A", "franquia")
    assert facade.get_facts("POL-A") == []


def test_cenario_fatos_persistem_com_ids_do_indice(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path):
    facade = build_facade(fixture_a, fixture_b, evidences_a, evidences_b, tmp_path)
    facade.extract_fields("POL-A", ALL_CODES)
    facade.extract_fields("POL-B", ALL_CODES)

    known_a = {ev.evidence_id for ev in evidences_a}
    known_b = {ev.evidence_id for ev in evidences_b}
    for fact in facade.get_facts("POL-A"):
        assert set(fact.evidence_ids) <= known_a  # mesmos IDs dos chunks indexados
    for fact in facade.get_facts("POL-B"):
        assert set(fact.evidence_ids) <= known_b
