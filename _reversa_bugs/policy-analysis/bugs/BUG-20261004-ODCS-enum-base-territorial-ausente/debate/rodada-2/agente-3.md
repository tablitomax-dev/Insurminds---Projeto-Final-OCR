---
protocol_version: 1
debate_id: BUG-20261004-ODCS-r2
bug_id: BUG-20261004-ODCS
role: solver
solver_id: agente-3
engine: local
round: 2
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

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

- agente-1: acerta que o gap de nome vive no proprio registro normativo (actions.md escreve `base_territorial` como field_code inexistente) e detecta o segundo registro falso do D2-P0-2, que verifiquei e confirmo. Ressalva: propoe "corrigir junto" sem separar em registro proprio; mexer no fluxo de revisao dentro deste fix mistura escopos e aumenta o risco de regressao.
- agente-2: melhor evidencia de consumidores (review.py sem validate_fact, quality.py ALTO, baseline 233/4) e melhor plano de teste. Ressalva: tratar o caminho sem revalidacao como "escape do revisor a preservar" contradiz a spec do D2-P0-2, que exige validate_fact em `correct` e isenta so `confirm`; e rotular de hipotese futura o que a nota de execucao afirma como presente hoje repete o mesmo erro de registro que gerou este bug.
- Convergencia final: os tres mantem `enum_base_territorial` sobre `extensao_territorial`, normalizacao por `normalize_text`, igualdade exata, rebaixamento para NEEDS_REVIEW e veredito spec-correta; a rodada 2 so fecha o destino da correcao humana e separa a divergencia do D2-P0-2.
