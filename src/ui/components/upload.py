"""Componente de upload das apólices (D2-P1-4c)."""

from __future__ import annotations

import streamlit as st

from ui.logic import policy_id_from_filename


def render_upload_section() -> tuple:
    """Renderiza os uploads A/B; o `policy_id` deriva do nome do PDF.

    Sem campos de id na UI: o que o usuário vê é o nome real da seguradora,
    identificado por LLM após o processamento (fallback pergunta ao usuário).
    """
    st.header("1. Carregar as apólices")
    col_a, col_b = st.columns(2)
    with col_a:
        upload_a = st.file_uploader("Apólice A (PDF)", type=["pdf"], key="upload_a")
    with col_b:
        upload_b = st.file_uploader("Apólice B (PDF)", type=["pdf"], key="upload_b")
    policy_id_a = policy_id_from_filename(upload_a.name) if upload_a is not None else ""
    policy_id_b = policy_id_from_filename(upload_b.name) if upload_b is not None else ""
    return upload_a, upload_b, policy_id_a, policy_id_b
