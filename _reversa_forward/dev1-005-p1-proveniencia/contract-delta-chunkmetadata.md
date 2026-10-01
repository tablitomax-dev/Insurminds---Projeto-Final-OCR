# Caixa postal — Contract Delta: `ChunkMetadata`

> Proposta: **D1-P1-1a** (feature `dev1-005-p1-proveniencia`)
> Proponente: **Desenvolvedor 1** · Destinatário de aceite: **Desenvolvedor 2**
> Data da proposta: `2026-09-26` (ISO 8601)
> Prazo de resposta: **1 dia útil** — silêncio = escalada ao humano (`_reversa_sdd/learning/aprendizados.md#§5.2`)
> Regra: uma mudança de contrato por vez (esta é a única em aberto)

## Proposta

Adicionar **um campo opcional** ao modelo `ChunkMetadata` (`src/shared_kernel/contracts.py`):

```python
content_fingerprint: str | None = None
```

- **Semântica:** `sha256` (hex, 64 chars, minúsculo) do **texto do chunk** (não do PDF, não do `chunk_id`).
- **`None`** ⇒ chunk indexado antes de v1.1.0 ou fonte sem texto estável — consumidores **não podem exigir** o campo.
- **Uso:** proveniência/integridade — comparar o hash gravado com o sha256 do texto recuperado detecta drift (chunk reescrito, corrompido ou merge manual). Divergência é **sinal de alerta**, não exceção.
- **Fora de escopo:** o campo não entra em filtro de busca, não altera ranking e não aparece em `EvidenceRef`.

## Impacto na versão

| Item | Valor |
|------|-------|
| Mudança | Aditiva, retrocompatível (campo opcional com default `None`) |
| Bump | `CONTRACTS_VERSION` `1.0.0` → **`1.1.0`** (MINOR) — quem propõe bumpa (`§5.2`) |
| Consumidores impactados | `document_processing/infrastructure/indexing.py` (payload Qdrant round-trip); Dev 2 **sem impacto obrigatório** (fachadas de análise não leem payload de chunk) |
| Migração | Nenhuma obrigatória; chunks v1.0.0 seguem válidos; repopular via reprocessamento idempotente é opcional |
| Payload Qdrant | Chave opcional `content_fingerprint` em `_payload_from_record`/`_record_from_payload` |

## Alternativas descartadas pelo proponente

1. Campo obrigatório — quebraria consumidores (MAJOR); não há necessidade.
2. Hash do PDF por documento — granularidade errada: a unidade citada/ancorada é o chunk.
3. Expor em `EvidenceRef` — contraria o contrato único do `shared_kernel` como contrato de consumo (plano Dev 1 §4.3).

## Aceite / Negativa

> **Preencher esta seção — é o registro obrigatório (§5.2).**
>
> - [X] **Aceito** — Dev 2: <nome/data>
> - [ ] **Negado** — Dev 2: <nome/data + motivo>
>
> Resposta do Dev 2: _silêncio após 1 dia útil (proposta de 2026-09-26) — escalada ao humano (`§5.2`). Humano (**pbena**) decidiu prosseguir com a entrega ("continue a 005 até acabar") em 2026-09-27; a proposta é aceita como base do `D1-P1-1c`/`D1-P1-1d`, sem prejuízo de revisão posterior no PR._

## Registro

| Data | Evento |
|------|--------|
| 2026-09-26 | Proposta escrita (D1-P1-1a); aguardando aceite. Código de contrato/payload **bloqueado** até o aceite (`D1-P1-1c`/`D1-P1-1d`) |
| 2026-09-27 | Silêncio do Dev 2 → escalada ao humano; aceite registrado por decisão humana (pbena). `D1-P1-1c`/`D1-P1-1d` desbloqueados |
