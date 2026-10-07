"""Tela Streamlit do analista de apólices D&O (RF-09 do requirements).

Jornada: carregar 2 apólices → acompanhar estágios (a seguradora é identificada
pela LLM e dá nome às apólices) → extração automática dos campos → conversar com
o Agente Inteligente → comparar com evidências → indicar divergências ao Agente
(correções revisadas alimentam a comparação) → exportar, com painel de métricas.

Uso: `python -B -m streamlit run src/ui/app.py`
A UI consome exclusivamente as fachadas públicas (RF-10, F-15), montadas no
composition root único (D2-P1-4): nenhum import de `domain`/`infrastructure`,
nenhum SQL na UI.
"""

from __future__ import annotations

import streamlit as st

from composition_root import build_facades
from ui.components import (
    current_labels,
    render_comparison,
    render_export,
    render_extraction,
    render_llm_health_banner,
    render_metrics_panel,
    render_processing,
    render_query,
    render_review,
    render_upload_section,
)
from ui.errors import sanitize_error_message

st.set_page_config(page_title="Comparação de Apólices D&O", layout="wide")
st.title("Comparação de Apólices D&O")


def _facades():
    """Monta (ou reusa) as fachadas reais na sessão, com erro amigável."""
    if "facades" not in st.session_state:
        try:
            st.session_state["facades"] = build_facades()
        except (RuntimeError, ImportError) as error:
            st.error(sanitize_error_message("WIRING", error))
            st.info(
                "Para a demonstração sem dependências, rode a suíte de testes: "
                "`python -B -m pytest -q -p no:cacheprovider` (jornada E2E com fakes)."
            )
            return None, None
    return st.session_state["facades"]


document_api, policy_api = _facades()
if document_api is None:
    st.stop()

# Saúde do provedor de IA no boot: banner verde/amarelo/vermelho com a causa
# raiz real — checagem única por sessão (não repete a cada rerun).
render_llm_health_banner(policy_api)

fields = policy_api.list_fields()
field_labels = {field["code"]: field["label"] for field in fields}

uploads_and_policies = render_upload_section()
_, _, policy_id_a, policy_id_b = uploads_and_policies
render_processing(document_api, policy_api, uploads_and_policies)
labels = current_labels((policy_id_a, policy_id_b))
render_extraction(policy_api, (policy_id_a, policy_id_b), fields, labels)
render_query(document_api, policy_api, (policy_id_a, policy_id_b), labels)
comparison_id = render_comparison(
    policy_api, policy_id_a, policy_id_b, fields, field_labels, labels
)
if comparison_id:
    render_export(policy_api, comparison_id)
# Seção "5. Relatório D&O" oculta nesta entrega: nada é montado na página —
# o componente de relatório continua em `ui/components/report.py`, sem uso.
render_metrics_panel(policy_api)
render_review(policy_api, (policy_id_a, policy_id_b), labels)
