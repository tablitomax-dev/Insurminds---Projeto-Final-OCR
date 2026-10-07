"""FallbackLLMClient — cadeia de failover glm → deepseek → mimo (EC-01, RF-09).

Sem rede: fakes locais contam chamadas, guardam prompts e falham sob demanda.
A cadeia aceita N clientes; os testes usam os 3 níveis reais do wiring.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from modules.policy_analysis.application.errors import ClassifiedError
from modules.policy_analysis.infrastructure.llm_agent import FallbackLLMClient, _with_retries

PROMPT = "prompt de teste"


class ModelHTTPError(Exception):
    """Réplica do erro HTTP do Pydantic AI (o nome bate com o do SDK)."""

    def __init__(self, message: str = "provedor indisponível", status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class FakeClient:
    """Cliente LLM fake: conta chamadas, guarda prompts e falha sob demanda.

    Contadores protegidos por lock: a cadeia é exercitada em paralelo e o
    teste de thread-safety exige que o fake não perca incrementos.
    """

    def __init__(
        self,
        resposta=None,
        falhas: int = 0,
        sempre_falha: bool = False,
        erro: Exception | None = None,
        modelo: str = "fake",
    ):
        self.resposta = resposta if resposta is not None else {"fonte": "fake"}
        self.falhas = falhas
        self.sempre_falha = sempre_falha
        self.erro = erro if erro is not None else ModelHTTPError("provedor indisponível")
        self._model_name = modelo
        self._lock = threading.Lock()
        self.calls = 0
        self.prompts: list[str] = []
        self.usage: list[dict] = []

    def complete_json(self, prompt: str):
        with self._lock:
            self.calls += 1
            self.prompts.append(prompt)
            falhar = self.sempre_falha or self.calls <= self.falhas
        if falhar:
            raise self.erro
        self.usage.append({"model": self._model_name, "tokens": None, "prompt_chars": len(prompt)})
        return self.resposta


def _rodar(client: FallbackLLMClient, prompt: str = PROMPT, attempts: int = 3):
    """Chamada como os agentes fazem: `_with_retries` ao redor do client."""
    return _with_retries(lambda: client.complete_json(prompt), attempts=attempts, backoff=0.0)


def _cadeia(**kwargs) -> tuple[FallbackLLMClient, FakeClient, FakeClient, FakeClient]:
    """Cadeia glm → deepseek → mimo com fakes nomeados como no wiring real."""
    glm = FakeClient(resposta={"fonte": "glm"}, modelo="glm-fake", **kwargs)
    deepseek = FakeClient(resposta={"fonte": "deepseek"}, modelo="deepseek-fake", **kwargs)
    mimo = FakeClient(resposta={"fonte": "mimo"}, modelo="mimo-fake", **kwargs)
    return FallbackLLMClient(glm, deepseek, mimo), glm, deepseek, mimo


def test_falha_unica_do_glm_eh_repetida_ainda_no_glm():
    """1 falha não atinge o limiar: o retry externo bate de novo no glm."""
    glm = FakeClient(resposta={"fonte": "glm"}, falhas=1, modelo="glm-fake")
    deepseek = FakeClient(resposta={"fonte": "deepseek"}, modelo="deepseek-fake")
    mimo = FakeClient(resposta={"fonte": "mimo"}, modelo="mimo-fake")
    client = FallbackLLMClient(glm, deepseek, mimo)

    resultado = _rodar(client)

    assert resultado == {"fonte": "glm"}
    assert glm.calls == 2
    assert deepseek.calls == 0
    assert mimo.calls == 0
    assert client.active_provider == "primary"
    assert client.active_model == "glm-fake"
    assert client.failures_by_provider == (0, 0, 0)
    assert client.usage[-1]["provider"] == "primary"


def test_duas_falhas_seguidas_do_glm_caem_no_deepseek_na_mesma_chamada():
    """2 falhas do glm + 1 sucesso do deepseek = 1 chamada OK para o chamador.

    É o ajuste fino do failover por tentativa: o `_with_retries(attempts=3)` do
    agente não precisa de nova chamada — o MESMO prompt cai no deepseek dentro do
    segundo `complete_json`.
    """
    client, glm, deepseek, mimo = _cadeia(sempre_falha=True)
    deepseek.sempre_falha = False

    resultado = _rodar(client)

    assert resultado == {"fonte": "deepseek"}
    assert glm.calls == 2
    assert deepseek.calls == 1
    assert deepseek.prompts == [PROMPT]  # MESMO prompt do glm
    assert mimo.calls == 0
    assert client.active_provider == "fallback"
    assert client.active_model == "deepseek-fake"
    assert client.usage[-1]["provider"] == "fallback"
    assert client.usage[-1]["model"] == "deepseek-fake"  # quem atendeu entra no usage


def test_glm_e_deepseek_esgotados_caem_no_mimo():
    """2 falhas do glm + 2 do deepseek → o mimo atende ainda na 3ª tentativa.

    O avanço cascateia dentro da cadeia: cada nível esgotado move o prompt para o
    próximo sem que o chamador receba erro enquanto houver provedor de pé.
    """
    client, glm, deepseek, mimo = _cadeia(sempre_falha=True)
    glm.sempre_falha = True
    deepseek.sempre_falha = True
    mimo.sempre_falha = False

    resultado = _rodar(client)

    assert resultado == {"fonte": "mimo"}
    assert glm.calls == 2
    assert deepseek.calls == 2
    assert mimo.calls == 1
    assert mimo.prompts == [PROMPT]
    assert client.active_provider == "last_resort"
    assert client.active_model == "mimo-fake"
    assert client.usage[-1]["provider"] == "last_resort"
    assert client.usage[-1]["model"] == "mimo-fake"


def test_cadeia_inteira_falhando_propaga_llm_unavailable():
    """Os 3 provedores esgotados viram `ClassifiedError("LLM_UNAVAILABLE")`."""
    client, glm, deepseek, mimo = _cadeia(sempre_falha=True)

    with pytest.raises(ClassifiedError) as excinfo:
        _rodar(client, attempts=5)  # cobre as 2 falhas do mimo (último recurso)
    assert excinfo.value.code == "LLM_UNAVAILABLE"
    assert excinfo.value.retriable is True
    assert (glm.calls, deepseek.calls, mimo.calls) == (2, 2, 3)
    assert client.failures_by_provider == (2, 2, 3)
    assert client.active_provider == "last_resort"

    # limiar 1 → cascata completa dentro da UMA chamada
    client, glm, deepseek, mimo = _cadeia(sempre_falha=True)
    client = FallbackLLMClient(glm, deepseek, mimo, failover_after=1)
    with pytest.raises(ClassifiedError) as excinfo:
        client.complete_json(PROMPT)
    assert excinfo.value.code == "LLM_UNAVAILABLE"
    assert excinfo.value.retriable is True
    assert (glm.calls, deepseek.calls, mimo.calls) == (1, 1, 1)


def test_apos_avancar_chamas_seguintes_vao_direto_ao_provedor_avancado():
    """Com o contador no limiar, o glm não é mais chamado (sem volta automática)."""
    client, glm, deepseek, mimo = _cadeia()
    glm.sempre_falha = True

    _rodar(client)  # força o failover (2 falhas seguidas do glm)
    chamadas_glm = glm.calls

    for _ in range(3):
        assert client.complete_json("outro prompt") == {"fonte": "deepseek"}

    assert glm.calls == chamadas_glm  # glm intocado após o failover
    assert deepseek.calls == 4
    assert client.failures_by_provider[0] == 2
    assert client.active_provider == "fallback"


def test_reset_failover_volta_ao_glm():
    """Recuperação manual: `reset_failover()` devolve o glm à frente da cadeia."""
    client, glm, deepseek, mimo = _cadeia()
    glm.sempre_falha = True
    _rodar(client)  # failover até o deepseek
    glm.sempre_falha = False  # o glm se recuperou

    client.reset_failover()

    assert client.complete_json(PROMPT) == {"fonte": "glm"}
    assert client.active_provider == "primary"
    assert client.active_model == "glm-fake"
    assert client.failures_by_provider == (0, 0, 0)


def test_sucesso_do_provedor_ativo_zera_o_contador_de_falhas():
    """Recuperação parcial: uma falha isolada não persiste após um sucesso."""
    glm = FakeClient(resposta={"fonte": "glm"}, falhas=1, modelo="glm-fake")
    deepseek = FakeClient(resposta={"fonte": "deepseek"}, modelo="deepseek-fake")
    client = FallbackLLMClient(glm, deepseek)

    with pytest.raises(ClassifiedError):
        client.complete_json(PROMPT)  # 1ª falha entra na contagem (ainda sem avanço)
    assert client.consecutive_failures == 1
    assert deepseek.calls == 0

    assert client.complete_json(PROMPT) == {"fonte": "glm"}  # sucesso zera
    assert client.consecutive_failures == 0

    glm.falhas = 3  # próxima chamada falha de novo
    with pytest.raises(ClassifiedError):
        client.complete_json(PROMPT)
    # o contador voltou do zero: 1 falha, e não 2 — o avanço não foi disparado
    assert client.consecutive_failures == 1
    assert client.active_provider == "primary"
    assert deepseek.calls == 0


def test_chamadas_concorrentes_nao_corrompem_os_contadores():
    """ThreadPoolExecutor: cada falha conta exatamente 1× em cada provedor."""
    client, glm, deepseek, mimo = _cadeia()
    glm.sempre_falha = True
    total = 32

    with ThreadPoolExecutor(max_workers=8) as pool:
        resultados = list(pool.map(lambda _: _rodar(client), range(total)))

    assert resultados == [{"fonte": "deepseek"}] * total
    assert deepseek.calls == total
    assert mimo.calls == 0
    # cada falha do glm incrementa o contador exatamente 1× (sem corrupção)
    assert client.failures_by_provider[0] == glm.calls
    # nenhuma rotina fica repetindo o glm para sempre: no máx. 2 tentativas por chamada
    assert 2 <= glm.calls <= 2 * total
    assert client.active_provider == "fallback"


# --- classificação por status HTTP (fail-fast; causa raiz preservada) --------


def test_403_falha_imediata_sem_retry_nem_avanco_de_cadeia():
    """403 (limite da conta) → `LLM_QUOTA_EXCEEDED` com retriable=False.

    É problema de CONTA: retry e cadeia de fallback não resolvem (todos os
    níveis compartilham a chave) — 1 chamada só e causa raiz na mensagem.
    """
    erro_403 = ModelHTTPError("Key limit exceeded (total limit)", status_code=403)
    client, glm, deepseek, mimo = _cadeia(sempre_falha=True)
    for fake in (glm, deepseek, mimo):
        fake.erro = erro_403

    with pytest.raises(ClassifiedError) as excinfo:
        _rodar(client, attempts=5)

    assert excinfo.value.code == "LLM_QUOTA_EXCEEDED"
    assert excinfo.value.retriable is False
    assert "HTTP 403 — Key limit exceeded" in str(excinfo.value)
    assert (glm.calls, deepseek.calls, mimo.calls) == (1, 0, 0)  # fail-fast
    assert client.failures_by_provider == (0, 0, 0)  # 401/403 não conta


def test_401_vira_llm_auth_failed():
    """401 (chave inválida) → `LLM_AUTH_FAILED` fail-fast, sem avançar a cadeia."""
    erro_401 = ModelHTTPError("no auth", status_code=401)
    client, glm, deepseek, mimo = _cadeia()
    glm.erro = erro_401
    glm.sempre_falha = True

    with pytest.raises(ClassifiedError) as excinfo:
        _rodar(client, attempts=5)

    assert excinfo.value.code == "LLM_AUTH_FAILED"
    assert excinfo.value.retriable is False
    assert "HTTP 401" in str(excinfo.value)
    assert (glm.calls, deepseek.calls, mimo.calls) == (1, 0, 0)
    assert client.active_provider == "primary"


def test_404_pula_direto_para_o_proximo_nivel_sem_consumir_o_limiar():
    """404 = modelo inválido NESTE nível: pula já, sem retry nem contagem."""
    erro_404 = ModelHTTPError("model not found", status_code=404)
    client, glm, deepseek, mimo = _cadeia()
    glm.erro = erro_404
    glm.sempre_falha = True

    resultado = _rodar(client)

    assert resultado == {"fonte": "deepseek"}
    assert glm.calls == 1  # sem retry no modelo inválido
    assert deepseek.calls == 1
    assert client.failures_by_provider[0] == 0  # não consumiu o failover_after
    assert client.active_provider == "fallback"


def test_ultimo_nivel_com_404_propaga_llm_unavailable_com_causa_raiz():
    """Cascata 400/404 até o fim da cadeia: `LLM_UNAVAILABLE` com "HTTP 404"."""
    erro_404 = ModelHTTPError("model not found", status_code=404)
    client, glm, deepseek, mimo = _cadeia()
    for fake in (glm, deepseek, mimo):
        fake.erro = erro_404
        fake.sempre_falha = True

    with pytest.raises(ClassifiedError) as excinfo:
        client.complete_json(PROMPT)  # pula direto, cabe tudo numa chamada

    assert excinfo.value.code == "LLM_UNAVAILABLE"
    assert excinfo.value.retriable is True
    assert "HTTP 404 — model not found" in str(excinfo.value)
    assert (glm.calls, deepseek.calls, mimo.calls) == (1, 1, 1)


def test_erro_nao_reexecutavel_nao_queima_tentativas_do_with_retries():
    """Fail-fast no `_with_retries`: retriable=False propaga na 1ª chamada."""
    chamadas = 0

    def fn():
        nonlocal chamadas
        chamadas += 1
        raise ClassifiedError("LLM_QUOTA_EXCEEDED", "sem crédito", retriable=False)

    with pytest.raises(ClassifiedError) as excinfo:
        _with_retries(fn, attempts=3, backoff=0.0)

    assert excinfo.value.code == "LLM_QUOTA_EXCEEDED"
    assert chamadas == 1


def test_mensagem_final_do_with_retries_traz_a_causa_raiz():
    """HTTP preserva a causa raiz; texto livre do provedor não vaza (T-2a)."""

    def fn():
        raise ModelHTTPError("Key limit exceeded (total limit)", status_code=502)

    with pytest.raises(ClassifiedError) as excinfo:
        _with_retries(fn, attempts=2, backoff=0.0)

    assert "após 2 tentativas" in str(excinfo.value)
    assert "HTTP 502 — Key limit exceeded (total limit)" in str(excinfo.value)

    def fn_solto():
        raise RuntimeError("boom: texto que ecoa apólice")

    with pytest.raises(ClassifiedError) as excinfo:
        _with_retries(fn_solto, attempts=1, backoff=0.0)

    assert "texto que ecoa apólice" not in str(excinfo.value)  # T-2a
    assert "RuntimeError" in str(excinfo.value)  # só o tipo


# --- health_check (diagnóstico da cadeia) -----------------------------------


def test_health_check_reporta_cada_nivel_com_causa_raiz():
    """Um item por nível; `detail` traz a causa raiz; não mexe nos contadores."""
    client, glm, deepseek, mimo = _cadeia()
    glm.sempre_falha = True
    glm.erro = ModelHTTPError("Key limit exceeded (total limit)", status_code=403)

    relatorio = client.health_check()

    assert [item["provider"] for item in relatorio] == ["primary", "fallback", "last_resort"]
    assert [item["ok"] for item in relatorio] == [False, True, True]
    assert relatorio[0]["model"] == "glm-fake"
    assert "HTTP 403 — Key limit exceeded" in relatorio[0]["detail"]
    assert relatorio[1]["detail"] is None
    assert client.failures_by_provider == (0, 0, 0)  # diagnóstico não conta
    assert client.active_provider == "primary"


def test_facade_llm_health_delega_ao_client_e_nunca_falha():
    """`PolicyAnalysisFacade.llm_health()`: contrato do banner da UI (F-15)."""
    from modules.policy_analysis.public_api import PolicyAnalysisFacade

    client, *_ = _cadeia()
    facade = PolicyAnalysisFacade(object(), object(), object(), llm_client=client)
    relatorio = facade.llm_health()
    assert len(relatorio) == 3
    assert all(item["ok"] for item in relatorio)

    # sem client compatível → []
    assert PolicyAnalysisFacade(object(), object(), object()).llm_health() == []

    # health_check que levanta exceção → [] (nunca derruba a UI)
    class Ruim:
        def health_check(self):
            raise RuntimeError("boom")

    assert PolicyAnalysisFacade(object(), object(), object(), llm_client=Ruim()).llm_health() == []
