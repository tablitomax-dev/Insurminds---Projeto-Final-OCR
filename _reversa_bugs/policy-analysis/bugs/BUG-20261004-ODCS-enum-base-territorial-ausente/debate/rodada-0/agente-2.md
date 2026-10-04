---
protocol_version: 1
debate_id: BUG-20261004-ODCS-r0
bug_id: BUG-20261004-ODCS
role: solver
solver_id: agente-2
engine: local
round: 0
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Leitura da regra
- Nome da regra conforme a spec: `enum_base_territorial`, aplicada ao campo real do catálogo `extensao_territorial` (FieldType.TEXT). "Base territorial" é só texto de documento (golden set), não um field_code; não deve entrar no catálogo nem virar campo novo.
- Enum fechado (actions.md D2-P0-3): brasil; eua/estados unidos; canadá; europa; américa latina; américa do sul; américa do norte; mundo/mundial/worldwide; internacional; exterior. Os grupos com barra são aliases do mesmo valor.
- Aceite por comparação sobre o valor normalizado: `normalize_text` (domain/value_types.py) já gera minúsculas, sem acentos (NFKD) e espaços colapsados, então os tokens canônicos são "brasil", "eua", "estados unidos", "canada", "europa", "america latina/sul/norte", "mundo", "mundial", "worldwide", "internacional", "exterior". Caixa e acento nunca decidem aceite ("Mundial", "MUNDIAL", "Canadá" passam sem regra extra).
- Valor legítimo fora do enum (ex.: "Atlântico Norte", "Estados Unidos e Canadá") não é erro: rebaixa FOUND para NEEDS_REVIEW + requires_human_review=true, com `value["rule_violations"]` trazendo rule="enum_base_territorial" e motivo sanitizado (só regra/campo, nunca o valor, T-2a). É sinal ao revisor, como `moeda_consistente`.
- Fora da regra: NOT_FOUND, valor não normalizável (EC-04 já trata) e textos vazios; `validate_fact` hoje só roda em FOUND (extraction.py), e isso permanece.

## Causa raiz proposta
- A execução de D2-P0-3 entregou 4 das 5 regras: `_rule_enum_base_territorial` nunca foi criada em domain/rules.py nem somada em `validate_fact`. As notas do actions.md e o adendo §6.1 descreveram as 5 regras copiando a intenção do plano, então a divergência nasce de registro de execução otimista (afirmação falsa sobre o código), não de decisão deliberada de descartar a regra.

## Teste
- Reprodução: ExtractionService + StubAgent com `extensao_territorial` FOUND, value={"text": "Atlântico Norte", "raw_text": "Trecho da apólice"} e evidência EV-A-001 ancorada: hoje sai FOUND sem rule_violations (teste fica vermelho); com a regra, NEEDS_REVIEW + requires_human_review=true + rule_violations=[enum_base_territorial] sem ecoar o valor.
- Unidade: válidos ("Brasil", "Mundial", "Estados Unidos", "Canadá", "eua", "worldwide") sem violação; inválido ("Atlântico Norte") dispara; motivo nunca contém o valor (padrão de test_motivo_da_regra_nunca_traz_o_valor).
- Regressão: suíte completa (baseline 233 passed, 4 skipped); fixtures apolice_a/b ("Mundial"/"Brasil") e golden set ("Mundo", "Estados Unidos") seguem FOUND sem violação; `test_texto_nao_recebe_regras_de_valor` mantém a asserção ("mundial" continua aceito) mas o nome fica obsoleto e pede renomeação; testes de comparação, export e revisão inalterados.

## Impacto sobre a spec
- RECOMENDAÇÃO: spec-correta. As quatro fontes da spec efetiva concordam em exigir a regra (plano D2-P0-3 "enums para base_territorial, falha → NEEDS_REVIEW nunca FOUND"; actions.md D2-P0-3 com o enum fechado; adendo §6.1; sdd RF-02/RF-03) e nenhuma registra descarte. O código está atrás da intenção normativa; o fix implementa a regra e corrige o registro de execução que afirma algo falso. Mantém-se o nome `enum_base_territorial` mirando `extensao_territorial`, com o mapeamento documentado na docstring (sem renomear o field_code).
- Consumidores: fila de revisão cresce (valores fora do enum caem lá); comparação não muda (NEEDS_REVIEW compara o valor cru antes da decisão humana, decisão registrada em D2-P0-2); export passa a levar rule_violations, já previsto no contrato v1.0.0; o quality report classifica regra violada como ALTO (application/quality.py).
- Pequeno gap de semântica a registrar no fix (não muda o veredito): lista canônica de aliases e destino de valores compostos.

## Riscos e efeitos colaterais
- Valores compostos legítimos ("Estados Unidos e Canadá") passam a NEEDS_REVIEW: aceitável (sinal, não erro), mas aumenta o trabalho do revisor.
- A correção humana hoje só normaliza (application/review.py não chama validate_fact), então o revisor ainda grava valor fora do enum e o `confirm` segue autoridade; se um fix futuro validar a correção com validate_fact, valor legítimo fora do enum ficaria bloqueado.
- Renomear o teste existente gera ruído de diff, e o golden set não tem caso fora do enum (a regressão do rebaixamento fica só nos testes novos).
- `NOT_FOUND` e AMBIGUOUS não recebem regra; mudar isso ampliaria o escopo além da spec.

## Evidências
- evidence/rules-py-docstring-regras.txt e domain/rules.py: docstring e implementação com 4 regras, sem checagem de enum.
- evidence/adendo-dev2-003-afirma-enum.txt, actions.md D2-P0-3 (enum fechado + "Regras implementadas" listando o enum) e plano-acao-dev2.md D2-P0-3.
- domain/value_types.py::normalize_text (caixa/acentos/espacos) e extraction.py::_apply_field_guards (validate_fact só em FOUND; violação rebaixa e anota rule_violations).
- tests/modules/policy_analysis/test_rules.py e fixtures apolice_a/b, golden_set.json ("Mundial", "Brasil", "Mundo", "Estados Unidos", todos dentro do enum).

## Confiança
alta: as fontes de spec são concordantes entre si e o código relevante foi lido por inteiro; só o destino de valores compostos fora do enum depende de gosto de produto.
