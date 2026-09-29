# Spec: policy-analysis

**Versão:** 1.0
**Status:** Rascunho
**Autor:** reversa-spec-sdd
**Data:** 2026-09-25
**Reviewers:** Desenvolvedor 2 (dono), pbena (interfaces públicas)

> 🟡 Selo PLANEJADO em todos os itens. Componente do vertical slice (~10 campos críticos, comparação entre 2 apólices) — sofisticações (avaliação completa, relatórios elaborados, múltiplos agentes) ficam fora desta versão.

---

## 1. Resumo

🟡 Este componente é o núcleo de análise do Dev 2: consome `EvidenceRef` recuperado pelo pipeline documental, extrai fatos estruturados por campo com agentes Pydantic AI (LLM extrai e explica, nunca compara), persiste em DuckDB, sinaliza revisão humana, executa a comparação determinística campo a campo entre 2 apólices, gera a explicação das diferenças com evidência anexada e exporta o resumo para defesa da análise.

---

## 2. Contexto e Motivação

**Problema:**
🟡 A comparação de apólices é manual, sem rastreio e sem auditoria de renovação (PRD §1); o resultado atual depende do analista ler PDFs inteiros e confiar de memória.

**Evidências:**
🟡 PRD: métrica de 1 comparação E2E com 100% de evidência anexada em 3 meses; jornada da persona (7 passos) começa a valer de fato quando os fatos extraídos existem; resumo §2.4 exige comparação puramente determinística.

**Por que agora:**
🟡 Com os contratos entregues (Fase 0) e o retrieval em desenvolvimento, este componente destrava a integração Fase 2: `Retrieval real → EvidenceRef → Extração real → ExtractedFact`.

---

## 3. Goals (Objetivos)

- 🟡 **G-01:** Extrair os ~10 campos críticos do vertical slice de uma apólice com `ExtractedFact` sempre ancorado em `evidence_ids`.
- 🟡 **G-02:** Persistir fatos e apólices em DuckDB (schema lógico dono: Dev 2) com IDs consistentes com o shared_kernel e com o Qdrant.
- 🟡 **G-03:** Roteirizar revisão humana: fatos AMBIGUOUS/NEEDS_REVIEW aparecem para o analista e a decisão fica registrada.
- 🟡 **G-04:** Comparar 2 apólices campo a campo por regras determinísticas (maior/menor/igual/ausente), sem LLM na comparação.
- 🟡 **G-05:** Explicar cada diferença com citações de evidência de ambas as apólices e exportar o resumo.

**Métricas de sucesso:**

| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| 🟡 Campos do catálogo extraídos por apólice fixture | 0 | 10 campos com `ExtractedFact` válido | Vertical slice |
| 🟡 Fatos FOUND com evidência | n/a | 100% | Contínuo |
| 🟡 Comparação determinística entre 2 apólices | 0 | 1 E2E com resultado determinístico por campo | Vertical slice |
| 🟡 Fatos sinalizados revisados pelo analista | n/a | 100% dos sinalizados | Vertical slice |

---

## 4. Non-Goals (Fora do Escopo)

- 🟡 **NG-01:** Comparação por similaridade vetorial ou interpretação livre do LLM — proibida (resumo §2.4, PRD §5).
- 🟡 **NG-02:** OCR/indexação/retrieval — tudo via `document_processing.public_api` (resumo §2.2).
- 🟡 **NG-03:** Avaliação completa de qualidade (LLM-as-judge, baterias) — módulo `evaluation` futuro (resumo §13).
- 🟡 **NG-04:** Relatórios sofisticados/branding — o export desta versão é o resumo essencial (PRD §5).
- 🟡 **NG-05:** Tela Streamlit — implementada na camada de aplicação (`app.py`/workflow) no ciclo forward; este componente oferece APIs, sem UI (resumo §7).

---

## 5. Usuários e Personas

**Usuário primário:**
🟡 **Analista de cotação D&O** (persona do PRD): consulta os fatos por campo, revisa os sinalizados, dispara a comparação, lê a explicação com evidência e exporta o resumo para defender a análise.

**Usuário secundário:**
🟡 **Desenvolvedor 1 (pbena)**: consome as assinaturas públicas (`public_api`) para integrar o fluxo de extração ao workflow — sem tocar no interno do módulo.

**Jornada atual (sem a feature):**
🟡 Leitura manual dos 2 PDFs, anotações em planilha, decisão sem rastro verificável.

**Jornada futura (com a feature):**
🟡 1. Fatos extraídos por campo com evidência; 2. revisão das sinalizações; 3. comparação determinística; 4. explicação e export — sem reler os PDFs.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | O sistema deve obter evidências exclusivamente via `document_processing.public_api` (`retrieve_evidence`) e nunca importar internals do módulo documental. | Must | Teste de arquitetura: zero imports em `infrastructure/**` alheia; somente fachada. |
| RF-02 | O sistema deve manter o catálogo dos ~10 `field_code` do vertical slice (ex.: limite agregado, limite por sinistro, franquia, exclusões-chave, vigência) com a semântica documentada de cada campo. | Must | O catálogo é a única fonte de `field_code`; campo fora do catálogo rejeitado na criação de `ExtractionRequest`. |
| RF-03 | O sistema deve extrair cada campo com um agente Pydantic AI que recebe `ExtractionRequest` (evidências + schema_version) e produz `ExtractedFact` validado, com `confidence` e `evidence_ids` dos trechos usados. | Must | Saída sempre válida pelo contrato; LLM não inventa ID de evidência (IDs vêm das evidências recebidas). |
| RF-04 | O sistema deve sinalizar revisão humana: `AMBIGUOUS`/`NEEDS_REVIEW` (ou `requires_human_review=true`) ficam na fila de revisão com a evidência anexa para decisão do analista. | Must | Toda sinalização tem evidência visível; decisão do analista registrada com fato novo ou confirmação. |
| RF-05 | O sistema deve persistir apólices, documentos e fatos em DuckDB com os mesmos identificadores do shared_kernel, usando `ProcessingStatus` para coordenar com o workflow. | Must | Fato consultado em DuckDB tem os mesmos IDs dos chunks Qdrant (0 divergências, resumo §14). |
| RF-06 | O sistema deve comparar 2 apólices campo a campo com regras determinísticas (numérico: maior/menor/igual; texto: igual/ausente; ausente: sinalizado) e retornar o resultado por campo. | Must | Comparação de 2 fixtures idênticas = 100% "igual"; divergências reproduzem o mesmo resultado em execuções repetidas (determinismo). |
| RF-07 | O sistema deve gerar, para cada diferença, uma explicação por LLM que cita evidência de ambas as apólices (`EvidenceRef` de página/trecho), em linguagem para o analista. | Must | Explicação sem evidência citada é rejeitada; citações resolvem para os `evidence_ids` dos fatos. |
| RF-08 | O sistema deve emitir `ComparisonId` único por comparação e exportar o resumo da comparação (por campo: valores, direção da diferença, evidências, explicação) em formato arquivo. | Must | O export contém todos os campos do catálogo, incluindo os ausentes, e abre sem o sistema (arquivo standalone). |
| RF-09 | O sistema deve validar toda saída de LLM contra o schema do contrato antes de aceitar; saída inválada retorna erro classificado para o workflow e gera sinalização de revisão. | Must | Resposta fora do schema nunca vira fato; registrada como falha classificada (reexecutável). |

### 6.2 Fluxo Principal (Happy Path)

🟡 Integração Fase 2 do plano (resumo §11):

1. 🟡 O workflow sinaliza que a apólice está `INDEXED`; o módulo monta `ExtractionRequest(field_code)` com evidências do retrieval.
2. 🟡 O agente do campo extrai e devolve `ExtractedFact` validado (status FOUND com evidências, ou NOT_FOUND/AMBIGUOUS com sinalização).
3. 🟡 O sistema persiste os fatos em DuckDB e publica `ProcessingStatus(stage="FACTS_EXTRACTED")`.
4. 🟡 Para 2 apólices completas, o sistema executa a comparação determinística por campo e persiste o resultado com `ComparisonId`.
5. 🟡 O analista revisa as sinalizações, recebe a explicação por diferença e exporta o resumo para defesa.

### 6.3 Fluxos Alternativos

🟡 **Fluxo Alternativo A — Campo não encontrado na apólice:**
1. Retrieval retorna `evidences=[]` ou o agente não identifica o campo nos trechos.
2. `ExtractedFact(status="NOT_FOUND")` sem evidência — entra na comparação como "ausente" (diferença por omissão).

🟡 **Fluxo Alternativo B — Saída do LLM inválida ou conflitante:**
1. O schema falha ou 2 trechos sustentam valores distintos.
2. Sistema registra falha classificada e reemite com novo run; em AMBIGUOUS, entra na fila de revisão humana (RF-04) — comparação usa o valor revisado ou registra ausência da comparação daquele campo.

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| RNF-01 | Determinismo da comparação | mesma entrada → mesma saída, 100% das execuções | resumo §2.4; sem temperatura/aleatoriedade na comparação |
| RNF-02 | Rastreabilidade | cada fato → evidências; cada comparação → ComparisonId + fato por campo | resumo §14 |
| RNF-03 | Custo de LLM medido | tokens/custo por run registrados (observabilidade mínima via run_id) | resumo §5.5; gateway de modelo compartilhado |
| RNF-04 | Latência de extração por campo | até 30s por campo (single-user) | premissa de custo/latência do PRD (risco R2) |
| RNF-05 | Isolamento | PaddleOCR/Qdrant/DuckDB/Streamlit não citados em domain/application | resumo §2.2 e §7 (importação apenas por public_api) |

---

## 8. Design e Interface

**Componentes afetados:**
🟡 `src/modules/policy_analysis/**` (domain, application, infrastructure, public_api); interfaces expostas por fachada pública; consome `shared_kernel.contracts` versado.

**Comportamento esperado (fachada pública):**

```
PolicyAnalysisFacade (public_api)
  extract_field(policy_id, field_code) -> ExtractedFact           (usa ExtractionRequest interno)
  get_facts(policy_id) -> ExtractedFact[]
  compare_policies(policy_id_a, policy_id_b) -> ComparisonResult  (determinístico, ComparisonId)
  explain_difference(comparison_id, field_code) -> Explanation    (cita EvidenceRef de ambos)
  export_comparison(comparison_id) -> file path do resumo
```

**Estados visíveis:**
- 🟡 Estado vazio: apólice sem fatos = aguardando processamento documental.
- 🟡 Carregamento: extrações em curso por campo (status do workflow).
- 🟡 Erro: falha de LLM/persistência classificada e reexecutável (não silencia).
- 🟡 Sucesso: fato(s) persistidos; comparação idempotente por par de apólices processadas.

---

## 9. Modelo de Dados

**Entidades novas/manipuladas:**
🟡 Tabelas DuckDB (dono: Dev 2): `policies` (policy_id, seguradora, vigência, fonte dos documentos), `documents` (document_id, policy_id), `facts` (fact_id, policy_id, field_code, status, value JSON, normalized_value JSON, confidence, evidence_ids, requires_human_review, revisão humana), `comparisons` (comparison_id, policy_id_a/b, campo, resultado determinístico, evidências e explicação citada). Contratos de trânsito vêm do shared_kernel (ExtractedFact, ProcessingStatus).

**Migrações necessárias:**
🟡 Não — schema DuckDB criado na primeira execução do vertical slice.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| 🟡 document_processing.public_api (retrieval) | Obrigatória | sem evidências → extração fica bloqueada com causa clara |
| 🟡 API Gemini (LLM dos agentes de extração/explicação) | Obrigatória | extração/explicação param; falha classificada e reexecutável (sem fallback de modelo nesta versão) |
| 🟡 DuckDB | Obrigatória | fatos não persistem; comparação segue em memória e perde persistência |
| 🟡 Pydantic AI | Obrigatória | orquestração dos agentes do vertical slice |
| 🟡 shared_kernel.contracts | Obrigatória | mudança major exige os 2 devs |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| EC-01: LLM timeout/429/indisponibilidade | falha externa do provedor | retry configurado com backoff; persistindo a falha → status de revisão; comparação espera fatos definitivos |
| EC-02: Dois trechos sustentam valores distintos | evidências conflitantes | `AMBIGUOUS` + requires_human_review; comparação daquele campo aguarda decisão (fluxo B) |
| EC-03: Campo ausente em uma das apólices | NOT_FOUND | comparação marca "ausente" como diferença por omissão — nunca erro |
| EC-04: Valor não normalizável (unidade/formato estranho) | normalização falha | fato fica NEEDS_REVIEW; comparação sinaliza campo sem valor comparável |
| EC-05: DuckDB indisponível | falha de persistência | extração segue; persistência reexecutável; status reflete a pendência |
| EC-06: Comparação repetida do mesmo par | mesmo par processado | mesmo `ComparisonId`/resultado (idempotência); sem duplicação de registros |
| EC-07: `field_code` fora do catálogo | request inválido | rejeitado na fronteira (RNF/RF-02); nada é extraído |

---

## 12. Segurança e Privacidade

- 🟡 **Autenticação/Autorização:** N/A — componente interno; acesso por fachada pública.
- 🟡 **Dados sensíveis:** trechos de apólice são enviados ao Gemini como parte da extração/explicação — decisão explícita registrada no PRD §6; nenhum texto integral em logs; export contém citações mínimas necessárias para a defesa.
- 🟡 **Auditoria:** fatos e comparações carregam IDs/evidências; revisão humana fica registrada quem/decidiu (run/analista mínimo desta versão).

---

## 13. Plano de Rollout

- 🟡 **Estratégia:** branch `feature/dev2-policy-analysis` (resumo §12.1) com mocks de evidência (Fase 1) e integração real só na Fase 2 (Retrieval real → Extração real) — nunca integrar comparação+relatório+observabilidade de uma vez.
- 🟡 **Rollback:** revert do branch; DuckDB recriável do schema; fatos fixture sintéticos.
- 🟡 **Monitoramento:** taxa de NOT_FOUND por campo, % sinalizado para revisão, custo por run, determinismo da comparação (execuções repetidas idênticas).

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| OQ-01 | Catálogo fechado dos ~10 `field_code`: quais exatamente entram no vertical slice e qual a semântica/normalização de cada um? | Alto | Dev 2 (propõe) + Dev 1 (revisa) | Antes do vertical slice |
| OQ-02 | Estratégia de prompts dos agentes (1 prompt por campo vs 1 agente multi-campo)? | Médio | Dev 2 | Antes do vertical slice |
| OQ-03 | Regras de comparação por tipo de valor (moeda, período, texto livre): tabela de regras inicial. | Alto | Dev 2 + Dev 1 (revisa) | Antes do vertical slice |
| OQ-04 | Formato do export (Markdown? PDF? XLSX?) para a defesa da análise. **RESOLVIDA em 2026-09-26: Markdown standalone (`exports/<ComparisonId>.md`)** — decisão do Dev 2 alinhada ao fluxo de implementação (`_reversa_forward/001-vertical-slice-e2e/` e `001-dev2-policy-analysis-slice/`) | Baixo | Dev 2 + persona | Resolvida |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| 🟡 Comparação 100% por regras; LLM só extrai/explica | comparar por LLM/similaridade | resumo §2.4 + PRD NG — determinismo e auditabilidade |
| 🟡 Fatos persistidos em DuckDB com IDs compartilhados | repositório próprio isolado | consistência DuckDB↔Qdrant exigida pelo resumo §14 |
| 🟡 Sinalização de revisão como parte do fluxo (não exceção) | falhar quando incerto | persona exige "zerar omissões"; revisão humana é 1ª classe no PRD |
| 🟡 Tela fora deste componente (NG-05) | UI dentro do módulo | resumo §7: interfaces ficam na camada de aplicação (app.py/workflow) |
| 🟡 Export mínimo nesta versão (NG-04) | relatórios ricos | vertical slice primeiro (resumo §13) |

---

## Apêndice

### Referências
- [§6 do resumo executivo](../../resumo_executivo_arquitetura_monolito_modular%20(1).md) — responsabilidade do Dev 2
- [§9 do resumo executivo](../../resumo_executivo_arquitetura_monolito_modular%20(1).md) — integração por fachada/workflow/banco
- PRD: `_reversa_sdd/prd.md` — jornada da persona, métricas, restrições
- Spec dos contratos: `_reversa_sdd/sdd/shared-kernel-contracts.md` — `ExtractedFact`, `EvidenceRef`, `ProcessingStatus`

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-09-25 | reversa-spec-sdd | Criação inicial |

### Relatório de avaliação (spec_scorer.py)

```
Score total: 100.0/100 — ⭐ Excelente — Pronta para implementação
Completude 100% · Testabilidade 100% · Clareza 100% · Escopo 100% · Edge Cases 100%
Gaps críticos: nenhum — Iterações: 2 (89.0 → 100.0)
```
