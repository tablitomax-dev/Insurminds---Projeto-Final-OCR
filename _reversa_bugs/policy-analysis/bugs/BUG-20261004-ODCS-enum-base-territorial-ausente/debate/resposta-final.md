---
protocol_version: 1
debate_id: BUG-20261004-ODCS-final
bug_id: BUG-20261004-ODCS
role: judge
round: 2
status: ok
finished_at: 2026-10-04
---

## Síntese

- Regra `enum_base_territorial` (nome da spec) aplicada por `field.code == "extensao_territorial"` (nunca por FieldType.TEXT, que cobre `exclusoes_chave`); campo e regra não renomeados (contrato v1.0.0, rastreabilidade em 4 fontes); mapeamento `base_territorial` = `extensao_territorial` documentado no docstring de `domain/rules.py`.
- Enum fechado (actions.md D2-P0-3), tokens canônicos após `normalize_text` (NFKD, minúsculas, sem acento, espaços colapsados): brasil; eua; estados unidos; canada; europa; america latina; america do sul; america do norte; mundo; mundial; worldwide; internacional; exterior. Aliases equivalentes: eua|estados unidos e mundo|mundial|worldwide.
- Aceite por igualdade EXATA do token normalizado, nunca substring/prefixo/composição: "mundial exceto brasil", "Estados Unidos e Canada", "Global" e "Atlântico Norte" são fora do enum e rebaixam.
- Normalização em duas camadas: `validate_fact` recebe valor normalizado, mas o helper `_violations` dos testes passa o dict cru e o comparador aceita "MUNDIAL" cru; a regra aplica `normalize_text` defensivo (idempotente, mesmo padrão de `moeda_conhecida`) antes de comparar; NormalizationError ou texto vazio = sem regra (padrão de `_rule_valor_positivo`, EC-04 antes das regras).
- Fora do enum: FOUND rebaixa para NEEDS_REVIEW + requires_human_review=true + `value["rule_violations"]` (rule="enum_base_territorial", motivo sanitizado: regra/campo, nunca o valor, T-2a). É sinal de revisão, não erro: o valor segue no fato e comparável até decisão humana (D2-P0-2).
- Disparo apenas em FOUND com normalizado não nulo (guard em `_apply_field_guards`); NOT_FOUND, AMBIGUOUS, None e texto vazio não recebem a regra.
- Plano de teste: reprodução vermelha (StubAgent, "Atlântico Norte" sai FOUND hoje; com a regra sai NEEDS_REVIEW + violação, motivo sem eco do valor); unidade em test_rules.py (válidos "mundial", "MUNDIAL", "Canadá", "américa latina", "eua", "estados unidos", "brasil", "worldwide" = 0; inválidos "Atlântico Norte", "mundial exceto brasil", "Estados Unidos e Canada", "Global" = 1; None/vazio = 0; `exclusoes_chave` sem a regra); manter a asserção de `test_texto_nao_recebe_regras_de_valor` ("mundial" = 0, agora por pertencer ao enum) e renomear o teste obsoleto; regressão da suíte completa (baseline 233 passed, 4 skipped, gate do actions.md linha 128, a confirmar na execução) com fixtures ("Mundial", "Brasil", "Canadá", "Estados Unidos", "Mundo"), golden set, comparação, export e e2e inalterados.

## Vencedora

P-A

## RECOMENDAÇÃO de veredito

`spec-correta`. Evidências: o plano (D2-P0-3: "falha de regra -> NEEDS_REVIEW, nunca FOUND"), o actions.md D2-P0-3 (enum fechado), o adendo dev2-003 §6.1 e o sdd RF-02/RF-03 exigem o mesmo comportamento e nenhuma fonte registra retirada da exigência; o código (docstring e dispatch de `domain/rules.py`) implementa só 4 das 5 regras. O que existe é registro de execução falso (adendo §6.1 e nota "Regras implementadas" copiaram a intenção como fato), não revogação (não é `spec-desatualizada`) nem ausência de norma (enum, rebaixamento e sanitização estão definidos; não é `spec-gap`): falta implementação. Correções de registro documentais junto do fix: frase do adendo §6.1, nota do actions.md que trata `base_territorial` como field_code, nota D2-P0-2 sobre `validate_fact` na correção humana (registro próprio) e mapeamento regra/campo na docstring. A decisão final é humana.

## Enxertos aproveitados

- De P-B: evidência de consumidores e baseline (gate actions.md linha 128: 233 passed, 4 skipped), efeito ALTO no quality report (`application/quality.py`) e export exibindo rule_violations (contrato v1.0.0).
- De P-C: "Global" como sinônimo fora do enum (rótulo único, destino = rebaixar) e a divergência D2-P0-2 (`review.py::record_decision` só chama `normalize_value`; a nota afirma `validate_fact`/`ContractValidationError`) tratada como registro separado, sem mexer no fluxo de revisão neste fix.

## Justificativa por critério

1. Material completo: P-A cobre código (rules.py, extraction.py `_apply_field_guards`, review.py, quality.py), spec (plano, actions.md, adendo, sdd) e contratos (fixtures, golden set, comparador com valor cru); P-B empataria em consumidores, mas fez a camada de normalização menos precisa.
2. RECOMENDAÇÃO: as três propõem `spec-correta` com as mesmas 4 fontes; P-A argumenta melhor contra as alternativas (nada revogou, nada falta na norma).
3. Nome/semântica: P-A é a única que fixa onde a normalização decide (normalização defensiva idempotente na regra, por causa do helper `_violations` com dict cru), igualdade exata, destino de compostos/sinônimos (fila de revisão, nunca substring) e local dos guards.
4. Consequências: P-A define mudança de comportamento (só valores fora do enum caem na fila), preserva testes/fixture/comparação, renomeia o teste obsoleto e fecha o plano de teste (reprodução + unidade + regressão), com riscos (compostos legítimos, assimetria do revisor) explicitamente registrados.

## Confiança

alta: as três propostas convergem no cerne (enum, igualdade exata, rebaixamento, veredito) e a vencedora fecha o único ponto técnico aberto, restando só decisões humanas (aliases de compostos e o destino do D2-P0-2).
