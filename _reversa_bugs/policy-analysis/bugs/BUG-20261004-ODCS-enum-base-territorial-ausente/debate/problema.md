# Debate — BUG-20261004-ODCS (setup congelado)

```yaml
debate_id: BUG-20261004-ODCS
bug_id: BUG-20261004-ODCS
mode: spec              # código, execução registrada e spec divergem; termina em RECOMENDAÇÃO
N: 3                    # solvers independentes
R: 2                    # rodadas/épocas, SEM early stopping
external_harness: none  # só agentes locais (aceite do usuário em 2026-10-04)
status: setup
```

## Problema P

**Defeito.** O item D2-P0-3 do plano Dev 2 (e a execução registrada da feature dev2-003) prevê
5 regras de campo em `src/modules/policy_analysis/domain/rules.py`, entre elas
`enum_base_territorial` para o campo de extensão territorial (`extensao_territorial`, FieldType.TEXT).
O código implementa apenas 4 (`valor_positivo`, `moeda_conhecida`, `moeda_consistente`,
`vigencia_ordem`): qualquer texto passa como `FOUND`, sem rebaixar para revisão.

**Divergência código x spec (o cerne do debate).**
- O ADENDO `_reversa_sdd/addenda/dev2-003-p0-analise-experiencia.md` §6.1 AFIRMA a regra como
  implementada: "regras por campo (`vigencia_ordem`, `valor_positivo`, moedas,
  `enum_base_territorial`) rebaixam fato inválido para `NEEDS_REVIEW`".
- O código NÃO tem a regra (docstring de `domain/rules.py` lista só as 4).
- O registro de execução `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md` (D2-P0-3)
  define o enum fechado: "brasil, eua/estados unidos, canadá, europa, américa latina, américa do
  sul, américa do norte, mundo/mundial/worldwide, internacional, exterior".
- O plano `_reversa_sdd/learning/plano-acao-dev2.md` (D2-P0-3) exige "enums para
  `base_territorial`. Falha de regra → `NEEDS_REVIEW` (nunca `FOUND`)".

**Evidências.**
- `../evidence/rules-py-docstring-regras.txt` (catálogo atual, sem o enum)
- `../evidence/adendo-dev2-003-afirma-enum.txt` (spec efetiva afirma a regra como existente)
- Observação de campo: o nome real do catálogo é `extensao_territorial`; "base territorial"
  aparece só como texto de documento (golden set).

**Mecanismo de reprodução (planejado).** ExtractionService com StubAgent devolvendo
`extensao_territorial` `FOUND` com `value={"text": "Atlântico Norte"}` (fora do enum) e evidência
correspondente: hoje sai `FOUND` sem `rule_violations`; com a regra, deve rebaixar para
`NEEDS_REVIEW`. Valores usados pelos fixtures (Mundial, Brasil, Canadá, Estados Unidos) devem
continuar aceitos.

**Spec efetiva (resumo).**
- `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md` (D2-P0-3, com o enum).
- `_reversa_sdd/addenda/dev2-003-p0-analise-experiencia.md` §6.1 (declara a regra existente).
- `_reversa_sdd/learning/plano-acao-dev2.md` (D2-P0-3).
- `_reversa_sdd/sdd/policy-analysis.md` §6.1 (RF-02 catálogo com semântica documentada; RF-03
  saída validada) e §11/§12.

**Restrições (Agent Notes do bug).** Implementar a regra com o nome da spec
(`enum_base_territorial`) mirando o campo `extensao_territorial`; motivo sanitizado (regra/campo,
nunca o valor — T-2a); teste existente `test_texto_nao_recebe_regras_de_valor` usa "mundial" e
continua válido (pertence ao enum). Autorização humana de 2026-10-04: código do Dev 2
(`policy_analysis`) pode ser alterado.

## Rubrica congelada (modo spec)

A proposta será avaliada por estes critérios, nesta ordem:

1. **Pondera TODO o material**: comportamento observado no código, spec efetiva (original +
   adendos), evidência histórica (actions.md/commit/handoffs) e contratos/consumidores
   (fixtures, golden set, comparação/export/revisão).
2. **Produz RECOMENDAÇÃO de veredito** com evidências: `spec-correta` | `spec-desatualizada` |
   `spec-gap`. Nunca decide: a decisão final é humana.
3. **Coerência do nome/semântica**: o que fazer com `base_territorial` vs
   `extensao_territorial`; enum fechado vs texto livre; normalização (caixa/acentos) e o
   destino de valores legítimos fora do enum.
4. **Consequências da recomendação**: o que muda no comportamento, nos testes existentes e nos
   consumidores (revisão humana, comparação), e o plano de teste (reprodução e regressão).

Decisão esperada do debate: leitura da regra (semântica exata do enum e do rebaixamento) +
RECOMENDAÇÃO de veredito de spec com justificativa + plano de teste.