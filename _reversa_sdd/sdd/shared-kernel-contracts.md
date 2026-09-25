# Spec: shared_kernel-contracts

**Versão:** 1.0
**Status:** Rascunho
**Autor:** reversa-spec-sdd
**Data:** 2026-09-25
**Reviewers:** pbena (Desenvolvedor 1), Desenvolvedor 2 (revisão obrigatória de contrato)

> 🟡 Selo PLANEJADO em todos os itens: esta spec descreve o que será construído, ainda não o que existe.

---

## 1. Resumo

🟡 Este componente define e implementa os **contratos compartilhados** do monólito modular em Python: identificadores, evidência, recuperação, extração, processamento, metadados de chunks, convenções de erro e versionamento no pacote `src/shared_kernel/`. São o acordo técnico entre Dev 1 (produz `EvidenceRef`) e Dev 2 (consome `EvidenceRef`, produz `ExtractedFact`), desenvolvidos ANTES de qualquer implementação substancial (resumo executivo §2.3 e §11, Fase 0) e alterados somente com revisão dos dois desenvolvedores.

---

## 2. Contexto e Motivação

**Problema:**
🟡 Dev 1 (pipeline documental/RAG) e Dev 2 (análise/streamlit) modelam evidências, documentos e fatos de formas incompatíveis se cada um criar seus próprios modelos (resumo §5.1). Sem contrato comum, a integração Retrieval→Extração quebra em Fase 2 do plano de desenvolvimento e gera retrabalho.

**Evidências:**
🟡 Resumo executivo (95% de confiança) define os contratos com código Pydantic no §8.1–8.5 e lista conflitos prováveis (`policy_models.py` compartilhado, nomes de metadados divergentes — §6, Conflitos 1 e 2). O PRD (escopo in) exige contratos definidos antes do desenvolvimento.

**Por que agora:**
🟡 Fase 0 do plano de desenvolvimento (resumo §11): "Nenhum desenvolvedor deve iniciar implementação substancial antes dessa fase." O usuário (Dev 1) vai iniciar o desenvolvimento e entregará o contexto delimitado por contratos ao Dev 2.

---

## 3. Goals (Objetivos)

- 🟡 **G-01:** Implementar em `src/shared_kernel/` os 7 identificadores (`PolicyId`, `DocumentId`, `PageId`, `ChunkId`, `FactId`, `ComparisonId`, `RunId`) e os 6 modelos Pydantic (`EvidenceRef`, `RetrievalQuery`, `RetrievalResult`, `ExtractionRequest`, `ExtractedFact`, `ProcessingStatus`, `ChunkMetadata`) — fielmente ao resumo §8.
- 🟡 **G-02:** Definir convenções de erro de contrato (`errors.py`) com uma hierarquia mínima e estável de exceções.
- 🟡 **G-03:** Estabelecer versionamento do contrato (constante `CONTRACTS_VERSION`, regras patch/minor/major e política de mudança exigindo revisão dos 2 devs).
- 🟡 **G-04:** Garantir rejeição imediata de qualquer payload que viole as invariants (page ≥ 1, scores em [0,1], literais fechados).
- 🟡 **G-05:** Fornecer fixtures JSON (1 válida por contrato + payloads inválidos) para os testes de contrato dos dois desenvolvedores.

**Métricas de sucesso:**

| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| 🟡 Contratos do resumo §8 implementados | 0/6 modelos | 6/6 modelos + 7 IDs | Fase 0 (antes do desenvolvimento paralelo) |
| 🟡 Fixtures de contrato | 0 | ≥ 6 válidas + ≥ 6 inválidas | Fase 0 |
| 🟡 Testes de contrato passando | 0 | 100% (suites `tests/contracts/`) | Fase 0 |
| 🟡 Divergência de metadados entre módulos (Conflito 2, resumo §6) | n/a | 0 (metadados só via `ChunkMetadata` versionado) | Fase 2 |

---

## 4. Non-Goals (Fora do Escopo)

- 🟡 **NG-01:** Nenhuma lógica de negócio, serviço ou dependência de infraestrutura no `shared_kernel` (sem LLM, sem Qdrant, sem DuckDB — resumo §12.3/"shared_kernel pequeno").
- 🟡 **NG-02:** Não gera IDs — os `NewType` não encapsulam geração (ex.: UUID); quem cria o ID é o dono da entidade. Geração centralizada é versão futura se necessário.
- 🟡 **NG-03:** Não define schemas por campo da extração (formato interno de `value`/`normalized_value` é domínio do `policy_analysis`, Dev 2).
- 🟡 **NG-04:** `observability.py` (resumo §5.5, §7) fica fora da Fase 0 — observabilidade transversal vira versão futura deste pacote após o vertical slice.
- 🟡 **NG-05:** Não define o workflow/orquestração (camada de aplicação, resumo §5.3) — apenas o dado de status que ele troca.

---

## 5. Usuários e Personas

**Usuário primário:**
🟡 **Desenvolvedor 1 (pbena)** — implementador do contrato e produtor de `EvidenceRef`, `RetrievalQuery/Result`, `ProcessingStatus` (etapas de documento) e `ChunkMetadata` no módulo `document_processing`.

**Usuário secundário:**
🟡 **Desenvolvedor 2** — consumidor de `EvidenceRef` no `policy_analysis` e produtor de `ExtractionRequest`, `ExtractedFact` e `ProcessingStatus` (etapas de fato). Revisa toda mudança de contrato.

**Jornada atual (sem a feature):**
🟡 Cada desenvolvedor modelaria evidência/documento/fato do seu jeito; a integração Retrieval→Extração (Fase 2 do plano) exigiria reescrita de modelos e adapters ad-hoc.

**Jornada futura (com a feature):**
🟡 1. Dev 1 importa `src/shared_kernel/contracts` e produz evidências/fatias de processamento; 2. Dev 2 importa os mesmos contratos e escreve extração/comparação contra eles; 3. A integração de Fase 2 funciona sem adapter porque os dados já fluem no formato acordado.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| 🟡 RF-01 | O sistema deve definir os 7 identificadores como `NewType(str)` exatamente como resumo §8.1: `PolicyId`, `DocumentId`, `PageId`, `ChunkId`, `FactId`, `ComparisonId`, `RunId`. | Must | `from src.shared_kernel.identifiers import *` funciona; cada identificador aceita e expõe `str`. |
| 🟡 RF-02 | O sistema deve definir `EvidenceRef` (Pydantic v2) com os campos e constraints do resumo §8.2: `evidence_id: str`, `policy_id: str`, `document_id: str`, `page_number: int ≥ 1`, `chunk_id/section_name/clause_number: str \| None`, `quoted_text: str (min_length=1)`, `retrieval_score/ocr_confidence: float \| None em [0,1]`, `source_type: Literal["NATIVE_TEXT","PADDLEOCR","PP_STRUCTURE"]`. | Must | Fixture válida instancia; payload com `page_number=0`, `quoted_text=""` ou `retrieval_score=1.5` rejeita com `ValidationError`. |
| 🟡 RF-03 | O sistema deve definir `RetrievalQuery` (`query`, `policy_id?`, `document_id?`, `section_name?`, `field_code?`, `top_k int default 5 em [1,20]`) e `RetrievalResult` (`query`, `evidences: EvidenceRef[]`, `retrieval_run_id`) como no resumo §8.3. | Must | `RetrievalResult` aceita `evidences=[]`; `top_k=0` e `top_k=21` rejeitam. |
| 🟡 RF-04 | O sistema deve definir `ExtractionRequest` (`policy_id`, `field_code`, `evidences`, `schema_version`) e `ExtractedFact` (`fact_id`, `policy_id`, `field_code`, `status: Literal["FOUND","NOT_FOUND","AMBIGUOUS","NEEDS_REVIEW"]`, `value/normalized_value: dict \| None`, `confidence [0,1]`, `evidence_ids`, `requires_human_review: bool`) como no resumo §8.4. | Must | Status fora do literal rejeita; `confidence=-0.1` rejeita; `evidence_ids` vazio é válido APENAS quando `status="NOT_FOUND"` (ver EC-05 — coerência por status, não por contradição). |
| 🟡 RF-05 | O sistema deve definir `ProcessingStatus` (`document_id`, `stage: Literal["RECEIVED","TEXT_EXTRACTED","OCR_COMPLETED","INDEXED","FACTS_EXTRACTED","REVIEW_REQUIRED","COMPLETED","FAILED"]`, `progress [0,1]`, `message?`) como no resumo §8.5. | Must | Os 8 estágios instanciam; `progress=1.1` e `stage="DONE"` rejeitam. |
| 🟡 RF-06 | O sistema deve definir `ChunkMetadata` (contrato versionado, zona de integração 2) com os campos mínimos acordados: `chunk_id`, `document_id`, `policy_id`, `page_number: int ≥ 1`, `chunk_index: int ≥ 0`, `source_type: Literal["NATIVE_TEXT","PADDLEOCR","PP_STRUCTURE"]`, `ocr_confidence: float \| None [0,1]`, `section_name: str \| None`, `metadata_version: str`. | Must | Fixtures válida/inválida (`page_number=0`) comportam-se como RF-02; campo ausente rejeita. |
| 🟡 RF-07 | O sistema deve definir em `errors.py` a hierarquia mínima de erros de contrato: `ContractError(Exception)` base + subclasses `ContractValidationError`, `ContractNotFound`, `ContractVersionMismatch`, todas com `message` e método `to_dict()` estável. | Must | Cada erro é lançável/capturável por `ContractError`; `to_dict()` retorna `{"error": classe, "message": ..., "contract_version": ...}`. |
| 🟡 RF-08 | O sistema deve expor versionamento: `CONTRACTS_VERSION = "1.0.0"` em `src/shared_kernel/` + regra semântica no módulo (patch = correção compatível; minor = campo opcional novo; major = quebra que exige revisão dos 2 devs) e `schema_version` obrigatório em `ExtractionRequest`. | Must | `CONTRACTS_VERSION` importável; docstring do módulo documenta a política. |
| 🟡 RF-09 | O repositório deve conter fixtures JSON em `tests/contracts/fixtures/data/`: 1 válida por contrato (6) + payloads inválidos (`page_number=0`, `retrieval_score=1.5`, `stage="DONE"`, `top_k=25`, `confidence=-0.1`, `quoted_text=""`). | Must | Toda fixture válida carrega; toda fixture em `invalid/` falha a validação. |
| 🟡 RF-10 | O código do pacote `shared_kernel` (`src/shared_kernel/**`) deve importar apenas stdlib + `pydantic` (sem LLM/clientes; ferramentas de dev como pytest/mypy vivem em `tests/` e fora do pacote), mantendo a regra de importação do resumo §7 (`shared_kernel.contracts` e `shared_kernel.identifiers` permitidos a qualquer módulo). | Must | `grep` por imports em `src/shared_kernel/**` não encontra `llamaindex`, `qdrant`, `duckdb`, `streamlit`, `paddleocr`. |

### 6.2 Fluxo Principal (Happy Path)

🟡 Uso do contrato na integração Fase 2 (resumo §11):

1. 🟡 Dev 1 processa um PDF e constrói `EvidenceRef` (fonte OCR/texto nativo) + `ChunkMetadata` por chunk.
2. 🟡 Dev 2 monta `RetrievalQuery` (ex.: `field_code="limit_apolice"`, `policy_id`, `top_k=5`) e o `document_processing` responde `RetrievalResult` com evidências.
3. 🟡 Dev 2 constrói `ExtractionRequest` com `schema_version` e evidências recebidas.
4. 🟡 O agente de extração (Dev 2) produz `ExtractedFact(status="FOUND", evidence_ids=[...])` apontando para as evidências.
5. 🟡 Resultado: fato extraído com evidência verificável de página/trecho, pronto para comparação determinística (que vive em `policy_analysis`, fora desta spec).

### 6.3 Fluxos Alternativos

🟡 **Fluxo Alternativo A — Campo não encontrado:**
1. O retrieval não retorna evidência suficiente (`RetrievalResult.evidences = []`).
2. Dev 2 registra `ExtractedFact(status="NOT_FOUND", value=None, evidence_ids=[])` — sem violar o contrato (regras de coerência por status: seção 11, EC-05).

🟡 **Fluxo Alternativo B — Processamento quebrado:**
1. O OCR falha com documento ilegível.
2. Dev 1 emite `ProcessingStatus(stage="FAILED", progress=<valor parcial>, message="OCR failed: ...")` reexecutável (sem estado novo ad-hoc).

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| 🟡 RNF-01 | Rejeição imediata | `ValidationError` disparada no construtor do modelo | Qualquer payload fora do contrato é rejeitado na fronteira, nunca propagado |
| 🟡 RNF-02 | Estabilidade do pacote | `shared_kernel` ≤ 6 arquivos de código (`__init__`, `identifiers`, `contracts`, `errors`, versão/config) | Se começar a conter serviços/helpers, tornou-se ponto de acoplamento (resumo §12.3) |
| 🟡 RNF-03 | Compatibilidade dos testes de contrato | Suite `tests/contracts` roda em < 10s, sem rede/Docker/LLM | Testes de contrato precisam ser rápidos para rodar em toda PR |
| 🟡 RNF-04 | Segurança | Nenhum dado de apólice real em fixtures | Fixtures usam dados sintéticos fictícios (PRD §6: dados confidenciais de cliente) |
| 🟡 RNF-05 | Rastreabilidade | `retrieval_run_id`, `metadata_version`, `schema_version` presentes nas estruturas | Alinhado aos quality gates (resumo §14: prompts/schemas/contratos versionados) |

---

## 8. Design e Interface

**Componentes afetados:**
🟡 `src/shared_kernel/` (novo pacote), `tests/contracts/` (novo), imports futuros dos módulos `document_processing` (Dev 1) e `policy_analysis`/`evaluation` (Dev 2). Não afeta telas ou endpoints (ainda não existem).

**Comportamento esperado (API dos contratos, fiel ao resumo §8.1–8.5):**

```
identifiers.py
  PolicyId = NewType("PolicyId", str)          (e DocumentId, PageId, ChunkId, FactId, ComparisonId, RunId)

contracts.py (Pydantic v2, BaseModel)
  EvidenceRef { evidence_id, policy_id, document_id, page_number ≥1, chunk_id?, section_name?,
                clause_number?, quoted_text (1..n), retrieval_score? [0,1], ocr_confidence? [0,1],
                source_type: NATIVE_TEXT|PADDLEOCR|PP_STRUCTURE }
  RetrievalQuery { query, policy_id?, document_id?, section_name?, field_code?, top_k: int [1,20]=5 }
  RetrievalResult { query: RetrievalQuery, evidences: EvidenceRef[], retrieval_run_id }
  ExtractionRequest { policy_id, field_code, evidences: EvidenceRef[], schema_version }
  ExtractedFact { fact_id, policy_id, field_code, status: FOUND|NOT_FOUND|AMBIGUOUS|NEEDS_REVIEW,
                  value?: dict, normalized_value?: dict, confidence [0,1], evidence_ids: list[str],
                  requires_human_review: bool }
  ProcessingStatus { document_id, stage: RECEIVED|TEXT_EXTRACTED|OCR_COMPLETED|INDEXED|
                     FACTS_EXTRACTED|REVIEW_REQUIRED|COMPLETED|FAILED, progress [0,1], message? }
  ChunkMetadata { chunk_id, document_id, policy_id, page_number ≥1, chunk_index ≥0, source_type,
                  ocr_confidence? [0,1], section_name?, metadata_version }        🟡 proposta (OQ-01)

errors.py
  ContractError(message) → .to_dict() | ContractValidationError | ContractNotFound | ContractVersionMismatch
```

**Estados da interface (para a futura troca de status na tela — comportamento, não visual):**
- 🟡 Estado vazio: documento sem `ProcessingStatus` = ainda não recebido; a UI não deve assumir progresso.
- 🟡 Estado de carregamento: `RECEIVED`/`TEXT_EXTRACTED`/`OCR_COMPLETED`/`INDEXED` com `progress` parcial.
- 🟡 Estado de erro: `FAILED` com `message` obrigatória no fluxo alternativo B.
- 🟡 Estado de sucesso: `COMPLETED` com `progress=1.0`.

---

## 9. Modelo de Dados

**Entidades novas:**
🟡 Todos os contratos Pydantic acima (ver seção 8 — formato canônico em `contracts.py`). Persistência dos fatos/evidências (DuckDB/Qdrant) NÃO é definida aqui — apenas o formato em trânsito; a duplicação DuckDB↔Qdrant de IDs (resumo §14) será garantida pelos donos das tabelas usarem os mesmos identificadores.

**Migrações necessárias:** 🟡 **Não** — projeto greenfield; nada existe além do `shared_kernel`.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| 🟡 `pydantic` (v2) | Obrigatória | Contratos não compilam; única dependência externa do pacote |
| 🟡 `pytest` (runner dos testes de contrato) | Obrigatória (dev) | Testes não executam |
| 🟡 `mypy` (checagem estática dos NewTypes) | Opcional (dev) | Perda de verificação estática, sem bloqueio |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| 🟡 EC-01: Página inválida | `page_number=0` ou negativo em `EvidenceRef`/`ChunkMetadata` | `ValidationError` imediata no construtor |
| 🟡 EC-02: Score fora do intervalo | `retrieval_score`/`ocr_confidence`/`confidence` < 0 ou > 1 | `ValidationError` imediata |
| 🟡 EC-03: Literais fechados | `stage="DONE"`, `status="OK"`, `source_type="OCR"` | `ValidationError` listando os valores válidos |
| 🟡 EC-04: Texto citado vazio | `quoted_text=""` em `EvidenceRef` | `ValidationError` (mínimo 1 caractere) |
| 🟡 EC-05: `FOUND` sem evidência | `ExtractedFact(status="FOUND", evidence_ids=[])` | 🟡 Rejeitado por `model_validator` (§2.5: evidência obrigatória — OQ-02); `NOT_FOUND` com `evidence_ids=[]` é válido |
| 🟡 EC-06: `requires_human_review=true` | Fato ambíguo com confiança baixa | Válido em qualquer status; a revisão é sinalização, não bloqueio do contrato |
| 🟡 EC-07: Contrato desatualizado | `schema_version` ou `metadata_version` incompatível com `CONTRACTS_VERSION` | O módulo consumidor lança `ContractVersionMismatch` (checagem do workflow, não do Pydantic) |
| 🟡 EC-08: Falha externa genérica | OCR/LLM/Qdrant indisponíveis | NÃO há contrato de erro de infraestrutura em `shared_kernel` (NG-01) — cada módulo mapeia para `ProcessingStatus(stage="FAILED", message=...)` |

---

## 12. Segurança e Privacidade

- 🟡 **Autenticação:** N/A — pacote interno de modelos, sem I/O.
- 🟡 **Autorização:** N/A — acesso via import; governado pela regra de importação do resumo §7.
- 🟡 **Dados sensíveis:** fixtures são sintéticas (apólices fictícias); nenhum dado de cliente entra em `shared_kernel` ou `tests/` (PRD §6).
- 🟡 **Auditoria:** os contratos carregam os ganchos de auditabilidade (`retrieval_run_id`, `evidence_id`, `schema_version`, `metadata_version`); o log de auditoria pertence à camada de workflow (fora do escopo).

---

## 13. Plano de Rollout

- 🟡 **Estratégia:** Fase 0 do plano (resumo §11) — contratos implementados ANTES do desenvolvimento paralelo; PR única em `develop` (ou `feature/dev1-shared-kernel-contracts`) revisada pelos 2 desenvolvedores (regra de PR do resumo §12.2, itens: "Qual contrato foi alterado?" e "Houve mudança de schema?").
- 🟡 **Como reverter (rollback):** revert do commit/PR dos contratos; nenhum módulo pode depender deles antes da Fase 1 (com mocks), portanto o revert é seguro.
- 🟡 **Monitoramento pós-PR:** suite `tests/contracts` verde em CI; qualquer PR futura que toque `src/shared_kernel/**` exige revisão dos 2 devs (ownership "Ambos", resumo §12.3).

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| 🟡 OQ-01 | Os campos propostos de `ChunkMetadata` (RF-06) atendem o Dev 2 para reconstruir contexto do chunk (posição na página, seção)? Falta algo (ex.: `char_offset`, `token_count`)? | Alto | Dev 2 (valida na revisão da PR de contratos) | Antes da Fase 1 |
| 🟡 OQ-02 | Confirmar a regra EC-05: `FOUND` exige `evidence_ids` não-vazio via validator (inferido do §2.5 — evidência obrigatória) | Médio | Dev 1 + Dev 2 | Antes da Fase 1 |
| 🟡 OQ-03 | Nomenclatura de `field_code` (catálogo de ~10 campos do vertical slice) — define-se em spec do `policy_analysis` ou junto aos contratos? | Médio | Dev 1 (propõe) + Dev 2 | Antes da spec de `policy_analysis` |
| 🟡 OQ-04 | `ComparisonId` fica sem contrato de comparação nesta Fase 0 (só o NewType) — suficiente para o Dev 2 começar? | Baixo | Dev 2 | Fase 1 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| 🟡 IDs como `NewType(str)` sem geração centralizada | Classe wrapper com validação de formato; IDs UUID auto-gerados | Fiel ao resumo §8.1; KISS/YAGNI — geração é responsabilidade do dono da entidade (NG-02) |
| 🟡 Todos os contratos em `contracts.py` (sem `result.py` separado nesta fase) | Seguir literalmente a árvore do resumo §7 com `result.py` | `RetrievalResult` é a única classe que iria para `result.py`; arquivo vazio não se justifica (YAGNI) — criar depois se `EvaluationResult` aparecer |
| 🟡 `ChunkMetadata` novo nesta spec (proposta de campos) | Deixar para o Dev 1 definir sozinho | É zona de integração 2 (metadados de chunks, contrato versionado) — sem definição no resumo, precisava de proposta explícita para o Dev 2 revisar (OQ-01) |
| 🟡 `source_type` mantém os 3 literais do resumo (inclui `PP_STRUCTURE`) | Restringir a `NATIVE_TEXT`/`PADDLEOCR` no MVP | O contrato não deve mudar com o vertical slice; PP-Structure é fase posterior e o literal já está reservado |
| 🟡 `FOUND` exige evidência (EC-05 via validator) | Contrato permissivo (validação semântica na aplicação) | Resumo §2.5 torna evidência obrigatória; rejeição imediata no contrato evita fato sem rastro chegar à comparação — sujeito a confirmação (OQ-02) |
| 🟡 `observability.py` fora da Fase 0 | Implementar contrato de observabilidade agora | NG-04 — vertical slice primeiro; observabilidade transversal completa vira evolução do pacote |
| 🟡 Versão semântica `CONTRACTS_VERSION` + regra major = revisão dos 2 devs | Versionar por contrato individual | Um número único é mais simples de checar no startup do workflow (EC-07) |

---

## Apêndice

### Referências
- [§8 do resumo executivo](../../resumo_executivo_arquitetura_monolito_modular%20(1).md) — contratos compartilhados, Fase 0, quality gates
- [_reversa_sdd/prd.md](../prd.md) — escopo, zonas de integração, restrições
- [§13 do resumo executivo](../../resumo_executivo_arquitetura_monolito_modular%20(1).md) — vertical slice (o que os contratos devem suportar no MVP: NATIVE_TEXT/PADDLEOCR, ~10 campos, comparação determinística)

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-09-25 | reversa-spec-sdd | Criação inicial |

---

## Pendências de qualidade

- 🟡 Nenhuma após iteração (ver relatório de avaliação abaixo).

### Relatório de avaliação (spec_scorer.py)

```
Score total: 100.0/100 — ⭐ Excelente — Pronta para implementação

Completude:    100/100 (peso 30%)
Testabilidade: 100/100 (peso 25%)
Clareza:       100/100 (peso 20%)
Escopo:        100/100 (peso 15%)
Edge Cases:    100/100 (peso 10%)

Gaps críticos: nenhum
Sugestões:     nenhuma
Iterações: 3 (75.0 → 75.0 → 100.0)
```
