# Regression-Watch: Vertical Slice E2E

> Identificador: `001-vertical-slice-e2e`
> Data: `2026-09-26`
> Feature greenfield: sem regras 🟢 extraídas de legado para vigiar. O watch principal
> fica vazio nesta primeira entrega; os RFs implementados ganham peso quando uma futura
> extração `/reversa` sobre o código novo os confirmar como 🟢.

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|---------------------|-------------------|
| — | — | — | — | — |

## Observações (sem peso de regressão)

IDs estáveis para acompanhamento dos RFs implementados (specs SDD, confidência 🟡/🟢 de planejamento):

| ID | Origem | RF implementado nesta feature |
|----|--------|-------------------------------|
| O001 | `_reversa_sdd/sdd/document-processing.md#6.1` | RF-01..RF-09 (validação de PDF, texto nativo, OCR, chunking, embeddings/Qdrant idempotente, status por estágio, retrieval, fachada) |
| O002 | `_reversa_sdd/sdd/policy-analysis.md#6.1` | RF-01..RF-09 (fachada documental, catálogo, extração com validação, fila de revisão, DuckDB, comparação determinística, explicação com evidência, ComparisonId + export, validação de saída LLM) |
| O003 | `_reversa_sdd/sdd/shared-kernel-contracts.md#6.1` | Contratos v1.0.0 consumidos sem mudança (RF-01..RF-10 da Fase 0 continuam válidos) |
| O004 | `_reversa_forward/001-vertical-slice-e2e/requirements.md#5` | RF-09 (UI Streamlit mínima) e RF-10 (isolamento de imports) |

## Histórico de re-extrações

| Data | Extração | Veredito |
|------|----------|----------|
| — | — | — |

## Arquivadas

| ID | Motivo | Data |
|----|--------|------|
| — | — | — |
