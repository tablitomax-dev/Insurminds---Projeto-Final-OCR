---
protocol_version: 1
debate_id: BUG-20261004-YFN3-r2
bug_id: BUG-20261004-YFN3
role: solver
solver_id: agente-2
engine: local
round: 2
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Estratégia de correção

Proposta final, sintetizando a convergência da rodada 1 e fechando os pontos em disputa:

1. Mensagem do `ClassifiedError` (`extraction.py` L135-139) só com tipo + estágio + IDs/diagnóstico permitido: `f"saída do LLM fora do contrato em {req.field_code}: {type(exc).__name__} com {len(exc.errors())} problema(s) de schema"`. Proibido `str(exc)`, `exc.errors()[...]["msg"|"ctx"|"input"|"url"]` e o dict completo (rota descartada em dev2-003). Ficam `LLM_SCHEMA_INVALID`, `field_code`, `ValidationError` e a contagem.
2. `from exc` vira `from None` (decisão final sobre o encadeamento): com `__suppress_context__`, nenhum traceback/log renderiza o `ValidationError` cru; `to_dict()`/`to_processing_status` herdam a mensagem já limpa. O residual `__context__` só aparece por introspecção deliberada, fora das superfícies da rubrica (mensagem, log, `to_dict()`); zerá-lo exigiria reestruturar o try/except (variante do agente-3), que viola "menor mudança" por ganho não observável. Fica como plano B registrado, não executado.
3. Escopo cirúrgico: somente o `except ValidationError` de `_build_fact`. `errors.py`, `llm_agent.py`, `document_processing_source.py` e `ui/errors.py` intactos; duas linhas alteradas, reversível em um token.
4. Retiro a promoção de BUG-20261004-ODCS do fechamento (crítica do agente-3 aceita: ruído de processo fora do escopo). Os ecos de `str(exc)` em `llm_agent.py` L267 e `document_processing_source.py` L30 seguem como followup próprio, fora do change_set.

## Causa raiz proposta

`f"...: {exc}"` interpola `str(ValidationError)`, que ecoa o `input` validado (valor da apólice); o `from exc` mantém o erro cru na cadeia, segunda via de vazamento. Raiz: o `except` não aplica o padrão T-2a, contrariando o normatizado em dev2-003. Precisão reafirmada: `errors.py` L40-41 interpola `{exc}` do `ClassifiedError`, logo a mensagem é o ponto único de fuga, e os consumidores ficam seguros por herança da mensagem limpa.

## Teste

Reprodução/anti-vazamento novo em `tests/modules/policy_analysis/` (padrão `APOLICE_MARKER` de `test_metrics.py`): StubAgent devolve `confidence="TEXTO-CONFIDENCIAL-APOLICE-XYZ"` (viola `Field(ge=0, le=1)` de `shared_kernel/contracts.py`). Vermelho antes do fix (o marcador aparece em `str(ClassifiedError)`); verde depois, com `pytest.raises(ClassifiedError)`:
- contrato: `code == "LLM_SCHEMA_INVALID"`, `retriable is True`, mensagem contém `field_code`, `ValidationError` e a contagem;
- anti-vazamento (caixa-preta, é o contrato): marcador ausente de `str(exc)`, `repr(exc)`, `exc.to_dict()["message"]`, `to_processing_status("DOC-1", exc).message` e `"".join(traceback.format_exception(exc))`;
- mecanismo (documenta a supressão, adotado do agente-1 e do agente-3 com a ressalva do agente-1): `exc.__cause__ is None` e `exc.__suppress_context__ is True`, sempre acompanhado da asserção de traceback, que é a prova real de não vazamento.

Regressão: suíte verde, com atenção a `test_extraction_agent`, `test_metrics`, `test_errors`, `test_error_sanitization`, `test_e2e_flow.test_cenario_saida_llm_invalida_nao_vira_fato`, `tests/e2e/test_governance_journey.py` e `tests/contracts/test_errors.py`. Confirmado por busca (agente-3, rodada 1): nenhum teste asserta o texto exato da mensagem.

## Impacto sobre a spec

Nenhuma mudança de spec: cumpre o já normatizado (plano-acao-dev2 T-2a; policy-analysis §12 "nenhum texto integral em logs" e §6.1 RF-09; dev2-003 §6.1 "erros sanitizados"; rota descartada em `actions.md`). Contrato público estável (`ClassifiedError`, `code`, `retriable`, `to_dict`, `to_processing_status`, UI). `resolution_kind`: fix de código, sem addenda; `change_risk` baixo reafirmado.

## Riscos e efeitos colaterais

- Diagnóstico mais sintético (perde a constraint exata): compensado por campo + tipo + contagem, exigido pela rubrica; reprodução local via teste determinístico com marcador.
- `from None` reduz contexto em depuração local; reversível em um token.
- Residual documentado: `__context__` segue apontando o erro cru em introspecção; plano B (levantar fora do bloco `except`) registrado, não executado.
- Consumidores: nenhum teste asserta texto exato da mensagem; `code`/`retriable`/formato preservados.

## Evidências

- `evidence/extracao-py-l135-140.txt` e `evidence/rota-descartada-dev2-003.txt`; `extraction.py` L134-139 reconfirmado no código (`f"...: {exc}"` + `from exc`).
- `errors.py` L40-41 (`message = f"{code}: {exc}..."`): ponto único de fuga; `ui/errors.py` ecoa só `.code`.
- T-2a: `_cause` em `document_processing/application/service.py` ("NUNCA `str(exc)`") e `_with_retries` em `policy_analysis/infrastructure/llm_agent.py` (só tipo + quantidade).
- `shared_kernel/contracts.py` (`confidence: float = Field(ge=0, le=1)`) e `test_metrics.py` (APOLICE_MARKER), padrão anti-vazamento a replicar.

## Confiança

alta. As três propostas convergiram na correção de duas linhas; a rodada 2 fecha os desníveis (asserção de mecanismo, decisão sobre `__context__`, escopo do fechamento) sem alterar a estratégia.

## Crítica às demais propostas

- agente-1: núcleo correto e síntese bem construída (mensagem, `from None`, escopo). Fraquezas que mantenho: cobrir `to_processing_status` e `__cause__` era apontado como lacuna, mas a prova real de supressão já era o teste de traceback formatado; e adotar `exc.__cause__ is None` sem a ressalva de que ele não distingue `from None` de ausência de causa é incompleta (o próprio agente-1 reconhece o ponto). Na rodada 2 incorporo as duas asserções, com essa ressalva explícita.
- agente-3: a mais completa em superfícies de asserção e correta em recusar reestruturar o try/except; adoto a busca por testes que assertam o texto e a asserção de mecanismo. Fraquezas que mantenho: `exc.__cause__ is None` como prova de não vazamento acopla ao mecanismo (só o traceback formatado prova a supressão); e a crítica de que minha tese sobre `__context__` ficava "sem evidência" se dissolve com as buscas do próprio agente-3 (zero `logger.exception`, zero leituras de `__context__`, único `__cause__` é teste alheio), que passo a citar como evidência compartilhada.
- Desfecho: rotas de sanitização equivalentes; a decisão se fecha por mensagem minimalista, `from None`, escopo cirúrgico e teste superconjunto (str, repr, `to_dict`, `to_processing_status`, traceback formatado, mais mecanismo), sem reestruturar o try e sem followups no change_set.
