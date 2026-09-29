"""Renderização do resumo da comparação em Markdown (OQ-04 revisada).

Documento standalone (abre em qualquer lugar) com TODOS os campos do catálogo,
inclusive ausentes, mais valores, direção da diferença, evidências e explicação.
"""

from __future__ import annotations

from pathlib import Path

from ..domain.field_catalog import get_field
from ..domain.models import ComparisonResult


def render_comparison_markdown(result: ComparisonResult, path: str | Path) -> str:
    lines = [
        "# Comparação de Apólices D&O — Resumo da Análise",
        "",
        f"- **ComparisonId:** `{result.comparison_id}`",
        f"- **Apólice A:** {result.policy_id_a}",
        f"- **Apólice B:** {result.policy_id_b}",
        "",
    ]
    for campo in result.campos:
        label = get_field(campo.field_code).label
        lines += [
            f"## {label} (`{campo.field_code}`)",
            "",
            f"- **Resultado:** {campo.resultado} (direção: {campo.direcao})",
            f"- **Valor A:** {_fmt(campo.valor_a)}",
            f"- **Valor B:** {_fmt(campo.valor_b)}",
            f"- **Evidências A:** {', '.join(campo.evidencias_a) or '—'}",
            f"- **Evidências B:** {', '.join(campo.evidencias_b) or '—'}",
            f"- **Explicação:** {campo.explicacao or 'pendente'}",
            "",
        ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def _fmt(value: dict | None) -> str:
    return "ausente" if value is None else ", ".join(f"{k}={v}" for k, v in sorted(value.items()))
