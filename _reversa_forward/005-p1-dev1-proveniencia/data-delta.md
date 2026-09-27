# Data Delta: P1 do Desenvolvedor 1 — Proveniência do Chunk e Modo Offline

> Identificador: `005-p1-dev1-proveniencia`
> Data: `2026-09-26`
> Baseline: `ChunkMetadata` de `_reversa_sdd/sdd/shared-kernel-contracts.md#§6.1` + payload de `_reversa_sdd/sdd/document-processing.md#§9 Modelo de Dados` (contrato v1.0.0)

## 1. Resumo

**Um campo opcional** de proveniência: `content_fingerprint` em `ChunkMetadata` e na chave homônima do payload do índice vetorial. Mudança **MINOR** (campo opcional retrocompatível): `CONTRACTS_VERSION` `1.0.0` → `1.1.0`. Nenhuma outra mudança — `EvidenceRef`, `RetrievalQuery`, tabelas DuckDB permanecem iguais.

## 2. Campos novos

| Campo | Onde | Tipo | Obrigatório | Observação |
|-------|------|------|-------------|------------|
| `content_fingerprint` | `ChunkMetadata` (`shared_kernel/contracts.py`) | `str \| None` (sha256 hex, 64 chars) | não (`default=None`) | sha256 do **texto do chunk** |
| `content_fingerprint` | payload do Qdrant (`_payload_from_record`/`_record_from_payload`) | `str \| None` | não | chave opcional; ausência lida como `None` |

## 3. Campos removidos

Nenhum. Nem `section_name`, nem `metadata_version`, nem nenhum campo de v1.0.0 é tocado.

## 4. Migrações necessárias

1. **Obrigatória:** nenhuma — chunks gravados em v1.0.0 continuam válidos (`content_fingerprint = None` na leitura).
2. **Opcional:** repopular fingerprints de documentos existentes via reprocessamento idempotente (delete+upsert por `uuid5` estável já implementado) — basta reprocessar o documento pelo pipeline.
3. **Versão:** `metadata_version` dos chunks novos passa a reportar a versão do contrato (`1.1.0`); a validação de compatibilidade (`shared_kernel/errors.py`) cobre a janela v1.0.0→1.1.0 por ser campo opcional.

## 5. Semântica do campo (fixada para consumidores)

- `content_fingerprint = sha256(texto_do_chunk)` em hex minúsculo, 64 caracteres.
- `None` ⇒ chunk indexado antes de v1.1.0 **ou** fonte sem texto estável — consumidor não deve exigir o campo.
- Recalcular o sha256 do texto recuperado e divergir do valor gravado indica drift (chunk re-escrito, texto corrompido ou merge manual) — **sinal de alerta, não exceção**: o consumidor decide o que fazer (nada muda automaticamente nesta rodada).
- O campo **não** é usado em filtro de busca nem altera ranking.

## 6. Round-trip exigido por teste

```
gravar ChunkRecord(texto T, metadata com fingerprint=sha256(T))
  → recuperar do índice
  → fingerprint recuperado == sha256(T)          # RF-02
gravar ChunkRecord sem fingerprint
  → recuperar
  → fingerprint is None e consumidor não quebra    # retrocompatibilidade
```
