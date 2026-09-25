# Spec: document-processing

**Versão:** 1.0
**Status:** Rascunho
**Autor:** reversa-spec-sdd
**Data:** 2026-09-25
**Reviewers:** pbena (Desenvolvedor 1, dono), Desenvolvedor 2 (interfaces públicas)

> 🟡 Selo PLANEJADO em todos os itens. Componente do vertical slice (resumo §13) — sofisticações (PP-Structure, tabelas, scoring avançado) ficam fora desta versão.

---

## 1. Resumo

🟡 Este componente é o pipeline documental do Dev 1: recebe PDFs de apólices D&O, extrai texto (nativo ou OCR básico), divide em chunks com metadados versionados, indexa embeddings no Qdrant local e responde consultas de evidência. Seu contrato de saída é `EvidenceRef` + `ProcessingStatus` + `ChunkMetadata` do shared_kernel — o módulo de análise nunca precisa conhecer PaddleOCR, PyMuPDF ou Qdrant (resumo §2.2).

---

## 2. Contexto e Motivação

**Problema:**
🟡 Apólices chegam como PDFs de formatos distintos por seguradora; sem um pipeline documental que normalize tudo em evidências recuperáveis, o Dev 2 não tem de onde extrair fatos com rastro de página/trecho (problema composto do PRD, frente 3).

**Evidências:**
🟡 PRD (§4 escopo in, §9 critérios de aceite) exige processamento visível por apólice e evidência anexada a 100% dos fatos; resumo §6.1 define a responsabilidade e §5.1 a decisão de evidência compartilhada.

**Por que agora:**
🟡 Fase 0 (contratos) está entregue; o vertical slice §13 começa por "PDF simples → texto/chunks → Qdrant → retrieval" para destravar a Fase 2 (primeiro contrato real).

---

## 3. Goals (Objetivos)

- 🟡 **G-01:** Processar um PDF de apólice ponta a ponta: texto por página, chunks, embeddings e índice Qdrant — com `source_type` atribuído a 100% das páginas processadas.
- 🟡 **G-02:** Emitir `ProcessingStatus` visível em todos os estágios do resumo §8.5, com `FAILED` classificado e reexecutável.
- 🟡 **G-03:** Responder `RetrievalQuery` com `RetrievalResult` contendo evidências ranqueadas e `retrieval_run_id`.
- 🟡 **G-04:** Expor fachada pública única (`public_api`) sem vazar infraestrutura (resumo §9.1).
- 🟡 **G-05:** Garantir IDs consistentes (document → page → chunk) entre os metadados e o Qdrant — pré-condição da consistência DuckDB↔Qdrant do resumo §14.

**Métricas de sucesso:**

| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| 🟡 Apólices processadas E2E (fixture sintética) | 0 | 1 apólice com 100% das páginas com texto/chunk | Vertical slice |
| 🟡 Chunks indexados com `ChunkMetadata` versionada | 0 | 100% | Vertical slice |
| 🟡 Consulta de evidência (top-5) | n/a | resposta em até 3s (single-user, máquina local) | Vertical slice |
| 🟡 IDs divergentes Qdrant vs metadados | n/a | 0 | Contínuo |

---

## 4. Non-Goals (Fora do Escopo)

- 🟡 **NG-01:** PP-StructureV3, análise de tabelas e extração de cláusulas estruturadas — fase posterior (resumo §13).
- 🟡 **NG-02:** Interpretação semântica ou extração de fatos — quem extrai é `policy_analysis` (Dev 2, resumo §6.1 "Fora da responsabilidade").
- 🟡 **NG-03:** Scoring avançado de recuperação, reranking e fallback de modelos de embedding — fase posterior.
- 🟡 **NG-04:** Persistência de fatos/apólices em DuckDB — dono é o Dev 2.
- 🟡 **NG-05:** Interface de usuário — upload e status ficam na camada de aplicação (workflow/app), coordenando esta fachada.

---

## 5. Usuários e Personas

**Usuário primário:**
🟡 **Desenvolvedor 2** (consumidor programático via `public_api`): monta `RetrievalQuery`, recebe `RetrievalResult` com `EvidenceRef` utilizáveis para extração e comparação — sem importar nada interno.

**Usuário secundário:**
🟡 **Analista de cotação D&O** (indireto, via workflow/app): acompanha o processamento pelo `ProcessingStatus` e faz upload na tela mínima do vertical slice.

**Jornada atual (sem a feature):**
🟡 O analista lê o PDF inteiro manualmente para achar limites/exclusões; não há evidência endereçável.

**Jornada futura (com a feature):**
🟡 1. Upload do PDF na tela; 2. O workflow chama esta fachada e o status avança por estágio; 3. O Dev 2 consulta evidências por campo com página/trecho confiável.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | O sistema deve aceitar um arquivo PDF de apólice e validá-lo (existência, extensão, tamanho máximo configurável, cabeçalho PDF) antes de processar. | Must | PDF válido entra; arquivo corrompido ou não-PDF recebe `ProcessingStatus(stage="FAILED", message explicando)` sem indexar nada. |
| RF-02 | O sistema deve extrair texto por página com PyMuPDF e atribuir `source_type="NATIVE_TEXT"` às páginas com texto nativo suficiente. | Must | Página com texto extraído vira input de chunk; `source_type` registrado. |
| RF-03 | O sistema deve aplicar OCR básico (PaddleOCR) às páginas sem texto nativo suficiente e atribuir `source_type="PADDLEOCR"` com `ocr_confidence` por página. | Must | 100% das páginas processadas têm `source_type`; páginas ilegíveis sinalizadas (EC-05). |
| RF-04 | O sistema deve dividir o texto de cada página em chunks sequenciais e produzir `ChunkMetadata` versionada (chunk_id, page_number, chunk_index, section_name quando detectável). | Must | Todo chunk indexado tem metadados válidos pelo contrato; `metadata_version` presente. |
| RF-05 | O sistema deve gerar embeddings (Gemini) e indexar chunks no Qdrant local com os mesmos `document_id`/`chunk_id` dos metadados (IDs consistentes, resumo §14). | Must | Consulta ao índice devolve payload com IDs iguais aos de `ChunkMetadata`; 0 divergências. |
| RF-06 | O sistema deve emitir `ProcessingStatus` em cada transição de estágio (RECEIVED → TEXT_EXTRACTED → OCR_COMPLETED → INDEXED) e `FAILED` com causa classificada quando um estágio quebra. | Must | Cada estágio publicado é um `ProcessingStatus` válido; falha de um estágio não avança o próximo sem intervenção. |
| RF-07 | O sistema deve responder `RetrievalQuery(dev 2)` com `RetrievalResult` contendo até `top_k` evidências (score de recuperação em [0,1]) e `retrieval_run_id`. | Must | `top_k` respeitado; evidências válidas pelo contrato; `retrieval_run_id` único por consulta. |
| RF-08 | O sistema deve expor apenas a fachada pública (`process_document`, `retrieve_evidence` — resumo §9.1) e proibir acesso a adaptadores internos a partir de outros módulos. | Must | Teste de arquitetura: nenhum import cross-module em `infrastructure/**`; somente `document_processing.public_api`. |
| RF-09 | O sistema deve ser reexecutável: processar de novo o mesmo documento (mesmo document_id) atualiza/limpa o estado anterior sem duplicar chunks no índice. | Must | Segunda execução deixa o índice com a mesma contagem de chunks da primeira (idempotência). |

### 6.2 Fluxo Principal (Happy Path)

🟡 Integração do vertical slice (resumo §11 Fase 2):

1. 🟡 O workflow recebe o PDF e chama `process_document(document_id, file_path)`.
2. 🟡 O sistema valida o arquivo e publica `ProcessingStatus(stage="RECEIVED")`.
3. 🟡 Por página: texto nativo via PyMuPDF, e quando vazio OCR básico via PaddleOCR — status avança para `TEXT_EXTRACTED`/`OCR_COMPLETED` com progresso parcial.
4. 🟡 O sistema cria chunks por página, gera embeddings Gemini e indexa no Qdrant — status `INDEXED` com progresso proporcional.
5. 🟡 O Dev 2 envia `RetrievalQuery` por campo; o sistema devolve `RetrievalResult` com evidências ranqueadas de página/trecho para extração com `EvidenceRef`.

### 6.3 Fluxos Alternativos

🟡 **Fluxo Alternativo A — Página escaneada (sem texto nativo):**
1. PyMuPDF retorna texto vazio abaixo do mínimo de caracteres.
2. PaddleOCR processa a página; `ocr_confidence` entra em `ChunkMetadata`; `source_type="PADDLEOCR"`.

🟡 **Fluxo Alternativo B — Falha de indexação (Qdrant indisponível):**
1. A chamada ao Qdrant falha com timeout/erro de rede.
2. O sistema publica `ProcessingStatus(stage="FAILED", message="INDEXING: <causa>")` e mantém o estado reexecutável — novo `process_document` do mesmo document_id retoma do estágio anterior (RF-09).

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| RNF-01 | Latência de retrieval (single-user, local) | até 3s por consulta top-5 | Premissa de custo/latência do PRD (risco R2); medir desde o vertical slice |
| RNF-02 | Segurança de entrada | toda entrada validada antes de processar | resumo §14: texto de apólice é dado não confiável; nunca injetado em comandos |
| RNF-03 | Idempotência | reprocessar = mesmo estado final | permite retry sem lixo no índice |
| RNF-04 | Rastreabilidade | todo chunk rastreável a document+página; consulta marcada com run_id | resumo §14 (rastreabilidade) |
| RNF-05 | Confidencialidade | nenhum conteúdo de apólice em logs além do necessário; envio a Gemini é decisão registrada | PRD §6 compliance |
| RNF-06 | Dependência isolada | PaddleOCR/PyMuPDF/Qdrant/LlamaIndex só em `infrastructure/**` | resumo §2.2 (isolar implementações) |

---

## 8. Design e Interface

**Componentes afetados:**
🟡 `src/modules/document_processing/**` (domain, application, infrastructure, public_api) — estrutura do resumo §7; consome contratos do shared_kernel.

**Comportamento esperado (fachada pública, fiel ao resumo §9.1):**

```
DocumentProcessingFacade (public_api)
  process_document(document_id, file_path) -> ProcessingStatus
  retrieve_evidence(query: RetrievalQuery) -> RetrievalResult
```

**Estados visíveis (via ProcessingStatus):**
- 🟡 Estado vazio: documento sem status = não recebido.
- 🟡 Carregamento: estágios intermediários com progress [0,1].
- 🟡 Erro: `FAILED` + mensagem classificada por estágio ("EXTRACT:", "OCR:", "INDEXING:").
- 🟡 Sucesso: índice pronto; retrieval retorna evidências ou lista vazia (nada encontrado não é erro).

---

## 9. Modelo de Dados

**Entidades novas/manipuladas:**
🟡 `ChunkMetadata` (produzida aqui, versão do shared_kernel), `EvidenceRef` (produzida aqui — página/trecho/score/ocr_confidence/source_type), `ProcessingStatus` (emitida aqui), payloads no Qdrant (texto do chunk + IDs). Persistência de fatos em DuckDB NÃO existe neste módulo (NG-04).

**Migrações necessárias:**
🟡 Não — primeiro uso real do índice Qdrant; coleção criada na primeira execução do vertical slice.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| 🟡 Qdrant (Docker local) | Obrigatória | indexação/retrieval param: `FAILED(INDEXING)` + retry manual (fluxo B) |
| 🟡 API Gemini (embeddings) | Obrigatória | chunks não indexados; `FAILED(INDEXING)` com causa; custo medido por run_id |
| 🟡 PyMuPDF | Obrigatória | texto nativo indisponível → OCR cobre (fluxo A) |
| 🟡 PaddleOCR | Obrigatória (páginas escaneadas) | páginas digitais seguem via texto nativo |
| 🟡 LlamaIndex (orquestração de indexação) | Oportunidade | substituível sem mudar contratos (isolado em infrastructure) |
| 🟡 shared_kernel.contracts | Obrigatória | contratos versados (1.0.0); mudança major exige os 2 devs |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| EC-01: PDF corrompido ou não-PDF | cabeçalho/parse inválidos | `ProcessingStatus(FAILED, "EXTRACT: arquivo inválido")`; nada indexado |
| EC-02: Página sem texto e ilegível no OCR | `ocr_confidence` < limiar configurável | página marcada com confidence baixa; documento segue; sinalização no status (EC-05 abaixo) |
| EC-03: Mesmo PDF reenviado (document_id duplicado) | segunda execução | idempotência (RF-09): chunks substituídos, sem duplicação no índice |
| EC-04: Qdrant/Gemini timeout ou 429 | falha externa | `FAILED(INDEXING: <causa>)`; execução reexecutável; sem fallback de modelo (NG-03) |
| EC-05: Documento com páginas ilegíveis | páginas com confiança baixa | `ProcessingStatus(stage="REVIEW_REQUIRED", message listando páginas)` — sinaliza o Dev 2 sem bloquear |
| EC-06: `RetrievalQuery` com top_k máximo | top_k=20 | respeitado; resposta em até 3s (RNF-01) — sem cache nesta versão |
| EC-07: Consulta sem resultados | nenhuma evidência acima do limiar | `RetrievalResult(evidences=[])` válido — consumidor registra `NOT_FOUND` (fluxo alternativo A da spec do contrato) |

---

## 12. Segurança e Privacidade

- 🟡 **Autenticação/Autorização:** N/A — componente interno do monólito; acesso pela fachada pública.
- 🟡 **Dados sensíveis:** conteúdo de apólice tratado como confidencial (PRD §6); envio de trechos ao Gemini e armazenamento no Qdrant local são decisões explícitas registradas; logs não incluem texto integral do chunk.
- 🟡 **Auditoria:** toda consulta e indexação carrega `run_id`/`retrieval_run_id` para reconstrução (resumo §5.5).

---

## 13. Plano de Rollout

- 🟡 **Estratégia:** implementar no branch `feature/dev1-document-processing` (resumo §12.1) em passos do vertical slice: 1 página → 1 documento fixture → índice real.
- 🟡 **Rollback:** revert do branch; o Qdrant é descartável (recriar coleção não perde fonte — PDFs ficam com o usuário).
- 🟡 **Monitoramento:** contagem de chunks por documento, latência de retrieval (RNF-01), taxa de páginas por OCR, custo de embeddings por run.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| OQ-01 | Qual limiar de caracteres/OCR confiança define "texto nativo suficiente" (EC-02) e o limiar de "ilegível"? | Médio | Dev 1 (pbena) | Antes do vertical slice |
| OQ-02 | Estratégia de chunking do vertical slice: tamanho fixo em caracteres por página ou por seção detectável? | Alto | Dev 1 (propõe) + Dev 2 (consome) | Antes do vertical slice |
| OQ-03 | `section_name`: detectar por heurística simples (marcadores do PDF) ou deixar null no vertical slice? | Médio | Dev 1 + Dev 2 | Antes do vertical slice |
| OQ-04 | Política de coleção do Qdrant: 1 coleção única com filtro por policy/document ou 1 coleção por apólice? | Médio | Dev 1 | Antes do vertical slice |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| 🟡 Texto nativo primeiro, OCR por página quando vazio | OCR sempre | Vertical slice §13 "PaddleOCR básico"; OCR só onde necessário reduz custo/latência (PRD R2) |
| 🟡 PaddleOCR básico nesta versão; PP-Structure fora | PP-StructureV3 desde o início | NG-01 — fase posterior (resumo §13) |
| 🟡 Idempotência por document_id (RF-09) | versionar execuções com novos IDs | reprocessar é o fluxo de recuperação natural (EC-03/EC-04) |
| 🟡 Fallback de modelos fora (NG-03) | múltiplos provedores | Gemini é provedor único (decisão da sessão); fallback é fase posterior |
| 🟡 `evidences=[]` como resposta legítima | erro quando nada encontrado | NOT_FOUND é resultado normal do domínio (contrato ExtractedFact) |

---

## Apêndice

### Referências
- [§6 do resumo executivo](../../resumo_executivo_arquitetura_monolito_modular%20(1).md) — responsabilidade do Dev 1 e estrutura de módulos
- [§9 do resumo executivo](../../resumo_executivo_arquitetura_monolito_modular%20(1).md) — integração por fachada e workflow
- [§13 do resumo executivo](../../resumo_executivo_arquitetura_monolito_modular%20(1).md) — vertical slice mínimo
- Spec dos contratos: `_reversa_sdd/sdd/shared-kernel-contracts.md` — contratos `EvidenceRef`, `RetrievalQuery/Result`, `ProcessingStatus`, `ChunkMetadata`

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-09-25 | reversa-spec-sdd | Criação inicial |

### Relatório de avaliação (spec_scorer.py)

```
Score total: 100.0/100 — ⭐ Excelente — Pronta para implementação
Completude 100% · Testabilidade 100% · Clareza 100% · Escopo 100% · Edge Cases 100%
Gaps críticos: nenhum — Iterações: 2 (93.0 → 100.0)
```
