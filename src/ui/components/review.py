"""Componente de revisão humana — fila agrupada por severidade (D2-P1-1d, D2-P1-4c)."""

from __future__ import annotations

import streamlit as st

from modules.policy_analysis.public_api import (
    Issue,
    PolicyAnalysisFacade,
    ReviewItem,
)
from ui.errors import sanitize_error_message
from ui.logic import group_by_severity


def _review_action(action_name: str, call, *args, **kwargs) -> None:
    """Registra uma decisão de revisão via fachada, com erro sanitizado (T-2b)."""
    try:
        fact = call(*args, **kwargs)
    except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
        st.error(sanitize_error_message(f"REVISAO/{action_name}", error))
        return
    st.success(
        f"Revisão registrada: {action_name} · fato {fact.fact_id} · "
        f"status {fact.status} · evidências: {', '.join(fact.evidence_ids) or 'n/a'}"
    )


def _render_evidence(
    policy_api: PolicyAnalysisFacade, policy_id: str, field_code: str
) -> None:
    """Mostra o trecho citado das evidências do fato (RF-04)."""
    for evidence in policy_api.get_evidences(policy_id, field_code):
        st.caption(
            f"evidência {evidence.evidence_id} (pág. {evidence.page_number}): "
            f"{evidence.quoted_text}"
        )


def render_review(policy_api: PolicyAnalysisFacade) -> None:
    """Fila de revisão agrupada por severidade + ações Confirmar/Corrigir (RF-04)."""
    st.header("4. Revisão humana (Confirmar / Corrigir valor)")
    st.caption(
        "Toda decisão grava revisor, timestamp, valor original e valor corrigido, ligada ao "
        "EvidenceRef do fato — o valor revisado alimenta a comparação."
    )
    reviewer = st.text_input("Revisor (quem decide)", value="", key="reviewer")
    queue: list[ReviewItem] = policy_api.list_review_queue()
    if not queue:
        st.write("Nenhuma sinalização pendente.")
        return

    issues: list[Issue] = []
    for policy_id in sorted({item.fact.policy_id for item in queue}):
        issues.extend(policy_api.list_issues(policy_id))
    items_by_fact_id = {item.fact.fact_id: item for item in queue}
    for severity, facts in group_by_severity([item.fact for item in queue], issues):
        st.subheader(f"Severidade {severity.value}")
        for fact in facts:
            item = items_by_fact_id[fact.fact_id]
            st.warning(
                f"{fact.policy_id} · {fact.field_code} · {fact.status} "
                f"(evidências: {', '.join(fact.evidence_ids) or 'n/a'})"
            )
            st.caption(f"valor atual: {fact.value} · revisão: {item.revisao_status}")
            _render_evidence(policy_api, fact.policy_id, fact.field_code)
            corrected = st.text_input("Valor corrigido", key=f"fix_{fact.fact_id}")
            col_confirm, col_correct = st.columns(2)
            with col_confirm:
                if st.button("Confirmar", key=f"confirm_{fact.fact_id}"):
                    _review_action(
                        "CONFIRMADO",
                        policy_api.record_review_decision,
                        fact.fact_id,
                        "CONFIRMADO",
                        reviewer,
                    )
            with col_correct:
                if st.button("Corrigir valor", key=f"correct_{fact.fact_id}"):
                    _review_action(
                        "CORRIGIDO",
                        policy_api.record_review_decision,
                        fact.fact_id,
                        "CORRIGIDO",
                        reviewer,
                        {"text": corrected},
                    )
