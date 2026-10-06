"""Achados extras (fora do catálogo fechado): agente, validação e persistência."""

from __future__ import annotations

import pytest

from modules.policy_analysis.application.errors import ClassifiedError
from modules.policy_analysis.domain.metrics import KIND_EXTRA, UsageMetricsCollector
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import (
    EXTRA_FINDINGS_PROMPT_VERSION,
    FixtureExplanationAgent,
    FixtureExtractionAgent,
    FixtureExtraFindingsAgent,
    LLMExtraFindingsAgent,
    build_extra_findings_prompt,
)
from modules.policy_analysis.public_api import PolicyAnalysisFacade
from shared_kernel.contracts import EvidenceRef

#: Markdown de duas páginas → evidências `ev_md_POL-A:p1:s0` e `ev_md_POL-A:p2:s0`.
PAGES = [
    (1, "# Produto\nApólice D&O SUSEP 12345.\n"),
    (2, "# Prazos\nNotificação em até 30 dias.\n"),
]

IDS = ["ev_md_POL-A:p1:s0", "ev_md_POL-A:p2:s0"]


class StubLLMClient:
    """Cliente de LLM roteirizado: devolve a resposta fixa e guarda o prompt."""

    def __init__(self, response):
        self._response = response
        self.usage: list[dict] = []
        self.prompt = ""

    def complete_json(self, prompt: str):
        self.prompt = prompt
        return self._response


def make_facade(extra_findings_agent=None, pages=None) -> PolicyAnalysisFacade:
    """Fachada em memória com markdown da `POL-A` já cacheado no repo."""
    facade = PolicyAnalysisFacade(
        MockEvidenceSource({}),
        FixtureExtractionAgent({}),
        FixtureExplanationAgent({}),
        db_path=":memory:",
        extra_findings_agent=extra_findings_agent,
    )
    facade.store_markdown("POL-A", PAGES if pages is None else pages, fingerprint="fp-1")
    return facade


def finding(label: str = "Produto", evidence_ids: list[str] | None = None, **extra) -> dict:
    item = {
        "label": label,
        "value": "D&O SUSEP 12345",
        "detail": "Produto identificado na abertura da apólice.",
        "evidence_ids": list(evidence_ids if evidence_ids is not None else [IDS[0]]),
    }
    item.update(extra)
    return item


# --- fachada: extração, validação e persistência ------------------------------


def test_agente_fixture_persiste_e_devolve():
    agent = FixtureExtraFindingsAgent({"POL-A": [finding()]})
    facade = make_facade(agent)

    findings = facade.extract_extra_findings("POL-A")

    assert len(findings) == 1
    assert findings[0]["finding_id"] == "EXF-POL-A-000"
    assert findings[0]["policy_id"] == "POL-A"
    assert findings[0]["label"] == "Produto"
    assert findings[0]["value"] == "D&O SUSEP 12345"
    assert findings[0]["evidence_ids"] == [IDS[0]]
    assert facade.get_extra_findings("POL-A") == findings


def test_evidence_id_inventado_e_descartado():
    agent = FixtureExtraFindingsAgent(
        {
            "POL-A": [
                finding("Legítimo", [IDS[0]]),
                finding("Inventado", ["ev_md_POL-A:p9:s9"]),  # RN-02: id nunca visto
                finding("Sem evidência", []),  # sem rastro não vira achado
            ]
        }
    )
    facade = make_facade(agent)

    findings = facade.extract_extra_findings("POL-A")

    assert [item["label"] for item in findings] == ["Legítimo"]


def test_reextracao_e_idempotente_e_nao_duplica():
    agent = FixtureExtraFindingsAgent({"POL-A": [finding("A", [IDS[0]]), finding("B", [IDS[1]])]})
    facade = make_facade(agent)

    primeira = facade.extract_extra_findings("POL-A")
    segunda = facade.extract_extra_findings("POL-A")

    assert len(primeira) == 2
    assert segunda == primeira
    assert len(facade.get_extra_findings("POL-A")) == 2


def test_sem_agente_configurado_levanta_classified_error():
    facade = make_facade()

    with pytest.raises(ClassifiedError) as excinfo:
        facade.extract_extra_findings("POL-A")

    assert excinfo.value.code == "LLM_UNAVAILABLE"


# --- store_markdown / get_markdown_sections -----------------------------------


def test_store_markdown_e_get_markdown_sections():
    facade = make_facade(pages=[])

    facade.store_markdown("POL-B", [(1, "# Cobertura\nLimite de R$ 1.000.000.\n")], "fp-2")
    sections = facade.get_markdown_sections("POL-B")

    assert sections == [
        {"title": "Cobertura", "text": "Limite de R$ 1.000.000.", "page_number": 1}
    ]


# --- agente LLM e prompt -----------------------------------------------------


def test_llm_extra_findings_agent_valida_ids_e_registra_uso():
    client = StubLLMClient(
        {
            "findings": [
                finding("SUSEP", ["ev_md_POL-A:p1:s0"], value="12345"),
                finding("Inventado", ["ev_INVENTADA"]),
            ]
        }
    )
    collector = UsageMetricsCollector()
    agent = LLMExtraFindingsAgent(client, usage_collector=collector)
    evidences = [
        EvidenceRef(
            evidence_id="ev_md_POL-A:p1:s0",
            policy_id="POL-A",
            document_id="POL-A",
            page_number=1,
            section_name="Produto",
            quoted_text="Apólice D&O SUSEP 12345.",
            source_type="PP_STRUCTURE",
        )
    ]

    findings = agent.extract("POL-A", evidences, run_id="run-1")

    assert [item["label"] for item in findings] == ["SUSEP"]
    assert findings[0]["value"] == "12345"
    assert collector.records_for("run-1")[0].kind == KIND_EXTRA
    assert agent.usage[0]["prompt_version"] == EXTRA_FINDINGS_PROMPT_VERSION


def test_llm_extra_findings_agent_sem_achados_devolve_lista_vazia():
    agent = LLMExtraFindingsAgent(StubLLMClient({"findings": []}))

    assert agent.extract("POL-A", [], run_id="run-1") == []


def test_prompt_builder_inclui_secoes_e_proibe_ids_inventados():
    evidence = EvidenceRef(
        evidence_id="ev_md_POL-A:p1:s0",
        policy_id="POL-A",
        document_id="POL-A",
        page_number=1,
        section_name="Produto",
        quoted_text="Apólice D&O SUSEP 12345.",
        source_type="PP_STRUCTURE",
    )

    prompt = build_extra_findings_prompt([evidence])

    assert "ev_md_POL-A:p1:s0" in prompt
    assert "Apólice D&O SUSEP 12345." in prompt
    assert "seção Produto" in prompt
    assert '"findings"' in prompt
    assert "nunca invente" in prompt.casefold()
    assert "page_hint" in prompt
