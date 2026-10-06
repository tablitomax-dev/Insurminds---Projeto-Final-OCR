"""Componente de export do resumo da comparação (D2-P1-4c; retenção T-2b)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from modules.policy_analysis.public_api import PolicyAnalysisFacade
from ui.errors import sanitize_error_message

#: Caminho FIXO e documentado dos exports (T-2b): sempre `exports/` na raiz.
EXPORT_DIR = Path("exports")

#: Aviso de retenção exibido junto do botão de exportar (T-2b).
EXPORT_RETENTION_NOTICE = (
    "Aviso de retenção: o resumo é gravado em `exports/` (caminho fixo da raiz do projeto) "
    "e permanece no disco até a exclusão manual — apólices são dados confidenciais; "
    "apague o arquivo após o uso."
)


def render_export(policy_api: PolicyAnalysisFacade, comparison_id: str) -> None:
    """Exporta o resumo da comparação em Markdown com aviso de retenção."""
    st.caption(EXPORT_RETENTION_NOTICE)
    if not st.button("Exportar resumo"):
        return
    try:
        path = policy_api.export_comparison(comparison_id)
    except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
        st.error(sanitize_error_message("EXPORTACAO", error))
    else:
        st.success(f"Exportação gerada em `{EXPORT_DIR}`: {path}")
        st.download_button(
            "Baixar resumo",
            data=Path(path).read_text(encoding="utf-8"),
            file_name=Path(path).name,
        )
