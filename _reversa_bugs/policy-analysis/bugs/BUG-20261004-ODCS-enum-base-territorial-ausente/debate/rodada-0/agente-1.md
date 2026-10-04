---
protocol_version: 1
debate_id: BUG-20261004-ODCS-r0
bug_id: BUG-20261004-ODCS
role: solver
solver_id: agente-1
engine: local
round: 0
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Leitura da regra

- Campo real e `extensao_territorial` (FieldType.TEXT em `field_catalog.py`); "base territorial" e so o rotulo do texto da apolice (golden set). Nome da regra segue a spec (`enum_base_territorial`) mirando o campo do catalogo; nao renomear o campo (contrato v1.0.0, fixtures e export ja usam `extensao_territorial`).
- Enum fechado (actions.md D2-P0-3), comparado sobre o texto ja normalizado (minusculas, sem acentos, espacos colapsados): brasil; eua|estados unidos; canada; europa; america latina; america do sul; america do norte; mundo|mundial|worldwide; internacional; exterior.
- Normalizacao: reaproveitar `normalize_text` (caixa e acentos nao decidem aceite; "CANADA", "America Do Sul" e "canada" caem no mesmo token). Aceite por igualdade do token normalizado contra o conjunto de aliases, nunca por substring (determinismo, A-08).
- Fora do enum: rebaixa `FOUND` para `NEEDS_REVIEW` + `requires_human_review=true` + violacao em `value["rule_violations"]` com `rule="enum_base_territorial"`, motivo sanitizado (regra/campo, nunca o valor, T-2a). E sinal de revisao, nao erro: o valor segue disponivel e o loop Confirmar/Corrigir decide.
- Escopo: so `extensao_territorial` (nao todo TEXT; `exclusoes_chave` e texto livre). `NOT_FOUND`, valor `None` ou texto vazio nao disparam regra (a normalizacao cuida do formato).

## Causa raiz proposta

- D2-P0-3 implementou 4 das 5 regras: falta `_rule_enum_base_territorial` e o registro em `validate_fact` (`domain/rules.py`). O adendo dev2-003 secao 6.1 registrou a regra como ja entregue sem que o codigo a contivesse (registro de execucao falso, nao requisito divergente).

## Teste

- Reproducao (vermelho antes do fix): `ExtractionService` + `StubAgent` com `extensao_territorial` `FOUND`, `value={"text": "Atlantico Norte", "raw_text": ...}` e evidencia; hoje sai `FOUND` sem `rule_violations`; com a regra deve sair `NEEDS_REVIEW` + `requires_human_review=true` + violacao `enum_base_territorial`.
- Regressao em `tests/modules/policy_analysis/test_rules.py`: validos aceitos ("mundial", "Mundial", "Brasil", "Canada", "Estados Unidos", "eua", "worldwide"); caixa/acentos aceitos ("CANADA", "America Latina"); fora do enum rebaixa; motivo nunca contem o valor; `NOT_FOUND`/`None` sem regra; `exclusoes_chave` sem a regra.
- Ajustar `test_texto_nao_recebe_regras_de_valor` (nome obsoleto: "mundial" e valido por pertencer ao enum) para o novo contrato; gate T-1 e suites de comparacao/export/e2e/golden set seguem verdes.

## Impacto sobre a spec

- Recomendacao de veredito: `spec-correta`. As 4 fontes normativas (actions.md D2-P0-3, plano-acao-dev2 D2-P0-3, adendo dev2-003 secao 6.1, sdd policy-analysis secao 6.1 RF-02/RF-03) concordam na regra e no enum; so o codigo esta atrasado. Mudam codigo + teste, e o adendo ganha correcao factual (a frase que afirma a regra ja implementada), sem alterar semantica normativa.
- Consumidores: revisao humana passa a receber na fila os casos fora do enum (fluxo Confirmar/Corrigir ja cobre); comparacao inalterada (fato `NEEDS_REVIEW` continua participando); export mantem formato e passa a exibir `NEEDS_REVIEW` + `rule_violations`; golden set e fixtures usam "Mundo", "Estados Unidos", "Canada", "Mundial", "Brasil", todos dentro do enum, entao os 20 casos seguem sem rebaixamento.

## Riscos e efeitos colaterais

- Enum fechado rebaixa valores legitimos compostos ("Europa e America Latina"): intencional (sinal, nao erro), mas aumenta a fila de revisao; cobrir compostos exige ampliar aliases por decisao explicita, nunca substring.
- Vocabulario divergente (regra `enum_base_territorial` vs campo `extensao_territorial`) pode confundir quem le `rule_violations`; mitigado documentando o alvo no docstring da regra.
- Aplicar a regra a todo FieldType.TEXT quebraria `exclusoes_chave` (texto livre); o dispatch deve ser por `field.code`.

## Evidencias

- `evidence/rules-py-docstring-regras.txt` (catalogo com 4 regras, sem enum); `evidence/adendo-dev2-003-afirma-enum.txt` (adendo afirma a regra como implementada).
- `src/modules/policy_analysis/domain/rules.py` (sem `_rule_enum_base_territorial`); `actions.md` D2-P0-3 (enum fechado); `tests/modules/policy_analysis/fixtures/` e `src/modules/evaluation/fixtures/golden_set.json` (todos os valores dentro do enum); `test_rules.py::test_texto_nao_recebe_regras_de_valor` (comportamento atual documenta o gap).

## Confianca

alta: enum e rebaixamento estao especificados de forma consistente em 4 fontes e todos os valores usados por consumidores ja pertencem ao enum, entao a correcao e de baixo risco.
