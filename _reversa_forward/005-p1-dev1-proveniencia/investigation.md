# Investigação: P1 do Desenvolvedor 1 — Proveniência do Chunk e Modo Offline

> Identificador: `005-p1-dev1-proveniencia`
> Data: `2026-09-26`

## 1. Pesquisa de fundo

- **Estado verificado no código (2026-09-26):** `ChunkMetadata` vive em `src/shared_kernel/contracts.py` (campos: `chunk_id`, `document_id`, `policy_id`, `page_number`, `chunk_index`, `source_type`, `ocr_confidence`, `section_name`, `metadata_version`); `CONTRACTS_VERSION = "1.0.0"` em `src/shared_kernel/version.py`. O payload do Qdrant é montado/desserializado por `_payload_from_record`/`_record_from_payload` em `document_processing/infrastructure/indexing.py` — os pontos exatos do round-trip. IDs de ponto são estáveis (`uuid5` por `chunk_id`), upsert idempotente (delete+upsert) — reprocessamento para popular fingerprints é seguro.
- **Origem do aproveitamento:** `_reversa_sdd/learning/benchmark-repos-referencia.md#§2.4` (proveniência rica no chunk: hash do conteúdo rastreia integridade do texto indexado) e `#§2.6` (fixtures offline para pipeline sem rede).
- **Semântica do fingerprint:** sha256 **do texto do chunk** (não do PDF, não do `chunk_id`) — prova que o texto recuperado é o texto indexado; qualquer edição/refix de chunk muda o hash e fica visível.

## 2. Alternativas avaliadas

| Tema | Alternativa adotada | Descartadas | Por quê |
|------|---------------------|-------------|---------|
| Granularidade do hash | Por chunk (texto do chunk) | Hash do PDF inteiro; hash por página | O consumidor confere integridade da unidade que cita (chunk/Evidência) |
| Algoritmo | sha256 (hex, 64 chars) | md5/xxhash (mais rápido, mais fraco); CRC | Colisão desprezível, padrão de integridade, custo irrelevante em texto curto |
| Onde expor o campo | Payload do chunk (`ChunkMetadata`) | Em `EvidenceRef`; coluna nova em tabela DuckDB | Proveniência é do chunk indexado; `EvidenceRef` é contrato de consumo e não deve crescer sem necessidade (§4.3 do plano Dev 1) |
| Mecânica de contrato | Caixa postal + bump MINOR `1.0.0→1.1.0` | Commit direto com aviso no PR; campo "só pra uso interno" | Convenção §5.2 absoluta; payload privado é anti-padrão reprovado pelo próprio plano |
| Fixture "escaneada" | PDF imagem-única commitado, gerado por receita documentada | Gerar no teste a cada run; usar PDF real escaneado | Reprodutibilidade; PDF real tem dado sensível (F-12/T-2) |
| Escopo do modo offline | Pipeline real + fake só do `Embedder` | Fakes de OCR/chunking também (não testa nada de real); Qdrant remoto | Definição corrigida pela crítica C2-05; Docker local = offline |
| Flag de truncamento | Não criar | Criar campo `truncated` "por garantia" | RN-04: o pipeline nunca trunca; flag nasce só com truncamento real (PP-Structure futuro) |

## 3. Fontes externas e padrões aplicáveis

- **Content-addressed integrity:** registrar hash do conteúdo junto ao dado persistido é o padrão de proveniência de data pipelines (detecção silenciosa de drift entre texto indexado e texto recuperado).
- **Testes opt-in por marker:** padrão de testes que dependem de infraestrutura local (Docker) — marker `integration` registrado no `pyproject.toml` (aprendizado F-03: marker sem registro gera warning e esconde configuração ausente).
- **Geração de PDF imagem-única:** receita com PyMuPDF (já dependência do projeto): página nova com imagem raster embutida → nenhum objeto de texto no PDF.
- Referências internas: `_reversa_sdd/learning/plano-acao-dev1.md#D1-P1-1` e `#D1-P1-2`, `_reversa_sdd/learning/aprendizados.md#§5.2`, `_reversa_sdd/sdd/shared-kernel-contracts.md#§6.1`.

## 4. Padrões anti-reincidência (aprendizados)

- Parâmetro/campo de contrato nunca é ignorado em silêncio (F-14) → o campo novo tem teste de round-trip (propagação gravada e lida de volta).
- Mudança em zona compartilhada só com aceite por escrito (A-02/§5.2) → o `contract-delta-chunkmetadata.md` é artefato **pré-código**, com data e assinatura do aceite.
- Decisão de implementação registrada (A-10) → este `investigation.md` + notas em `actions.md`.
- Teste "pronto quando" real, sem frase autocontraditória (C2-05) → "offline" = rede de embeddings fakes; o teste declara real vs fake no próprio código.
