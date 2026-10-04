---
schema_version: 1
id: BUG-20261004-KD2H
display_number: 3
title: Notas do D2-P0-2 afirmam validate_fact na correção humana, mas review.py não chama
status: resolved
phase: testing
severity: low
priority: P2
created: 2026-10-04
updated: 2026-10-04
express: true

origin:
  type: inspection
  external_ref: {provider: reversa-debugger-debate, id: BUG-20261004-ODCS}

area: policy-analysis
module: policy_analysis
feature: revisao-humana
labels: [d2-p0-2, divergencia-codigo-spec, registro-de-execucao]

visibility: normal
security_suspected: false

reproduction:
  classification: deterministic
  rate: "1/1"
  suspected_triggers: []

blocking: []
relationships:
  - bug: BUG-20261004-ODCS
    type: related-to
    state: proposed
    evidence: []

traceability:
  specs:
    - "_reversa_forward/dev2-003-p0-analise-experiencia/actions.md#d2-p0-2"
    - "_reversa_sdd/learning/plano-acao-dev2.md#d2-p0-3"
  affected_code:
    - "src/modules/policy_analysis/application/review.py"
  root_cause:
    state: confirmed
    hypothesis: "A implementação do D2-P0-2 normalizou o valor corrigido mas nunca acoplou as regras de campo (validate_fact) ao ramo CORRIGIDO de record_decision, embora o registro de execução declarasse a guarda; o `ContractValidationError` descrito na nota nunca existiu."
    causal_path:
      - "D2-P0-2 registra execução com guarda inexistente (actions.md linha 135)"
      - "application/review.py::record_decision (ramo CORRIGIDO) chama só raw_value_from_text/normalize_value"
      - "valor que viola regras (negativo, moeda desconhecida, fora do enum) persiste como FOUND"
      - "comparação/export passam a usar o valor revisado sem última checagem de regra"
    evidence:
      - {ref: "evidence/reproduction.md", observation: "CORRIGIDO persiste negativo com moeda XYZ como FOUND"}
      - {ref: "evidence/repro_kd2h.py", observation: "script de reprodução funcional via fachada"}
      - {ref: "evidence/nota-actions-d2-p0-2.txt", observation: "nota da spec afirma guarda que o código não tem"}
    code_refs:
      - {file: "src/modules/policy_analysis/application/review.py", symbol: "ReviewService.record_decision", commit: "1784ad9"}
  reproduction_tests:
    - "evidence/repro_kd2h.py"
    - "tests/modules/policy_analysis/test_review_queue.py::test_corrigido_com_valor_que_viola_regra_e_rejeitado_sem_persistir"
  regression_tests:
    - "tests/modules/policy_analysis/test_review_queue.py::test_corrigido_com_moeda_invalida_tambem_e_rejeitado"
    - "tests/modules/policy_analysis/test_review_queue.py::test_confirm_nao_recebe_regras"
    - "tests/modules/policy_analysis/test_review_queue.py::test_decisao_corrigido_substitui_valor_e_normaliza"
    - "tests/e2e/test_review_cycle.py"

spec_verdict: spec-correta
change_set:
  - id: CHG-005
    kind: test
    artifact: tests/modules/policy_analysis/test_review_queue.py
    purpose: "guarda do CORRIGIDO (rejeição + nada persistido + motivo sanitizado) e CONFIRMADO sem regras"
    diff: fix/CHG-005.diff
  - id: CHG-006
    kind: code
    artifact: src/modules/policy_analysis/application/review.py
    purpose: "validate_fact no ramo CORRIGIDO de record_decision; violação = ContractValidationError sanitizado, sem persistir"
    diff: fix/CHG-006.diff

closure:
  policy: local-software
  satisfied: true
resolution_kind: fixed
---

# Notas do D2-P0-2 afirmam validate_fact na correção humana, mas review.py não chama

## Summary

Segunda divergência código x spec do módulo (mesmo padrão do BUG-20261004-ODCS, achada no
debate multiagente de 2026-10-04): o registro de execução do D2-P0-2 afirma que a correção
humana passa pelas regras de campo (`validate_fact`) com `ContractValidationError` sanitizado,
mas `application/review.py::record_decision` só chama `normalize_value`. O revisor consegue
gravar valor que viola qualquer regra (enum da extensão territorial, valor positivo, moeda)
sem guarda, e nada é sinalizado.

## Expected Behavior

- Spec efetiva:
  - `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md` (D2-P0-2, linha 135):
    "Correção humana passa pelas regras do campo (`validate_fact`) como guarda contra erro de
    digitação: violação → `ContractValidationError` sanitizado (só regra/campo, nunca o valor) e
    nada é persistido. `confirm` **não** recebe regras — o revisor é a autoridade final sobre o
    valor documentado (é para isso que a fila existe)".
  - `_reversa_sdd/learning/plano-acao-dev2.md` (D2-P0-3): as regras "alimentam o loop do
    `D2-P0-2`".
- Questão em aberto para o fix (com decisão humana): a intenção descrita no registro vale como
  norma, ou a ausência da guarda no código é o comportamento desejado (revisor como autoridade
  irrestrita)? Com o enum da extensão territorial em vigor (BUG-20261004-ODCS), a ausência de
  guarda no `correct` permite valores fora do enum por cima de um fato revisado.

## Actual Behavior

`application/review.py::record_decision` (linhas 46-68): `correct` valida só a presença de
`value`, e chama `raw_value_from_text`/`normalize_value`; não existe chamada a `validate_fact`
nem o `ContractValidationError` descrito. Confirmação por busca em 2026-10-04 (grep de
`validate_fact` em `src/modules/policy_analysis/application/review.py`: zero ocorrências).

## Steps to Reproduce

1. Extrair um fato `NEEDS_REVIEW` de `extensao_territorial` (ex.: valor fora do enum).
2. Na fila de revisão, executar `CORRIGIDO` com `value={"text": "Atlântico Norte"}` (fora do
   enum) via `ReviewService.record_decision`.
3. Observar: a decisão é persistida sem violação, sem `ContractValidationError` e sem
   sinalização; o fato passa a ter o valor corrigido.

## Evidence

- `evidence/nota-actions-d2-p0-2.txt` (citação da nota + trecho do código)
- Origem: debate multiagente do BUG-20261004-ODCS (rodadas 1 e 2), achado convergente dos 3
  solvers, verificado no código pelo moderador.

## Suspected Area

- `src/modules/policy_analysis/application/review.py` (`record_decision`, ramo `CORRIGIDO`).
- Consumidores: comparação/export passam a usar o valor revisado sem última checagem de regra.

## Acceptance Criteria

- Decisão humana registrada sobre a semântica (guarda em `correct` x revisor como autoridade).
- Se a guarda valer: `CORRIGIDO` com valor que viola regra levanta `ContractValidationError`
  sanitizado e nada é persistido; `confirm` segue sem regras; testes próprios.
- Se a ausência de guarda valer: o registro do D2-P0-2 é corrigido para refletir o código, com
  a decisão registrada.

## Traceability

- Specs: `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md` (D2-P0-2);
  `_reversa_sdd/learning/plano-acao-dev2.md` (D2-P0-3).
- Código afetado: `src/modules/policy_analysis/application/review.py`.
- Causa raiz: preenchida pelo fix.

## Resolution

- **Root cause (confirmed):** a implementação do D2-P0-2 normalizou o valor corrigido mas
  nunca acoplou as regras de campo (`validate_fact`) ao ramo `CORRIGIDO` de
  `ReviewService.record_decision`; o `ContractValidationError` descrito na nota nunca existiu.
  Comprovado por reprodução funcional (`evidence/reproduction.md`): `CORRIGIDO` aceitou
  `{"amount": "-100.00", "currency": "XYZ"}` como `FOUND`.
- **Veredito de spec (decisão humana de 2026-10-04, mesma deliberação da semântica):**
  `spec-correta` — a nota do D2-P0-2 define o comportamento desejado (guarda em `CORRIGIDO`,
  `confirm` sem regras); o código estava em falta. Nenhum adendo necessário; as correções de
  registro documentais vão em documento próprio
  (`_reversa_forward/dev2-003-p0-analise-experiencia/registro-correcoes-20261004.md`).
- **resolution_kind:** `fixed`.
- **Change set:**

| CHG | Tipo | Artefato | Propósito | Diff |
|-----|------|----------|-----------|------|
| CHG-005 | test | tests/modules/policy_analysis/test_review_queue.py | guarda do CORRIGIDO + CONFIRMADO sem regras | fix/CHG-005.diff |
| CHG-006 | code | src/modules/policy_analysis/application/review.py | `validate_fact` no `CORRIGIDO`; violação = `ContractValidationError` sanitizado | fix/CHG-006.diff |

- **Prova vermelho → verde:** vermelho em 2026-10-04 (3 testes "DID NOT RAISE"); verde após o
  fix (`349 passed, 4 skipped` na suíte completa; `ruff` e `mypy` limpos). O script
  `evidence/repro_kd2h.py` inverte a saída de "DEFEITO CONFIRMADO" (antes) para "GUARDA ATIVA:
  CORRIGIDO rejeitou valor que viola regras" (depois).
- **Semântica implementada (decisão do usuário):** `CORRIGIDO` roda `validate_fact` sobre o
  valor normalizado; violação levanta `ContractValidationError` com só regra/campo (nunca o
  valor, T-2a) e nada é persistido (fato segue na fila); `CONFIRMADO` continua sem regras
  (revisor é autoridade final); `DIVERGENTE` inalterado. Regras monetárias seguem só para
  campos MONEY (comportamento do `validate_fact` preservado).
- **Observações:** um teste foi corrigido durante o gate por premissa errada do próprio agente
  (regra de moeda aplicada a campo NUMBER; ajustado para campo monetário). Relação
  `related-to` com BUG-20261004-ODCS permanece em `proposed` (sem promoção).

## Agent Notes

- Severidade `low` e prioridade `P2` propostas pelo registrador (origem: inspection do debate
  BUG-20261004-ODCS; ajustar se o humano julgar diferente).
- Relação `related-to` com BUG-20261004-ODCS em estado `proposed` (mesmo padrão de registro de
  execução falso); promover quando um fix/auditoria confirmar o vínculo causal.
- As correções de registro documentais decididas no debate do BUG-20261004-ODCS (frase do
  adendo dev2-003 §6.1, nota "Regras implementadas" do actions.md, mapeamento
  `base_territorial` x `extensao_territorial`) acompanham este bug, por serem do mesmo padrão.
- T-2a se houver erro novo: motivo só com regra/campo, nunca o valor.