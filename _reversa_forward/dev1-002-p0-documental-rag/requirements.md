# Requirements: P0 do Desenvolvedor 1 — Documental e RAG

> Identificador: `dev1-002-p0-documental-rag`
> Data: `2026-09-26` (ISO 8601)
> Dono: **Desenvolvedor 1** (pipeline documental: PDF → evidências)
> Fonte normativa: `_reversa_sdd/learning/plano-acao-dev1.md` v1.0 (detalhe do "como"), `_reversa_sdd/learning/aprendizados.md` v1.0 (regras F-xx/A-xx, convenções §5)
> Este documento fixa o **escopo e a aceitação**; o plano de ação fixa o **método**. Em conflito, vale o plano de ação para o "como" e este para o "o quê/quando está pronto".

## 1. Objetivo

Fechar os gaps reais do `document_processing` verificados no código em 2026-09-26: bug de contrato vivo no retrieval (F-14), vazamento de texto de apólice em erros (A-13 ressalva), erros sem tipagem por porta e lacunas de lote/health-check na indexação — sem re-implementar o que já está verde.

## 2. Escopo

**Nesta feature:** `D1-P0-1`, `D1-P0-2`, `D1-P0-3`, `T-2a` (parte do Dev 1) — ações detalhadas em `actions.md`.
**Fora:** itens `D1-P1-*`/`D1-P2-*` (backlog, ver plano), PP-Structure, ModelGateway, GitHub Actions.

## 3. Requisitos de aceitação (pronto quando)

| ID | Requisito | Aceitação | Conf. |
|----|-----------|-----------|-------|
| RF-01 | Exceções tipadas por porta (`EmbeddingError`, `IndexingError`, `OcrError`) e retry só no Gemini (3 tentativas, backoff 1s→2s, timeout 30s; 429/5xx) | Teste de backoff (falha 2×, acerta na 3ª) + erro externo vira exceção da porta + teste de arquitetura verde; **sem** retry no Qdrant | 🟢 |
| RF-02 | `RetrievalQuery` honrado por completo: `section_name`/`field_code` implementados como filtro **ou** removidos do contrato via caixa postal — nunca descartados (F-14) | Teste de contrato por parâmetro (todo campo chega à porta `VectorIndex.search`); teste falha se filtro for ignorado | 🟢 |
| RF-03 | Gaps de indexação fechados: (a) isolamento entre apólices provado na consulta; (b) limite de 100 textos por request de embeddings; (c) sem loop do SDK legado; (d) health-check com `FAILED("INDEXING: ...")` | Cada gap (a)-(d) com teste próprio que falha se o gap voltar; nada do que já está verde é refeito | 🟢 |
| RF-04 | Nenhum erro/log carrega texto de apólice (`T-2a`): `_cause` nunca retorna `str(exc)` cru | Teste anti-vazamento: mensagem de erro externa nunca contém texto de chunk | 🟢 |

## 4. Premissas e dependências

- Mudança em contrato compartilhado (ex.: payload do Qdrant) só via **caixa postal** (`aprendizados.md` §5.2): `_reversa_forward/<feature>/contract-delta-*.md` → aceite do Dev 2 (1 dia útil; silêncio = escalada ao humano) → bump de `CONTRACTS_VERSION`.
- Gate `T-1` (ruff + mypy + `python -B -m pytest -q -p no:cacheprovider`) verde antes de todo PR; comando mantido pelo Dev 2, execução obrigatória de ambos.
- Ambiente Windows/PowerShell: consultar `aprendizados.md` Apêndice A antes de comandos de ferramenta externa.

## 5. Fora de escopo (registro)

PP-StructureV3/`section_name` real (NG-01, próxima feature de documento complexo); ModelGateway (gatelo: 2º provedor/consumidor); GitHub Actions (gatelo: remoto estável + 2º dev ativo); prompt injection em PDF (risco aceito registrado); retenção automática plena (mínimo em `T-2b`, do Dev 2).

## 6. Fontes

- `_reversa_sdd/learning/plano-acao-dev1.md` (§2 estado atual verificado; §3 método; §5 ritual)
- `_reversa_sdd/learning/aprendizados.md` (F-01..F-16, A-01..A-16, §5 convenções)
- `_reversa_sdd/learning/benchmark-repos-referencia.md` §2 (resiliência, lote, proveniência)
- `_reversa_sdd/sdd/document-processing.md` (RFs/RNFs do módulo)
