---
protocol_version: 1
debate_id: BUG-20261004-YFN3-r0
bug_id: BUG-20261004-YFN3
role: solver
solver_id: agente-1
engine: local
round: 0
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Estratégia de correção
1. Em `application/extraction.py` (135-140), trocar `{exc}` por só tipo e contagem:
`f"saída do LLM fora do contrato em {req.field_code}: {len(exc.errors())} problema(s) de schema ({type(exc).__name__})"`. Fica: código `LLM_SCHEMA_INVALID`, `field_code`, tipo (`ValidationError`) e contagem de problemas; sai `str(exc)`, `exc.errors()[...]["msg"]` e todo eco de valor (o input do Pydantic).
2. Trocar `from exc` por `from None`: a cadeia `__cause__` preserva o `ValidationError` cru (que ecoa o input) e qualquer `logger.exception`/traceback de exceção não tratada imprime a cadeia, vazando o texto mesmo com a mensagem limpa. `from None` suprime a cadeia; o tipo da causa continua registrado na própria mensagem.
3. Escopo cirúrgico: só este `except`. `errors.py`, `llm_agent.py` e `ui/errors.py` já seguem T-2a (só tipo/código); não alterar. Duas linhas mudadas, reversão trivial.

Alternativa rejeitada: manter `from exc` "para diagnóstico". O rastro útil (tipo + campo + contagem) já está na mensagem; a cadeia reintroduz o vetor que T-2a proíbe em log.

## Causa raiz proposta
`str(exc)` do Pydantic interpolado na mensagem do `ClassifiedError`: o `ValidationError` do `model_validate` ecoa o `input` de cada campo rejeitado, e aí mora o valor extraído da apólice. Soma-se o `from exc`, que mantém esse `ValidationError` cru acessível via cadeia de exceções. O `except` não aplica o padrão T-2a (a decisão dev2-003 descartou exatamente `str(exc)`/`exc.errors()[...]["msg"]`): derrapagem de implementação, não de spec.

## Teste
Reprodução/anti-vazamento (novo em `tests/modules/policy_analysis/`, reusando os fakes do `conftest.py` e o padrão de `test_metrics.py`): StubAgent devolve fato com `confidence="TEXTO-CONFIDENCIAL-APOLICE-XYZ"` (tipo inválido; o Pydantic rejeita e o marcador vira `input` do erro). Com `pytest.raises(ClassifiedError)`:
- `code == "LLM_SCHEMA_INVALID"` e `retriable is True` (comportamento preservado);
- marcador ausente de `str(exc)`, `exc.to_dict()["message"]` e do traceback formatado (`traceback.format_exception(exc)`, que cobre a cadeia de causa);
- mensagem contém `field_code`, o tipo `ValidationError` e a contagem de problemas.

Regressão: suíte verde (`test_extraction_agent`, `test_quality`, `test_metrics`, `test_errors`, `test_error_sanitization`, e2e) e `to_processing_status` sem o marcador.

## Impacto sobre a spec
Cumpre T-2a (tipo + campo/IDs + contagem, nunca valor), RF-09 do §6.1 e o §12 ("nenhum texto integral em logs") sem mudança de spec. Contrato público estável: `ClassifiedError`, `code`, `retriable` e o shape de `to_dict()` inalterados; nada a ajustar em `policy-analysis.md`.

## Riscos e efeitos colaterais
- Diagnóstico mais pobre que o traceback cru: aceito pela higiene T-2a, mitigado por tipo + campo + contagem e pelo teste de reprodução.
- `from None` esconde a causa em depuração local; para investigar, reproduzir via teste com marcador (caminho determinístico), não via log.
- Consumidores do texto da mensagem: nenhum identificado (`to_processing_status` e a UI usam código/tipo); não estender às pontas internas (hoje seguras) preserva a menor mudança coerente.

## Evidências
- `src/modules/policy_analysis/application/extraction.py` 135-140 (`f"...: {exc}"` + `from exc`) e `evidence/rota-descartada-dev2-003.txt` (rota descartada: `str(exc)`/`exc.errors()[...]["msg"]`).
- Padrão T-2a: `_cause` em `document_processing/application/service.py` (só `type(exc).__name__`) e `_with_retries` em `policy_analysis/infrastructure/llm_agent.py` (tipo + contagem de tentativas).
- `str(ValidationError)` imprime o input; `test_metrics.py` (APOLICE_MARKER, 268-277) é o padrão anti-vazamento a replicar; `src/ui/errors.py` mostra que o vazamento segue por `str(exc)`, `to_dict()` e `to_processing_status`.

## Confiança
alta. Causa, padrão canônico do projeto e superfícies de vazamento estão confirmados no código e nas evidências congeladas.
