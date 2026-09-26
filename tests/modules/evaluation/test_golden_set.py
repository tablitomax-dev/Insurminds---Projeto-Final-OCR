"""Golden set sintético (RF-04): 1 execução → relatório dos 20 casos.

A extração roda via fachada do `policy_analysis` com `LlmExtractor` injetado
(scriptado/determinístico — sem custo de LLM real). O relatório responde por
campo: campo correto? evidência correta? — e carrega a ressalva R1/R3.
"""

from fakes.policy_analysis import (
    FakeEvidenceRetriever,
    FakeExplanationGenerator,
    FakeLlmExtractor,
    InMemoryFactRepository,
    ScriptedLlmExtractor,
    make_evidence,
)
from modules.evaluation.public_api import (
    GOLDEN_SET_PATH,
    SYNTHETIC_CAVEAT,
    create_evaluation,
    load_reference_set,
)
from modules.policy_analysis.public_api import create_policy_analysis

FIELD_CODES = {
    "limite_agregado",
    "limite_por_sinistro",
    "franquia",
    "vigencia_inicio",
    "vigencia_fim",
    "base_territorial",
    "retroatividade",
    "prazo_notificacao",
    "exclusoes_chave",
    "nome_segurado",
}


def _stack(reference, outputs=None, extractor=None):
    """Fachada de análise com fakes determinísticos derivados da referência."""
    evidences_by_policy = {}
    scripted = {}
    for case in reference.cases:
        evidences_by_policy[case.policy_id] = [
            make_evidence(
                f"ev_{case.case_id}_{chunk.chunk_id}",
                policy_id=case.policy_id,
                quoted_text=chunk.text,
            )
            for chunk in case.chunks
        ]
        for expected in case.expected_facts:
            scripted[(case.policy_id, expected.field_code)] = {
                "status": expected.status,
                "value": expected.expected_value,
                "anchor": expected.evidence_quote,
            }
    if outputs:
        scripted.update(outputs)
    return create_policy_analysis(
        retriever=FakeEvidenceRetriever(evidences_by_policy=evidences_by_policy),
        llm_extractor=extractor or ScriptedLlmExtractor(scripted),
        repository=InMemoryFactRepository(),
        explanation_generator=FakeExplanationGenerator(),
    )


def test_uma_execucao_produz_o_relatorio_dos_20_casos(tmp_path):
    reference = load_reference_set(GOLDEN_SET_PATH)
    policy = _stack(reference)
    report_dir = tmp_path / "relatorios"

    report = create_evaluation(policy, report_dir=report_dir).run_evaluation(reference)

    assert len(report.entries) == 20
    assert report.totals.total_cases == 20
    assert report.totals.correct == 20
    assert report.totals.divergent == 0
    assert report.totals.evidence_correct == 20  # evidência correta em todos
    assert all(entry.result == "correto" for entry in report.entries)
    assert {entry.field_code for entry in report.entries} == FIELD_CODES
    assert {entry.policy_id for entry in report.entries} == {"pol_sint_a", "pol_sint_b"}

    # Ressalva obrigatória no artefato (RF-04).
    assert report.caveat == SYNTHETIC_CAVEAT
    assert "NÃO valida R1/R3 do PRD" in report.caveat
    assert "D2-P1-3" in report.caveat
    # OQ-02 = substring (ancoragem literal) registrado no artefato.
    assert report.oq_02 == "substring (ancoragem literal)"

    report_path = report_dir / f"evaluation_{report.run_id}.json"
    content = report_path.read_text(encoding="utf-8")
    assert report.caveat in content
    assert "golden-v1-sintetico" in content
    assert report.run_id in content


def test_caso_divergente_e_sinalizado(tmp_path):
    reference = load_reference_set(GOLDEN_SET_PATH)
    overrides = {
        ("pol_sint_a", "franquia"): {
            "status": "FOUND",
            "value": {"amount": 30000.0, "currency": "BRL", "raw_text": "R$ 25.000,00"},
            "anchor": "Franquia: R$ 25.000,00",
        },
        ("pol_sint_b", "nome_segurado"): {
            "status": "FOUND",
            "value": {"text": "Outra Empresa Ltda.", "raw_text": "Bravo Tech Ltda."},
            "anchor": "Bravo Tech Ltda.",
        },
    }

    report = create_evaluation(_stack(reference, outputs=overrides), report_dir=tmp_path).run_evaluation(
        reference
    )

    divergent = [entry for entry in report.entries if entry.result == "divergente"]
    assert {(entry.policy_id, entry.field_code) for entry in divergent} == {
        ("pol_sint_a", "franquia"),
        ("pol_sint_b", "nome_segurado"),
    }
    assert report.totals.divergent == 2
    assert report.totals.correct == 18
    for entry in divergent:
        # Divergência sempre traz os dois valores (esperado × extraído).
        assert entry.expected_scalar is not None
        assert entry.extracted_scalar is not None
        assert entry.expected_scalar != entry.extracted_scalar
        assert entry.detail


def test_relatorio_eh_deterministico(tmp_path):
    reference = load_reference_set(GOLDEN_SET_PATH)

    first = create_evaluation(_stack(reference), report_dir=tmp_path / "a").run_evaluation(reference)
    second = create_evaluation(_stack(reference), report_dir=tmp_path / "b").run_evaluation(reference)

    assert first.run_id == second.run_id
    assert first.entries == second.entries
    assert first.totals == second.totals


def test_falha_externa_nao_conta_como_erro_de_extracao(tmp_path):
    reference = load_reference_set(GOLDEN_SET_PATH)
    policy = _stack(
        reference, extractor=FakeLlmExtractor(error=RuntimeError("timeout do provedor"))
    )

    report = create_evaluation(policy, report_dir=tmp_path).run_evaluation(reference)

    assert report.totals.not_evaluated == 20
    assert report.totals.correct == 0
    for entry in report.entries:
        assert entry.result == "nao_avaliado"
        assert "falha externa" in entry.detail
        assert "timeout do provedor" not in entry.detail  # T-2a: sem mensagem crua
