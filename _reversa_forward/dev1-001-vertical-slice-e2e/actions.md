# Actions: Vertical Slice E2E — PDF até comparação e tela

> Identificador: `dev1-001-vertical-slice-e2e`
> Data: `2026-09-26`
> Roadmap: `_reversa_forward/dev1-001-vertical-slice-e2e/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 21 |
| Paralelizáveis (`[//]`) | 11 |
| Maior cadeia de dependência | 10 (T001→T003→T005→T009→T010→T011→T014→T015→T016→T020) |

## Análise de granularidade (atômico vs. maior)

Decisão explícita sobre o tamanho de cada ação, antes de codificar:

- **Ações atômicas (maioria):** lógica pura e testes — domínio de chunking, regras de comparação, catálogo, validação de saída LLM. Cada uma cabe num turno, tem verificação própria (teste) e troca de assunto zero. Critério do skill (≤5 subpontos, ≤3 arquivos) atendido naturalmente.
- **Ações maiores e coesas (exceção justificada):** scaffolding (T001) e portas por módulo (T002/T003) ficam como ações maiores porque a interface precisa nascer coerente de uma vez — quebrar em "um arquivo por turno" geraria churn de assinatura entre turnos e dependência artificial. A atomicidade que importa é "um turno sem feedback humano", não "menor diff possível".
- **Integração em pares independentes:** adapters de infraestrutura (T012–T014) são separados por dependência externa (PyMuPDF/PaddleOCR, Gemini/Qdrant, DuckDB/Pydantic AI) — arquivos distintos, paralelizáveis, cada um substituível por fake nos testes.
- **UI por último e única (T019):** é cola, não lógica; uma ação maior evita refatorar estado entre turnos.

## Fase 1, Preparação

<!-- Setup, scaffolding, migrações iniciais, configuração de infraestrutura local. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Scaffolding dos pacotes `src/modules/document_processing`, `src/modules/policy_analysis`, `src/ui`, `tests/modules`, `tests/e2e`, `tests/architecture`, `tests/integration` (camadas domain/application/infrastructure + `__init__`) | - | `[//]` | `src/modules/` | 🟢 | `[X]` |
| T002 | Portas do document_processing (`application/ports.py`: TextExtractor, OcrEngine, Embedder, VectorIndex, StatusSink — `typing.Protocol`) | T001 | - | `src/modules/document_processing/application/ports.py` | 🟢 | `[X]` |
| T003 | Portas do policy_analysis (`application/ports.py`: LlmExtractor, FactRepository, ExplanationGenerator — `typing.Protocol`) | T001 | `[//]` | `src/modules/policy_analysis/application/ports.py` | 🟢 | `[X]` |

## Fase 2, Testes

<!-- Testes que precisam existir antes ou logo após o núcleo (TDD no núcleo determinístico). -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T004 | Testes do domínio de processamento: limiares (40 chars / OCR 0.5) e chunking 800/100 com `ChunkMetadata` válido | T002 | - | `tests/modules/document_processing/test_domain.py` | 🟡 | `[X]` |
| T005 | Testes do domínio de comparação: normalização, direções (maior/menor/igual/ausente/divergente), determinismo | T003 | `[//]` | `tests/modules/policy_analysis/test_comparison.py` | 🟢 | `[X]` |
| T006 | Testes do catálogo: 10 field_code aceitos, campo fora do catálogo rejeitado | T003 | `[//]` | `tests/modules/policy_analysis/test_catalog.py` | 🟡 | `[X]` |

## Fase 3, Núcleo

<!-- Lógica central da feature. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T007 | Domínio document_processing: constantes de limiar, classificação de página (NATIVE_TEXT/PADDLEOCR/REVIEW), chunker sequencial com overlap | T004 | - | `src/modules/document_processing/domain/` | 🟡 | `[X]` |
| T008 | Application document_processing: orquestração `process_document` (estágios + ProcessingStatus) e `retrieve_evidence` (RetrievalQuery→RetrievalResult, run_id) via portas | T007 | - | `src/modules/document_processing/application/service.py` | 🟢 | `[X]` |
| T009 | Domínio policy_analysis: catálogo dos 10 campos (semântica documentada), normalização de valores, regras determinísticas de comparação | T005, T006 | - | `src/modules/policy_analysis/domain/` | 🟡 | `[X]` |
| T010 | Application policy_analysis: `extract_field`/`get_facts` — monta `ExtractionRequest`, valida saída do LLM contra `ExtractedFact` (RN-05), fila de revisão (RF-04) | T009 | - | `src/modules/policy_analysis/application/extraction.py` | 🟢 | `[X]` |
| T011 | Application policy_analysis: `compare_policies` (ComparisonId), `explain_difference` (exige evidência citada) e `export_comparison` (Markdown standalone) | T010 | - | `src/modules/policy_analysis/application/comparison.py` | 🟢 | `[X]` |

## Fase 4, Integração

<!-- Cola com outras partes do sistema, contratos externos, ganchos. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T012 | Infra document_processing: adapter PyMuPDF (texto por página) + adapter PaddleOCR (OCR por página com confiança) | T008 | `[//]` | `src/modules/document_processing/infrastructure/extractors.py` | 🟡 | `[X]` |
| T013 | Infra document_processing: adapter Gemini (Embedder) + adapter Qdrant (VectorIndex com idempotência por document_id, coleção `policy_chunks`) | T008 | `[//]` | `src/modules/document_processing/infrastructure/indexing.py` | 🟡 | `[X]` |
| T014 | Infra policy_analysis: adapter DuckDB (`FactRepository` com upsert idempotente) + adapter Pydantic AI (`LlmExtractor` com schema do contrato) | T011 | `[//]` | `src/modules/policy_analysis/infrastructure/` | 🟡 | `[X]` |
| T015 | Fachadas públicas `public_api.py` dos dois módulos (única superfície cross-module) | T012, T013, T014 | - | `src/modules/*/public_api.py` | 🟢 | `[X]` |
| T016 | Teste E2E da jornada com fakes: 2 PDFs → indexação → extração de `limite_agregado` → comparação → export (RF-01..RF-09) | T015 | - | `tests/e2e/test_vertical_slice.py` | 🟢 | `[X]` |
| T017 | Testes de arquitetura: nenhuma dependência externa em domain/application; cross-module só via fachada | T015 | `[//]` | `tests/architecture/test_imports.py` | 🟢 | `[X]` |
| T018 | Testes de integração reais (PyMuPDF/Qdrant/Gemini/DuckDB) marcados `integration`, skip gracioso sem dependência | T015 | `[//]` | `tests/integration/` | 🟡 | `[X]` |
| T019 | UI Streamlit mínima: carregar 2 PDFs, acompanhar estágios, extração do campo, comparação com evidências, fila de revisão, export | T015 | - | `src/ui/app.py` | 🟡 | `[X]` |

## Fase 5, Polimento

<!-- Logs, telemetria, mensagens de erro, documentação curta. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T020 | Mensagens de erro classificadas por estágio (`EXTRACT:`/`OCR:`/`INDEXING:`) e logs sem conteúdo de apólice (só IDs/estágios, RNF-05) | T016 | `[//]` | `src/modules/` | 🟢 | `[X]` |
| T021 | Atualizar `requirements.txt` (núcleo + extras de integração comentados) e `onboarding.md` com o estado real da entrega | T019 | `[//]` | `requirements.txt` | 🟢 | `[X]` |

## Notas de execução

- Execução em 2026-09-26, dois agentes em paralelo (módulos independentes) + integração pelo orquestrador.
- T001/T002/T003/T004/T007/T008/T012/T013 e T005/T006/T009/T010/T011/T014 entregues pelos agentes dos módulos `document_processing` e `policy_analysis` respectivamente.
- Decisões registradas pelos agentes (aceitas): `ChunkRecord.vector` opcional (embedding viaja no record); point id do Qdrant = `uuid5` estável derivado do `chunk_id` (idempotência preservada); `_LoggingStatusSink` como StatusSink padrão; `GeminiEmbedder` com fallback `google.genai` → `google.generativeai`; PK de `comparisons` = `(comparison_id, field_code)`; tabela extra `evidences` no DuckDB (a porta `FactRepository` exige persistência de `EvidenceRef`).
- Normalização de valores tolerante a formatos pt-br (`1.000.000,00`, `dd/mm/aaaa`) — determinística e testada.
- E2E (T016) usa os fakes dos dois módulos + `DocumentProcessingRetriever` real (cross-module via fachada); correção durante a execução: extração de `franquia` do lado A faltava antes da comparação (bug do teste, não do código).
- Falha de LLM coberta por testes de unidade (`LlmOutputError`, nada persistido) e explicação sem citação rejeitada no E2E.
- "Quality gates" do plano: PDF nativo/escaneado, documento duplicado (idempotência), baixa confiança (REVIEW_REQUIRED) e falha de LLM cobertos; "tabela" ficou fora do escopo (NG-01 — PP-Structure fase posterior).

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-to-do` | reversa |
| 2026-09-26 | Todas as 21 ações executadas e marcadas por `/reversa-coding` | reversa |
