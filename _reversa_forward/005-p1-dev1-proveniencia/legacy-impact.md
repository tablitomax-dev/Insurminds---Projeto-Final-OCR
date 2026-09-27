# Legacy Impact: P1 do Desenvolvedor 1 — Proveniência do Chunk e Modo Offline

> Identificador: `005-p1-dev1-proveniencia`
> Data: `2026-09-27` (ISO 8601)
> Feature **greenfield**, sem legado pré-existente. Âncora: `prd.md` + specs SDD (`_reversa_sdd/sdd/`).
> Política de edição do legado no momento da execução: `allowLegacyEdits: true`; `allowedPaths` = `["src/**", "tests/**", "pyproject.toml", "requirements.txt", ".gitignore"]` (todas as escritas desta feature casaram com a lista).

## Arquivos afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|-----------------|------------|------|------------|---------------|
| `src/shared_kernel/contracts.py` | `_reversa_sdd/sdd/shared-kernel-contracts.md#§6.1 Requisitos Funcionais` | contrato-alterado | MEDIUM | Campo opcional `content_fingerprint: str \| None = None` em `ChunkMetadata` (v1.1.0) — mudança MINOR via caixa postal (`contract-delta-chunkmetadata.md`) |
| `src/shared_kernel/version.py` | `_reversa_sdd/sdd/shared-kernel-contracts.md#§6.1` | contrato-alterado | LOW | `CONTRACTS_VERSION` `1.0.0` → `1.1.0` (MINOR retrocompatível; quem propõe bumpa) |
| `src/modules/document_processing/domain/chunk_fingerprint.py` | `_reversa_sdd/sdd/document-processing.md#§9 Modelo de Dados` | componente-novo | LOW | Função pura `compute_content_fingerprint` (sha256 hex do texto do chunk) |
| `src/modules/document_processing/application/service.py` | `_reversa_sdd/sdd/document-processing.md#§6.1 Requisitos Funcionais` | regra-alterada | LOW | Preenche `content_fingerprint` ao montar o `ChunkRecord` (proveniência em todo chunk indexado) |
| `src/modules/document_processing/infrastructure/indexing.py` | `_reversa_sdd/sdd/document-processing.md#§9 Modelo de Dados` | delta-de-dados | MEDIUM | Payload do Qdrant ganha a chave opcional `content_fingerprint` no round-trip (`_payload_from_record`/`_record_from_payload`) |
| `tests/fixtures/aplice_digital.pdf`, `tests/fixtures/aplice_escaneada.pdf` | `_reversa_sdd/sdd/document-processing.md#§6.1` | componente-novo | — | Fixtures < 100 KB (digital com camada de texto; "escaneado" imagem única sem texto) |
| `tests/integration/test_fixtures_pdf.py` | `_reversa_sdd/sdd/document-processing.md#§6.1` | componente-novo | — | Prova a ausência de camada de texto do "escaneado" (stdlib puro, roda sempre) |
| `tests/integration/test_pipeline_offline.py` | `_reversa_sdd/sdd/document-processing.md#§6.1` | componente-novo | — | Integração opt-in (`-m integration`) offline, fake apenas do `Embedder` |
| `tests/modules/document_processing/test_fingerprint.py` | specs `document-processing` | componente-novo | — | Testes da função pura (vetores FIPS 180-2) |
| `tests/modules/document_processing/test_indexing.py` | specs `document-processing` | regra-alterada | — | Round-trip do fingerprint + retrocompatibilidade do payload legado |
| `tests/contracts/test_packaging.py` | `_reversa_sdd/sdd/shared-kernel-contracts.md#§6.1` | regra-alterada | LOW | Guard de versão do contrato acompanhado para `1.1.0` |
| `pyproject.toml` | `_reversa_sdd/learning/aprendizados.md#§5.2` | regra-alterada | LOW | Comentário do `per-file-ignores` atualizado (mudanças no contrato só via caixa postal + bump) |

## Diff conceitual por componente

- **shared_kernel (contrato):** `ChunkMetadata` ganha **um campo opcional** de proveniência (`content_fingerprint`) e o contrato sobe para v1.1.0 — MINOR retrocompatível, precedido de caixa postal com aceite registrado; `EvidenceRef` permanece intacto.
- **document_processing (domínio/aplicação):** nasce a função pura de resumo de conteúdo; o orquestrador do pipeline passa a marcar cada chunk com o sha256 do próprio texto.
- **document_processing (infraestrutura):** o payload do índice vetorial carrega a chave opcional (grava e lê de volta); chunks gravados antes de v1.1.0 continuam válidos com `None`.
- **testes:** fixtures offline (PDF digital + "escaneado" imagem única), prova de camada de texto, round-trip do fingerprint e teste de integração opt-in com declaração real vs fake.

## Preservadas

Nenhuma regra 🟢 extraída foi alterada sem autorização: a única zona compartilhada tocada (`ChunkMetadata`) mudou **via caixa postal** com aceite registrado (RN-01/RN-02); `EvidenceRef` não muda; `chunk_text` segue sem truncamento (nenhuma flag de truncamento nasce — RN-04); a comparação determinística e o loop de revisão (adendos 002/003) seguem intactos.

## Modificadas

Nenhuma regra 🟢 removida; as linhas `regra-alterada`/`delta-de-dados` da tabela acima são extensões aditivas e retrocompatíveis (campo opcional, chave opcional no payload, guard de versão acompanhado).
