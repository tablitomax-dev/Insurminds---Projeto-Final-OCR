# Actions: P1 do Desenvolvedor 2 — Experiência e Governança da Análise

> Identificador: `004-p1-dev2-experiencia`
> Data: `2026-09-26` (ISO 8601)
> Fonte: `roadmap.md` + `data-delta.md` desta feature · Método: `_reversa_sdd/learning/plano-acao-dev2.md` v1.0 (`D2-P1-1`, `D2-P1-2`, `D2-P1-4`)
> Convenções: IDs `D2-*`/`T-*` (aprendizados §5.1); ação atômica = um turno de agente (A-01); gate `T-1` antes de todo PR; nenhum texto de apólice em métrica/erro (`T-2a`).

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 11 |
| Paralelizáveis (`[//]`) | 5 (`D2-P1-1a`, `D2-P1-2a`, `D2-P1-4a`, `D2-P1-1d`, `D2-P1-2e`) |
| Maior cadeia de dependência | 6 (`D2-P1-2a` → `D2-P1-2b` → `D2-P1-4b` → `D2-P1-4c` → `D2-P1-2e` → `D2-P1-4d`) |
| Fora desta feature (backlog) | `D2-P1-3` (apólices reais — externo), `D2-P2-1`..`D2-P2-3` |

## Análise de granularidade (A-01)

- `D2-P1-1a`/`D2-P1-2a` são modelos puros + testes — atômicos e paralelizáveis entre si.
- `D2-P1-1b` mantém derivação **e** agregação juntas: o mapa sinal→severidade só faz sentido com o `QualityReport` que o consome (quebrar gera churn de assinatura).
- `D2-P1-2b` e `D2-P1-2c` estão separados: instrumentar e provar anti-vazamento são blocos distintos de verificação (RF-03 vs RF-04).
- `D2-P1-4c` é a maior ação (decomposição da UI), mas é um refactor coeso — quebrar por componente geraria estados intermediários com a jornada quebrada.

## Fase 1 — Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P1-4a | Composition root: `src/composition_root/` montando `create_default_document_processing` + `create_default_policy_analysis` num só lugar; estender `tests/architecture/test_imports.py` para varrer `src/ui` **e** `src/composition_root` (F-15: regra arquitetural cobre todo o alvo) | - | `[//]` | `src/composition_root/`, `tests/architecture/test_imports.py` | 🟢 | `[X]` |

## Fase 2 — Testes (modelos puros primeiro, A-04)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P1-1a | Modelos puros `Issue` (enum `CRÍTICO\|ALTO\|MÉDIO\|BAIXO`; `severity`, `field_code`, `reason`, `evidence_ref`) e `QualityReport` em `domain/quality.py` + testes cobrindo cada valor de severidade | - | `[//]` | `src/modules/policy_analysis/domain/quality.py`, `tests/modules/policy_analysis/test_quality.py` | 🟢 | `[X]` |
| D2-P1-2a | Modelo `UsageRecord` (tokens, custo USD, latência por chamada) + agregado por `run_id` em `domain/metrics.py`; tabela de preços USD versionada com data de referência em `infrastructure/pricing.py` + testes (custo = tokens × preço; tabela registra data) | - | `[//]` | `src/modules/policy_analysis/domain/metrics.py`, `infrastructure/pricing.py`, `tests/modules/policy_analysis/test_metrics.py` | 🟢 | `[X]` |

## Fase 3 — Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P1-1b | Derivação de `Issue` dos sinais **já existentes** (mapa do `data-delta.md`: falha de ancoragem/validação = `CRÍTICO`; regra de campo violada = `ALTO`; `NEEDS_REVIEW` = `MÉDIO`; informativo = `BAIXO`) + `QualityReport` por documento e por comparação em `application/quality.py` — sem novo detector | D2-P1-1a | - | `src/modules/policy_analysis/application/quality.py`, `tests/modules/policy_analysis/test_quality.py` | 🟢 | `[X]` |
| D2-P1-2b | Instrumentar `llm_extractors.py` (`extract`/`explain`): cada chamada registra `UsageRecord` (tokens, latência medida, custo via `pricing`) no coletor por `run_id` + log estruturado **sem texto de apólice** | D2-P1-2a | - | `src/modules/policy_analysis/infrastructure/llm_extractors.py`, `tests/modules/policy_analysis/test_metrics.py` | 🟡 | `[X]` |
| D2-P1-2c | Teste anti-vazamento de métricas (RF-04): run com texto marcador de apólice → `UsageMetrics`, logs e erros não contêm o marcador | D2-P1-2b | - | `tests/modules/policy_analysis/test_metrics.py` | 🟢 | `[X]` |

## Fase 4 — Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P1-4b | Fachada: `list_issues`, `get_quality_report`, `get_usage_metrics` (último run e por `run_id`) em `public_api.py`, consumindo `application/quality` e `domain/metrics` | D2-P1-1b, D2-P1-2b | - | `src/modules/policy_analysis/public_api.py` | 🟢 | `[X]` |
| D2-P1-4c | Decompor `src/ui/app.py` em `src/ui/components/` (upload, estágios, revisão, comparação, export), recebendo as fachadas do composition root; nenhum SQL/consulta vetorial/prompt na UI; a jornada do onboarding funciona sem pular etapa | D2-P1-4a, D2-P1-4b | - | `src/ui/app.py`, `src/ui/components/` | 🟢 | `[X]` |

## Fase 5 — Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P1-1d | Componente de revisão: fila agrupada e ordenada por severidade (`CRÍTICO`→`BAIXO`); cada item mostra `field_code`, motivo e evidência | D2-P1-4b, D2-P1-4c | `[//]` | `src/ui/components/` (revisão), `tests/ui/` | 🟢 | `[X]` |
| D2-P1-2e | Painel de métricas na UI: tokens, custo estimado (USD, com data de referência da tabela) e latência do último run; declara que mostra o último run do processo | D2-P1-4b, D2-P1-4c | `[//]` | `src/ui/components/` (métricas), `tests/ui/` | 🟢 | `[X]` |
| D2-P1-4d | E2E da jornada (upload → estágios → revisão → comparação → export) com fila por severidade e painel de métricas; registrar decisões (A-10) e preencher `regression-watch.md` | D2-P1-1d, D2-P1-2e | - | `tests/e2e/`, `_reversa_forward/004-p1-dev2-experiencia/` | 🟢 | `[X]` |

## Checklist de encerramento (ritual — plano Dev 2 §5)

- [ ] Granularidade registrada nesta tabela (feito no cabeçalho).
- [ ] Todo output de LLM tem teste de falha; todo output de métrica tem teste anti-vazamento (`T-2a`).
- [ ] Gate `T-1` verde (`ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider`).
- [ ] Musts do PRD §9 relidos ao fechar escopo (F-16) — nenhum Must novo esquecido.
- [ ] `requires_human_review` intacto no contrato (RN-01).
- [ ] Estado remoto checado (`gh pr list --state all`) antes do PR.
- [ ] `regression-watch.md` atualizado e `/reversa-sync` executado ao concluir (plano B: adendo manual).

## Notas de execução

<!-- Reservado para /reversa-coding registrar avisos ou observações da execução. -->

- **Decisões registradas (A-10):**
  1. `Issue` ganhou `policy_id` além dos campos do `data-delta.md` (issue precisa ser localizável na fila) — aditivo, sem contrato de `shared_kernel`.
  2. `BAIXO` deixou de ser "reservado" e passou a representar o fato sinalizado pelo LLM sem violação (`requires_human_review`) — fecha o mapa sinal→severidade e torna o agrupamento da fila total; `data-delta.md` atualizado.
  3. Lógica pura da UI (`group_by_severity`, `format_usage_summary`) ficou em `src/ui/logic.py` **sem `streamlit`**: os testes do sandbox não têm a lib e a lógica precisa ser testável isoladamente; os componentes apenas apresentam.
  4. Métricas: instrumentação local no adapter (`_usage_tokens` defensivo entre versões do SDK) + coletor por `run_id`; persistência durável = log estruturado `policy_analysis.usage` (decisão D-03 do roadmap).
  5. Tabela de preços `USD_PER_1M_TOKENS` com `PRICE_REFERENCE_DATE = "2026-09-26"`; modelo fora da tabela → custo `None` exibido como "n/d" (nada de número inventado).
- **Ambiente:** `streamlit` não está instalado no sandbox de testes — a UI é validada pelos helpers puros + teste de arquitetura; o smoke manual da UI fica no `onboarding.md`.
- **Gate `T-1`:** verde 3× consecutivas em 2026-09-26 (`ruff` All checks passed; `mypy` Success 59 arquivos; `pytest` 271 passed, 4 skipped).

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-to-do` | reversa |
