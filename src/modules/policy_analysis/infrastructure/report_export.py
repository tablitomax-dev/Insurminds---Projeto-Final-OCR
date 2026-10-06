"""Export Markdown do Relatório D&O (§1 e §5–§11 da metodologia).

Documento standalone: identificação por documento, matriz principal, as 5
tabelas especiais, cenários com a ressalva fixa, ranking + sensibilidade,
conclusões, checklist (✓/✗) e a nota de rastreabilidade (§10) que explica a
`origem` de cada célula. O rótulo oficial de ausência é "Não localizado" —
a expressão "não existe" nunca aparece no documento.
"""

from __future__ import annotations

from pathlib import Path

from ..domain.report import RankingResult, Report
from ..domain.report_catalog import CATEGORIES, RANKING_CRITERIA, SENSITIVITY_SCENARIOS

_CONCLUSION_TITLES: dict[str, str] = {
    "5_diferencas": "5 diferenças mais relevantes",
    "5_riscos": "5 riscos mais relevantes",
    "vantagens": "Vantagens",
    "desvantagens": "Desvantagens",
    "nao_comparaveis": "Itens não comparáveis",
    "negociaveis": "Itens negociáveis",
    "perguntas_corretor": "Perguntas para o corretor",
    "documentos_adicionais": "Documentos adicionais a solicitar",
}

_IDENT_FIELDS: tuple[tuple[str, str], ...] = (
    ("seguradora", "Seguradora"),
    ("produto", "Produto"),
    ("processo_susep", "Processo SUSEP"),
    ("versao_data", "Versão/data"),
    ("publico_alvo", "Público-alvo"),
    ("empresa_aberta_fechada", "Empresa aberta/fechada"),
    ("num_paginas", "Nº de páginas"),
)


def render_report_markdown(report: Report) -> str:
    """Renderiza o Relatório D&O completo em Markdown standalone."""
    doc_label = {pid: f"Doc {index}" for index, pid in enumerate(report.policy_ids, start=1)}
    lines = [
        "# Relatório D&O — Comparação de Apólices",
        "",
        f"- **ReportId:** `{report.report_id}`",
        f"- **Documentos:** {', '.join(f'{doc_label[pid]} ({pid})' for pid in report.policy_ids)}",
        f"- **Modo de perfil:** {report.profile_mode}",
        "",
    ]
    lines += _identification_section(report, doc_label)
    lines += _matrix_section(report, doc_label)
    lines += _tables_section(report, doc_label)
    lines += _scenarios_section(report, doc_label)
    lines += _ranking_section(report, doc_label)
    lines += _conclusions_section(report)
    lines += _checklist_section(report)
    lines += _traceability_section()
    return "\n".join(lines)


def export_report(report: Report, path: str | Path) -> str:
    """Escreve o relatório em Markdown no caminho indicado e devolve o caminho."""
    Path(path).write_text(render_report_markdown(report), encoding="utf-8")
    return str(path)


# --- §1 identificação ---------------------------------------------------------


def _identification_section(report: Report, doc_label: dict[str, str]) -> list[str]:
    lines = ["## 1. Identificação dos documentos analisados", ""]
    for pid in report.policy_ids:
        ident = report.identifications.get(pid)
        lines.append(f"### {doc_label[pid]} — {pid}")
        lines.append("")
        if ident is None:
            lines += ["- **Situação:** identificação não localizada", ""]
            continue
        for attr, label in _IDENT_FIELDS:
            lines.append(f"- **{label}:** {_fmt_value(getattr(ident, attr))}")
        lines.append(f"- **Seções/natureza:** {_fmt_tuple(ident.secoes_natureza)}")
        lines.append(f"- **Coberturas descritas:** {_fmt_tuple(ident.coberturas_descritas)}")
        lines.append(f"- **Limitações:** {_fmt_tuple(ident.limitacoes)}")
        lines.append(f"- **Ausentes:** {_fmt_value(ident.ausentes)}")
        lines.append("")
    return lines


# --- §5 matriz principal ------------------------------------------------------


def _matrix_section(report: Report, doc_label: dict[str, str]) -> list[str]:
    headers = [
        "Categoria",
        "Campo",
        "Importância",
        "Documento",
        "Status de contratação",
        "Limite/franquia",
        "Exclusões e condições",
        "Impacto prático",
        "Impacto financeiro",
        "Referência documental",
    ]
    category_labels = {category.code: category.label for category in CATEGORIES}
    rows: list[list[str]] = []
    for row in report.rows:
        for pid in report.policy_ids:
            cell = row.cells.get(pid)
            if cell is None:
                continue
            rows.append(
                [
                    category_labels.get(row.field.category, row.field.category),
                    row.field.label,
                    row.field.importance.value,
                    f"{doc_label[pid]} ({pid})",
                    cell.status.value,
                    cell.limite_franquia or "—",
                    cell.exclusoes_condicoes or "—",
                    cell.impacto_pratico or "—",
                    cell.impacto_financeiro or "—",
                    cell.referencia or "—",
                ]
            )
    return ["## 5. Matriz principal de comparação", ""] + _table(headers, rows) + [""]


# --- §6 tabelas especiais -----------------------------------------------------


def _tables_section(report: Report, doc_label: dict[str, str]) -> list[str]:
    lines = ["## 6. Tabelas especiais", ""]
    for table in report.tables:
        lines.append(f"### {table.title} (`{table.code}`)")
        lines.append("")
        headers = ["Item"] + [f"{doc_label[pid]} ({pid})" for pid in report.policy_ids]
        rows = [
            [table_row.label] + [table_row.cells.get(pid) or "—" for pid in report.policy_ids]
            for table_row in table.rows
        ]
        lines += _table(headers, rows)
        lines.append("")
    return lines


# --- §7 cenários --------------------------------------------------------------


def _scenarios_section(report: Report, doc_label: dict[str, str]) -> list[str]:
    lines = ["## 7. Cenários hipotéticos", ""]
    for scenario in report.scenarios:
        lines.append(f"### {scenario.name}")
        lines.append("")
        for pid in report.policy_ids:
            lines.append(f"- **{doc_label[pid]} ({pid}):** {scenario.policy_findings.get(pid) or '—'}")
        lines.append("")
        lines.append(f"> {scenario.ressalva}")
        lines.append("")
    return lines


# --- §8 ranking e sensibilidade -----------------------------------------------


def _ranking_section(report: Report, doc_label: dict[str, str]) -> list[str]:
    lines = ["## 8. Ranking informativo (critérios e pesos)", ""]
    lines += _ranking_table(report.ranking, doc_label, include_total_column=True)
    lines.append("")
    if report.ranking.informative_only:
        motivo = report.ranking.motivo_sem_vencedora or "dados financeiros incompletos (§9)."
        lines.append(f"> **Ranking informativo, sem vencedora geral** — {motivo}")
        lines.append("")
    lines.append("### 8.1 Cenários de sensibilidade")
    lines.append("")
    for scenario, result in zip(SENSITIVITY_SCENARIOS, report.sensitivity):
        lines.append(f"#### Cenário: {scenario.name}")
        lines.append("")
        lines += _ranking_table(result, doc_label, include_total_column=False)
        lines.append("")
    return lines


def _ranking_table(
    ranking: RankingResult, doc_label: dict[str, str], include_total_column: bool
) -> list[str]:
    labels = {criterion.code: criterion.label for criterion in RANKING_CRITERIA}
    headers = ["Critério", "Peso"] + [
        f"{prefix} {doc_label[score.policy_id]}" for score in ranking.scores for prefix in ("Nota", "Contribuição")
    ]
    if include_total_column:
        headers.append("Total")
    rows: list[list[str]] = []
    for code, weight in ranking.weights.items():
        row = [labels.get(code, code), _num(weight)]
        for score in ranking.scores:
            row.append(_num(score.nota_por_criterio.get(code, 0.0)))
            row.append(_num(score.contribuicao_por_criterio.get(code, 0.0)))
        if include_total_column:
            row.append("—")
        rows.append(row)
    total_row = ["**Total**", _num(sum(ranking.weights.values()))]
    for score in ranking.scores:
        total_row.append("—")
        total_row.append(_num(score.total))
    if include_total_column:
        total_row.append("—")
    rows.append(total_row)
    return _table(headers, rows)


# --- §9 conclusões ------------------------------------------------------------


def _conclusions_section(report: Report) -> list[str]:
    lines = ["## 9. Conclusões", ""]
    for key, title in _CONCLUSION_TITLES.items():
        lines.append(f"### {title} (`{key}`)")
        lines.append("")
        lines += _render_value(report.conclusions.get(key, []))
        lines.append("")
    return lines


def _render_value(value) -> list[str]:
    if isinstance(value, dict):
        return [f"- **{key}:** {item}" for key, item in value.items()] or ["- —"]
    if isinstance(value, (list, tuple)):
        return [f"- {item}" for item in value] or ["- —"]
    return [str(value) if value else "- —"]


# --- §11 checklist ------------------------------------------------------------


def _checklist_section(report: Report) -> list[str]:
    lines = ["## 11. Checklist de verificação final", ""]
    for item, ok in report.checklist.items():
        lines.append(f"- {'✓' if ok else '✗'} {item}")
    lines.append("")
    return lines


# --- §10 rastreabilidade ------------------------------------------------------


def _traceability_section() -> list[str]:
    return [
        "## 10. Nota de rastreabilidade",
        "",
        "Toda célula com status diferente de \"Não localizado\" carrega referência documental",
        "(arquivo/página/seção); célula sem lastro documental foi rebaixada para",
        "\"Requer confirmação\" — nada de afirmação sem fonte.",
        "",
        "- **fato:** trecho localizado no documento analisado;",
        "- **interpretacao:** leitura do texto pelo analista/agente (com referência);",
        "- **inferencia:** derivada de outros trechos — revisar antes de decidir;",
        "- **nao_localizado:** ausência no conjunto de documentos analisados — a ausência",
        "  é sempre relativa aos documentos analisados (rótulo oficial \"Não localizado\");",
        "- **requer_confirmacao:** sem lastro documental suficiente; confirmar com o corretor.",
        "",
    ]


# --- helpers de renderização --------------------------------------------------


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(_esc(cell) for cell in row) + " |")
    return lines


def _esc(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _num(value) -> str:
    return f"{float(value):.2f}".replace(".", ",")


def _fmt_value(value) -> str:
    if value is None:
        return "Não localizado"
    if isinstance(value, (list, tuple)):
        return _fmt_tuple(value)
    return str(value)


def _fmt_tuple(values) -> str:
    return ", ".join(str(item) for item in values) if values else "Não localizado"
