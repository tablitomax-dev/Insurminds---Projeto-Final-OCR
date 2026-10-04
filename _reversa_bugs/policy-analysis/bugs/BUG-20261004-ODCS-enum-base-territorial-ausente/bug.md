---
schema_version: 1
id: BUG-20261004-ODCS
display_number: 2
title: Regra enum_base_territorial ausente, extensao_territorial fora do enum passa como FOUND
status: resolved
phase: testing
severity: medium
priority: P1
created: 2026-10-04
updated: 2026-10-04
express: true

origin:
  type: inspection
  external_ref: null

area: policy-analysis
module: policy_analysis
feature: extracao
labels: [d2-p0-3, regra-de-campo]

visibility: normal
security_suspected: false

reproduction:
  classification: deterministic
  rate: "1/1"
  suspected_triggers: []

blocking: []
relationships: []

traceability:
  specs:
    - "_reversa_forward/dev2-003-p0-analise-experiencia/actions.md#d2-p0-3"
    - "_reversa_sdd/addenda/dev2-003-p0-analise-experiencia.md#61-requisitos-funcionais"
    - "_reversa_sdd/learning/plano-acao-dev2.md#d2-p0-3"
    - "_reversa_sdd/sdd/policy-analysis.md#61-requisitos-principais"
  affected_code:
    - "src/modules/policy_analysis/domain/rules.py"
    - "src/modules/policy_analysis/domain/field_catalog.py"
  root_cause:
    state: confirmed
    hypothesis: "D2-P0-3 entregou 4 das 5 regras de campo: `_rule_enum_base_territorial` nunca entrou em domain/rules.py nem em validate_fact, mas o registro de execução (adendo dev2-003 §6.1 e notas do actions.md) copiou a intenção do plano como fato."
    causal_path:
      - "plano/actions D2-P0-3 prevê 5 regras, incluindo enum_base_territorial"
      - "domain/rules.py implementa e documenta 4 regras; dispatch sem o enum"
      - "qualquer texto em extensao_territorial passa como FOUND sem rule_violations"
      - "o adendo dev2-003 §6.1 afirma a regra como implementada (registro de execução falso)"
    evidence:
      - {ref: "evidence/rules-py-docstring-regras.txt", observation: "docstring lista só as 4 regras"}
      - {ref: "evidence/adendo-dev2-003-afirma-enum.txt", observation: "spec efetiva declara a regra existente"}
      - {ref: "evidence/reproduction.md", observation: "vermelho antes (FOUND sem violação), verde depois"}
    code_refs:
      - {file: "src/modules/policy_analysis/domain/rules.py", symbol: "validate_fact", commit: "1784ad9"}
  reproduction_tests:
    - "tests/modules/policy_analysis/test_rules.py::test_enum_rebaixa_found_para_needs_review_no_servico"
    - "tests/modules/policy_analysis/test_rules.py::test_enum_base_territorial_rejeita_fora_do_enum"
  regression_tests:
    - "tests/modules/policy_analysis/test_rules.py::test_enum_base_territorial_aceita_valores_do_enum"
    - "tests/modules/policy_analysis/test_rules.py::test_enum_valido_mantem_found_no_servico"
    - "tests/modules/policy_analysis/test_rules.py::test_enum_base_territorial_motivo_nunca_traz_o_valor"
    - "tests/modules/policy_analysis/test_rules.py::test_enum_nao_alcanca_texto_livre_de_exclusoes"

spec_verdict: spec-correta
change_set:
  - id: CHG-003
    kind: test
    artifact: tests/modules/policy_analysis/test_rules.py
    purpose: "reprodução + unidade do enum (aceita/rejeita/motivo sanitizado) + integração (rebaixa FOUND, mantém FOUND válido)"
    diff: fix/CHG-003.diff
  - id: CHG-004
    kind: code
    artifact: src/modules/policy_analysis/domain/rules.py
    purpose: "regra enum_base_territorial (enum fechado, igualdade exata pós-normalização defensiva) em validate_fact"
    diff: fix/CHG-004.diff

closure:
  policy: local-software
  satisfied: true
resolution_kind: fixed
---

# Regra enum_base_territorial ausente, extensao_territorial fora do enum passa como FOUND

## Summary

O item D2-P0-3 do plano Dev 2 (e o registro de execução da feature dev2-003) prevê 5 regras de
campo em `domain/rules.py`, entre elas `enum_base_territorial`. O código tem apenas 4
(`valor_positivo`, `moeda_conhecida`, `moeda_consistente`, `vigencia_ordem`): o campo
`extensao_territorial` (TEXT) aceita QUALQUER texto como `FOUND`, sem rebaixar para revisão
quando o valor está fora do enum fechado esperado.

## Expected Behavior

- Spec efetiva:
  - `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md` (D2-P0-3): "`enum_base_territorial`
    — `base_territorial` ∈ enum fechado (brasil, eua/estados unidos, canadá, europa, américa
    latina, américa do sul, américa do norte, mundo/mundial/worldwide, internacional, exterior)".
  - `_reversa_sdd/addenda/dev2-003-p0-analise-experiencia.md` §6.1: regras por campo
    "(`vigencia_ordem`, `valor_positivo`, moedas, `enum_base_territorial`) rebaixam fato inválido
    para `NEEDS_REVIEW`".
  - `_reversa_sdd/learning/plano-acao-dev2.md` (D2-P0-3): "enums para `base_territorial`. Falha de
    regra → `NEEDS_REVIEW` (nunca `FOUND`)".
  - `_reversa_sdd/sdd/policy-analysis.md` §6.1 RF-02/RF-03: catálogo com semântica documentada e
    saída validada por campo.
- Falha da regra deve rebaixar o fato `FOUND` para `NEEDS_REVIEW` com
  `requires_human_review=true` e motivo sanitizado em `value["rule_violations"]`
  (regra/campo, nunca o valor — T-2a).

## Actual Behavior

`src/modules/policy_analysis/domain/rules.py` documenta e implementa só 4 regras; não há
checagem de enum para `extensao_territorial` (campo TEXT em `domain/field_catalog.py`, cujo valor
normalizado é `{"text": ...}`). Qualquer string vira `FOUND` sem violação.

Nota de divergência: o adendo dev2-003 (spec efetiva) AFIRMA que `enum_base_territorial` foi
implementada; o código não a contém. O veredito de spec (spec-correta vs spec-desatualizada) é
decisão humana e fica para o fix.

## Steps to Reproduce

1. Rodar `ExtractionService` com agente fake devolvendo `field_code="extensao_territorial"`,
   `status="FOUND"`, `value={"text": "Atlântico Norte", "raw_text": "Trecho da apólice"}` (texto
   fora do enum) e evidência correspondente.
2. Observar o fato resultante: `status="FOUND"`, `requires_human_review=false`, sem
   `value["rule_violations"]`.

## Evidence

- `evidence/rules-py-docstring-regras.txt` (catálogo de regras implementadas, sem o enum)
- `evidence/adendo-dev2-003-afirma-enum.txt` (spec efetiva afirma a regra como existente)
- Relato de origem: `../intake/relato-20261004-1030.md`

## Suspected Area

- `src/modules/policy_analysis/domain/rules.py` (falta a função de regra e o registro em
  `validate_fact`).
- `src/modules/policy_analysis/domain/field_catalog.py` (semântica do campo
  `extensao_territorial`; hoje TEXT puro).
- Consumidores que confiam em `FOUND` para esse campo: comparação/export (semântica de revisão já
  cobre o rebaixamento; nada muda fora da regra).

## Acceptance Criteria

- `extensao_territorial` tem regra `enum_base_territorial` com o enum fechado da spec efetiva
  (comparação normalizada: caixa e acentos não decidem aceite; aliases do enum cobrem
  "estados unidos"/"eua", "mundo"/"mundial"/"worldwide").
- Valor fora do enum rebaixa `FOUND` para `NEEDS_REVIEW` + `requires_human_review=true`, com
  violação registrada em `value["rule_violations"]` (`rule="enum_base_territorial"`).
- Motivo sanitizado: nunca carrega o valor rejeitado (T-2a).
- Valores do enum usados pelos fixtures/golden set (ex.: "Mundial", "Brasil", "Canadá") continuam
  aceitos sem violação.
- Testes próprios em `tests/modules/policy_analysis/test_rules.py`: valor válido passa, valor
  inválido rebaixa, motivo sem o valor.

## Traceability

- Specs: `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md` (D2-P0-3);
  `_reversa_sdd/addenda/dev2-003-p0-analise-experiencia.md` §6.1; `_reversa_sdd/learning/plano-acao-dev2.md`
  (D2-P0-3); `_reversa_sdd/sdd/policy-analysis.md` §6.1 (RF-02/RF-03).
- Código afetado: `src/modules/policy_analysis/domain/rules.py`,
  `src/modules/policy_analysis/domain/field_catalog.py`.
- Causa raiz: preenchida pelo fix.

## Resolution

- **Root cause (confirmed):** D2-P0-3 (plano e actions.md) previa 5 regras de campo; a
  implementação entregou 4 e `_rule_enum_base_territorial` nunca entrou em
  `domain/rules.py`/`validate_fact`. O registro de execução (adendo dev2-003 §6.1 e a nota
  "Regras implementadas" do actions.md) copiou a intenção do plano como fato.
- **Veredito de spec (aprovado pelo usuário em 2026-10-04):** `spec-correta` — as 4 fontes
  normativas (plano D2-P0-3, actions.md D2-P0-3 com o enum fechado, adendo §6.1, sdd RF-02/RF-03)
  exigem o comportamento e nenhuma registra retirada; falta implementação, não norma. Nenhum
  adendo necessário.
- **resolution_kind:** `fixed`.
- **Change set:**

| CHG | Tipo | Artefato | Propósito | Diff |
|-----|------|----------|-----------|------|
| CHG-003 | test | tests/modules/policy_analysis/test_rules.py | reprodução + unidade do enum + integração | fix/CHG-003.diff |
| CHG-004 | code | src/modules/policy_analysis/domain/rules.py | regra `enum_base_territorial` em `validate_fact` | fix/CHG-004.diff |

- **Prova vermelho → verde:** vermelho em 2026-10-04 (`test_enum_*` falhando e
  `test_enum_rebaixa_found_para_needs_review_no_servico` provando `FOUND` indevido); verde após
  o fix (`50 passed` nos arquivos tocados; suíte completa `346 passed, 4 skipped`; `ruff` e
  `mypy` limpos). Comandos e taxas em `evidence/reproduction.md`.
- **Semântica implementada (síntese do debate, resposta-final.md):** regra
  `enum_base_territorial` (nome da spec) por `field.code == "extensao_territorial"` (campo real);
  enum fechado de 13 tokens canônicos com aliases (eua/estados unidos, mundo/mundial/worldwide);
  aceite por igualdade EXATA após normalização defensiva (`_fold_text`, caixa/acentos neutros);
  nunca substring ("mundial exceto brasil", "Global" e compostos rebaixam como sinal de revisão);
  violação rebaixa `FOUND` → `NEEDS_REVIEW` + `requires_human_review=true` com motivo sanitizado
  em `value["rule_violations"]` (regra/campo, nunca o valor — T-2a); `NOT_FOUND`/`None`/texto
  vazio (EC-04) não recebem regra; ampliação de aliases só por adendo futuro.
- **Correções de registro (documentais, decididas no debate):** frase do adendo dev2-003 §6.1 e
  nota "Regras implementadas" do actions.md afirmam execução que não existia; mapeamento
  `base_territorial` (escrito como campo) vs `extensao_territorial` (campo real) ficou na
  docstring de `domain/rules.py`. Essas correções vão em documento de registro próprio,
  juntamente com a divergência D2-P0-2 (ver bug novo registrado em 2026-10-04).
- **Fora do change set (decisão explícita):** guarda de regras na correção humana
  (`review.py` não chama `validate_fact`; hoje a decisão humana é autoridade) e ampliação de
  aliases para valores compostos ("Canadá e Estados Unidos"). `test_texto_nao_recebe_regras_de_valor`
  mantido ("mundial" segue aceito, agora por pertencer ao enum); renomeação do teste fica para
  manutenção.

## Agent Notes

- Severidade `medium` e prioridade `P1` assumidas na rota expressa pelo agente de registro
  (fato inválido passa como FOUND, mas o ciclo de revisão humana cobre a correção posterior).
- Origem: item apontado em auditoria de pendências de 2026-10-04 e aceito pelo usuário como
  correção a fechar (rota expressa).
- O plano chama a regra de `enum_base_territorial`, mas o campo real do catálogo é
  `extensao_territorial` ("base territorial" aparece só como texto de documento). Implementar o
  nome da regra conforme a spec (`enum_base_territorial`) e mirar o campo `extensao_territorial`.
- Enum esperado (actions.md D2-P0-3): brasil, eua/estados unidos, canadá, europa, américa latina,
  américa do sul, américa do norte, mundo/mundial/worldwide, internacional, exterior.
- Teste existente `test_texto_nao_recebe_regras_de_valor` usa `{"text": "mundial"}` e espera zero
  violações; "mundial" pertence ao enum, então permanece válido (o nome do teste fica obsoleto).
- Relação `related-to` provável com BUG-20261004-YFN3 (mesma auditoria, mesmo módulo) não foi
  gravada: a rota expressa pula a correlação; o fix pode promovê-la.
- Veredito de spec necessário no fechamento: a spec efetiva (adendo dev2-003) diz que a regra
  existe; o código não a tem — confirmar com o humano se a implementação é que está atrasada
  (spec-correta) antes de declarar `fixed`.