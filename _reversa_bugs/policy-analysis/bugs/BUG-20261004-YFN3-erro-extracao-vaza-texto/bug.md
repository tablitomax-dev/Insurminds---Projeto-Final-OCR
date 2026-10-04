---
schema_version: 1
id: BUG-20261004-YFN3
display_number: 1
title: Erro de validação na extração interpola ValidationError cru e vaza texto de apólice
status: resolved
phase: testing
severity: medium
priority: P0
created: 2026-10-04
updated: 2026-10-04
express: true

origin:
  type: inspection
  external_ref: null

area: policy-analysis
module: policy_analysis
feature: extracao
labels: [t2a, higiene-de-dados]

visibility: internal
security_suspected: false

reproduction:
  classification: deterministic
  rate: "1/1"
  suspected_triggers: []

blocking: []
relationships: []

traceability:
  specs:
    - "_reversa_sdd/sdd/policy-analysis.md#12-seguranca-e-privacidade"
    - "_reversa_sdd/sdd/policy-analysis.md#61-requisitos-principais"
    - "_reversa_sdd/learning/plano-acao-dev2.md#transversal-sua-manutencao"
    - "_reversa_sdd/addenda/dev2-003-p0-analise-experiencia.md#61-requisitos-funcionais"
  affected_code:
    - "src/modules/policy_analysis/application/extraction.py"
  root_cause:
    state: confirmed
    hypothesis: "O except de ValidationError em _build_fact monta a mensagem com f-string sobre o ValidationError cru (eco do input) e mantém o erro vivo na cadeia via `from exc`."
    causal_path:
      - "LLM devolve saída fora do schema do ExtractedFact"
      - "ExtractedFact.model_validate levanta ValidationError cujo str()/errors() contêm o input (valor da apólice)"
      - "extraction.py interpola `{exc}` na mensagem do ClassifiedError e re-lança `from exc`"
      - "mensagem, to_dict(), to_processing_status e traceback renderizam o texto da apólice"
    evidence:
      - {ref: "evidence/extracao-py-l135-140.txt", observation: "código antes do fix com `{exc}` + `from exc`"}
      - {ref: "evidence/reproduction.md", observation: "teste vermelho com o marcador visível na mensagem; verde após o fix"}
      - {ref: "evidence/rota-descartada-dev2-003.txt", observation: "decisão registrada descartava exatamente str(exc)/msg por conterem input"}
    code_refs:
      - {file: "src/modules/policy_analysis/application/extraction.py", symbol: "ExtractionService._build_fact", commit: "1784ad9"}
  reproduction_tests:
    - "tests/modules/policy_analysis/test_extraction_agent.py::test_erro_de_schema_nao_ecoa_texto_de_apolice"
  regression_tests:
    - "tests/modules/policy_analysis/test_extraction_agent.py::test_erro_de_schema_nao_ecoa_texto_de_apolice"
    - "tests/modules/policy_analysis/test_extraction_agent.py::test_saida_fora_do_schema_nunca_vira_fato"
    - "tests/ui/test_error_sanitization.py"

spec_verdict: spec-correta
change_set:
  - id: CHG-001
    kind: test
    artifact: tests/modules/policy_analysis/test_extraction_agent.py
    purpose: "reprodução + anti-vazamento T-2a (marcador ausente de str/repr/to_dict/to_processing_status/traceback + guarda from None)"
    diff: fix/CHG-001.diff
  - id: CHG-002
    kind: code
    artifact: src/modules/policy_analysis/application/extraction.py
    purpose: "mensagem do ClassifiedError só com tipo + quantidade + field_code; `from exc` vira `from None`"
    diff: fix/CHG-002.diff

closure:
  policy: local-software
  satisfied: true
resolution_kind: fixed
---

# Erro de validação na extração interpola ValidationError cru e vaza texto de apólice

## Summary

Quando o LLM devolve saída fora do contrato, `application/extraction.py` monta a mensagem do
`ClassifiedError` interpolando `str(exc)` do Pydantic. O `ValidationError` do Pydantic ecoa o
input da validação, que é o valor extraído da apólice: o texto do documento vaza pela mensagem de
erro (e chega a logs/cadeia de exceções). Viola a regra T-2a do plano de ação Dev 2 (nunca
`ValidationError` crua; tipo + estágio + IDs) e a rota de sanitização decidida no registro da
feature dev2-003 ("Alternativa descartada: manter `str(exc)`/`exc.errors()[...][\"msg\"]` (ambos
podem conter o input)").

## Expected Behavior

- Spec efetiva:
  - `_reversa_sdd/sdd/policy-analysis.md` §12 Segurança e Privacidade: "nenhum texto integral em
    logs"; trechos de apólice só seguem para o Gemini e para citações mínimas do export.
  - `_reversa_sdd/sdd/policy-analysis.md` §6.1 RF-09: saída fora do schema nunca vira fato e é
    "registrada como falha classificada" (erro classificado, sem eco do input).
  - `_reversa_sdd/learning/plano-acao-dev2.md` (T-2a, seção Transversal): sanitização de exceções,
    "nunca `ValidationError` crua; tipo + estágio + IDs; teste anti-vazamento".
  - `_reversa_sdd/addenda/dev2-003-p0-analise-experiencia.md` §6.1: "erros sanitizados".
- O `ClassifiedError` deve carregar código (`LLM_SCHEMA_INVALID`), campo (`field_code`) e
  quantidade/tipos de erro de schema, sem nenhum fragmento do input.

## Actual Behavior

`application/extraction.py` linhas 135-140:

```python
except ValidationError as exc:
    raise ClassifiedError(
        "LLM_SCHEMA_INVALID",
        f"saída do LLM fora do contrato em {req.field_code}: {exc}",
        retriable=True,
    ) from exc
```

`f"...: {exc}"` chama `str(exc)` do Pydantic, que imprime o valor de input de cada campo com
erro. Não existe teste anti-vazamento específico para este caminho (o teste anti-vazamento
existente cobre o caminho de métricas/LLM).

## Steps to Reproduce

1. Executar `ExtractionService` com um agente fake que devolve saída fora do schema do
   `ExtractedFact` (ex.: campo obrigatório ausente ou tipo inválido) com um marcador de apólice
   dentro do valor rejeitado (ex.: "SEGREDO-APOlice-XYZ").
2. Capturar o `ClassifiedError` levantado.
3. Observar `str(exc)` do erro: o marcador da apólice aparece na mensagem.

## Evidence

- `evidence/extracao-py-l135-140.txt` (trecho do código)
- `evidence/rota-descartada-dev2-003.txt` (decisão registrada na feature que o código não cumpre)
- Relato de origem: `../intake/relato-20261004-1030.md`

## Suspected Area

- `src/modules/policy_analysis/application/extraction.py` (catch de `ValidationError` do
  `ExtractedFact.model_validate`).
- Mesmo padrão de eco de `str(exc)` aparece em pontas internas
  (`application/errors.py`, `infrastructure/llm_agent.py`,
  `infrastructure/document_processing_source.py`) que hoje não são exibidas pela UI; o fix decide
  se estende a sanitização ou restringe ao caminho do `ClassifiedError` (ver Agent Notes).

## Acceptance Criteria

- A mensagem do `ClassifiedError` do caminho acima traz apenas: código do erro, `field_code`,
  tipo da exceção e quantidade de problemas de schema; zero fragmentos do input.
- Teste anti-vazamento específico para este caminho: fake de agente devolve saída inválida com
  marcador de apólice no valor rejeitado; o teste prova que o marcador não aparece em
  `str(exc)` da exceção levantada.
- Testes existentes continuam verdes (o erro continua classificado como `LLM_SCHEMA_INVALID`,
  `retriable=True`).

## Traceability

- Specs: `_reversa_sdd/sdd/policy-analysis.md` §12 e §6.1 (RF-09); `_reversa_sdd/learning/plano-acao-dev2.md`
  (T-2a); `_reversa_sdd/addenda/dev2-003-p0-analise-experiencia.md` §6.1.
- Código afetado: `src/modules/policy_analysis/application/extraction.py`.
- Causa raiz: preenchida pelo fix.

## Resolution

- **Root cause (confirmed):** o `except ValidationError` de `_build_fact`
  (`application/extraction.py`) interpolava `str(exc)` do Pydantic na mensagem do
  `ClassifiedError` (o `str`/`errors()` do `ValidationError` ecoa o `input`, que é o valor
  extraído da apólice) e re-lançava `from exc`, mantendo o erro cru renderizável em
  traceback/log. Mecanismo comprovado pela reprodução vermelha (marcador visível na mensagem).
- **Veredito de spec (aprovado pelo usuário em 2026-10-04):** `spec-correta` — T-2a
  (plano-acao-dev2), `policy-analysis.md` §12 ("nenhum texto integral em logs") e §6.1 RF-09
  já exigiam a sanitização; o código divergiu. Nenhum adendo necessário.
- **resolution_kind:** `fixed`.
- **Change set:**

| CHG | Tipo | Artefato | Propósito | Diff |
|-----|------|----------|-----------|------|
| CHG-001 | test | tests/modules/policy_analysis/test_extraction_agent.py | reprodução + anti-vazamento T-2a | fix/CHG-001.diff |
| CHG-002 | code | src/modules/policy_analysis/application/extraction.py | mensagem sanitizada (tipo + quantidade + field_code) + `from None` | fix/CHG-002.diff |

- **Prova vermelho → verde:** vermelho em 2026-10-04 (7 failed; o marcador
  `TEXTO-CONFIDENCIAL-APOLICE-XYZ` aparecia na mensagem do `ClassifiedError`); verde após o fix
  (`50 passed` nos arquivos tocados; suíte completa `346 passed, 4 skipped`; `ruff` e `mypy`
  limpos). Comandos e taxas em `evidence/reproduction.md`.
- **Testes:** reprodução/anti-vazamento `test_erro_de_schema_nao_ecoa_texto_de_apolice`
  (str, repr, `to_dict`, `to_processing_status`, traceback formatado + guarda
  `__cause__`/`__suppress_context__` da decisão `from None`); regressão coberta pelo mesmo
  guard, por `test_saida_fora_do_schema_nunca_vira_fato` e pela suíte de sanitização de UI.
- **Decisões do debate (resposta-final.md):** mensagem minimalista no padrão T-2a canônico
  (`_cause`/`_with_retries`); `from None` com plano B documentado (zerar `__context__` por
  reestruturação do try, não executado); escopo cirúrgico limitado ao `except` do bug.
- **Fora do change set (follow-up próprio):** ecos residuais de `str(exc)` em
  `infrastructure/llm_agent.py:267` e `infrastructure/document_processing_source.py:30`;
  promoção de relação com BUG-20261004-ODCS (retirada como ruído de processo).

## Agent Notes

- Severidade `medium` e prioridade `P0` assumidas na rota expressa pelo agente de registro
  (T-2a é declarado P0 no plano de ação Dev 2; o estrago é vazamento em mensagem de erro/logs,
  e a UI já sanitiza mensagens exibidas).
- Origem: item apontado em auditoria de pendências de 2026-10-04 e aceito pelo usuário como
  correção a fechar (rota expressa).
- Relação `related-to` provável com BUG-20261004-ODCS (mesma auditoria, mesmo módulo) não foi
  gravada: a rota expressa pula a correlação; o fix pode promovê-la.
- Restrição T-2a para o fix: o motivo/erro nunca carrega valor, só tipo/contagem/IDs.