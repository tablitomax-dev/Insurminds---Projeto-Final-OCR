# Data Delta: Documento complexo — estrutura, cláusulas e tabelas (NG-01)

> Identificador: `dev1-006-p2-documento-complexo`
> Data: `2026-10-01`
> Base: `_reversa_sdd/sdd/shared-kernel-contracts.md` (RF-06) + `_reversa_sdd/sdd/document-processing.md#9`

## 1. Resumo

**Nenhum campo novo, nenhum campo removido, nenhuma migração.** A feature passa a preencher campos que o contrato já prevê como opcionais e a usar um literal já reservado. `CONTRACTS_VERSION` segue `1.1.0` — nenhuma caixa postal ao Dev 2 (aprendizados §5.2).

## 2. Diff conceitual por entidade

### `ChunkMetadata` (shared_kernel — sem mudança de forma)

| Campo | Antes | Depois | Observação |
|-------|-------|--------|------------|
| `section_name: str \| None` | sempre `None` (`processing.py::build_chunk_metadata`, OQ-03) | literal do marcador vigente (Cláusula/Artigo/Seção/Epígrafe) ou `None` | campo opcional já existente; chunks antigos permanecem válidos |
| `source_type` | `NATIVE_TEXT` \| `PADDLEOCR` | + primeiro uso de `PP_STRUCTURE` (páginas analisadas pelo motor de layout) | literal já previsto no Literal do contrato |
| demais campos | — | inalterados | `metadata_version` segue `CONTRACTS_VERSION` |

### `EvidenceRef` (shared_kernel — sem mudança de forma)

| Campo | Antes | Depois |
|-------|-------|--------|
| `section_name` | derivado do chunk (sempre `None`) | derivado do chunk (preenchido quando houver seção) — já consumido pelo Dev 2 em `llm_agent.py` (`" seção {ev.section_name}"`) sem mudança |

### Payload do Qdrant (coleção `policy_chunks`)

| Campo | Antes | Depois |
|-------|-------|--------|
| `section_name` | sempre `None` no payload | valor literal ou `None`; filtro `section_name` na consulta (`indexing.py`) passa a ter dados | 
| texto do chunk | texto puro da página | texto puro + tabela serializada com marcador `[TABELA]` quando houver região de tabela no layout |

## 3. Novos modelos (não persistidos, domínio puro)

- `structure.SectionMarker` (dataclass): `name: str` (literal), `char_offset: int` — resultado da detecção.
- `ports.LayoutRegion` (dataclass em `application/ports.py`, ao lado de `EmbeddingError`/`IndexingError`): `kind: Literal["heading","table","text"]`, `text: str`, `order: int` — saída normalizada do motor; não vira contrato (corrigido no `/reversa-to-do`: a porta mora em `application/ports.py`, não em `infrastructure/`, para o domínio/serviço não importar infraestrutura).

## 4. Migrações necessárias

Nenhuma. Adoção natural por reprocessamento idempotente (RF-09 do componente): reprocessar um documento substitui chunks e preenche `section_name`.

## 5. Zonas compartilhadas

Nenhuma mudança em `src/shared_kernel/` — consumidores (Dev 2: `policy_analysis`, UI) não precisam de alteração; o ganho aparece automaticamente em `EvidenceRef.section_name` e no filtro `RetrievalQuery.section_name`.
