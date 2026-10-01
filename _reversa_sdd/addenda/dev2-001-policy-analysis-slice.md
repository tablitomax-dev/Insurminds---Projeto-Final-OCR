# Adendo 001: dev2-policy-analysis-slice

> Feature: `_reversa_forward/dev2-001-policy-analysis-slice/`
> Entregue por: `/reversa-coding` em 2026-09-26
> Escopo: vertical slice do `policy_analysis` (Dev 2) — extração de fatos, comparação determinística, explicação e export
> Observação: o skill `reversa-sync` não está instalado neste projeto (installer 1.3.3); este adendo segue o contrato documentado nos skills do ciclo forward (nome iniciado pelo `feature-id`, seção Vigência, deltas sobre `_reversa_sdd/`).

## Vigência

- **Vigente desde 2026-09-26.**
- Nenhuma linha de superação. Adendos futuros que mudarem este conteúdo devem registrar a superação aqui.
- **Vínculo (2026-09-26):** existe planejamento complementar do Dev 2 em `_reversa_sdd/learning/plano-acao-dev2.md` (itens `D2-P0-*`..`D2-P2-*`), escrito sobre a implementação paralela do remoto (features `dev1-001-vertical-slice-e2e`, `dev1-002-p0-documental-rag`, `dev2-003-p0-analise-experiencia`). Este adendo e esta feature permanecem vigentes como registro da implementação paralela `dev2-001-policy-analysis-slice` (branch `feature/dev2-policy-analysis-slice`); o mapeamento entrega ↔ plano está nas notas do `actions.md` desta feature. Divergências: **export resolvida em 2026-09-26 → Markdown** (decisão do usuário, alinhada ao fluxo paralelo); decisão de granularidade de specs `feature` (aqui) vs `hybrid` (lá) segue aberta.

## Deltas sobre `_reversa_sdd/sdd/policy-analysis.md`

A spec está marcada 🟡 PLANEJADO; a implementação abaixo confirma e detalha os pontos:

1. **RF-01..RF-10 implementados** em `src/modules/policy_analysis/` (domain, application, infrastructure, public_api). Cobertura: `tests/modules/policy_analysis/` (53 testes + E2E dos 7 cenários Gherkin do requirements).
2. **OQ-01 RESOLVIDA — catálogo fechado de 10 `field_code`** (`domain/field_catalog.py`): `limite_agregado`, `limite_por_sinistro`, `franquia`, `vigencia`, `prazo_notificacao_sinistro`, `extensao_territorial`, `exclusoes_chave`, `limite_defesa_custos`, `retroatividade`, `indice_reajuste` — com tipo de valor (MONEY/NUMBER/PERIOD/DATE/TEXT) e normalização por campo. Ainda pendente de confirmação do Dev 1 (como previsto na spec).
3. **OQ-02 RESOLVIDA — agente multi-campo**: uma chamada de LLM por apólice extrai todos os campos (`infrastructure/llm_agent.py`), não "um agente por campo".
4. **OQ-03 RESOLVIDA — regras de comparação híbridas** (`domain/comparison.py`): numérico/moeda (Decimal, BRL pela taxa injetada)/data por maior-menor-igual; período por duração (janelas iguais em duração mas deslocadas → DIVERGENTE); texto livre igual/divergente após normalização (semântica com o analista); ausente → diferença por omissão.
5. **OQ-04 RESOLVIDA — export standalone**, com os 10 campos inclusive ausentes. **Revisada em 2026-09-26: formato Markdown em `exports/<ComparisonId>.md`** (a escolha inicial da sessão clarify era PDF/fpdf2; a decisão final alinha com o formato e caminho do fluxo paralelo, `_reversa_forward/dev1-001-vertical-slice-e2e/`).
6. **Delta de enum (em relação à spec §6.1/RF-06):** acrescentado o resultado `AGUARDANDO_REVISAO` à comparação — campo cujo fato está `AMBIGUOUS`/`NEEDS_REVIEW` não é comparado até a decisão humana (EC-02/fluxo B), conforme exigido pela própria spec.
7. **Detalhes de implementação fixados:** `fact_id` determinístico (`FAC-<policy_id>-<field_code>`); `ComparisonId` = UUIDv5 do par `(policy_id_a, policy_id_b)` (idempotência EC-06); revisão humana com decisões `CONFIRMADO`/`CORRIGIDO` auditadas (quem/quando); falhas de LLM mapeadas para `ClassifiedError(code, retriable)` + `ProcessingStatus(stage="FAILED")`.

## Fronteiras respeitadas

- `src/shared_kernel/` **não foi modificado** — apenas consumido (contratos da Fase 0).
- `document_processing` é consumido **somente** por `document_processing.public_api` (único arquivo: `infrastructure/document_processing_source.py`), com `MockEvidenceSource` cobrindo o desenvolvimento paralelo até o retrieval real do Dev 1.
- `src/modules/evaluation/` intocado (fora do escopo, NG-03 da spec).
- Camada de aplicação/Streamlit intocada (NG-05).

## Estado atual dos testes

- `tests/contracts/` (Fase 0): 67 testes verdes, zero regressão.
- `tests/modules/policy_analysis/`: 53 testes verdes (unit + E2E).
- Total: 120 testes passando em 2026-09-26.

## Referências

- Requirements/roadmap/actions/auditoria: `_reversa_forward/dev2-001-policy-analysis-slice/`
- Código: `src/modules/policy_analysis/` + `tests/modules/policy_analysis/`

## Histórico

| Data | Evento | Autor |
|------|--------|-------|
| 2026-09-26 | Criação do adendo (convergência da entrega da feature 001) | reversa |