# Legacy-Impact: P0 do Desenvolvedor 1 — Documental e RAG

> Identificador: `002-p0-dev1-documental-rag`
> Data: `2026-09-26`
> Feature greenfield (âncora: prd.md + specs SDD); "legado" aqui = código entregue pela feature `001`.
> Política de edição: `allowLegacyEdits: true`, `allowedPaths = ["src/**", "tests/**", "pyproject.toml", "requirements.txt", ".gitignore"]` — escritas restritas a esses globs.

## Modificadas

| Arquivo afetado | Componente (spec) | Tipo | Severidade | Justificativa |
|-----------------|-------------------|------|------------|---------------|
| `src/modules/document_processing/application/service.py` | `document-processing` (`_reversa_sdd/sdd/document-processing.md#6.1`) | regra-alterada | MEDIUM | `_cause` sanitizado (nunca `str(exc)` cru — texto de apólice não vaza em erro); `retrieve_evidence` honra `section_name` (filtro) e `field_code` (hint composto) — F-14 corrigido; health-check fail-fast antes dos embeddings |
| `src/modules/document_processing/application/ports.py` | `document-processing` | regra-nova | LOW | hierarquia de exceções tipadas por porta (`PortError`, `TextExtractionError`, `OcrError`, `EmbeddingError`, `IndexingError`); `VectorIndex.search` passa a receber `field_code` explicitamente |
| `src/modules/document_processing/infrastructure/indexing.py` | `document-processing` | regra-nova | LOW | retry Gemini (3 tentativas, backoff 1s→2s, timeout 30s, só transitórios; Qdrant sem retry); lote de embeddings limitado a 100 textos/request; loop do SDK legado eliminado |
| `src/modules/document_processing/infrastructure/extractors.py` | `document-processing` | regra-alterada | LOW | tradução de erro externo para exceção tipada da porta |

## Arquivos criados (todo o impacto é `componente-novo`)

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|-----------------|-----------|------|------------|---------------|
| `tests/modules/document_processing/test_retrieval_contract.py` | suíte de verificação | componente-novo | LOW | teste de contrato por parâmetro: todo campo de `RetrievalQuery` chega à porta e é consumido |
| `tests/modules/document_processing/test_indexing.py` | suíte de verificação | componente-novo | LOW | isolamento entre apólices, `QdrantClient` mockado (`query_filter`), limite de lote, health-check, retry |
| `_reversa_forward/002-.../contract-delta-retrievalquery.md` | coordenação Dev 1↔Dev 2 | componente-novo | LOW | caixa postal da semântica de `field_code` (não muda o contrato) |

## Diff conceitual por componente

- **document_processing:** erros tipados e sanitizados; retrieval honra o contrato inteiro (`section_name` filtra, `field_code` é hint determinístico `"{query}\n[campo: {code}]"`); indexação com lote ≤100/request, sem loop do SDK legado, health-check fail-fast; retry só no Gemini.
- **shared_kernel:** contrato v1.0.0 consumido sem alteração — `RetrievalQuery` passa a ser honrado por completo (antes `section_name`/`field_code` eram descartados em silêncio).
- **policy_analysis / evaluation / UI:** intocados (terreno do Dev 2).

## Preservadas

Chunking/limiares do slice (800/100; 40 chars; OCR 0.5), idempotência (`uuid5`), coleção `policy_chunks`, vocabulário de erros (`EXTRACT:`/`OCR:`/`INDEXING:`).

## Modificadas (regras removidas)

Nenhuma regra removida.
