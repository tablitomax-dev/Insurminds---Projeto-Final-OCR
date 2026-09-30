"""Componente de revisão humana — fila agrupada por severidade (D2-P1-1d, D2-P1-4c)."""

from __future__ import annotations

import streamlit as st

from modules.policy_analysis.public_api import Issue, PolicyAnalysisFacade
from ui.errors import sanitize_error_message
from ui.logic import group_by_severity


def _review_action(action_name: str, call, *args, **kwargs) -> None:
    """Aplica uma ação de revisão via fachada, com erro sanitizado (T-2b)."""
    try:
        _, decision = call(*args, **kwargs)
    except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
        st.error(sanitize_error_message(f"REVISAO/{action_name}", error))
        return
    st.success(
        f"Revisão registrada: {decision.action} · revisor {decision.reviewer} · "
        f"{decision.reviewed_at} · review_id {decision.review_id}"
    )


def render_review(policy_api: PolicyAnalysisFacade) -> None:
    """Fila de revisão agrupada por severidade + ações Confirmar/Corrigir/Registrar."""
    st.header("4. Revisão humana (Confirmar / Corrigir valor / Registrar divergência)")
    st.caption(
        "Toda decisão grava revisor, timestamp, valor original e valor corrigido, ligada ao "
        "EvidenceRef do fato — o valor revisado alimenta a comparação."
    )
    reviewer = st.text_input("Revisor (quem decide)", value="", key="reviewer")
    queue = policy_api.get_review_queue()
    if not queue:
        st.write("Nenhuma sinalização pendente.")
        return

    issues: list[Issue] = []
    for policy_id in sorted({fact.policy_id for fact in queue}):
        issues.extend(policy_api.list_issues(policy_id))
    for severity, facts in group_by_severity(queue, issues):
        st.subheader(f"Severidade {severity.value}")
        for fact in facts:
            st.warning(
                f"{fact.policy_id} · {fact.field_code} · {fact.status} "
                f"(evidências: {', '.join(fact.evidence_ids) or 'n/a'})"
            )
            corrected = st.text_input("Valor corrigido", key=f"fix_{fact.fact_id}")
            note = st.text_input("Observação", key=f"note_{fact.fact_id}")
            col_confirm, col_correct, col_divergence = st.columns(3)
            with col_confirm:
                if st.button("Confirmar", key=f"confirm_{fact.fact_id}"):
                    _review_action(
                        "confirmar",
                        policy_api.confirm_fact,
                        fact.policy_id,
                        fact.field_code,
                        reviewer,
                        note or None,
                    )
            with col_correct:
                if st.button("Corrigir valor", key=f"correct_{fact.fact_id}"):
                    _review_action(
                        "corrigir",
                        policy_api.correct_fact,
                        fact.policy_id,
                        fact.field_code,
                        reviewer,
                        {"text": corrected},
                        fact.evidence_ids,
                        note or None,
                    )
            with col_divergence:
                if st.button("Registrar divergência", key=f"divergence_{fact.fact_id}"):
                    _review_action(
                        "divergencia",
                        policy_api.register_divergence,
                        fact.policy_id,
                        fact.field_code,
                        reviewer,
                        note or None,
                    )

    decisions = policy_api.list_review_decisions()
    if decisions:
        st.subheader("Decisões registradas")
        st.table(
            [
                {
                    "review_id": decision.review_id,
                    "campo": decision.field_code,
                    "ação": decision.action,
                    "revisor": decision.reviewer,
                    "quando": decision.reviewed_at,
                    "evidências": ", ".join(decision.evidence_ids) or "n/a",
                }
                for decision in decisions
            ]
        )
