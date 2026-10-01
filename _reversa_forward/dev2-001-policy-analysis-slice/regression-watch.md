# Regression Watch: Vertical slice do policy_analysis

> Identificador: `dev2-001-policy-analysis-slice`
> Data: `2026-09-26`
> Feature greenfield, sem legado pré-existente. Âncora: `prd.md` + specs SDD (`_reversa_sdd/sdd/`).

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|---------------------|-------------------|

(vazio — não há regras 🟢 extraídas de código pré-existente para vigiar; nada foi extraído de legado ainda.)

## Observações (sem peso de regressão)

RFs implementados da spec `_reversa_sdd/sdd/policy-analysis.md#6.1`, ainda 🟡 PLANEJADO: ganham peso de regressão quando uma futura extração `/reversa` sobre o código novo os confirmar como 🟢.

- W-obs-01 | RF-01 | Evidências só via `document_processing.public_api`; zero imports de internos | presença | `test_architecture.py` falha |
- W-obs-02 | RF-02/RN-05 | Catálogo fechado de 10 `field_code`; fora do catálogo é rejeitado na fronteira | presença | `test_field_catalog.py` falha |
- W-obs-03 | RF-03/RN-02 | Fato FOUND sempre ancorado em `evidence_ids` reais do pedido | presença | `test_extraction_agent.py` falha |
- W-obs-04 | RF-04/RN-03 | AMBIGUOUS/NEEDS_REVIEW entram na fila de revisão com evidência anexa | presença | `test_review_queue.py` falha |
- W-obs-05 | RF-05 | Fatos e comparações em DuckDB com IDs do shared_kernel; upsert idempotente | presença | `test_repository.py` falha |
- W-obs-06 | RF-06/RN-01/RN-06 | Comparação 100% determinística, sem LLM; mesmo par → mesmo `ComparisonId` | presença | `test_comparison.py` falha |
- W-obs-07 | RF-07 | Explicação sem evidência citada dos dois lados é rejeitada | presença | `test_explanation.py` falha |
- W-obs-08 | RF-08 | Export PDF standalone contém os 10 campos, inclusive ausentes | presença | `test_export_pdf.py` falha |
- W-obs-09 | RF-09 | Saída de LLM fora do schema nunca vira fato | presença | `test_extraction_agent.py` falha |
- W-obs-10 | RF-10 | Mesmo fluxo roda com evidências mockadas e reais (porta `EvidenceSource`) | presença | `test_e2e_flow.py` falha |

## Histórico de re-extrações

| Data | Agente | Resultado |
|------|--------|-----------|

(vazio — será preenchido quando `/reversa` rodar de novo sobre o código novo.)

## Arquivadas

(vazio)

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-coding` | reversa |