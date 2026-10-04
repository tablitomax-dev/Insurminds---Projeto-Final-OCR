"""T010 — Agente de extração: validação de schema, evidência real, retry (RF-03, RF-09, EC-01)."""

from __future__ import annotations

import traceback

import pytest

from modules.policy_analysis.application.errors import ClassifiedError, to_processing_status
from modules.policy_analysis.application.extraction import ExtractionService
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import (
    FixtureExtractionAgent,
    MultiFieldExtractionAgent,
)

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


class StubAgent:
    """Agente que devolve uma saída bruta pronta (para casos de violação)."""

    def __init__(self, raw_list: list[dict]):
        self.raw_list = raw_list
        self.calls = 0

    def extract(self, requests, run_id):
        self.calls += 1
        return self.raw_list


class FlakyClient:
    """Cliente LLM que falha N vezes antes de responder (EC-01)."""

    def __init__(self, fail_times: int, response=None):
        self.fail_times = fail_times
        self.calls = 0
        self.response = response if response is not None else {"facts": []}

    def complete_json(self, prompt: str):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TimeoutError("provedor indisponível")
        return self.response


def test_extracao_valida_usa_apenas_evidencias_do_pedido(fixture_a, evidences_a):
    repo = _memory_repo()
    service = ExtractionService(
        MockEvidenceSource({"POL-A": evidences_a}),
        FixtureExtractionAgent({"POL-A": fixture_a["llm_output"]}),
        repo,
    )
    facts = service.extract_fields("POL-A", ALL_CODES)

    assert len(facts) == 10
    by_code = {f.field_code: f for f in facts}
    assert by_code["limite_agregado"].status == "FOUND"
    assert by_code["limite_agregado"].evidence_ids == ["EV-A-001"]
    assert by_code["indice_reajuste"].status == "AMBIGUOUS"
    assert by_code["indice_reajuste"].requires_human_review is True
    # normalização determinística aplicada pelo serviço
    assert by_code["limite_agregado"].normalized_value == {"amount": "5000000.00", "currency": "BRL"}
    assert by_code["vigencia"].normalized_value["duration_days"] == 365


def test_agente_multi_campo_faz_uma_chamada_por_apolice(fixture_a, evidences_a):
    agent = FixtureExtractionAgent({"POL-A": fixture_a["llm_output"]})
    repo = _memory_repo()
    service = ExtractionService(MockEvidenceSource({"POL-A": evidences_a}), agent, repo)

    service.extract_fields("POL-A", ALL_CODES)
    assert agent.calls == 1


def test_evidencia_fora_do_pedido_nao_vira_fato(fixture_a, evidences_a):
    raw = [
        {
            "field_code": "franquia",
            "status": "FOUND",
            "value": {"amount": "50000.00", "currency": "BRL"},
            "confidence": 0.9,
            "evidence_ids": ["EV-INEXISTENTE"],
            "requires_human_review": False,
        }
    ]
    repo = _memory_repo()
    service = ExtractionService(MockEvidenceSource({"POL-A": evidences_a}), StubAgent(raw), repo)

    with pytest.raises(ClassifiedError) as exc:
        service.extract_fields("POL-A", ["franquia"])
    assert exc.value.code == "EVIDENCE_UNKNOWN"
    assert repo.get_facts("POL-A") == []


def test_campo_ausente_na_saida_vira_not_found(fixture_a, evidences_a):
    raw = [
        {
            "field_code": "franquia",
            "status": "FOUND",
            "value": {"amount": "50000.00", "currency": "BRL"},
            "confidence": 0.9,
            "evidence_ids": ["EV-A-003"],
            "requires_human_review": False,
        }
    ]
    repo = _memory_repo()
    service = ExtractionService(MockEvidenceSource({"POL-A": evidences_a}), StubAgent(raw), repo)

    facts = service.extract_fields("POL-A", ["franquia", "vigencia"])
    by_code = {f.field_code: f for f in facts}
    assert by_code["vigencia"].status == "NOT_FOUND"
    assert by_code["vigencia"].evidence_ids == []


def test_saida_fora_do_schema_nunca_vira_fato(fixture_a, evidences_a):
    raw = [{"field_code": "franquia", "status": "FOUND", "value": {}, "confidence": 99}]
    repo = _memory_repo()
    service = ExtractionService(MockEvidenceSource({"POL-A": evidences_a}), StubAgent(raw), repo)

    with pytest.raises(ClassifiedError) as exc:
        service.extract_fields("POL-A", ["franquia"])
    assert exc.value.code == "LLM_SCHEMA_INVALID"
    assert repo.get_facts("POL-A") == []


#: Marcador de texto de apólice: nunca pode vazar em erro classificado (T-2a).
APOLICE_MARKER = "TEXTO-CONFIDENCIAL-APOLICE-XYZ"


def test_erro_de_schema_nao_ecoa_texto_de_apolice(fixture_a, evidences_a):
    """Reprodução/anti-vazamento BUG-20261004-YFN3 (T-2a)."""
    raw = [
        {
            "field_code": "franquia",
            "status": "FOUND",
            "value": {"amount": "50000.00", "currency": "BRL"},
            "confidence": APOLICE_MARKER,
            "evidence_ids": ["EV-A-003"],
            "requires_human_review": False,
        }
    ]
    repo = _memory_repo()
    service = ExtractionService(MockEvidenceSource({"POL-A": evidences_a}), StubAgent(raw), repo)

    with pytest.raises(ClassifiedError) as excinfo:
        service.extract_fields("POL-A", ["franquia"])

    error = excinfo.value
    assert error.code == "LLM_SCHEMA_INVALID"
    assert error.retriable is True
    # Diagnóstico permitido (padrão T-2a do projeto): campo + tipo + contagem.
    assert "franquia" in error.message
    assert "ValidationError" in error.message
    assert "1 problema" in error.message
    # Anti-vazamento: o marcador não chega a NENHUMA superfície de renderização.
    assert APOLICE_MARKER not in str(error)
    assert APOLICE_MARKER not in repr(error)
    assert APOLICE_MARKER not in error.to_dict()["message"]
    assert APOLICE_MARKER not in to_processing_status("DOC-1", error).message
    assert APOLICE_MARKER not in "".join(traceback.format_exception(error))
    # Guarda mecanística da decisão `from None` (política T-2a): falha se alguém
    # voltar a `from exc` mantendo a mensagem limpa.
    assert error.__cause__ is None and error.__suppress_context__


def test_retry_com_backoff_diante_de_falha_temporaria():
    client = FlakyClient(fail_times=2, response={"facts": []})
    agent = MultiFieldExtractionAgent(client, retries=3, backoff=0)

    assert agent.extract([], "RUN-1") == []
    assert client.calls == 3


def test_falha_persistente_vira_erro_classificado_reexecutavel():
    client = FlakyClient(fail_times=99)
    agent = MultiFieldExtractionAgent(client, retries=3, backoff=0)

    with pytest.raises(ClassifiedError) as exc:
        agent.extract([], "RUN-1")
    assert exc.value.code == "LLM_UNAVAILABLE"
    assert exc.value.retriable is True
    assert client.calls == 3


def test_resposta_nao_estruturada_e_rejeitada():
    client = FlakyClient(fail_times=0, response="não é json estruturado")
    agent = MultiFieldExtractionAgent(client, retries=1, backoff=0)

    with pytest.raises(ClassifiedError) as exc:
        agent.extract([], "RUN-1")
    assert exc.value.code == "LLM_SCHEMA_INVALID"


# --- D2-P2-2: prompts versionados (hash auditável) --------------------------


def test_prompt_fingerprint_estavel_e_detecta_mudanca():
    from modules.policy_analysis.infrastructure.llm_agent import prompt_fingerprint

    assert prompt_fingerprint("abc") == prompt_fingerprint("abc")
    assert prompt_fingerprint("abc") != prompt_fingerprint("abd")


def test_prompts_versionados_registrados_no_uso():
    from modules.policy_analysis.infrastructure.llm_agent import (
        EXTRACTION_PROMPT_VERSION,
    )

    client = FlakyClient(fail_times=0, response={"facts": []})
    agent = MultiFieldExtractionAgent(client, retries=1, backoff=0)
    agent.extract([], "RUN-1")

    uso = agent.usage[-1]
    assert uso["prompt_version"] == EXTRACTION_PROMPT_VERSION
    assert uso["prompt_hash"]


def _memory_repo():
    from modules.policy_analysis.infrastructure.duckdb_repository import PolicyAnalysisRepository

    return PolicyAnalysisRepository(":memory:")
