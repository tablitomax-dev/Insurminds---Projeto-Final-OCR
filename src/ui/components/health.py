"""Banner de saúde do provedor de IA na abertura do app (checagem única).

A UI consome apenas a fachada pública (F-15): `PolicyAnalysisFacade.llm_health()`
devolve um item por nível da cadeia de modelos — `{"provider", "model", "ok",
"detail"}` — com a causa raiz da falha em `detail` (ex.: `HTTP 403 — Key limit
exceeded (total limit)`). O relatório fica em `st.session_state`: os reruns do
Streamlit reexibem o banner sem repetir a checagem (não a cada rerun).
"""

from __future__ import annotations

import streamlit as st

from modules.policy_analysis.public_api import PolicyAnalysisFacade

#: Chave do `st.session_state` com o relatório de saúde (checagem única por sessão).
HEALTH_SESSION_KEY = "llm_health"


def _check_health(policy_api: PolicyAnalysisFacade) -> list[dict] | None:
    """Relatório de saúde da cadeia de modelos; `None` quando não há o que mostrar.

    Fachada sem `llm_health` ou checagem que levanta exceção viram `None` —
    o banner é informativo e nunca pode derrubar a UI.
    """
    llm_health = getattr(policy_api, "llm_health", None)
    if not callable(llm_health):
        return None
    try:
        report = llm_health()
    except Exception:  # noqa: BLE001 — falha na checagem vira "sem banner"
        return None
    return report if isinstance(report, list) and report else None


def _model(level: dict) -> str:
    """Modelo do nível da cadeia (leitura humana quando o nome falta)."""
    return str(level.get("model") or level.get("provider") or "modelo não informado")


def render_llm_health_banner(policy_api: PolicyAnalysisFacade) -> None:
    """Banner verde/amarelo/vermelho do provedor de IA — uma checagem por sessão.

    Verde quando todos os níveis respondem (mostra o primeiro modelo ok);
    amarelo quando há níveis em falha com failover ativo; vermelho quando todos
    falham, com a causa raiz real (`HTTP 403 — …`) no texto. Cadeia vazia ou
    checagem indisponível → sem banner.
    """
    if HEALTH_SESSION_KEY not in st.session_state:
        st.session_state[HEALTH_SESSION_KEY] = _check_health(policy_api)
    report = st.session_state[HEALTH_SESSION_KEY]
    if not report:
        return
    healthy = [level for level in report if level.get("ok")]
    degraded = [level for level in report if not level.get("ok")]
    if not degraded:
        st.success(f"Provedor de IA: OK ({_model(healthy[0])})")
        return
    detail = str(degraded[0].get("detail") or "sem detalhe")
    if not healthy:
        st.error(
            f"Provedor de IA indisponível — {detail}. "
            "Recarregue os créditos da chave em openrouter.ai e recarregue a página."
        )
        return
    models = ", ".join(_model(level) for level in degraded)
    st.warning(
        f"Provedor de IA com níveis indisponíveis: {models} (motivo: {detail}) — o failover está ativo."
    )
