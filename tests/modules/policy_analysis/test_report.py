"""Testes do Relatório D&O: funções puras e `ReportService` com agente fixture.

Cobre a fórmula exata do ranking, validação de notas/pesos, empate, cenários de
sensibilidade, guarda §9 (sem vencedora sem dados), checklist §11 e o fluxo
completo do relatório (incluindo célula sem referência → "Requer confirmação").
"""

from __future__ import annotations

import pytest

from modules.policy_analysis.application.errors import ClassifiedError
from modules.policy_analysis.application.report_service import ReportService
from modules.policy_analysis.domain.report import (
    SCENARIO_RESSALVA,
    RankingResult,
    ReportCell,
    ReportRow,
    build_checklist,
    compute_ranking,
    compute_sensitivity,
    guard_sem_vencedora,
)
from modules.policy_analysis.domain.report_catalog import (
    CHECKLIST_ITEMS,
    DEFAULT_WEIGHTS,
    FIELDS_BY_CODE,
    REPORT_FIELDS,
    SENSITIVITY_SCENARIOS,
    CoverageStatus,
)
from modules.policy_analysis.infrastructure.report_agent import FixtureReportAgent

CRITERIA = tuple(DEFAULT_WEIGHTS)


def _notes(protecao_a: float, demais_a: float, protecao_b: float, demais_b: float) -> dict:
    """Notas por apólice: `protecao_individual` isolada, demais critérios iguais."""
    def build(protecao, demais):
        return {code: protecao if code == "protecao_individual" else demais for code in CRITERIA}

    return {"POL-A": build(protecao_a, demais_a), "POL-B": build(protecao_b, demais_b)}


def _row(code: str, cells: dict) -> ReportRow:
    return ReportRow(field=FIELDS_BY_CODE[code], cells=cells)


def _cell(status=CoverageStatus.PREVISTO, referencia="doc.pdf · pág. 1", origem="fato", **kwargs) -> ReportCell:
    return ReportCell(status=status, referencia=referencia, origem=origem, **kwargs)


class MarkdownSectionsSource:
    """Porta de seções via `get_markdown_sections` (duck-typing)."""

    def get_markdown_sections(self, policy_id: str) -> list[dict]:
        return [{"title": "Condições gerais", "text": f"Condições gerais da apólice {policy_id}."}]


class EvidencesSourceStub:
    """Porta de seções via `get_evidences` (duck-typing)."""

    def __init__(self, evidences_by_policy: dict):
        self._by_policy = evidences_by_policy

    def get_evidences(self, policy_id: str) -> list:
        return list(self._by_policy.get(policy_id, []))


# --- compute_ranking (§8) -----------------------------------------------------


def test_compute_ranking_formula_exata():
    notes = {"POL-A": {"c1": 8.0, "c2": 6.0}, "POL-B": {"c1": 5.0, "c2": 8.0}}
    scores = compute_ranking(notes, {"c1": 50.0, "c2": 50.0})

    assert [score.policy_id for score in scores] == ["POL-A", "POL-B"]
    assert scores[0].total == pytest.approx((8.0 * 50 + 6.0 * 50) / 10)
    assert scores[1].total == pytest.approx((5.0 * 50 + 8.0 * 50) / 10)
    assert scores[0].contribuicao_por_criterio["c1"] == pytest.approx(8.0 * 50 / 10)
    assert scores[0].contribuicao_por_criterio["c2"] == pytest.approx(6.0 * 50 / 10)
    assert scores[0].nota_por_criterio == {"c1": 8.0, "c2": 6.0}


def test_compute_ranking_rejeita_nota_fora_da_faixa():
    with pytest.raises(ValueError):
        compute_ranking({"POL-A": {"c1": 10.5}}, {"c1": 100.0})
    with pytest.raises(ValueError):
        compute_ranking({"POL-A": {"c1": -0.1}}, {"c1": 100.0})


def test_compute_ranking_rejeita_pesos_que_nao_somam_100():
    with pytest.raises(ValueError):
        compute_ranking({"POL-A": {"c1": 5.0}}, {"c1": 60.0, "c2": 30.0})


def test_compute_ranking_rejeita_criterio_sem_nota():
    with pytest.raises(ValueError):
        compute_ranking({"POL-A": {"c1": 5.0}}, {"c1": 40.0, "c2": 60.0})


def test_compute_ranking_empate_preserva_ordem_de_entrada():
    notes = {"POL-B": {"c1": 6.0}, "POL-A": {"c1": 6.0}}
    scores = compute_ranking(notes, {"c1": 100.0})

    assert [score.policy_id for score in scores] == ["POL-B", "POL-A"]


def test_compute_ranking_usando_default_weights():
    scores = compute_ranking(_notes(8.0, 7.0, 6.0, 6.5), DEFAULT_WEIGHTS)

    assert len(scores) == 2
    assert all(score.total == pytest.approx(sum(score.contribuicao_por_criterio.values())) for score in scores)


# --- compute_sensitivity (§8) -------------------------------------------------


def test_compute_sensitivity_cenario_1_muda_a_ordem_quando_protecao_domin():
    # POL-A domina proteção individual; POL-B domina os demais critérios.
    notes = _notes(protecao_a=10.0, demais_a=5.0, protecao_b=0.0, demais_b=9.0)

    base = compute_ranking(notes, DEFAULT_WEIGHTS)
    assert [score.policy_id for score in base] == ["POL-B", "POL-A"]

    results = compute_sensitivity(notes, SENSITIVITY_SCENARIOS)
    assert len(results) == 2
    assert [score.policy_id for score in results[0].scores] == ["POL-A", "POL-B"]
    # cenário 2 ("Exclusões críticas") devolve a ordem de base
    assert [score.policy_id for score in results[1].scores] == ["POL-B", "POL-A"]
    for result in results:
        assert abs(sum(result.weights.values()) - 100.0) <= 0.01
        assert result.informative_only is False


def test_compute_sensitivity_respeita_a_ordem_dos_cenarios():
    results = compute_sensitivity(_notes(8.0, 7.0, 7.0, 7.0), SENSITIVITY_SCENARIOS)
    assert [result.weights["extensoes"] for result in results] == [0.0, pytest.approx(5.0 * 100 / 105)]


# --- guard_sem_vencedora (§9) -------------------------------------------------


def test_guard_sem_vencedora_sem_premio_e_lmg():
    incomplete, motivo = guard_sem_vencedora({"lmg": False}, profile_complete=False)

    assert incomplete is True
    assert "prêmio" in motivo
    assert "LMG" in motivo


def test_guard_sem_vencedora_com_dados_completos():
    facts = {
        "preco": True,
        "lmg": True,
        "lmis": True,
        "franquias": True,
        "sublimites": True,
        "cobertura_efetivamente_contratada": True,
        "perfil_do_contratante": True,
    }
    incomplete, motivo = guard_sem_vencedora(facts, profile_complete=True)

    assert incomplete is False
    assert motivo is None


def test_guard_sem_vencedora_exige_perfil_completo():
    facts = {
        "preco": True,
        "lmg": True,
        "lmis": True,
        "franquias": True,
        "sublimites": True,
        "cobertura_efetivamente_contratada": True,
        "perfil_do_contratante": True,
    }
    incomplete, motivo = guard_sem_vencedora(facts, profile_complete=False)

    assert incomplete is True
    assert "perfil do contratante" in motivo


# --- build_checklist (§11) ----------------------------------------------------


def test_build_checklist_itens_externos_vem_do_report_data():
    checklist = build_checklist(
        {"documentos_analisados_integralmente": True, "condicoes_particulares_incluidas": True}
    )

    assert list(checklist) == list(CHECKLIST_ITEMS)
    assert checklist["documentos analisados integralmente"] is True
    assert checklist["condições particulares incluídas"] is True
    assert checklist["análise agnóstica em relação a seguradoras e número de propostas"] is False


def test_build_checklist_extensao_prevista_sem_referencia_falha():
    rows = [
        _row(
            "investigacoes_internas_externas",
            {"POL-A": _cell(status=CoverageStatus.PREVISTO, referencia=None)},
        )
    ]
    checklist = build_checklist({"rows": rows})

    assert checklist["extensões não tratadas como automaticamente contratadas"] is False

    rows[0].cells["POL-A"] = _cell(status=CoverageStatus.PREVISTO, referencia="doc.pdf · pág. 9")
    checklist = build_checklist({"rows": rows})
    assert checklist["extensões não tratadas como automaticamente contratadas"] is True


def test_build_checklist_lacuna_com_origem_de_suposição_falha():
    rows = [
        _row(
            "dano_ambiental",
            {"POL-A": _cell(status=CoverageStatus.NAO_LOCALIZADO, referencia=None, origem="inferencia")},
        )
    ]
    checklist = build_checklist({"rows": rows})

    assert checklist["nenhuma lacuna preenchida por suposição de prática de mercado"] is False


def test_build_checklist_sem_conclusao_financeira_sem_dados():
    ranking = RankingResult(scores=(), weights=dict(DEFAULT_WEIGHTS), informative_only=True)
    rows = [
        _row("lmg", {"POL-A": _cell()}),
        _row("lmi", {"POL-A": _cell()}),
        _row("limite_agregado", {"POL-A": _cell()}),
        _row("sublimites", {"POL-A": _cell()}),
    ]
    checklist = build_checklist({"rows": rows, "ranking": ranking})

    assert checklist["LMG, LMI, limite agregado e sublimites diferenciados"] is True
    assert checklist["sem conclusão financeira sem dados financeiros"] is True

    checklist = build_checklist(
        {"rows": rows, "ranking": ranking, "dados_financeiros_disponiveis": True}
    )
    assert checklist["sem conclusão financeira sem dados financeiros"] is True


# --- ReportService ------------------------------------------------------------


def test_report_service_sem_agente_disponivel():
    service = ReportService(MarkdownSectionsSource())

    with pytest.raises(ClassifiedError) as exc:
        service.build_report(["POL-A"])

    assert exc.value.code == "LLM_UNAVAILABLE"


def test_report_service_gera_relatorio_completo():
    service = ReportService(MarkdownSectionsSource(), FixtureReportAgent())

    report = service.build_report(["POL-A", "POL-B"])

    assert set(report.identifications) == {"POL-A", "POL-B"}
    assert len(report.rows) == len(REPORT_FIELDS)
    assert all(set(row.cells) == {"POL-A", "POL-B"} for row in report.rows)
    assert [table.code for table in report.tables] == [
        "pessoas_protegidas",
        "limites",
        "matriz_temporal",
        "exclusoes_criticas",
        "coberturas_sociedade",
    ]
    assert report.scenarios
    assert all(scenario.ressalva == SCENARIO_RESSALVA for scenario in report.scenarios)
    assert len(report.sensitivity) == len(SENSITIVITY_SCENARIOS)
    assert report.profile_mode == "comparacao_documental"
    assert list(report.checklist) == list(CHECKLIST_ITEMS)
    assert len(report.conclusions) == 8
    # guarda §9 ativa: sem prêmio/LMG não há vencedora geral
    assert report.ranking.informative_only is True
    assert "prêmio" in report.ranking.motivo_sem_vencedora
    assert "LMG" in report.ranking.motivo_sem_vencedora


def test_report_service_celula_sem_referencia_vira_requer_confirmacao():
    agent = FixtureReportAgent(
        cells={
            "POL-A": {
                "protecao_direta_administrador_ab_side": {
                    "status": "Previsto",
                    "origem": "fato",
                    "referencia": None,
                }
            }
        }
    )
    service = ReportService(MarkdownSectionsSource(), agent)

    report = service.build_report(["POL-A"])
    row = next(r for r in report.rows if r.field.code == "protecao_direta_administrador_ab_side")

    cell = row.cells["POL-A"]
    assert cell.status is CoverageStatus.REQUER_CONFIRMACAO
    assert cell.origem == "requer_confirmacao"
    assert cell.referencia is None


def test_report_service_com_dados_completos_libera_vencedora():
    profile = {
        "facts_available": {
            "preco": True,
            "lmg": True,
            "lmis": True,
            "franquias": True,
            "sublimites": True,
            "cobertura_efetivamente_contratada": True,
            "perfil_do_contratante": True,
        },
        "perfil_completo": True,
    }
    service = ReportService(MarkdownSectionsSource(), FixtureReportAgent())

    report = service.build_report(["POL-A", "POL-B"], profile=profile)

    assert report.profile_mode == "com_documentos_perfil"
    assert report.ranking.informative_only is False
    assert report.ranking.motivo_sem_vencedora is None


def test_report_service_aceita_fonte_de_evidencias():
    from shared_kernel.contracts import EvidenceRef

    evidence = EvidenceRef(
        evidence_id="EV-1",
        policy_id="POL-A",
        document_id="DOC-1",
        page_number=3,
        quoted_text="Cobertura de responsabilidade civil dos administradores.",
        source_type="NATIVE_TEXT",
    )
    service = ReportService(
        EvidencesSourceStub({"POL-A": [evidence]}), FixtureReportAgent()
    )

    report = service.build_report(["POL-A"])

    assert len(report.rows) == len(REPORT_FIELDS)
    assert report.ranking.scores


def test_report_service_rejeita_pesos_customizados_invalidos():
    service = ReportService(MarkdownSectionsSource(), FixtureReportAgent())

    with pytest.raises(ValueError):
        service.build_report(["POL-A"], weights={"protecao_individual": 25.0})
