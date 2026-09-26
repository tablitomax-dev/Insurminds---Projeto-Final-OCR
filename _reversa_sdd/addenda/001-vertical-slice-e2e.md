# Adendo: Vertical Slice E2E — PDF até comparação e tela

> Identificador: `001-vertical-slice-e2e`
> Data: `2026-09-26` (ISO 8601)
> Cenário: `greenfield`
> Gerado por `/reversa-sync` após `/reversa-coding` (21/21 ações concluídas)

## Vigência

Vigente desde 2026-09-26.

## Resumo da entrega

O vertical slice do PRD foi implementado de ponta a ponta: um PDF de apólice D&O entra, vira evidências recuperáveis (texto nativo/OCR → chunks → índice vetorial), depois fatos estruturados extraídos com evidência, uma comparação determinística entre 2 apólices e uma tela Streamlit mínima para o analista — com export standalone. 21 de 21 ações do `actions.md` concluídas; suíte de testes com 137 testes verdes (4 de integração real pulados quando as dependências externas estão ausentes).

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `_reversa_sdd/prd.md` | §4. Escopo (in) | componente-novo | A jornada de 7 passos está implementada no slice (1 campo extraído + 1 comparação + tela); leia como "prova fim a fim disponível em `src/modules/**` e `src/ui/app.py`" |
| `_reversa_sdd/sdd/document-processing.md` | §6.1 Requisitos Funcionais | componente-novo | RF-01..RF-09 implementados em `src/modules/document_processing/` (domain/application/infrastructure/public_api); fachada `process_document`/`retrieve_evidence` real, não mais apenas planejada |
| `_reversa_sdd/sdd/document-processing.md` | §14. Open Questions | componente-novo | OQ-01..OQ-04 resolvidas com defaults do slice: limiar 40 caracteres / OCR 0.5, chunking fixo 800/100, `section_name=null`, coleção única `policy_chunks`; ver `_reversa_forward/001-vertical-slice-e2e/requirements.md#10` |
| `_reversa_sdd/sdd/policy-analysis.md` | §6.1 Requisitos Funcionais | componente-novo | RF-01..RF-09 implementados em `src/modules/policy_analysis/`; comparação determinística com 7 direções (`maior`/`menor`/`igual`/`ausente_a`/`ausente_b`/`ausente_ambas`/`divergente`); extração demonstrada com `limite_agregado` |
| `_reversa_sdd/sdd/policy-analysis.md` | §9. Modelo de Dados | componente-novo | Tabelas DuckDB criadas conforme `data-delta.md` da feature, com ajustes: PK de `comparisons` = `(comparison_id, field_code)` e tabela extra `evidences`; catálogo dos 10 `field_code` definido em `domain/catalog.py` |
| `_reversa_sdd/sdd/shared-kernel-contracts.md` | §6.1 Requisitos Funcionais | componente-novo | Contratos v1.0.0 consumidos sem nenhuma mudança (sem delta MAJOR); `ExtractedFact` com EC-05 é a base da validação de saída de LLM |
| `_reversa_sdd/sdd/evaluation.md` | §4. Non-Goals | componente-novo | Sem delta nesta entrega: avaliação automatizada continua fase posterior, como previsto |

## Regras sob vigilância

Nenhum watch item na tabela principal (cenário greenfield, sem regras 🟢 extraídas de legado). Observações sem peso de regressão: `O001`, `O002`, `O003`, `O004` em `_reversa_forward/001-vertical-slice-e2e/regression-watch.md`.

## Fontes

- `_reversa_forward/001-vertical-slice-e2e/requirements.md`
- `_reversa_forward/001-vertical-slice-e2e/roadmap.md`
- `_reversa_forward/001-vertical-slice-e2e/data-delta.md`
- `_reversa_forward/001-vertical-slice-e2e/actions.md`
- `_reversa_forward/001-vertical-slice-e2e/progress.jsonl`
- `_reversa_forward/001-vertical-slice-e2e/legacy-impact.md`
- `_reversa_forward/001-vertical-slice-e2e/regression-watch.md`
