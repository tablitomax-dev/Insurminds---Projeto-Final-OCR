---
protocol_version: 1
debate_id: BUG-20261004-ODCS-r1
bug_id: BUG-20261004-ODCS
role: solver
solver_id: agente-3
engine: local
round: 1
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Leitura da regra

- Regra `enum_base_territorial` (nome da spec) aplicada ao campo real `extensao_territorial` (FieldType.TEXT, `field_catalog.py`). A divergência de nome também vive dentro da spec: actions.md D2-P0-3 escreve "enums de `base_territorial`", campo que não existe no catálogo; registrar o mapeamento na docstring de `rules.py` e corrigir a frase do registro.
- Enum fechado, tokens canônicos SEM acento após normalização: brasil; eua; estados unidos; canada; europa; america latina; america do sul; america do norte; mundo; mundial; worldwide; internacional; exterior. Grupos de aliases (eua/estados unidos, mundo/mundial/worldwide) são o mesmo valor.
- Normalização: `normalize_text` (NFKD, minúsculas, sem acentos, espaços colapsados) já roda em `normalize_text_value`, então a regra compara `normalized["text"]` por igualdade EXATA com os tokens canônicos. Nada de substring: "mundial exceto brasil" não pode passar.
- Escopo: dispatch por `field.code == "extensao_territorial"`, nunca por FieldType.TEXT (que cobre `exclusoes_chave`, texto livre).
- Fora do enum: violação rebaixa FOUND para NEEDS_REVIEW + `requires_human_review=true` + `value["rule_violations"]` com `rule="enum_base_territorial"` e motivo sanitizado (regra/campo, nunca o valor, T-2a). É sinal para revisão, não erro; o valor segue no fato e no comparável (D2-P0-2). `application/quality.py` classifica regra violada como ALTO.
- Disparo: `validate_fact` só roda em FOUND com valor normalizado não nulo (`_apply_field_guards`); texto vazio nem chega aqui (levanta `NormalizationError`, EC-04, antes das regras); NOT_FOUND/AMBIGUOUS não recebem regra.

## Causa raiz proposta

- D2-P0-3 foi marcado `[X]` em 2026-09-26 com 4 das 5 regras escritas; `_rule_enum_base_territorial` nunca existiu em `domain/rules.py` nem entrou em `validate_fact`. O adendo §6.1 e as notas do actions.md repetiram a lista do plano ("Regras implementadas"), afirmando falso sobre o código. Confirmei no código: docstring e `validate_fact` citam só `valor_positivo`, `moeda_conhecida`, `moeda_consistente`, `vigencia_ordem`. Mantenho a causa da rodada 0.

## Teste

- Reprodução (vermelho antes do fix): ExtractionService + StubAgent com `extensao_territorial` FOUND, `value={"text": "Atlântico Norte", "raw_text": ...}` e evidência ancorada: hoje sai FOUND sem `rule_violations`; com a regra, NEEDS_REVIEW + `requires_human_review=true` + violação `enum_base_territorial`; assert de que o valor não aparece no motivo (T-2a).
- Regressão em `tests/modules/policy_analysis/test_rules.py`: válidos com caixa/acento variados ("mundial", "MUNDIAL", "Canadá", "américa latina", "eua", "estados unidos", "brasil") = 0 violações; inválidos ("Atlântico Norte", "mundial exceto brasil", "Estados Unidos e Canadá") = 1 violação; None = 0 violações.
- Manter a asserção de `test_texto_nao_recebe_regras_de_valor` ("mundial" segue aceito, agora por pertencer ao enum) e renomear o teste, que ficou com nome obsoleto.
- Suite completa verde (baseline 233 passed, 4 skipped) e golden set inalterado: valores dos fixtures ("Mundial", "Brasil", "Mundo", "Estados Unidos") estão no enum.

## Impacto sobre a spec

- RECOMENDAÇÃO de veredito: **spec-correta**, reafirmada após a rodada 1. As quatro fontes (plano D2-P0-3, actions.md D2-P0-3, adendo §6.1, sdd RF-02/RF-03) exigem o mesmo comportamento e nenhuma registra descarte; falta implementação, não norma. O que está errado é o registro de execução que afirma a regra existente, e isso se corrige em documento, sem mudar semântica normativa.
- Gap documental menor (não muda o veredito): explicitar mapeamento `base_territorial` vs `extensao_territorial`, tokens canônicos, normalização e destino de valor composto fora do enum.
- Consumidores: fila de revisão cresce; comparação não muda (NEEDS_REVIEW compara o valor cru até decisão humana); export passa a exibir `rule_violations` (já previsto no contrato v1.0.0); quality report passa a sinalizar ALTO nesses fatos.

## Riscos e efeitos colaterais

- Valores legítimos compostos ("Canadá e Estados Unidos", "Global") caem em NEEDS_REVIEW: aceitável como sinal, aumenta a fila.
- Retiro o risco afirmado na rodada 0: `review.py` NÃO chama `validate_fact`; a correção humana com valor fora do enum só normaliza e grava FOUND, sem regra. Não há `ContractValidationError` nem bloqueio: a decisão humana é autoridade (igual ao `confirm`). O risco real é o inverso, o revisor pode gravar valor fora do enum por escolha, o que é desejado.
- Enum fechado exige decisão explícita de spec para novo território; não improvisar tokens no código.
- Renomear o teste existente gera ruído de diff, aceitável e pontual.

## Evidências

- `src/modules/policy_analysis/domain/rules.py`: docstring e `validate_fact` com 4 regras, sem enum (idem `evidence/rules-py-docstring-regras.txt`).
- `evidence/adendo-dev2-003-afirma-enum.txt` e adendo §6.1: afirma a regra como implementada.
- `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md` (D2-P0-3): enum fechado, rebaixamento para NEEDS_REVIEW e a lista falsa "Regras implementadas"; `_reversa_sdd/learning/plano-acao-dev2.md` (D2-P0-3): "Falha de regra → NEEDS_REVIEW (nunca FOUND)".
- `domain/value_types.py` (`normalize_text` NFKD; vazio levanta `NormalizationError`), `application/extraction.py` (`validate_fact` só em FOUND), `application/review.py` (correção sem revalidação por regra), `application/quality.py` (regra violada = ALTO).

## Confiança

alta. As fontes normativas são convergentes e o código é inequívoco; a única correção da rodada 0 foi o destino da correção humana, resolvida lendo `review.py`, e a decisão sobre aceitar compostos segue sendo de produto/humana.

## Crítica às demais propostas

- agente-1: leitura correta no mapeamento de nome, na normalização e na igualdade exata; acerta ao exigir dispatch por `field.code` e alertar que aplicar a regra a todo TEXT quebraria `exclusoes_chave`, ponto que incorporo. Fracilidades: diz só que "o fluxo Confirmar/Corrigir já cobre" o destino de valores fora do enum, sem verificar que a correção não passa por regras; e não notou que o nome `base_territorial` como campo aparece dentro do actions.md, ou seja, a ambiguidade é da spec, não só do código.
- agente-2: é quem tem a melhor evidência de consumidores: acerta que `application/review.py` não chama `validate_fact` (correção humana grava FOUND sem revalidar, contra o que eu havia afirmado na rodada 0, e eu concedo) e que `quality.py` marca ALTO; acerta também o mecanismo exato do disparo (guard `status == "FOUND"`). Ressalvas: o cenário "se um fix futuro validar a correção com validate_fact" é hipótese fora do escopo deste bug, que não deve mexer no fluxo de revisão; e o baseline citado (233/4) vale confirmar antes de fechar o plano de teste.
- Convergência final: os três mantêm `enum_base_territorial` sobre `extensao_territorial`, normalização via `normalize_text`, igualdade exata e veredito spec-correta; a divergência real da rodada 0 era só o destino da correção humana, e ela se resolve a favor da leitura do agente-2.
