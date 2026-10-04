---
protocol_version: 1
debate_id: BUG-20261004-ODCS-r1
bug_id: BUG-20261004-ODCS
role: solver
solver_id: agente-2
engine: local
round: 1
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Leitura da regra
- Nome conforme a spec: `enum_base_territorial`, aplicada ao campo real `extensao_territorial` (FieldType.TEXT). "Base territorial" existe só como texto de documento (golden set); o actions.md usa `base_territorial` como se fosse field_code, mas esse código não existe no catálogo. Mantém-se o nome da regra e registra-se o mapeamento na docstring (sem renomear campo, contrato v1.0.0).
- Enum fechado (actions.md D2-P0-3) com grupos de aliases: brasil; eua|estados unidos; canada; europa; america latina; america do sul; america do norte; mundo|mundial|worldwide; internacional; exterior.
- Aceite por igualdade EXATA do token normalizado contra o conjunto de aliases, nunca por substring ("não cobre américa do sul" não pode passar). Normalização: `normalize_text` (domain/value_types.py) já gera minúsculas, sem acentos (NFKD) e espaços colapsados, então caixa/acentos nunca decidem aceite ("Mundial", "Canadá", "MUNDIAL" passam sem regra extra).
- Valor legítimo fora do enum (ex.: "Atlântico Norte", "Canadá e Estados Unidos") não é erro: rebaixa FOUND para NEEDS_REVIEW + requires_human_review=true + `value["rule_violations"]` com rule="enum_base_territorial" e motivo sanitizado (regra/campo, nunca o valor, T-2a). É sinal ao revisor, como `moeda_consistente`.
- Escopo: dispatch por `field.code` (só `extensao_territorial`); NOT_FOUND, valor None, texto vazio e AMBIGUOUS não recebem regra, mesmo padrão das 4 regras atuais.

## Causa raiz proposta
- D2-P0-3 entregou 4 das 5 regras: `_rule_enum_base_territorial` nunca foi escrita em domain/rules.py nem somada em `validate_fact` (hoje só `valor_positivo`, `moeda_conhecida`, `moeda_consistente`, `vigencia_ordem`). O adendo §6.1 copiou a intenção do plano como se estivesse implementada: registro de execução otimista, não decisão de descarte.

## Teste
- Reprodução (vermelho antes do fix): ExtractionService + StubAgent com `extensao_territorial` FOUND, value={"text": "Atlântico Norte", "raw_text": ...} e evidência ancorada: hoje sai FOUND sem rule_violations; com a regra, NEEDS_REVIEW + requires_human_review=true + rule_violations=[enum_base_territorial] e o motivo não ecoa o valor.
- Unidade em test_rules.py: válidos ("Brasil", "Mundial", "MUNDIAL", "Canadá", "Estados Unidos", "eua", "worldwide") com 0 violações; inválidos ("Atlântico Norte", "mundial exceto brasil", este como armadilha de substring) com 1 violação; None/NOT_FOUND com 0. Ajustar `test_texto_nao_recebe_regras_de_valor` ("mundial" segue aceito, agora por pertencer ao enum; nome obsoleto).
- Regressão: suíte completa (baseline 233 passed, 4 skipped); fixtures apolice_a/b ("Mundial"/"Brasil") e golden set ("Mundo", "Estados Unidos") seguem FOUND sem violação; comparação, export e revisão inalterados.

## Impacto sobre a spec
- RECOMENDAÇÃO de veredito: spec-correta. As quatro fontes normativas (plano D2-P0-3 "falha → NEEDS_REVIEW, nunca FOUND"; actions.md D2-P0-3 com o enum fechado; adendo §6.1; sdd RF-02/RF-03) concordam no comportamento exigido e nenhuma registra retirada da regra; o código está atrás da intenção. O fix implementa a regra, documenta o mapeamento nome/campo e corrige a frase falsa do adendo (correção factual de registro, não de norma).
- Gap semântico menor a registrar no fix (não muda o veredito): lista canônica de aliases e destino de valores compostos.
- Consumidores: fila de revisão cresce (valores fora do enum caem lá, loop Confirmar/Corrigir cobre); comparação não muda (NEEDS_REVIEW compara o valor cru até a decisão humana, D2-P0-2); export passa a levar rule_violations (já previsto no contrato v1.0.0); quality report classifica regra violada como ALTO (application/quality.py).

## Riscos e efeitos colaterais
- Valores compostos legítimos ("Estados Unidos e Canadá") caem em NEEDS_REVIEW: aceitável (sinal, não erro), mas aumenta o trabalho do revisor; cobrir compostos exige ampliar aliases por decisão explícita de spec, nunca substring.
- O caminho de correção humana (application/review.py::record_decision) NÃO chama `validate_fact`: hoje o revisor grava valor fora do enum sem guarda e o `confirm` segue autoridade. Se um fix futuro passar a revalidar a correção, valor legítimo fora do enum ficaria bloqueado; por isso o escape do revisor deve ser preservado.
- Renomear o teste existente gera ruído de diff; golden set não tem caso fora do enum (a regressão do rebaixamento fica só nos testes novos).
- Vocabulário divergente (regra `enum_base_territorial` vs campo `extensao_territorial`) pode confundir quem lê rule_violations; mitigado pela docstring.

## Evidências
- evidence/rules-py-docstring-regras.txt e src/modules/policy_analysis/domain/rules.py: 4 regras, sem enum.
- evidence/adendo-dev2-003-afirma-enum.txt, actions.md D2-P0-3 (enum fechado) e plano-acao-dev2.md D2-P0-3.
- domain/value_types.py::normalize_text; application/extraction.py::_apply_field_guards (validate_fact só em FOUND) e ::_apply_cross_field_rules; application/review.py (sem validate_fact); application/quality.py (rule_violations → ALTO).
- tests/modules/policy_analysis/test_rules.py::test_texto_nao_recebe_regras_de_valor, fixtures apolice_a/b e golden_set.json (todos os valores dentro do enum).

## Confiança
alta: fontes de spec concordantes e código lido por inteiro; permanece aberto só o gosto de produto sobre valores compostos fora do enum.

## Crítica às demais propostas
- agente-1: leitura correta e bem alinhada (nome da regra vs campo, igualdade de token sem substring, rebaixamento como sinal). Fragilidades: (a) afirma que o "loop Confirmar/Corrigir já cobre" sem notar que review.py não reexecuta `validate_fact`, ou seja, hoje não há guarda nenhuma na correção e um fix futuro de revalidação bloquearia valor legítimo fora do enum; (b) não observa o efeito no quality report (ALTO) nem cita baseline numérico da regressão; (c) diz que "gate T-1 ... seguem verdes" sem detalhar a asserção que garante isso.
- agente-3: contribui útil ao registrar a armadilha de substring ("mundial exceto brasil"), que adoto no plano de teste. Erro factual a corrigir: afirma que "correção humana fora do enum passa a devolver ContractValidationError" e recomenda citar o `confirm` como escape; `validate_fact` só é chamado em application/extraction.py, e application/review.py apenas registra decisões, então hoje a correção não falha e o risco descrito não existe. Também traz a relação "related-to" com BUG-20261004-YFN3 sem evidência no material do debate (fora do escopo da rubrica) e rotula "Global" como valor composto legítimo, quando na verdade é sinônimo fora do enum e corretamente rebaixa.
- Convergência final: os três mantêm `enum_base_territorial` mirando `extensao_territorial` com normalização via `normalize_text` e rebaixamento para NEEDS_REVIEW, e os três recomendam spec-correta; a rodada reforça o veredito e só refina o destino da correção humana e o plano de teste.
