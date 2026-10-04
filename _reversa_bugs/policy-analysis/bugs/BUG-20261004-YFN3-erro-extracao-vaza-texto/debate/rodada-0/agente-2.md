---
protocol_version: 1
debate_id: BUG-20261004-YFN3-r0
bug_id: BUG-20261004-YFN3
role: solver
solver_id: agente-2
engine: local
round: 0
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Estratégia de correção

1. Mensagem do `ClassifiedError` passa a conter só: código (`LLM_SCHEMA_INVALID`), `field_code`, tipo da exceção (`type(exc).__name__`) e contagem de problemas de schema (`len(exc.errors())`), ex.:
   `f"saída do LLM fora do contrato em {req.field_code}: {type(exc).__name__} com {len(exc.errors())} erro(s) de schema"`.
2. Proibido na mensagem: `str(exc)`, `exc.errors()[...]["msg"]`, `"input"`/`"ctx"` e o dict de erros completo (rota descartada em dev2-003, todos podem ecoar o valor da apólice).
3. Encadeamento: trocar `raise ... from exc` por `raise ... from None`, suprimindo a renderização da cadeia em traceback/log (o `ValidationError` crudo ecoa o input via `__cause__`). Rejeito manter `from exc` (traceback logado re-ecoaria o valor) e rejeito reestruturar o try para levantar fora do bloco (mudança maior que o necessário: o `__context__` residual com `__suppress_context__` não é renderizado por caminho de log do projeto).
4. Escopo cirúrgico: só o `except ValidationError` de `extraction.py` (linhas 135-140). Não mexer em `errors.py`, `llm_agent.py` nem `document_processing_source.py`; `to_processing_status` interpola o `{exc}` do `ClassifiedError` e fica seguro por herança da mensagem sanitizada.

## Causa raiz proposta

`f"...: {exc}"` chama `str(ValidationError)` do Pydantic, que formata cada erro do schema incluindo o `input` validado (valor extraído da apólice); o `from exc` mantém esse erro vivo na cadeia de exceções, que também é logada. Duas vias de vazamento: mensagem direta e cadeia. Causa de processo: o código não cumpre a sanitização decidida em dev2-003 nem o padrão T-2a (tipo + estágio + IDs).

## Teste

- Reprodução/anti-vazamento (novo em `tests/modules/policy_analysis/`, padrão `APOLICE_MARKER` de `test_metrics.py`): StubAgent devolve fato com `confidence` = marcador "TEXTO-CONFIDENCIAL-APOLICE-XYZ" (não numérico) para `ExtractedFact.model_validate` rejeitar. Assertivas: `ClassifiedError` com `code == "LLM_SCHEMA_INVALID"` e `retriable is True`; marcador ausente de `str(exc)`, `repr(exc)`, `exc.to_dict()` e de `traceback.format_exception(exc)` (prova que a cadeia suprimida não vaza em log).
- Regressão: suíte verde, em especial `test_e2e_flow.test_cenario_saida_llm_invalida_nao_vira_fato`, `tests/e2e/test_governance_journey.py`, `tests/ui/test_error_sanitization.py` e `tests/contracts/test_errors.py`. Contratos intactos (`ClassifiedError`, `to_dict`, `to_processing_status`, UI `sanitize_error_message`).

## Impacto sobre a spec

Nenhuma mudança de spec: a correção implementa o já normatizado (plano-acao-dev2 T-2a; policy-analysis.md §12 "nenhum texto integral em logs" e §6.1 RF-09; dev2-003 §6.1 "erros sanitizados"). No fechamento: preencher causa raiz, verdict de spec e change_set; promover `related-to` BUG-20261004-ODCS se a auditoria confirmar o mesmo padrão.

## Riscos e efeitos colaterais

- Debug menos detalhado (sem o campo problemático): mitigado por `field_code` + tipo + contagem, diagnóstico útil exigido pela rubrica.
- `from None` reduz contexto de depuração local; reversível em um token.
- Nenhum consumidor quebra: muda o conteúdo da mensagem, não o formato; code/retriable preservados.
- Pontas internas com `str(exc)` (fora do caminho exibido) ficam para issue própria (possível BUG-20261004-ODCS), para não ampliar o change_set.

## Evidências

- `evidence/extracao-py-l135-140.txt` e `evidence/rota-descartada-dev2-003.txt`.
- Padrão T-2a: `_cause` em `document_processing/application/service.py` ("NUNCA `str(exc)`... só o tipo da exceção") e `_with_retries` em `policy_analysis/infrastructure/llm_agent.py` (só tipo + quantidade de tentativas).
- `errors.py::to_processing_status` ecoa `{exc}` do `ClassifiedError`: a mensagem é o ponto único de fuga a sanitizar.

## Confiança

alta, a causa e a rota correta estão registradas na própria feature dev2-003 e o padrão T-2a já é canônico no projeto.
