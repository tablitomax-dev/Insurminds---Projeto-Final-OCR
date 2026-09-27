# Adendo: P1 do Desenvolvedor 1 — Proveniência do Chunk e Modo Offline

> Identificador: `005-p1-dev1-proveniencia`
> Data: `2026-09-27` (ISO 8601)
> Cenário: `greenfield`
> Gerado por `/reversa-sync` após a implementação das ações P1 (`D1-P1-1a`..`D1-P1-1e`, `D1-P1-2a`..`D1-P1-2b` — 7/7 concluídas)

## Vigência

Vigente desde 2026-09-27.

## Resumo da entrega

O chunk indexado ganhou proveniência verificável e o projeto ganhou modo de teste offline confiável. `ChunkMetadata` recebeu o campo **opcional** `content_fingerprint` (sha256 hex do **texto do chunk**) e o contrato subiu para **v1.1.0** (MINOR retrocompatível, precedido de caixa postal `contract-delta-chunkmetadata.md` com aceite registrado); o pipeline passa a marcar cada chunk com o resumo do próprio texto e o payload do índice vetorial faz o round-trip do campo — divergência entre o resumo gravado e o do texto recuperado é sinal de alerta, nunca exceção. Em paralelo, nasceram fixtures offline (1 PDF digital + 1 PDF "escaneado" imagem-única sem camada de texto, &lt; 100 KB cada, com a ausência de texto provada por teste stdlib) e o teste de integração opt-in (`-m integration`) que roda o **pipeline real** sem internet com **fake apenas do `Embedder`**, declarando real vs fake. Nenhuma flag de truncamento criada (RN-04). Suíte do projeto após a entrega: 280 passed, 6 skipped (esta feature contribuiu com +9 testes); gate local `ruff + mypy + pytest` verde 3× consecutivas.

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `_reversa_sdd/sdd/shared-kernel-contracts.md` | §6.1 Requisitos Funcionais | contrato-alterado | `ChunkMetadata` ganha o campo opcional `content_fingerprint: str \| None = None` (sha256 hex 64 do texto do chunk; `None` = chunk legado ou fonte sem texto estável — consumidores não podem exigir) + `CONTRACTS_VERSION` `1.0.0` → `1.1.0` (MINOR retrocompatível). Mudança precedida de caixa postal com aceite registrado (§5.2); `EvidenceRef` permanece intacto |
| `_reversa_sdd/sdd/document-processing.md` | §9 Modelo de Dados | componente-novo | `domain/chunk_fingerprint.py`: função pura `compute_content_fingerprint(text)` (determinística, vetores FIPS 180-2 testados) |
| `_reversa_sdd/sdd/document-processing.md` | §6.1 Requisitos Funcionais | regra-alterada | O pipeline marca todo chunk com o fingerprint do próprio texto ao montar o `ChunkRecord` (proveniência em cada chunk indexado; adapter segue serializando apenas) |
| `_reversa_sdd/sdd/document-processing.md` | §9 Modelo de Dados | delta-de-dados | Payload do índice vetorial ganha a chave **opcional** `content_fingerprint` no round-trip (`_payload_from_record`/`_record_from_payload`); chunks gravados antes de v1.1.0 voltam `None` e seguem válidos — sem migração obrigatória |
| `_reversa_sdd/sdd/document-processing.md` | §6.1 Requisitos Funcionais | componente-novo | Modo offline: fixtures `tests/fixtures/` (digital + "escaneado" imagem única, receita documentada), teste de prova de camada de texto e teste opt-in `-m integration` com pipeline real (PyMuPDF + PaddleOCR + Qdrant local) e fake apenas do `Embedder` |

## Regras sob vigilância

Nenhum watch item na tabela principal (cenário greenfield). Observações sem peso de regressão: `O001`..`O005` em `_reversa_forward/005-p1-dev1-proveniencia/regression-watch.md` — destaque para `O004`: o teste opt-in de integração **não roda no dia a dia** e deve ser executado explicitamente antes de todo PR (`pytest -m integration`).

## Fontes

- `_reversa_forward/005-p1-dev1-proveniencia/requirements.md`
- `_reversa_forward/005-p1-dev1-proveniencia/actions.md`
- `_reversa_forward/005-p1-dev1-proveniencia/progress.jsonl`
- `_reversa_forward/005-p1-dev1-proveniencia/legacy-impact.md`
- `_reversa_forward/005-p1-dev1-proveniencia/regression-watch.md`
- `_reversa_forward/005-p1-dev1-proveniencia/decisions.md`
- `_reversa_forward/005-p1-dev1-proveniencia/contract-delta-chunkmetadata.md`
