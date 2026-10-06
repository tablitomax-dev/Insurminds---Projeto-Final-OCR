"""Componente do Relatório D&O (metodologia §1–§11) na UI do analista.

O painel de pesos (§8.2) vira controles interativos: o analista ajusta os
critérios do ranking antes de calcular; sem ajuste, os pesos padrão são usados
e o próprio relatório registra que o ranking pode ser recalculado. O relatório
só é montado sobre as seções do markdown já processadas.
"""

from __future__ import annotations

import streamlit as st

from modules.policy_analysis.public_api import PolicyAnalysisFacade
from ui.errors import sanitize_error_message

#: Pesos padrão do ranking (§8.1) — soma 100.
DEFAULT_WEIGHTS: dict[str, float] = {
    "protecao_individual": 25,
    "custos_defesa": 15,
    "alcance_temporal": 15,
    "limites_exposicao": 15,
    "exclusoes_criticas": 15,
    "cobertura_sociedade": 10,
    "extensoes": 5,
    "procedimentos": 5,
}

CRITERION_LABELS: dict[str, str] = {
    "protecao_individual": "Proteção individual do administrador",
    "custos_defesa": "Custos de defesa",
    "alcance_temporal": "Alcance temporal e notificação",
    "limites_exposicao": "Limites, sublimites e exposição financeira",
    "exclusoes_criticas": "Exclusões críticas",
    "cobertura_sociedade": "Cobertura da sociedade e reembolso",
    "extensoes": "Extensões e coberturas adicionais",
    "procedimentos": "Procedimentos e obrigações",
}


def render_report(
    policy_api: PolicyAnalysisFacade,
    policy_ids: tuple[str, str],
    labels: dict[str, str],
) -> None:
    """Seção "5. Relatório D&O": pesos do ranking, geração e exportação."""
    st.header("5. Relatório D&O")
    st.caption(
        "Comparação técnica completa (identificação, matriz por categoria, "
        "tabelas especiais, cenários, ranking parametrizável e checklist) — "
        "gerada sobre o markdown estruturado das apólices processadas."
    )

    with st.expander("Pesos do ranking (§8.2) — ajuste antes de calcular"):
        st.caption(
            "Pesos propostos (soma 100). Ajuste os pesos, inclua/remova critérios "
            "na observação, ou mantenha os padrões — o ranking é recalculado com "
            "os pesos usados e a sensibilidade (§8.3) vem no relatório."
        )
        weights: dict[str, float] = {}
        for code, default in DEFAULT_WEIGHTS.items():
            weights[code] = float(
                st.number_input(
                    f"{CRITERION_LABELS[code]} (padrão {default})",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(default),
                    step=1.0,
                    key=f"report_weight_{code}",
                )
            )
        total = sum(weights.values())
        if abs(total - 100.0) > 0.01:
            st.warning(f"A soma dos pesos é {total:.0f} — ajuste para 100 para calcular o ranking.")
        else:
            st.caption(f"Soma dos pesos: {total:.0f} ✓")

    if st.button("Gerar Relatório D&O", type="primary"):
        if abs(sum(weights.values()) - 100.0) > 0.01:
            st.error("Os pesos do ranking precisam somar 100.")
        else:
            try:
                report = policy_api.build_report(list(policy_ids), weights=weights)
            except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
                st.error(sanitize_error_message("RELATORIO", error))
            else:
                st.session_state["dno_report"] = report
                st.session_state["dno_report_ids"] = tuple(policy_ids)

    report = st.session_state.get("dno_report")
    if report is None or st.session_state.get("dno_report_ids") != tuple(policy_ids):
        return

    st.success(f"Relatório `{report.report_id}` gerado ({report.profile_mode}).")
    if report.ranking.informative_only:
        st.info(f"Ranking informativo, sem vencedora geral: {report.ranking.motivo_sem_vencedora}")

    st.subheader("Ranking (§8)")
    st.dataframe(
        [
            {
                "critério": CRITERION_LABELS.get(code, code),
                "peso": report.ranking.weights.get(code, 0),
                **{
                    labels.get(score.policy_id, score.policy_id): score.nota_por_criterio.get(code)
                    for score in report.ranking.scores
                },
            }
            for code in CRITERION_LABELS
        ],
        hide_index=True,
    )
    st.dataframe(
        [
            {
                "apólice": labels.get(score.policy_id, score.policy_id),
                "pontuação": score.total,
            }
            for score in report.ranking.scores
        ],
        hide_index=True,
    )

    st.subheader("Checklist de verificação final (§11)")
    st.dataframe(
        [
            {"verificação": item, "status": "✓" if ok else "✗"}
            for item, ok in report.checklist.items()
        ],
        hide_index=True,
    )

    if st.button("Exportar Relatório D&O (Markdown)"):
        try:
            path = policy_api.export_report(report)
        except Exception as error:  # noqa: BLE001 — mensagem sanitizada na UI
            st.error(sanitize_error_message("EXPORTACAO-RELATORIO", error))
        else:
            st.success(f"Relatório exportado em {path}")
