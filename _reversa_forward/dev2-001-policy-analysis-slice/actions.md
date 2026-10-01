# Actions: Vertical slice do policy_analysis — extração de fatos, comparação determinística e export

> Identificador: `dev2-001-policy-analysis-slice`
> Data: `2026-09-26`
> Roadmap: `_reversa_forward/dev2-001-policy-analysis-slice/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 31 |
| Paralelizáveis (`[//]`) | 15 |
| Maior cadeia de dependência | 8 (T001 → T004 → T008 → T015 → T022 → T025 → T026 → T028) |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Criar o scaffolding do módulo: `src/modules/policy_analysis/` com pacotes `domain/`, `application/`, `infrastructure/` e `__init__.py` | - | - | `src/modules/policy_analysis/` | 🟡 | `[X]` |
| T002 | Atualizar `requirements.txt` com as dependências do módulo (`pydantic-ai`, `duckdb`, `fpdf2`) e instalá-las no venv | - | `[//]` | `requirements.txt` | 🟡 | `[X]` |
| T003 | Implementar value objects de domínio: `Money` (Decimal, normalização BRL), `Period` (datas/duração), `FieldCode` | T001 | `[//]` | `src/modules/policy_analysis/domain/value_types.py` | 🟢 | `[X]` |
| T004 | Implementar o catálogo fechado dos 10 `field_code` com semântica, tipo de valor e regra de normalização por campo; rejeição de campo fora do catálogo | T001 | `[//]` | `src/modules/policy_analysis/domain/field_catalog.py` | 🟢 | `[X]` |
| T005 | Criar fixtures de evidência mockada: 2 apólices sintéticas (JSON de `EvidenceRef`) para o vertical slice | T001 | `[//]` | `tests/modules/policy_analysis/fixtures/` | 🟡 | `[X]` |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T006 | Testes do catálogo: 10 campos válidos, `field_code` fora do catálogo rejeitado na fronteira (RN-05) | T004 | `[//]` | `tests/modules/policy_analysis/test_field_catalog.py` | 🟢 | `[X]` |
| T007 | Testes dos value objects: normalização de moeda/período/texto e validações de limites | T003 | `[//]` | `tests/modules/policy_analysis/test_value_types.py` | 🟢 | `[X]` |
| T008 | Testes do comparador determinístico: maior/menor/igual, divergência de texto, ausente (RN-04), determinismo e idempotência (RN-06) | T003, T004 | - | `tests/modules/policy_analysis/test_comparison.py` | 🟢 | `[X]` |
| T009 | Testes do repositório DuckDB: schema auto-criado, upsert de fatos, IDs do shared_kernel, reexecução sem duplicar | T002 | `[//]` | `tests/modules/policy_analysis/test_repository.py` | 🟡 | `[X]` |
| T010 | Testes do agente de extração com LLM mockado: saída válida vira fato; saída fora do schema nunca vira fato (RF-09); retry com backoff (EC-01) | T002 | `[//]` | `tests/modules/policy_analysis/test_extraction_agent.py` | 🟡 | `[X]` |
| T011 | Testes da fila de revisão humana: sinalização AMBIGUOUS/NEEDS_REVIEW com evidência anexa e registro de decisão (RN-03) | T004 | `[//]` | `tests/modules/policy_analysis/test_review_queue.py` | 🟡 | `[X]` |
| T012 | Testes da explicação: citação obrigatória de `evidence_ids` dos dois lados; explicação sem citação é rejeitada (RF-07) | T005 | `[//]` | `tests/modules/policy_analysis/test_explanation.py` | 🟡 | `[X]` |
| T013 | Testes do export PDF: documento contém os 10 campos do catálogo, inclusive ausentes, e é standalone (RF-08) | T002 | `[//]` | `tests/modules/policy_analysis/test_export_pdf.py` | 🟡 | `[X]` |
| T014 | Teste de arquitetura: zero imports de internos de `document_processing` em `policy_analysis`; somente a fachada (RF-01) | T001 | `[//]` | `tests/modules/policy_analysis/test_architecture.py` | 🟡 | `[X]` |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T015 | Implementar os comparadores determinísticos por tipo de valor (numérico, moeda, período, texto, ausente) — função pura, sem LLM (RN-01) | T008 | - | `src/modules/policy_analysis/domain/comparison.py` | 🟢 | `[X]` |
| T016 | Implementar modelos de domínio `Fact` e `ComparisonResult` com validação (FOUND exige `evidence_ids` reais — RN-02) | T003, T004 | - | `src/modules/policy_analysis/domain/models.py` | 🟡 | `[X]` |
| T017 | Implementar a porta `EvidenceSource` (protocolo) e o `MockEvidenceSource` sobre as fixtures (RF-10) | T005 | - | `src/modules/policy_analysis/infrastructure/evidence_source.py` | 🟡 | `[X]` |
| T018 | Implementar schema DuckDB auto-criado e repositórios de `policies`/`documents`/`facts`/`comparisons` com upsert idempotente | T009 | - | `src/modules/policy_analysis/infrastructure/duckdb_repository.py` | 🟡 | `[X]` |
| T019 | Implementar o agente multi-campo Pydantic AI (1 chamada por apólice) com saída estruturada validada, retry/backoff e falha classificada | T010 | - | `src/modules/policy_analysis/infrastructure/llm_agent.py` | 🟢 | `[X]` |
| T020 | Implementar os casos de uso `extract_field` e `get_facts` (evidência → agente → validação → persistência → `ProcessingStatus`) | T016, T017, T018, T019 | - | `src/modules/policy_analysis/application/extraction.py` | 🟡 | `[X]` |
| T021 | Implementar a fila de revisão humana (listar sinalizados, registrar decisão do analista como fato novo ou confirmação) | T011, T018 | - | `src/modules/policy_analysis/application/review.py` | 🟡 | `[X]` |
| T022 | Implementar `compare_policies`: comparação determinística campo a campo + `ComparisonId` determinístico (hash do par ordenado) + persistência idempotente | T015, T016, T018 | - | `src/modules/policy_analysis/application/comparison_service.py` | 🟢 | `[X]` |
| T023 | Implementar `explain_difference`: explicação por LLM citando `evidence_ids` dos dois lados, com rejeição de explicação sem citação | T012, T016, T019 | - | `src/modules/policy_analysis/application/explanation.py` | 🟡 | `[X]` |
| T024 | Implementar o gerador de PDF (fpdf2) do resumo da comparação | T013 | - | `src/modules/policy_analysis/infrastructure/pdf_export.py` | 🟡 | `[X]` |
| T025 | Implementar `export_comparison` (resumo por campo: valores, direção, evidências, explicação → caminho do PDF) | T022, T024 | - | `src/modules/policy_analysis/application/export.py` | 🟡 | `[X]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T026 | Implementar `PolicyAnalysisFacade` no `public_api.py` expondo as 5 operações da spec | T020, T021, T022, T023, T025 | - | `src/modules/policy_analysis/public_api.py` | 🟡 | `[X]` |
| T027 | Implementar `DocumentProcessingEvidenceSource` (adaptador da fachada `retrieve_evidence` do Dev 1) | T017 | `[//]` | `src/modules/policy_analysis/infrastructure/document_processing_source.py` | 🟡 | `[X]` |
| T028 | Implementar o script de demonstração ponta a ponta (extração → comparação → explicação → export com evidências mockadas) | T026 | - | `src/modules/policy_analysis/demo.py` | 🟡 | `[X]` |
| T029 | Teste E2E do fluxo feliz cobrindo os 7 cenários Gherkin do `requirements.md` | T026 | - | `tests/modules/policy_analysis/test_e2e_flow.py` | 🟡 | `[X]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T030 | Registrar `run_id`, tokens e custo por execução de LLM (observabilidade RNF-03) | T019 | `[//]` | `src/modules/policy_analysis/infrastructure/llm_agent.py` | 🟡 | `[X]` |
| T031 | Padronizar mensagens de erro classificadas e mapeamento para `ProcessingStatus(stage="FAILED")` reexecutável | T020 | `[//]` | `src/modules/policy_analysis/application/errors.py` | 🟡 | `[X]` |

## Notas de execução

- Resultado `AGUARDANDO_REVISAO` acrescentado ao enum da `data-delta.md` (campo pendente de revisão não é comparado — EC-02/fluxo B da spec).
- Os agentes de extração e explicação recebem `run_id` no protocolo; `PydanticAIClient` e `MultiFieldExtractionAgent` registram uso (tokens/prompt) para o RNF-03.
- Composição por injeção: `ExportService` recebe o renderizador PDF (ou resolve adiado) para `application/` não importar `infrastructure/` (isolamento, RNF-05).
- Ambiente Windows/sandbox: rodar com `PYTHONDONTWRITEBYTECODE=1` (o sandbox bloqueia escrita de `.pyc` na instalação do Python) e o demo com `PYTHONPATH=src`.
- fpdf2 (fontes core, latin-1): textos são sanitizados (`_safe`) e o cursor é realinhado à margem esquerda a cada linha (gotcha do `multi_cell`). — **Obsoleto (2026-09-26):** o export foi migrado para Markdown (OQ-04 revisada); `pdf_export.py` removido e `fpdf2` retirado do `requirements.txt`.
- **Vínculo com o planejamento complementar** (`_reversa_sdd/learning/plano-acao-dev2.md`, trazido do remoto em 2026-09-26): nossa entrega cobre parte do `D2-P0-2` (fila de revisão com Confirmar/Corrigir auditada — falta "Registrar divergência") e do `D2-P0-3` (normalização por tipo com NEEDS_REVIEW — faltam regras como vigência início≤fim); `D2-P0-1` está parcial (`evidence_ids` validado contra o pedido, mas sem ancoragem de substring no `quoted_text` nem temperature 0); `D2-P0-4` (evaluation + golden set) não é desta feature (NG-03). O plano complementar foi escrito sobre a implementação paralela do remoto (features dev1-001-vertical-slice-e2e/002/003) — os 🟢 da seção "Estado atual" dele não se aplicam a este código. Divergências de decisão: export **resolvida em 2026-09-26 → Markdown** (formato do fluxo paralelo); gate `T-1` (ruff/mypy) ainda não configurado neste branch.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-to-do` | reversa |