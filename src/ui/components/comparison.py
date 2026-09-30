"""Componente de comparação determinística e explicação (D2-P1-4c)."""

from __future__ import annotations

import streamlit as st

from modules.policy_analysis.public_api import PolicyAnalysisFacade
from ui.errors import sanitize_error_message


def render_comparison(
    policy_api: PolicyAnalysisFacade,
    policy_id_a: str,
    policy_id_b: str,
    fields: list[dict[str, str]],
    field_labels: dict[str, str],
) -> str | None:
    """Compara A × B e explica diferenças; devolve o `comparison_id` da sessão."""
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
                        "campo": campo.field_code,
                        "resultado": campo.resultado,
                        "direção": campo.direcao,
                        "valor A": campo.valor_a,
                        "valor B": campo.valor_b,
                        "evidências A": ", ".join(campo.evidencias_a),
                        "evidências B": ", ".join(campo.evidencias_b),
                    }
                    for campo in comparison.campos
                ]
            )

    comparison_id = st.session_state.get("comparison_id")
    if not comparison_id:
        return None
    explain_field = st.selectbox(
        "Explicar diferença do campo",
        [field["code"] for field in fields],
        key="explain_field",
    )
    if st.button("Gerar explicação"):
        try:
            explanation = policy_api.explain_difference(comparison_id, explain_field)
        except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
            st.error(sanitize_error_message(f"EXPLICACAO/{explain_field}", error))
        else:
            st.write(explanation.text)
            st.caption(f"evidências citadas: {', '.join(explanation.evidence_ids)}")
    return comparison_id
