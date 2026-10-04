---
protocol_version: 1
debate_id: BUG-20261004-YFN3-r1
bug_id: BUG-20261004-YFN3
role: solver
solver_id: agente-1
engine: local
round: 1
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Estratégia de correção
Mantida a essência da rodada 0 (sanitizar a mensagem + suprimir a cadeia) e refinada com o que os demais acertaram:
1. Em `application/extraction.py` (135-140), trocar `{exc}` por só tipo, campo e contagem:
   `f"saída do LLM fora do contrato em {req.field_code}: {type(exc).__name__} com {len(exc.errors())} erro(s) de schema"`.
   Sai `str(exc)`, `exc.errors()[...]["msg"|"ctx"|"input"|"url"]` e todo eco de valor; ficam `LLM_SCHEMA_INVALID`, `field_code`, `ValidationError` e a contagem (diagnóstico útil).
2. Trocar `from exc` por `from None`: a cadeia renderizada em traceback/log deixa de expor o `ValidationError` cru (que ecoa o input). Reversível em um token.
3. Escopo cirúrgico: somente este `except`. Nada em `errors.py`, `llm_agent.py`, `document_processing_source.py` nem UI; mudança de duas linhas, `ClassifiedError`, `code`, `retriable` e o shape de `to_dict()` intactos.
Decisão mantida contra a variante "levantar fora do bloco `except`" (agente-3): `from None` já torna segura toda superfície de log/renderização do projeto (a rubrica fala de mensagem, log e `to_dict()`); zerar também o `__context__` residual, alcançável só por introspecção, custa reestruturação do try/except e é adiável.

## Causa raiz proposta
`f"...: {exc}"` interpola `str(ValidationError)` do Pydantic, que ecoa o `input` da validação (valor extraído da apólice); o `from exc` mantém esse erro cru vivo na cadeia de exceções, segunda via de vazamento em traceback/log. O `except` não aplica o padrão T-2a (dev2-003 descartou exatamente `str(exc)`/`errors()[...]["msg"]`): derrapagem de implementação, não de spec.

## Teste
Anti-vazamento novo em `tests/modules/policy_analysis/test_extraction_agent.py`, padrão `APOLICE_MARKER` de `test_metrics.py` (L27, L265-278): StubAgent devolve `confidence="TEXTO-CONFIDENCIAL-APOLICE-XYZ"`; o Pydantic rejeita e o marcador vira `input` do erro. Com `pytest.raises(ClassifiedError)`:
- `code == "LLM_SCHEMA_INVALID"`, `retriable is True`, mensagem traz `field_code` e a contagem;
- marcador ausente de `str(exc)`, `repr(exc)`, `exc.to_dict()["message"]`, `to_processing_status("DOC-1", exc).message` e `"".join(traceback.format_exception(exc))` (prova a cadeia suprimida);
- `exc.__cause__ is None` (e `__suppress_context__` True).
Vermelho antes do fix, verde depois. Regressão: suíte verde (módulo policy_analysis, `test_errors`, `test_error_sanitization`, `test_pipeline_offline`, e2e/governance); nenhum teste existente asserta texto exato da mensagem (verificado por busca).

## Impacto sobre a spec
Nenhuma mudança de spec: cumpre o já normatizado (T-2a do plano-acao-dev2: tipo + estágio/field_code + IDs/contagem, nunca valor; policy-analysis §12 "nenhum texto integral em logs"; §6.1 RF-09; dev2-003 §6.1). Contrato público estável.

## Riscos e efeitos colaterais
- Diagnóstico mais sintético (perde qual constraint falhou): aceito pela higiene T-2a, compensado por tipo + campo + contagem.
- `from None` esconde a causa em depuração local; investigar reproduzindo o caso com marcador no teste, não via log.
- Residual conhecido: `__context__` continua apontando para o `ValidationError` cru em introspecção (agente-3); fora das superfícies de log e coberto pela variante de rodada 2 se necessário.
- Consumidores do texto: nenhum identificado (`to_processing_status` repete só a mensagem já sanitizada; UI usa `.code`).

## Evidências
- `extraction.py` 135-140 (`{exc}` + `from exc`); `evidence/rota-descartada-dev2-003.txt`.
- T-2a: `_cause` em `document_processing/application/service.py` (L285: "NUNCA `str(exc)`") e `_with_retries` em `policy_analysis/infrastructure/llm_agent.py` (só tipo + contagem).
- `errors.py` L41 (`to_processing_status` ecoa `{exc}` da mensagem) e `src/ui/errors.py` (UI ecoa só `.code`).
- Eco de `str(exc)` também em `llm_agent.py` L267 e `document_processing_source.py` L30 (fora do caminho exibido; follow-up próprio, não entra no change_set).
- Uso de `__cause__` no repo: só `tests/integration/test_pipeline_offline.py` L92 (não depende desta exceção).

## Confiança
alta. Causa, vetores (mensagem e cadeia), superfícies consumidoras e o padrão canônico estão confirmados no código; correção de duas linhas com teste anti-vazamento específico.

## Crítica às demais propostas
- agente-2: convergente e correta nas duas vias (mensagem e `from exc`) e boa inclusão de `repr(exc)` no teste, que adoto. Pontos fracos: afirma que o `__context__` residual "não é renderizado por caminho de log" sem evidência de teste (é verdade para renderização com `__suppress_context__`, mas introspecção continua expondo o erro cru); não asserta `to_processing_status` nem `__cause__ is None`; sugere promover BUG-20261004-ODCS sem eu ter visto no snapshot a evidência que sustenta o vínculo. Mantém escopo cirúrgico correto.
- agente-3: a mais completa em teste (arquivo fixado, `to_processing_status`, `__cause__ is None`, verificação de que nenhum teste asserta o texto da mensagem) e a única a nomear os ecos residuais (`llm_agent.py` L267, `document_processing_source.py`), que conferi e confirmo como follow-up. Pontos fracos: a variante "levantar fora do bloco `except`" é mudança maior que a rubrica pede para o ganho marginal de zerar `__context__`, e ela própria admite que renderização de log já fica segura com `from None`; a assertiva `exc.__cause__ is None` sozinha não distingue `from None` de "sem exceção ativa", o teste de traceback formatado é o que realmente prova a supressão.
- Síntese adotada: mensagem minimalista de agente-2/agente-3 + `from None` com decisão explícita sobre `__context__` (agente-3) + bateria de assertivas de agente-3 enriquecida com `__suppress_context__` e traceback formatado. Nenhum dos três errou a causa raiz; a disputa era de profundidade de teste e de limpeza da cadeia.
