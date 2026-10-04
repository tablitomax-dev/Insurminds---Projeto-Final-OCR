---
protocol_version: 1
debate_id: BUG-20261004-YFN3-r0
bug_id: BUG-20261004-YFN3
role: solver
solver_id: agente-3
engine: local
round: 0
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Estratégia de correção
Correção cirúrgica só no `except ValidationError` de `_build_fact` (`application/extraction.py` L135-140):
1. Mensagem do `ClassifiedError` fica com código (`LLM_SCHEMA_INVALID`), `field_code`, tipo da exceção (`type(exc).__name__`) e contagem de problemas (`len(exc.errors())`); sai tudo que ecoa valor (`str(exc)`, `errors()[...]["msg"|"ctx"|"input"|"url"]`). Ex.: `f"saída do LLM fora do contrato em {req.field_code}: {type(exc).__name__}, {len(exc.errors())} problema(s) de schema"`.
2. Encadeamento: `raise ... from exc` vira `raise ... from None`. O `ValidationError` cru carrega o input em `str`/`repr`/`errors()` e como `__cause__` reabre o vazamento em traceback/log; nenhum consumidor depende de `__cause__` aqui (único uso do repo é em `tests/integration/test_pipeline_offline.py`).
3. Escopo contido: as pontas que ecoam `str(exc)` (`llm_agent.py` L267, `document_processing_source.py`) ficam para follow-up (internas, não exibidas); o fix já torna seguros `to_dict()` e `to_processing_status`, que repetem só a mensagem sanitizada. `_cause` e `EVIDENCE_UNKNOWN` (só IDs) ficam intactos.

## Causa raiz proposta
Mensagem montada com `str(exc)` do Pydantic, que por contrato ecoa o input da validação (valor da apólice), violando T-2a; camada residual: `from exc` preserva o `ValidationError` cru na cadeia de exceções, canal de vazamento via tracebacks/logs.
É falha de higiene de dado em mensagem de erro, não de contrato nem de lógica de extração (RF-09 segue cumprida: nada vira fato).

## Teste
Reprodução/anti-vazamento em `tests/modules/policy_analysis/test_extraction_agent.py` (padrão `APOLICE_MARKER` de `test_metrics.py`): StubAgent devolve fato de "franquia" com `confidence="TEXTO-CONFIDENCIAL-APOLICE-XYZ"`; o Pydantic rejeita com `ValidationError` cujo `input` ecoa o marcador.
Assertivas: `code == "LLM_SCHEMA_INVALID"` e `retriable is True`; marcador ausente de `str(exc)`, `repr(exc)`, `to_dict()["message"]`, `to_processing_status("DOC-1", exc).message` e `"".join(traceback.format_exception(exc))`; `exc.__cause__ is None`; mensagem ainda traz `field_code` e a contagem. Vermelho antes do fix, verde depois.
Regressão: `tests/modules/policy_analysis` (inclusive `test_saida_fora_do_schema_nunca_vira_fato`, que asserta só `code`), `tests/e2e/test_governance_journey.py`, `tests/contracts/test_errors.py`, `tests/ui/test_error_sanitization.py` e `tests/modules/document_processing`; nenhum teste existente asserta o texto exato da mensagem (verificado por busca no repo).

## Impacto sobre a spec
Nenhuma mudança de spec: o fix apenas passa a cumprir o já normatizado (policy-analysis §12 e §6.1 RF-09, plano-acao-dev2 T-2a, addenda dev2-003 §6.1, rota descartada em dev2-003/actions.md).
`change_risk` baixo reafirmado (mensagem de erro; sem contrato, dados, UI ou migração); `resolution_kind`: fix de código, sem addenda.

## Riscos e efeitos colaterais
- Diagnóstico mais sintético (perde qual constraint falhou), compensado por campo + contagem + tipo; reprodução local segue possível com o payload do agente.
- `from None` zera a cadeia visível; se a rodada 2 exigir eliminar também `__context__` em introspecção, a variante é levantar o erro fora do bloco `except` (ainda pequena e reversível).
- Texto da mensagem muda (consumidores usam `code`/`retriable`/`to_dict()`, verificados, risco baixo); pontas internas que ainda ecoam `str(exc)` seguem fora de escopo e pedem issue própria.

## Evidências
- `evidence/extracao-py-l135-140.txt` e `evidence/rota-descartada-dev2-003.txt`.
- `_cause` (`src/modules/document_processing/application/service.py` L282-289): "NUNCA `str(exc)`"; `_with_retries` (`src/modules/policy_analysis/infrastructure/llm_agent.py` L65-71): só tipo + quantidade.
- `src/shared_kernel/contracts.py` L140 (`confidence: float = Field(ge=0, le=1)`), campo que ecoa o valor; `tests/modules/policy_analysis/test_metrics.py` (L26-27, L265-278), padrão do marcador anti-vazamento.
- `src/ui/errors.py` (`sanitize_error_message`): a UI ecoa só `.code` do ClassifiedError (consumidor estável).

## Confiança
alta (causa e canal de vazamento observáveis no código; correção de poucas linhas, coberta por teste anti-vazamento específico e por regressão já existente).
