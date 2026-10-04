# Debate — BUG-20261004-YFN3 (setup congelado)

```yaml
debate_id: BUG-20261004-YFN3
bug_id: BUG-20261004-YFN3
mode: repair            # causa confirmada; disputa de estratégia de correção
N: 3                    # solvers independentes
R: 2                    # rodadas/épocas, SEM early stopping
external_harness: none  # só agentes locais (aceite do usuário em 2026-10-04)
status: setup
```

## Problema P

**Defeito.** Quando o LLM devolve saída fora do contrato, `src/modules/policy_analysis/application/extraction.py`
(linhas 135-140), no `except ValidationError` do `ExtractedFact.model_validate`, monta a mensagem
do `ClassifiedError` com `f"saída do LLM fora do contrato em {req.field_code}: {exc}"`. `str(exc)`
do Pydantic ecoa o `input` da validação, que é o valor extraído da apólice: texto de apólice vaza
pela mensagem de erro/logs (viola a regra T-2a do plano de ação Dev 2 e a decisão registrada na
feature dev2-003, que descartou manter `str(exc)`/`exc.errors()[...]["msg"]` porque ambos podem
conter o input).

**Evidências.**
- `../evidence/extracao-py-l135-140.txt` (trecho do código)
- `../evidence/rota-descartada-dev2-003.txt` (decisão registrada que o código não cumpre)
- Padrão canônico T-2a do projeto: `_cause` em `src/modules/document_processing/application/service.py`
  ("NUNCA `str(exc)`... só o tipo da exceção") e `_retry` em
  `src/modules/policy_analysis/infrastructure/llm_agent.py` (só tipo + quantidade).

**Mecanismo de reprodução (planejado).** StubAgent devolve fato com `confidence` = marcador
"TEXTO-CONFIDENCIAL-APOLICE-XYZ"; o Pydantic rejeita com `ValidationError` cujo `input` ecoa o
marcador; `str(ClassifiedError)` hoje contém o marcador. Teste anti-vazamento deve provar que
depois da correção o marcador não está em `str(exc)` do erro classificado.

**Spec efetiva.**
- `_reversa_sdd/sdd/policy-analysis.md` §12: "nenhum texto integral em logs"; §6.1 RF-09: saída
  fora do schema nunca vira fato e é registrada como falha classificada.
- `_reversa_sdd/learning/plano-acao-dev2.md` (T-2a): "nunca `ValidationError` crua; tipo +
  estágio + IDs; teste anti-vazamento".
- `_reversa_sdd/addenda/dev2-003-p0-analise-experiencia.md` §6.1: "erros sanitizados".
- `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md`: alternativa descartada =
  manter `str(exc)`/`exc.errors()[...]["msg"]`.

**Restrições (Agent Notes do bug).** Motivo/erro nunca carrega valor, só tipo/contagem/IDs.
Autorização humana de 2026-10-04: código do Dev 2 (`policy_analysis`) pode ser alterado.
`change_risk` avaliado pelo fix: baixo (mensagem de erro; sem contrato, dados, UI, migração).

## Rubrica congelada (modo repair)

A proposta será avaliada por estes critérios, nesta ordem:

1. **Elimina a causa raiz**: o input do Pydantic (e qualquer eco de valor) não chega a
   mensagem de erro, log ou `to_dict()`.
2. **Menor mudança coerente**: escopo cirúrgico; nada de refatoração ampla junto da correção.
3. **Menor risco de regressão**: não quebra `ClassifiedError`/`retriable`/consumidores
   (`to_processing_status`, UI `sanitize_error_message`, fakes e testes existentes).
4. **Reversibilidade**: mudança simples de reverter.
5. **Aderência à spec efetiva e aos Agent Notes**: padrão T-2a do projeto (tipo + estágio +
  IDs), diagnóstico ainda útil (quantidade/campo), teste anti-vazamento específico.

Decisão esperada do debate: estratégia vencedora de sanitização (o que vai e o que fica na
mensagem; o que fazer com o encadeamento `from exc`) + plano de teste (reprodução e regressão).