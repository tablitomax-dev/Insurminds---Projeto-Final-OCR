"""Revisão por indicação de divergências ao Agente (RF-04 + agentes LLM).

A fila agrupada por severidade fica visível como referência (as divergências
registradas); o revisor indica o que está errado numa mensagem e a LLM aplica
as correções via fluxo de revisão (`decided_by` do Agente + nota de auditoria
com a mensagem original) — a comparação é recalculada em seguida.
"""

from __future__ import annotations

import streamlit as st

from modules.policy_analysis.public_api import (
    Issue,
    PolicyAnalysisFacade,
    ReviewItem,
)
from ui.errors import sanitize_error_message
from ui.logic import group_by_severity, status_label

#: Chave da sessão com o histórico de indicações/correções do Agente.
_SESSION_KEY = "divergencia_conversa"


def _render_evidence(
    policy_api: PolicyAnalysisFacade, policy_id: str, field_code: str
) -> None:
    """Mostra o trecho citado das evidências do fato (RF-04)."""
    for evidence in policy_api.get_evidences(policy_id, field_code):
        st.caption(
            f"evidência {evidence.evidence_id} (pág. {evidence.page_number}): "
            f"{evidence.quoted_text}"
        )


def _render_history(policy_api: PolicyAnalysisFacade) -> None:
    """Histórico de revisões já decididas (RF-04)."""
    decisions = policy_api.list_review_decisions()
    if not decisions:
        return
    with st.expander(f"Histórico de decisões ({len(decisions)})"):
        for item in decisions:
            st.caption(
                f"{item.fact.policy_id} · {item.fact.field_code} · {item.revisao_status} "
                f"· revisor: {item.revisao_por or 'n/a'} · {item.revisao_em or 'n/a'} "
                f"· valor: {item.fact.value}"
            )


def render_review(
    policy_api: PolicyAnalysisFacade,
    policy_ids: tuple[str, str],
    labels: dict[str, str],
) -> None:
    """Fila de referência + indicação de divergências por mensagem ao Agente."""
    st.header("4. Alguma divergência? Me indique por aqui:")

    queue: list[ReviewItem] = policy_api.list_review_queue()
    if not queue:
        st.write("Nenhuma sinalização pendente.")
    else:
        issues: list[Issue] = []
        for policy_id in sorted({item.fact.policy_id for item in queue}):
            issues.extend(policy_api.list_issues(policy_id))
        items_by_fact_id = {item.fact.fact_id: item for item in queue}
        for severity, facts in group_by_severity([item.fact for item in queue], issues):
            st.subheader(f"Severidade {severity.value}")
            for fact in facts:
                item = items_by_fact_id[fact.fact_id]
                st.warning(
                    f"{labels.get(fact.policy_id, fact.policy_id)} · {fact.field_code} · "
                    f"{status_label(fact.status)} "
                    f"(evidências: {', '.join(fact.evidence_ids) or 'n/a'})"
                )
                st.caption(f"valor atual: {fact.value} · revisão: {item.revisao_status}")
                _render_evidence(policy_api, fact.policy_id, fact.field_code)

    col_message, col_send = st.columns([6, 1], vertical_alignment="bottom")
    with col_message:
        message = st.text_input("Mensagem para o Agente", key="divergencia_msg")
    with col_send:
        send = st.button(
            "Enviar",
            icon=":material/arrow_upward:",
            type="primary",
            key="divergencia_enviar",
        )

    history = st.session_state.setdefault(_SESSION_KEY, [])
    if send:
        if not message.strip():
            st.warning("Descreva a divergência antes de enviar.")
        else:
            with st.spinner("Agente analisando as divergências…"):
                entry = _apply_feedback(
                    policy_api, policy_ids, labels, message.strip()
                )
            history.append(entry)

    for entry in history:
        with st.chat_message("user"):
            st.write(entry["message"])
        with st.chat_message("assistant"):
            for line in entry.get("applied") or []:
                st.success(line)
            for line in entry.get("skipped") or []:
                st.warning(line)
            if entry.get("notice"):
                st.info(entry["notice"])

    _render_history(policy_api)


def _apply_feedback(
    policy_api: PolicyAnalysisFacade,
    policy_ids: tuple[str, str],
    labels: dict[str, str],
    message: str,
) -> dict:
    """Aplica a indicação via LLM e recalcula a comparação entre as apólices."""
    entry: dict = {"message": message, "applied": [], "skipped": [], "notice": None}
    try:
        result = policy_api.apply_review_feedback(message, list(policy_ids))
    except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
        entry["notice"] = sanitize_error_message("REVISAO", error)
        return entry
    for item in result.get("applied") or []:
        entry["applied"].append(
            f"Correção aplicada: {item['field_code']} · {item['decision']}"
        )
    for item in result.get("skipped") or []:
        entry["skipped"].append(f"Não aplicado ({item['reason']})")
    if not entry["applied"] and not entry["skipped"]:
        entry["notice"] = "Nenhuma correção indicada — especifique os campos divergentes."
    try:
        comparison = policy_api.compare_policies(policy_ids[0], policy_ids[1])
    except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
        entry["notice"] = sanitize_error_message("COMPARACAO", error)
    else:
        # Atualiza a comparação exibida: o valor revisado alimenta o comparativo.
        st.session_state["comparison_id"] = comparison.comparison_id
        entry["notice"] = (
            entry["notice"] or f"Comparação atualizada ({labels.get(policy_ids[0], policy_ids[0])} "
            f"× {labels.get(policy_ids[1], policy_ids[1])})."
        )
    return entry
