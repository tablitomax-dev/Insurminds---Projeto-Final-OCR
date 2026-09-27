# Requirements: P1 do Desenvolvedor 2 — Experiência e Governança da Análise

> Identificador: `004-p1-dev2-experiencia`
> Data: `2026-09-26`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA
> Dono de execução: **Desenvolvedor 2** (itens `D2-P1-1`, `D2-P1-2`, `D2-P1-4` de `_reversa_sdd/learning/plano-acao-dev2.md#§3`)

## 1. Resumo executivo

A feature entrega governança e experiência ao analista de cotação D&O: problemas de qualidade passam a existir como `Issue` com severidade (fila de revisão agrupada por prioridade), cada execução de extração/explicação expõe métricas de tokens, custo estimado e latência (`UsageMetrics`, por `run_id`), e a tela do analista passa a ser montada por um composition root único, decomposta em componentes que consomem apenas as fachadas públicas. Resolve três pendências do backlog P1: a fila sem priorização (sem severidade), o risco R2 do PRD sem medição de custo/latência, e a montagem ad hoc da UI.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/prd.md#§8 Riscos` | Risco R2 (custo/latência de Gemini + OCR) tem como mitigação "medir custo/latência desde o vertical slice" — hoje não há medição; `D2-P1-2` fecha essa lacuna | 🟡 |
| `_reversa_sdd/prd.md#§6 Restrições` | Viés de custo baixo, uso single-user: métrica de custo é o instrumento de controle | 🟡 |
| `_reversa_sdd/prd.md#§9 Critérios de aceite` | Revisão humana confirmar/corriger com resultado registrado — já entregue (adendo 003); esta feature **agrega severidade** ao fluxo, sem reescrevê-lo | 🟢 |
| `_reversa_sdd/sdd/policy-analysis.md#§6.1 Requisitos Funcionais` | Fila de revisão e validação pós-extração existem; não há modelo de problema de qualidade com severidade | 🟢 |
| `_reversa_sdd/sdd/policy-analysis.md#§9 Modelo de Dados` | Tabelas DuckDB + tabela `reviews` (adendo 003); `QualityReport` se apoia nesse modelo, sem novo contrato externo | 🟢 |
| `_reversa_sdd/addenda/003-p0-dev2-analise-experiencia.md#Impacto por artefato` | Estado pós-P0 vigente: guardas pós-LLM, loop humano Confirmar/Corrigir/Registrar, golden set 20 casos, UI via fachadas | 🟢 |
| `_reversa_sdd/learning/plano-acao-dev2.md#D2-P1-1` | Origem do escopo: `Issue`/`QualityReport` **aditivo**, `requires_human_review` permanece no contrato | 🟢 |
| `_reversa_sdd/learning/plano-acao-dev2.md#D2-P1-2` | `UsageMetrics` local no adapter; **sem `ModelGateway`** nesta rodada (gatelo registrado); embeddings fora desta conta | 🟢 |
| `_reversa_sdd/learning/plano-acao-dev2.md#D2-P1-4` | Composition root único; UI em componentes; nenhum SQL/Qdrant/prompt na UI | 🟢 |
| `_reversa_sdd/learning/aprendizados.md#§5 Convenções de coordenação` | Gate `T-1`, caixa postal para contrato, registro de decisões, marco de PR | 🟢 |
| `_reversa_sdd/sdd/shared-kernel-contracts.md#§6.1 Requisitos Funcionais` | Contrato v1.0.0 permanece íntegro: `Issue` é aditivo ao lado do contrato, não substitui `ExtractedFact`/`requires_human_review` | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Analista de cotação D&O (`_reversa_sdd/personas.md#Persona 1`) | Revisar fatos extraídos da apólice com prioridade clara | O analista abre a fila de revisão, vê os problemas agrupados por severidade, resolve os críticos primeiro e confirma/corrige cada fato |
| Analista de cotação D&O | Controlar custo e espera da análise | Após rodar a extração de uma apólice, o analista vê tokens, custo estimado e latência daquele run |
| Desenvolvedor do time | Manter a UI sem recair em imports proibidos | Ao alterar a UI, o teste de arquitetura reprova qualquer import de `infrastructure`/`domain` alheio |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** `Issue` (severidade, `field_code`, motivo, `EvidenceRef`) é **aditivo** ao modelo: `requires_human_review` permanece no contrato; qualquer remoção ou substituição exige caixa postal MAJOR (`_reversa_sdd/learning/aprendizados.md#§5.2`). 🟢
   - Origem no legado: `_reversa_sdd/learning/plano-acao-dev2.md#D2-P1-1`
   - Tipo: nova
2. **RN-02:** `Issue` tem escala de severidade fixa em enum de 4 níveis — `CRÍTICO | ALTO | MÉDIO | BAIXO` (falha dura = `CRÍTICO`; ruído informativo = `BAIXO`) — coberta por teste; a fila de revisão é agrupada e ordenada por severidade. 🟢
   - Origem no legado: `_reversa_sdd/learning/plano-acao-dev2.md#D2-P1-1` (define severidade, não define a escala); escala decidida na sessão de esclarecimentos de 2026-09-26
   - Tipo: nova
3. **RN-03:** Métricas de uso (`UsageMetrics`) são **locais por `run_id`**: tokens, custo estimado e latência por chamada de LLM de extração/explicação, no log estruturado. Custo estimado é expresso em **USD** e reproduzível a partir dos tokens e de uma tabela de preços **versionada no código, com data de referência**. Sem `ModelGateway` nesta rodada; fallback de modelo continua fora do escopo (não-objetivo do PRD). 🟢
   - Origem no legado: `_reversa_sdd/learning/plano-acao-dev2.md#D2-P1-2`; `_reversa_sdd/prd.md#§8 Riscos` (R2)
   - Tipo: nova
4. **RN-04:** A montagem de dependências acontece em **um único composition root**; a UI consome apenas fachadas públicas e não executa SQL, não fala com o índice vetorial e não monta prompts. 🟢
   - Origem no legado: `_reversa_sdd/learning/plano-acao-dev2.md#D2-P1-4`; `_reversa_sdd/addenda/003-p0-dev2-analise-experiencia.md#Impacto por artefato` (UI já via fachadas — esta regra formaliza e estrutura)
   - Tipo: alterada
5. **RN-05:** Métricas, logs e erros **nunca contêm texto de apólice** — apenas tipo de erro, estágio e identificadores. 🟢
   - Origem no legado: `_reversa_sdd/learning/aprendizados.md` (`T-2a`); adendos 002/003 (sanitização vigente)
   - Tipo: alterada (estende a sanitização às métricas)

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Cada problema de qualidade detectado vira um `Issue` (severidade, `field_code`, motivo, `EvidenceRef`) e um `QualityReport` agregado fica disponível por documento e por comparação | Must | Teste cobre cada valor de severidade; fachada pública devolve `Issue` e `QualityReport` para um documento/processamento com problema conhecido; os sinais geradores são **os já existentes no pipeline** (regras por campo violadas, `NEEDS_REVIEW`, falhas de ancoragem/validação pós-LLM) — nenhum novo detector nesta rodada | 🟢 |
| RF-02 | A fila de revisão na UI é agrupada e ordenada por severidade | Must | Com uma fila contendo severidades distintas, a UI exibe os grupos na ordem da severidade; teste de componente cobre a ordenação | 🟢 |
| RF-03 | Cada run de extração/explicação expõe `UsageMetrics` (tokens, custo estimado em USD, latência por chamada), agregado por `run_id`, no log estruturado e em painel simples na UI | Must | Após um run, os dados de tokens/custo/latência existem por chamada e no agregado por `run_id`, e a UI exibe o painel com o último run; sem chamada de LLM não há métrica (estado vazio tratado) | 🟢 |
| RF-04 | Métricas e erros do run não contêm texto de apólice | Must | Teste anti-vazamento: rodar extração com fato de apólice conhecido e provar que `UsageMetrics`, logs e erros não contêm o texto da apólice | 🟢 |
| RF-05 | Um composition root único monta as fachadas; a UI recebe as dependências dele | Must | Não existe montagem de dependências espalhada pela UI; teste de arquitetura cobre `src/ui` e o composition root | 🟢 |
| RF-06 | A UI do analista fica decomposta em componentes (upload, estágios, revisão, comparação, export) consumindo apenas fachadas | Must | Cada componente tem responsabilidade única verificável; nenhum SQL/consulta vetorial/prompt na UI; a jornada do `_reversa_forward/001-vertical-slice-e2e/onboarding.md` funciona sem pular etapa | 🟢 |
| RF-07 | O teste de arquitetura garante `src/ui` (e o composition root) sem imports de `infrastructure`/`domain` alheios | Must | Um import proibido inserido em `src/ui` reprova o teste de arquitetura | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Privacidade | Métricas, logs e erros sem conteúdo de apólice (RN-05) | `_reversa_sdd/learning/aprendizados.md` (`T-2a`); adendos 002/003 | 🟢 |
| Observabilidade | Log estruturado por `run_id` com tokens/custo/latência por chamada | Mitigação do risco R2 (`_reversa_sdd/prd.md#§8 Riscos`) | 🟡 |
| Desempenho | Instrumentação de métricas é local: sem chamada de rede extra e sem latência perceptível na UI | Viés de custo baixo (`_reversa_sdd/prd.md#§6 Restrições`) | 🟡 |
| Custo | Custo estimado do run é visível desde a primeira execução | `prd.md#§8` R2: "medir custo/latência desde o vertical slice" | 🟢 |
| Manutenibilidade | Toda regra arquitetural tem teste que varre todo o alvo | Falha F-15 (`_reversa_sdd/learning/aprendizados.md`) | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Fila de revisão agrupada por severidade
  Dado uma fila de revisão com fatos em severidades diferentes
  Quando o analista abre a fila de revisão
  Então os problemas aparecem agrupados e ordenados por severidade
  E cada problema mostra field_code, motivo e evidência associada

Cenário: Run de extração expõe métricas de uso
  Dado um run de extração de apólice com chamadas de LLM
  Quando o run termina
  Então existem métricas de tokens, custo estimado (USD) e latência por chamada
  E o agregado do run_id está disponível no log estruturado
  E a UI exibe painel simples com os dados do último run

Cenário: Jornada completa sem pular etapa com composition root
  Dado a UI montada pelo composition root
  Quando o analista executa a jornada do onboarding (upload → estágios → revisão → comparação → export)
  Então cada etapa funciona consumindo apenas fachadas públicas

Cenário negativo: métrica e erro não vazam texto de apólice
  Dado um run cuja apólice contém um texto marcador conhecido
  Quando o run termina com sucesso ou com erro
  Então nenhum métrica, log ou mensagem de erro contém o texto marcador

Cenário negativo: import proibido na UI reprova a arquitetura
  Dado a UI e o teste de arquitetura
  Quando um import de infrastructure ou domain alheio é adicionado em src/ui
  Então a suíte de arquitetura reprova
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (`Issue`/`QualityReport`) | Must | Sem problema tipado e priorizado, a fila de revisão não escala para os 10 campos × múltiplas regras |
| RF-02 (fila por severidade) | Must | Entrega direta de valor ao analista; "pronto quando" definido no plano `D2-P1-1` |
| RF-03 (`UsageMetrics`) | Must | Mitigação formal do risco R2 do PRD, que exige medição desde o slice |
| RF-04 (anti-vazamento em métrica) | Must | Regra absoluta de higiene de dados sensíveis (`T-2a`) |
| RF-05 (composition root) | Must | Prende a montagem de dependências num único lugar (F-15) |
| RF-06 (UI em componentes) | Must | Escopo definido em `D2-P1-4`; sem isso a UI volta a acumular regra |
| RF-07 (teste de arquitetura) | Must | Regra arquitetural sem teste cobrindo todo o alvo é intenção (F-15) |
| RNF de desempenho | Should | Instrumentação local; relevante mas não bloqueia a entrega |

## 9. Esclarecimentos

### Sessão 2026-09-26

- **Q:** Qual escala de severidade o enum de `Issue` deve usar? — **R:** 4 níveis em pt-br, padrão de análise de risco: `CRÍTICO | ALTO | MÉDIO | BAIXO` (falha dura = `CRÍTICO`; ruído informativo = `BAIXO`).
- **Q:** Onde as `UsageMetrics` ficam visíveis nesta rodada? — **R:** Log estruturado por `run_id` **+ painel simples na UI** (tokens/custo/latência do último run).
- **Q:** Quais sinais geram `Issue` nesta rodada? — **R:** Apenas os sinais já existentes no pipeline (regras por campo violadas, `NEEDS_REVIEW`, falhas de ancoragem/validação pós-LLM); nenhum novo detector.
- **Q:** Como o "custo estimado" do run é expresso? — **R:** Em **USD**, com tabela de preços versionada no código e data de referência.

## 10. Lacunas

- 🔴 Premissa R1/R3 do PRD segue aberta: validação com apólices reais/anonimizadas é a tarefa externa `D2-P1-3`, **fora desta feature** — esta entrega não se declara validada em campo (ressalva já registrada no golden set, adendo 003).
- 🟡 Fallback de modelo e `ModelGateway` seguem deliberadamente fora do escopo (gatelo registrado em `D2-P1-2`); se surgir 2º provedor ou 2º consumidor, abrir caixa postal de contrato.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-requirements` | reversa |
| 2026-09-26 | Sessão `/reversa-clarify`: escala de severidade, superfície de métricas, fontes de `Issue` e forma de custo decididas | reversa + pbena |
