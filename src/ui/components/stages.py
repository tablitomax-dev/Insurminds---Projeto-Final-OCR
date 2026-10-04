"""Componentes dos estágios do pipeline: processamento e extração (D2-P1-4c)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from modules.document_processing.public_api import DocumentProcessingFacade
from modules.policy_analysis.public_api import PolicyAnalysisFacade
from ui.errors import sanitize_error_message
from ui.uploads import cleanup_uploads, save_upload


def render_processing(
    document_api: DocumentProcessingFacade,
    uploads_and_policies: tuple,
) -> None:
    """Processa os PDFs enviados, mostrando o estágio de cada um (T-2b: upload limpo)."""
    upload_a, upload_b, policy_id_a, policy_id_b = uploads_and_policies
    if not st.button("Processar apólices", type="primary"):
        return
    saved_uploads: list[Path] = []
    try:
        for upload, policy_id in ((upload_a, policy_id_a), (upload_b, policy_id_b)):
            if upload is None:
                st.warning("Envie os dois PDFs para processar.")
                st.stop()
            file_path = save_upload(upload.name, upload.getbuffer())
            saved_uploads.append(file_path)
            try:
                status = document_api.process_document(
                    document_id=f"doc_{policy_id}", policy_id=policy_id, file_path=str(file_path)
                )
            except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
                st.error(sanitize_error_message(f"PROCESSAMENTO/{policy_id}", error))
                continue
            st.write(f"`{policy_id}` → **{status.stage}** (progresso {status.progress:.0%})")
            if status.message:
                st.caption(status.message)
    finally:
        # T-2b: upload temporário não persiste depois do fluxo.
        cleanup_uploads(saved_uploads)


def render_extraction(
    policy_api: PolicyAnalysisFacade,
    policy_ids: tuple[str, str],
    fields: list[dict[str, str]],
    field_labels: dict[str, str],
) -> None:
    """Estágio de extração: TODOS os campos das duas apólices em um passo.

    A extração completa persiste os fatos — é o que deixa a comparação
    determinística pronta (ela consome os fatos das duas apólices).
    """
    st.header("2. Extrair campos")
    codes = [field["code"] for field in fields]
    if st.button("Extrair todos os campos das duas apólices"):
        facts_by_policy: dict[str, list] = {}
        for policy_id in policy_ids:
            try:
                facts_by_policy[policy_id] = policy_api.extract_fields(policy_id, codes)
            except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
                st.error(sanitize_error_message(f"EXTRACAO/{policy_id}", error))
                facts_by_policy[policy_id] = []
        # Botão do Streamlit é efêmero: o resultado fica na sessão para
        # continuar visível enquanto o usuário usa a comparação/revisão.
        st.session_state["extracted_facts"] = (tuple(policy_ids), facts_by_policy)

    cached = st.session_state.get("extracted_facts")
    if not cached or cached[0] != tuple(policy_ids):
        return
    facts_by_policy = cached[1]

    st.success("Campos extraídos — prontos para a comparação determinística.")
    st.dataframe(
        [
            {
                "campo": field_labels.get(code, code),
                **{
                    policy_id: next(
                        (
                            fact.status
                            for fact in facts_by_policy.get(policy_id, [])
                            if fact.field_code == code
                        ),
                        "—",
                    )
                    for policy_id in policy_ids
                },
            }
            for code in codes
        ],
        hide_index=True,
    )
    for policy_id in policy_ids:
        for fact in facts_by_policy.get(policy_id, []):
            label = field_labels.get(fact.field_code, fact.field_code)
            with st.expander(f"{policy_id} · {label} · {fact.status}"):
                st.json(fact.model_dump())
                for evidence_id in fact.evidence_ids:
                    st.caption(f"evidência: {evidence_id}")
