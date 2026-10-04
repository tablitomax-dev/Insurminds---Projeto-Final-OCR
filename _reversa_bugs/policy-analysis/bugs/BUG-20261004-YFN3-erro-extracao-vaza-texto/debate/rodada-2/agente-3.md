---
protocol_version: 1
debate_id: BUG-20261004-YFN3-r2
bug_id: BUG-20261004-YFN3
role: solver
solver_id: agente-3
engine: local
round: 2
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Estratégia de correção
Proposta final, já desempatada pelo debate (as 3 rotas convergiram; mudo só o ponto que agente-1 e agente-2 me contestaram com razão):
1. Somente o `except ValidationError` de `_build_fact` (`application/extraction.py` L134-139). Mensagem do `ClassifiedError` passa a ter só tipo + estágio + IDs/contagem (T-2a): `f"saída do LLM fora do contrato em {req.field_code}: {type(exc).__name__}, {len(exc.errors())} problema(s) de schema"`. Ficam `LLM_SCHEMA_INVALID`, `field_code`, `ValidationError`, contagem; sai `{exc}`, `str/repr`, `errors()[...]["msg"|"ctx"|"input"]` e todo eco de valor (rota descartada em dev2-003).
2. `raise ... from exc` vira `raise ... from None`: `__suppress_context__` impede a renderização da cadeia crua em traceback/log; reversível em um token.
3. Decisão final sobre `from exc`: RETIRO da proposta executada a variante "levantar fora do bloco `except`" que eu defendia para zerar `__context__`. Agente-1 e agente-2 acertam: o residual de `__context__` só é alcançável por introspecção (varredura do repo reconfirmada hoje: zero `__context__`, zero `logger.exception`, único `__cause__` é `tests/integration/test_pipeline_offline.py` L92, alheio), e reestruturar o try viola "menor mudança coerente" e "menor risco de regressão", que a rubrica põe antes da limpeza absoluta. Guardada como plano B documentado, não executada.
4. Escopo cirúrgico: duas linhas de um `except`. `errors.py`, `llm_agent.py`, `document_processing_source.py`, `ui/errors.py`, contratos e UI intactos.

## Causa raiz proposta
`f"...: {exc}"` interpola `str(ValidationError)` do Pydantic, que ecoa o `input` validado (valor da apólice); o `from exc` mantém esse erro cru vivo em `__cause__`, segunda via de vazamento em traceback/log. Raiz: o `except` não aplica o padrão T-2a, descumprindo o que dev2-003 já normatizou. É falha de higiene de dado em mensagem de erro, não de contrato: RF-09 continua cumprida (nada vira fato).

## Teste
Reprodução + anti-vazamento novos em `tests/modules/policy_analysis/test_extraction_agent.py` (ao lado de `test_saida_fora_do_schema_nunca_vira_fato`, L125, que já cobre o caminho com `confidence: 99`), padrão `APOLICE_MARKER` de `test_metrics.py` L27 e do estilo T-2a de `test_service.py` L245 ("só o tipo, nunca o texto"): StubAgent devolve `confidence="TEXTO-CONFIDENCIAL-APOLICE-XYZ"` (viola `Field(ge=0, le=1)` de `shared_kernel/contracts.py`) e o marcador vira `input` do `ValidationError`. Com `pytest.raises(ClassifiedError)`:
- `code == "LLM_SCHEMA_INVALID"`, `retriable is True`; mensagem traz `field_code`, `type(exc).__name__` e a contagem;
- marcador ausente de `str(exc)`, `repr(exc)`, `exc.to_dict()["message"]`, `to_processing_status("DOC-1", exc).message` (consumidor real de `errors.py` L41) e `"".join(traceback.format_exception(exc))`;
- guarda mecanística única e deliberada: `exc.__cause__ is None and exc.__suppress_context__`. Respondo à crítica de agente-2 (white-box): ela é policy assert, não acidente de implementação; documenta a decisão `from None` e faz o teste falhar se alguém reintroduzir `from exc` mesmo que alguma superfície de renderização mude. O traceback formatado continua sendo a prova preta de não vazamento.
Vermelho antes do fix, verde depois. Regressão: `tests/modules/policy_analysis`, `tests/contracts/test_errors.py`, `tests/contracts/test_processing_status.py`, `tests/ui/test_error_sanitization.py`, `tests/e2e/test_governance_journey.py`, `tests/modules/document_processing`, `tests/integration/test_pipeline_offline.py`. Reconfirmado por busca hoje: nenhum teste asserta o texto exato da mensagem de produção (o stub de `test_governance_journey.py` L113-117 monta texto parecido, mas as asserções L187-188 usam só `.code`).

## Impacto sobre a spec
Nenhuma mudança de spec: implementa o já normatizado (plano-acao-dev2 T-2a; policy-analysis §12 "nenhum texto integral em logs" e §6.1 RF-09; dev2-003 §6.1 "erros sanitizados"; rota descartada em `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md`). `ClassifiedError`, `code`, `retriable`, `to_dict()` e `to_processing_status` com contrato estável. `resolution_kind`: fix de código, sem addenda; `change_risk` baixo.

## Riscos e efeitos colaterais
- Diagnóstico mais sintético (perde a constraint exata): compensado por campo + tipo + contagem, exigido pela rubrica; reprodução local via teste com marcador.
- `from None` reduz o contexto em depuração local; investigar pelo teste determinístico, não pelo log.
- Residual consciente: `__context__` ainda aponta para o `ValidationError` cru em introspecção (preenchimento do Python dentro do `except`); sem superfície de renderização no repo, coberto pelo plano B se a auditoria futura exigir.
- Texto da mensagem muda: consumidores usam `code`/`retriable`/`to_dict()`/`to_processing_status` (todos cobertos pelo teste).
- Pontas internas com `str(exc)` (`llm_agent.py` L267, `document_processing_source.py` L30) seguem fora do escopo, para issue própria; ampliá-las aqui inflaria o change_set.

## Evidências
- `evidence/extracao-py-l135-140.txt` e `evidence/rota-descartada-dev2-003.txt`; `extraction.py` L134-139 reconfirmado no código desta rodada (`{exc}` + `from exc`).
- `errors.py` L41 (`message = f"{code}: {exc} (reexecutável={retriable})"`): ponto único de fuga, seguro por herança da mensagem limpa.
- Padrão T-2a: `_cause` (`document_processing/application/service.py` L285, "NUNCA `str(exc)`") e `_with_retries` (`policy_analysis/infrastructure/llm_agent.py`, só tipo + contagem).
- Testes: `test_metrics.py` L27/L265-278 (APOLICE_MARKER), `test_service.py` L195/L245 (só tipo, nunca texto), `test_extraction_agent.py` L125-133 (caminho já coberto).
- Buscas no repo (2026-10-04): zero `__context__`/`logger.exception`; único `__cause__` em `test_pipeline_offline.py` L92; nenhum teste asserta o texto exato da mensagem.

## Confiança
alta: causa, canais de vazamento, consumidores e padrão canônico verificados no código hoje; as 3 propostas convergiram e a rodada 2 apenas fechou a aresta do `__context__` e da guarda de teste.

## Crítica às demais propostas
- agente-1: núcleo correto (mensagem tipo + campo + contagem, `from None`, escopo de um `except`) e boa recusa da alternativa "manter `from exc`". Fraquezas: (a) inclui no teste `exc.__cause__ is None` e ao mesmo tempo afirma que essa asserção "não distingue `from None` de sem exceção ativa", inconsistência que só se resolve nomeando a asserção como guarda deliberada (faço isso acima); (b) a nota de que o residual de `__context__` fica "coberto pela variante de rodada 2 se necessário" é vaga, sem dizer se executa ou arquiva; (c) alega que `errors.py` "repete só a mensagem já sanitizada" sem frisar que a segurança é por herança do fix, não pré-existente (ponto que agente-2 captou bem).
- agente-2: a mais precisa na fundamentação do ponto único de fuga (`errors.py` L41 ecoa `{exc}`; consumidores ficam seguros por herança) e correta em exigir busca por testes que assertem o texto. Fraquezas: (a) recusa qualquer assert de mecanismo ("o contrato é não vazamento"), o que deixa a decisão T-2a de supressão da cadeia sem guarda explícita e permite regressão silenciosa para `from exc` se as superfícies de renderização mudarem; uma asserção barata resolve; (b) promover `related-to` BUG-20261004-ODCS no fechamento continua ruído de processo fora do escopo do fix (rubrica: menor mudança coerente); (c) não menciona o residual de `__context__` como risco consciente, só a reversibilidade do `from None`.
- Desempate final: mensagem minimalista comum aos 3 + `from None` (agente-1 e agente-2 me convenceram a arquivar a reestruturação do try) + bateria de teste superconjunto (str/repr/to_dict/to_processing_status/traceback) com a guarda mecanística nomeada como política. A disputa real da rodada 1 era profundidade de teste e limpeza da cadeia; está fechada.
