# Handoff Dev 2 — Entrega `001-dev2-policy-analysis-slice` (resumo para o assistente de IA do Dev 1)

> **Destinatário:** assistente de IA do Dev 1 (pbena) — leitura integral recomendada antes de revisar/integrar.
> **Data:** 2026-09-29 · **Autor:** Dev 2
> **Branch:** `feature/dev2-policy-analysis-slice` (4 commits, push pendente de permissão no GitHub)
> **Base:** `98e5bd3` (main antiga) — os commits NÃO contêm o código do fluxo paralelo (`001-vertical-slice-e2e`/P0); apenas o planejamento dele foi incorporado.

---

## 1. Visão geral do que foi desenvolvido

Implementação completa do **vertical slice do módulo `policy_analysis` (Dev 2)** pelo ciclo forward do Reversa (requirements → clarify → plan → to-do → coding → sync): extração de fatos de apólices D&O com LLM, validação total de saída, revisão humana, comparação determinística entre 2 apólices, explicação rastreável e export do resumo.

- **Código:** `src/modules/policy_analysis/` (camadas `domain` / `application` / `infrastructure` / `public_api`)
- **Testes:** `tests/modules/policy_analysis/` — **120 testes verdes** no total (67 de contrato da Fase 0 + 53 novos, incluindo E2E dos 7 cenários Gherkin)
- **Artefatos de planejamento/auditoria:** `_reversa_forward/001-dev2-policy-analysis-slice/` + adendo em `_reversa_sdd/addenda/`

## 2. Commits incluídos nesta entrega

| Commit | O que contém |
|--------|--------------|
| `e29c420` | Feature completa: módulo `policy_analysis`, 53 testes, demo ponta a ponta, artefatos do ciclo forward, adendo 001 |
| `cf00a49` | Planejamento complementar trazido do remoto (`_reversa_sdd/learning/` com `plano-acao-dev2.md`, features `001-vertical-slice-e2e`/`002`/`003` e adendos) + Reversa v1.3.4 + estado reconciliado |
| `9fcd8e1` | Export migrado de PDF para **Markdown** (decisão OQ-04 revisada) — `markdown_export.py` no lugar de `pdf_export.py` |
| `ac6d43a` | Export padronizado em **`exports/<ComparisonId>.md`** (alinhado ao fluxo paralelo) e **OQ-04 fechada na spec** `policy-analysis.md` |

## 3. Decisões fixadas (OQ-01..OQ-04 da spec `policy-analysis.md`)

| OQ | Decisão | Detalhe |
|----|---------|---------|
| OQ-01 | **Catálogo fechado de 10 `field_code`** | `limite_agregado`, `limite_por_sinistro`, `franquia`, `vigencia`, `prazo_notificacao_sinistro`, `extensao_territorial`, `exclusoes_chave`, `limite_defesa_custos`, `retroatividade`, `indice_reajuste` — com tipo de valor (MONEY/NUMBER/PERIOD/DATE/TEXT) e normalização por campo (`domain/field_catalog.py`) |
| OQ-02 | **Agente multi-campo** | 1 chamada de LLM por apólice extrai todos os campos (`infrastructure/llm_agent.py`) |
| OQ-03 | **Regras de comparação híbridas** | numérico/moeda (Decimal, BRL por taxa injetada)/data → maior/menor/igual; período → duração (janela deslocada = DIVERGENTE); texto livre → igual/divergente após normalização (semântica com o analista); ausente → diferença por omissão, nunca erro |
| OQ-04 | **Export Markdown standalone** | `exports/<ComparisonId>.md` — formato e caminho alinhados ao fluxo paralelo |

## 4. Arquitetura entregue (como ler o código)

```
src/modules/policy_analysis/
  domain/          value_types.py (Money/Period/normalização), field_catalog.py (10 campos),
                   models.py (FieldComparison/ComparisonResult/Explanation/ReviewItem),
                   comparison.py (função pura determinística — SEM LLM na comparação)
  application/     extraction.py, review.py, comparison_service.py, explanation.py,
                   export.py, errors.py (ClassifiedError + ProcessingStatus FAILED)
  infrastructure/  evidence_source.py (porta + mock), document_processing_source.py,
                   duckdb_repository.py (5 tabelas, upsert idempotente),
                   llm_agent.py (multi-campo, retry/backoff, PydanticAIClient, fixtures),
                   markdown_export.py
  public_api.py    PolicyAnalysisFacade — ÚNICA entrada do módulo
  demo.py          fluxo ponta a ponta offline (fixtures) ou com Gemini
```

**Fachada pública (o que o Dev 1/workflow consome):**

```python
PolicyAnalysisFacade(evidence_source, extraction_agent, explanation_agent, db_path, output_dir, currency_rates)
  .extract_field(policy_id, field_code) -> ExtractedFact
  .extract_fields(policy_id, field_codes) -> list[ExtractedFact]
  .get_facts(policy_id) -> list[ExtractedFact]
  .list_review_queue(policy_id=None) -> list[ReviewItem]
  .record_review_decision(fact_id, "CONFIRMADO"|"CORRIGIDO", decided_by, value=None) -> ExtractedFact
  .compare_policies(policy_id_a, policy_id_b) -> ComparisonResult   # ComparisonId determinístico/idempotente
  .explain_difference(comparison_id, field_code) -> Explanation      # exige citação dos DOIS lados
  .export_comparison(comparison_id) -> str                          # exports/<ComparisonId>.md
```

## 5. Fronteiras respeitadas (importante para a integração)

- **`src/shared_kernel/` NÃO foi modificado** — apenas consumido (`EvidenceRef`, `ExtractionRequest`, `ExtractedFact`, `ProcessingStatus`).
- **`document_processing` é consumido SOMENTE via `public_api`** — o único ponto de contato é `infrastructure/document_processing_source.py` (`DocumentProcessingEvidenceSource`), com import adiado. Teste de arquitetura garante isso (`tests/modules/policy_analysis/test_architecture.py`).
- **Desenvolvimento desbloqueado em paralelo:** `MockEvidenceSource` (fixtures) + agentes de fixture permitem rodar tudo offline. Para integração real, basta injetar `DocumentProcessingEvidenceSource` + `PydanticAIClient` — nenhum contrato muda (RF-10).
- `evaluation` e `src/ui/` **intocados** nesta entrega.

## 6. Comportamentos-chave para validar na integração

1. **LLM nunca compara** — a comparação é função pura em `domain/comparison.py` (RN-01 do PRD).
2. **Nada vira fato sem validação:** saída fora do schema → `ClassifiedError("LLM_SCHEMA_INVALID")`, nada persistido; `evidence_ids` inventados → `ClassifiedError("EVIDENCE_UNKNOWN")`; `FOUND` sem evidência é rejeitado pelo próprio contrato.
3. **Revisão humana é fluxo de 1ª classe:** `AMBIGUOUS`/`NEEDS_REVIEW` → fila com evidência anexa; a comparação do campo fica `AGUARDANDO_REVISAO` até a decisão (delta de enum registrado no adendo 001) — `CONFIRMADO`/`CORRIGIDO` auditados (quem/quando).
4. **Idempotência:** `ComparisonId` = UUIDv5 do par ordenado; re-extração/re-comparação não duplicam registros (DuckDB upsert = DELETE+INSERT em transação).
5. **Falhas nunca silenciosas:** retry com backoff (3x) no LLM; depois `ClassifiedError(code, retriable)` + `to_processing_status()` → `ProcessingStatus(stage="FAILED", message)`.

## 7. Como rodar

```powershell
cd Insurminds---Projeto-Final-OCR
.\.venv\Scripts\Activate.ps1        # venv já criado (Python 3.12.10)
$env:PYTHONDONTWRITEBYTECODE="1"    # o sandbox do Trae bloqueia escrita de .pyc
python -B -m pytest tests/ -q       # 120 testes (67 contratos + 53 novos)
$env:PYTHONPATH="src"
python -B -m modules.policy_analysis.demo   # demo ponta a ponta → exports/<ComparisonId>.md
```

## 8. Pendências e pontos abertos (para diálogo Dev 1 ↔ Dev 2)

| Item | Estado |
|------|--------|
| Push da branch para o GitHub | **Pendente de permissão** (conta `amitigiovani-prog` sem escrita no repo `tablitomax-dev/...`) |
| Divergência de granularidade de specs | `feature` (nosso config) vs `hybrid` (fluxo paralelo) — sem impacto funcional, decidir junto |
| Gaps do `plano-acao-dev2.md` nesta implementação | `D2-P0-1` parcial (validação de `evidence_ids`, falta ancoragem de substring no `quoted_text` + temperature 0); `D2-P0-2` parcial (falta "Registrar divergência"); `D2-P0-3` parcial (faltam regras como vigência início≤fim) |
| Gate `T-1` (ruff + mypy) | Não configurado neste branch |
| Reconciliação de código com o fluxo paralelo | Em aberto — nosso `policy_analysis` é implementação paralela ao do PR #4; decisão de base (adotar/fundir) é o próximo passo |

## 9. O que queremos do Dev 1

1. Confirmar que os contratos consumidos batem com o que o `document_processing` devolve (`RetrievalResult.evidences`, IDs de chunk).
2. Feedback sobre o catálogo dos 10 `field_code` (OQ-01 previa revisão do Dev 1).
3. Alinhar o gate `T-1` e a divergência de granularidade.

---

## 10. Lista exata de arquivos e trechos modificados (por commit)

### `e29c420` — feature completa (49 arquivos)

| Arquivo | Trecho/ação |
|---------|-------------|
| `src/modules/policy_analysis/public_api.py` | **novo** — classe `PolicyAnalysisFacade` (5 operações da spec + fila de revisão) |
| `src/modules/policy_analysis/domain/value_types.py` | **novo** — `Money`, `Period`, `parse_decimal/parse_date`, `normalize_value()` (dispatch por tipo) |
| `src/modules/policy_analysis/domain/field_catalog.py` | **novo** — `CATALOG` com 10 `FieldDefinition`, `get_field()` (rejeita fora do catálogo) |
| `src/modules/policy_analysis/domain/comparison.py` | **novo** — `compare_facts()` (função pura, 8 resultados) e `comparison_id()` (UUIDv5 do par) |
| `src/modules/policy_analysis/domain/models.py` | **novo** — `FieldComparison`, `ComparisonResult`, `Explanation`, `ReviewItem` |
| `src/modules/policy_analysis/application/extraction.py` | **novo** — `ExtractionService.extract_fields()` / `_build_fact()` (valida `evidence_ids` ⊆ pedido; normaliza; sintetiza NOT_FOUND) |
| `src/modules/policy_analysis/application/review.py` | **novo** — `ReviewService.list_pending()` / `record_decision()` (CONFIRMADO/CORRIGIDO auditado) |
| `src/modules/policy_analysis/application/comparison_service.py` | **novo** — `ComparisonService.compare_policies()` (idempotente, preserva explicações) |
| `src/modules/policy_analysis/application/explanation.py` | **novo** — `ExplanationService.explain_difference()` (rejeita sem citação dos dois lados) |
| `src/modules/policy_analysis/application/export.py` | **novo** — `ExportService.export_comparison()` |
| `src/modules/policy_analysis/application/errors.py` | **novo** — `ClassifiedError(code, retriable)` + `to_processing_status()` |
| `src/modules/policy_analysis/infrastructure/duckdb_repository.py` | **novo** — schema `_SCHEMA` (4 tabelas) + `upsert_fact/upsert_comparison/record_review` (DELETE+INSERT em transação) |
| `src/modules/policy_analysis/infrastructure/llm_agent.py` | **novo** — `MultiFieldExtractionAgent`, `LLMExplanationAgent`, `PydanticAIClient` (pydantic-ai lazy), `Fixture*Agent`, `_with_retries()` |
| `src/modules/policy_analysis/infrastructure/evidence_source.py` | **novo** — protocolo `EvidenceSource` + `MockEvidenceSource` |
| `src/modules/policy_analysis/infrastructure/document_processing_source.py` | **novo** — `DocumentProcessingEvidenceSource` (único import de `document_processing`, via `public_api`, lazy) |
| `src/modules/policy_analysis/infrastructure/pdf_export.py` | **novo** (posteriormente removido no `9fcd8e1`) |
| `src/modules/policy_analysis/demo.py` | **novo** — fluxo ponta a ponta offline/Gemini |
| `tests/modules/policy_analysis/` (12 arquivos) | **novos** — `conftest.py`, `fixtures/apolice_{a,b}.json`, `test_field_catalog/value_types/comparison/repository/extraction_agent/review_queue/explanation/export_pdf/architecture/e2e_flow.py` |
| `_reversa_forward/001-dev2-policy-analysis-slice/` (10 artefatos) | **novos** — requirements, roadmap, investigation, data-delta, onboarding, actions, progress.jsonl, legacy-impact, regression-watch, interfaces/llm-provider |
| `_reversa_sdd/addenda/001-dev2-policy-analysis-slice.md` | **novo** — adendo de convergência (vigente) |
| `.reversa/config.toml` | seção `[specs]` preenchida (`granularity = "feature"`) |
| `.reversa/active-requirements.json` | **novo** — feature ativa `001-dev2-policy-analysis-slice` |
| `requirements.txt` | +`pydantic-ai`, `duckdb`, `fpdf2` (este removido depois) |

### `cf00a49` — planejamento e framework

- `_reversa_sdd/learning/` (4 docs: `plano-acao-dev2.md`, `plano-acao-dev1.md`, `aprendizados.md`, `benchmark-repos-referencia.md`) — **novos**, trazidos do remoto sem alteração.
- `_reversa_forward/001-vertical-slice-e2e/`, `002-p0-dev1-documental-rag/`, `003-p0-dev2-analise-experiencia/` + adendos 001/002/003 — **novos**, trazidos do remoto sem alteração.
- `.agents/skills/`, `.claude/skills/` + `.reversa/version` + `.reversa/_config/` — Reversa v1.3.4.
- `.reversa/state.json` — mesclado: `forward_progress` (fluxo paralelo) preservado + `forward_progress_dev2` acrescentado + `completed_stages` estendido.
- `.reversa/plan.md` — 2 linhas acrescentadas na seção "Implementação (/reversa-forward)".

### `9fcd8e1` — export Markdown

- `src/modules/policy_analysis/infrastructure/markdown_export.py` **novo** (`render_comparison_markdown()`); `pdf_export.py` **removido**.
- `application/export.py` — `_default_renderer()` aponta para markdown; extensão `.md`.
- `tests/.../test_export_pdf.py` → **renomeado** `test_export_markdown.py` (asserções de texto UTF-8); `test_e2e_flow.py` — asserção `%PDF` → `startswith("#")`.
- `demo.py` (mensagem), `requirements.txt` (−`fpdf2`), docs da feature (requirements/roadmap/investigation/actions/adendo).

### `ac6d43a` — caminho padronizado + OQ-04 fechada

- `application/export.py` — `output_dir` padrão `"exports"`; nome do arquivo `f"{comparison_id}.md"` (antes `output/comparison_<id>.md`).
- `demo.py` — `output_dir=REPO_ROOT/"exports"`.
- `_reversa_sdd/sdd/policy-analysis.md` — **linha 210 (§14 OQ-04)** marcada RESOLVIDA.
- `onboarding.md`, `requirements.md` (feature), adendo 001, `progress.jsonl` (linhas `corrected`).

## 11. Relatório de ações em zonas compartilhadas (Dev 1 ↔ Dev 2)

| Zona compartilhada | Ação executada por nós | Risco de conflito |
|--------------------|------------------------|-------------------|
| `src/shared_kernel/` | **NENHUMA alteração** — apenas consumo dos contratos (verificado por teste de arquitetura) | zero |
| `_reversa_sdd/sdd/policy-analysis.md` | Única edição: linha da OQ-04 (§14) marcada RESOLVIDA com decisão Markdown | baixo (uma linha; Dev 1 não mexe nas OQs do Dev 2) |
| `_reversa_sdd/addenda/` | 1 arquivo novo (`001-dev2-policy-analysis-slice.md`); adendos do fluxo paralelo preservados intocados | zero (nomes distintos) |
| `_reversa_sdd/learning/` | Somente leitura/adição dos handoffs | zero |
| `.reversa/state.json` | Mesclagem manual: preservamos todos os campos do fluxo paraleiro e acrescentamos `forward_progress_dev2` | médio se outro agente reescrever o arquivo — **mesclar, nunca sobrescrever** |
| `.reversa/plan.md` | 2 linhas acrescentadas (registro das entregas) | baixo |
| `.reversa/config.toml` / `active-requirements.json` | Nossos valores mantidos (`granularity="feature"`; feature ativa = nossa) — divergência `hybrid` aberta | médio (decidir junto) |
| `requirements.txt` | +`pydantic-ai`, `duckdb` (e `fpdf2`, removido em seguida) | baixo (linhas base intactas) |
| `pyproject.toml` | **NÃO alterado** | zero |

## 12. Passos sequenciais para integrar sem conflitos de merge

1. **Não dar merge/checkout que sobrescreva `src/modules/policy_analysis/`** antes de decidir a base do código (nossa implementação vs a do PR #4) — existem arquivos homônimos com designs divergentes (`field_catalog.py` vs `catalog.py`, `comparison_service.py` vs `comparison.py`).
2. Resolver a permissão de escrita (conta `amitigiovani-prog` no repo) → `git push -u origin feature/dev2-policy-analysis-slice` → abrir PR **com este handoff na descrição**.
3. Decisão de base do `policy_analysis` (adotar o do PR #4 ou fundir) — nossa branch é a garantia de que nada se perde em qualquer cenário.
4. Em alterações futuras nas zonas da tabela acima: **mesclar `state.json`/`plan.md` linha a linha**, nunca sobrescrever; `shared_kernel` só via PR conjunto; specs só via adendos.
5. Nossos artefatos de feature ficam isolados em `_reversa_forward/001-dev2-policy-analysis-slice/` — não colidem com os do fluxo paralelo.

---

> **Regra perpétua (registrada em `CLAUDE.md`, vigor desde 2026-09-29):** todo commit, push ou PR do Dev 2 inclui histórico detalhado (arquivos + trechos modificados, funcionalidades, passos anti-conflito, relatório de zonas compartilhadas) nos campos de comentário, mais um resumo por entrega em `_reversa_sdd/learning/handoffs/` para leitura do assistente de IA do Dev 1.