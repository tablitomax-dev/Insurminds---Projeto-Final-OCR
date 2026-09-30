# Regression Watch: P1 do Desenvolvedor 2 — Experiência e Governança da Análise

> Identificador: `004-p1-dev2-experiencia`
> Data: `2026-09-26` (ISO 8601)
> Cenário **greenfield** (âncora: `prd.md` + specs SDD): não há regras 🟢 extraídas para vigiar — o watch principal fica vazio e os RFs implementados ficam em "Observações", sem peso de regressão. Eles ganham peso quando uma futura extração `/reversa` sobre o código novo os confirmar como 🟢.

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|---------------------|-------------------|
| — | — | — | — | — |

## Observações (sem peso de regressão)

| ID | Origem | Expectativa observada |
|----|--------|-----------------------|
| O001 | `requirements.md` RF-01 | `Issue`/`QualityReport` derivados apenas dos sinais existentes (regras violadas, `NEEDS_REVIEW`, `AMBIGUOUS`, falhas pós-LLM, sinalização do LLM) — nenhum novo detector |
| O002 | `requirements.md` RF-02 | Fila de revisão agrupada e ordenada `CRÍTICO` → `BAIXO` (`ui/logic.group_by_severity`) |
| O003 | `requirements.md` RF-03 | Cada run de LLM expõe tokens/custo USD/latência por chamada, agregado por `run_id`, no log estruturado e no painel |
| O004 | `requirements.md` RF-04 | Métricas, logs e erros nunca contêm texto de apólice (teste com marcador) |
| O005 | `requirements.md` RF-05/RF-07 | `src/composition_root` é o único wiring; teste de arquitetura varre `src/ui` **e** `src/composition_root` |
| O006 | `requirements.md` RF-06 | UI em componentes (upload, estágios, revisão, comparação, export, métricas) só via fachadas |
| O007 | `requirements.md` RN-01 | `requires_human_review` permanece no contrato `ExtractedFact` — `Issue` é aditivo |
| O008 | `roadmap.md` D-03/D-04 | Métricas por processo + log durável; custo estimado em USD com `PRICE_REFERENCE_DATE` visível; modelo fora da tabela → `None` |

## Histórico de re-extrações

_(vazio — será preenchido quando uma re-extração `/reversa` rodar sobre o código novo)_

## Arquivadas

_(vazio)_
