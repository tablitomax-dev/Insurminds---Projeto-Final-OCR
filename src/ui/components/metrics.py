"""Painel de métricas de uso do último run (D2-P1-2e, roadmap D-03/D-04)."""

from __future__ import annotations

import streamlit as st

from modules.policy_analysis.public_api import PolicyAnalysisFacade
from ui.logic import format_usage_summary


def render_metrics_panel(policy_api: PolicyAnalysisFacade) -> None:
    """Cartão com tokens/custo/latência do último run (RF-03, decisão do clarify)."""
    st.subheader("Métricas de uso do último run")
    summary = policy_api.get_usage_metrics()
    formatted = format_usage_summary(summary)
    if formatted is None:
        st.write("Nenhuma métrica registrada ainda — rode uma extração.")
        return
    st.table([formatted])
    st.caption(
        "Último run do processo atual; o histórico por run_id fica no log estruturado "
        "(decisão D-03). Custo é estimativa a partir da tabela de preços versionada."
    )
