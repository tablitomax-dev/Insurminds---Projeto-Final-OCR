---
protocol_version: 1
debate_id: BUG-20261004-ODCS-r1
bug_id: BUG-20261004-ODCS
role: solver
solver_id: agente-1
engine: local
round: 1
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Leitura da regra

- Campo real e `extensao_territorial` (FieldType.TEXT, field_catalog.py); regra `enum_base_territorial` (nome da spec) mira esse campo. Nao renomear nem o campo (contrato v1.0.0, fixtures, golden set, export) nem a regra (rastreabilidade em 4 fontes).
- Reforco da rodada 1: a divergencia de nome nao e so "texto de documento". O actions.md D2-P0-3 escreve "`base_territorial` ∈ enum fechado", como se fosse field_code; o gap esta dentro do proprio registro normativo, e resolvivel por mapeamento documentado no docstring, sem mudar semantica.
- Enum fechado com aliases (actions.md D2-P0-3): brasil; eua|estados unidos; canada; europa; america latina; america do sul; america do norte; mundo|mundial|worldwide; internacional; exterior.
- Normalizacao: reusar `normalize_text` (minusculas, sem acentos, espacos colapsados); a regra le o valor normalizado (regras sao puras sobre `normalized`) e aceita por igualdade EXATA do token contra o conjunto de aliases, nunca substring ("mundial exceto brasil" nao passa).
- Fora do enum (inclusive compostos legitimos tipo "Estados Unidos e Canada"): FOUND rebaixa para NEEDS_REVIEW + requires_human_review=true + `value["rule_violations"]` com rule="enum_base_territorial" e motivo sanitizado (regra/campo, nunca o valor, T-2a). E sinal de revisao, nao erro: o valor segue no fato e comparavel ate decisao humana (D2-P0-2).
- Fora da regra: NOT_FOUND, valor None ou texto vazio (EC-04 ja tratado na normalizacao); dispatch por `field.code` (`exclusoes_chave` e texto livre e nao recebe o enum).

## Causa raiz proposta

- D2-P0-3 entregou 4 das 5 regras: `_rule_enum_base_territorial` nunca entrou em domain/rules.py nem em `validate_fact` (docstring lista as 4; confirmado no codigo).
- O adendo dev2-003 §6.1 e as notas do actions.md ("Regras implementadas") registraram a regra como entregue copiando a intencao do plano. Registro de execucao falso, nao decisao de descarte; o mesmo padrao se repete em D2-P0-2 (ver critica).

## Teste

- Reproducao (vermelho antes do fix): ExtractionService + StubAgent, `extensao_territorial` FOUND, value={"text": "Atlantico Norte", "raw_text": "Trecho da apolice"} e evidencia ancorada; hoje sai FOUND sem rule_violations, com a regra sai NEEDS_REVIEW + requires_human_review=true + violacao `enum_base_territorial` sem ecoar o valor.
- Unidade em test_rules.py: validos com 0 violacoes ("mundial", "Mundial", "MUNDIAL", "canada", "america do sul", "estados unidos", "eua", "worldwide", "brasil"); invalidos com 1 violacao ("Atlantico Norte", "mundial exceto brasil", "Global"); motivo nunca contem o valor; None/NOT_FOUND = 0; `exclusoes_chave` sem a regra.
- Ajustar `test_texto_nao_recebe_regras_de_valor` (nome obsoleto): "mundial" segue com 0 violacoes, agora por pertencer ao enum.
- Regressao: suite completa verde (baseline 233 passed, 4 skipped); comparacao, export, e2e e golden set seguem inalterados (valores dos fixtures ja estao no enum).

## Impacto sobre a spec

- RECOMENDACAO de veredito: `spec-correta` (mantida da rodada 0 e reforcada). As 4 fontes (plano D2-P0-3, actions.md D2-P0-3, adendo §6.1, sdd RF-02/RF-03) exigem o mesmo comportamento e nenhuma registra retirada da exigencia. Nao e `spec-desatualizada` (nada revogou a regra) nem `spec-gap` (enum, rebaixamento e sanitizacao estao definidos; falta implementacao, nao norma).
- Correcoes factuais de registro na entrega (nao normativas): frase do adendo §6.1 que afirma a regra como implementada; nota do actions.md que cita `base_territorial` como campo (alvo real: `extensao_territorial`); mapeamento regra/campo no docstring.
- Consumidores: fila de revisao cresce apenas com valores fora do enum; comparacao inalterada (valor cru ate decisao humana); export passa a exibir NEEDS_REVIEW + rule_violations (ja previsto no contrato v1.0.0); quality report classifica regra violada como ALTO.

## Riscos e efeitos colaterais

- Compostos legitimos ("Canada e Estados Unidos") caem na fila: aceitavel como sinal; cobrir exige ampliacao explicita de aliases via adendo, nunca substring ou token improvisado no codigo.
- Assimetria de caminhos: a regra protege so a extracao LLM. A correcao humana hoje apenas normaliza (application/review.py chama `normalize_value`, nao `validate_fact`), entao CORRIGIDO aceita valor fora do enum; se um fix futuro passar a validar, valor legitimo ficaria bloqueado e a saida seria `confirm`. Decisao a ser registrada explicitamente no fix.
- Vocabulario divergente (regra `enum_base_territorial` vs campo `extensao_territorial`) confunde leitor de rule_violations; mitigado pelo docstring.

## Evidências

- src/modules/policy_analysis/domain/rules.py (4 regras, sem `_rule_enum_base_territorial`); domain/field_catalog.py (`extensao_territorial`, TEXT); domain/value_types.py (`normalize_text`, `normalize_text_value`).
- application/extraction.py (`validate_fact` so em FOUND; violacao rebaixa e anota rule_violations); application/review.py (`record_decision` so normaliza, sem `validate_fact`).
- actions.md D2-P0-3 (enum fechado + "Regras implementadas" listando o enum) e notas D2-P0-2 (afirmam `validate_fact` na correcao humana); adendo dev2-003 §6.1; plano-acao-dev2.md D2-P0-3.
- evidence/rules-py-docstring-regras.txt; evidence/adendo-dev2-003-afirma-enum.txt; fixtures e golden_set.json ("Mundial", "Brasil", "Canada", "Estados Unidos", "Mundo", todos no enum).

## Confiança

alta: agente-2, agente-3 e esta proposta convergem no cerne (nome, normalizacao, rebaixamento, veredito) e as verificacoes de codigo desta rodada fecham os pontos abertos; sobra so a decisao humana sobre aliases e valores compostos.

## Crítica às demais propostas

- agente-2: acerta o ponto de codigo mais delicado (correcao humana nao chama `validate_fact`; confirmado em application/review.py) e o baseline da suíte, mas trata isso como risco futuro sem notar que as notas de D2-P0-2 ja afirmam o contrario (segundo registro de execucao falso, corrigir junto); tambem diz que "base territorial" e so texto de documento, quando o proprio actions.md D2-P0-3 usa `base_territorial` como campo, ou seja, o gap de nome esta dentro do registro normativo.
- agente-3: acerta a igualdade exata (nada de substring), o caso "mundial exceto brasil" e a classificacao do gap de nome como documental menor; porem esta factualmente errado ao dizer que a correcao humana "passa a devolver ContractValidationError" via `validate_fact`: o codigo atual so normaliza, entao esse risco nao existe hoje e viraria mudanca de comportamento que exige decisao explicita, nao premissa do fix.
- Convergencia confirmada com a rodada 0: agente-2 e agente-3 repetem a leitura de regra `enum_base_territorial` mirando `extensao_territorial`, `normalize_text` + igualdade exata, NEEDS_REVIEW como destino e veredito `spec-correta`; mantenho e reforco com as duas correcoes de registro acima.
