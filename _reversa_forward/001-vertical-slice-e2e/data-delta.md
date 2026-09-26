# Data-Delta: Vertical Slice E2E

> Identificador: `001-vertical-slice-e2e`
> Data: `2026-09-26`
> Base: `_reversa_sdd/sdd/document-processing.md#9`, `_reversa_sdd/sdd/policy-analysis.md#9`, `_reversa_sdd/sdd/shared-kernel-contracts.md#9`

Estado inicial (greenfield): não há dado legado. Este documento descreve o que o slice cria em cada armazenamento.

## 1. Qdrant (coleção `policy_chunks`) — OQ-04 decidida

| Campo do payload | Tipo | Origem | Observação |
|------------------|------|--------|------------|
| `chunk_id` | str | `ChunkMetadata` | ID compartilhado com DuckDB (RN-03) |
| `document_id` | str | `ChunkMetadata` | filtro de idempotência (D-07) |
| `policy_id` | str | `ChunkMetadata` | filtro por apólice |
| `page` | int | `ChunkMetadata` | ≥ 1 |
| `chunk_index` | int | `ChunkMetadata` | sequencial por página |
| `section_name` | str/null | `ChunkMetadata` | `null` no slice (OQ-03) |
| `metadata_version` | str | `ChunkMetadata` | versão do contrato |
| `source_type` | str | `EvidenceRef` | NATIVE_TEXT / PADDLEOCR |
| `ocr_confidence` | float/null | `EvidenceRef` | só quando OCR |
| `text` | str | chunk | confidencial — logs nunca imprimem (RNF-05) |

- Vetor: embedding Gemini (dimensão do modelo configurado), distância cosine.
- Migrações: nenhuma. Recriação da coleção é segura (fonte = PDFs do usuário).

## 2. DuckDB (arquivo local `data/facts.duckdb`)

```sql
CREATE TABLE policies (
  policy_id VARCHAR PRIMARY KEY,
  seguradora VARCHAR,
  vigencia_inicio DATE,
  vigencia_fim DATE
);
CREATE TABLE documents (
  document_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR NOT NULL,
  file_path VARCHAR
);
CREATE TABLE facts (
  fact_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR NOT NULL,
  field_code VARCHAR NOT NULL,
  status VARCHAR NOT NULL,            -- FOUND | NOT_FOUND | AMBIGUOUS | NEEDS_REVIEW
  value JSON,                         -- valor extraído (JSON serializado)
  normalized_value JSON,              -- forma canônica usada na comparação
  confidence DOUBLE,                  -- [0,1]
  evidence_ids JSON,                  -- list[str]; vazio somente em NOT_FOUND (RN-02)
  requires_human_review BOOLEAN,
  created_at TIMESTAMP
);
CREATE TABLE comparisons (
  comparison_id VARCHAR PRIMARY KEY,
  policy_id_a VARCHAR NOT NULL,
  policy_id_b VARCHAR NOT NULL,
  field_code VARCHAR NOT NULL,
  direction VARCHAR NOT NULL,         -- maior | menor | igual | ausente_a | ausente_b | divergente
  result JSON,
  explanation TEXT,
  created_at TIMESTAMP
);
```

- Chave natural de upsert (idempotência, RN-04): `facts (policy_id, field_code)`; `documents (document_id)`.
- IDs são os mesmos do shared_kernel (`PolicyId`, `DocumentId`, `FactId`, `ComparisonId`).

## 3. Sistema de arquivos

| Caminho | Conteúdo |
|---------|----------|
| `exports/<ComparisonId>.md` | Resumo standalone da comparação (RF-08) |

## 4. Campos removidos / migrações

Nenhum. Nenhuma migração necessária neste slice.
