# Relatório de auditoria pós-merge — PR #8 (`feature/dev2-policy-analysis-slice`)

> Data: `2026-09-29` (ISO 8601) · Auditor: assistente do **Dev 1**
> Destinatário: **pbena** (confidencial — encaminhar ao Dev 2 a critério do destinatário)
> Intervalo auditado: `7bd6cec..95fc44f` (7 commits do fluxo do Dev 2, PR #8)
> Escopo: sincronização completa do `main` + verificação de integridade do código, configurações e documentação, com foco nas entregas do Dev 1.

## 1. Resumo executivo

- **Dev 1: 100% preservado.** Nenhum arquivo do nosso quadrado foi tocado (diff vazio em `src/modules/document_processing/**`, `src/shared_kernel/**`, `tests/modules/document_processing/**`, `tests/integration/**`, `tests/fixtures/**`, `tests/contracts/**`). Contrato v1.1.0 e `content_fingerprint` intactos; nossos adendos (002, 004, 005, `decisao-export-markdown.md`) intactos.
- **Porém o `main` está FUNCIONALMENTE QUEBRADO após o merge:** 2 arquivos com **erro de sintaxe**, código duplicado em 6 arquivos do módulo `policy_analysis` e **18 erros de coleta** — nenhum teste roda (inclusive os nossos: `test_quality.py`, `test_metrics.py`, e2e e ui). O gate `T-1` não passa.
- Causa raiz: o merge `4318274` ("Merge branch 'main' into feature/dev2-policy-analysis-slice") **concatenou** os dois códigos em vez de unificá-los — em `extraction.py` o corte acontece **no meio de uma expressão**.

## 2. Achados

### C1 — CRÍTICO · Arquivos com sintaxe inválida (nada roda)
| Arquivo | Evidência |
|---------|-----------|
| `src/modules/policy_analysis/application/extraction.py` | `SyntaxError: '(' was never closed` (mypy/pytest); linhas 75–79: `return ExtractedFact(` do bloco do Dev 2 é **cortado no meio** e na linha 79 começa o docstring do arquivo antigo do Dev 1/fluxo anterior |
| `src/modules/policy_analysis/infrastructure/duckdb_repository.py` | 7 erros de sintaxe do ruff (`invalid-syntax`) nas linhas 129, 324–325 e 472 (ex.: `rows = self._conn.execute(` com indentação órfã após função encerrada) |

Impacto: `python -m pytest` aborta na coleta (18 errors); `mypy` para no primeiro erro ("errors prevented further checking"); ruff reporta **62 erros**.

### C2 — CRÍTICO · Código duplicado/empilhado (redefinições silenciosas)
| Arquivo | Duplicação |
|---------|------------|
| `application/extraction.py` | **2 classes `ExtractionService`** (linhas 24 e 118) — em Python a última definição vence; a primeira fica morta |
| `public_api.py` | **2 classes `PolicyAnalysisFacade`** (linhas 21 e 107) + duas árvores de import (a do Dev 2 no topo; a do fluxo anterior no meio, linha 83+ — E402) + `ExtractedFact`/`ComparisonService`/`ExtractionService`/`ComparisonResult` importados 2× (F811) |
| `application/review.py` | 12 erros ruff — mescla de `ReviewService` (Dev 2) e `HumanReviewService` (fluxo anterior) |
| `domain/comparison.py` | 8 erros — mescla de duas implementações de comparação/normalização |
| `tests/.../test_comparison.py` | 2 blocos de teste concatenados (docstring/imports no meio do arquivo, linha 124+; `make_fact` redefinido) |
| `tests/.../test_architecture.py` | imports após código (E402) — arquivo concatenado |

Incompatibilidades de assinatura entre as cópias (agrava o risco de quem "vencer"):
- `PolicyAnalysisFacade.export_comparison`: Dev 2 = `(comparison_id) -> str`; fluxo anterior = `(comparison_id, export_dir=...) -> Path`.
- `ExtractionService.__init__`: Dev 2 = `(evidence_source, agent, repo)`; fluxo anterior = `(retriever, extractor, repository, ...)`.

### C3 — ALTO · Suíte de testes não roda
18 erros de coleta atingem tanto os testes do Dev 2 (`test_e2e_flow`, `test_extraction_agent`, `test_repository`, `test_review_queue`, `test_explanation`, `test_export_markdown`) quanto **os nossos** (`tests/modules/policy_analysis/test_quality.py`, `test_metrics.py`, `tests/e2e/*`, `tests/ui/*`). Gate `T-1` (obrigatório antes de PR, convenção §5.3) não estava verde no momento do merge.

### C4 — MÉDIO · Método: artefato da extração editado diretamente
`_reversa_sdd/sdd/policy-analysis.md` foi **modificado** (OQ-04 marcada como resolvida). Pelo método (regra do Reversa + `/reversa-sync`), artefatos da extração não se alteram — superação é via **adendo**. Nós já temos o adendo canônico `_reversa_sdd/addenda/decisao-export-markdown.md` (decisão do **humano pbena**, 2026-09-27). A marcação na spec atribui a decisão ao Dev 2 com data `2026-09-26` — datas/donos divergem entre spec e adendo.

### C5 — MÉDIO · Numeração de feature duplicada
`_reversa_forward/001-dev2-policy-analysis-slice` colide com `_reversa_forward/001-vertical-slice-e2e` (dois prefixos `001`). Idem para o adendo `001-dev2-policy-analysis-slice.md`. Risco: ambiguidade de referência nos próximos ciclos.

### C6 — BAIXO · `CLAUDE.md` editado fora da política de allowedPaths
O Dev 2 acrescentou a "Regra perpétua de entregas (commits, PRs e pushes) — Dev 2". Conteúdo **convergente** com a nossa convenção §5.6 (`aprendizados.md`, decisão perpétua de pbena de 2026-09-27), sem conflito literal, mas duplicado em dois lugares — e `CLAUDE.md` está **fora** de `allowedPaths` da política de edição do legado. O acréscimo do handoff em `_reversa_sdd/learning/handoffs/` é novo e útil.

### C7 — INFO · `requirements.txt` muda a política de dependências
`pydantic-ai>=0.2` e `duckdb>=1.0` entraram como dependências **do núcleo** (antes estavam como extras comentadas). Efeito colateral: o ambiente mínimo de testes deixa de ser "pydantic + pytest".

## 3. Preservação das entregas do Dev 1 (verificada item a item)

| Item do Dev 1 | Estado |
|---------------|--------|
| `src/modules/document_processing/**` (pipeline, chunking, adapters, fingerprint) | ✅ intacto (diff vazio) |
| `src/shared_kernel/contracts.py` (`content_fingerprint`) e `version.py` (`CONTRACTS_VERSION = "1.1.0"`) | ✅ intactos |
| `tests/modules/document_processing/**`, `tests/fixtures/*.pdf`, `tests/integration/*` (opt-in offline) | ✅ intactos |
| `tests/contracts/**` (guard v1.1.0) | ✅ intacto |
| Adendos `002`, `004`, `005` e `decisao-export-markdown.md` | ✅ intactos |
| Convenções `aprendizados.md` (§5.2 caixa postal, §5.6 regra perpétua) | ✅ intactas |
| Nossos módulos da feature 004 (`domain/quality.py`, `domain/metrics.py`, `infrastructure/pricing.py`, `src/ui/logic.py`, `src/composition_root/`) | ✅ existentes; porém **inutilizáveis no momento** enquanto o módulo `policy_analysis` não compila (C1) |

## 4. Recomendações (para decisão do destinatário)

1. **Não partir de `main` para novas features até o C1/C2 serem resolvidos** — a base não compila.
2. Resolver a duplicação em `extraction.py`, `public_api.py`, `review.py` e `comparison.py` **escolhendo UMA arquitetura por módulo** (sugestão: a do Dev 2 como base do `policy_analysis`, reconectando as costuras aditivas do fluxo anterior que devem sobreviver — `QualitySignalLog`, `UsageMetricsCollector`, `pricing`, `human review` — ou explicitamente descontinuando-as via decisão registrada).
3. Corrigir a sintaxe de `extraction.py` (linhas 75–79) e `duckdb_repository.py` (linhas 129/324/472) e depois rodar o gate `T-1` completo até verde (§5.3).
4. Alinhar a marcação da OQ-04 na spec ao adendo canônico (`decisao-export-markdown.md` — decisão do humano, 2026-09-27) ou consolidar por re-extração.
5. Renumerar uma das features `001-*` para evitar colisão (ex.: `006-dev2-policy-analysis-slice`).
6. Unificar a regra perpétua de entregas num lugar só (`aprendizados.md` §5.6) e deixar o `CLAUDE.md` apontar para ela.

## 5. Desfecho da operação de conserto (2026-09-29)

Decisões do humano (pbena): **a arquitetura do Dev 2 prevalece**; as features 003/004 são **reimplementadas sobre ela**; os formatos do Dev 2 (comparação/explicação/export) prevalecem e os consumidores (UI/evaluation) se adaptam.

Executado:
1. **Restauração dos 7 arquivos empilhados** a partir do commit puro do Dev 2 (`717fc8e`): `extraction.py`, `public_api.py`, `review.py`, `domain/comparison.py`, `duckdb_repository.py`, `test_comparison.py`, `test_architecture.py` — sintaxe 100% recuperada.
2. **Costuras 003/004 reimplementadas sobre o Dev 2:** fachada única estendida com `list_issues`/`get_quality_report`/`get_comparison_quality_report`/`get_usage_metrics` + `list_fields`/`normalize_field_value`/`get_evidences` + fábricas (`create_policy_analysis`, `create_default_policy_analysis`, `create_document_processing_evidence_source`); `QualityService`/`QualitySignalLog` adaptados (duck-typed repo; evidências via `EvidenceSource`); instrumentação de métricas nos agents do Dev 2 (`MultiFieldExtractionAgent`/`LLMExplanationAgent` com `usage_collector=`) + log estruturado `policy_analysis.usage`.
3. **Consumidores adaptados:** `src/ui/**` (comparação por `campos`, export `-> str`, revisão por `ReviewItem`/`record_review_decision`, `ClassifiedError` no lugar de `LlmOutputError`), `src/composition_root/**`, `src/modules/evaluation/**` (porta: `get_evidences`), testes e2e/ui/integration/módulo + fakes.
4. **Módulos órfãos do mundo anterior removidos:** `application/ports.py`, `application/comparison.py`, `domain/catalog.py`, `domain/rules.py`, `domain/anchoring.py`, `domain/review.py`, `infrastructure/llm_extractors.py`, `infrastructure/document_retriever.py` (+ 6 arquivos de teste que os cobriam).
5. **Defeito real corrigido:** `UsageMetricsCollector.record` quebrava com `KeyError` para `run_id` externos (o `ExtractionService` do Dev 2 gera `run_id` próprio) — agora cria o run em memória.
6. **Gate `T-1` verde 3× consecutivas:** `ruff` All checks passed · `mypy` Success (64 arquivos) · `pytest` **258 passed, 4 skipped**.

Itens observados (para decisão futura, sem bloqueio):
- Guardas de extração do ciclo anterior (regras por campo `domain/rules.py`, ancoragem `domain/anchoring.py`) ficaram de fora — substituídas pelas validações do Dev 2 (`value_types` + `_build_fact`); o ramo `ALTO` da governança só ocorre se o fato vier com `value["rule_violations"]`.
- A UI não lista decisões de revisão já registradas (o `ReviewService` do Dev 2 só expõe pendentes) e o valor corrigido é enviado como `{"text": ...}` (campos não-texto podem levantar `NormalizationError`, sanitizada na UI).
- `src/modules/evaluation/fixtures/golden_set.json` realinhado aos códigos do catálogo novo (zona compartilhada — registro do agente executor).
- Continuam pendentes (decisões do humano): colisão de numeração `001-*` em `_reversa_forward/`; marcação da OQ-04 na spec vs adendo canônico; regra perpétua duplicada (CLAUDE.md × `aprendizados.md` §5.6).

## 6. Método da auditoria

- `git fetch --all` + comparação `7bd6cec..95fc44f` (log, diff --stat por área, diff linha a linha nos arquivos compartilhados).
- Verificação de presença/conteúdo dos símbolos do Dev 1 (`compute_content_fingerprint`, `content_fingerprint`, `CONTRACTS_VERSION`, fixtures, adendos).
- Gate `T-1` completo (`ruff` 62 erros · `mypy` para em erro de sintaxe · `pytest` 18 erros de coleta).
