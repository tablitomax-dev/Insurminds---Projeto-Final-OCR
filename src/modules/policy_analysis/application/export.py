"""Export do resumo da comparação em Markdown standalone (RF-08, OQ-04 revisada)."""

from __future__ import annotations

from pathlib import Path

from .errors import ClassifiedError


def _default_renderer():
    """Composição adiada: o renderizador vive na infrastructure (injeção)."""
    from ..infrastructure.markdown_export import render_comparison_markdown

    return render_comparison_markdown


class ExportService:
    """Casos de uso de export da defesa da análise."""

    def __init__(self, repo, output_dir: str = "exports", renderer=None):
        self._repo = repo
        self._output_dir = output_dir
        self._renderer = renderer

    def export_comparison(self, comparison_id: str) -> str:
        result = self._repo.get_comparison(comparison_id)
        if result is None:
            raise ClassifiedError(
                "COMPARISON_NOT_FOUND", f"comparação não encontrada: {comparison_id}", retriable=False
            )
        Path(self._output_dir).mkdir(parents=True, exist_ok=True)
        path = str(Path(self._output_dir) / f"{comparison_id}.md")
        renderer = self._renderer or _default_renderer()
        return renderer(result, path)
