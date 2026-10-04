# Handoff — merge de `feature/dev2-policy-analysis-slice` no main (2026-10-04)

Registro detalhado (§5.6) da integração do trabalho do Dev 2 (pós-PR #11) ao `main`
já consolidado com os PRs #12/#13 (Dev 1) e #14 (bugs policy_analysis).

## 1. Escopo

Branch de integração `merge/dev2-policy-analysis-final` = `origin/main` (0dcde99,
PR #14 mergeado) + `origin/feature/dev2-policy-analysis-slice` (42dcced).

Commits trazidos do Dev 2 (5 de conteúdo):

- `2336499` — restaurar `enum_base_territorial` (D2-P0-3) + registrar OQ-02 (substring) + fix `datetime.utcnow`
- `8e6d18c` — handoff Dev 2 de 2026-10-01 (fechamento de pendências)
- `543dd8a` — UI: extração de todos os campos por passo + valores A/B formatados + launcher demo offline
- `ebc52f7` — UI: tela de consulta livre às evidências + relatório de aderência atualizado
- `42dcced` — adapters: chamadas reais dos SDKs Gemini (`embed_content` + `GoogleModel`) e modelo padrão `gemini-3.8-flash`

## 2. Arquivos/trechos modificados no merge

- `src/modules/policy_analysis/domain/rules.py` — **conflito de conteúdo**, resolvido
  mantendo a versão mais recente do `main` (`2f09adc`, 2026-10-04) em vez da do Dev 2
  (`2336499`, 2026-10-01): implementação do `enum_base_territorial` com dispatch por
  `field.code`, `_fold_text` e motivo sanitizado T-2a. A duplicata do Dev 2
  (`KNOWN_TERRITORY_BASES`, versão com `normalize_text`) foi descartada — vocabulários
  idênticos (13 tokens), comportamento equivalente.
- `tests/modules/policy_analysis/test_rules.py` — auto-merge ok; os dois blocos de
  testes de enum são preservados integralmente (Dev 2 + BUG-20261004-ODCS). A única
  adequação: renomeado o teste homônimo **do bloco mais recente** (nosso, parametrizado)
  para `test_enum_base_territorial_rejeita_compostos_fora_do_enum`, mantendo intactas as
  linhas do Dev 2 (`test_enum_base_territorial_rejeita_fora_do_enum` e demais) — o ruff
  F811 impedia a coexistência dos nomes idênticos.
- Demais 21 arquivos do Dev 2 entraram sem conflito (UI, adapters, docs, `pyproject.toml`).

## 3. Funcionalidades integradas

- UI: consulta livre às evidências (`src/ui/components/query.py`), extração por passo
  com valores A/B formatados (`stages.py`, `logic.py`, `comparison.py`), launcher
  `run_ui_demo.py` (demo offline).
- Infra: chamadas reais dos SDKs Gemini (`llm_agent.py`, `indexing.py`), modelo padrão
  `gemini-3.8-flash`, `duckdb_repository.py`, `root.py`, `public_api.py`.
- Docs: `decisions.md` (dev2-003), handoffs Dev 2 (10-01, 10-03), `relatorio-aderencia-escopo-projeto-final.md`.

## 4. Anti-conflito de merge

- Regra aplicada: **manter o arquivo mais recente** (decisão do usuário) — datas
  confirmadas via `git log -1 -- <arquivo>` por lado.
- Conflito único: `rules.py` (2 hunks: docstring + função do enum) → `git checkout --ours`
  (lado do `main`, mais novo) + remoção da duplicata `KNOWN_TERRITORY_BASES` vinda do Dev 2.
- Testes de ambos os lados preservados; em `test_rules.py`, o homônimo colidente
  (ruff F811) foi renomeado no bloco mais recente (nosso) para não tocar nas linhas do Dev 2.

## 5. Zonas compartilhadas

- `rules.py` (domínio policy_analysis) — zona Dev 1×Dev 2? Não: domínio do Dev 2, mas
  tocado pelo fix BUG-ODCS no PR #14; unificado na versão mais recente.
- `test_rules.py` — testes dos dois lados consolidados (sem duplicação).
- `pyproject.toml`, `src/composition_root/root.py` — alterações do Dev 2 aceitas
  (modelo padrão e wiring); `shared_kernel` não foi tocado.
- `document_processing` (`indexing.py`, `test_indexing.py`) — ajuste pontual do Dev 2
  (métrica/SDK), compatível com os PRs #12/#13.

## 6. Gate T-1 (resultado)

- `ruff check src tests` — All checks passed.
- `mypy src` — Success: no issues found in 69 source files.
- `pytest -q` — **371 passed, 4 skipped** (inclui testes novos de UI: `test_query.py`, `test_value_format.py`
  e os 3 testes de enum do Dev 2 preservados em `test_rules.py`).
