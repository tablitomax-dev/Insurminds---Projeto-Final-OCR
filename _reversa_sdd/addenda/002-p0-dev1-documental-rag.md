# Adendo: P0 do Desenvolvedor 1 — Documental e RAG

> Identificador: `002-p0-dev1-documental-rag`
> Data: `2026-09-26` (ISO 8601)
> Cenário: `greenfield`
> Gerado por `/reversa-sync` após a implementação das ações P0 (`T-2a`, `D1-P0-1`, `D1-P0-2`, `D1-P0-3` — 4/4 concluídas)

## Vigência

Vigente desde 2026-09-26.

## Resumo da entrega

Os gaps reais do `document_processing` (verificados no código em 2026-09-26) foram fechados: erros nunca carregam texto de apólice (sanitização), exceções ficaram tipadas por porta com retry resiliente só no Gemini, o `RetrievalQuery` passou a ser honrado por completo (o bug F-14 descartava `section_name`/`field_code` em silêncio) e a indexação ganhou os gaps de lote/health-check/isolamento provados por teste. Suíte do projeto após a entrega: 233 passed, 4 skipped (esta feature contribuiu com +36 testes).

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `_reversa_sdd/sdd/document-processing.md` | §6.1 Requisitos Funcionais | componente-novo | Retrieval (RF-07/RF-08) agora honra o contrato inteiro: `section_name` filtra no metadata filter e `field_code` é hint determinístico da busca; erros são tipados por porta e sanitizados (RNF de confidencialidade materializada — nada de texto de apólice em erro/log) |
| `_reversa_sdd/sdd/document-processing.md` | §7 RNFs / §9 Modelo de Dados | regra-nova | Indexação: lote de embeddings ≤100 textos por request, sem loop do SDK legado, health-check fail-fast com `FAILED("INDEXING: ...")`; isolamento entre apólices provado com `QdrantClient` mockado (`query_filter` na consulta) |
| `_reversa_sdd/sdd/shared-kernel-contracts.md` | §6.1 Requisitos Funcionais | componente-novo | Contrato v1.0.0 intacto — mudança é de consumo: `RetrievalQuery` (RF-03) passou a ser integralmente honrado; antes `section_name`/`field_code` eram descartados em silêncio pelo serviço |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | regra-alterada | A jornada de ingestão fica mais confiável em PDF real: retry em 429/5xx do Gemini (3 tentativas, backoff 1s→2s, timeout 30s; Qdrant sem retry — idempotência já cobre); ver `legacy-impact.md` da feature |

## Regras sob vigilância

Nenhum watch item na tabela principal (cenário greenfield). Observações sem peso de regressão: `O001`..`O004` em `_reversa_forward/002-p0-dev1-documental-rag/regression-watch.md`.

## Fontes

- `_reversa_forward/002-p0-dev1-documental-rag/requirements.md`
- `_reversa_forward/002-p0-dev1-documental-rag/actions.md`
- `_reversa_forward/002-p0-dev1-documental-rag/progress.jsonl`
- `_reversa_forward/002-p0-dev1-documental-rag/legacy-impact.md`
- `_reversa_forward/002-p0-dev1-documental-rag/regression-watch.md`
