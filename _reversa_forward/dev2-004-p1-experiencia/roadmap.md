# Roadmap: P1 do Desenvolvedor 2 — Experiência e Governança da Análise

> Identificador: `dev2-004-p1-experiencia`
> Data: `2026-09-26`
> Requirements: `_reversa_forward/dev2-004-p1-experiencia/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Três deltas independentes sobre o núcleo de análise já entregue (adendo 003): (a) um modelo puro de qualidade — `Issue` (com enum `CRÍTICO | ALTO | MÉDIO | BAIXO`) e `QualityReport` — **derivado dos sinais que o pipeline já detecta** (regras por campo violadas, `NEEDS_REVIEW`, falhas de ancoragem/validação), sem novo detector e sem tabela nova; (b) `UsageMetrics` instrumentado localmente no adapter de LLM (`llm_extractors.py`), com tabela de preços USD versionada no código, exposto em log estruturado por `run_id` e em painel simples na UI; (c) um composition root único (`src/composition_root/`) que monta as fachadas, com a UI decomposta em componentes consumindo só fachadas, e o teste de arquitetura varrendo `src/ui` e o composition root. `requires_human_review` e o contrato v1.0.0 permanecem intactos (mudança aditiva).

## 2. Princípios aplicados

`.reversa/principles.md` não existe neste projeto (verificação em 2026-09-26). As normas vigentes são as convenções de `_reversa_sdd/learning/aprendizados.md#§5` e as regras absolutas dos planos de ação:

| Norma | Como a feature se relaciona | Status |
|-------|------------------------------|--------|
| `aprendizados.md` §5.2 (caixa postal) | Nenhuma mudança de contrato nesta feature — `Issue` é aditivo fora do `shared_kernel` | respeita |
| `aprendizados.md` §5.3 (gate `T-1`) | Gate executado antes do PR | respeita |
| Plano Dev 2 §4.3 ("LLM jamais decide quem cobre mais") | `Issue`/`QualityReport` são determinísticos, derivados de sinais já validados | respeita |
| Plano Dev 2 §4.5 (sem SQL/regra escondida na UI) | Composition root + componentes de UI só via fachadas | respeita |
| Plano Dev 2 §4.8 (nunca interpolar exceção crua) | Métricas e erros do painel seguem `T-2a` (tipo + estágio + IDs) | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|---------------|--------------------------|-------------|
| D-01 | `Issue`/`QualityReport` como modelos puros em `policy_analysis/domain/quality.py`, **derivados** dos sinais existentes (`rule_violations` em `value`, `NEEDS_REVIEW`, falhas de ancoragem/validação pós-LLM) | Escopo fechado no clarify ("nenhum novo detector"); determinismo (A-08); sem duplicar estado já persistido | Novos detectores de qualidade; tabela `issues` no DuckDB | 🟢 |
| D-02 | Enum de severidade `CRÍTICO \| ALTO \| MÉDIO \| BAIXO` | Decidido na sessão de clarify de 2026-09-26 (4 níveis pt-br, padrão análise de risco) | `ERROR/WARNING/INFO`, escalas em inglês | 🟢 |
| D-03 | `UsageMetrics` por chamada (tokens, custo USD, latência) coletado no adapter `llm_extractors.py`, agregado por `run_id`; log estruturado + retenção em memória do último run para o painel | Escopo `D2-P1-2` (instrumentação local; sem `ModelGateway`); o painel da UI precisa de leitura imediata em sessão single-user | `ModelGateway` (gatelo registrado); tabela DuckDB de métricas (persistência além do necessário nesta rodada) | 🟡 |
| D-04 | Tabela de preços do Gemini em **USD** como constante versionada no código, com data de referência visível no painel | Decidido no clarify; reproducibilidade do custo estimado | Conversão BRL (exige manter câmbio); só tokens sem valor monetário | 🟢 |
| D-05 | Composition root em `src/composition_root/` montando `create_default_document_processing` e `create_default_policy_analysis` num só lugar; `src/ui` recebe as fachadas dele | `D2-P1-4`; fecha de vez o padrão F-15 (montagem espalhada) | Montagem por módulo da UI; factory global no `public_api` | 🟢 |
| D-06 | UI decomposta em `src/ui/components/` (upload, estágios, revisão, comparação, export, painel de métricas) | Responsabilidade única; "pronto quando" do `D2-P1-4` (jornada do onboarding sem pular etapa) | Manter `app.py` monolítico | 🟢 |
| D-07 | Teste de arquitetura estendido para varrer `src/composition_root/` além de `src/ui` | Regra arquitetural só é real com teste cobrindo todo o alvo (F-15) | Confiar em revisão de PR | 🟢 |
| D-08 | Fila de revisão agrupada por severidade no componente de revisão (ordem `CRÍTICO`→`BAIXO`) | RF-02; decisão de UX do clarify | Ordenação por data apenas | 🟢 |

## 4. Premissas

Nenhuma premissa derivada de `[DÚVIDA]` — a sessão de esclarecimentos de 2026-09-26 fechou os quatro pontos abertos (severidade, superfície de métricas, fontes de `Issue`, forma de custo). Premissas de contexto (não resolvíveis em clarify):

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| Métricas retidas em memória do processo bastam ao painel nesta rodada (single-user, sem restart frequentes) | §10 Lacunas (registro) | Painel vazio após restart do servidor — mitigado pelo log estruturado persistente |
| Golden set e testes existentes (233 passed) continuam verdes sem mudança de contrato | §2 Contexto | Retrabalho se algum teste assumir a UI monolítica |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `policy_analysis/domain/quality.py` | `_reversa_sdd/sdd/policy-analysis.md#§8 Design e Interface` | componente-novo | Modelos puros `Issue` (severity, field_code, reason, evidence_ref) e `QualityReport` |
| `policy_analysis/application/quality.py` | `_reversa_sdd/sdd/policy-analysis.md#§6.1 Requisitos Funcionais` | componente-novo | Deriva `Issue` dos sinais existentes e agrega `QualityReport` por documento/comparação |
| `policy_analysis/domain/metrics.py` | `_reversa_sdd/prd.md#§8 Riscos` (R2) | componente-novo | Modelo `UsageRecord`/agregado por `run_id` (tokens, custo USD, latência) |
| `policy_analysis/infrastructure/llm_extractors.py` | `_reversa_sdd/sdd/policy-analysis.md#§10 Integrações e Dependências` | regra-alterada | Instrumentação local: cada chamada de extração/explicação registra `UsageRecord` |
| `policy_analysis/infrastructure/pricing.py` | `_reversa_sdd/prd.md#§6 Restrições` (viés custo baixo) | componente-novo | Tabela de preços USD versionada, com data de referência |
| `policy_analysis/public_api.py` | `_reversa_sdd/sdd/policy-analysis.md#§8 Design e Interface` | regra-alterada | Novos métodos de fachada: `list_issues`, `get_quality_report`, `get_usage_metrics` |
| `src/composition_root/` | `_reversa_sdd/prd.md#§4 Escopo (in)` | componente-novo | Montagem única das fachadas para UI e ferramentas |
| `src/ui/app.py` + `src/ui/components/` | `_reversa_sdd/prd.md#§4 Escopo (in)` (adendo 003) | regra-alterada | Decomposição em componentes; painel de métricas; fila agrupada por severidade |
| `tests/architecture/test_imports.py` | `_reversa_sdd/learning/aprendizados.md` (F-15) | regra-alterada | Varredura estendida a `src/composition_root/` |

## 6. Delta no modelo de dados

- Resumo das mudanças: **nenhuma mudança de schema** — `Issue`/`QualityReport` são derivados de `facts`/`reviews` já persistidos; `UsageMetrics` vive em log estruturado + memória de sessão (decisão D-03). `requires_human_review` e as 6 tabelas DuckDB permanecem iguais.
- Detalhe completo em: `_reversa_forward/dev2-004-p1-experiencia/data-delta.md`

## 7. Delta de contratos externos

Nenhum contrato externo (HTTP/fila/gRPC/GraphQL) afetado. Diretório `interfaces/` omitido. Mudança no contrato do `shared_kernel`: **nenhuma** (aditividade de `Issue` acontece fora do contrato — RN-01).

## 8. Plano de migração

n/a (sem mudança de schema nem de contrato). Sequência de refactor segura:

1. Implementar `quality.py` e `metrics.py` (modelos puros + testes) sem tocar na UI
2. Instrumentar `llm_extractors.py` + `pricing.py` (testes com fake de LLM)
3. Criar `src/composition_root/` e apontar `src/ui/app.py` para ele (teste de arquitetura verde em cada passo)
4. Decompor a UI em componentes; adicionar painel de métricas e agrupamento por severidade
5. Rodar o gate `T-1` completo + jornada do onboarding

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| `Issue` derivado não reflete histórico de problemas já corrigidos (fato corrigido deixa de gerar `Issue`) | médio | média | Comportamento aceito nesta rodada: `Issue` descreve o estado atual; decisões passadas continuam auditáveis em `reviews`; tabela histórica é item futuro registrado |
| Métricas em memória somem com restart do servidor | baixo | alta | Log estruturado persiste por `run_id`; o painel declara que mostra o último run **do processo atual** |
| Refactor da UI quebrar a jornada do onboarding | alto | média | Decomposição por etapas (item 3 e 4 do plano de migração), teste de arquitetura verde a cada passo, jornada E2E executada antes do PR |
| Tabela de preços USD desatualizada distorcer o custo estimado | baixo | alta | Data de referência visível no painel e no log; custo é "estimado" por definição (RN-03) |
| Painel de métricas vazar texto de apólice | alto | baixo | RF-04 com teste anti-vazamento específico para métricas/painel (`T-2a`) |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] Gate `T-1` (`ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider`) verde 3× consecutivas
- [ ] RF-01..RF-07 do `requirements.md` com teste que falha se o requisito regredir
- [ ] `regression-watch.md` gerado
- [ ] `/reversa-sync` executado ao final (adendo na extração)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-plan` | reversa |
