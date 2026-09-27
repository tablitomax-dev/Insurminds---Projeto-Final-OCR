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
    """Estágio de extração de campo das duas apólices."""
    st.header("2. Extrair campo")
    field_code = st.selectbox(
        "Campo do catálogo",
        [field["code"] for field in fields],
        format_func=lambda code: field_labels.get(code, code),
    )
    if not st.button("Extrair das duas apólices"):
        return
    for policy_id in policy_ids:
        try:
            fact = policy_api.extract_field(policy_id, field_code)
        except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
            st.error(sanitize_error_message(f"EXTRACAO/{policy_id}/{field_code}", error))
            continue
        st.subheader(f"{policy_id} · {field_code} · {fact.status}")
        st.json(fact.model_dump())
        for evidence_id in fact.evidence_ids:
            st.caption(f"evidência: {evidence_id}")
