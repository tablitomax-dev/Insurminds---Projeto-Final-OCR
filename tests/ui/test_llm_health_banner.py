"""Banner de saúde do provedor de IA na abertura do app (checagem única).

O Streamlit real não é necessário — um stub registra o que a página montaria.
Cobre as três variantes do semáforo (verde, vermelho com a causa raiz real e
amarelo com failover), o silêncio quando a cadeia de modelos está vazia ou a
checagem falha, e a checagem ÚNICA por sessão (o rerun não repete `llm_health`).
"""

from __future__ import annotations

import importlib
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

#: Raiz da UI no código-fonte (o boot chama o banner no `app.py`).
UI_DIR = Path(__file__).resolve().parents[2] / "src" / "ui"

#: Causa raiz real de um provedor sem crédito (formato do contrato `llm_health`).
DETAIL_403 = "HTTP 403 — Key limit exceeded (total limit)"


class FakeStreamlit(types.ModuleType):
    """Stub de `streamlit` que registra os elementos que a UI renderizaria."""

    def __init__(self) -> None:
        super().__init__("streamlit")
        self.session_state: dict = {}
        self.calls: list[tuple[str, object]] = []

    def _record(self, kind: str, payload: object = None) -> None:
        self.calls.append((kind, payload))

    def success(self, message, **kwargs) -> None:
        self._record("success", message)

    def error(self, message, **kwargs) -> None:
        self._record("error", message)

    def warning(self, message, **kwargs) -> None:
        self._record("warning", message)

    def info(self, message, **kwargs) -> None:
        self._record("info", message)

    def caption(self, message, **kwargs) -> None:
        self._record("caption", message)

    def write(self, message, **kwargs) -> None:
        self._record("write", message)

    def json(self, body, **kwargs) -> None:
        self._record("json", body)

    def subheader(self, message, **kwargs) -> None:
        self._record("subheader", message)

    def header(self, message, **kwargs) -> None:
        self._record("header", message)

    def dataframe(self, data, **kwargs) -> None:
        self._record("dataframe", data)

    def table(self, data, **kwargs) -> None:
        self._record("table", data)

    def button(self, label, **kwargs) -> bool:
        self._record("button", label)
        return False

    @contextmanager
    def spinner(self, text):
        self._record("spinner", text)
        yield

    @contextmanager
    def expander(self, label):
        self._record("expander", label)
        yield


class StubPolicyApi:
    """Fachada de análise mínima para o banner (registra as chamadas de saúde)."""

    def __init__(self, report: list | None = None, error: Exception | None = None) -> None:
        self.health_calls = 0
        self.report = report
        self.error = error

    def llm_health(self) -> list:
        self.health_calls += 1
        if self.error is not None:
            raise self.error
        return self.report


class StubSemSaude:
    """Fachada sem `llm_health` (client de LLM ausente ou fachada defasada)."""


def _level(model: str, ok: bool, detail: str | None = None) -> dict:
    """Um nível da cadeia de modelos no formato do contrato `llm_health`."""
    return {"provider": "openrouter", "model": model, "ok": ok, "detail": detail}


@pytest.fixture
def ui_health(monkeypatch):
    """`ui.components.health` reimportado sobre o stub de `streamlit`."""
    fake = FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    for name in [name for name in sys.modules if name.startswith("ui.components")]:
        monkeypatch.delitem(sys.modules, name)
    health = importlib.import_module("ui.components.health")
    return fake, health


def test_banner_verde_com_um_nivel_ok(ui_health):
    fake, health = ui_health
    api = StubPolicyApi([_level("xiaomi/mimo-v2.6-pro", True)])

    health.render_llm_health_banner(api)

    assert fake.calls == [("success", "Provedor de IA: OK (xiaomi/mimo-v2.6-pro)")]


def test_banner_vermelho_mostra_a_causa_raiz_quando_todos_os_niveis_falham(ui_health):
    fake, health = ui_health
    api = StubPolicyApi(
        [
            _level("xiaomi/mimo-v2.6-pro", False, DETAIL_403),
            _level("gemini-3.8-flash", False, DETAIL_403),
        ]
    )

    health.render_llm_health_banner(api)

    message = (
        f"Provedor de IA indisponível — {DETAIL_403}. "
        "Recarregue os créditos da chave em openrouter.ai e recarregue a página."
    )
    assert fake.calls == [("error", message)]
    assert DETAIL_403 in message  # causa raiz real (HTTP 403) visível na tela


def test_banner_amarelo_quando_ha_niveis_degradados_com_failover(ui_health):
    fake, health = ui_health
    api = StubPolicyApi(
        [
            _level("xiaomi/mimo-v2.6-pro", False, DETAIL_403),
            _level("gemini-3.8-flash", True),
        ]
    )

    health.render_llm_health_banner(api)

    assert fake.calls == [
        (
            "warning",
            f"Provedor de IA com níveis indisponíveis: xiaomi/mimo-v2.6-pro "
            f"(motivo: {DETAIL_403}) — o failover está ativo.",
        )
    ]


def test_sem_banner_para_cadeia_de_modelos_vazia(ui_health):
    fake, health = ui_health
    api = StubPolicyApi([])

    health.render_llm_health_banner(api)

    assert fake.calls == []  # sem níveis compatíveis → silêncio na tela


def test_sem_banner_quando_a_fachada_nao_tem_llm_health(ui_health):
    fake, health = ui_health

    health.render_llm_health_banner(StubSemSaude())  # não pode quebrar o app

    assert fake.calls == []


def test_sem_banner_quando_llm_health_levanta_excecao(ui_health):
    fake, health = ui_health
    api = StubPolicyApi(error=RuntimeError("sem rede"))

    health.render_llm_health_banner(api)  # não pode quebrar o app

    assert fake.calls == []


def test_checagem_de_saude_roda_uma_unica_vez_por_sessao(ui_health):
    fake, health = ui_health
    api = StubPolicyApi([_level("xiaomi/mimo-v2.6-pro", True)])

    health.render_llm_health_banner(api)
    fake.calls.clear()
    health.render_llm_health_banner(api)  # rerun do Streamlit

    assert api.health_calls == 1  # o provedor não é consultado de novo
    assert fake.calls == [("success", "Provedor de IA: OK (xiaomi/mimo-v2.6-pro)")]  # banner segue visível


def test_app_chama_o_banner_na_abertura():
    """O boot da UI consulta a saúde do provedor antes do restante da página."""
    app_source = (UI_DIR / "app.py").read_text(encoding="utf-8")

    assert "render_llm_health_banner(policy_api)" in app_source
