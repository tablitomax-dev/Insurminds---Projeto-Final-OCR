"""Componente de comparação determinística e explicação (D2-P1-4c)."""

from __future__ import annotations

import streamlit as st

from modules.policy_analysis.public_api import PolicyAnalysisFacade
from ui.errors import sanitize_error_message
from ui.logic import format_value


def render_comparison(
    policy_api: PolicyAnalysisFacade,
    policy_id_a: str,
    policy_id_b: str,
    fields: list[dict[str, str]],
    field_labels: dict[str, str],
    labels: dict[str, str] | None = None,
) -> str | None:
    """Compara A × B e explica diferenças; devolve o `comparison_id` da sessão."""
    st.header("3. Comparação")
    label_a = (labels or {}).get(policy_id_a, policy_id_a)
    label_b = (labels or {}).get(policy_id_b, policy_id_b)
    if st.button("Comparar A × B"):
        try:
            comparison = policy_api.compare_policies(policy_id_a, policy_id_b)
        except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
            st.error(sanitize_error_message("COMPARACAO", error))
        else:
            st.session_state["comparison_id"] = comparison.comparison_id
            st.caption(f"ID da comparação: {comparison.comparison_id}")
            units = {field["code"]: field.get("unit") for field in fields}
            st.table(
                [
                    {
                        "campo": campo.field_code,
                        "resultado": campo.resultado,
                        "direção": campo.direcao,
                        f"valor {label_a}": format_value(
                            campo.valor_a, units.get(campo.field_code)
                        ),
                        f"valor {label_b}": format_value(
                            campo.valor_b, units.get(campo.field_code)
                        ),
                        f"evidências {label_a}": ", ".join(campo.evidencias_a),
                        f"evidências {label_b}": ", ".join(campo.evidencias_b),
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
