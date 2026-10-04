---
protocol_version: 1
debate_id: BUG-20261004-ODCS-r2
bug_id: BUG-20261004-ODCS
role: solver
solver_id: agente-2
engine: local
round: 2
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

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
- agente-1: acertou o segundo registro falso (D2-P0-2 afirma `validate_fact` na correção humana), que confirmei em actions.md linha 135 x review.py, e o gap de nome dentro do próprio registro normativo. Fragilidade: trata "Global" como caso inválido em teste sem notar que a rótula de agente-3 ("valor legítimo") descreve o mesmo comportamento (1 violação, NEEDS_REVIEW); a divergência é de rótulo e não muda código nem teste.
- agente-3: corrigiu a rodada 0 ao retirar o risco de `ContractValidationError`, o que confirma a leitura desta proposta; acerta igualdade exata, armadilha de substring e dispatch por `field.code`. Fragilidades: rotula "Global" como composto legítimo, mas ele está fora da lista fechada do actions.md e se comporta como qualquer valor fora do enum; e o baseline 233/4 segue só registrado no gate, sem reexecução em ambiente.
