---
protocol_version: 1
debate_id: BUG-20261004-YFN3-r1
bug_id: BUG-20261004-YFN3
role: solver
solver_id: agente-2
engine: local
round: 1
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Estratégia de correção

Mantenho a estratégia da rodada 0, com dois refinamentos de plano de teste e de fundamentação:

1. Mensagem do `ClassifiedError` só com tipo + estágio + IDs/diagnóstico permitido: código `LLM_SCHEMA_INVALID`, `field_code`, `type(exc).__name__` e `len(exc.errors())`, ex. `f"saída do LLM fora do contrato em {req.field_code}: {type(exc).__name__} com {len(exc.errors())} erro(s) de schema"`. Proibido `str(exc)`, `exc.errors()[...]["msg"|"ctx"|"input"]` e o dict completo (rota descartada em dev2-003).
2. `raise ... from exc` vira `raise ... from None`: o traceback formatado respeita `__suppress_context__` e não renderiza o `ValidationError` cru, e `to_dict()`/`to_processing_status` ecoam só a mensagem, que fica limpa. Dois tokens mudados, reversível em um token.
3. Escopo cirúrgico: apenas o `except ValidationError` de `extraction.py` (L135-140). `errors.py`, `llm_agent.py`, `document_processing_source.py` e `ui/errors.py` intactos.
4. Refinamentos da rodada 1: incorporo a verificação do agente-3 de que nenhum teste existente asserta o texto exato da mensagem (risco de regressão confirmado baixo por busca no repo) e o assert explícito sobre `to_processing_status` no teste anti-vazamento.

## Causa raiz proposta

`f"...: {exc}"` interpola `str(ValidationError)`, que ecoa o `input` validado (valor da apólice); o `from exc` mantém esse erro cru na cadeia (`__cause__`), segunda via de vazamento em traceback/log. Raiz: o `except` não aplica o padrão T-2a, contrariando a rota descartada em dev2-003. Reafirmo o ponto da rodada 0, agora com leitura direta do código: `errors.py` L41 monta `f"{code}: {exc}..."`, logo a mensagem do `ClassifiedError` é o ponto único de fuga a sanitizar; a segurança de `to_processing_status` é por herança da mensagem limpa, não porque o arquivo "já segue T-2a" por conta própria.

## Teste

Reprodução/anti-vazamento novo em `tests/modules/policy_analysis/` (padrão `APOLICE_MARKER` de `test_metrics.py`): StubAgent devolve `confidence="TEXTO-CONFIDENCIAL-APOLICE-XYZ"` (viola `Field(ge=0, le=1)` de `shared_kernel/contracts.py`) e `model_validate` rejeita. Com `pytest.raises(ClassifiedError)`: `code == "LLM_SCHEMA_INVALID"` e `retriable is True`; marcador ausente de `str(exc)`, `repr(exc)`, `exc.to_dict()["message"]`, `to_processing_status("DOC-1", exc).message` e `"".join(traceback.format_exception(exc))`; mensagem ainda contém `field_code`, o tipo `ValidationError` e a contagem de problemas. Vermelho antes do fix, verde depois. Sem assert white-box em `exc.__cause__`: o contrato é "sem vazamento", não o mecanismo de supressão da cadeia. Regressão: suíte verde, com atenção a `test_extraction_agent`, `test_metrics`, `test_errors`, `test_error_sanitization`, `test_e2e_flow.test_cenario_saida_llm_invalida_nao_vira_fato`, `tests/e2e/test_governance_journey.py` e `tests/contracts/test_errors.py`.

## Impacto sobre a spec

Nenhuma mudança de spec: implementa o já normatizado (plano-acao-dev2 T-2a; policy-analysis §12 "nenhum texto integral em logs" e §6.1 RF-09; dev2-003 §6.1 "erros sanitizados"; rota descartada em `actions.md`). Contrato público estável (`ClassifiedError`, `code`, `retriable`, `to_dict`, `to_processing_status`, UI). No fechamento: verdict de spec, change_set e, se a auditoria confirmar o mesmo padrão nas pontas internas, promover `related-to` BUG-20261004-ODCS.

## Riscos e efeitos colaterais

- Diagnóstico mais sintético (perde qual constraint falhou): mitigado por `field_code` + tipo + contagem, diagnóstico útil exigido pela rubrica.
- `from None` reduz o contexto em depuração local; investigação via teste determinístico com marcador; reversível em um token.
- Consumidores: nenhum teste asserta texto exato da mensagem (verificado pelo agente-3); code/retriable/formato preservados.
- Pontas internas que ainda ecoam `str(exc)` (`llm_agent.py`, `document_processing_source.py`) seguem fora de escopo (issue própria), para preservar a menor mudança coerente.

## Evidências

- `evidence/extracao-py-l135-140.txt` e `evidence/rota-descartada-dev2-003.txt`; `extraction.py` L135-140 reconfirmado no código desta rodada (`f"...: {exc}"` + `from exc`).
- `errors.py` L41 (`to_processing_status` interpola `{exc}` da mensagem): ponto único de fuga.
- Padrão T-2a: `_cause` em `document_processing/application/service.py` ("NUNCA `str(exc)`") e `_with_retries` em `policy_analysis/infrastructure/llm_agent.py` (só tipo + quantidade).
- `shared_kernel/contracts.py` (`confidence: float = Field(ge=0, le=1)`) e `test_metrics.py` (APOLICE_MARKER), padrão anti-vazamento a replicar.

## Confiança

alta. As três propostas convergem para a mesma correção de duas linhas; a rodada 1 refina o plano de teste e corrige premissas descritivas, sem mudar a estratégia.

## Crítica às demais propostas

- agente-1: acerta o núcleo (mensagem tipo + campo + contagem, `from None`, escopo de um `except`) e a recusa da alternativa "manter `from exc` para diagnóstico". Fraquezas: afirma que `errors.py`, `llm_agent.py` e `ui/errors.py` "já seguem T-2a (só tipo/código)", o que é impreciso, pois `to_processing_status` ecoa `{exc}` e só fica seguro por herança da mensagem sanitizada; o plano de teste não cobre `repr(exc)` nem asserta `to_processing_status` de forma explícita (só cita na regressão); não trata do `__context__` residual nem do trade-off com a variante "fora do bloco".
- agente-3: a mais completa em superfícies de asserção (`repr`, `to_processing_status(...).message`, ausência de marcador no traceback) e a que melhor desrisca (busca confirmando que nenhum teste asserta o texto exato; único uso de `__cause__` no repo). Fraquezas: o assert `exc.__cause__ is None` é white-box e acopla o teste ao mecanismo de `from None`; a variante "levantar fora do bloco `except`" para zerar `__context__` é mudança maior que o necessário, pois nenhum caminho de log do projeto renderiza `__context__` quando `__suppress_context__` está setado; guardá-la como plano B é aceitável, executá-la não.
- agente-1 e agente-3 coincidem comigo no que a rubrica decide (mensagem sanitizada tipo + campo + contagem, `from None`, escopo cirúrgico, teste anti-vazamento com marcador); a separação está na qualidade do teste e da fundamentação, e mantenho minha proposta por combinar o ponto único de fuga (mensagem herda a segurança dos consumidores) com a asserção mais ampla e menos acoplada.
