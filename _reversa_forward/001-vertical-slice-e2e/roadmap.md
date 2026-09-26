# Roadmap: Vertical Slice E2E — PDF até comparação e tela

> Identificador: `001-vertical-slice-e2e`
> Data: `2026-09-26`
> Requirements: `_reversa_forward/001-vertical-slice-e2e/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Implementar os dois módulos do monólito modular (`document_processing` e `policy_analysis`) na estrutura domain/application/infrastructure/public_api prevista no resumo executivo (§7/§2.2), consumindo os contratos já implementados em `src/shared_kernel` (v1.0.0). O núcleo (domain + application) fica puro e testável sem dependências externas atrás de portas (TextExtractor, OcrEngine, Embedder, VectorIndex, FactRepository, LlmExtractor); as dependências reais (PyMuPDF, PaddleOCR, Qdrant, Gemini, DuckDB, Pydantic AI) vivem só em `infrastructure/**`. A comparação é 100% determinística em código, sem LLM. A tela Streamlit mínima consome exclusivamente as duas fachadas públicas. Os testes usam adapters fake e cobrem a jornada fim a fim; os adapters reais entram marcados como integração (rodáveis quando as dependências estiverem instaladas).

## 2. Princípios aplicados

`.reversa/principles.md` não existe neste projeto (greenfield via `/reversa-new`). Valem como princípios de projeto os definidos no PRD e no resumo executivo:

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| KISS/YAGNI (`_reversa_sdd/prd.md#6`) | Defaults simples do slice (chunking fixo, coleção única, 1 campo demonstrado) sem configuração extra | respeita |
| Isolamento de dependências (`document-processing#7` RNF-06) | Externos só em `infrastructure/**`; núcleo testável com fakes | respeita |
| LLM extrai/explica, jamais compara (`policy-analysis#6.1` RF-06) | Comparação implementada como regras determinísticas puras | respeita |
| Núcleo antes de Integração | Domain puro primeiro, depois application, depois adapters/UI | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | Estrutura por módulo com camadas `domain/`, `application/`, `infrastructure/`, `public_api.py` em `src/modules/<modulo>/` | É o desenho do resumo executivo §7 e das specs (`document-processing#8`, `policy-analysis#8`) | módulo flat; pacote único | 🟢 |
| D-02 | Portas como `Protocol` (typing) em `application/ports.py`, implementadas em `infrastructure/` | Testes determinísticos sem Qdrant/Gemini/PaddleOCR; adapters substituíveis (LlamaIndex fora do slice é substituível) | herança abstrata; mocks de biblioteca | 🟢 |
| D-03 | Chunking fixo por página (800 chars, overlap 100), `section_name=None` | Resposta às OQ-02/OQ-03 do slice (requirements §10) — simples, determinístico, revisável | chunking por seção; semântico | 🟡 |
| D-04 | Limiares: 40 caracteres não-brancos para texto nativo; `ocr_confidence < 0.5` = página ilegível → `REVIEW_REQUIRED` | Resposta à OQ-01 (requirements §10); configurável em constantes do módulo | limiares por ML; fixos embutidos no adapter | 🟡 |
| D-05 | Coleção Qdrant única `policy_chunks` com filtro por `policy_id`/`document_id` | Resposta à OQ-04; recriar coleção não perde fonte (PDFs ficam com o usuário) | 1 coleção por apólice | 🟡 |
| D-06 | Extração com Pydantic AI (`pydantic-ai`) com saída validada contra `ExtractedFact`; retry único + falha classificada | RF-09 policy-analysis: resposta fora do schema nunca vira fato | JSON mode puro; function calling manual | 🟢 |
| D-07 | Idempotência por `document_id`: delete por filtro antes de reindexar (Qdrant) e upsert por chave (DuckDB) | RF-09 document-processing / RN-04 | versionar execuções com IDs novos | 🟢 |
| D-08 | Comparação normaliza valores (`normalized_value` numérico/string) e decide direção com regras puras; `ComparisonId` = `cmp_<uuid4>` | Determinismo (RNF-01) e rastreabilidade (RNF-02) | hash determinístico de conteúdo; LLM comparando | 🟢 |
| D-09 | Export da comparação em Markdown standalone (`exports/<ComparisonId>.md`) | RF-08: abre sem o sistema; formato textual diffável | PDF; HTML; CSV | 🟡 |
| D-10 | Testes: unit do núcleo com fakes + teste E2E da jornada com fakes + testes de arquitetura (imports) + testes de integração reais marcados `integration` (skip sem dependência) | "Tudo testado" sem exigir Docker/API key no CI local | testes só com dependências reais | 🟢 |
| D-11 | UI Streamlit em `src/ui/app.py`, consome só `public_api` dos dois módulos | RF-10; UI fora do núcleo | UI dentro dos módulos; CLI | 🟡 |

## 4. Premissas

Sem `[DÚVIDA]` abertos no requirements. Premissas derivadas das decisões do slice (requirements §10), ajustáveis na PR com Dev 2:

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| Limiares 40 chars / 0.5 OCR são adequados para apólices reais | §10 item 1 | Páginas com texto escasso vão para OCR à toa (custo) ou ilegíveis passam — ajuste pontual de constante |
| Chunking fixo 800/100 atende o retrieval do Dev 2 | §10 item 2 | Evidências muito granulares ou grosseiras — mudar só o chunker |
| Catálogo de 10 field_code reflete o contrato do Dev 2 | §10 item 5 | Renomear/ajustar campos do catálogo — sem impacto nos contratos shared_kernel |
| Export Markdown atende o analista no slice | §10 item 6 | Formato precisa virar PDF/HTML depois — só o gerador de export muda |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `document_processing` | `_reversa_sdd/sdd/document-processing.md#8` | componente-novo | Módulo completo (domain/application/infrastructure/public_api) com fachada `process_document`/`retrieve_evidence` |
| `policy_analysis` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | Módulo completo com fachada `extract_field`/`get_facts`/`compare_policies`/`explain_difference`/`export_comparison` |
| `shared_kernel` | `_reversa_sdd/sdd/shared-kernel-contracts.md#8` | contrato-existente | Consumido como está (v1.0.0, já implementado em `src/shared_kernel`) |
| `ui` (Streamlit) | `_reversa_sdd/prd.md#4` | componente-novo | Tela mínima que consome as duas fachadas |
| `evaluation` | `_reversa_sdd/sdd/evaluation.md#4` | n/a neste slice | Fora do escopo (fase posterior) |

## 6. Delta no modelo de dados

- Resumo das mudanças: primeiro uso real do índice Qdrant (coleção `policy_chunks`, payload com IDs + texto) e criação das tabelas DuckDB `policies`, `documents`, `facts`, `comparisons` (dono Dev 2 na spec, implementadas aqui no slice para provar a jornada). Nenhuma migração — estado inicial.
- Detalhe completo em: `_reversa_forward/001-vertical-slice-e2e/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| n/a — sem contratos HTTP/fila/gRPC/GraphQL; trânsito interno usa `shared_kernel.contracts` v1.0.0 | — | — |

## 8. Plano de migração

n/a — estado inicial (nenhum dado legado).

1. Criar estrutura `src/modules/` + `src/ui/` e módulos de teste.
2. `pip install -r requirements.txt` (+ extras de integração quando disponíveis).
3. Subir Qdrant local (`docker run`) apenas para testes de integração/UI real.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Dependências pesadas (PaddleOCR, PyMuPDF) não instaláveis neste ambiente | médio | médio | Núcleo testado com fakes; adapters reais isolados e cobertos por testes `integration` com skip gracioso |
| Gemas de API (Gemini) indisponível sem chave | médio | alto no dev local | Porta `Embedder`/`LlmExtractor` com fake determinístico nos testes; integração opt-in |
| Catálogo de campos divergente do Dev 2 | baixo | médio | Catálogo isolado em `catalog.py`, mudança localizada; validação na PR |
| Schemas LLM inválidos com frequência | médio | médio | Validação dura + retry único + `NEEDS_REVIEW` (nunca fato sem validação) |
| Latência de retrieval acima de 3s (RNF-01) | baixo | baixo | Medir desde o slice (métrica simples por run); ajuste de `top_k`/chunk depois |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] Suíte de testes verde (`pytest`) cobrindo: contratos, domínio puro, jornada E2E com fakes, arquitetura de imports
- [ ] `regression-watch.md` gerado
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-plan` | reversa |
