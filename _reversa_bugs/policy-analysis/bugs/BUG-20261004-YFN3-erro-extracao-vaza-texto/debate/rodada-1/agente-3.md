---
protocol_version: 1
debate_id: BUG-20261004-YFN3-r1
bug_id: BUG-20261004-YFN3
role: solver
solver_id: agente-3
engine: local
round: 1
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Estratégia de correção
Mantenho a proposta da rodada 0 (houve convergência entre os 3 solvers; não há motivo para mudar de rota), com dois refinamentos de precisão:
1. Só o `except ValidationError` de `_build_fact` (`application/extraction.py` L135-139): a mensagem do `ClassifiedError` passa a conter apenas código (`LLM_SCHEMA_INVALID`), `field_code`, `type(exc).__name__` e `len(exc.errors())`, ex.: `f"saída do LLM fora do contrato em {req.field_code}: {type(exc).__name__}, {len(exc.errors())} problema(s) de schema"`. Sai `{exc}` e tudo que ecoa valor (rota descartada em dev2-003).
2. `raise ... from exc` vira `raise ... from None`, suprimindo a cadeia renderizável (o `ValidationError` cru ecoa o input em `str`/`repr`/`errors()`).
3. Escopo cirúrgico confirmado: `_cause`, `EVIDENCE_UNKNOWN`, `errors.py`, `ui/errors.py`, `llm_agent.py` e `document_processing_source.py` ficam intactos; reversão em duas linhas.

## Causa raiz proposta
`f"...: {exc}"` interpola `str(ValidationError)` do Pydantic, que ecoa o `input` da validação (valor extraído da apólice), e `from exc` mantém esse erro cru acessível na cadeia de exceções. O `except` não aplica o padrão T-2a (tipo + estágio + IDs, nunca valor), descumprindo o que dev2-003 já normatizou. É falha de higiene de dado em mensagem de erro, não de contrato: RF-09 continua cumprida (nada vira fato).

## Teste
Anti-vazamento novo em `tests/modules/policy_analysis/` (padrão `APOLICE_MARKER` de `test_metrics.py`): StubAgent devolve fato com `confidence="TEXTO-CONFIDENCIAL-APOLICE-XYZ"`; o Pydantic rejeita com o marcador como `input`. Assertivas: `code == "LLM_SCHEMA_INVALID"`, `retriable is True`; marcador ausente de `str(exc)`, `repr(exc)`, `to_dict()["message"]`, `to_processing_status("DOC-1", exc).message` (o consumidor real de `errors.py` L41) e `"".join(traceback.format_exception(exc))`; `exc.__cause__ is None`; mensagem ainda traz `field_code` e a contagem. Vermelho antes, verde depois.
Regressão: `tests/modules/policy_analysis` (inclui `test_saida_fora_do_schema_nunca_vira_fato`), `tests/contracts/test_errors.py`, `tests/ui/test_error_sanitization.py`, `tests/e2e/test_governance_journey.py`, `tests/modules/document_processing`. Verifiquei por busca: nenhum teste asserta o texto exato da mensagem.

## Impacto sobre a spec
Nenhuma mudança de spec: o fix implementa o já normatizado (policy-analysis §12 e §6.1 RF-09, plano-acao-dev2 T-2a, dev2-003 §6.1, rota descartada em dev2-003/actions.md). `ClassifiedError`, `code`, `retriable` e o shape de `to_dict()` inalterados. `change_risk` baixo reafirmado; `resolution_kind`: fix de código, sem addenda.

## Riscos e efeitos colaterais
- Diagnóstico mais sintético (perde a constraint exata): compensado por campo + tipo + contagem, exigido pela rubrica; reprodução local segue via teste com marcador.
- Residual consciente: `__context__` ainda referencia o `ValidationError` (Python o preenche dentro do `except`), mas nada o renderiza quando `__suppress_context__` está ativo. Mantive `from None` em vez de reestruturar o try porque a varredura do repo mostra zero usos de `__context__`/`__cause__` (o único é `tests/integration/test_pipeline_offline.py` L92, alheio) e zero `logger.exception`; a variante de levantar fora do bloco violaria "menor mudança" sem ganho observável. Se a rodada 2 exigir zerar também `__context__`, a variante é pequena e reversível.
- Texto da mensagem muda: consumidores usam `code`/`retriable`/`to_dict()`/`to_processing_status` (todos cobertos pelo teste), risco baixo.
- Pontas internas com `str(exc)` (`llm_agent.py` L267, `document_processing_source.py` L30) ficam para issue própria: são mensagens de erro, não seguras; ampliá-las aqui inflaria o change_set.

## Evidências
- `evidence/extracao-py-l135-140.txt` e `evidence/rota-descartada-dev2-003.txt`.
- Padrão T-2a: `_cause` (`document_processing/application/service.py` L282-289, "NUNCA `str(exc)`") e `_with_retries` (`policy_analysis/infrastructure/llm_agent.py`, só tipo + quantidade).
- `errors.py` L41 (`message = f"{code}: {exc}..."`) e `ui/errors.py` (`ClassifiedError` ecoa só `.code`): superfícies de consumo verificadas.
- Buscas no repo (2026-10-04): nenhum `__context__`, nenhum `logger.exception`, único `__cause__` é o teste citado; nenhum teste asserta o texto da mensagem.

## Confiança
alta: causa, canais de vazamento e consumidores verificados no código; as 3 propostas convergem, restando só detalhe de teste e o residual de `__context__`, ambos documentados.

## Crítica às demais propostas
- agente-1: núcleo correto e alternativa "manter from exc" bem rejeitada. Fraquezas: (a) não asserta `repr(exc)` nem `exc.__cause__ is None`, prova fraca de que a cadeia realmente sumiu; (b) não testa `to_processing_status`, que é o consumidor que interpola `{exc}` (`errors.py` L41); (c) contradição nas evidências: diz que `ui/errors.py` "mostra que o vazamento segue por str(exc), to_dict() e to_processing_status" e no item 3 chama o mesmo arquivo de "já seguro" (a leitura correta: `ui/errors.py` só ecoa `.code`, quem interpola é `errors.py`); (d) chama `llm_agent.py`/`document_processing_source.py` de "hoje seguras", mas ambas interpolam `str(exc)` em mensagens.
- agente-2: a mais forte, concordo com a rejeição de reestruturar o try e com a higienização da mensagem. Fraquezas: (a) a alegação de que `__context__` "não é renderizado por caminho de log do projeto" fica sem evidência (eu a verifiquei: zero `logger.exception`/`__context__` no repo); (b) o teste cobre `to_dict()` mas não `to_processing_status` nem `repr(exc)`; (c) propor promover BUG-20261004-ODCS no fechamento é ruído de processo, fora do escopo do fix (rubrica: menor mudança coerente).
- Conclusão: mantenho minha proposta por ter o teste superconjunto (str/repr/to_dict/to_processing_status/traceback/__cause__) e o único par de linhas alterado; as três rotas de sanitização são equivalentes, então a decisão se desempata pelo plano de teste e pela disciplina de escopo.
