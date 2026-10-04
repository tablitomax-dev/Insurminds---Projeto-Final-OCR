---
protocol_version: 1
debate_id: BUG-20261004-YFN3-final
bug_id: BUG-20261004-YFN3
role: judge
round: 2
status: ok
finished_at: 2026-10-04
---

## Síntese

Estratégia vencedora (correção de duas linhas, somente o `except ValidationError` de `_build_fact` em `src/modules/policy_analysis/application/extraction.py` L134-139):
1. Mensagem do `ClassifiedError` passa a conter só tipo + estágio + IDs/contagem (T-2a):
   `f"saída do LLM fora do contrato em {req.field_code}: {type(exc).__name__}, {len(exc.errors())} problema(s) de schema"`.
   Ficam `code` `LLM_SCHEMA_INVALID`, `field_code`, `ValidationError` e a contagem de problemas;
   sai todo eco de valor: `{exc}`, `str(exc)`, `repr(exc)`, `exc.errors()[...]["msg"|"ctx"|"input"|"url"]` e o dict completo (rota descartada em dev2-003). `retriable=True` intacto.
2. Encadeamento: `raise ... from exc` vira `raise ... from None`. `__suppress_context__` impede a renderização do `ValidationError` cru (que ecoa o input) em traceback/log; reversível em um token. O residual `__context__` só é alcançável por introspecção (varredura: zero `logger.exception`, zero leituras de `__context__`, único `__cause__` é teste alheio) e fica como plano B documentado (levantar fora do bloco `except`), não executado, pois reestruturar o try viola a menor mudança coerente.
3. Escopo: só este `except`. `errors.py`, `llm_agent.py`, `document_processing_source.py`, `ui/errors.py` e testes existentes intactos; `ClassifiedError`, `code`, `retriable` e o shape de `to_dict()`/`to_processing_status` preservados (esses ficam seguros por herança da mensagem limpa). Ecos de `str(exc)` em `llm_agent.py` L267 e `document_processing_source.py` L30: follow-up próprio, fora do change_set.
4. Teste (reprodução + anti-vazamento) em `tests/modules/policy_analysis/test_extraction_agent.py`, padrão `APOLICE_MARKER` de `test_metrics.py`: StubAgent devolve `confidence="TEXTO-CONFIDENCIAL-APOLICE-XYZ"` (viola `Field(ge=0, le=1)` de `shared_kernel/contracts.py`) e o marcador vira `input` do `ValidationError`. Vermelho antes do fix, verde depois, com `pytest.raises(ClassifiedError)`: contrato (`code == "LLM_SCHEMA_INVALID"`, `retriable is True`, mensagem traz `field_code`, `type(exc).__name__` e a contagem); caixa-preta (contrato real): marcador ausente de `str(exc)`, `repr(exc)`, `exc.to_dict()["message"]`, `to_processing_status("DOC-1", exc).message` e `"".join(traceback.format_exception(exc))`; guarda de mecanismo única e nomeada como política: `exc.__cause__ is None` e `exc.__suppress_context__ is True`, sempre acompanhada da asserção de traceback (a prova real de não vazamento), para travar regressão silenciosa para `from exc`. Regressão: `tests/modules/policy_analysis`, `tests/contracts/test_errors.py`, `tests/contracts/test_processing_status.py`, `tests/ui/test_error_sanitization.py`, `tests/e2e/test_governance_journey.py`, `tests/integration/test_pipeline_offline.py`, `tests/modules/document_processing`. Nenhum teste asserta o texto exato da mensagem (busca reconfirmada).

## Vencedora

P-B

## Enxertos aproveitados

- De P-A: a ressalva de que `exc.__cause__ is None` não distingue `from None` de ausência de causa (por isso a asserção vem pareada com `__suppress_context__` e nomeada como guarda deliberada); o inventário explícito dos ecos residuais de `str(exc)` (`llm_agent.py` L267, `document_processing_source.py` L30) como follow-up fora do escopo; a correção de que `errors.py` L41 interpola `{exc}` e só é seguro por herança da mensagem já limpa.
- De P-C: a regra de que o assert de mecanismo só vale sempre acompanhado do teste de traceback formatado (caixa-preta é o contrato); a retirada da promoção de `related-to` BUG-20261004-ODCS do fechamento (ruído de processo fora do escopo do fix).

## Justificativa por critério

1. Elimina a causa raiz: empate técnico (as três veem as duas vias: `{exc}` na mensagem e `from exc` na cadeia); todas trocam por tipo + campo + contagem e `from None`.
2. Menor mudança coerente: empate (duas linhas, um `except`); P-B foi a única que explicitamente arquivou a reestruturação do try como plano B não executado, com evidência da varredura.
3. Menor risco de regressão: P-B vence, com a bateria mais completa de superfícies (str, repr, `to_dict`, `to_processing_status`, traceback) e a suíte de regressão mais ampla (`test_processing_status`, `test_pipeline_offline`).
4. Reversibilidade: empate (fix de duas linhas, `from None` reversível em um token, contrato público estável).
5. Aderência à spec e Agent Notes: P-B vence no desempate fino: guarda de mecanismo nomeada como política (resolve a inconsistência apontada em P-A), diagnóstico útil mantido (campo/tipo/contagem) e teste anti-vazamento específico vermelho/verde, tudo dentro do T-2a, RF-09 e da rota descartada de dev2-003.

## Confiança

alta. As três propostas convergiram na correção de duas linhas e o desempate se deu por profundidade de teste e disciplina de escopo, com evidências de código reconfirmadas nas duas rodadas.
