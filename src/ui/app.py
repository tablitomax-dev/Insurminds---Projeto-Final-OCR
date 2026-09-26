"""Tela Streamlit mínima do vertical slice (RF-09 do requirements).

Jornada do analista: carregar 2 apólices → acompanhar processamento →
extrair campo → comparar com evidências → revisão humana → exportar.

Uso: `python -B -m streamlit run src/ui/app.py`
A UI consome exclusivamente as fachadas públicas dos módulos (RF-10, F-15):
nenhum import de `domain`/`infrastructure` alheio, nenhum SQL na UI.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from modules.document_processing.public_api import create_default_document_processing
from modules.policy_analysis.public_api import (
    create_default_policy_analysis,
    create_document_processing_retriever,
)
from ui.errors import sanitize_error_message
from ui.uploads import cleanup_uploads, save_upload

#: Caminho FIXO e documentado dos exports (T-2b): sempre `exports/` na raiz.
EXPORT_DIR = Path("exports")

#: Aviso de retenção exibido junto do botão de exportar (T-2b).
EXPORT_RETENTION_NOTICE = (
    "Aviso de retenção: o resumo é gravado em `exports/` (caminho fixo da raiz do projeto) "
    "e permanece no disco até a exclusão manual — apólices são dados confidenciais; "
    "apague o arquivo após o uso."
)

st.set_page_config(page_title="Comparação de Apólices D&O", layout="wide")
st.title("Comparação de Apólices D&O — vertical slice")


def _facade_pair():
    """Monta (ou reusa) as fachadas reais na sessão, com erro amigável."""
    if "facades" not in st.session_state:
        try:
            document = create_default_document_processing()
            policy = create_default_policy_analysis(
                retriever=create_document_processing_retriever(document)
            )
        except (RuntimeError, ImportError) as error:
            st.error(sanitize_error_message("WIRING", error))
            st.info(
                "Para a demonstração sem dependências, rode a suíte de testes: "
                "`python -B -m pytest -q -p no:cacheprovider` (jornada E2E com fakes)."
            )
            return None, None
        st.session_state["facades"] = (document, policy)
    return st.session_state["facades"]


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


document_api, policy_api = _facade_pair()
if document_api is None:
    st.stop()

fields = policy_api.list_fields()
field_labels = {field["code"]: field["label"] for field in fields}

st.header("1. Carregar as apólices")
col_a, col_b = st.columns(2)
with col_a:
    upload_a = st.file_uploader("Apólice A (PDF)", type=["pdf"], key="upload_a")
    policy_id_a = st.text_input("policy_id A", value="pol_acme", key="pol_a")
with col_b:
    upload_b = st.file_uploader("Apólice B (PDF)", type=["pdf"], key="upload_b")
    policy_id_b = st.text_input("policy_id B", value="pol_bravo", key="pol_b")

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
            st.write(f"`{policy_id}` → **{status.stage}** (progresso {status.progress:.0%})")
            if status.message:
                st.caption(status.message)
    finally:
        # T-2b: upload temporário não persiste depois do fluxo.
        cleanup_uploads(saved_uploads)

st.header("2. Extrair campo")
field_code = st.selectbox(
    "Campo do catálogo",
    [field["code"] for field in fields],
    format_func=lambda code: field_labels.get(code, code),
)
if st.button("Extrair das duas apólices"):
    for policy_id in (policy_id_a, policy_id_b):
        try:
            fact = policy_api.extract_field(policy_id, field_code)
        except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
            st.error(sanitize_error_message(f"EXTRACAO/{policy_id}/{field_code}", error))
            continue
        st.subheader(f"{policy_id} · {field_code} · {fact.status}")
        st.json(fact.model_dump())
        for evidence_id in fact.evidence_ids:
            st.caption(f"evidência: {evidence_id}")

st.header("3. Comparação determinística")
if st.button("Comparar A × B"):
    try:
        comparison = policy_api.compare_policies(policy_id_a, policy_id_b)
    except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
        st.error(sanitize_error_message("COMPARACAO", error))
    else:
        st.session_state["comparison_id"] = comparison.comparison_id
        st.caption(f"ComparisonId: {comparison.comparison_id}")
        st.table(
            [
                {
                    "campo": row.field_code,
                    "direção": row.direction,
                    "valor A": row.value_a,
                    "valor B": row.value_b,
                    "evidências A": ", ".join(row.evidence_ids_a),
                    "evidências B": ", ".join(row.evidence_ids_b),
                }
                for row in comparison.rows
            ]
        )

comparison_id = st.session_state.get("comparison_id")
if comparison_id:
    explain_field = st.selectbox(
        "Explicar diferença do campo",
        [field["code"] for field in fields],
        key="explain_field",
    )
    if st.button("Gerar explicação"):
        try:
            text, cited = policy_api.explain_difference(comparison_id, explain_field)
        except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
            st.error(sanitize_error_message(f"EXPLICACAO/{explain_field}", error))
        else:
            st.write(text)
            st.caption(f"evidências citadas: {', '.join(cited)}")

    st.caption(EXPORT_RETENTION_NOTICE)
    if st.button("Exportar resumo"):
        try:
            path = policy_api.export_comparison(comparison_id, export_dir=EXPORT_DIR)
        except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
            st.error(sanitize_error_message("EXPORTACAO", error))
        else:
            st.success(f"Export gerado: {path}")
            st.download_button(
                "Baixar resumo",
                data=Path(path).read_text(encoding="utf-8"),
                file_name=Path(path).name,
            )

st.header("4. Revisão humana (Confirmar / Corrigir valor / Registrar divergência)")
st.caption(
    "Toda decisão grava revisor, timestamp, valor original e valor corrigido, ligada ao "
    "EvidenceRef do fato — o valor revisado alimenta a comparação."
)
reviewer = st.text_input("Revisor (quem decide)", value="", key="reviewer")
queue = policy_api.get_review_queue()
if not queue:
    st.write("Nenhuma sinalização pendente.")
for fact in queue:
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
