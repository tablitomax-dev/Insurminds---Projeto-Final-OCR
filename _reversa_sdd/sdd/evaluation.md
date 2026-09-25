# Spec: evaluation

**Versão:** 1.0
**Status:** Rascunho
**Autor:** reversa-spec-sdd
**Data:** 2026-09-25
**Reviewers:** Desenvolvedor 2 (dono), pbena (revisor)

> 🟡 Selo PLANEJADO em todos os itens. O PRD classifica avaliação completa como fase posterior (NG-08); esta spec define o esqueleto mínimo coeso para o módulo existir no monólito conforme o resumo §7 — nada de baterias de avaliação ou LLM-as-judge nesta versão.

---

## 1. Resumo

🟡 `evaluation` é o módulo que mede, com casos de referência, a qualidade da extração e da comparação do sistema: dado um conjunto sintético de apólices com fatos esperados, compara os `ExtractedFact` produzidos contra os esperados e produz um relatório simples de acertos por campo. No vertical slice, o módulo existe como pacote + fachada mínima; o uso real completo é fase posterior.

---

## 2. Contexto e Motivação

**Problema:**
🟡 Sem medição, regressões na extração (prompt alterado, OCR variável) passam despercebidas até a comparação final — exatamente o tipo de omissão que a persona não pode aceitar (PRD, objetivo 3).

**Evidências:**
🟡 Resumo §7 prevê o módulo `evaluation` na estrutura do monólito; PRD §5 adia a avaliação completa para depois do vertical slice; resumo §14 pede validação por Pydantic e rastreabilidade — medição é parte do gate de qualidade.

**Por que agora:**
🟡 O monólito modular é definido agora; criar o esqueleto com limites claros evita que medições ad-hoc invadam `policy_analysis` depois (KISS: um lugar para medir).

---

## 3. Goals (Objetivos)

- 🟡 **G-01:** Módulo `evaluation` presente na estrutura com `public_api` mínima e sem depender de implementações internas de outros módulos.
- 🟡 **G-02:** Definir o formato do caso de referência (apólice sintética + fatos esperados por `field_code`) versionado.
- 🟡 **G-03:** Definir o cálculo de acerto por campo e por execução, com resultado validado por Pydantic.
- 🟡 **G-04:** Estabelecer o limite desta versão: nenhuma bateria completa, nenhum LLM-as-judge (PRD NG-08).

**Métricas de sucesso:**

| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| 🟡 Casos de referência mínimos | 0 | 2 apólices sintéticas × 10 campos = 20 casos | Antes da fase posterior |
| 🟡 Execução da suíte de avaliação mínima | 0 | 1 execução produz relatório por campo (< 60s) | Fase posterior |
| 🟡 Regressões capturadas por mudança de prompt | n/a | 100% dos casos divergentes sinalizados | Fase posterior |

---

## 4. Non-Goals (Fora do Escopo)

- 🟡 **NG-01:** LLM-as-judge — fase posterior (PRD §5).
- 🟡 **NG-02:** Baterias de avaliação automatizadas em CI — fase posterior.
- 🟡 **NG-03:** Datasets reais de clientes — apenas dados sintéticos (PRD §6).
- 🟡 **NG-04:** Dashboards/relatórios visuais — relatório em arquivo estruturado somente.
- 🟡 **NG-05:** Avaliação do OCR/retreival isoladamente nesta versão — foco nos fatos extraídos (a camada de evidência tem seus próprios fixtures, spec do shared_kernel).

---

## 5. Usuários e Personas

**Usuário primário:**
🟡 **Desenvolvedor 2**: antes de mudar um prompt ou regra, roda a avaliação e vê o impacto por campo — evita regressão silenciosa nos ~10 campos.

**Usuário secundário:**
🟡 **Desenvolvedor 1 (pbena)**: consome os relatórios para validar que mudanças de chunking/OCR não degradaram a extração.

**Jornada atual (sem a feature):**
🟡 Mudança de prompt é validada olho a olho na comparação manual — regressões aparecem tarde.

**Jornada futura (com a feature):**
🟡 1. Executar avaliação contra os casos de referência; 2. ler o relatório por campo; 3. decidir entre avançar ou revisar a mudança.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | O sistema deve definir o caso de referência versionado: apólice sintética (texto fixture do documento) + fatos esperados por `field_code` com valores normalizados. | Must | Caso de referência carregável e validado por Pydantic; `reference_version` presente. |
| RF-02 | O sistema deve executar a extração sobre o caso de referência via fachada pública do `policy_analysis` (sem importar internals). | Must | Extração roda no fluxo real do vertical slice; nada duplicado dentro do módulo. |
| RF-03 | O sistema deve comparar fato extraído vs fato esperado por campo com regras determinísticas (igual/diferente/ausente), reaproveitando as mesmas regras de comparação da análise. | Must | Relatório com resultado por campo; mesma entrada → mesmo relatório (determinismo). |
| RF-04 | O sistema deve produzir relatório estruturado por execução (run_id, casos, acertos por campo, divergências com os dois valores) em arquivo. | Must | Relatório abre sem o sistema; divergência sempre traz extraído esperado. |
| RF-05 | O sistema deve expor apenas a fachada pública mínima (`run_evaluation(reference_set) -> report`) na estrutura do monólito. | Must | Nenhum outro módulo importa internals de evaluation. |
| RF-06 | O sistema deve validar todos os artefatos (caso, relatório) contra contratos Pydantic versionados do shared_kernel quando transportarem fatos (`ExtractedFact`). | Must | Artefato fora do contrato rejeita na fronteira. |

### 6.2 Fluxo Principal (Happy Path)

🟡 Uso mínimo previsto para a fase posterior:

1. 🟡 O desenvolvedor prepara o conjunto de referência (2 apólices sintéticas, 10 campos, valores esperados).
2. 🟡 Chama a fachada pública de avaliação com o conjunto.
3. 🟡 O módulo executa a extração real sobre o fluxo do vertical slice.
4. 🟡 O módulo compara extraído vs esperado por campo e escreve o relatório (arquivo + run_id).
5. 🟡 Resultado: relatório por campo com divergências sinalizadas para decisão.

### 6.3 Fluxos Alternativos

🟡 **Fluxo Alternativo A — Caso de referência inválido:**
1. Referência fora do contrato (campo sem valor esperado normalizado).
2. Avaliação rejeita o conjunto na fronteira com erro classificado — nada é executado.

🟡 **Fluxo Alternativo B — Falha do provedor durante a avaliação:**
1. A extração real falha (timeout/429 do LLM).
2. O relatório marca os campos afetados como "não avaliados: falha externa" e o run_id permite reexecução — nunca conta falha externa como erro de extração.

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| RNF-01 | Determinismo do relatório | mesma entrada → mesmo relatório | regras de comparação compartilhadas com policy_analysis |
| RNF-02 | Tempo da avaliação mínima | até 60s para 20 casos (single-user) | execução local, custo controlado |
| RNF-03 | Isolamento | avaliação consome apenas fachadas públicas | resumo §7 (regra de importação) |
| RNF-04 | Rastreabilidade | relatório carrega run_id e reference_version | resumo §14 |

---

## 8. Design e Interface

**Componentes afetados:**
🟡 `src/modules/evaluation/**` (esqueleto: domain, application, public_api sem infrastructure própria nesta versão). Consome `policy_analysis.public_api` e `shared_kernel.contracts`.

**Comportamento esperado:**

```
EvaluationFacade (public_api)
  run_evaluation(reference_set) -> EvaluationReport (arquivo + run_id)
```

**Estados visíveis:**
- 🟡 Estado vazio: nenhum conjunto de referência registrado.
- 🟡 Erro: causa classificada (referência inválida / falha externa), com campos "não avaliados".
- 🟡 Sucesso: relatório por campo com resultado determinístico.

---

## 9. Modelo de Dados

**Entidades novas/manipuladas:**
🟡 `ReferenceCase` (apólice sintética + fatos esperados), `EvaluationReportEntry` (field_code, extraído, esperado, resultado), `EvaluationReport` (run_id, reference_version, entradas). Persistência própria mínima (caches de relatório em arquivo) — sem DuckDB novo (fatos continuam no módulo de análise).

**Migrações necessárias:**
🟡 Não — módulo novo, sem estado herdado.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| 🟡 policy_analysis.public_api | Obrigatória | avaliação não roda (sem extra real); relatório marca "não avaliado" |
| 🟡 API Gemini (via fluxo real de extração) | Obrigatória nos casos reais | fluxo alternativo B sinaliza "não avaliado: falha externa" |
| 🟡 shared_kernel.contracts | Obrigatória | contratos versados; major exige os 2 devs |
| 🟡 pydantic | Obrigatória | validação de casos e relatórios |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| EC-01: Referência fora do contrato | campo esperado sem valor normalizado | rejeição na fronteira com erro classificado; nada executa (fluxo A) |
| EC-02: Provedor indisponível (timeout/429) | falha externa durante extração | campo marcado "não avaliado: falha externa"; run_id para reexecução; nunca conta como erro de extração |
| EC-03: Fato AMBIGUOUS no extraído | extração sinalizada | campo marcado "inconclusivo" com apontamento para a revisão — nunca conta como acerto |
| EC-04: Conjunto com campo repetido | mesmo field_code 2× na referência | rejeitado na carga (uniqueness por campo) |
| EC-05: Caso de referência modificado sem versionar | reference_version antigo | relatório registra a versão usada; divergência entre versões fica explicitamente comparável |

---

## 12. Segurança e Privacidade

- 🟡 **Autenticação/Autorização:** N/A — componente interno.
- 🟡 **Dados sensíveis:** apenas apólices sintéticas; nenhum dado de cliente em casos de referência ou relatórios (PRD §6, NG-03).
- 🟡 **Auditoria:** relatório carrega run_id + reference_version para reproduo exato da execução.

---

## 13. Plano de Rollout

- 🟡 **Estratégia:** esqueleto entra junto do vertical slice (estrutura e fachada); uso com 20 casos quando a extração dos 2 documentos fixture estiver estável — fase posterior ao MVP.
- 🟡 **Rollback:** revert do branch; nenhum dado persistido relevante.
- 🟡 **Monitoramento:** nº de divergências por campo entre versões de prompt/regra — sinaliza regressão antes de chegar ao analista.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| OQ-01 | As 2 apólices sintéticas de referência: elaboradas a partir de templates reais (anonimizados) ou inventadas do zero? | Médio | Dev 2 + Dev 1 | Antes da fase posterior |
| OQ-02 | Criterio de acerto de texto livre (exclusões): substring exato ou semelhança mínima definida por regra? | Alto | Dev 2 (propõe) + Dev 1 | Antes da fase posterior |
| OQ-03 | Avaliação também cobre o OCR (camada de evidência) em versão futura? | Baixo | Dev 1 | Fase posterior |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| 🟡 Esqueleto do módulo agora; uso real depois do MVP | módulo inteiro agora | PRD NG-08 (fase posterior), estrutura do monólito existe desde o resumo §7 |
| 🟡 Reuso das regras de comparação da análise | regras duplicadas no evaluation | determinismo único (resumo §2.4); uma fonte de verdade |
| 🟡 Falha externa ≠ erro de extração no relatório | contar tudo como erro | medir qualidade real — falha de provedor não é regressão (EC-02) |
| 🟡 Sem LLM-as-judge nesta versão | judge desde já | PRD NG-08 — judge é fase posterior, com critério documentado |

---

## Apêndice

### Referências
- [§7 do resumo executivo](../../resumo_executivo_arquitetura_monolito_modular%20(1).md) — estrutura do monólito e regra de importação
- [§13 do resumo executivo](../../resumo_executivo_arquitetura_monolito_modular%20(1).md) — avaliação completa como fase posterior
- PRD: `_reversa_sdd/prd.md` — non-goals e personas
- Spec policy-analysis: `_reversa_sdd/sdd/policy-analysis.md` — regras de comparação reaproveitadas

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-09-25 | reversa-spec-sdd | Criação inicial |

### Relatório de avaliação (spec_scorer.py)

```
Score total: 100.0/100 — ⭐ Excelente — Pronta para implementação
Completude 100% · Testabilidade 100% · Clareza 100% · Escopo 100% · Edge Cases 100%
Gaps críticos: nenhum — Iterações: 2 (91.0 → 100.0)
```
