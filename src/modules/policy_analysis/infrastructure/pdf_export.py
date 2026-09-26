"""Renderização do PDF da comparação (D-08, RF-08).

Documento standalone (abre sem o sistema) com TODOS os campos do catálogo,
inclusive ausentes, mais valores, direção da diferença, evidências e
explicação. `set_compression(False)` mantém o texto auditável no arquivo.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from ..domain.field_catalog import get_field
from ..domain.models import ComparisonResult


def render_comparison_pdf(result: ComparisonResult, path: str | Path) -> str:
    pdf = FPDF()
    pdf.set_compression(False)
    pdf.add_page()

    _line(pdf, 14, "B", 10, "Comparacao de Apolices D&O - Resumo da Analise")
    _line(pdf, 10, None, 6, f"ComparisonId: {result.comparison_id}")
    _line(pdf, 10, None, 6, f"Apolice A: {result.policy_id_a}")
    _line(pdf, 10, None, 6, f"Apolice B: {result.policy_id_b}")
    pdf.ln(4)

    for campo in result.campos:
        label = get_field(campo.field_code).label
        _line(pdf, 11, "B", 6, f"{label} ({campo.field_code})")
        _line(pdf, 10, None, 5, f"Resultado: {campo.resultado} (direcao: {campo.direcao})")
        _line(pdf, 10, None, 5, f"Valor A: {_fmt(campo.valor_a)}")
        _line(pdf, 10, None, 5, f"Valor B: {_fmt(campo.valor_b)}")
        _line(pdf, 10, None, 5, f"Evidencias A: {', '.join(campo.evidencias_a) or '-'}")
        _line(pdf, 10, None, 5, f"Evidencias B: {', '.join(campo.evidencias_b) or '-'}")
        _line(pdf, 10, None, 5, f"Explicacao: {campo.explicacao or 'pendente'}")
        pdf.ln(2)

    pdf.output(str(path))
    return str(path)


def _line(pdf: FPDF, size: int, style: str | None, height: float, text: str) -> None:
    """Escreve uma linha com cursor sempre na margem esquerda (gotcha do fpdf2)."""
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", style=style or "", size=size)
    pdf.multi_cell(0, height, text=_safe(text))


def _safe(text: str) -> str:
    """Fonte core do PDF é latin-1: normaliza caracteres fora do alcance."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _fmt(value: dict | None) -> str:
    return "ausente" if value is None else ", ".join(f"{k}={v}" for k, v in sorted(value.items()))
