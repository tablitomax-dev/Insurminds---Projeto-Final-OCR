# Actions: P0 do Desenvolvedor 1 — Documental e RAG

> Identificador: `002-p0-dev1-documental-rag`
> Data: `2026-09-26` (ISO 8601)
> Fonte: `_reversa_sdd/learning/plano-acao-dev1.md` v1.0 (método detalhado) · Aceitação: `requirements.md` desta feature
> Convenções: IDs `D1-*`/`T-*` (aprendizados §5.1); granularidade decidida por ação (A-01); caixa postal para contrato (§5.2); gate `T-1` antes de todo PR.

## Resumo

| Métrica | Valor |
|---------|-------|
| Ações desta rodada | 4 (`D1-P0-1`..`D1-P0-3` + `T-2a`) |
| Ordem de execução | `T-2a` → `D1-P0-1` → `D1-P0-2` → `D1-P0-3` |
| Backlog (não executar agora) | `D1-P1-1`, `D1-P1-2`, `D1-P2-1` |

## Análise de granularidade (A-01)

- `D1-P0-1` e `T-2a` são ações atômicas (arquivos e testes bem delimitados).
- `D1-P0-2` é uma ação maior coesa: a semântica dos filtros precisa nascer coerente (contrato + implementação + teste de propagação juntos) — quebrar gera churn de assinatura.
- `D1-P0-3` é uma ação de **auditoria + gaps** (o que já está verde não é refeito); os 4 gaps são verificáveis isoladamente dentro da ação.

## Fase 1 — Segurança e erros (P0)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T-2a | Sanitizar `_cause` (`application/service.py:216`): nunca `str(exc)` cru — só tipo do erro, estágio e IDs; teste anti-vazamento (mensagem de erro externa não contém texto de chunk) | - | `[//]` | `src/modules/document_processing/application/service.py` | 🟢 | `[X]` |
| D1-P0-1 | Exceções tipadas por porta (`EmbeddingError`, `IndexingError`, `OcrError`) em `application/ports.py` + retry só no Gemini (3 tentativas, backoff 1s→2s, timeout 30s, 429/5xx) em `infrastructure/indexing.py`; sem retry no Qdrant | T-2a | - | `src/modules/document_processing/application/ports.py`, `infrastructure/indexing.py` | 🟢 | `[X]` |

## Fase 2 — Contrato de retrieval (P0)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D1-P0-2 | Honrar `RetrievalQuery` (F-14): decidir via caixa postal a semântica de `section_name`/`field_code` (filtro no metadata filter OU remoção do contrato com aceite do Dev 2) e implementar; **teste de contrato por parâmetro** (todo campo chega a `VectorIndex.search` — spy/fake gravando a chamada) | D1-P0-1 | - | `src/modules/document_processing/application/service.py`, `infrastructure/indexing.py`, `tests/modules/document_processing/` | 🟢 | `[X]` |

## Fase 3 — Gaps de indexação (P0)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D1-P0-3 | Auditoria + gaps (sem re-implementar o verde): (a) teste de isolamento com 2 apólices intercaladas + `QdrantClient` mockado assertando `query_filter` em `query_points`; (b) limite de 100 textos por request de embeddings; (c) eliminar loop do SDK legado (`embed_content` por texto); (d) health-check da coleção com `ProcessingStatus.FAILED("INDEXING: ...")` | D1-P0-2 | - | `src/modules/document_processing/infrastructure/indexing.py`, `tests/modules/document_processing/`, `tests/integration/` | 🟢 | `[X]` |

## Backlog da rodada (não executar agora — ver plano de ação)

| ID | Descrição | Quando |
|----|-----------|--------|
| D1-P1-1 | Proveniência rica no chunk (`content_fingerprint` opcional) via caixa postal | P1 |
| D1-P1-2 | Fixtures offline (PDF digital + escaneado gerado; pipeline real com fake de `Embedder`) | P1 |
| D1-P2-1 | Métrica de embedding no log estruturado | P2 |

## Checklist de encerramento (ritual — plano §5)

- [ ] Granularidade desta feature registrada aqui (feito no cabeçalho).
- [ ] Testes primeiro na lógica determinística (A-04).
- [ ] Gate `T-1` verde (`ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider`).
- [ ] Caixa postal usada para qualquer mudança de contrato (uma por vez).
- [ ] Nenhum texto de apólice em erro/log (`T-2a`).
- [ ] Estado remoto checado (`gh pr list --state all`) antes do PR.
- [ ] `regression-watch.md` atualizado e `/reversa-sync` executado ao concluir (plano B: adendo manual).

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial — ações P0 do Dev 1 derivadas de `plano-acao-dev1.md` v1.0 (pós-debate multiagente) | reversa |
| 2026-09-26 | `T-2a`, `D1-P0-1`, `D1-P0-2`, `D1-P0-3` executadas — ver "Notas de execução" | Dev 1 |

## Notas de execução

### Resultado do gate

- `python -B -m pytest -q -p no:cacheprovider` → **173 passed, 4 skipped** (baseline: 137 passed, 4 skipped; +36 testes novos, nenhum removido).
- `ruff` e `mypy` **não instalados neste ambiente** (não estão em `pyproject.toml`); gate `T-1` completo fica pendente de execução onde as ferramentas existirem.
- **Nenhum ajuste foi necessário em `tests/e2e/test_vertical_slice.py`.** Fakes ampliados de forma mínima em `tests/fakes/document_processing.py` (sem enfraquecer nenhuma guarda): `InMemoryVectorIndex` ganhou spy `search_calls`, filtro real por `section_name` e falha injetável `ensure_collection_error`.

### T-2a — Sanitização de erro

- `_cause` (`application/service.py`) agora retorna **apenas `type(exc).__name__`** — nunca `str(exc)`. Mensagem do status: `"{ESTÁGIO}: {tipo}"` (estágio `EXTRACT:`/`OCR:`/`INDEXING:`); IDs já vão no próprio `ProcessingStatus`.
- Testes anti-vazamento para extrator, OCR e embedder (mensagem da exceção com texto de política) + teste de log via `_LoggingStatusSink`/`caplog`. As 3 asserções antigas que esperavam `str(exc)` cru foram atualizadas para o tipo da exceção.

### D1-P0-1 — Erros tipados por porta + retry só no Gemini

- Exceções em `application/ports.py` (base `PortError`): `TextExtractionError`, `OcrError`, `EmbeddingError`, `IndexingError` — mensagens sempre sanitizadas (só tipo do erro externo + IDs).
- Adapters traduzem erro externo para a exceção da porta: `extractors.py` (PyMuPDF/PaddleOCR), `indexing.py` (Gemini/Qdrant).
- Retry **somente** no `GeminiEmbedder`: 3 tentativas, backoff exponencial 1s→2s, timeout 30s por chamada (via `HttpOptions(timeout=30000)` — unidade do SDK google-genai é milissegundos), **apenas** em erros transitórios (429/5xx/timeouts/conexão — classificação em `is_transient_error`). Sleep injetável (`sleep=`) e monkeypatchável (`time.sleep` resolvido em tempo de chamada).
- **Qdrant sem retry** (testado: 1 chamada só, mesmo com erro transitório).

### D1-P0-2 — Semântica de `section_name`/`field_code` (F-14) — ESCOLHA

- **Escolha:** `section_name` → **filtro de metadata na consulta** (`FieldCondition(key="section_name")` no `query_filter` do Qdrant; filtro equivalente no fake em memória). `field_code` → **hint determinístico de consulta**: consumido por `compose_search_text` no formato fixo `"{query}\n[campo: {field_code}]"` (mesma entrada ⇒ mesmo texto), que é o texto embutido; além disso o campo é **propagado explicitamente** até `VectorIndex.search(field_code=...)` — nunca descartado em silêncio.
- **Alternativas descartadas:**
  1. *Caixa postal para remover `field_code` de `RetrievalQuery`* — mudaria contrato compartilhado (v1.0.0) e dependia de aceite do Dev 2 antes do P0; desnecessária, já que o campo tem consumo útil.
  2. *Caixa postal para colocar `field_code` no payload do chunk e filtrar de verdade* — mudança de payload com reindexação; certa a médio prazo (ver abaixo), pesada para esta rodada.
  3. *Descartar em silêncio* (status quo) — proibido (F-14).
- **Por quê:** é a solução mais simples que elimina o descarte semântico **sem tocar o `shared_kernel`**, com semântica determinística e testada por contrato por parâmetro (`tests/modules/document_processing/test_retrieval_contract.py`: para cada campo de `RetrievalQuery` — `query`, `top_k`, `policy_id`, `document_id`, `section_name`, `field_code` — há teste provando chegada à porta `VectorIndex.search` via spy e consumo com efeito observável).
- **Evolução prevista (sem caixa postal nesta rodada):** quando PP-Structure/`section_name` real entrar (NG-01) e/ou `D1-P1-1` abrir caixa postal de payload, `field_code` pode virar campo persistido → vira filtro automático em `search` (o parâmetro já está na porta). Aí sim abrir `contract-delta-*.md`.
- **Aviso ao Dev 2 (mudança de semântica percebida pelo consumidor):** (1) `section_name` agora **filtra de verdade** — como `build_chunk_metadata` ainda produz `section_name=None` (até PP-Structure), consulta com `section_name` explícito devolve vazio hoje; (2) `field_code` muda o vetor de busca (hint concatenado) — quem manda `field_code` (ex.: `ExtractionService`) passa a ter o código do campo refletido na similaridade.

### D1-P0-3 — Gaps de indexação (só o que faltava)

- (a) Teste de isolamento com 2 apólices **intercaladas** (A, B, A — consulta da A devolve só A) + teste do `QdrantVectorIndex` com `QdrantClient` **mockado** provando que `query_filter` (policy_id/document_id/section_name) chega em `query_points` — filtro NA consulta.
- (b) `MAX_EMBEDDING_TEXTS_PER_REQUEST = 100`: 250 textos ⇒ 3 requests (100/100/50), testado contando chamadas.
- (c) Loop do SDK legado eliminado: `google.generativeai.embed_content` agora recebe a **lista** de textos (chamada em lote, `response.embeddings`) — testado que 3 textos ⇒ 1 chamada em ambos os SDKs. Fallback legado **mantido** (o SDK legado suporta lote; alternativa de removê-lo foi descartada para não quebrar ambientes só com `google-generativeai`). Imports lazy continuam; normalização de resposta tolera attr/dict (formatos diferentes entre SDKs).
- (d) Health-check (`ensure_collection`) movido para **antes** de gerar embeddings (fail-fast: não gasta cota de embedding com Qdrant fora); falha classificada `ProcessingStatus.FAILED("INDEXING: ...")` **sem crash** — testado (embedder nunca é chamado; status publicado).
- Nada do que já estava verde foi refeito (upsert em lote, idempotência, filtro de policy/document, chunking 800/100 intactos).
