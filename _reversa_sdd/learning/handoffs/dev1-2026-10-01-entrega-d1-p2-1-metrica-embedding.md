# Handoff Dev 1 → Dev 2 — entrega `D1-P2-1` (métrica de embeddings, 2026-10-01)

> **Autor:** Dev 1 (pbena + assistente) · **Destinatário:** Dev 2 (leitura do assistente de IA)
> **Branch:** `feat/d1-p2-1-metrica-embedding` (base: `main`) · **PR #13** mesclado em 2026-10-02 (merge `00580ea`, commit `f5fa268`)
> **Gate `T-1`:** verde 3× antes do PR — `ruff` ok · `mypy` Success · `pytest` 303 passed, 4 skipped; no `main` unificado: **323 passed, 4 skipped**.

## 1. Escopo (quadrado do Dev 1, `document_processing`)

Métrica de embeddings no **log estruturado** do adapter `infrastructure/indexing.py` — um evento por request de embedding (logger `document_processing.embedding`), no padrão do `_record_usage` do `llm_agent.py` de vocês: `{"kind": "EMBED", "model_name", "texts", "total_tokens", "latency_ms"}`. Extração defensiva de `usage_metadata` entre SDKs (sem reporte → `0`).

## 2. Efeito para o quadrado do Dev 2

**Nenhum.** Nenhuma assinatura, contrato ou comportamento mudou — só telemetria interna (custo/latência de embedding). `shared_kernel` intocado.

## 3. Anti-vazamento (T-2a)

- Só números e nomes de modelo no evento — **nunca** texto de apólice, chunk ou embedding.
- Teste dedicado garante que literal de apólice não aparece no log; mesmo padrão do `test_service.py` da `dev1-006`.

## 4. FECHAMENTO (2026-10-02)

- **PR #13 mesclado** em `main` (merge `00580ea`, 2026-10-02T02:15:35Z) — independente do PR #12 (`dev1-006`, merge `1291cd6`); zero conflito entre os dois (arquivos distintos).
- **Gate `T-1` no `main` unificado (`00580ea`):** `ruff` All checks passed · `mypy` Success (68 arquivos) · `pytest` **323 passed, 4 skipped**.
