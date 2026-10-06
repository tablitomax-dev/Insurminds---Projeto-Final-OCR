"""Agente Inteligente sobre as apólices (RAG: busca automática + resposta).

A busca semântica roda automaticamente sob os panos (sem controles na UI) e a
LLM responde com base apenas nas evidências recuperadas, citando as fontes
(F-15: nenhum SQL, consulta vetorial ou prompt na UI). O histórico persiste
na sessão (botão do Streamlit é efêmero).
"""

from __future__ import annotations

import streamlit as st

from modules.document_processing.public_api import DocumentProcessingFacade
from modules.policy_analysis.public_api import PolicyAnalysisFacade
from shared_kernel.contracts import RetrievalQuery
from ui.errors import sanitize_error_message
from ui.logic import format_evidence_rows

#: Chave da sessão com o histórico de perguntas/respostas do Agente.
_SESSION_KEY = "agente_conversa"

#: Busca fixa sob os panos: sempre as duas apólices, `top_k` evidências.
_TOP_K = 5

#: Teto do fallback por apólice quando a busca semântica não retorna nada.
_MAX_FALLBACK_EVIDENCES = 10

QUERY_CAPTION = (
    "Converse com o Agente Inteligente sobre as apólices — digite termos como "
    "cláusulas, coberturas, exclusões, limites, etc."
)

NO_EVIDENCE_NOTICE = "Não encontrei base nas apólices para essa pergunta."


def _ask_agent(
    document_api: DocumentProcessingFacade,
    policy_api: PolicyAnalysisFacade,
    policy_ids: tuple[str, str],
    question: str,
) -> dict:
    """Busca automática de evidências + resposta da LLM com citações.

    Sem evidência na busca semântica, cai no conjunto de evidências das
    apólices (fixtures no demo); sem base nenhuma, responde determinístico —
    a LLM nunca é chamada sem evidências (nada de alucinação).
    """
    try:
        result = document_api.retrieve_evidence(
            RetrievalQuery(query=question, policy_id=None, top_k=_TOP_K)
        )
        evidences = list(result.evidences)
        if not evidences:
            seen: set[str] = set()
            for policy_id in policy_ids:
                for evidence in policy_api.get_evidences(policy_id):
                    if evidence.evidence_id in seen or len(seen) >= _MAX_FALLBACK_EVIDENCES:
                        continue
                    seen.add(evidence.evidence_id)
                    evidences.append(evidence)
    except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
        return {
            "question": question,
            "answer": None,
            "evidences": [],
            "notice": sanitize_error_message("CONSULTA", error),
        }
    if not evidences:
        return {"question": question, "answer": None, "evidences": [], "notice": NO_EVIDENCE_NOTICE}
    try:
        answer = policy_api.answer_question(question, evidences)
    except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
        return {
            "question": question,
            "answer": None,
            "evidences": evidences,
            "notice": sanitize_error_message("AGENTE", error),
        }
    cited_ids = set(answer.get("evidence_ids") or [])
    cited = [ev for ev in evidences if ev.evidence_id in cited_ids] or evidences
    return {"question": question, "answer": answer.get("text"), "evidences": cited}


def render_query(
    document_api: DocumentProcessingFacade,
    policy_api: PolicyAnalysisFacade,
    policy_ids: tuple[str, str],
    labels: dict[str, str],
) -> None:
    """Conversa com o Agente Inteligente sobre as duas apólices."""
    st.header("2. Consulta livre às apólices")
    st.caption(QUERY_CAPTION)

    col_question, col_send = st.columns([6, 1], vertical_alignment="bottom")
    with col_question:
        question = st.text_input("Digite sua dúvida", key="agente_pergunta")
    with col_send:
        send = st.button(
            "Enviar",
            icon=":material/arrow_upward:",
            type="primary",
            key="agente_enviar",
        )

    history = st.session_state.setdefault(_SESSION_KEY, [])
    if send:
        if not question.strip():
            st.warning("Digite sua dúvida antes de enviar.")
        else:
            with st.spinner("Agente consultando as apólices…"):
                history.append(_ask_agent(document_api, policy_api, policy_ids, question.strip()))

    for entry in history:
        with st.chat_message("user"):
            st.write(entry["question"])
        with st.chat_message("assistant"):
            if entry.get("answer"):
                st.write(entry["answer"])
            else:
                st.info(entry.get("notice") or NO_EVIDENCE_NOTICE)
            evidences = entry.get("evidences") or []
            if evidences:
                rows = format_evidence_rows(evidences, labels)
                with st.expander(f"Evidências citadas ({len(rows)})"):
                    st.dataframe(rows, hide_index=True)
