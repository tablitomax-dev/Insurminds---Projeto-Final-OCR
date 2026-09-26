# Legacy-Impact: Vertical Slice E2E

> Identificador: `001-vertical-slice-e2e`
> Data: `2026-09-26`
> Feature greenfield, sem legado pré-existente. Âncora: prd.md + specs SDD.
> Política de edição na execução: `allowLegacyEdits: true`, `allowedPaths = ["src/**", "tests/**", "pyproject.toml", "requirements.txt", ".gitignore"]` (todas as escritas restritas a esses globs).

## Arquivos criados (todo o impacto é `componente-novo`)

| Arquivo afetado | Componente (spec) | Tipo | Severidade | Justificativa |
|-----------------|-------------------|------|------------|---------------|
| `src/modules/document_processing/domain/processing.py` | `document-processing` (`_reversa_sdd/sdd/document-processing.md#8`) | componente-novo | LOW | limiares + chunker + classificação de página (OQ-01..03 do slice) |
| `src/modules/document_processing/application/ports.py` | `document-processing` | componente-novo | LOW | portas TextExtractor/OcrEngine/Embedder/VectorIndex/StatusSink |
| `src/modules/document_processing/application/service.py` | `document-processing` | componente-novo | MEDIUM | orquestração RF-01..RF-07, RF-09 (estágios, idempotência, retrieval) |
| `src/modules/document_processing/infrastructure/extractors.py` | `document-processing` | componente-novo | LOW | adapters PyMuPDF + PaddleOCR (imports lazy) |
| `src/modules/document_processing/infrastructure/indexing.py` | `document-processing` | componente-novo | LOW | adapters Gemini + Qdrant (coleção `policy_chunks`, OQ-04) |
| `src/modules/document_processing/public_api.py` | `document-processing` (RF-08) | componente-novo | LOW | fachada única do módulo |
| `src/modules/policy_analysis/domain/catalog.py` | `policy-analysis` (`_reversa_sdd/sdd/policy-analysis.md#8`) | componente-novo | LOW | catálogo dos 10 field_code (RF-02) |
| `src/modules/policy_analysis/domain/comparison.py` | `policy-analysis` (RF-06) | componente-novo | MEDIUM | regras determinísticas de comparação (RN-01) |
| `src/modules/policy_analysis/application/ports.py` | `policy-analysis` | componente-novo | LOW | portas EvidenceRetriever/LlmExtractor/FactRepository/ExplanationGenerator |
| `src/modules/policy_analysis/application/extraction.py` | `policy-analysis` (RF-03/RF-04/RF-09) | componente-novo | MEDIUM | extração com validação de saída LLM e fila de revisão |
| `src/modules/policy_analysis/application/comparison.py` | `policy-analysis` (RF-06..RF-08) | componente-novo | MEDIUM | comparação + explicação com evidência + export |
| `src/modules/policy_analysis/infrastructure/duckdb_repository.py` | `policy-analysis` (RF-05) | componente-novo | LOW | persistência DuckDB idempotente (schema do data-delta) |
| `src/modules/policy_analysis/infrastructure/llm_extractors.py` | `policy-analysis` | componente-novo | LOW | adapters Pydantic AI/Gemini (imports lazy) |
| `src/modules/policy_analysis/infrastructure/document_retriever.py` | `policy-analysis` (RF-01) | componente-novo | LOW | cross-module exclusivamente via `document_processing.public_api` |
| `src/modules/policy_analysis/public_api.py` | `policy-analysis` | componente-novo | LOW | fachada única do módulo |
| `src/ui/app.py` | `prd.md#4` (tela do analista) | componente-novo | LOW | UI Streamlit mínima (RF-09) |
| `tests/fakes/**`, `tests/modules/**`, `tests/e2e/**`, `tests/architecture/**`, `tests/integration/**` | suíte de verificação | componente-novo | LOW | 137 testes verdes (4 skipped de integração) |
| `requirements.txt`, `pyproject.toml` | infraestrutura do projeto | componente-novo | LOW | extras comentados; mark `integration` registrado |

## Diff conceitual por componente

- **document_processing:** nasceu completo (domain/application/infrastructure/public_api), fiel a `document-processing.md#8`; contratos vêm do `shared_kernel` v1.0.0 sem alteração.
- **policy_analysis:** nasceu completo, fiel a `policy-analysis.md#8`; comparação 100% determinística; LLM só extrai e explica.
- **shared_kernel:** consumido como está — nenhuma mudança de contrato (não há delta MAJOR).
- **evaluation:** intocado (fase posterior, `evaluation.md#4`).

## Preservadas

N/a — feature greenfield; nada pré-existente foi tocado além de `requirements.txt`/`pyproject.toml` (completados, sem remover conteúdo).

## Modificadas

Nenhuma regra alterada ou removida.
