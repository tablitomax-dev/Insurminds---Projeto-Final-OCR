---
protocol_version: 1
debate_id: BUG-20261004-ODCS-r2
bug_id: BUG-20261004-ODCS
role: solver
solver_id: agente-1
engine: local
round: 2
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Leitura da regra

- Regra `enum_base_territorial` (nome da spec) sobre o campo real `extensao_territorial` (FieldType.TEXT). Nao renomear campo (contrato v1.0.0, fixtures, golden set) nem regra (rastreabilidade em 4 fontes); mapeamento registrado na docstring de `domain/rules.py`.
- Enum fechado (actions.md D2-P0-3), tokens canonicos ja normalizados (minusculas, sem acento): brasil; eua; estados unidos; canada; europa; america latina; america do sul; america do norte; mundo; mundial; worldwide; internacional; exterior (13 tokens; eua|estados unidos e mundo|mundial|worldwide valem como o mesmo valor).
- Aceite por igualdade EXATA do texto normalizado contra o token, nunca substring ou prefixo: "mundial exceto brasil", "Estados Unidos e Canada", "Global" estao fora do enum e rebaixam.
- Normalizacao em duas camadas (refino desta rodada): `validate_fact` recebe o valor ja normalizado, mas o helper `_violations` dos testes passa o dict cru e o comparador aceita "MUNDIAL" cru; por isso a regra aplica `normalize_text` defensivo (idempotente, NFKD, mesmo padrao do `.upper()` em `moeda_conhecida`) antes de comparar; NormalizationError ou texto vazio = sem regra (mesmo padrao de `_rule_valor_positivo`).
- Fora do enum: FOUND rebaixa para NEEDS_REVIEW + requires_human_review=true + `value["rule_violations"]` com rule="enum_base_territorial" e motivo sanitizado (regra/campo, nunca o valor, T-2a). E sinal de revisao, nao erro: o valor segue no fato e comparavel ate decisao humana (D2-P0-2).
- Disparo so em FOUND com normalizado nao nulo (guarda em `_apply_field_guards`); NOT_FOUND, AMBIGUOUS, None e texto vazio (EC-04 rebaixa antes das regras) nao recebem o enum; dispatch por `field.code`, nunca por FieldType.TEXT (pegaria `exclusoes_chave`).

## Causa raiz proposta

- D2-P0-3 entregou 4 das 5 regras: `_rule_enum_base_territorial` nunca entrou em `domain/rules.py` nem em `validate_fact` (docstring lista as 4). O adendo dev2-003 §6.1 e as notas do actions.md ("Regras implementadas") copiaram a intencao do plano como fato: registro de execucao falso, nao descarte de requisito. O mesmo padrao se repete em D2-P0-2 (notas afirmam `validate_fact` na correcao humana; o codigo nao chama).

## Teste

- Reproducao (vermelho antes do fix): ExtractionService + StubAgent, `extensao_territorial` FOUND, value={"text": "Atlantico Norte", "raw_text": ...} e evidencia ancorada: hoje sai FOUND sem rule_violations; com a regra sai NEEDS_REVIEW + requires_human_review=true + violacao `enum_base_territorial` e motivo sem eco do valor.
- Unidade em test_rules.py: validos com caixa/acento variados ("mundial", "MUNDIAL", "Canada", "america latina", "eua", "estados unidos", "brasil", "worldwide") = 0 violacoes; invalidos ("Atlantico Norte", "mundial exceto brasil", "Estados Unidos e Canada", "Global") = 1 violacao; motivo nunca contem o valor; None e texto vazio = 0; `exclusoes_chave` nao recebe a regra.
- Manter a assercao de `test_texto_nao_recebe_regras_de_valor` ("mundial" = 0 violacoes, agora por pertencer ao enum) e renomear o teste, cujo nome ficou obsoleto.
- Regressao: suite completa verde (baseline declarado 233 passed, 4 skipped, confirmar na execucao); fixtures ("Mundial", "Brasil") e golden set ("Mundo", "Estados Unidos") inalterados; comparacao (Mundial vs MUNDIAL segue igual), export e e2e sem mudanca.

## Impacto sobre a spec

- RECOMENDACAO de veredito: `spec-correta` (mantida nas rodadas 0 e 1 e reforcada). As 4 fontes (plano D2-P0-3 "falha = NEEDS_REVIEW, nunca FOUND"; actions.md D2-P0-3 com o enum fechado; adendo §6.1; sdd RF-02/RF-03) exigem o mesmo comportamento e nenhuma registra retirada da exigencia. Nao e `spec-desatualizada` (nada revogou a regra) nem `spec-gap` (enum, rebaixamento e sanitizacao estao definidos; falta implementacao, nao norma).
- Correcoes de registro na entrega (factual, nao normativa): frase falsa do adendo §6.1; nota do actions.md que trata `base_territorial` como field_code (campo real: `extensao_territorial`); mapeamento regra/campo e tokens canonicos na docstring.
- Consumidores: fila de revisao cresce so com valores fora do enum; comparacao inalterada (valor cru ate decisao humana); export passa a exibir rule_violations (contrato v1.0.0 ja previsto); quality report marca ALTO (application/quality.py).

## Riscos e efeitos colaterais

- Compostos legitimos ("Canada e Estados Unidos") caem na fila: aceitavel como sinal, nao erro; cobrir compostos exige ampliacao explicita de aliases via adendo, nunca substring ou token improvisado no codigo.
- Correcao humana (application/review.py) nao chama `validate_fact`: o revisor grava valor fora do enum sem guarda e isso e desejado (decisao humana e autoridade). Nao mexer no fluxo de revisao neste fix; registrar a decisao explicitamente para que um fix futuro de revalidacao nao bloqueie valor legitimo.
- Normalizacao defensiva na regra e idempotente sobre valores ja normalizados, mas esconderia falha de pipeline se a normalizacao upstream deixasse de rodar; mitigado pelo teste de reproducao na camada de extracao.

## Evidências

- src/modules/policy_analysis/domain/rules.py (4 regras, dispatch por FieldType, sem `_rule_enum_base_territorial`); domain/value_types.py (`normalize_text` NFKD; vazio = NormalizationError, EC-04); domain/field_catalog.py (`extensao_territorial`, TEXT).
- application/extraction.py (`validate_fact` so em FOUND com normalizado nao nulo em `_apply_field_guards`; violacao rebaixa e anota rule_violations); application/review.py (so normaliza, sem `validate_fact`); application/quality.py (violacao = ALTO).
- actions.md D2-P0-3 (enum fechado, `base_territorial` como campo, lista falsa "Regras implementadas"); adendo dev2-003 §6.1; plano-acao-dev2.md D2-P0-3; tests/modules/policy_analysis/test_rules.py (helper `_violations` cru) e fixtures apolice_a/apolice_b.

## Confiança

alta: agente-2, agente-3 e esta proposta convergem em nome, enum, rebaixamento e veredito; esta rodada fecha o ponto aberto (em que camada a normalizacao decide o aceite) e ratifica a correcao sobre `review.py`. Resta so a decisao humana sobre aliases de valores compostos.

## Crítica às demais propostas

- agente-2 (rodada 1): acerta o ponto mais delicado (`review.py` nao chama `validate_fact`), o efeito ALTO no quality report e o baseline, e incorpora a armadilha de substring; ratifico tudo. Fragilidades: (a) o teste unitario com "MUNDIAL"/"Canada" so passa se a regra normalizar defensivamente (ou se o teste entregar o valor pronto), camada que agente-2 nao fixa; (b) diz que AMBIGUOUS/vazio "nao recebem regra" sem localizar quem decide (guard `status == "FOUND"` em `_apply_field_guards`, e EC-04 antes das regras); (c) trata a hipotetica revalidacao da correcao humana como risco de codigo, quando neste fix cabe apenas registrar a decisao.
- agente-3 (rodada 1): acerta igualdade exata, o caso "mundial exceto brasil" e concede comprovadamente o erro da rodada 0 sobre `ContractValidationError` (correto: `review.py` so normaliza). Fragilidades: (a) mesma lacuna de agente-2 sobre a camada de normalizacao nos testes com caixa/acento; (b) rotulou "Global" como composto legítimo na rodada 0 e como sinonimo fora do enum na rodada 1: a posicao final (fora do enum, rebaixa) e a correta e fica aqui fixada; (c) chama o gap de nome de so documental, mas `base_territorial` nasce do proprio actions.md, que e registro normativo, logo exige correcao de registro explicita na entrega.
