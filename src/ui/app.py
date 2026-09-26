"""Tela Streamlit mínima do vertical slice (RF-09 do requirements).

Jornada do analista: carregar 2 apólices → acompanhar processamento →
extrair campo → comparar com evidências → fila de revisão → exportar.

Uso: `python -B -m streamlit run src/ui/app.py`
A UI consome exclusivamente as fachadas públicas dos módulos (RF-10).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from modules.document_processing.public_api import (
    create_default_document_processing,
    create_document_processing,
)
from modules.policy_analysis.infrastructure.document_retriever import (
    DocumentProcessingRetriever,
)
from modules.policy_analysis.public_api import (
    create_default_policy_analysis,
    create_policy_analysis,
)
from modules.policy_analysis.domain.catalog import FIELD_CATALOG

EXPORT_DIR = Path("exports")

st.set_page_config(page_title="Comparação de Apólices D&O", layout="wide")
st.title("Comparação de Apólices D&O — vertical slice")


def _facade_pair():
    """Monta (ou reusa) as fachadas reais na sessão, com erro amigável."""
    if "facades" not in st.session_state:
        try:
            document = create_default_document_processing()
            policy = create_default_policy_analysis(
                retriever=DocumentProcessingRetriever(document)
            )
        except (RuntimeError, ImportError) as error:
            st.error(f"Dependências indisponíveis para a jornada real: {error}")
            st.info(
                "Para a demonstração sem dependências, rode a suíte de testes: "
                "`python -B -m pytest -q -p no:cacheprovider` (jornada E2E com fakes)."
            )
            return None, None
        st.session_state["facades"] = (document, policy)
    return st.session_state["facades"]


def _save_upload(upload) -> str:
    tmp = Path(tempfile.gettempdir()) / f"apolice_{upload.name}"
    tmp.write_bytes(upload.getbuffer())
    return str(tmp)


document_api, policy_api = _facade_pair()
if document_api is None:
    st.stop()

st.header("1. Carregar as apólices")
col_a, col_b = st.columns(2)
with col_a:
    upload_a = st.file_uploader("Apólice A (PDF)", type=["pdf"], key="upload_a")
    policy_id_a = st.text_input("policy_id A", value="pol_acme", key="pol_a")
with col_b:
    upload_b = st.file_uploader("Apólice B (PDF)", type=["pdf"], key="upload_b")
    policy_id_b = st.text_input("policy_id B", value="pol_bravo", key="pol_b")

if st.button("Processar apólices", type="primary"):
    for upload, policy_id in ((upload_a, policy_id_a), (upload_b, policy_id_b)):
        if upload is None:
            st.warning("Envie os dois PDFs para processar.")
            st.stop()
        file_path = _save_upload(upload)
        status = document_api.process_document(
            document_id=f"doc_{policy_id}", policy_id=policy_id, file_path=file_path
        )
        st.write(f"`{policy_id}` → **{status.stage}** (progresso {status.progress:.0%})")
        if status.message:
            st.caption(status.message)

st.header("2. Extrair campo")
field_code = st.selectbox(
    "Campo do catálogo", list(FIELD_CATALOG), format_func=lambda code: FIELD_CATALOG[code].label
)
if st.button("Extrair das duas apólices"):
    for policy_id in (policy_id_a, policy_id_b):
        fact = policy_api.extract_field(policy_id, field_code)
        st.subheader(f"{policy_id} · {field_code} · {fact.status}")
        st.json(fact.model_dump())
        for evidence_id in fact.evidence_ids:
            st.caption(f"evidência: {evidence_id}")

st.header("3. Comparação determinística")
if st.button("Comparar A × B"):
    comparison = policy_api.compare_policies(policy_id_a, policy_id_b)
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
        [row for row in FIELD_CATALOG],
        key="explain_field",
    )
    if st.button("Gerar explicação"):
        try:
            text, cited = policy_api.explain_difference(comparison_id, explain_field)
            st.write(text)
            st.caption(f"evidências citadas: {', '.join(cited)}")
        except Exception as error:  # noqa: BLE001 — mensagem amigável na UI
            st.error(f"Explicação rejeitada: {error}")

    if st.button("Exportar resumo"):
        path = policy_api.export_comparison(comparison_id, export_dir=EXPORT_DIR)
        st.success(f"Export gerado: {path}")
        st.download_button("Baixar resumo", data=Path(path).read_text(encoding="utf-8"), file_name=Path(path).name)

st.header("4. Fila de revisão humana")
queue = policy_api.get_review_queue()
if not queue:
    st.write("Nenhuma sinalização pendente.")
for fact in queue:
    st.warning(
        f"{fact.policy_id} · {fact.field_code} · {fact.status} "
        f"(evidências: {', '.join(fact.evidence_ids) or 'n/a'})"
    )
