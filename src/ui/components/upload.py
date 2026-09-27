"""Componente de upload das apólices (D2-P1-4c)."""

from __future__ import annotations

import streamlit as st


def render_upload_section() -> tuple:
    """Renderiza os uploads A/B e os `policy_id`; devolve a tupla dos 4 campos."""
    st.header("1. Carregar as apólices")
    col_a, col_b = st.columns(2)
    with col_a:
        upload_a = st.file_uploader("Apólice A (PDF)", type=["pdf"], key="upload_a")
        policy_id_a = st.text_input("policy_id A", value="pol_acme", key="pol_a")
    with col_b:
        upload_b = st.file_uploader("Apólice B (PDF)", type=["pdf"], key="upload_b")
        policy_id_b = st.text_input("policy_id B", value="pol_bravo", key="pol_b")
    return upload_a, upload_b, policy_id_a, policy_id_b
