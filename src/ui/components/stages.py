"""Componentes dos estágios do pipeline: processamento e extração (D2-P1-4c)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from modules.document_processing.public_api import DocumentProcessingFacade
from modules.policy_analysis.public_api import PolicyAnalysisFacade
from ui.errors import sanitize_error_message
from ui.logic import build_display_labels, stage_label
from ui.uploads import cleanup_uploads, save_upload

#: Aviso de conclusão da extração — o usuário segue direto para a consulta.
EXTRACTION_DONE_NOTICE = (
    "Extração concluída — você já pode fazer suas perguntas na seção de consulta livre."
)


def current_labels(policy_ids: tuple[str, str]) -> dict[str, str]:
    """Rótulos de exibição atuais: nome real da seguradora por `policy_id`.

    Combina a detecção por LLM (`insurer_info`) com o nome digitado pelo
    usuário quando a LLM não identifica (`insurer_manual`).
    """
    detected = st.session_state.get("insurer_info") or {}
    manual = st.session_state.get("insurer_manual") or {}
    merged: dict[str, dict | None] = {}
    for policy_id in policy_ids:
        if not policy_id:
            continue
        info = dict(detected.get(policy_id) or {})
        if not info.get("name") and manual.get(policy_id):
            info = {"name": manual[policy_id], "year": info.get("year")}
        merged[policy_id] = info or None
    return build_display_labels(policy_ids, merged)


def render_processing(
    document_api: DocumentProcessingFacade,
    policy_api: PolicyAnalysisFacade,
    uploads_and_policies: tuple,
) -> None:
    """Processa os PDFs e identifica a seguradora de cada um (nome + ano, T-2b).

    O nome da empresa provedora sai das páginas 1–2 via LLM; sem identificação,
    a UI pede o nome ao usuário (fallback). Upload temporário não persiste.
    """
    upload_a, upload_b, policy_id_a, policy_id_b = uploads_and_policies
    if st.button("Processar apólices", type="primary"):
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
                st.session_state.setdefault("process_status", {})[policy_id] = status
                # Markdown estruturado por página (OCR pesado único, cache por
                # fingerprint) — base do RAG por seções e do Relatório D&O.
                try:
                    markdown_pages = document_api.extract_markdown(str(file_path))
                    policy_api.store_markdown(
                        policy_id,
                        list(enumerate(markdown_pages, start=1)),
                        file_path=str(file_path),
                    )
                except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
                    st.error(sanitize_error_message(f"MARKDOWN/{policy_id}", error))
                # Seguradora: páginas 1–2 do PDF + LLM (nome + ano de referência).
                preview = document_api.extract_preview(str(file_path), max_pages=2)
                st.session_state.setdefault("insurer_info", {})[policy_id] = (
                    policy_api.identify_insurer(policy_id, preview)
                )
            if all((upload_a is not None, upload_b is not None)):
                st.session_state["process_done"] = (policy_id_a, policy_id_b)
        finally:
            # T-2b: upload temporário não persiste depois do fluxo.
            cleanup_uploads(saved_uploads)

    done = st.session_state.get("process_done")
    if not done or done != (policy_id_a, policy_id_b):
        return

    labels = current_labels((policy_id_a, policy_id_b))
    for policy_id in (policy_id_a, policy_id_b):
        stored = (st.session_state.get("process_status") or {}).get(policy_id)
        if stored is None:
            continue
        st.write(
            f"`{labels.get(policy_id, policy_id)}` → **{stage_label(stored.stage)}** "
            f"(progresso {stored.progress:.0%})"
        )
        if stored.message:
            st.caption(stored.message)

    # Fallback da identificação: nome que a LLM não achou é pedido ao usuário.
    manual = st.session_state.setdefault("insurer_manual", {})
    detected = st.session_state.get("insurer_info") or {}
    for policy_id in (policy_id_a, policy_id_b):
        if (detected.get(policy_id) or {}).get("name") or manual.get(policy_id):
            continue
        typed = st.text_input(
            f"Não identifiquei a seguradora da apólice `{policy_id}` — informe o nome:",
            key=f"insurer_manual_{policy_id}",
        )
        if typed.strip():
            manual[policy_id] = typed.strip()


def render_extraction(
    policy_api: PolicyAnalysisFacade,
    policy_ids: tuple[str, str],
    fields: list[dict[str, str]],
    labels: dict[str, str],
) -> None:
    """Extração automática dos campos quando o processamento termina.

    Roda UMA única vez por conjunto de apólices (idempotente via
    `st.session_state` — não repete a cada rerun do Streamlit; a extração usa
    LLM e pode demorar). A tabela de campos extraídos não é mais exibida: os
    fatos ficam nos bastidores (a comparação e a revisão consomem os fatos
    persistidos) e o usuário só vê o aviso de conclusão antes de ir para a
    consulta livre.
    """
    if not all(policy_ids) or st.session_state.get("process_done") != tuple(policy_ids):
        return

    cached = st.session_state.get("extracted_facts")
    if not cached or cached[0] != tuple(policy_ids):
        codes = [field["code"] for field in fields]
        facts_by_policy: dict[str, list] = {}
        errors: list[str] = []
        with st.spinner("Extraindo os campos das apólices…"):
            for policy_id in policy_ids:
                try:
                    facts_by_policy[policy_id] = policy_api.extract_fields(policy_id, codes)
                except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
                    errors.append(
                        sanitize_error_message(f"EXTRACAO/{labels.get(policy_id, policy_id)}", error)
                    )
                    facts_by_policy[policy_id] = []
        # Idempotência: o resultado fica na sessão e o rerun não refaz a extração.
        cached = (tuple(policy_ids), facts_by_policy, errors)
        st.session_state["extracted_facts"] = cached

    errors = cached[2]
    if errors:
        for message in errors:
            st.error(message)
    else:
        st.success(EXTRACTION_DONE_NOTICE)
