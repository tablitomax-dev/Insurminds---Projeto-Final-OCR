"""Componentes da UI do analista (D2-P1-4c, roadmap D-06).

Cada componente tem responsabilidade única e consome **apenas** as fachadas
públicas recebidas como parâmetro — nenhum SQL, consulta vetorial ou prompt
na UI (F-15).
"""

from ui.components.comparison import render_comparison
from ui.components.export import render_export
from ui.components.metrics import format_usage_summary, render_metrics_panel
from ui.components.review import group_by_severity, render_review
from ui.components.stages import render_extraction, render_processing
from ui.components.upload import render_upload_section

__all__ = [
    "format_usage_summary",
    "group_by_severity",
    "render_comparison",
    "render_export",
    "render_extraction",
    "render_metrics_panel",
    "render_processing",
    "render_review",
    "render_upload_section",
]
