# Regression-Watch: P0 do Desenvolvedor 1 — Documental e RAG

> Identificador: `dev1-002-p0-documental-rag`
> Data: `2026-09-26`
> Feature greenfield: sem regras 🟢 extraídas de legado para vigiar. O watch principal
> fica vazio; as regras implementadas ganham peso quando uma futura re-extração `/reversa`
> sobre o código novo as confirmar como 🟢.

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|---------------------|-------------------|
| — | — | — | — | — |

## Observações (sem peso de regressão)

IDs estáveis para acompanhamento das regras implementadas nesta feature:

| ID | Origem | Regra implementada nesta feature |
|----|--------|----------------------------------|
| O001 | `actions.md` T-2a | Erros/logs nunca carregam texto de apólice (só tipo + estágio + IDs) |
| O002 | `actions.md` D1-P0-1 | Exceções tipadas por porta; retry 3× com backoff só no Gemini (429/5xx); Qdrant sem retry |
| O003 | `actions.md` D1-P0-2 | `RetrievalQuery` honrado por completo: `section_name` filtra na consulta; `field_code` é hint determinístico — nunca descarte silencioso |
| O004 | `actions.md` D1-P0-3 | Lote de embeddings ≤100 por request; sem loop do SDK legado; health-check `FAILED("INDEXING: ...")`; isolamento entre apólices provado com `QdrantClient` mockado |

## Histórico de re-extrações

| Data | Extração | Veredito |
|------|----------|----------|
| — | — | — |

## Arquivadas

| ID | Motivo | Data |
|----|--------|------|
| — | — | — |
