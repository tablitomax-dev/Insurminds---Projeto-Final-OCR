"""Testes do export Markdown do Relatório D&O (§1, §5–§11)."""

from __future__ import annotations

from modules.policy_analysis.application.report_service import ReportService
from modules.policy_analysis.domain.report_catalog import CHECKLIST_ITEMS
from modules.policy_analysis.infrastructure.report_agent import FixtureReportAgent
from modules.policy_analysis.infrastructure.report_export import (
    export_report,
    render_report_markdown,
)


class MarkdownSectionsSource:
    def get_markdown_sections(self, policy_id: str) -> list[dict]:
        return [{"title": "Condições gerais", "text": f"Condições gerais da apólice {policy_id}."}]


def _report():
    service = ReportService(MarkdownSectionsSource(), FixtureReportAgent())
    return service.build_report(["POL-A", "POL-B"])


def test_render_inclui_matriz_tabelas_ranking_sensibilidade_e_checklist():
    text = render_report_markdown(_report())

    assert text.startswith("# Relatório D&O")
    # §5 matriz principal, com as colunas da metodologia
    assert "Matriz principal de comparação" in text
    for column in (
        "Categoria",
        "Campo",
        "Importância",
        "Status de contratação",
        "Limite/franquia",
        "Exclusões e condições",
        "Impacto prático",
        "Impacto financeiro",
        "Referência documental",
    ):
        assert column in text, f"coluna ausente: {column}"
    # §6 as 5 tabelas especiais
    for title in (
        "Pessoas protegidas",
        "Limites, sublimites e franquias",
        "Matriz temporal",
        "Exclusões críticas",
        "Cobertura da sociedade e reembolso",
    ):
        assert title in text, f"tabela ausente: {title}"
    # §8 ranking e sensibilidade
    assert "Ranking informativo" in text
    assert "Critério" in text and "Peso" in text and "Contribuição" in text
    assert "Cenários de sensibilidade" in text
    assert "Proteção individual elevada" in text
    assert "Exclusões críticas" in text
    # §11 checklist com ✓/✗
    assert "Checklist de verificação final" in text
    assert "✓" in text and "✗" in text
    for item in CHECKLIST_ITEMS:
        assert item in text, f"item de checklist ausente: {item}"


def test_render_usa_nao_localizado_nunca_nao_existe():
    text = render_report_markdown(_report())

    assert "Não localizado" in text
    assert "não existe" not in text.lower()


def test_render_inclui_ressalva_dos_cenarios_e_nota_de_rastreabilidade():
    text = render_report_markdown(_report())

    assert "Cenário hipotético — sem afirmar que a cobertura será necessariamente aceita." in text
    assert "Nota de rastreabilidade" in text
    assert "requer_confirmacao" in text
    assert "fato" in text


def test_render_marca_ranking_informativo_sem_vencedora():
    text = render_report_markdown(_report())

    assert "ranking informativo, sem vencedora geral" in text.lower()


def test_export_report_gra_arquivo_markdown(tmp_path):
    report = _report()
    path = export_report(report, tmp_path / "relatorio.md")

    assert path.endswith(".md")
    content = open(path, encoding="utf-8").read()
    assert content == render_report_markdown(report)
    assert len(content) > 1000
