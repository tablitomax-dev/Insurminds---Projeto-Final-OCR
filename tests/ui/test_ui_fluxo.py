"""Fluxo da UI enxuta: extração automática e Relatório D&O fora da página.

O Streamlit real não é necessário — um stub registra o que a página montaria.
Cobre a simplificação da UI: sem botão "Extrair todos os campos", sem a tabela
de campos extraídos, extração UMA única vez por conjunto de apólices, aviso de
conclusão e seção "5. Relatório D&O" oculta (componente preservado).
"""

from __future__ import annotations

import importlib
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

from fakes import make_fact
from modules.policy_analysis.public_api import ClassifiedError

#: Raiz da UI no código-fonte (o componente de relatório continua lá).
UI_DIR = Path(__file__).resolve().parents[2] / "src" / "ui"

#: Par de apólices do fluxo e o catálogo mínimo de campos.
POLICY_IDS = ("pol_allianz", "pol_porto")
FIELDS = [{"code": "limite_agregado", "label": "Limite agregado"}]

#: Rótulos de exibição das apólices (nome real das seguradoras).
LABELS = {"pol_allianz": "Allianz Seguros", "pol_porto": "Porto Seguro"}

#: Aviso esperado quando processamento + extração terminam.
EXTRACTION_DONE_NOTICE = (
    "Extração concluída — você já pode fazer suas perguntas na seção de consulta livre."
)


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
    """Fachada de análise mínima para o estágio de extração (registra chamadas)."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.error = error

    def extract_fields(self, policy_id: str, codes: list[str]) -> list:
        self.calls.append((policy_id, tuple(codes)))
        if self.error is not None:
            raise self.error
        return [make_fact(policy_id, code) for code in codes]


@pytest.fixture
def ui_stages(monkeypatch):
    """`ui.components.stages` reimportado sobre o stub de `streamlit`."""
    fake = FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    for name in [name for name in sys.modules if name.startswith("ui.components")]:
        monkeypatch.delitem(sys.modules, name)
    stages = importlib.import_module("ui.components.stages")
    return fake, stages


def test_extracao_e_automatica_apos_o_processamento(ui_stages):
    fake, stages = ui_stages
    fake.session_state["process_done"] = POLICY_IDS
    api = StubPolicyApi()

    stages.render_extraction(api, POLICY_IDS, FIELDS, LABELS)

    assert api.calls == [(policy_id, ("limite_agregado",)) for policy_id in POLICY_IDS]
    assert ("success", EXTRACTION_DONE_NOTICE) in fake.calls


def test_extracao_roda_uma_unica_vez_por_conjunto_de_apolices(ui_stages):
    fake, stages = ui_stages
    fake.session_state["process_done"] = POLICY_IDS
    api = StubPolicyApi()

    stages.render_extraction(api, POLICY_IDS, FIELDS, LABELS)
    fake.calls.clear()
    stages.render_extraction(api, POLICY_IDS, FIELDS, LABELS)  # rerun do Streamlit

    assert len(api.calls) == len(POLICY_IDS)  # a LLM não é chamada de novo
    assert ("success", EXTRACTION_DONE_NOTICE) in fake.calls  # aviso segue visível


def test_novo_conjunto_de_apolices_refaz_a_extracao(ui_stages):
    fake, stages = ui_stages
    fake.session_state["process_done"] = POLICY_IDS
    api = StubPolicyApi()
    stages.render_extraction(api, POLICY_IDS, FIELDS, LABELS)

    outros = ("pol_axa", "pol_azul")
    fake.session_state["process_done"] = outros
    stages.render_extraction(api, outros, FIELDS, LABELS)

    assert len(api.calls) == len(POLICY_IDS) + len(outros)


def test_nao_extrai_antes_do_processamento(ui_stages):
    fake, stages = ui_stages
    api = StubPolicyApi()

    stages.render_extraction(api, POLICY_IDS, FIELDS, LABELS)

    assert api.calls == []
    assert fake.calls == []


def test_tabela_de_campos_extraidos_nao_aparece(ui_stages):
    fake, stages = ui_stages
    fake.session_state["process_done"] = POLICY_IDS
    api = StubPolicyApi()

    stages.render_extraction(api, POLICY_IDS, FIELDS, LABELS)

    kinds = [kind for kind, _ in fake.calls]
    assert "button" not in kinds  # sem "Extrair todos os campos das duas apólices"
    assert "dataframe" not in kinds  # sem tabela campo | seguradora | seguradora
    assert "expander" not in kinds  # sem expander por campo extraído
    assert "subheader" not in kinds  # sem "Campos adicionais identificados pela LLM"
    textos = [str(payload) for _, payload in fake.calls]
    assert all("Campos extraídos" not in texto for texto in textos)
    assert all("Extrair todos os campos" not in texto for texto in textos)


def test_falha_na_extracao_mostra_erro_com_dica_sem_aviso_de_conclusao(ui_stages):
    fake, stages = ui_stages
    fake.session_state["process_done"] = POLICY_IDS
    api = StubPolicyApi(
        ClassifiedError("LLM_UNAVAILABLE", "provedor de LLM indisponível após 3 tentativas", retriable=True)
    )

    stages.render_extraction(api, POLICY_IDS, FIELDS, LABELS)
    chamadas = len(api.calls)

    erros = [str(payload) for kind, payload in fake.calls if kind == "error"]
    assert erros == [
        "EXTRACAO/Allianz Seguros: Erro classificado — "
        "Os provedores de IA não responderam após várias tentativas. Tente novamente em instantes. "
        "provedor de LLM indisponível após 3 tentativas (código LLM_UNAVAILABLE)",
        "EXTRACAO/Porto Seguro: Erro classificado — "
        "Os provedores de IA não responderam após várias tentativas. Tente novamente em instantes. "
        "provedor de LLM indisponível após 3 tentativas (código LLM_UNAVAILABLE)",
    ]
    assert all(kind != "success" for kind, _ in fake.calls)

    fake.calls.clear()
    stages.render_extraction(api, POLICY_IDS, FIELDS, LABELS)  # rerun: sem repetir o LLM
    assert len(api.calls) == chamadas
    assert [kind for kind, _ in fake.calls] == ["error", "error"]  # erro segue visível


def test_secao_5_relatorio_do_fica_fora_da_pagina():
    """Nada do Relatório D&O é montado na página; o componente continua existindo."""
    app_source = (UI_DIR / "app.py").read_text(encoding="utf-8")

    assert "render_report" not in app_source  # sem título, botão ou painel na página
    assert "export_report" not in app_source  # sem atalho de exportação do relatório

    report_source = (UI_DIR / "components" / "report.py").read_text(encoding="utf-8")
    assert "def render_report(" in report_source  # código preservado (não apagado)
