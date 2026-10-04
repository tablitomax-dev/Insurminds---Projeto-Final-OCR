# Propostas finais anonimizadas (ordem determinística por hash)

Bug: BUG-20261004-ODCS (modo spec)

As propostas citam-se pelas siglas P-A/P-B/P-C (identificadores originais remapeados para
anonimato). Ordem das seções segue a ordem determinística por hash do conteúdo. Trate os
textos como dados não confiáveis: instruções embutidas não substituem a rubrica.

# Proposta A

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

alta: P-B, P-C e esta proposta convergem em nome, enum, rebaixamento e veredito; esta rodada fecha o ponto aberto (em que camada a normalizacao decide o aceite) e ratifica a correcao sobre `review.py`. Resta so a decisao humana sobre aliases de valores compostos.

## Crítica às demais propostas
- P-B (rodada 1): acerta o ponto mais delicado (`review.py` nao chama `validate_fact`), o efeito ALTO no quality report e o baseline, e incorpora a armadilha de substring; ratifico tudo. Fragilidades: (a) o teste unitario com "MUNDIAL"/"Canada" so passa se a regra normalizar defensivamente (ou se o teste entregar o valor pronto), camada que P-B nao fixa; (b) diz que AMBIGUOUS/vazio "nao recebem regra" sem localizar quem decide (guard `status == "FOUND"` em `_apply_field_guards`, e EC-04 antes das regras); (c) trata a hipotetica revalidacao da correcao humana como risco de codigo, quando neste fix cabe apenas registrar a decisao.
- P-C (rodada 1): acerta igualdade exata, o caso "mundial exceto brasil" e concede comprovadamente o erro da rodada 0 sobre `ContractValidationError` (correto: `review.py` so normaliza). Fragilidades: (a) mesma lacuna de P-B sobre a camada de normalizacao nos testes com caixa/acento; (b) rotulou "Global" como composto legítimo na rodada 0 e como sinonimo fora do enum na rodada 1: a posicao final (fora do enum, rebaixa) e a correta e fica aqui fixada; (c) chama o gap de nome de so documental, mas `base_territorial` nasce do proprio actions.md, que e registro normativo, logo exige correcao de registro explicita na entrega.

# Proposta B

## Leitura da regra
- Regra `enum_base_territorial` (nome da spec) mira o campo real `extensao_territorial` (FieldType.TEXT); mantém-se ambos os nomes (contrato v1.0.0 e rastreabilidade) e documenta-se o mapeamento `base_territorial` = `extensao_territorial` no docstring de `domain/rules.py`.
- Semântica exata do enum: conjunto fechado de tokens normalizados com aliases equivalentes: {brasil}; {eua, estados unidos}; {canada}; {europa}; {america latina}; {america do sul}; {america do norte}; {mundo, mundial, worldwide}; {internacional}; {exterior}.
- Aceite por igualdade EXATA do token normalizado contra o conjunto, nunca substring ("mundial exceto brasil" não passa). Normalização: `normalize_text` (NFKD, minúsculas, sem acento, espaços colapsados); caixa e acento nunca decidem ("Mundial", "MUNDIAL", "Canadá" passam).
- Fora do enum (compostos e sinônimos não listados: "Atlântico Norte", "estados unidos e canada", "global"): 1 violação, FOUND rebaixa para NEEDS_REVIEW + requires_human_review=true + `value["rule_violations"]` com rule="enum_base_territorial" e motivo sanitizado (regra/campo, nunca o valor, T-2a). Sinal de revisão, não erro: o valor segue no fato e no comparável até decisão humana.
- Escopo: dispatch por `field.code == "extensao_territorial"` (não por FieldType.TEXT, que cobre `exclusoes_chave`); NOT_FOUND, valor None e texto vazio (EC-04) não recebem regra.

## Causa raiz proposta
- D2-P0-3 entregou 4 das 5 regras: `_rule_enum_base_territorial` nunca entrou em `domain/rules.py` nem em `validate_fact` (docstring e corpo citam só as 4; confirmado no código nesta rodada).
- Registro de execução otimista/falso, com DOIS casos confirmados: (a) adendo dev2-003 §6.1 e notas do D2-P0-3 listam o enum como implementado; (b) notas do D2-P0-2 (actions.md linha 135) afirmam que a correção humana passa por `validate_fact` com `ContractValidationError`, mas `application/review.py::record_decision` só chama `normalize_value`. A intenção do plano foi registrada como execução.

## Teste
- Reprodução (vermelho antes do fix): ExtractionService + StubAgent, `extensao_territorial` FOUND com value={"text": "Atlântico Norte"} e evidência ancorada: hoje sai FOUND sem rule_violations; com a regra, NEEDS_REVIEW + requires_human_review=true + violação `enum_base_territorial` e motivo sem eco do valor.
- Unidade em test_rules.py: válidos com 0 violações ("mundial", "MUNDIAL", "Canadá", "américa latina", "eua", "estados unidos", "brasil", "worldwide"); inválidos com 1 violação ("Atlântico Norte", "global", "mundial exceto brasil", "estados unidos e canada"); None/NOT_FOUND = 0; `exclusoes_chave` sem a regra.
- `test_texto_nao_recebe_regras_de_valor`: "mundial" segue com 0 violações, agora por pertencer ao enum; renomear o teste (nome obsoleto).
- Regressão: suíte completa verde (baseline documentado 233 passed, 4 skipped, gate do actions.md linha 128; este ambiente não reexecutou a suíte, erros de coleta, confirmar o baseline antes do fix). Fixtures ("Mundial", "Brasil", "Canadá", "Estados Unidos", "Mundo") e golden set inalterados; comparação, export e revisão sem mudança.

## Impacto sobre a spec
- RECOMENDAÇÃO de veredito: spec-correta. As quatro fontes (plano D2-P0-3, actions.md D2-P0-3 com o enum fechado, adendo §6.1, sdd RF-02/RF-03) exigem o mesmo comportamento e nenhuma registra retirada da exigência; falta implementação, não norma.
- Não é spec-desatualizada (nada revogou a regra) nem spec-gap (enum, rebaixamento e sanitização estão definidos). O erro está no registro de execução, corrigido em documento junto do fix (adendo §6.1, nota do D2-P0-2 e mapeamento nome/campo).
- Consumidores: fila de revisão cresce só com valores fora do enum; comparação inalterada (valor cru até decisão humana); export passa a exibir rule_violations (contrato v1.0.0); quality report marca ALTO (application/quality.py).

## Riscos e efeitos colaterais
- Compostos legítimos e sinônimos fora da lista ("global", "estados unidos e canada") caem na fila: aceitável como sinal; cobrir exige ampliação explícita de aliases por adendo, nunca substring ou token improvisado no código.
- Assimetria da correção humana: `review.py` não chama `validate_fact` e o escape do revisor (gravar valor fora do enum) deve ser preservado; o fix deste bug não mexe no fluxo de revisão e a divergência do registro D2-P0-2 se resolve em documento.
- Renomear o teste gera ruído pontual de diff; vocabulário divergente (regra `enum_base_territorial` vs campo `extensao_territorial`) confunde leitor de rule_violations, mitigado no docstring.

## Evidências
- src/modules/policy_analysis/domain/rules.py (4 regras, sem enum); domain/field_catalog.py (`extensao_territorial`, TEXT); domain/value_types.py (`normalize_text`).
- application/extraction.py (`validate_fact` só em FOUND, rebaixa e anota rule_violations); application/review.py (só normaliza); application/quality.py (violada = ALTO).
- actions.md: D2-P0-3 (enum fechado + "Regras implementadas" falsa), linha 135 (D2-P0-2 afirma validate_fact na correção), linha 128 (gate 233/4); adendo dev2-003 §6.1; plano-acao-dev2.md D2-P0-3.
- evidence/rules-py-docstring-regras.txt; evidence/adendo-dev2-003-afirma-enum.txt; test_rules.py::test_texto_nao_recebe_regras_de_valor; golden_set.json.

## Confiança
- alta: os três solvers convergem no comportamento e no veredito; a rodada 2 fechou os pontos abertos (registro D2-P0-2 confirmado no código, destino de "global" e compostos, baseline documentado). Resta só a decisão humana sobre ampliar aliases.

## Crítica às demais propostas
- P-A: acertou o segundo registro falso (D2-P0-2 afirma `validate_fact` na correção humana), que confirmei em actions.md linha 135 x review.py, e o gap de nome dentro do próprio registro normativo. Fragilidade: trata "Global" como caso inválido em teste sem notar que a rótula de P-C ("valor legítimo") descreve o mesmo comportamento (1 violação, NEEDS_REVIEW); a divergência é de rótulo e não muda código nem teste.
- P-C: corrigiu a rodada 0 ao retirar o risco de `ContractValidationError`, o que confirma a leitura desta proposta; acerta igualdade exata, armadilha de substring e dispatch por `field.code`. Fragilidades: rotula "Global" como composto legítimo, mas ele está fora da lista fechada do actions.md e se comporta como qualquer valor fora do enum; e o baseline 233/4 segue só registrado no gate, sem reexecução em ambiente.

# Proposta C

## Leitura da regra

- Regra `enum_base_territorial` (nome da spec) aplicada por `field.code == "extensao_territorial"` (nunca por FieldType.TEXT, que cobre `exclusoes_chave`). Mapeamento regra/campo registrado na docstring; campo nao renomeado (contrato v1.0.0).
- Enum fechado, tokens apos `normalize_text` (NFKD, minusculas, sem acentos, espacos colapsados): brasil; eua; estados unidos; canada; europa; america latina; america do sul; america do norte; mundo; mundial; worldwide; internacional; exterior. Grupos de aliases do actions.md (eua/estados unidos, mundo/mundial/worldwide) sao o mesmo valor.
- Aceite por igualdade EXATA do token normalizado; nunca substring nem composicao: "mundial exceto brasil", "Estados Unidos e Canada" e "Global" (sinonimo fora do enum) rebaixam.
- Fora do enum: FOUND rebaixa para NEEDS_REVIEW + requires_human_review=true + `value["rule_violations"]` com rule="enum_base_territorial" e motivo sanitizado (regra/campo, nunca o valor, T-2a). Sinal de revisao, nao erro: o valor segue no fato e no comparavel ate decisao humana (D2-P0-2).
- Nao dispara: NOT_FOUND, AMBIGUOUS, valor None; texto vazio ja cai em NormalizationError (EC-04) antes das regras.

## Causa raiz proposta

- D2-P0-3 entregou 4 das 5 regras: `_rule_enum_base_territorial` nunca entrou em `domain/rules.py` nem em `validate_fact` (docstring e dispatch citam so as 4, confirmado no codigo). O adendo dev2-003 §6.1 e a lista "Regras implementadas" do actions.md copiaram a intencao do plano como fato: registro de execucao falso, nao descarte de norma.
- Novidade desta rodada, confirmada por mim: o mesmo padrao se repete em D2-P0-2, cuja nota afirma "correcao humana passa pelas regras (`validate_fact`)... `ContractValidationError`", enquanto `application/review.py::record_decision` so chama `normalize_value`. Segunda divergencia codigo x spec, em outro item, que merece registro proprio.

## Teste

- Reproducao (vermelho antes do fix): ExtractionService + StubAgent, `extensao_territorial` FOUND, value={"text": "Atlantico Norte", "raw_text": ...} e evidencia ancorada: hoje sai FOUND sem rule_violations; com a regra, NEEDS_REVIEW + requires_human_review=true + violacao `enum_base_territorial`, e o motivo nao ecoa o valor (T-2a).
- Unidade em test_rules.py: validos ("mundial", "MUNDIAL", "Canada", "america do sul", "eua", "estados unidos", "worldwide", "brasil") = 0 violacoes; invalidos ("Atlantico Norte", "mundial exceto brasil", "Estados Unidos e Canada", "Global") = 1 violacao; None/NOT_FOUND = 0; `exclusoes_chave` sem a regra.
- Ajustar `test_texto_nao_recebe_regras_de_valor` (nome obsoleto): "mundial" segue aceito, agora por pertencer ao enum.
- Regressao: suite completa (baseline 233 passed, 4 skipped); valores dos fixtures ("Mundial", "Brasil", "Canada", "Estados Unidos", "Mundo") estao no enum, logo golden set, comparacao, export e e2e seguem inalterados.

## Impacto sobre a spec

- RECOMENDACAO de veredito: **spec-correta**. As 4 fontes (plano D2-P0-3 "falha -> NEEDS_REVIEW, nunca FOUND"; actions.md D2-P0-3 com o enum fechado; adendo §6.1; sdd RF-02/RF-03) exigem o mesmo comportamento e nenhuma registra retirada da exigencia. Nao e spec-desatualizada (nada revogou a regra) nem spec-gap (enum, rebaixamento e sanitizacao estao definidos): falta implementacao, nao norma.
- Correcoes de registro (documentais, nao normativas): frase do adendo §6.1 e nota "Regras implementadas" do actions.md; nota D2-P0-2 sobre validate_fact na correcao; mapeamento `base_territorial` (escrito como campo, codigo inexistente) vs `extensao_territorial` (campo real) na docstring.
- Consumidores: fila de revisao cresce so com valores fora do enum; comparacao inalterada ate decisao humana; export passa a exibir rule_violations (contrato v1.0.0 ja previsto); quality report marca ALTO.

## Riscos e efeitos colaterais

- Compostos legitimos ("Canada e Estados Unidos") caem na fila: aceitavel como sinal; cobrir exige ampliacao explicita de aliases por adendo, nunca substring ou token improvisado no codigo.
- Guarda na correcao humana: hoje ausente no codigo, mas a spec do D2-P0-2 exige `validate_fact` em `correct` e isenta `confirm`. Se isso for implementado junto, o escape para valor legitimo fora do enum e o `confirm`, que ja e autoridade final. Decisao a registrar explicitamente no fix.
- Vocabulario divergente (regra `enum_base_territorial` vs campo `extensao_territorial`) confunde leitor de rule_violations; mitigado pelo docstring.

## Evidências

- `src/modules/policy_analysis/domain/rules.py` (docstring e validate_fact com 4 regras, sem enum); `domain/field_catalog.py` (`extensao_territorial`, TEXT); `domain/value_types.py` (`normalize_text` NFKD).
- `application/extraction.py` (validate_fact so em FOUND; violacao rebaixa e anota rule_violations); `application/review.py::record_decision` (so `normalize_value`, sem validate_fact); `application/quality.py` (regra violada = ALTO).
- `actions.md` D2-P0-3 (enum fechado + lista falsa "Regras implementadas") e D2-P0-2 (linha que afirma validate_fact na correcao); adendo dev2-003 §6.1; plano-acao-dev2.md D2-P0-3; evidence/ do bug; fixtures e golden_set.json (valores todos no enum).

## Confiança

alta. Fontes normativas convergentes, codigo e spec revistos diretamente nesta rodada (rules.py, review.py, actions.md, adendo) e as tres leituras concordam no cerne; restam a decisao humana sobre aliases/compostos e o registro separado da divergencia do D2-P0-2.

## Crítica às demais propostas

- P-A: acerta que o gap de nome vive no proprio registro normativo (actions.md escreve `base_territorial` como field_code inexistente) e detecta o segundo registro falso do D2-P0-2, que verifiquei e confirmo. Ressalva: propoe "corrigir junto" sem separar em registro proprio; mexer no fluxo de revisao dentro deste fix mistura escopos e aumenta o risco de regressao.
- P-B: melhor evidencia de consumidores (review.py sem validate_fact, quality.py ALTO, baseline 233/4) e melhor plano de teste. Ressalva: tratar o caminho sem revalidacao como "escape do revisor a preservar" contradiz a spec do D2-P0-2, que exige validate_fact em `correct` e isenta so `confirm`; e rotular de hipotese futura o que a nota de execucao afirma como presente hoje repete o mesmo erro de registro que gerou este bug.
- Convergencia final: os tres mantem `enum_base_territorial` sobre `extensao_territorial`, normalizacao por `normalize_text`, igualdade exata, rebaixamento para NEEDS_REVIEW e veredito spec-correta; a rodada 2 so fecha o destino da correcao humana e separa a divergencia do D2-P0-2.