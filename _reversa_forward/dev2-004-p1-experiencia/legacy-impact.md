# Legacy Impact: P1 do Desenvolvedor 2 — Experiência e Governança da Análise

> Identificador: `dev2-004-p1-experiencia`
> Data: `2026-09-26` (ISO 8601)
> Feature **greenfield**, sem legado pré-existente. Âncora: `prd.md` + specs SDD (`_reversa_sdd/sdd/`).
> Política de edição do legado no momento da execução: `allowLegacyEdits: true`; `allowedPaths` = `["src/**", "tests/**", "pyproject.toml", "requirements.txt", ".gitignore"]` (todas as escritas desta feature casaram com a lista).

## Arquivos afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|-----------------|------------|------|------------|---------------|
| `src/modules/policy_analysis/domain/quality.py` | `_reversa_sdd/sdd/policy-analysis.md#§8 Design e Interface` | componente-novo | MEDIUM | Modelos puros `Issue`/`QualityReport` + enum de severidade (RN-01/RN-02) |
| `src/modules/policy_analysis/application/quality.py` | `_reversa_sdd/sdd/policy-analysis.md#§6.1 Requisitos Funcionais` | componente-novo | MEDIUM | Derivação dos sinais existentes + `QualitySignalLog` (RF-01) |
| `src/modules/policy_analysis/domain/metrics.py` | `_reversa_sdd/prd.md#§8 Riscos` (R2) | componente-novo | LOW | `UsageRecord`/`UsageSummary`/`UsageMetricsCollector` (RF-03) |
| `src/modules/policy_analysis/infrastructure/pricing.py` | `_reversa_sdd/prd.md#§6 Restrições` | componente-novo | LOW | Tabela de preços USD versionada com data de referência |
| `src/modules/policy_analysis/application/extraction.py` | `_reversa_sdd/sdd/policy-analysis.md#§6.1` | regra-alterada | LOW | `LlmOutputError` passa a registrar sinal CRÍTICO no `QualitySignalLog` antes de propagar (comportamento externo idêntico) |
| `src/modules/policy_analysis/infrastructure/llm_extractors.py` | `_reversa_sdd/sdd/policy-analysis.md#§10 Integrações e Dependências` | regra-alterada | LOW | Instrumentação local de métricas (tokens/custo/latência) + log estruturado sem texto de apólice |
| `src/modules/policy_analysis/public_api.py` | `_reversa_sdd/sdd/policy-analysis.md#§8 Design e Interface` | regra-alterada | MEDIUM | Fachada ganha `list_issues`/`get_quality_report`/`get_comparison_quality_report`/`get_usage_metrics` (aditivo) |
| `src/composition_root/` (`__init__.py`, `root.py`) | `_reversa_sdd/prd.md#§4 Escopo (in)` | componente-novo | MEDIUM | Wiring único `build_facades()` (D2-P1-4, fecha F-15) |
| `src/ui/app.py` | `_reversa_sdd/prd.md#§4 Escopo (in)` | regra-alterada | MEDIUM | Vira orquestrador fino sobre o composition root + componentes |
| `src/ui/logic.py` | `_reversa_sdd/prd.md#§4 Escopo (in)` | componente-novo | LOW | Lógica pura de UI (agrupamento por severidade, formatação de métricas) sem `streamlit` |
| `src/ui/components/` (6 módulos + `__init__.py`) | `_reversa_sdd/prd.md#§4 Escopo (in)` | componente-novo | MEDIUM | upload, estágios, comparação, export, revisão (fila por severidade), métricas |
| `tests/architecture/test_imports.py` | `_reversa_sdd/learning/aprendizados.md` (F-15) | regra-alterada | LOW | Varredura estendida a `src/composition_root` |
| `tests/modules/policy_analysis/test_quality.py`, `test_metrics.py` | specs `policy-analysis`/`prd.md` | componente-novo | — | Modelos, derivação, instrumentação e anti-vazamento |
| `tests/ui/test_review_grouping.py`, `test_metrics_panel.py` | `prd.md#§4` | componente-novo | — | Helpers puros da UI |
| `tests/e2e/test_governance_journey.py` | `prd.md#§9` | componente-novo | — | Jornada de governança ponta a ponta |

## Diff conceitual por componente

- **policy-analysis (domínio/aplicação):** nasce a camada de **governança aditiva** — `Issue`/`QualityReport` derivados de sinais que o pipeline já produzia (violações de regra, `NEEDS_REVIEW`, `AMBIGUOUS`, falhas pós-LLM, sinalização do LLM). Nada do fluxo de extração/revisão/comparação muda de comportamento; a única costura é o registro do sinal CRÍTICO em `QualitySignalLog` quando `LlmOutputError` dispara.
- **policy-analysis (infraestrutura):** o adapter de LLM passa a medir cada chamada (tokens/latência/custo) e emitir log estruturado; a estimativa de custo usa tabela USD versionada (`PRICE_REFERENCE_DATE = 2026-09-26`).
- **composição/UI:** o wiring das fachadas centraliza-se no `composition_root`; a UI decompõe-se em componentes com responsabilidade única e lógica pura testável em `src/ui/logic.py`; a fila de revisão agrupa-se por severidade e ganha painel de métricas.

## Preservadas

Nenhuma regra 🟢 extraída foi alterada: o contrato `shared_kernel` v1.0.0 permanece intacto (`requires_human_review` no lugar — RN-01), o loop de revisão Confirmar/Corrigir/Registrar (adendo 003) segue como estava e a comparação continua determinística (LLM jamais decide "quem cobre mais").

## Modificadas

Nenhuma regra 🟢 removida ou alterada; as linhas `regra-alterada` da tabela acima são extensões aditivas de superfície (fachada, instrumentação, composição da UI) sem mudança de semântica do que já existia.
