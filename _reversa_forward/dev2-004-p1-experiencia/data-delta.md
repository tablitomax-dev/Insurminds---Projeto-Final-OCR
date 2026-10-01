# Data Delta: P1 do Desenvolvedor 2 — Experiência e Governança da Análise

> Identificador: `dev2-004-p1-experiencia`
> Data: `2026-09-26`
> Baseline: modelo de dados de `_reversa_sdd/sdd/policy-analysis.md#§9 Modelo de Dados` + delta do adendo 003 (tabela `reviews`)

## 1. Resumo

**Nenhuma mudança de schema.** As 6 tabelas DuckDB vigentes (`policies`, `documents`, `facts`, `comparisons`, `evidences`, `reviews`) permanecem intactas. `Issue`/`QualityReport` são derivados de dados já persistidos; `UsageMetrics` vive em log estruturado + memória de processo.

## 2. Campos novos

| Campo | Onde | Tipo | Obrigatório | Observação |
|-------|------|------|-------------|------------|
| `Issue.severity` | modelo em memória (`domain/quality.py`) | enum `CRÍTICO\|ALTO\|MÉDIO\|BAIXO` | sim | derivado, não persistido |
| `Issue.field_code` | modelo em memória | str (catálogo de 10) | sim | |
| `Issue.reason` | modelo em memória | str sanitizado | sim | sem texto de apólice (`T-2a`) |
| `Issue.evidence_ref` | modelo em memória | `EvidenceRef` ou None | não | aponta a evidência quando o sinal tem origem documental |
| `UsageRecord.tokens` | log estruturado | int (prompt + completion) | sim | por chamada de LLM |
| `UsageRecord.cost_usd` | log estruturado | decimal | sim | tabela de preços USD versionada (D-04) |
| `UsageRecord.latency_ms` | log estruturado | int | sim | por chamada de LLM |
| `run_id` (agregado) | log estruturado | str | sim | mesma chave de `RetrievalResult`/execução |

## 3. Campos removidos

Nenhum. `requires_human_review` permanece no contrato (`ExtractedFact`) — RN-01.

## 4. Migrações necessárias

Nenhuma. Sem `ALTER TABLE`, sem baseline nova do DuckDB.

## 5. Derivação de `Issue` (mapa sinal → severidade proposta)

| Sinal existente | Origem | Severidade |
|-----------------|--------|------------|
| Violação de regra por campo (`rule_violations`) | `domain/rules.py` | `ALTO` |
| `NEEDS_REVIEW` sem violação de regra (LLM incerto) | `application/extraction.py` | `MÉDIO` |
| Falha de ancoragem/validação pós-LLM (`LlmOutputError`) | `domain/anchoring.py` | `CRÍTICO` |
| Sinal informativo sem violação de regra (fato sinalizado pelo LLM, `requires_human_review`) | `application/extraction.py` | `BAIXO` |

> A severidade por sinal é decisão de implementação proposta aqui; o teste de `RF-01` fixa o mapeamento. Mudança de severidade por sinal não é mudança de contrato (fora do `shared_kernel`).
