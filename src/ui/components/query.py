"""Componente de consulta livre às evidências das apólices (etapa 5 do escopo).

Busca semântica em linguagem natural sobre os chunks indexados, via fachada
pública do `document_processing` (F-15: nenhum SQL, consulta vetorial ou
prompt na UI). O resultado persiste na sessão (botão do Streamlit é efêmero).
"""

from __future__ import annotations

import streamlit as st

from modules.document_processing.public_api import DocumentProcessingFacade
from shared_kernel.contracts import RetrievalQuery
from ui.errors import sanitize_error_message
from ui.logic import format_evidence_rows

#: Chave da sessão com a última consulta e seu resultado.
_SESSION_KEY = "consulta_evidencias"


def render_query(
    document_api: DocumentProcessingFacade,
    policy_ids: tuple[str, str],
) -> None:
    """Consulta livre às evidências das duas apólices (filtros: apólice, top_k)."""
    st.header("3. Consulta livre às apólices")
    st.caption(
        "Busca semântica em linguagem natural sobre as evidências indexadas — "
        "digite termos como cláusulas, coberturas, exclusões ou limites."
    )

    policy_id_a, policy_id_b = policy_ids
    query_text = st.text_input("Termos da consulta", key="consulta_texto")
    col_policy, col_top_k = st.columns(2)
    with col_policy:
        scope = st.selectbox(
            "Consultar em",
            ["Ambas as apólices", policy_id_a, policy_id_b],
            key="consulta_escopo",
        )
    with col_top_k:
        top_k = int(
            st.number_input(
                "Máximo de evidências", min_value=1, max_value=20, value=5, key="consulta_top_k"
            )
        )

    if st.button("Consultar evidências"):
        if not query_text.strip():
            st.warning("Digite os termos da consulta.")
        else:
            try:
                query = RetrievalQuery(
                    query=query_text.strip(),
                    policy_id=None if scope == "Ambas as apólices" else scope,
                    top_k=top_k,
                )
                result = document_api.retrieve_evidence(query)
            except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
                st.error(sanitize_error_message("CONSULTA", error))
            else:
                # Botão do Streamlit é efêmero: o resultado fica na sessão.
                st.session_state[_SESSION_KEY] = (query_text.strip(), scope, result)

    cached = st.session_state.get(_SESSION_KEY)
    if not cached:
        return
    query_text, scope, result = cached

    if not result.evidences:
        st.info(
            f"Nenhuma evidência encontrada para “{query_text}” em {scope}. "
            "Tente outros termos ou processe as apólices antes."
        )
        return

    st.success(
        f"{len(result.evidences)} evidência(s) para “{query_text}” em {scope} "
        f"(run {result.retrieval_run_id})"
    )
    rows = format_evidence_rows(result.evidences)
    st.dataframe(rows, hide_index=True)

    for row, evidence in zip(rows, result.evidences):
        with st.expander(
            f"{row['apólice']} · pág. {row['página']} · score {row['score']}"
        ):
            st.caption(
                f"seção: {row['seção']} · origem: {row['origem']} · "
                f"evidência: {evidence.evidence_id}"
            )
            st.write(evidence.quoted_text)