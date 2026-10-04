---
protocol_version: 1
debate_id: BUG-20261004-ODCS-r0
bug_id: BUG-20261004-ODCS
role: solver
solver_id: agente-3
engine: local
round: 0
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Leitura da regra

- Nome: regra `enum_base_territorial` (nome da spec) mirando o campo `extensao_territorial` do catálogo (FieldType.TEXT). "Base territorial" existe só como texto de documento; o mapeamento deve ser registrado no docstring de `rules.py`.
- Enum fechado, tokens canônicos após normalização: brasil; eua; estados unidos; canada; europa; america latina; america do sul; america do norte; mundo; mundial; worldwide; internacional; exterior. Aliases de mesmo significado (eua/estados unidos, mundo/mundial/worldwide) formam o mesmo grupo.
- Normalização: reusar `normalize_text` (minúsculas, sem acentos, espaços colapsados), então "Mundial", "MUNDIAL", "Canadá", "América Latina" casam sem regra extra de caixa/acento.
- Aceite: igualdade EXATA do texto normalizado a um token do enum. Nada de substring: "não cobre américa do sul" não pode passar.
- Fora do enum: violação rebaixa FOUND para NEEDS_REVIEW + `requires_human_review=true` + `value["rule_violations"]` com `rule="enum_base_territorial"` e motivo sanitizado (regra/campo, nunca o valor, T-2a). É sinal para revisão, não erro: o valor documentado segue no fato e comparável (decisão do D2-P0-2).
- Sem valor legível (None, texto vazio) ou NOT_FOUND: nenhuma regra dispara, mesmo padrão das 4 regras atuais.

## Causa raiz proposta

- `D2-P0-3` foi marcado `[X]` na execução de 2026-09-26, mas `domain/rules.py` nasceu com só 4 regras e a quinta (o enum) nunca foi escrita; o adendo §6.1 repetiu a lista do plano como se estivesse implementada, sem checar o código. Lacuna de implementação encoberta por registro de execução otimista, falha de verificação no encerramento da feature.

## Teste

- Reprodução: ExtractionService + StubAgent com `extensao_territorial` FOUND, `value={"text": "Atlântico Norte", "raw_text": "Trecho da apólice"}` e evidência: hoje sai FOUND sem `rule_violations`; com a regra, NEEDS_REVIEW + `requires_human_review=true` + violação `rule="enum_base_territorial"`; assert de que "Atlântico Norte" não aparece no motivo (T-2a).
- Regressão em `tests/modules/policy_analysis/test_rules.py`: válidos ("mundial", "Mundial", "MUNDIAL", "canadá", "estados unidos", "eua", "brasil", "américa latina") = 0 violações; inválidos ("Atlântico Norte", "mundial exceto brasil") = 1 violação; None/NOT_FOUND = 0 violações.
- Ajustar `test_texto_nao_recebe_regras_de_valor` (nome fica obsoleto): "mundial" segue com 0 violações, agora por pertencer ao enum.
- Suite completa verde (pytest) e golden set inalterado: fixtures usam "Mundial", "Brasil", "Estados Unidos", todos no enum.

## Impacto sobre a spec

- RECOMENDAÇÃO de veredito: **spec-correta**. As quatro fontes (plano D2-P0-3, actions.md D2-P0-3, adendo §6.1, sdd RF-02/RF-03) concordam no comportamento exigido e nada indica retirada ou revisão da exigência; falta implementação, não spec. O adendo §6.1 está factualmente errado ao dizer "implementadas", mas como norma define o alvo correto; corrigir a frase na entrega (registro, não norma).
- Gap documental menor (não muda o veredito): a spec nunca explicitou `base_territorial` vs `extensao_territorial` nem a normalização; sanar registrando o mapeamento e o critério (caixa/acentos via `normalize_text`, igualdade exata).
- Consumidores: revisão humana recebe mais fatos do campo na fila (correção humana fora do enum passa a falhar em `validate_fact`, guard de digitação; escape é `confirm`, que não passa por regras); comparação não muda (NEEDS_REVIEW compara o valor cru até decisão humana); export passa a exibir `rule_violations` no campo; golden set e `run_id` idem (valores dos fixtures já estão no enum).

## Riscos e efeitos colaterais

- Falsos positivos para valores legítimos compostos ("Canadá e Estados Unidos", "Global") caem em NEEDS_REVIEW e aumentam a fila; aceitável como sinal, não erro.
- Enum fechado exige adendo de spec para novo território; não improvisar tokens no código.
- Correção humana para valor fora do enum passa a devolver `ContractValidationError` sanitizado; citar o escape `confirm` na entrega.
- Relação `related-to` com BUG-20261004-YFN3 pode ser promovida no fix.

## Evidências

- `evidence/rules-py-docstring-regras.txt` e `src/modules/policy_analysis/domain/rules.py`: só 4 regras, sem enum.
- `evidence/adendo-dev2-003-afirma-enum.txt`: adendo §6.1 afirma a regra como implementada.
- `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md` (D2-P0-3): enum fechado e rebaixamento para NEEDS_REVIEW.
- `_reversa_sdd/learning/plano-acao-dev2.md` (D2-P0-3): "Falha de regra → NEEDS_REVIEW (nunca FOUND)".
- `field_catalog.py` (campo real `extensao_territorial`, TEXT), `value_types.py` (`normalize_text`) e testes/fixtures ("Mundial"/"Brasil"/"Estados Unidos").

## Confiança

alta. As fontes da spec são convergentes e o código é inequívoco; o ponto aberto é só a confirmação humana do mapeamento de nome e do destino de valores compostos fora do enum.
