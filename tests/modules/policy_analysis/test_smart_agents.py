"""Agentes inteligentes do policy_analysis: seguradora, perguntas e revisão (RF-04/RF-07 + agentes)."""

from __future__ import annotations

import pytest

from fakes.policy_analysis import SlotFallback, make_evidence
from modules.policy_analysis.application.errors import ClassifiedError
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import (
    FixtureExplanationAgent,
    FixtureExtractionAgent,
    FixtureInsurerNameAgent,
    InsurerNameAgent,
    LLMQuestionAgent,
    LLMReviewAgent,
    build_insurer_prompt,
    build_question_prompt,
)
from modules.policy_analysis.public_api import (
    AGENT_REVIEWER,
    PolicyAnalysisFacade,
)


class StubLLMClient:
    """Cliente de LLM roteirizado: devolve a resposta fixa e guarda o prompt."""

    def __init__(self, response):
        self._response = response
        self.usage: list[dict] = []
        self.prompt = ""

    def complete_json(self, prompt: str):
        self.prompt = prompt
        return self._response


class StubInsurerAgent:
    def __init__(self, info: dict | None = None, error: Exception | None = None):
        self._info = info
        self._error = error
        self.calls = 0

    def identify(self, policy_id, page_texts, run_id):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._info


class StubReviewAgent:
    def __init__(self, corrections: list[dict]):
        self._corrections = corrections
        self.facts: list[dict] = []

    def corrections(self, message, facts, run_id):
        self.facts = facts
        return self._corrections


#: Saída roteirizada de extração para o fato de teste.
_OUTPUTS = {
    "POL-A": [
        {
            "field_code": "limite_agregado",
            "status": "FOUND",
            "value": {"amount": "5000000.00", "currency": "BRL"},
            "confidence": 0.95,
            "evidence_ids": ["EV-A-001"],
            "requires_human_review": False,
        }
    ]
}


def _facade_with_fact(**kwargs) -> PolicyAnalysisFacade:
    """Fachada com um fato `POL-A/limite_agregado` extraído (repo em memória)."""
    source = MockEvidenceSource({"POL-A": [make_evidence("EV-A-001", policy_id="POL-A")]})
    facade = PolicyAnalysisFacade(
        source,
        FixtureExtractionAgent(_OUTPUTS),
        FixtureExplanationAgent({}),
        db_path=":memory:",
        **kwargs,
    )
    facade.extract_fields("POL-A", ["limite_agregado"])
    return facade


# --- agente de seguradora -----------------------------------------------------


def test_insurer_name_agent_identifica_nome_e_ano():
    client = StubLLMClient({"name": "Porto Seguro", "year": "2024"})
    agent = InsurerNameAgent(client)
    assert agent.identify("POL-A", ["APOLICE D&O — Porto Seguro..."], run_id="r1") == {
        "name": "Porto Seguro",
        "year": "2024",
    }
    assert "## Página 1" in client.prompt


def test_insurer_name_agent_nao_inventa_nome():
    client = StubLLMClient({"name": "null", "year": None})
    agent = InsurerNameAgent(client)
    assert agent.identify("POL-A", ["(sem texto)"], run_id="r1") == {
        "name": None,
        "year": None,
    }


def test_fixture_insurer_name_agent_lookup_por_policy_id():
    agent = FixtureInsurerNameAgent({"POL-A": {"name": "Seguradora Alfa", "year": "2025"}})
    assert agent.identify("POL-A", [], run_id="r1") == {
        "name": "Seguradora Alfa",
        "year": "2025",
    }
    assert agent.identify("POL-Z", [], run_id="r1") == {"name": None, "year": None}


def test_slot_fallback_mapeia_ids_desconhecidos_por_ordem():
    slots = SlotFallback({"POL-A": ["a"], "POL-B": ["b"]})
    assert slots.get("POL-A") == ["a"]  # id conhecido casa exato
    assert slots.get("apolice_porto_2024") == ["a"]  # 1º desconhecido → 1ª fixture
    assert slots.get("apolice_allianz") == ["b"]  # 2º desconhecido → 2ª fixture
    assert slots.get("apolice_porto_2024") == ["a"]  # estável por id


def test_insurer_prompt_mostra_as_paginas():
    prompt = build_insurer_prompt(["primeira página", "segunda página"])
    assert "primeira página" in prompt
    assert "segunda página" in prompt
    assert "## Página 2" in prompt


# --- agente de perguntas (RAG) ------------------------------------------------


def test_question_agent_responde_com_citacoes():
    client = StubLLMClient({"text": "O limite é R$ 5 mi.", "evidence_ids": ["EV-A-001"]})
    agent = LLMQuestionAgent(client)
    evidences = [make_evidence("EV-A-001", policy_id="POL-A")]
    answer = agent.answer("Qual o limite agregado?", evidences, run_id="r1")
    assert answer == {"text": "O limite é R$ 5 mi.", "evidence_ids": ["EV-A-001"]}
    assert "Qual o limite agregado?" in client.prompt
    assert "EV-A-001" in client.prompt


def test_question_prompt_exige_base_nas_evidencias():
    prompt = build_question_prompt("pergunta", [make_evidence("EV-1")])
    assert "SOMENTE com base nas evidências" in prompt
    assert "Nunca invente" in prompt


# --- agente de revisão --------------------------------------------------------


def test_review_agent_parses_corrections():
    client = StubLLMClient(
        {"corrections": [{"fact_id": "f1", "decision": "CORRIGIDO", "value": "R$ 2.000.000"}]}
    )
    agent = LLMReviewAgent(client)
    corrections = agent.corrections("o limite está errado", [{"fact_id": "f1"}], run_id="r1")
    assert corrections == [
        {"fact_id": "f1", "decision": "CORRIGIDO", "value": "R$ 2.000.000"}
    ]


def test_review_agent_schema_invalido_levanta_classified_error():
    client = StubLLMClient({"corrections": "não é lista"})
    agent = LLMReviewAgent(client)
    with pytest.raises(ClassifiedError) as excinfo:
        agent.corrections("msg", [], run_id="r1")
    assert excinfo.value.code == "LLM_SCHEMA_INVALID"


# --- fachada: identify_insurer / answer_question / apply_review_feedback ------


def test_identify_insurer_sem_agente_retorna_none():
    facade = _facade_with_fact()
    assert facade.identify_insurer("POL-A", ["texto"]) is None


def test_identify_insurer_degrada_para_none_em_falha():
    facade = _facade_with_fact(insurer_agent=StubInsurerAgent(error=RuntimeError("boom")))
    assert facade.identify_insurer("POL-A", ["texto"]) is None


def test_identify_insurer_devolve_nome_e_ano():
    facade = _facade_with_fact(
        insurer_agent=StubInsurerAgent({"name": "Allianz", "year": "2025"})
    )
    assert facade.identify_insurer("POL-A", ["texto"]) == {
        "name": "Allianz",
        "year": "2025",
    }


def test_identify_insurer_leitura_direta_nao_chama_a_llm():
    # OCR-primeiro: nome confiável na página resolve SEM custo de LLM.
    agent = StubInsurerAgent({"name": "Nome Inventado", "year": "1999"})
    facade = _facade_with_fact(insurer_agent=agent)
    info = facade.identify_insurer(
        "POL-A", ["[OCR/visão]\nTOKIO MARINE SEGUROS\nVigência: 01/03/2025"]
    )
    assert info == {"name": "TOKIO MARINE SEGUROS", "year": "2025"}
    assert agent.calls == 0


def test_identify_insurer_escala_para_llm_no_caso_estranho():
    # Dois candidatos divergentes: caso estranho → a LLM confirma.
    agent = StubInsurerAgent({"name": "Porto Seguro", "year": "2025"})
    facade = _facade_with_fact(insurer_agent=agent)
    info = facade.identify_insurer(
        "POL-A", ["Porto Seguro\nAllianz Seguros"]
    )
    assert info == {"name": "Porto Seguro", "year": "2025"}
    assert agent.calls == 1


def test_answer_question_sem_agente_levanta_classified_error():
    facade = _facade_with_fact()
    with pytest.raises(ClassifiedError) as excinfo:
        facade.answer_question("pergunta", [])
    assert excinfo.value.code == "LLM_UNAVAILABLE"


def test_apply_review_feedback_aplica_correcao_e_registra_auditoria():
    facade = _facade_with_fact()
    fact = facade.get_facts("POL-A")[0]
    review_agent = StubReviewAgent(
        [{"fact_id": fact.fact_id, "decision": "CORRIGIDO", "value": "2000000.00"}]
    )
    facade._review_agent = review_agent

    result = facade.apply_review_feedback("limite agregado está errado", ["POL-A"])

    assert [item["field_code"] for item in result["applied"]] == ["limite_agregado"]
    assert result["skipped"] == []
    # O agente recebeu os fatos candidatos com evidências.
    assert review_agent.facts[0]["fact_id"] == fact.fact_id
    # Auditoria: revisor do Agente + nota com a mensagem original do revisor.
    decisions = facade.list_review_decisions("POL-A")
    assert decisions[0].revisao_por == AGENT_REVIEWER
    assert decisions[0].revisao_decisao.get("nota") == "limite agregado está errado"


def test_apply_review_feedback_pula_fato_desconhecido_e_correcao_invalida():
    facade = _facade_with_fact()
    facade._review_agent = StubReviewAgent(
        [
            {"fact_id": "nao_existe", "decision": "CORRIGIDO", "value": "x"},
            {"fact_id": facade.get_facts("POL-A")[0].fact_id, "decision": "CORRIGIDO", "value": None},
        ]
    )
    result = facade.apply_review_feedback("mensagem", ["POL-A"])
    assert result["applied"] == []
    reasons = {item["fact_id"]: item["reason"] for item in result["skipped"]}
    assert reasons["nao_existe"] == "UNKNOWN_FACT"


def test_apply_review_feedback_sem_fatos_nao_chama_agente():
    facade = PolicyAnalysisFacade(
        MockEvidenceSource({}),
        FixtureExtractionAgent({}),
        FixtureExplanationAgent({}),
        db_path=":memory:",
        review_agent=StubReviewAgent([{"fact_id": "x"}]),
    )
    result = facade.apply_review_feedback("mensagem", ["POL-A"])
    assert result == {"applied": [], "skipped": []}
