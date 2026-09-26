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
| T-2a | Sanitizar `_cause` (`application/service.py:216`): nunca `str(exc)` cru — só tipo do erro, estágio e IDs; teste anti-vazamento (mensagem de erro externa não contém texto de chunk) | - | `[//]` | `src/modules/document_processing/application/service.py` | 🟢 | `[ ]` |
| D1-P0-1 | Exceções tipadas por porta (`EmbeddingError`, `IndexingError`, `OcrError`) em `application/ports.py` + retry só no Gemini (3 tentativas, backoff 1s→2s, timeout 30s, 429/5xx) em `infrastructure/indexing.py`; sem retry no Qdrant | T-2a | - | `src/modules/document_processing/application/ports.py`, `infrastructure/indexing.py` | 🟢 | `[ ]` |

## Fase 2 — Contrato de retrieval (P0)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D1-P0-2 | Honrar `RetrievalQuery` (F-14): decidir via caixa postal a semântica de `section_name`/`field_code` (filtro no metadata filter OU remoção do contrato com aceite do Dev 2) e implementar; **teste de contrato por parâmetro** (todo campo chega a `VectorIndex.search` — spy/fake gravando a chamada) | D1-P0-1 | - | `src/modules/document_processing/application/service.py`, `infrastructure/indexing.py`, `tests/modules/document_processing/` | 🟢 | `[ ]` |

## Fase 3 — Gaps de indexação (P0)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D1-P0-3 | Auditoria + gaps (sem re-implementar o verde): (a) teste de isolamento com 2 apólices intercaladas + `QdrantClient` mockado assertando `query_filter` em `query_points`; (b) limite de 100 textos por request de embeddings; (c) eliminar loop do SDK legado (`embed_content` por texto); (d) health-check da coleção com `ProcessingStatus.FAILED("INDEXING: ...")` | D1-P0-2 | - | `src/modules/document_processing/infrastructure/indexing.py`, `tests/modules/document_processing/`, `tests/integration/` | 🟢 | `[ ]` |

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
