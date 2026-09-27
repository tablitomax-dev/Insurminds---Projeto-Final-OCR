# Adendo: P1 do Desenvolvedor 2 — Experiência e Governança da Análise

> Identificador: `004-p1-dev2-experiencia`
> Data: `2026-09-26` (ISO 8601)
> Cenário: `greenfield`
> Gerado por `/reversa-sync` após a implementação das ações P1 (`D2-P1-1a`..`D2-P1-1d`, `D2-P1-2a`..`D2-P1-2e`, `D2-P1-4a`..`D2-P1-4d` — 11/11 concluídas)

## Vigência

Vigente desde 2026-09-26.

## Resumo da entrega

A análise ganhou governança e observabilidade aditivas: problemas de qualidade passaram a existir como `Issue` com severidade (`CRÍTICO | ALTO | MÉDIO | BAIXO`), derivados **apenas** dos sinais que o pipeline já produzia (regras por campo violadas, `NEEDS_REVIEW`, `AMBIGUOUS`, falhas pós-LLM, sinalização do LLM), com `QualityReport` por documento e por comparação; cada run de LLM passou a expor `UsageMetrics` (tokens, custo estimado em USD, latência) agregado por `run_id`, em log estruturado e em painel da UI; e a UI foi decomposta em componentes montados por um composition root único. Suíte do projeto após a entrega: 271 passed, 4 skipped (esta feature contribuiu com +38 testes); gate local `ruff + mypy + pytest` verde 3× consecutivas.

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `_reversa_sdd/sdd/policy-analysis.md` | §6.1 Requisitos Funcionais / §8 Design e Interface | componente-novo | Governança aditiva: `Issue`/`QualityReport` (RFs 01/02) derivados dos sinais existentes — mapa sinal→severidade (falha pós-LLM=`CRÍTICO`, regra violada=`ALTO`, `NEEDS_REVIEW`/`AMBIGUOUS`=`MÉDIO`, sinalização do LLM=`BAIXO`); a fachada ganha `list_issues`/`get_quality_report`/`get_comparison_quality_report` |
| `_reversa_sdd/prd.md` | §8 Riscos (R2) / §6 Restrições | componente-novo | R2 deixa de ser risco sem medição: `UsageMetrics` por `run_id` (tokens/custo USD/latência por chamada de extração/explicação), com tabela de preços USD versionada (`PRICE_REFERENCE_DATE = 2026-09-26`); log estruturado `policy_analysis.usage` + painel na UI (RFs 03/04); sem `ModelGateway` (gatelo segue registrado) |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | regra-alterada | Tela do analista passa a ser montada por `src/composition_root/` (wiring único) e decomposta em componentes (upload, estágios, revisão, comparação, export, métricas); fila de revisão agrupada por severidade (`CRÍTICO`→`BAIXO`); teste de arquitetura varre `src/ui` **e** `src/composition_root` (RFs 05/06/07) |
| `_reversa_sdd/sdd/policy-analysis.md` | §9 Modelo de Dados | delta-de-dados | Nenhuma mudança de schema: `Issue`/`QualityReport` derivam de `facts`/`reviews` e `UsageMetrics` vive em log estruturado + memória de processo (decisão registrada em `legacy-impact.md`); as 6 tabelas DuckDB permanecem |
| `_reversa_sdd/sdd/shared-kernel-contracts.md` | §6.1 Requisitos Funcionais | componente-novo | Contrato v1.0.0 intacto: `requires_human_review` permanece e `Issue` é aditivo **fora** do `shared_kernel` (RN-01 — nenhum delta MAJOR/MINOR nesta feature) |

## Regras sob vigilância

Nenhum watch item na tabela principal (cenário greenfield). Observações sem peso de regressão: `O001`..`O008` em `_reversa_forward/004-p1-dev2-experiencia/regression-watch.md`.

## Fontes

- `_reversa_forward/004-p1-dev2-experiencia/requirements.md`
- `_reversa_forward/004-p1-dev2-experiencia/actions.md`
- `_reversa_forward/004-p1-dev2-experiencia/progress.jsonl`
- `_reversa_forward/004-p1-dev2-experiencia/legacy-impact.md`
- `_reversa_forward/004-p1-dev2-experiencia/regression-watch.md`
